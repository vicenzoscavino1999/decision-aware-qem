"""Independent reconstruction of A3 bootstrap arrays and strict pilot decisions."""
import argparse,itertools,json,math
from fractions import Fraction
from pathlib import Path
import numpy as np
from scipy.integrate import quad
from scipy.special import log_ndtr
from scipy.stats import norm,multivariate_normal


def lw_cov(samples):
    x=samples-samples.mean(axis=0);n,p=x.shape
    empirical=x.T@x/n;mu=np.trace(empirical)/p
    delta=np.sum(empirical**2)/p-mu*mu
    beta=(np.mean(np.sum(x*x,axis=1)**2)-np.sum(empirical**2))/(p*n)
    shrink=0. if delta<=0 else min(max(beta,0.),delta)/delta
    return (1-shrink)*empirical+shrink*mu*np.eye(p)


def structured_risk(mu,sigma):
    d=len(mu);shared=float(np.median(sigma[~np.eye(d,dtype=bool)]));v=np.diag(sigma)-shared
    def f(t):return norm.pdf(t)*(-np.expm1(np.sum(log_ndtr((mu-np.sqrt(shared)*t)/np.sqrt(v)))))
    return quad(f,-14,14,epsabs=2e-12,epsrel=2e-11,limit=200)[0]


def verify(package):
    root=package/'results';folder=root/'pilot/a3_audit_evidence'
    index=json.loads((folder/'audit_index.json').read_text())
    errors={k:0. for k in ('bootstrap_covariance','prediction_covariance','signed_projection','interval_endpoint','structured_risk','gradient_direction','common_risk_crosscheck','calibration_covariance')}
    def check(key,a,b,tol):
        err=float(np.max(np.abs(np.asarray(a)-np.asarray(b))));errors[key]=max(errors[key],err)
        assert err<=tol,(key,err,tol)
    rows={}
    for r in index['stability_rows']:
        if 'pair_id' in r:rows[r['problem_cell'],r['budget'],r['pair_id']]=r
    boot_count=0;directions=0
    for name in sorted(index['cases']):
        with np.load(folder/f'{name}.npz') as data:d={k:data[k] for k in data.files}
        instance=name.split('_')[0];budget=int(d['budget']);names=list(d['methods']);pairs=list(d['pairs']);bi=None
        with np.load(package/f'results/pilot/a3_frozen_prediction/{instance}.npz') as frozen:
            bi=list(frozen['budgets']).index(budget)
            predicted=np.array([(m*frozen['cdev_true_diag_unit'])@m.T/budget for m in frozen['gap_maps']])
        check('prediction_covariance',predicted,d['sigma_pred'],3e-12)
        covs=np.array([[lw_cov(sample[inds]) for sample in d['samples']] for inds in d['bootstrap_indices']])
        check('bootstrap_covariance',covs,d['bootstrap_covariances'],3e-12);boot_count+=covs.shape[0]*covs.shape[1]
        sigma=np.array([lw_cov(s) for s in d['samples']]);g=d['gradients'];pred=d['sigma_pred']
        for pi,pair in enumerate(pairs):
            left,right=pair.split('_vs_');li=names.index(left);ri=names.index(right)
            # Explicit traces include both off-diagonal entries.
            errors_boot=np.array([np.trace(g[li].T@(c[li]-pred[li]))-np.trace(g[ri].T@(c[ri]-pred[ri])) for c in covs])
            check('signed_projection',errors_boot,d['bootstrap_signed_projection_errors'][pi],2e-12)
            point=np.trace(g[li].T@(sigma[li]-pred[li]))-np.trace(g[ri].T@(sigma[ri]-pred[ri]))
            check('signed_projection',point,d['signed_projection_errors'][pi],2e-12)
            row=rows[instance,budget,pair]
            if row['active_pair']:
                interval=np.quantile(abs(errors_boot)/row['tau'],[.025,.975])
                check('interval_endpoint',interval,[row['bootstrap_ratio_ci_low'],row['bootstrap_ratio_ci_high']],2e-10)
            else:assert row['baseline_projected_ratio'] is None and row['verdict']=='inactive_pair'
        common=d['common_subset']
        for mi in range(len(names)):
            risk=structured_risk(d['mu'],pred[mi]);check('structured_risk',risk,d['predicted_risks'][mi],2e-6)
            s=float(np.median(pred[mi][~np.eye(len(d['mu']),dtype=bool)]));v=np.diag(pred[mi])-s
            direction=np.diag(.05*v*np.cos(np.arange(len(v))))+.03*s
            h=.001
            derivative=(structured_risk(d['mu'],pred[mi]+h*direction)-structured_risk(d['mu'],pred[mi]-h*direction))/(2*h)
            check('gradient_direction',derivative,np.sum(g[mi]*direction),2e-9);directions+=1
            # Independent seed and more points; rare scores are bounded by marginals.
            mu=d['mu'][common];c=sigma[mi][np.ix_(common,common)];marg=norm.sf(mu/np.sqrt(np.diag(c)))
            saved=d['common_risks'][mi]
            if marg.sum()<1e-7:assert marg.max()<=saved*(1+1e-7) and saved<=marg.sum()*(1+1e-7)
            else:
                direct=1-multivariate_normal.cdf(mu,cov=c,rng=np.random.default_rng(9182),maxpts=2000000,abseps=1e-8,releps=1e-8)
                check('common_risk_crosscheck',direct,saved,2e-6)
    decisions=0;calibration_changes=[]
    for row in index['calibration_rows']:
        instance=row['problem_cell'];b=row['budget'];m=row['method']
        with np.load(package/f'results/pilot/raw/{instance}.npz') as raw:
            idx=list(raw['budgets']).index(b);sums=(raw['primitive_objective_estimates'][:,:,:,idx]*b).astype(np.int64);x=int(raw['x_star'])
        with np.load(package/f'results/pilot/a3_frozen_prediction/{instance}.npz') as frozen:
            coefficients=frozen['method_coefficients'][list(frozen['method_names']).index(m)]
        if m=='Raw':weights=[Fraction(1),Fraction(0),Fraction(0)]
        elif m=='Accuracy-ZNE':weights=[Fraction(4,3),Fraction(1,3),Fraction(-2,3)]
        else:
            t=Fraction(float(coefficients[2]));weights=[2+t,-1-2*t,t]
        flags=np.array([any(sum(weights[k]*int(r[k,j]-r[k,x]) for k in range(3))<=0 for j in range(r.shape[1]) if j!=x) for r in sums])
        with np.load(folder/f'calibration_{instance}_{b}_{m}.npz') as data:
            assert np.array_equal(flags,data['failures'])
            check('calibration_covariance',lw_cov(data['samples']),data['sigma'],3e-12)
        assert np.mean(flags)==row['empirical_failure_rate']
        assert row['calibration_within_tolerance']==(abs(row['gri_at_sample_mean']-np.mean(flags))<=row['tau_R'])
        decisions+=len(flags)
    return dict(cases=len(index['cases']),bootstrap_covariances=boot_count,gradient_direction_checks=directions,strict_decisions=decisions,max_errors=errors)


def verify_c3(package):
    folder=package/'results/pilot/a3_audit_evidence'
    result=json.loads((package/'results/pilot/c3_reanalysis.json').read_text())
    checked=0;max_error=0.;ratios_checked=0
    c2={(r['cell'],r['pair_id'],r['budget']):r for r in result['c2']}
    for row in result['c3']:
        instance=row['cell'];budget=row['budget']
        with np.load(folder/f'{instance}_B{budget}.npz') as d:
            names=list(d['methods']);pairs=list(d['pairs']);pi=pairs.index(row['pair_id']);left,right=row['pair_id'].split('_vs_')
            li,ri=names.index(left),names.index(right);g=d['gradients'];pred=d['sigma_pred']
            draws=d['bootstrap_signed_projection_errors'][pi];observed=d['sigma_hat']
            tau=result['rho_C']*abs(d['predicted_risks'][li]-d['predicted_risks'][ri])
        with np.load(package/f'results/pilot/cdev_evidence/{instance}_propagation.npz') as learned:
            with np.load(package/f'results/pilot/a3_frozen_prediction/{instance}.npz') as frozen:bi=list(frozen['budgets']).index(budget)
            import hashlib
            metadata=json.loads(str(learned['metadata_json']))
            assert metadata['reference_prediction_sha256']==hashlib.sha256((package/f'results/pilot/a3_frozen_prediction/{instance}.npz').read_bytes()).hexdigest()
            sigma=learned['sigma_learned'][:,bi]
        shift=np.trace(g[li].T@(sigma[li]-pred[li]))-np.trace(g[ri].T@(sigma[ri]-pred[ri]))
        reference_error=np.trace(g[li].T@(observed[li]-pred[li]))-np.trace(g[ri].T@(observed[ri]-pred[ri]))
        learned_error=np.trace(g[li].T@(observed[li]-sigma[li]))-np.trace(g[ri].T@(observed[ri]-sigma[ri]))
        c2row=c2[(instance,row['pair_id'],budget)];denominator=max(tau,1e-12)
        np.testing.assert_allclose(c2row['tau_C'],tau,atol=1e-15,rtol=1e-12)
        for value,numerator in ((c2row['projected_error_over_tolerance'],abs(shift)),
                                (row['true_vs_sigmahat_ratio'],abs(reference_error)),
                                (row['learned_vs_sigmahat_ratio'],abs(learned_error))):
            np.testing.assert_allclose(value*denominator,numerator,atol=1e-11,rtol=1e-9)
            ratios_checked+=1
        assert row['true_vs_sigmahat_status']==('pass' if abs(reference_error)<denominator else 'fail')
        assert c2row['c2_status']==('inactive' if not row['active_pair'] else 'pass' if abs(shift)<denominator else 'fail')
        if not row['active_pair']:
            assert row['sampling_intervals_at_C3_tolerance'] is None
            continue
        for key,values in [('reference',abs(draws)/tau),('learned',abs(draws-shift)/tau)]:
            interval=np.quantile(values,[.025,.975]);record=row['sampling_intervals_at_C3_tolerance'][key]
            error=float(np.max(abs(interval-[record['bootstrap_ratio_ci_low'],record['bootstrap_ratio_ci_high']])))
            max_error=max(max_error,error);assert error<2e-12
            verdict='interval_crosses_threshold' if interval[0]<=1<=interval[1] else 'interval_above_threshold' if interval[0]>1 else 'interval_below_threshold'
            assert verdict==record['verdict']
        checked+=1
    return dict(active_pairs=checked,intervals=2*checked,ratios_checked=ratios_checked,max_interval_error=max_error)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--c3-only',action='store_true')
    args=p.parse_args();result=verify_c3(args.package) if args.c3_only else verify(args.package);args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
