"""Content-addressed provenance for local probability and analysis checkpoints."""
from pathlib import Path
import hashlib,json,os
import numpy as np


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def atomic_json(path,payload):
    path=Path(path);temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(payload,indent=2,allow_nan=False),encoding='utf-8')
    os.replace(temporary,path)


def atomic_npz(path,**arrays):
    path=Path(path);temporary=path.with_name(path.name+'.tmp')
    with temporary.open('wb') as f:np.savez_compressed(f,**arrays)
    os.replace(temporary,path)


def load_json(path):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):return None


def valid_probability(path,identity):
    path=Path(path);metadata=load_json(path.with_suffix('.json'))
    return bool(path.is_file() and metadata and metadata.get('identity')==identity
                and metadata.get('sha256')==sha256(path))


def valid_analysis(record,identity,sample_path):
    return bool(record and record.get('cache_identity')==identity and Path(sample_path).is_file()
                and record.get('samples_sha256')==sha256(sample_path))
