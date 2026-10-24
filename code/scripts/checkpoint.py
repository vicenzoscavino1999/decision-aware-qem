"""Atomic receipts for resumable analysis jobs; no incomplete job is reusable."""
import json,time
from pathlib import Path
from scripts.release_pipeline import dump,sha,safe_member

def run_block(root,key,identity,outputs,producer):
    root=Path(root).resolve();outputs=list(outputs)
    if not outputs or len(set(outputs))!=len(outputs):raise ValueError('Expected outputs must be nonempty and unique')
    paths=[safe_member(root,p) for p in outputs]
    receipt=safe_member(root,f'results/checkpoints/{key}.json')
    previous=None
    if receipt.exists():
        try:previous=json.loads(receipt.read_text())
        except (ValueError,OSError):previous=None
    if previous is not None:
        if previous.get('identity')!=identity:raise ValueError('Checkpoint inputs changed; use a new output directory')
        if previous.get('status')=='complete' and set(previous.get('outputs',{}))==set(outputs):
            if all(p.is_file() and sha(p)==previous['outputs'][name] for name,p in zip(outputs,paths)):
                return dict(reused=True,key=key,result=previous['result'])
    started=time.perf_counter()
    dump(receipt,dict(identity=identity,status='running',outputs={}))
    try:
        result=producer()
        if not all(p.is_file() for p in paths):raise ValueError('Producer omitted an expected output')
        dump(receipt,dict(identity=identity,status='complete',outputs={name:sha(p) for name,p in zip(outputs,paths)},result=result,seconds=time.perf_counter()-started))
    except BaseException as exc:
        dump(receipt,dict(identity=identity,status='incomplete',outputs={},error=str(exc)))
        raise
    return dict(reused=False,key=key,result=result)
