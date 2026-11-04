"""Statische Extraktoren mit UML-Modellen aus Repositories vergleichen, deren Umfang vorher festgelegt wurde.

Die Werte messen die Übereinstimmung mit den Diagrammen aus den Repos. Ob der
Quelltext vollständig korrekt gelesen wurde, zeigen sie nicht. Unbekannte oder
mehrdeutige Zuordnungen zwischen Modell und Code werden gemeldet und nicht
geraten.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent.parent
# Alle Pfade in den JSON-Dateien der Lindholmen-Auswahl sind relativ zu diesem Ordner.
DATA=ROOT/'daten'/'lindholmen'
TOOLS=ROOT/'werkzeuge'
RESULTS=ROOT/'ergebnisse'/'messungen'

def local(s):return s.rsplit('}',1)[-1].rsplit(':',1)[-1]
def attr(e,key):
    return next((v for k,v in e.attrib.items() if local(k)==key or k=='xmi.'+key),None)
def kind(e):
    return next((local(v) for k,v in e.attrib.items() if local(k)=='type' and ':' in v),local(e.tag))
def read(p):
    raw=p.read_bytes()
    for enc in ('utf-8','cp1252','latin-1'):
        try:return raw.decode(enc)
        except UnicodeDecodeError:pass
def edge(s,t,k):
    return (*sorted((s,t)),k) if k=='association' else (s,t,k)

def reference(path):
    root=ET.parse(path).getroot()
    parents={c:p for p in root.iter() for c in p}
    ids={attr(e,'id'):e for e in root.iter() if attr(e,'id')}
    nodes={i:{'name':e.get('name'),'kind':kind(e)} for i,e in ids.items()
           if kind(e) in ('Class','Interface','Enumeration','AssociationClass') and e.get('name')}
    edges=set();unresolved=[]
    def owner(e):
        while e in parents:
            e=parents[e]
            if attr(e,'id') in nodes:return attr(e,'id')
        return None
    def type_id(e):
        val=e.get('type') or e.get('participant')
        if val:return val
        for c in e.iter():
            if c is e:continue
            if local(c.tag)=='type' or kind(c) in ('Class','Interface'):
                v=attr(c,'idref') or c.get('href','').split('#')[-1]
                if v:return v
        return None
    def add(s,t,k,origin):
        if s in nodes and t in nodes:edges.add(edge(s,t,k))
        elif s or t:unresolved.append({'source':s,'target':t,'kind':k,'origin':origin})
    for e in root.iter():
        k=kind(e);origin=attr(e,'id')
        if k in ('Generalization','generalization') and not attr(e,'idref'):
            add(e.get('child') or owner(e),e.get('general') or e.get('parent'),'inheritance',origin)
        elif k in ('InterfaceRealization','interfaceRealization'):
            add(e.get('client') or owner(e),e.get('contract') or e.get('supplier'),'realization',origin)
        elif k in ('Association','AssociationClass'):
            ends=[ids[i] for i in e.get('memberEnd','').split() if i in ids]
            if not ends:ends=[x for x in e.iter() if kind(x) in ('AssociationEnd','ownedEnd')]
            targets=[type_id(x) for x in ends]
            if len(targets)==2:add(*targets,'association',origin)
            else:unresolved.append({'origin':origin,'kind':k,'reason':'non-binary or missing ends'})
        elif k in ('ownedAttribute','Attribute'):
            add(owner(e),type_id(e),'association',origin)
        elif k in ('Abstraction','Realization') and e.get('client') and e.get('supplier'):
            supplier=e.get('supplier')
            if nodes.get(supplier,{}).get('kind')=='Interface':add(e.get('client'),supplier,'realization',origin)
    return {'nodes':nodes,'edges':sorted(edges),'unresolved':unresolved}

def jl_graph(files,root):
    import javalang as jl
    nodes={};pending=[];failures=[];duplicates=[]
    def name(t):
        out=[]
        while t is not None:
            if getattr(t,'name',None):out.append(t.name)
            t=getattr(t,'sub_type',None)
        return '.'.join(out)
    def refs(t):
        if t is None:return set()
        ns={name(t)}
        while t is not None:
            for a in getattr(t,'arguments',None) or []:ns.update(refs(getattr(a,'type',None)))
            t=getattr(t,'sub_type',None)
        return ns-{''}
    decl=jl.tree.TypeDeclaration
    for f in files:
        try:tree=jl.parse.parse(read(f))
        except Exception as exc:
            failures.append({'file':str(f.relative_to(root)),'error':type(exc).__name__});continue
        pkg=tree.package.name if tree.package else ''
        for path,c in tree.filter(decl):
            outers=[p.name for p in path if isinstance(p,decl)]
            q='.'.join(([pkg] if pkg else [])+outers+[c.name])
            if q in nodes:duplicates.append(q)
            nodes[q]={'name':c.name,'file':str(f.relative_to(root))}
            ext=getattr(c,'extends',None)
            for t in (ext if isinstance(ext,list) else [ext] if ext else []):pending.append((q,name(t),'inheritance'))
            for t in getattr(c,'implements',None) or []:pending.append((q,name(t),'realization'))
            for fdecl in c.fields:
                for n in refs(fdecl.type):pending.append((q,n,'association'))
    by_name=defaultdict(list)
    for q,n in nodes.items():by_name[n['name']].append(q)
    edges=[];ambiguous=[]
    for s,t,k in pending:
        if t in nodes:resolved=t
        else:
            choices=by_name[t.rsplit('.',1)[-1]]
            if len(choices)!=1:
                if choices:ambiguous.append([s,t,k])
                continue
            resolved=choices[0]
        edges.append(edge(s,resolved,k))
    return dict(nodes=nodes,edges=sorted(set(edges)),failures=failures,
                duplicate_ids=sorted(set(duplicates)),ambiguous_references=ambiguous)

def ours(files,root):
    from src.parsing.java import run_java_pass,build_java_graph
    classes,_=run_java_pass(files,root)
    g=build_java_graph(classes,root.name)
    # Den vollen Paketnamen aus der ursprünglichen Deklaration wiederherstellen,
    # damit Klassen nicht über den Kurznamen zusammenfallen. Externe Knoten gehören
    # nicht zur Zuordnung zwischen Quelltext und Modell.
    full={}
    for c in classes:
        m=re.search(r'(?m)^\s*package\s+([\w.]+)\s*;',read(c.file))
        pkg=m.group(1) if m else ''
        localname=c.qualified_name[len(c.module)+1:] if c.module else c.qualified_name
        full[c.qualified_name]='.'.join(x for x in (pkg,localname) if x)
    nodes={full[c.qualified_name]:{'name':c.name,'file':str(c.file.relative_to(root))} for c in classes}
    edges=[edge(full[e.source],full[e.target],e.type if e.type in ('inheritance','realization') else 'association')
           for e in g.edges if e.source in full and e.target in full]
    return dict(nodes=nodes,edges=sorted(set(edges)),duplicate_ids=[q for q,n in Counter(full[c.qualified_name] for c in classes).items() if n>1])

def puml(text):
    nodes={};edges=[];unparsed=[]
    for line in text.splitlines():
        m=re.match(r'\s*(?:abstract\s+)?(?:class|interface|enum)\s+(\w+)',line)
        if m:nodes[m[1]]={'name':m[1]}
        m=re.match(r'^\s*(\w+)\s*(--\|>|\.\.\|>|--)\s*(?:"[^"]*"\s*)?(\w+)\s*$',line)
        if m:
            edges.append(edge(m[1],m[3],{'--|>':'inheritance','..|>':'realization','--':'association'}[m[2]]))
        elif re.search(r'--|\.\.\|>',line):unparsed.append(line)
    return dict(nodes=nodes,edges=sorted(set(edges)),unparsed_relation_lines=unparsed)

def j2p(files,root,out):
    cp=str(TOOLS/'javaparser-core-3.4.0.jar')+':'+str(TOOLS/'java2plantuml/classes')
    with tempfile.TemporaryDirectory(prefix='java-uml-') as td:
        stage=Path(td)/'src';stage.mkdir()
        for f in files:
            dest=stage/f.relative_to(root);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(read(f),encoding='utf-8')
        r=subprocess.run(['java','-cp',cp,'MainDriver',str(stage)],cwd=td,capture_output=True,text=True,timeout=90)
        fp=Path(td)/'output.puml';text=fp.read_text() if fp.exists() else ''
        out.with_suffix('.puml').write_text(text)
        out.with_suffix('.log').write_text(r.stdout+'\n'+r.stderr)
        if r.returncode or '@startuml' not in text:
            return dict(nodes={},edges=[],error='tool failed or reported parse error',returncode=r.returncode,output=text[:250])
        return puml(text)

def metrics(pred,ref):
    tp=len(pred&ref);fp=len(pred-ref);fn=len(ref-pred)
    return dict(tp=tp,fp=fp,fn=fn,precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None,f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)

def source_files(root):
    # Alle Extraktoren bekommen dieselbe Liste von Eingabedateien.
    excluded={'target','build','bin','.git','test','tests','androidTest'}
    return sorted(f for f in root.rglob('*.java') if not excluded.intersection(f.relative_to(root).parts))

def prepare():
    rows=json.loads((DATA/'acquisition.json').read_text());selected=[];excluded=[]
    for r in rows:
        if r['status']!='paired':continue
        root=DATA/r['source_dir'];files=source_files(root)
        ref=reference(root/r['path']);inv=jl_graph(files,root)
        src_names=defaultdict(list);model_names=defaultdict(list)
        for q,n in inv['nodes'].items():src_names[n['name']].append(q)
        for q,n in ref['nodes'].items():model_names[n['name']].append(q)
        mapping={};unmapped=[]
        for q,n in ref['nodes'].items():
            choices=src_names[n['name']]
            if len(choices)==1 and len(model_names[n['name']])==1 and choices[0] not in inv['duplicate_ids']:
                mapping[q]=choices[0]
            else:unmapped.append({'model_id':q,'name':n['name'],'source_candidates':choices,'reason':'missing or ambiguous identity'})
        edges={edge(mapping[s],mapping[t],k) for s,t,k in ref['edges'] if s in mapping and t in mapping}
        # Nötig sind mindestens drei zugeordnete Knoten und eine zugeordnete Beziehung.
        if len(mapping)<3 or not edges:
            excluded.append(dict(repo=r['repo'],reason='fewer than 3 unambiguous mapped nodes or no mapped relation',mapped_nodes=len(mapping),mapped_edges=len(edges)));continue
        r=dict(r,files=[str(f.relative_to(root)) for f in files],mapping=mapping,
               unmapped_model_nodes=unmapped,reference_nodes=sorted(mapping.values()),reference_edges=sorted(edges),
               model_total_nodes=len(ref['nodes']),model_total_edges=len(ref['edges']),
               model_unresolved_relations=ref['unresolved'],inventory_failures=inv['failures'],
               source_duplicate_ids=inv['duplicate_ids'])
        selected.append(r)
    (DATA/'eligible-manifest.json').write_text(json.dumps(selected,indent=2))
    (DATA/'preparation-exclusions.json').write_text(json.dumps(excluded,indent=2))
    print('Eligible paired projects:',len(selected),'; graph exclusions:',len(excluded))

def run(label,limit,tools):
    rows=json.loads((DATA/'manifest.json').read_text())[:limit]
    out=RESULTS/label;out.mkdir(parents=True,exist_ok=True);results=[]
    for rec in rows:
        root=DATA/rec['source_dir'];files=[root/f for f in rec['files']]
        for f in files:
            expected=rec.get('input_sha256',{}).get(str(f.relative_to(root)))
            if expected and hashlib.sha256(f.read_bytes()).hexdigest()!=expected:
                raise ValueError(f'Pinned benchmark input changed: {f}')
        refnodes=set(rec['reference_nodes']);refedges={tuple(e) for e in rec['reference_edges']}
        labels={q.rsplit('.',1)[-1]:q for q in refnodes}
        for tool in tools:
            dest=out/(rec['repo'].replace('/','__')+'__'+tool+'.json')
            t=time.perf_counter()
            def timed_out(signum,frame):
                raise TimeoutError('extractor exceeded 120 second timeout')
            previous_handler=signal.signal(signal.SIGALRM,timed_out)
            signal.alarm(120)
            try:
                raw=ours(files,root) if tool=='ours' else jl_graph(files,root) if tool=='javalang' else j2p(files,root,dest)
            except Exception as exc:raw=dict(nodes={},edges=[],error=type(exc).__name__+': '+str(exc))
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM,previous_handler)
            seconds=time.perf_counter()-t
            # Java2PlantUML wirft die Pakete weg. Zugeordnet wird deshalb nur über Namen,
            # die sich bei der Vorbereitung als eindeutig erwiesen haben.
            conv={q:(labels.get(q) if tool=='java2plantuml' else q) for q in raw['nodes']}
            prednodes={v for v in conv.values() if v in refnodes}
            prededges={edge(conv.get(s),conv.get(t),k) for s,t,k in raw['edges'] if conv.get(s) in refnodes and conv.get(t) in refnodes}
            result=dict(repo=rec['repo'],tool=tool,seconds=seconds,status='failed' if raw.get('error') else 'partial' if raw.get('failures') else 'ok',
                        source_files=len(files),raw_nodes=len(raw['nodes']),raw_edges=len(raw['edges']),
                        nodes=metrics(prednodes,refnodes),edges=metrics(prededges,refedges),
                        missing_edges=sorted(refedges-prededges),extra_edges=sorted(prededges-refedges),raw=raw)
            dest.write_text(json.dumps(result,indent=2));results.append(result)
            print(label,rec['repo'],tool,result['status'],result['edges'],flush=True)
    (out/'results.json').write_text(json.dumps(results,indent=2))
    fields=['repo','tool','status','seconds','source_files','raw_nodes','raw_edges','node_recall','edge_precision','edge_recall','edge_f1','tp','fp','fn']
    with (out/'results.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in results:
            w.writerow({**{k:r[k] for k in fields[:7]},'node_recall':r['nodes']['recall'],**{'edge_'+k:r['edges'][k] for k in ('precision','recall','f1')},**{k:r['edges'][k] for k in ('tp','fp','fn')}})

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--label',default='before');ap.add_argument('--limit',type=int,default=30);ap.add_argument('--tools',nargs='+',default=['ours','javalang','java2plantuml']);a=ap.parse_args()
    if a.prepare:prepare()
    else:run(a.label,a.limit,a.tools)
