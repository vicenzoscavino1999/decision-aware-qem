"""Produce the Linux wheel lock inside the pinned Python base image.

Run once while preparing a release. Ordinary reviewers install the sealed lock.
Only hashes of the Linux CPython 3.12 wheels actually selected are recorded.
"""
from pathlib import Path
import hashlib, json, subprocess, sys
from zipfile import ZipFile
from email.parser import Parser

root=Path(__file__).resolve().parent
wheelhouse=Path('/tmp/repro-wheels');wheelhouse.mkdir(exist_ok=True)
pins=[]
excluded={'sspilib','pymupdf4llm','pymupdf_layout','onnxruntime','flatbuffers','protobuf','mpmath','sympy'}
for line in (root/'requirements_this_run.txt').read_text().splitlines():
    if line.split('==')[0].lower() not in excluded:
        pins.append(line)
requirements=Path('/tmp/linux-pins.txt');requirements.write_text('\n'.join(pins)+'\n')
subprocess.run([sys.executable,'-m','pip','download','--only-binary=:all:','-r',str(requirements),'-d',str(wheelhouse)],check=True)
rows=[];metadata=[]
for wheel in sorted(wheelhouse.glob('*.whl')):
    with ZipFile(wheel) as z:
        filename=next(p for p in z.namelist() if p.endswith('.dist-info/METADATA'))
        record=Parser().parsestr(z.read(filename).decode())
    digest=hashlib.sha256(wheel.read_bytes()).hexdigest()
    rows.append(f'{record["Name"]}=={record["Version"]} --hash=sha256:{digest}')
    metadata.append(dict(name=record['Name'],version=record['Version'],wheel=wheel.name,sha256=digest))
(root/'requirements-lock.linux.txt').write_text('# Linux amd64 / CPython 3.12; generated in the pinned base image.\n'+'\n'.join(sorted(rows,key=str.lower))+'\n')
(root/'validation/linux_wheels.json').write_text(json.dumps(metadata,indent=2)+'\n')
