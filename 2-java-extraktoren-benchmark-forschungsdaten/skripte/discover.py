"""Eine reproduzierbare Teilmenge von Lindholmen untersuchen. Heruntergeladener Code wird nie ausgeführt."""
import concurrent.futures as cf
import csv
import hashlib
import json
from pathlib import Path
import random
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent.parent
# Alle Pfade in den JSON-Dateien der Lindholmen-Auswahl sind relativ zu diesem Ordner.
DATA=ROOT/'daten'/'lindholmen'

def local(s):
    return s.rsplit('}', 1)[-1].rsplit(':', 1)[-1]

def inspect(row):
    repo = row['Project'].strip('/')
    link = row['Model Link - Github']
    rest = link.split('/tree/', 1)[1]
    branch, path = rest.split('/', 1)
    key = hashlib.sha256(link.encode()).hexdigest()[:16]
    dest = DATA / 'model-probes' / (key + '.xml')
    rec = dict(repo=repo, branch=branch, path=path, dataset_url=link, probe=str(dest.relative_to(DATA)))
    try:
        if dest.exists():
            data = dest.read_bytes()
        else:
            url = 'https://raw.githubusercontent.com/' + repo + '/' + branch + '/' + urllib.parse.quote(path)
            with urllib.request.urlopen(url, timeout=15) as r:
                data = r.read(2_000_001)
            if len(data)>2_000_000:
                raise ValueError('model exceeds 2 MB probe limit')
            dest.write_bytes(data)
        xml = ET.fromstring(data)
        types = []
        relations = 0
        for e in xml.iter():
            kind = local(e.tag)
            for k,v in e.attrib.items():
                if local(k) == 'type' and (':' in v):
                    kind = local(v)
            if kind in ('Class','Interface','Enumeration') and e.get('name'):
                types.append(e.get('name'))
            if kind in ('Association','Generalization','InterfaceRealization','generalization','interfaceRealization'):
                relations += 1
        rec.update(status='parsed', types=types, n_types=len(types), n_relations=relations,
                   sha256=hashlib.sha256(data).hexdigest())
    except Exception as exc:
        rec.update(status='unusable', error=str(exc))
    return rec

def main():
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=300);args=ap.parse_args()
    (DATA/'model-probes').mkdir(exist_ok=True)
    rows=list(csv.DictReader((DATA/'UMLFiles_List_V2.0.csv').open()))
    by_repo={}
    for row in rows:
        link=row['Model Link - Github']
        if link.endswith(('.uml','.xmi')) and '/tree/' in link:
            by_repo.setdefault(row['Project'],[]).append(row)
    # Nur Repos mit wenigen Modellen, damit keine Sammlungen fremder
    # Modellierungsbeispiele in die Auswahl kommen.
    candidates=[min(v,key=lambda r:len(r['Model Link - Github'])) for v in by_repo.values() if len(v)<=10]
    random.Random(20260920).shuffle(candidates)
    candidates=candidates[:args.limit]
    out=[]
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        for i,r in enumerate(pool.map(inspect,candidates),1):
            out.append(r)
            if r.get('n_types',0)>=3 and r.get('n_relations',0)>=1:
                print(i,r['repo'],r['n_types'],r['n_relations'],flush=True)
            if i%25==0:
                (DATA/'discovery.json').write_text(json.dumps(out,indent=2))
    (DATA/'discovery.json').write_text(json.dumps(out,indent=2))
    print('Inspected',len(out),'candidates',flush=True)

if __name__=='__main__':main()
