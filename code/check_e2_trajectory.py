"""Replay corrected and historical E2 decisions on the SAME fresh shot records.

Local Aer simulation only. Default: C002, trajectory 0, all 20 rounds and six
budgets. --trajectories 40 covers all archived trajectories of an instance.
The supplied historical CSV is checked against the old decision implementation
before any change is attributed to the correction. Original files are read-only.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,importlib.metadata,json,os,shutil,sys,time
os.environ.setdefault('OMP_NUM_THREADS','4')
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
import numpy as np
import pandas as pd
from experiments import e2_dynamic_batch_candidate_optimizer as corrected

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,default=Path(r'D:\Copia_Laptop_D\paper fisica 5'))
    parser.add_argument('--instance',default='C002')
    parser.add_argument('--trajectories',type=int,default=1)
    parser.add_argument('--output',type=Path,default=ROOT.parent/'validation/e2_C002')
    args=parser.parse_args()
    if args.instance not in corrected.CONFIRMATORY_E2_INSTANCE_IDS or not 1<=args.trajectories<=40:
        parser.error('Use C001..C032 and 1..40 trajectories')
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    source=args.project/'revision_v21';inputs=out/'runtime_inputs'
    selection=args.project/'results/confirmatory/e1_static_selector_table.csv'
    frozen=source/f'inputs/reproducibility/reference_confirmatory/a3/{args.instance}.npz'
    archived_path=source/f'inputs/reproducibility/reference_confirmatory/e2/instances/{args.instance}_results.csv'
    (inputs/'confirmatory/a3_frozen_prediction').mkdir(parents=True,exist_ok=True)
    shutil.copy2(selection,inputs/'confirmatory/e1_static_selector_table.csv')
    shutil.copy2(frozen,inputs/f'confirmatory/a3_frozen_prediction/{args.instance}.npz')
    old_path=source/'code/experiments/e2_dynamic_batch_candidate_optimizer.py'
    spec=importlib.util.spec_from_file_location('legacy_e2',old_path)
    legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
    config=corrected.load_config('full');config['trajectories']=args.trajectories
    config['instance_ids']=[args.instance]
    records=[];evaluator=corrected._evaluate_candidate_batch
    def capture(**kwargs):
        start=time.perf_counter();means,variances,cost=evaluator(**kwargs)
        records.append({'trajectory':kwargs['trajectory_id'],'round':kwargs['round_id'],
                        'angles':kwargs['angles'].copy(),'means':means.copy(),'variances':variances.copy(),'cost':cost})
        print(f"{args.instance} trajectory {kwargs['trajectory_id']} round {kwargs['round_id']}: {time.perf_counter()-start:.1f}s",flush=True)
        return means,variances,cost
    corrected._evaluate_candidate_batch=capture
    start=time.perf_counter()
    new,newtrace,cost=corrected._run_instance(output_root=inputs,instance_id=args.instance,config=config)
    corrected._evaluate_candidate_batch=evaluator
    np.savez_compressed(out/'records.npz',
        angles=np.stack([r['angles'] for r in records]),primitive_means=np.stack([r['means'] for r in records]),
        primitive_mean_variances=np.stack([r['variances'] for r in records]),
        trajectory=np.array([r['trajectory'] for r in records]),round=np.array([r['round'] for r in records]))
    iterator=iter(records)
    def replay(**kwargs):
        record=next(iterator)
        assert (kwargs['trajectory_id'],kwargs['round_id'])==(record['trajectory'],record['round'])
        np.testing.assert_array_equal(kwargs['angles'],record['angles'])
        return record['means'],record['variances'],record['cost']
    legacy._evaluate_candidate_batch=replay
    old,oldtrace,_=legacy._run_instance(output_root=inputs,instance_id=args.instance,config=config)
    assert next(iterator,None) is None
    keys=['instance','trajectory','selector','budget']
    historical=pd.read_csv(archived_path)
    historical=historical[historical.trajectory<args.trajectories]
    old=old.sort_values(keys).reset_index(drop=True);new=new.sort_values(keys).reset_index(drop=True)
    historical=historical.sort_values(keys).reset_index(drop=True)
    assert old[keys].equals(historical[keys]) and new[keys].equals(old[keys])
    numeric=['final_ideal_value','best_seen_ideal_value','epsilon_opt','regret_decision']
    # CSV round-trip can alter the last bit of ideal floats; comparison tolerance
    # is used only for provenance checking, never for selecting a candidate.
    legacy_matches=bool(np.allclose(old[numeric],historical[numeric],rtol=0,atol=1e-12)
                        and old.success_decision.equals(historical.success_decision)
                        and old.selected_method.equals(historical.selected_method))
    changed=new.success_decision!=old.success_decision
    differences=new[keys].copy()
    differences['old_success']=old.success_decision;differences['corrected_success']=new.success_decision
    differences['old_final_ideal']=old.final_ideal_value;differences['corrected_final_ideal']=new.final_ideal_value
    differences['changed_success']=changed
    old.to_csv(out/'legacy_results.csv',index=False);new.to_csv(out/'corrected_results.csv',index=False)
    oldtrace.to_csv(out/'legacy_trace.csv',index=False);newtrace.to_csv(out/'corrected_trace.csv',index=False)
    differences.to_csv(out/'comparison.csv',index=False)
    report={'instance':args.instance,'trajectories':args.trajectories,'rounds_per_trajectory':config['max_rounds'],
            'budgets':config['budget_grid'],'rows':len(new),'fresh_aer_cost':cost,
            'legacy_matches_archived_subset':legacy_matches,'same_raw_proposal_trajectory':True,
            'changed_success_labels':int(changed.sum()),
            'changed_final_ideal_values':int((abs(new.final_ideal_value-old.final_ideal_value)>1e-12).sum()),
            'changed_batch_choices':{p:int((newtrace[p+'_candidate']!=oldtrace[p+'_candidate']).sum()) for p in ['MSE','DA']},
            'elapsed_seconds':time.perf_counter()-start,
            'input_sha256':{str(p):sha(p) for p in [selection,frozen,archived_path,old_path]},
            'corrected_source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in [Path(corrected.__file__),ROOT/'src/daqem/decisions.py']},
            'versions':{p:importlib.metadata.version(p) for p in ['numpy','scipy','qiskit','qiskit-aer']},
            'scope':'This subset only; aggregate impact over 32 x 40 trajectories is not inferred.'}
    (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
    if not legacy_matches:
        raise RuntimeError('Historical replay differs from the archive; do not attribute aggregate changes to the correction.')

if __name__=='__main__':main()
