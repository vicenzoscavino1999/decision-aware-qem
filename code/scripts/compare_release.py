"""Scientific reference comparison with exact decisions and bounded float drift."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
from copy import deepcopy
from functools import lru_cache
CONFIG=yaml.safe_load((Path(__file__).resolve().parents[1]/'reproducibility/config/tolerances.yaml').read_text())['release_comparison']
ATOL=CONFIG['regular_abs']['value']
RTOL=CONFIG['relative']['value']
CDF_ATOL=CONFIG['cdf_abs']['value']
RISK_ARRAYS={'risks_pred','predicted_risks','full_risks','raw_risks','common_risks','bootstrap_common_risks'}
# These hashes depend on the producing environment; stage receipts verify them.
PROVENANCE={'cache_identity','samples_sha256','primitive_evidence_hash','reference_prediction_sha256','_frozen_hash'}

def equivalent(left,right,path,stats):
    if isinstance(left,dict):
        if not isinstance(right,dict) or set(left)!=set(right):raise ValueError(f'Fields changed: {path}')
        for key in left:
            if key not in PROVENANCE:equivalent(left[key],right[key],f'{path}/{key}',stats)
    elif isinstance(left,list):
        if not isinstance(right,list) or len(left)!=len(right):raise ValueError(f'Length changed: {path}')
        for i,(a,b) in enumerate(zip(left,right)):equivalent(a,b,f'{path}/{i}',stats)
    elif isinstance(left,(bool,int,str)) or left is None:
        if type(left)!=type(right) or left!=right:raise ValueError(f'Exact value changed: {path}: {left} != {right}')
    elif isinstance(left,float):
        if not isinstance(right,(float,int)) or not np.isfinite([left,right]).all():raise ValueError(f'Nonfinite value: {path}')
        stats['max_abs_difference']=max(stats['max_abs_difference'],abs(left-right))
        tolerance=CDF_ATOL if path.endswith(('/gri','/tau_C')) else ATOL
        if not np.isclose(left,right,atol=tolerance,rtol=RTOL):raise ValueError(f'Numeric value changed: {path}: {left} != {right}')
    else:raise TypeError(f'Unsupported value {path}: {type(left)}')

@lru_cache(maxsize=96)
def _prediction(root,instance):
    with np.load(Path(root)/f'results/confirmatory/a3_frozen_prediction/{instance}.npz') as d:
        return {k:d[k] for k in ('method_names','budgets','gradients')}

def ratio_denominators(root,frame,kind):
    epsilon=1e-12;answer=[]
    for row in frame.itertuples():
        denominator=max(row.tau_flip_projected,epsilon)
        if kind=='frobenius_error_over_tolerance':
            frozen=_prediction(str(root),row.problem_cell);names=list(frozen['method_names']);bi=list(frozen['budgets']).index(row.budget)
            left,right=row.pair_id.split('_vs_')
            norm=sum(np.linalg.norm(frozen['gradients'][names.index(name),bi],ord='fro') for name in (left,right))
            denominator=max(denominator/(norm+epsilon),epsilon)
        answer.append(denominator)
    return np.asarray(answer)

def normalized_c3(value):
    value=deepcopy(value);tolerances={}
    for row in value['c2']:
        denominator=max(row['tau_C'],1e-12)
        tolerances[(row['cell'],row['pair_id'],row['budget'])]=denominator
        row['projected_error_over_tolerance']*=denominator
    for row in value['c3']:
        denominator=tolerances[(row['cell'],row['pair_id'],row['budget'])]
        for key in ('true_vs_sigmahat_ratio','learned_vs_sigmahat_ratio'):row[key]*=denominator
        intervals=row['sampling_intervals_at_C3_tolerance']
        if intervals:
            for interval in intervals.values():
                for key in ('bootstrap_ratio_ci_low','bootstrap_ratio_ci_high'):interval[key]*=denominator
    return value

def compare(reference,generated):
    reference=Path(reference);generated=Path(generated)
    stats=dict(files=0,max_abs_difference=0.,atol=ATOL,rtol=RTOL,cdf_atol=CDF_ATOL,decisions='exact',
        ratio_comparison='Compare numerators after multiplying by each stored, independently checked denominator; CDF tolerances apply to denominators.',
        provenance_fields_checked_separately=sorted(PROVENANCE))
    csvs=[]
    for folder in ('e1','confirmatory','e2','fakekolkata_fixed10'):
        csvs.extend(sorted((reference/'results'/folder).glob('*.csv')))
    jsons=[reference/'results'/name for name in ('e1/diagnostics.json','confirmatory/e3_summary.json','e2/e2_summary.json','fakekolkata_fixed10/summary.json','hardware/hardware.json','pilot/c3_summary.json','pilot/c3_reanalysis.json')]
    jsons+=sorted((reference/'results/fakekolkata_fixed10').glob('*_analysis.json'))
    for file in csvs:
        rel=file.relative_to(reference);a=pd.read_csv(file);b=pd.read_csv(generated/rel)
        if list(a.columns)!=list(b.columns) or a.shape!=b.shape:raise ValueError(f'Table shape or columns changed: {rel}')
        for col in a:
            if col in PROVENANCE:continue
            if not a[col].isna().equals(b[col].isna()):raise ValueError(f'Missing-value mask changed: {rel}/{col}')
            x=a.loc[a[col].notna(),col];y=b.loc[b[col].notna(),col]
            if pd.api.types.is_float_dtype(x):
                if not np.isfinite(x).all() or not np.isfinite(y).all():raise ValueError(f'Nonfinite table value: {rel}/{col}')
                if col in ('projected_error_over_tolerance','frobenius_error_over_tolerance'):
                    mask=a[col].notna().to_numpy()
                    x=x*ratio_denominators(reference,a,col)[mask];y=y*ratio_denominators(generated,b,col)[mask]
                if len(x):stats['max_abs_difference']=max(stats['max_abs_difference'],float(np.max(abs(x-y))))
                tolerance=CDF_ATOL if col in ('left_predicted_risk','right_predicted_risk','tau_flip_projected') else ATOL
                np.testing.assert_allclose(x,y,rtol=RTOL,atol=tolerance,err_msg=f'{rel}/{col}')
            else:pd.testing.assert_series_equal(x,y,check_exact=True,check_dtype=True)
        stats['files']+=1
    for file in jsons:
        rel=file.relative_to(reference)
        x=json.loads(file.read_text());y=json.loads((generated/rel).read_text())
        if rel.as_posix()=='results/pilot/c3_reanalysis.json':x=normalized_c3(x);y=normalized_c3(y)
        equivalent(x,y,str(rel),stats);stats['files']+=1
    arrays=[]
    for folder,pattern in [('confirmatory/a3_frozen_prediction','*.npz'),('confirmatory/a3_primitive_evidence','*.npz'),('pilot/a3_audit_evidence','*.npz'),('fakekolkata_fixed10','*_samples.npz'),('hardware','*.npz')]:
        arrays+=list((reference/'results'/folder).glob(pattern))
    for file in sorted(arrays):
        rel=file.relative_to(reference)
        with np.load(file,allow_pickle=False) as a,np.load(generated/rel,allow_pickle=False) as b:
            if set(a.files)!=set(b.files):raise ValueError(f'Array set changed: {rel}')
            for key in a.files:
                x,y=a[key],b[key]
                if x.shape!=y.shape or x.dtype!=y.dtype:raise ValueError(f'Array shape or dtype changed: {rel}/{key}')
                if key=='metadata_json':equivalent(json.loads(str(x)),json.loads(str(y)),f'{rel}/{key}',stats)
                elif x.dtype.kind in 'fc':
                    if not np.array_equal(np.isfinite(x),np.isfinite(y)):raise ValueError(f'Finite mask changed: {rel}/{key}')
                    mask=np.isfinite(x)
                    if mask.any():stats['max_abs_difference']=max(stats['max_abs_difference'],float(np.max(abs(x[mask]-y[mask]))))
                    tolerance=CDF_ATOL if key in RISK_ARRAYS or key=='tau_flip_projected' else CONFIG['difference_of_risks_abs']['value'] if key=='delta_pred' else CONFIG['derivative_abs']['value'] if key in ('gradients','method_coefficients','gap_maps') else ATOL
                    np.testing.assert_allclose(x,y,atol=tolerance,rtol=RTOL,err_msg=f'{rel}/{key}')
                else:np.testing.assert_array_equal(x,y,err_msg=f'{rel}/{key}')
        stats['files']+=1
    return stats
