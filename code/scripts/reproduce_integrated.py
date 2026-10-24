"""Reproduce corrected analyses using explicit inputs and per-stage fingerprints.

This entry point never submits hardware jobs or launches the long E2 acquisition.
Use a new package/output directory after changing code or input data.
"""
from __future__ import annotations
import argparse,hashlib,importlib.metadata,json,os,sys,time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
CODE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(CODE/'src'),str(CODE)]
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8');tmp.replace(path)


def files(paths):
    found=[]
    for path in paths:
        path=Path(path)
        if not path.exists():raise FileNotFoundError(path)
        found.extend(sorted(p for p in path.rglob('*') if p.is_file() and p.suffix!='.pyc' and '__pycache__' not in p.parts) if path.is_dir() else [path])
    return sorted(set(found))


def fingerprint(package,stage):
    common=[CODE/'src',CODE/'scripts/reproduce_integrated.py',CODE/'scripts/checkpoint.py',CODE/'scripts/release_pipeline.py']
    if stage=='confirmatory':
        source=['experiments/a3_pullback_frontier.py','experiments/e3_bstar_prediction.py','experiments/gate0_pilot_full_vs_diagonal.py','run_archive_corrections.py','revision_v19/e1_reanalysis.py','reproducibility/config/a3_pullback_frontier.yaml','reproducibility/config/gate0_pilot.yaml']
        inputs=[package/'results/confirmatory/raw']
    elif stage=='e1':
        source=['revision_v19/e1_reanalysis.py','revision_v19/protocol.json'];inputs=[package/'inputs/reproducibility/reference_confirmatory/raw']
    elif stage=='pilot':
        source=['experiments/a3_gaussianity_sigmahat_audit.py','experiments/a3_pullback_frontier.py','experiments/gate0_pilot_full_vs_diagonal.py','reproducibility/config/a3_gaussianity.yaml','reproducibility/config/a3_pullback_frontier.yaml','reproducibility/config/gate0_pilot.yaml']
        inputs=[package/'results/pilot/raw',package/'results/pilot/a3_frozen_prediction']
    elif stage=='c3':
        source=['scripts/replay_c3_audit.py','experiments/cdev_learned_arm.py','experiments/a3_gaussianity_sigmahat_audit.py','experiments/a3_pullback_frontier.py','reproducibility/config/cdev_learning.yaml']
        inputs=[package/'inputs/learned_evidence',package/'inputs/learned_primitives',package/'results/pilot/a3_frozen_prediction',package/'results/pilot/raw',package/'results/pilot/a3_audit_evidence',package/'results/pilot/pullback_frontier.csv']
    else:raise ValueError(stage)
    paths=files(common+[CODE/s for s in source]+inputs)
    record={str(p.relative_to(package)):sha(p) for p in paths}
    versions={n:importlib.metadata.version(n) for n in ['numpy','scipy','qiskit','qiskit-aer','cvxpy','pandas','scikit-learn','networkx','PyYAML']}
    payload=dict(stage=stage,inputs_and_code=record,versions=versions,python=sys.version)
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(),payload


def check_receipt(package,path,current_fingerprint):
    r=json.loads(path.read_text(encoding='utf-8'))
    if r['fingerprint']!=current_fingerprint:raise ValueError('Code/inputs/environment changed; use a new output package')
    if r['status']!='complete':raise ValueError('Stage is incomplete; it cannot certify these results')
    for rel,h in r['outputs'].items():
        p=package/rel
        if not p.exists() or sha(p)!=h:raise ValueError(f'Output changed or missing: {rel}')
    return r


def job(task):
    kind,package,value=task;package=Path(package);start=time.perf_counter()
    import pandas as pd
    if kind=='confirmatory':
        from experiments import a3_pullback_frontier as a3,e3_bstar_prediction as e3
        from run_archive_corrections import e3_instance
        cfg=a3.load_config('confirmatory_full')
        path=a3.build_frozen_prediction_for_cell(instance_id=value,output_root=package/'results',config=cfg)
        frame=e3.analyze_confirmatory_instance(output_root=package/'results',instance_id=value,config=e3._profile_config('full'))
        folder=package/'results/confirmatory/_parts';folder.mkdir(parents=True,exist_ok=True)
        frame.to_csv(folder/f'{value}_frontier.csv',index=False)
        independent=e3_instance(package/'inputs',value,frame,
            prediction_dir=package/'results/confirmatory/a3_frozen_prediction',raw_dir=package/'results/confirmatory/raw')
        dump(folder/f'{value}_independent.json',independent)
        dump(folder/f'{value}_generation.json',dict(frozen_sha256=sha(path),crosscheck=frame.attrs['mean_crosscheck']))
    elif kind=='e1':
        from revision_v19.e1_reanalysis import analyse_instance
        protocol=json.loads((CODE/'revision_v19/protocol.json').read_text())
        result=analyse_instance(package/f'inputs/reproducibility/reference_confirmatory/raw/{value}.npz',protocol['base_shots_per_scale'])
        dump(package/f'results/e1/_parts/{value}.json',result)
    else:
        from experiments import a3_gaussianity_sigmahat_audit as a
        cfg=a.load_config('full');instance,budget=value
        if kind=='pilot_case':result=a.audit_rows_for_case(output_root=package/'results',instance_id=instance,budget=budget,config=cfg)
        elif kind=='pilot_calibration':
            cfg['instance_ids']=[instance];result=a.gaussianity_rows(package/'results',cfg)
        else:raise ValueError(kind)
        dump(package/f'results/pilot/_parts/{kind}_{instance}_{budget}.json',result)
    return dict(kind=kind,item=value,seconds=time.perf_counter()-start)


def cached_job(task,identity):
    from scripts.checkpoint import run_block
    kind,package,value=task
    if kind=='confirmatory':
        outputs=[f'results/confirmatory/{folder}/{value}.npz' for folder in ('a3_frozen_prediction','a3_primitive_evidence')]
        outputs += [f'results/confirmatory/_parts/{value}_{suffix}' for suffix in ('frontier.csv','independent.json','generation.json')]
        key=f'{kind}/{value}'
    elif kind=='e1':
        outputs=[f'results/e1/_parts/{value}.json'];key=f'{kind}/{value}'
    else:
        instance,budget=value;key=f'{kind}/{instance}_{budget}'
        outputs=[f'results/pilot/_parts/{kind}_{instance}_{budget}.json']
        if kind=='pilot_case':outputs += [f'results/pilot/a3_audit_evidence/{instance}_B{budget}.{ext}' for ext in ('npz','json')]
        else:outputs += [f'results/pilot/a3_audit_evidence/calibration_{instance}_{b}_{method}.npz' for b in (256,512,1024,2048,4096,8192) for method in ('Raw','Accuracy-ZNE','Decision-ZNE')]
    record=run_block(package,key,identity,outputs,lambda:job(task))
    return dict(record['result'],checkpoint_reused=record['reused'])


def _run_stage(package,stage,workers):
    import pandas as pd
    package=Path(package).resolve();finger,description=fingerprint(package,stage)
    receipt=package/f'results/integration/{stage}.json'
    if receipt.exists():
        prior=json.loads(receipt.read_text())
        if prior.get('fingerprint')!=finger:raise ValueError('Code/inputs/environment changed; use a new output package')
        try:
            result=check_receipt(package,receipt,finger);print(f'{stage}: verified cached stage',flush=True);return result
        except ValueError:
            backup=package/f'validation/invalidated_receipts/{stage}.{time.time_ns()}.json'
            backup.parent.mkdir(parents=True,exist_ok=True);receipt.replace(backup)
    start=time.perf_counter()
    if stage in ('confirmatory','e1'):
        tasks=[(stage,str(package),f'C{i:03}') for i in range(1,49)]
    elif stage=='pilot':
        tasks=[('pilot_case',str(package),(f'P{i:03}',b)) for i in range(1,5) for b in (256,512,1024,2048,4096,8192)]
        tasks += [('pilot_calibration',str(package),(f'P{i:03}',0)) for i in range(1,5)]
    elif stage=='c3':tasks=[]
    timings=[]
    if tasks:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for future in as_completed([pool.submit(cached_job,t,finger) for t in tasks]):
                result=future.result();timings.append(result);print(json.dumps(result),flush=True)
    if stage=='confirmatory':
        from experiments.e3_bstar_prediction import directional_summary
        from run_archive_corrections import e3_order_counts
        folder=package/'results/confirmatory';parts=folder/'_parts'
        frontier=pd.concat([pd.read_csv(p) for p in sorted(parts.glob('*_frontier.csv'))],ignore_index=True)
        frontier.drop(columns=['_frozen_hash']).to_csv(folder/'e3_pullback_frontier.csv',index=False)
        by_instance,summary=directional_summary(frontier);by_instance.to_csv(folder/'e3_by_instance.csv',index=False)
        independent=pd.DataFrame([row for p in sorted(parts.glob('*_independent.json')) for row in json.loads(p.read_text())])
        independent.to_csv(folder/'e3_independent_mean_and_failure.csv',index=False)
        summary['covariance_score_vs_all40_failure']=e3_order_counts(independent,'old_covariance_order','old_all40_failure_order')
        summary['method_mean_train_vs_independent_test']=e3_order_counts(independent,'method_mean_train_order','test_failure_order')
        summary['scope']='retrospective regenerated covariance predictions; 20 train/20 test for effective means; dependent pairs, no prospective claim'
        dump(folder/'e3_summary.json',summary)
        owned=[p for p in files([folder]) if 'raw' not in p.parts]
    elif stage=='e1':
        from revision_v19.e1_reanalysis import summarize
        folder=package/'results/e1';parts=[json.loads(p.read_text()) for p in sorted((folder/'_parts').glob('*.json'))]
        outcomes=pd.DataFrame([r for v in parts for r in v[0]])
        outcomes.to_csv(folder/'outcomes.csv',index=False);summarize(outcomes).to_csv(folder/'summary.csv',index=False)
        pd.DataFrame([r for v in parts for r in v[2]]).to_csv(folder/'budget_ledger.csv',index=False)
        dump(folder/'diagnostics.json',[r for v in parts for r in v[1]])
        owned=files([folder]);summary=dict(instances=48,decisions=len(outcomes),scope='fixed 10/10/20 split and shot intervals; current numerical core')
    elif stage=='pilot':
        from experiments import a3_gaussianity_sigmahat_audit as a
        folder=package/'results/pilot/_parts'
        cases=[json.loads(p.read_text()) for p in sorted(folder.glob('pilot_case_*.json'))]
        calibration=[json.loads(p.read_text()) for p in sorted(folder.glob('pilot_calibration_*.json'))]
        summary=a.finish_audit(package/'results',a.load_config('full'),[r for v in calibration for r in v[0]],[r for v in calibration for r in v[1]],cases)
        owned=files([folder,package/'results/pilot/a3_audit_evidence',package/'results/pilot/a3_gaussianity.md',package/'results/pilot/a3_sigmahat_audit.md'])
    else:
        from scripts.replay_c3_audit import replay
        summary=replay(package)
        owned=files([package/'results/pilot/c3_reanalysis.json',package/'results/pilot/c3_summary.json',package/'results/pilot/cdev_evidence'])
    final_finger,_=fingerprint(package,stage)
    if final_finger!=finger:raise ValueError('Inputs/code changed during stage; results are not certified')
    result=dict(schema_version=1,stage=stage,status='complete',fingerprint=finger,source=description,
        outputs={p.relative_to(package).as_posix():sha(p) for p in owned},summary=summary,
        seconds=time.perf_counter()-start,workers=workers,jobs=timings)
    dump(receipt,result);print(json.dumps(dict(stage=stage,summary=summary,seconds=result['seconds'])),flush=True)
    return result


def run_stage(package,stage,workers):
    from reproducibility.run_all import RunLock
    with RunLock(Path(package)/f'results/stage_locks/{stage}'):
        return _run_stage(package,stage,workers)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=CODE.parent)
    parser.add_argument('--stage',choices=['confirmatory','e1','pilot','c3'],required=True)
    parser.add_argument('--workers',type=int,default=8)
    args=parser.parse_args()
    if args.workers<1:parser.error('--workers must be positive')
    run_stage(args.package,args.stage,args.workers)


if __name__=='__main__':main()
