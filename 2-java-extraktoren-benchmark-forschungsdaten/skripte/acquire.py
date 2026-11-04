"""Für die gefundenen UML-Dateien den Commit festlegen und den öffentlichen Quelltext herunterladen."""
import concurrent.futures as cf
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parent.parent
# Alle Pfade in den JSON-Dateien der Lindholmen-Auswahl sind relativ zu diesem Ordner.
DATA=ROOT/'daten'/'lindholmen'

def acquire(rec):
    r=dict(rec)
    folder=DATA/'corpus'/r['repo'].replace('/','__')
    meta=folder/'acquisition.json'
    if meta.exists(): return json.loads(meta.read_text())
    try:
        proc=subprocess.run(['git','ls-remote','https://github.com/'+r['repo']+'.git','refs/heads/'+r['branch']],
            capture_output=True,text=True,timeout=25,env={**os.environ,'GIT_TERMINAL_PROMPT':'0'})
        sha=proc.stdout.split()[0] if proc.returncode==0 and proc.stdout.strip() else ''
        if not re.fullmatch('[0-9a-f]{40}',sha): raise ValueError('branch commit unavailable')
        r['commit']=sha
        url='https://codeload.github.com/'+r['repo']+'/zip/'+sha
        with urllib.request.urlopen(url,timeout=40) as resp: data=resp.read(15_000_001)
        if len(data)>15_000_000: raise ValueError('archive exceeds 15 MB acquisition limit')
        r.update(archive_url=url,archive_sha256=hashlib.sha256(data).hexdigest(),archive_bytes=len(data))
        archive=zipfile.ZipFile(io.BytesIO(data))
        files=[i for i in archive.infolist() if not i.is_dir()]
        java=[i for i in files if i.filename.endswith('.java')]
        if not 3<=len(java)<=1500: raise ValueError(f'Java file count outside 3..1500: {len(java)}')
        root=files[0].filename.split('/')[0]+'/'
        model=next((i for i in files if i.filename==root+r['path']),None)
        if model is None: raise ValueError('indexed model not in pinned source snapshot')
        if model.file_size>2_000_000: raise ValueError('model too large')
        source_names=set()
        for f in java:
            if f.file_size>2_000_000: raise ValueError('individual Java file too large')
            s=archive.read(f).decode('utf-8',errors='replace')
            source_names.update(re.findall(r'\b(?:class|interface|enum|record)\s+(\w+)',s))
        matching=sorted(set(r['types'])&source_names)
        r.update(java_files=len(java),matching_type_names=matching,matching_type_count=len(matching))
        if len(matching)<3: raise ValueError('fewer than three matching model/source type names')
        # Hier wird nur geprüft, ob sich das Paar verwenden lässt. Über Korrektheit
        # oder Konsistenz sagt das nichts aus.
        keep=java+[model]+[i for i in files if PurePosixPath(i.filename).name.lower().startswith(('license','copying','readme'))]
        if sum(f.file_size for f in keep)>40_000_000: raise ValueError('expanded selected files exceed 40 MB')
        folder.mkdir(parents=True,exist_ok=True)
        for f in keep:
            rel=PurePosixPath(f.filename[len(root):])
            if rel.is_absolute() or '..' in rel.parts: raise ValueError('unsafe archive path')
            dest=folder/'source'/str(rel)
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(archive.read(f))
        r.update(status='paired',source_dir=str((folder/'source').relative_to(DATA)),
                 pinned_model_sha256=hashlib.sha256(archive.read(model)).hexdigest(),
                 license_files=[f.filename[len(root):] for f in keep if PurePosixPath(f.filename).name.lower().startswith(('license','copying'))])
        meta.write_text(json.dumps(r,indent=2))
    except Exception as exc:r.update(status='excluded',reason=str(exc))
    return r

def main():
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=80);a=ap.parse_args()
    all_rows=json.loads((DATA/'discovery.json').read_text())
    rows=[r for r in all_rows if 3<=r.get('n_types',0)<=200 and r.get('n_relations',0)>=1][:a.limit]
    old = {r['repo']:r for r in json.loads((DATA/'acquisition.json').read_text())} if (DATA/'acquisition.json').exists() else {}
    out=[]
    def cached(rec):
        return old[rec['repo']] if rec['repo'] in old else acquire(rec)
    with cf.ThreadPoolExecutor(max_workers=5) as pool:
        for i,r in enumerate(pool.map(cached,rows),1):
            out.append(r)
            print(i,r['repo'],r['status'],r.get('java_files',''),r.get('matching_type_count',''),r.get('reason',''),flush=True)
            (DATA/'acquisition.json').write_text(json.dumps(out,indent=2))
    print('PAIRED',sum(r['status']=='paired' for r in out),'OF',len(rows),flush=True)

if __name__=='__main__':main()
