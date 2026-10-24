"""Rebuild E2 aggregation and costs from saved outcomes, without new trajectories."""
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd


def verify(package):
    source=package/'evidence/e2/corrected'
    frames=[pd.read_csv(p,float_precision='round_trip') for p in sorted((source/'inputs/reproducibility/reference_confirmatory/e2/instances').glob('*_results.csv'))]
    assert len(frames)==32
    data=pd.concat(frames,ignore_index=True)
    keys=['instance','trajectory','selector','budget']
    assert len(data)==15360 and not data.duplicated(keys).any()
    assert set(data.instance)=={f'C{i:03}' for i in range(1,33)}
    assert set(data.selector)=={'DA','MSE'} and set(data.budget)=={256,512,1024,2048,4096,8192}
    assert (data.success==data.success_decision).all()
    rows=[]
    for (instance,selector,budget),group in data.groupby(['instance','selector','budget'],sort=True):
        assert len(group)==40 and set(group.trajectory)==set(range(40))
        for c in ('selected_method','active_scales','selector_source_budget'):assert group[c].nunique()==1
        row=group.iloc[0];scales=int(row.active_scales);train=40*3*25*int(row.selector_source_budget)
        proposal=19*5*8192;incremental=(19*(scales-1)+scales)*5*int(budget)
        rows.append(dict(instance=instance,selector=selector,budget=int(budget),method=row.selected_method,
                         success_rate=int(group.success_decision.sum())/40,reported_shots_per_trajectory=100*scales*int(budget),
                         proposal_shots_per_trajectory=proposal,incremental_selection_shots_per_trajectory=incremental,
                         static_training_shots_per_instance=train,amortized_static_training_shots=train/40,
                         total_shots_per_trajectory=proposal+incremental+train/40,
                         executed_union_shots_per_trajectory=20*5*(8192+(scales-1)*int(budget))+train/40))
    expected=pd.DataFrame(rows)
    root=package/'results/e2'
    actual=pd.read_csv(root/'e2_full_ledger.csv',float_precision='round_trip')
    pd.testing.assert_frame_equal(expected[actual.columns],actual,check_exact=True,check_dtype=False)
    crossings=[]
    for _,group in expected.groupby(['instance','selector'],sort=True):
        good=group[group.success_rate>=.8]
        if len(good):crossings.append(good.sort_values(['total_shots_per_trajectory','budget']).iloc[0])
    cross=pd.DataFrame(crossings).reset_index(drop=True)
    pd.testing.assert_frame_equal(cross,pd.read_csv(root/'e2_corrected_crossings.csv',float_precision='round_trip'),check_exact=True,check_dtype=False)
    summary=json.loads((root/'e2_summary.json').read_text())
    paired=cross.pivot(index='instance',columns='selector',values='total_shots_per_trajectory').dropna()
    assert summary['both_cross_instances']==len(paired)==13
    assert summary['median_full_cost_ratio_MSE_over_DA']==float(np.median(paired.MSE/paired.DA))==1.3
    series=[]
    for (selector,budget),group in expected.groupby(['selector','budget'],sort=True):
        selected=data[(data.selector==selector)&(data.budget==budget)]
        series.append(dict(selector=selector,budget=int(budget),mean_full_shots=float(group.total_shots_per_trajectory.mean()),
                           successful_trajectories=int(selected.success.sum()),trajectories=1280,success_rate=int(selected.success.sum())/1280))
    for selector in ('DA','MSE'):
        assert summary['pooled_max_success'][selector]==max(r['success_rate'] for r in series if r['selector']==selector)
    for name in ('e2_full_ledger.csv','e2_corrected_crossings.csv'):
        pd.testing.assert_frame_equal(pd.read_csv(source/name),pd.read_csv(root/name),check_exact=True,check_dtype=False)
    assert summary==json.loads((source/'e2_summary.json').read_text())
    return dict(outcomes_verified=len(data),ledger_rows=len(actual),both_cross_instances=len(paired),series=series,
                scope='Outcome-level aggregation and costs; does not independently reconstruct all raw trajectories')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=verify(a.package);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
