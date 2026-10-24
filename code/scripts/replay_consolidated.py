"""Offline reanalysis of E2, FakeKolkata and archived hardware measurements."""
from __future__ import annotations
import argparse,hashlib,importlib.metadata,json,os,sys,time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
CODE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(CODE/'src'),str(CODE)]
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import numpy as np
import pandas as pd
from scripts.reproduce_integrated import dump,sha,files,check_receipt


def identity(package,stage):
    dependencies=files([CODE/'src',CODE/'experiments',CODE/'revision_v19',CODE/'run_archive_corrections.py',
                        CODE/'run_fakekolkata_v21.py',CODE/'scripts/analysis_from_hardware.py',Path(__file__),package/'protocol.json',
                        package/f'evidence/{stage}'])
    data=dict(stage=stage,files={p.relative_to(package).as_posix():sha(p) for p in dependencies},
              versions={p:importlib.metadata.version(p) for p in ('numpy','scipy','qiskit','qiskit-aer','qiskit-ibm-runtime','cvxpy','clarabel','scikit-learn','pandas','networkx')},python=sys.version)
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest(),data


def forbidden(*args,**kwargs):raise RuntimeError('New physical sampling is forbidden by this offline entry point')


def fake_worker(package,name):
    import run_fakekolkata_v21 as fk
    from qiskit_aer import AerSimulator
    package=Path(package);source=package/'evidence/fakekolkata/results/fakekolkata_fixed10'
    destination=package/'results/fakekolkata_fixed10'
    AerSimulator.run=forbidden;fk.old._probability_array_for_cell=forbidden
    sys.argv=['run_fakekolkata_v21.py','--instances',name,'--bounded-10-qubits','--probability-inputs',str(source),'--output',str(destination)]
    # Each worker writes only its own instance; aggregation is done once below.
    original_json=fk.atomic_json;original_csv=pd.DataFrame.to_csv
    def json_without_summary(path,value):
        if Path(path).name!='summary.json':original_json(path,value)
    def csv_without_summary(frame,path,*args,**kwargs):
        if Path(path).name!='outcomes.csv':return original_csv(frame,path,*args,**kwargs)
    fk.atomic_json=json_without_summary;pd.DataFrame.to_csv=csv_without_summary
    try:fk.main()
    finally:fk.atomic_json=original_json;pd.DataFrame.to_csv=original_csv
    return name


def run(package,stage,workers):
    package=Path(package).resolve();finger,source=identity(package,stage);start=time.perf_counter()
    receipt=package/f'results/integration/{stage}.json'
    if receipt.exists():
        prior=json.loads(receipt.read_text())
        if prior.get('fingerprint')!=finger:raise ValueError('Code/inputs/environment changed; use a new output package')
        try:return check_receipt(package,receipt,finger)
        except ValueError:
            backup=package/f'validation/invalidated_receipts/{stage}.{time.time_ns()}.json'
            backup.parent.mkdir(parents=True,exist_ok=True);receipt.replace(backup)
    if stage=='fakekolkata':
        import run_fakekolkata_v21 as fk
        from qiskit_aer import AerSimulator
        source_dir=package/'evidence/fakekolkata/results/fakekolkata_fixed10'
        fk._validate_protocol();backend=fk.FakeKolkataV2();noise=fk.NoiseModel.from_backend(backend)
        backend,noise,physical=fk.bounded_backend(backend,noise)
        for name in (f'C{i:03}' for i in range(1,49)):
            if not fk.valid_probability(source_dir/f'{name}_probabilities.npz',fk.probability_identity(name,backend,noise,physical)):
                raise ValueError(f'Probability source is incompatible with current physical model: {name}')
        folder=package/'results/fakekolkata_fixed10';folder.mkdir(parents=True,exist_ok=True)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures=[pool.submit(fake_worker,str(package),f'C{i:03}') for i in range(1,49)]
            for future in as_completed(futures):print('replayed '+future.result(),flush=True)
        AerSimulator.run=forbidden;fk.old._probability_array_for_cell=forbidden;fk.analyze=forbidden
        sys.argv=['run_fakekolkata_v21.py','--bounded-10-qubits','--output',str(folder)]
        fk.main()
        summary=json.loads((folder/'summary.json').read_text())
    elif stage=='hardware':
        from experiments.hardware_sigma import run_main as h
        from run_archive_corrections import hardware
        h.load_ibm_service_phase_b_only=forbidden;h.RuntimeSamplerAdapter.__init__=forbidden
        folder=package/'results/hardware';folder.mkdir(parents=True,exist_ok=True)
        probabilities=[];original=h.noisy_probabilities
        def capture(circuit,noise):
            result=original(circuit,noise);probabilities.append(result.copy());return result
        h.noisy_probabilities=capture
        try:hardware(package/'evidence/hardware/inputs',folder)
        finally:h.noisy_probabilities=original
        assert len(probabilities)==12
        np.savez_compressed(folder/'prediction_probabilities.npz',probabilities=np.array(probabilities))
        summary=json.loads((folder/'hardware.json').read_text())
    elif stage=='e2':
        from run_archive_corrections import e2
        folder=package/'results/e2';folder.mkdir(parents=True,exist_ok=True)
        e2(package/'evidence/e2/corrected/inputs',folder)
        summary=json.loads((folder/'e2_summary.json').read_text())
    else:raise ValueError(stage)
    assert identity(package,stage)[0]==finger,'Inputs or producer code changed during reanalysis'
    result=dict(status='complete',stage=stage,fingerprint=finger,source=source,
                outputs={p.relative_to(package).as_posix():sha(p) for p in files([folder])},summary=summary,
                seconds=time.perf_counter()-start,workers=workers,
                scope='offline reanalysis; no new shots, E2 starts from saved trajectory outcomes, hardware retains executed coefficients')
    dump(receipt,result);print(f'{stage} complete: {result["seconds"]:.2f}s',flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['e2','fakekolkata','hardware'],required=True)
    p.add_argument('--workers',type=int,default=8);args=p.parse_args()
    if args.workers<1:p.error('--workers must be positive')
    run(CODE.parent,args.stage,args.workers)
