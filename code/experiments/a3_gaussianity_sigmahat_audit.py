"""Retrospective diagnostics of fixed pilot gap estimators and covariance error.

Bootstrap intervals condition on the archived coefficients, means and design.
They are percentile diagnostics, not certificates of Gaussianity or nonlinear
ranking stability. Original frozen predictions are never overwritten.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import sys
import time
from pathlib import Path
REPO_ROOT=Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:sys.path.insert(0,str(REPO_ROOT))
import numpy as np
import yaml
from scipy import stats
from daqem.risk import gri_risk
from daqem.rng import make_rng
from daqem.decisions import integer_shot_sums,zne_failures
from daqem.learned_control import common_incumbent_gradient
from experiments.a3_pullback_frontier import FROZEN_REL_DIR,_covariance,_method_samples_from_raw,_matched_budget_indices
from experiments.gate0_pilot_full_vs_diagonal import raw_relpath

CONFIG_PATH=REPO_ROOT/'reproducibility/config/a3_gaussianity.yaml'
DEFAULT_OUTPUT_ROOT=REPO_ROOT/'results'
GAUSSIANITY_REL=Path('pilot/a3_gaussianity.md')
SIGMAHAT_AUDIT_REL=Path('pilot/a3_sigmahat_audit.md')
EVIDENCE_REL=Path('pilot/a3_audit_evidence')
AUDIT_SCHEMA='a3_full_gradient_joint_bootstrap_v1'
RISK_NUMERICAL_TOL=2e-6


def sha256(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def _dump(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def load_config(profile='smoke'):
    raw=yaml.safe_load(CONFIG_PATH.read_text(encoding='utf-8'))
    if profile not in raw['profiles']:raise ValueError(f'unknown F1c-A profile: {profile}')
    config={**raw['defaults'],**raw['profiles'][profile],'profile':profile}
    if not 0<config['bootstrap_ci']<1 or not 0<config['tau_R']<1:
        raise ValueError('Invalid CI or risk tolerance')
    if int(config['bootstrap_replicates'])!=config['bootstrap_replicates'] or config['bootstrap_replicates']<2:
        raise ValueError('At least two bootstrap replicates are required')
    config['tail_min_expected_count']=5
    return config


def load_raw_frozen(output_root,instance_id):
    def read(path):
        with np.load(path,allow_pickle=False) as data:return {k:data[k] for k in data.files}
    raw=read(output_root/raw_relpath(instance_id));frozen=read(output_root/FROZEN_REL_DIR/f'{instance_id}.npz')
    rm=json.loads(str(raw['metadata_json'].item()));fm=json.loads(str(frozen['metadata_json'].item()))
    if rm['instance_id']!=instance_id or fm['instance_id']!=instance_id or rm['profile']!=fm['gate0_profile']:
        raise ValueError('Raw/frozen instance or profile mismatch')
    _matched_budget_indices(frozen['budgets'],raw['budgets'])
    ideal=np.asarray(raw['ideal_values']);x=int(raw['x_star']);est=np.asarray(raw['primitive_objective_estimates'])
    names=list(frozen['method_names']);budgets=frozen['budgets'];d=len(ideal)-1
    if (not np.isfinite(ideal).all() or x!=np.argmin(ideal) or x!=int(frozen['x_star'])
        or not np.allclose(ideal,frozen['ideal_values'],atol=1e-12,rtol=0)
        or est.shape!=(rm['replicates'],3,len(ideal),len(raw['budgets']))
        or len(set(names))!=len(names) or set(names)!={'Raw','Accuracy-ZNE','Decision-ZNE'}
        or not np.array_equal(raw['zne_lambdas'],[1.,2.,3.])
        or frozen['sigma_pred'].shape!=(3,len(budgets),d,d)
        or frozen['gradients'].shape!=frozen['sigma_pred'].shape
        or frozen['active_masks'].shape!=(3,len(budgets),d)):
        raise ValueError('Incompatible raw/frozen shapes, methods or candidate landscape')
    comp=[i for i in range(len(ideal)) if i!=x]
    if not np.allclose(frozen['mu'],ideal[comp]-ideal[x],atol=1e-12,rtol=0):raise ValueError('Frozen margins differ from raw landscape')
    for idx,b in enumerate(raw['budgets']):integer_shot_sums(est[:,:,:,idx],int(b))
    if not np.isfinite(frozen['sigma_pred']).all() or not np.isfinite(frozen['method_coefficients']).all():raise ValueError('Nonfinite frozen model')
    return raw,frozen


def _raw_budget_index(raw,frozen,budget_idx):
    budget=int(frozen['budgets'][budget_idx])
    mapping={b:r for _,r,b in _matched_budget_indices(frozen['budgets'],raw['budgets'])}
    return mapping[budget]


def method_samples(raw,frozen,budget_idx):
    return _method_samples_from_raw(raw,budget_idx=_raw_budget_index(raw,frozen,budget_idx),
        method_names=list(frozen['method_names']),method_coefficients=frozen['method_coefficients'])


def method_failures(raw,frozen,budget_idx):
    budget=int(frozen['budgets'][budget_idx]);idx=_raw_budget_index(raw,frozen,budget_idx)
    primitive=raw['primitive_objective_estimates'][:,:,:,idx];x=int(raw['x_star'])
    sums=integer_shot_sums(primitive,budget);comp=[j for j in range(sums.shape[2]) if j!=x]
    coeffs=dict(zip(map(str,frozen['method_names']),frozen['method_coefficients'],strict=True))
    return {'Raw':np.any(sums[:,0,comp]<=sums[:,0,[x]],axis=1),
        'Accuracy-ZNE':zne_failures(primitive,x,budget),
        'Decision-ZNE':zne_failures(primitive,x,budget,coefficients=coeffs['Decision-ZNE'])}


def _anderson_reject_5(sample):
    x=np.asarray(sample,dtype=float)
    if x.ndim!=1 or len(x)<4 or not np.isfinite(x).all():raise ValueError('At least four finite observations are required')
    if np.std(x,ddof=1)==0:return None,None
    result=stats.anderson(x,dist='norm',method='interpolate')
    return float(result.statistic),bool(float(result.pvalue)<.05)


def tail_ratios(sample,thresholds):
    x=np.asarray(sample,dtype=float)
    if x.ndim!=1 or len(x)<2 or not np.isfinite(x).all():raise ValueError('Invalid tail sample')
    sd=float(np.std(x,ddof=1))
    result={}
    for threshold in thresholds:
        if not np.isfinite(threshold) or threshold<=0:raise ValueError('Tail thresholds must be positive')
        p=float(2*stats.norm.sf(threshold))
        result[float(threshold)]=None if sd==0 or p==0 else float(np.mean(np.abs((x-x.mean())/sd)>threshold)/p)
    return result


def henze_zirkler_statistic(samples):
    """HZ descriptive statistic with S_n normalized by n (Ebner & Henze, 2020)."""
    x=np.asarray(samples,dtype=float)
    if x.ndim!=2 or not np.isfinite(x).all():raise ValueError('Finite matrix required')
    n,p=x.shape
    if n<8 or p<2 or n<=p:return None
    centered=x-x.mean(axis=0);cov=centered.T@centered/n
    if np.linalg.matrix_rank(cov)<p:return None
    # Cholesky whitening avoids constructing a pseudoinverse.
    white=np.linalg.solve(np.linalg.cholesky(cov),centered.T).T
    distance=np.sum((white[:,None,:]-white[None,:,:])**2,axis=-1)
    mahal=np.sum(white**2,axis=1)
    beta=(((2*p+1)*n/4)**(1/(p+4)))/np.sqrt(2)
    statistic=n*(np.mean(np.exp(-.5*beta**2*distance))
        -2*(1+beta**2)**(-p/2)*np.mean(np.exp(-.5*beta**2/(1+beta**2)*mahal))
        +(1+2*beta**2)**(-p/2))
    return float(max(statistic,0.))


def gaussianity_rows(output_root,config):
    gaussian_rows=[];calibration_rows=[]
    for instance_id in config['instance_ids']:
        raw,frozen=load_raw_frozen(output_root,instance_id)
        for idx,budget in enumerate(map(int,frozen['budgets'])):
            samples_by_method=method_samples(raw,frozen,idx);failures=method_failures(raw,frozen,idx)
            for mi,method in enumerate(map(str,frozen['method_names'])):
                samples=samples_by_method[method];active=np.flatnonzero(frozen['active_masks'][mi,idx]);details=[];flagged=[]
                for gap in active:
                    sample=samples[:,gap];ad,reject=_anderson_reject_5(sample);degenerate=ad is None
                    skew=None if degenerate else float(stats.skew(sample,bias=False))
                    kurt=None if degenerate else float(stats.kurtosis(sample,fisher=True,bias=False))
                    ratios=tail_ratios(sample,config['tail_thresholds']);tails=[]
                    flags=[]
                    if degenerate:flags.append('degenerate_sample')
                    else:
                        if reject:flags.append('AD_unadjusted_5pct')
                        if abs(skew)>config['skew_abs_flag']:flags.append('skew_heuristic')
                        if abs(kurt)>config['excess_kurtosis_abs_flag']:flags.append('kurtosis_heuristic')
                    for z,ratio in ratios.items():
                        expected=len(sample)*2*stats.norm.sf(z)
                        assessed=ratio is not None and expected>=config.get('tail_min_expected_count',5)
                        outside=assessed and (ratio<config['tail_ratio_low_flag'] or ratio>config['tail_ratio_high_flag'])
                        if outside:flags.append(f'tail_{z:g}_heuristic')
                        tails.append(dict(threshold=z,ratio=ratio,expected_normal_count=float(expected),heuristic_assessed=bool(assessed)))
                    if flags:flagged.append(int(gap))
                    details.append(dict(gap=int(gap),AD=ad,AD_reject=reject,skew=skew,excess_kurtosis=kurt,tails=tails,flags=flags))
                hz=henze_zirkler_statistic(samples[:,active]) if len(active)<=config['hz_max_dim'] else None
                gaussian_rows.append(dict(problem_cell=instance_id,method=method,budget=budget,
                    active_gaps=active.tolist(),flagged_gaps=flagged,henze_zirkler=hz,gap_diagnostics=details,
                    scope='exploratory_marginal_flags_and_descriptive_HZ_no_joint_acceptance_test'))
                sigma=_covariance(samples,shrinkage=True);mu_sample=samples.mean(axis=0)
                risk_sample=gri_risk(mu_sample,sigma);risk_ideal=gri_risk(frozen['mu'],sigma)
                empirical=float(np.mean(failures[method]));diff=abs(risk_sample-empirical)
                calibration_rows.append(dict(problem_cell=instance_id,method=method,budget=budget,
                    gri_at_sample_mean=risk_sample,gri_at_true_mean=risk_ideal,empirical_failure_rate=empirical,
                    abs_diff_gaussianity=diff,abs_diff_true_mean=abs(risk_ideal-empirical),tau_R=float(config['tau_R']),
                    calibration_within_tolerance=bool(diff<=config['tau_R']),scope='same_sample_calibration_only'))
                folder=output_root/EVIDENCE_REL;folder.mkdir(parents=True,exist_ok=True)
                np.savez_compressed(folder/f'calibration_{instance_id}_{budget}_{method}.npz',samples=samples,
                    failures=failures[method],sigma=sigma,sample_mean=mu_sample,ideal_mean=frozen['mu'],active=active)
    return gaussian_rows,calibration_rows


def bootstrap_indices(*,n,count,instance_id,method,budget,stream):
    if n<2 or count<2 or int(n)!=n or int(count)!=count:raise ValueError('Bootstrap sizes must be integers >= 2')
    rng=make_rng(instance_id=instance_id,method=method,budget=int(budget),replicate_id=0,stream=stream)
    return rng.integers(0,int(n),size=(int(count),int(n)))


def joint_bootstrap_indices(*,n,count,instance_id,budget):
    return bootstrap_indices(n=n,count=count,instance_id=instance_id,method='joint',budget=budget,stream='f1c_joint_bootstrap')


def covariance_ci_summary(samples,active,*,indices,ci):
    """Fit the full estimator in every draw, then extract its active block."""
    active=np.asarray(active,dtype=int)
    if len(active)==0 or not 0<ci<1:raise ValueError('Nonempty active coordinates and valid CI required')
    covariances=np.array([_covariance(samples[row],shrinkage=True)[np.ix_(active,active)] for row in indices])
    lower,upper=np.quantile(covariances,[(1-ci)/2,(1+ci)/2],axis=0);width=upper-lower
    off=width[~np.eye(len(active),dtype=bool)]
    return dict(max_cov_ci_width=float(width.max()),max_diag_ci_width=float(np.diag(width).max()),
        max_offdiag_ci_width=float(off.max()) if len(off) else 0.)


def risk_order(method_names,risks,*,tolerance=RISK_NUMERICAL_TOL):
    """Numerically resolved pairwise relations; '~' means unresolved, not equality."""
    risks=np.asarray(risks,dtype=float)
    if risks.shape!=(len(method_names),) or not np.isfinite(risks).all() or np.any((risks<0)|(risks>1)):
        raise ValueError('Finite probabilities required for all methods')
    labels=[]
    for i,j in itertools.combinations(range(len(method_names)),2):
        delta=risks[i]-risks[j]
        labels.append(f'{method_names[i]}~{method_names[j]}' if abs(delta)<=tolerance else
                      f'{method_names[i]}<{method_names[j]}' if delta<0 else f'{method_names[j]}<{method_names[i]}')
    return ';'.join(labels)


def projected_ratio_for_pair(*,sigma_left,sigma_right,sigma_pred_left,sigma_pred_right,grad_left,grad_right,tau,epsilon0):
    if not np.isfinite(tau) or tau<=epsilon0:raise ValueError('Unresolved tolerance cannot establish a projected comparison')
    signed=float(np.sum(grad_left*(sigma_left-sigma_pred_left))-np.sum(grad_right*(sigma_right-sigma_pred_right)))
    return abs(signed)/tau


def ratio_verdict(ratios,ci):
    low,high=np.quantile(ratios,[(1-ci)/2,(1+ci)/2])
    verdict='interval_crosses_threshold' if low<=1<=high else 'interval_above_threshold' if low>1 else 'interval_below_threshold'
    return dict(bootstrap_ratio_ci_low=float(low),bootstrap_ratio_ci_high=float(high),
                bootstrap_fail_fraction=float(np.mean(ratios>=1)),verdict=verdict)


def audit_rows_for_case(*,output_root,instance_id,budget,config):
    raw,frozen=load_raw_frozen(output_root,instance_id);idx=list(frozen['budgets']).index(budget)
    names=list(map(str,frozen['method_names']));mu=frozen['mu'];meta=json.loads(str(frozen['metadata_json'].item()))
    samples_by_method=method_samples(raw,frozen,idx);samples=np.array([samples_by_method[m] for m in names])
    n=samples.shape[1];count=int(config['bootstrap_replicates']);ci=float(config['bootstrap_ci'])
    active_masks=frozen['active_masks'][:,idx];common=np.flatnonzero(np.any(active_masks,axis=0))
    if len(common)==0:raise ValueError('No active coordinates')
    sigma_pred=frozen['sigma_pred'][:,idx]
    gradients=np.array([common_incumbent_gradient(mu,s) for s in sigma_pred])
    predicted_risks=np.array([gri_risk(mu,s) for s in sigma_pred])
    sigma_hat=np.array([_covariance(s,shrinkage=True) for s in samples]);sigma_raw=np.array([_covariance(s,shrinkage=False) for s in samples])
    full_risks=np.array([gri_risk(mu,s) for s in sigma_hat]);raw_risks=np.array([gri_risk(mu,s) for s in sigma_raw])
    common_risks=np.array([gri_risk(mu[common],s[np.ix_(common,common)]) for s in sigma_hat])
    common_raw=np.array([gri_risk(mu[common],s[np.ix_(common,common)]) for s in sigma_raw])
    indices=joint_bootstrap_indices(n=n,count=count,instance_id=instance_id,budget=budget)
    boot_cov=np.array([[_covariance(s[row],shrinkage=True) for s in samples] for row in indices])
    boot_risks=np.array([[gri_risk(mu[common],s[np.ix_(common,common)]) for s in covs] for covs in boot_cov])
    ci_rows=[];shrink=[];suff=[];stability=[]
    for mi,method in enumerate(names):
        active=np.flatnonzero(active_masks[mi]);covs=boot_cov[:,mi][:,active][:,:,active]
        low,high=np.quantile(covs,[(1-ci)/2,(1+ci)/2],axis=0);width=high-low;off=width[~np.eye(len(active),dtype=bool)]
        ci_rows.append(dict(problem_cell=instance_id,method=method,budget=budget,active_dim=len(active),
            max_cov_ci_width=float(width.max()),max_diag_ci_width=float(np.diag(width).max()),max_offdiag_ci_width=float(off.max()) if off.size else 0.,
            estimator='full_LedoitWolf_then_submatrix',scope='pointwise_percentile_width_not_simultaneous_band'))
        shrink.append(dict(problem_cell=instance_id,method=method,budget=budget,risk_ledoit_wolf=float(full_risks[mi]),risk_sample_cov=float(raw_risks[mi]),abs_risk_shift=float(abs(full_risks[mi]-raw_risks[mi]))))
        for size in map(int,config['subsample_sizes']):
            if size>n:continue
            rng=make_rng(instance_id=instance_id,method=method,budget=budget,replicate_id=size,stream='f1c_sigmahat_subsample')
            chosen=rng.choice(n,size=size,replace=False)
            value=gri_risk(mu,_covariance(samples[mi,chosen],shrinkage=True))
            suff.append(dict(problem_cell=instance_id,method=method,budget=budget,subsample_R=size,risk_subsample=value,
                             risk_full_R=float(full_risks[mi]),abs_risk_shift_from_full=float(abs(value-full_risks[mi])),scope='one_subsample_sensitivity_not_sample_size_sufficiency'))
    relation=risk_order(names,common_risks)
    boot_patterns=[risk_order(names,r) for r in boot_risks]
    stability.append(dict(problem_cell=instance_id,budget=budget,ordering_ledoit_wolf=risk_order(names,full_risks),
        ordering_sample_cov=risk_order(names,raw_risks),common_subset=common.tolist(),restricted_ordering_ledoit_wolf=relation,
        restricted_ordering_sample_cov=risk_order(names,common_raw),bootstrap_relation_pattern_frequency=float(np.mean([r==relation for r in boot_patterns])),
        all_baseline_relations_resolved='~' not in relation,bootstrap_scope='common_subset_same_fixed_ideal_mean_not_full_risk',numerical_tolerance=RISK_NUMERICAL_TOL))
    pairs=list(map(str,frozen['pair_names']));signed=[];boot_signed=[]
    for pair in pairs:
        left,right=pair.split('_vs_');li=names.index(left);ri=names.index(right)
        delta=float(predicted_risks[li]-predicted_risks[ri]);tau=meta['rho_flip']*abs(delta)
        active=abs(delta)>=meta['mde_absolute'] and abs(delta)>RISK_NUMERICAL_TOL
        point=float(np.sum(gradients[li]*(sigma_hat[li]-sigma_pred[li]))-np.sum(gradients[ri]*(sigma_hat[ri]-sigma_pred[ri])))
        draws=np.einsum('ij,bij->b',gradients[li],boot_cov[:,li]-sigma_pred[li])-np.einsum('ij,bij->b',gradients[ri],boot_cov[:,ri]-sigma_pred[ri])
        signed.append(point);boot_signed.append(draws)
        row=dict(problem_cell=instance_id,budget=budget,pair_id=pair,active_pair=bool(active),predicted_delta=delta,tau=tau,
            signed_projected_error=point,baseline_projected_ratio=abs(point)/tau if active else None,
            bootstrap_ratio_ci_low=None,bootstrap_ratio_ci_high=None,bootstrap_fail_fraction=None,verdict='inactive_pair',
            scope='fixed_ideal_mean_full_gradient_linearized_covariance_error')
        if active:row.update(ratio_verdict(abs(draws)/tau,ci))
        stability.append(row)
    folder=output_root/EVIDENCE_REL;folder.mkdir(parents=True,exist_ok=True)
    path=folder/f'{instance_id}_B{budget}.npz'
    np.savez_compressed(path,methods=np.array(names),pairs=np.array(pairs),budget=budget,mu=mu,samples=samples,
        sigma_pred=sigma_pred,gradients=gradients,predicted_risks=predicted_risks,sigma_hat=sigma_hat,sigma_raw=sigma_raw,
        full_risks=full_risks,raw_risks=raw_risks,common_subset=common,active_masks=active_masks,common_risks=common_risks,
        bootstrap_indices=indices,bootstrap_covariances=boot_cov,bootstrap_common_risks=boot_risks,
        signed_projection_errors=np.array(signed),bootstrap_signed_projection_errors=np.array(boot_signed))
    _dump(path.with_suffix('.json'),dict(schema=AUDIT_SCHEMA,instance_id=instance_id,budget=budget,
        raw_sha256=sha256(output_root/raw_relpath(instance_id)),frozen_sha256=sha256(output_root/FROZEN_REL_DIR/f'{instance_id}.npz'),
        evidence_sha256=sha256(path),bootstrap_ci=ci,bootstrap_replicates=count,rho_flip=meta['rho_flip'],mde_absolute=meta['mde_absolute'],
        original_frozen_derivative=meta['gradient'],corrected_derivative='full_common_incumbent_Frobenius',
        ci_rows=ci_rows,shrinkage_rows=shrink,sensitivity_rows=suff,stability_rows=stability))
    return ci_rows,shrink,suff,stability



def load_current_case_evidence(output_root,instance_id,budget,*,gradients,predicted_risks):
    """Accept only a complete audit for the exact raw/frozen sources and derivative."""
    folder=output_root/EVIDENCE_REL
    index_path=folder/'audit_index.json'
    if not index_path.exists():return None
    index=json.loads(index_path.read_text(encoding='utf-8'))
    if index.get('schema')!=AUDIT_SCHEMA:raise ValueError('Unsupported A3 audit schema')
    source=index['sources'].get(instance_id)
    if source is None:return None
    for key,path in [('raw_sha256',output_root/raw_relpath(instance_id)),('frozen_sha256',output_root/FROZEN_REL_DIR/f'{instance_id}.npz')]:
        if source[key]!=sha256(path):raise ValueError('A3 audit source hash mismatch')
    key=f'{instance_id}_B{budget}';path=folder/f'{key}.npz'
    if key not in index['cases']:return None
    metadata=json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
    if (metadata['schema']!=AUDIT_SCHEMA or metadata['instance_id']!=instance_id or metadata['budget']!=budget
        or metadata['raw_sha256']!=source['raw_sha256'] or metadata['frozen_sha256']!=source['frozen_sha256']
        or sha256(path)!=index['cases'][key] or sha256(path)!=metadata['evidence_sha256']):
        raise ValueError('A3 audit evidence hash/identity mismatch')
    with np.load(path,allow_pickle=False) as data:case={k:data[k] for k in data.files}
    if not np.array_equal(case['gradients'],gradients) or not np.array_equal(case['predicted_risks'],predicted_risks):
        raise ValueError('A3 audit gradient or risk differs from the consumer')
    rows=[r for r in index['calibration_rows'] if r['problem_cell']==instance_id and r['budget']==budget]
    calibration={r['method']:r['calibration_within_tolerance'] for r in rows}
    if len(calibration)!=len(rows) or any(type(v) is not bool for v in calibration.values()):raise ValueError('Malformed A3 calibration rows')
    return case,metadata,calibration


def c3_bootstrap_summary(case,pair_index,*,signed_learned_error,tau,ci):
    """Use C3's own tolerance and shift BOTH endpoints by learned-minus-true."""
    if tau<=0 or not np.isfinite(tau):raise ValueError('Positive C3 tolerance required')
    draws=case['bootstrap_signed_projection_errors'][pair_index]
    return dict(reference=ratio_verdict(abs(draws)/tau,ci),
                learned=ratio_verdict(abs(draws-signed_learned_error)/tau,ci))

def render_gaussianity_report(output_root,gaussian_rows,calibration_rows,config):
    lines=['# A3 Gaussianity and same-sample calibration','',
        'Exploratory diagnostics. Marginal flags are not multiplicity-adjusted; lack of rejection does not establish normality. HZ is a descriptive statistic without a calibrated rejection rule here.',
        'Tail ratios remain descriptive when the expected normal count is below five. At n=200, the expected count beyond three standard deviations is about 0.54; zero observations is not a failure of normality.',
        'Calibration fits the Gaussian mean/covariance and evaluates failure using the same repetitions. Passing the absolute tolerance is not held-out model validation. Fixed-ideal-mean scores isolate covariance and do not include method bias.','',
        '## Active-gap diagnostics','','| cell | method | B | active | flagged | HZ |','|---|---|---:|---|---|---:|']
    for r in gaussian_rows:lines.append(f"| {r['problem_cell']} | {r['method']} | {r['budget']} | {r['active_gaps']} | {r['flagged_gaps']} | {r['henze_zirkler']} |")
    lines+=['','## GRI vs Empirical Failure','','| cell | method | B | GRI_sample_mean | GRI_ideal_mean | empirical_failure | abs_diff_sample | abs_diff_ideal | tau_R | within_tolerance |','|---|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in calibration_rows:
        lines.append('| {problem_cell} | {method} | {budget} | {gri_at_sample_mean:.9g} | {gri_at_true_mean:.9g} | {empirical_failure_rate:.9g} | {abs_diff_gaussianity:.9g} | {abs_diff_true_mean:.9g} | {tau_R:.9g} | {calibration_within_tolerance} |'.format(**r))
    lines+=['','HZ normalization and scope: https://doi.org/10.1007/s11749-020-00740-0; tuning parameter: https://search.r-project.org/CRAN/refmans/mnt/html/HZ.html.']
    p=output_root/GAUSSIANITY_REL;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('\n'.join(lines)+'\n',encoding='utf-8')


def render_sigmahat_report(output_root,ci_rows,shrinkage_rows,sufficiency_rows,stability_rows,config):
    lines=['# A3 covariance bootstrap diagnostic','',
        'All draws resample shared replicate IDs jointly across methods. Each draw refits the full Ledoit-Wolf covariance before extracting submatrices. Coefficients, ideal margins and reference covariance remain fixed.',
        'Pointwise percentile intervals describe estimator variability conditional on this pilot. They are not simultaneous coverage bounds or certified population-error bounds. One random subsample per size is a sensitivity check, not proof of sample-size sufficiency.',
        'Full-risk point relations and bootstrap relations on one common restricted gap event are reported separately. A tilde means numerically unresolved within 2e-6, not exact equality. Repeated unresolved relations do not certify a strict order.',
        'Projection uses the full analytic Frobenius gradient of the reference covariance and recomputed margins. Pairs below the original absolute risk margin 0.005 are inactive. The projected condition is linearized and does not control Taylor remainder or method-dependent bias.','',
        f"Bootstrap draws: {config['bootstrap_replicates']}; percentile interval: {config['bootstrap_ci']}.",'',
        '## Projected covariance-error ratios','','| cell | B | pair | active | point | CI low | CI high | fraction above 1 | diagnostic |','|---|---:|---|---|---:|---:|---:|---:|---|']
    for r in stability_rows:
        if 'pair_id' in r:lines.append('| {problem_cell} | {budget} | {pair_id} | {active_pair} | {baseline_projected_ratio} | {bootstrap_ratio_ci_low} | {bootstrap_ratio_ci_high} | {bootstrap_fail_fraction} | {verdict} |'.format(**r))
    lines+=['','All covariance widths, shrinkage comparisons, subsamples, relations and underlying bootstrap arrays are saved in a3_audit_evidence/. See audit_index.json for source hashes and schema.']
    (output_root/SIGMAHAT_AUDIT_REL).write_text('\n'.join(lines)+'\n',encoding='utf-8')


def finish_audit(output_root,config,gaussian_rows,calibration_rows,cases):
    ci,shrink,suff,stable=([r for case in cases for r in case[i]] for i in range(4))
    render_gaussianity_report(output_root,gaussian_rows,calibration_rows,config)
    render_sigmahat_report(output_root,ci,shrink,suff,stable,config)
    folder=output_root/EVIDENCE_REL
    sources={}
    for instance in sorted({r['problem_cell'] for r in stable}):
        sources[instance]=dict(raw_sha256=sha256(output_root/raw_relpath(instance)),frozen_sha256=sha256(output_root/FROZEN_REL_DIR/f'{instance}.npz'))
    payload=dict(schema=AUDIT_SCHEMA,config=config,sources=sources,gaussianity_rows=gaussian_rows,calibration_rows=calibration_rows,
        ci_rows=ci,shrinkage_rows=shrink,sensitivity_rows=suff,stability_rows=stable,
        cases={p.stem:sha256(p) for p in sorted(folder.glob('P*_B*.npz'))})
    _dump(folder/'audit_index.json',payload)
    result=dict(schema=AUDIT_SCHEMA,gaussianity_rows=len(gaussian_rows),calibration_rows=len(calibration_rows),
        within_tolerance=sum(r['calibration_within_tolerance'] for r in calibration_rows),audit_cases=len(cases),
        pair_verdicts={v:sum(r.get('verdict')==v for r in stable) for v in ['inactive_pair','interval_below_threshold','interval_crosses_threshold','interval_above_threshold']})
    _dump(folder/'summary.json',result)
    return result


def run(output_root=DEFAULT_OUTPUT_ROOT,*,profile='smoke'):
    start=time.perf_counter();config=load_config(profile)
    gaussian,calibration=gaussianity_rows(output_root,config)
    jobs=[(i,int(b)) for i in config['instance_ids'] for b in load_raw_frozen(output_root,i)[1]['budgets']]
    for focus in config.get('focus_cases',[]):
        job=(str(focus['instance_id']),int(focus['budget']))
        if job not in jobs:jobs.append(job)
    cases=[audit_rows_for_case(output_root=output_root,instance_id=i,budget=b,config=config) for i,b in jobs]
    result=finish_audit(output_root,config,gaussian,calibration,cases);result['seconds']=time.perf_counter()-start
    print(json.dumps(result,indent=2));return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT_ROOT);parser.add_argument('--profile',default='smoke')
    args=parser.parse_args(argv);run(args.output,profile=args.profile);return 0
if __name__=='__main__':raise SystemExit(main())
