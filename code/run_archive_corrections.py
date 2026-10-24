"""Recalculate archived hardware, full E2 ledgers and independent E3 evaluation."""
from pathlib import Path
import argparse,sys,json
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
import numpy as np
import pandas as pd
from revision_v19.e1_reanalysis import split_replicates,risk_score,gaps
from daqem.decisions import zne_failures

def hardware(repo,out):
    from scripts import analysis_from_hardware as analysis
    reference=json.loads((repo/'results/hardware_sigma_attempt2/hsmc_result.json').read_text())
    result=analysis.recompute_from_archive(repo=repo)
    result.update(old_endpoint=reference['primary_projected_ranking'],
        corrected_endpoint=result['primary_projected_ranking'],
        secondary=result['secondary_frobenius'],label=result['result_label'])
    (out/'hardware.json').write_text(json.dumps(result,indent=2))
    print('Hardware:',result['label'],flush=True)

def dynamic_ledger(budget,active_scales,source_budget,rounds=20,candidates=5,trajectories=40,bmax=8192):
    # 19 proposal updates influence later candidates; final-round update is unused.
    proposal=(rounds-1)*candidates*bmax
    incremental=((rounds-1)*(active_scales-1)+active_scales)*candidates*budget
    # The historical static selector acquires 40 repetitions, 3 scales, 25 candidates.
    training=40*3*25*source_budget
    return {'proposal_shots_per_trajectory':proposal,'incremental_selection_shots_per_trajectory':incremental,
        'static_training_shots_per_instance':training,'amortized_static_training_shots':training/trajectories,
        'total_shots_per_trajectory':proposal+incremental+training/trajectories,
        'executed_union_shots_per_trajectory':rounds*candidates*(bmax+(active_scales-1)*budget)+training/trajectories}

def e2(repo,out):
    df=pd.concat([pd.read_csv(p) for p in sorted((repo/'reproducibility/reference_confirmatory/e2/instances').glob('*_results.csv'))],ignore_index=True)
    rows=[]
    for keys,g in df.groupby(['instance','selector','budget','selected_method','active_scales','selector_source_budget']):
        instance,selector,budget,method,scales,source=keys
        ledger=dynamic_ledger(int(budget),int(scales),int(source))
        rows.append({'instance':instance,'selector':selector,'budget':budget,'method':method,'success_rate':g.success.mean(),
          'reported_shots_per_trajectory':100*scales*budget,**ledger})
    rates=pd.DataFrame(rows);rates.to_csv(out/'e2_full_ledger.csv',index=False)
    crossings=[]
    for (instance,selector),g in rates.groupby(['instance','selector']):
        good=g[g.success_rate>=.8]
        if good.empty:continue
        row=good.sort_values(['total_shots_per_trajectory','budget']).iloc[0].to_dict()
        crossings.append(row)
    cross=pd.DataFrame(crossings,columns=rates.columns);cross.to_csv(out/'e2_corrected_crossings.csv',index=False)
    paired=cross.pivot(index='instance',columns='selector',values='total_shots_per_trajectory').reindex(columns=['DA','MSE']).dropna()
    ratios=paired.MSE/paired.DA
    pooled=rates.groupby(['selector','budget']).success_rate.mean()
    result={'instances':int(df.instance.nunique()),'target':.8,'pooled_max_success':pooled.groupby(level=0).max().to_dict(),
      'both_cross_instances':len(paired),'median_full_cost_ratio_MSE_over_DA':float(ratios.median()) if len(ratios) else None,
      'ratios':ratios.to_dict(),'scope':'shared Raw_Bmax assisted trajectory; full shot ledger, conditional crossings, no end-to-end dynamic superiority claim',
      'training':'historical fixed static selector (40 repetitions x 3 scales x 25 candidates) amortized over 40 trajectories',
      'oracle':'analytic A3 coefficient computation and noiseless reference values excluded from shot ledger; not a deployment cost claim'}
    (out/'e2_summary.json').write_text(json.dumps(result,indent=2));print('E2:',result,flush=True)

def e3_instance(repo, instance, frontier, *, prediction_dir=None, raw_dir=None):
    """Reanalyse one instance; independent instances can run in separate processes."""
    from experiments.a3_pullback_frontier import _matched_budget_indices
    rows=[]
    prediction_dir = Path(prediction_dir) if prediction_dir is not None else repo/'reproducibility/reference_confirmatory/a3'
    raw_dir = Path(raw_dir) if raw_dir is not None else repo/'reproducibility/reference_confirmatory/raw'
    with np.load(prediction_dir/f'{instance}.npz',allow_pickle=False) as fr, np.load(raw_dir/f'{instance}.npz',allow_pickle=False) as raw:
        names=[str(x) for x in fr['method_names']];coeffs=fr['method_coefficients'];opt=int(raw['x_star'])
        split=split_replicates(instance);training=np.r_[split['fit'],split['select']];test=split['test']
        for bi,raw_bi,budget in _matched_budget_indices(fr['budgets'],raw['budgets']):
            objective=np.einsum('ms,rsc->mrc',coeffs,raw['primitive_objective_estimates'][:,:,:,raw_bi])
            predicted=[risk_score(v[training],opt,20261022) for v in objective]
            primitive=raw['primitive_objective_estimates'][:,:,:,raw_bi]
            all_failures=[np.any(gaps(v,opt)<=0,axis=1) for v in objective]
            for mi,name in enumerate(names):
                if name=='Accuracy-ZNE':all_failures[mi]=zne_failures(primitive,opt,int(budget))
                elif name=='Decision-ZNE':all_failures[mi]=zne_failures(primitive,opt,int(budget),coefficients=coeffs[mi])
            failures=[f[test].astype(int) for f in all_failures]
            oldfail=[f.mean() for f in all_failures]
            active=frontier[(frontier.problem_cell==instance)&(frontier.budget==budget)&frontier.active_pair]
            for row in active.itertuples():
                left,right=row.pair_id.split('_vs_');a,b=names.index(left),names.index(right)
                def order(x,y):return f'{left}<{right}' if x<y else f'{right}<{left}' if y<x else 'tie'
                observed=order(failures[a].mean(),failures[b].mean());predorder=order(predicted[a],predicted[b])
                rows.append({'instance':instance,'budget':int(budget),'pair':row.pair_id,'old_covariance_order':row.predicted_order,
                   'old_all40_failure_order':order(oldfail[a],oldfail[b]),'method_mean_train_order':predorder,
                   'test_failure_order':observed,'left_test_failure':failures[a].mean(),'right_test_failure':failures[b].mean(),
                   'left_predicted_risk':predicted[a],'right_predicted_risk':predicted[b],
                   'test_paired_difference':float((failures[a]-failures[b]).mean())})
    return rows


def e3_order_counts(df, predicted, observed):
    """Partition all pairs without treating a tied prediction as a reversal."""
    predicted_tie = df[predicted] == 'tie'
    observed_tie = df[observed] == 'tie'
    same = df[predicted] == df[observed]
    return {'match':int((same & ~predicted_tie).sum()),
            'ties':int(observed_tie.sum()),
            'reversal':int((~same & ~observed_tie & ~predicted_tie).sum()),
            'prediction_only_ties':int((predicted_tie & ~observed_tie).sum())}


def e3(repo,out):
    frontier=pd.read_csv(repo/'results/confirmatory/e3_pullback_frontier.csv')
    rows=[]
    for i in range(1,49):
        instance=f'C{i:03}'
        rows.extend(e3_instance(repo,instance,frontier))
        print(f'E3 {instance} complete',flush=True)
    df=pd.DataFrame(rows);df.to_csv(out/'e3_independent_mean_and_failure.csv',index=False)
    result={'active_pairs':len(df),'old_covariance_score_vs_all40_actual_failure':e3_order_counts(df,'old_covariance_order','old_all40_failure_order'),
       'new_method_mean_train_vs_independent_test':e3_order_counts(df,'method_mean_train_order','test_failure_order'),
       'scope':'descriptive pairs selected by historical covariance endpoint; 20 train/20 test; 48 dependent instance clusters; no independent significance claim'}
    (out/'e3_summary.json').write_text(json.dumps(result,indent=2));print('E3:',result,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--repo',type=Path,required=True);parser.add_argument('--only',choices=['hardware','e2','e3','all'],default='all')
    parser.add_argument('--output',type=Path,default=ROOT.parent/'results');a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    for label,fn in [('hardware',hardware),('e2',e2),('e3',e3)]:
        if a.only in (label,'all'):fn(a.repo,a.output)
