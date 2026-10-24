"""Reanalyze archived learned covariances using the corrected A3 bootstrap."""
import argparse,json,sys,hashlib
from pathlib import Path
REPO_ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO_ROOT),str(REPO_ROOT/'src')]
import numpy as np
from experiments import cdev_learned_arm as c


def propagate_current_reference(package, instance):
    """Reuse learned primitive variances, never an old method covariance map."""
    from daqem.gap_kernel import nearest_psd
    frozen_path=package/f'results/pilot/a3_frozen_prediction/{instance}.npz'
    primitive_path=package/f'inputs/learned_primitives/{instance}.npz'
    source_path=package/f'inputs/learned_evidence/{instance}_propagation.npz'
    with np.load(frozen_path,allow_pickle=False) as frozen, np.load(primitive_path,allow_pickle=False) as primitive, np.load(source_path,allow_pickle=False) as source:
        if (int(primitive['x_star'])!=int(frozen['x_star']) or
            not np.allclose(primitive['ideal_values'],frozen['ideal_values'],rtol=0,atol=1e-11)):
            raise ValueError('Learned and reference landscapes differ')
        variances=primitive['variances'].reshape(-1)
        if not np.isfinite(variances).all() or np.any(variances<0):raise ValueError('Invalid primitive variances')
        if not np.allclose(variances,source['cdev_learned'],rtol=0,atol=1e-12):
            raise ValueError('Archived primitive variances differ from learned evidence')
        budgets=frozen['budgets'];maps=frozen['gap_maps']
        sigma=np.array([[nearest_psd((gap_map*variances)@gap_map.T/float(b)) for b in budgets] for gap_map in maps])
        max_change=float(np.max(abs(sigma-source['sigma_learned'])))
    folder=package/'results/pilot/cdev_evidence';folder.mkdir(parents=True,exist_ok=True)
    from experiments.a3_pullback_frontier import _write_deterministic_npz
    metadata=dict(instance=instance,reference_prediction_sha256=hashlib.sha256(frozen_path.read_bytes()).hexdigest(),
        learned_primitive_sha256=hashlib.sha256(primitive_path.read_bytes()).hexdigest(),
        archived_propagation_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
        scope='archived_learned_variances_propagated_with_current_reference_maps',max_change_from_archived_covariance=max_change)
    _write_deterministic_npz(folder/f'{instance}_propagation.npz',sigma_learned=sigma,cdev_learned=variances,budgets=budgets,
        metadata_json=np.array(json.dumps(metadata,sort_keys=True)))
    return sigma


def replay(package):
    config=c.load_config('full');c2=[];c3=[]
    for instance in config['instance_ids']:
        learned=propagate_current_reference(package,instance)
        a,b=c.c2_c3_rows_for_cell(instance_id=instance,output_root=package/'results',config=config,sigma_learned=learned)
        c2+=a;c3+=b
    result=dict(scope='archived_learned_primitive_variances_with_current_gap_maps_no_new_characterization',rho_C=config['rho_C'],c2=c2,c3=c3)
    path=package/'results/pilot/c3_reanalysis.json';path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    summary=dict(active=sum(r['active_pair'] for r in c3),interpretations={v:sum(r['c3_interpretation']==v for r in c3) for v in sorted({r['c3_interpretation'] for r in c3})},active_changes=sum(r['active_pair']!=r['archived_active_pair'] for r in c3))
    (path.parent/'c3_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--package',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(replay(args.package),indent=2))
