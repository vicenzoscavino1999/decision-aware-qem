"""Portable E2 generation or read-only replay of original per-shot round records.

One instance is the unit of execution. Repeat the command to resume. The default
one-trajectory prefix is a real simulation, not a full-paper reproduction.
"""
import argparse,importlib.metadata,json,os,sys,time,shutil
from pathlib import Path
CODE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(CODE/'src'),str(CODE)]
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import numpy as np
import pandas as pd
from experiments import e2_dynamic_batch_candidate_optimizer as e2
from scripts.e2_rounds import RoundStore,generation_identity,validate_shot_statistics,write_json,sha,OutputLock

def _run(instance,trajectories,output,raw=None):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    config=e2.load_config('full');config['instance_ids']=[instance]
    versions={p:importlib.metadata.version(p) for p in ['numpy','scipy','qiskit','qiskit-aer','pandas','networkx']}
    identity=generation_identity(e2,config,versions,1,1)
    rounds=Path(raw).resolve() if raw else output/'rounds'
    if raw and not (rounds/'identity.json').exists():raise FileNotFoundError('Original round identity is required')
    store=RoundStore(rounds,identity)
    inputs=output/'runtime_inputs/confirmatory';inputs.mkdir(parents=True,exist_ok=True)
    protocol=CODE.parent/'inputs/e2_protocol'
    shutil.copy2(protocol/'e1_static_selector_table.csv',inputs/'e1_static_selector_table.csv')
    (inputs/'a3_frozen_prediction').mkdir(exist_ok=True)
    shutil.copy2(protocol/f'a3_frozen_prediction/{instance}.npz',inputs/f'a3_frozen_prediction/{instance}.npz')
    config['trajectories']=trajectories
    evaluator=e2._evaluate_candidate_batch;prefix=e2._prefix_objective_stats
    memories=[];counts=dict(fresh_rounds=0,reused_rounds=0);started=time.perf_counter()
    def memory(values,graph,budgets):
        if graph.number_of_nodes()>16:raise ValueError('Shot archive requires at most 16 qubits')
        memories.append(np.fromiter((int(s.replace(' ',''),2) for s in values),dtype=np.uint16,count=len(values)))
        return prefix(values,graph,budgets)
    def evaluate(**kw):
        t,r=kw['trajectory_id'],kw['round_id'];saved=store.load(t,r,kw['angles'],include_states=True)
        if saved is None:
            if raw:raise RuntimeError(f'Incomplete original archive: {t}/{r}; no simulation allowed')
            memories.clear();means,variance,cost=evaluator(**kw)
            states=np.stack(memories).reshape(len(kw['scales']),len(kw['angles']),kw['b_max'])
            validate_shot_statistics(states,kw['graph'],kw['budgets'],means,variance)
            store.save(t,r,kw['angles'],means,variance,cost,states);counts['fresh_rounds']+=1
        else:
            means,variance,cost,states=saved
            validate_shot_statistics(states,kw['graph'],kw['budgets'],means,variance);counts['reused_rounds']+=1
        print(f'{instance} {t}/{r} saved',flush=True)
        return means,variance,cost
    if True:  # The public run() owns the whole output transaction.
        write_json(output/'report.json',dict(status='running',instance=instance,trajectories=trajectories))
        e2._evaluate_candidate_batch=evaluate;e2._prefix_objective_stats=memory
        try:frame,trace,cost=e2._run_instance(output_root=output/'runtime_inputs',instance_id=instance,config=config)
        except BaseException as exc:
            write_json(output/'report.json',dict(status='incomplete',error=str(exc)));raise
        finally:e2._evaluate_candidate_batch=evaluator;e2._prefix_objective_stats=prefix
        for name,data in [('corrected_results.csv',frame),('corrected_trace.csv',trace)]:
            temporary=output/(name+'.tmp');data.to_csv(temporary,index=False);temporary.replace(output/name)
        reference=pd.read_csv(CODE.parent/f'evidence/e2/corrected/inputs/reproducibility/reference_confirmatory/e2/instances/{instance}_results.csv')
        reference=reference[reference.trajectory<trajectories]
        keys=['instance','trajectory','selector','budget'];a=frame.sort_values(keys).reset_index(drop=True);b=reference.sort_values(keys).reset_index(drop=True)
        discrete=keys+['selected_method','success_decision','success_global']
        try:
            pd.testing.assert_frame_equal(a[discrete],b[discrete],check_dtype=False,check_exact=True)
            np.testing.assert_allclose(a[['final_ideal_value','regret_decision']],b[['final_ideal_value','regret_decision']],rtol=0,atol=1e-10)
        except BaseException as exc:
            write_json(output/'report.json',dict(status='incomplete',reason='reference comparison failed',error=str(exc)));raise
        result=dict(status='complete',instance=instance,trajectories=trajectories,**counts,seconds=time.perf_counter()-started,
            scope='trajectory prefix' if trajectories<40 else 'full instance; full campaign requires all 32',
            source_round_identity=store.identity,versions=versions,readonly_replay=bool(raw),decisions_match_corrected_reference=True,
            outputs={name:sha(output/name) for name in ('corrected_results.csv','corrected_trace.csv')})
        write_json(output/'report.json',result);return result

def run(instance,trajectories,output,raw=None):
    with OutputLock(Path(output).resolve()):return _run(instance,trajectories,output,raw)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--instance',choices=[f'C{i:03}' for i in range(1,33)],default='C001')
    p.add_argument('--trajectories',type=int,default=1);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--rounds-readonly',type=Path);a=p.parse_args()
    if not 1<=a.trajectories<=40:p.error('trajectories must be 1..40')
    print(json.dumps(run(a.instance,a.trajectories,a.output,a.rounds_readonly),indent=2))
