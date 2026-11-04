"""Den ausgewählten Korpus aus den festgelegten öffentlichen Archiven wiederherstellen. Dabei wird kein Code ausgeführt."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parent.parent
# Alle Pfade in den JSON-Dateien der Lindholmen-Auswahl sind relativ zu diesem Ordner.
DATA=ROOT/'daten'/'lindholmen'

def restore(rec):
    root=DATA/rec['source_dir']
    wanted=set(rec['files'])|{rec['path']}|set(rec['license_files'])
    if all((root/f).exists() for f in wanted):
        for f,h in rec.get('input_sha256',{}).items():
            if hashlib.sha256((root/f).read_bytes()).hexdigest()!=h:
                raise ValueError('Modified local input: '+str(root/f))
        if hashlib.sha256((root/rec['path']).read_bytes()).hexdigest()!=rec['pinned_model_sha256']:
            raise ValueError('Modified local model: '+rec['repo'])
        return rec['repo']+' already present and verified'
    with urllib.request.urlopen(rec['archive_url'],timeout=60) as r:data=r.read(15_000_001)
    if len(data)>15_000_000:raise ValueError('Archive size exceeds limit')
    if hashlib.sha256(data).hexdigest()!=rec['archive_sha256']:raise ValueError('Archive hash mismatch: '+rec['repo'])
    archive=zipfile.ZipFile(io.BytesIO(data))
    prefix=archive.infolist()[0].filename.split('/')[0]+'/'
    for name in wanted:
        rel=PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts:raise ValueError('Unsafe archive path')
        info=archive.getinfo(prefix+name)
        if info.file_size>2_000_000:raise ValueError('Individual file too large')
        dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(archive.read(info))
    return rec['repo']+' restored'

if __name__=='__main__':
    records=json.loads((DATA/'manifest.json').read_text())
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(restore,records):print(result,flush=True)
