"""Verify all original E2 shots and replay all decisions without new simulation."""
import argparse,json,os,sys,time,subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
CODE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(CODE/'src'),str(CODE)]
from scripts.release_pipeline import dump,sha,safe_member
from reproducibility.run_all import RunLock

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--raw-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=8);a=p.parse_args()
    if a.workers<1:p.error('workers must be positive')
    root=a.raw_root.resolve();out=a.output.resolve()
    if out.is_relative_to(root):p.error('Output must be outside original measurements')
    out.mkdir(parents=True,exist_ok=True);started=time.perf_counter()
    with RunLock(out):
        dump(out/'report.json',dict(status='running',scope='read-only full E2 replay'))
        metadata=json.loads((CODE.parent/'validation/consolidated/external_E2_raw_manifest.json').read_text())
        if len(metadata['files'])!=25600:raise ValueError('Expected 25,600 original rounds')
        for rel,record in metadata['files'].items():
            file=safe_member(root,rel)
            if file.stat().st_size!=record['bytes'] or sha(file)!=record['sha256']:raise ValueError(f'Raw data changed: {rel}')
        print('Verified original 25,600 round-file hashes',flush=True)
        def worker(name):
            destination=out/name
            command=[sys.executable,str(CODE/'scripts/regenerate_e2.py'),'--instance',name,'--trajectories','40',
                '--rounds-readonly',str(root/name/'rounds'),'--output',str(destination)]
            with (out/f'{name}.log').open('w') as log:result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
            if result.returncode:raise RuntimeError(f'{name} replay failed: see {name}.log')
            report=json.loads((destination/'report.json').read_text())
            if report['status']!='complete' or report['fresh_rounds']!=0 or report['reused_rounds']!=800:raise ValueError(f'Incomplete replay: {name}')
            return report
        results=[];names=iter(f'C{i:03}' for i in range(1,33))
        try:
            with ThreadPoolExecutor(max_workers=a.workers) as pool:
                pending={pool.submit(worker,next(names)):None for _ in range(min(a.workers,32))}
                while pending:
                    done,_=wait(pending,return_when=FIRST_COMPLETED)
                    for future in done:
                        pending.pop(future);report=future.result();results.append(report)
                        print(f'{report["instance"]} complete ({len(results)}/32)',flush=True)
                    for _ in range(a.workers-len(pending)):
                        name=next(names,None)
                        if name is None:break
                        pending[pool.submit(worker,name)]=None
        except BaseException as exc:
            dump(out/'report.json',dict(status='incomplete',error=str(exc),instances=results));raise
        result=dict(status='complete',instances=sorted(results,key=lambda v:v['instance']),original_round_files_verified=25600,
            trajectories=1280,decisions=15360,new_simulated_rounds=0,seconds=time.perf_counter()-started,
            runner_sha256=sha(__file__),per_instance_runner_sha256=sha(CODE/'scripts/regenerate_e2.py'),
            scope='All saved shot states validated against moments; exact candidate-angle and decision replay. No new quantum simulation.')
        dump(out/'report.json',result);print('E2_ARCHIVE_REPLAY_PASS',flush=True)

if __name__=='__main__':main()
