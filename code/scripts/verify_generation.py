"""Reconstruct primitive moments, covariance, derivatives and decisions independently."""
import argparse,json,hashlib,math
from pathlib import Path
from fractions import Fraction
import numpy as np
import pandas as pd
from scipy.integrate import quad
from scipy.special import log_ndtr
from scipy.stats import norm


def structured_risk(mu,sigma):
    n=len(mu);shared=float(np.median(sigma[~np.eye(n,dtype=bool)]));v=np.diag(sigma)-shared
    def f(t):return norm.pdf(t)*(-np.expm1(np.sum(log_ndtr((mu-np.sqrt(shared)*t)/np.sqrt(v)))))
    return quad(f,-14,14,epsabs=2e-12,epsrel=2e-11,limit=200)[0]


def digest(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest().upper()


def verify(package,previous=None):
    errors={k:0. for k in ('mean','variance','covariance','risk','gradient_direction','projected_error')}
    differences={k:0. for k in ('primitive_mean_unit','primitive_variance_unit','method_coefficients','risks_pred','gradients')}
    prior_differences=dict(risks=0.,gradients=0.) if previous else None
    decision_changes=[];checked=0;directions=0;unmasked=0;frames=[];calibration=[]
    def check(key,a,b,tol):
        err=float(np.max(np.abs(np.asarray(a)-np.asarray(b))));errors[key]=max(errors[key],err)
        assert err<=tol,(key,err,tol)
    frontier=pd.read_csv(package/'results/pilot/pullback_frontier.csv')
    for instance in ('P001','P002','P003','P004'):
        with np.load(package/f'results/pilot/a3_frozen_prediction/{instance}.npz') as data:f={k:data[k] for k in data.files}
        with np.load(package/f'inputs/pilot/a3_frozen_prediction/{instance}.npz') as data:old={k:data[k] for k in data.files}
        with np.load(package/f'results/pilot/raw/{instance}.npz') as data:raw={k:data[k] for k in data.files}
        meta=json.loads(str(f['metadata_json']));evidence=package/'results'/meta['primitive_evidence_path']
        assert digest(evidence)==meta['primitive_evidence_hash']
        assert not meta['prospective_preregistration']
        with np.load(evidence) as data:e={k:data[k] for k in data.files}
        p=e['probabilities'];values=e['values_by_state'];mu=f['mu'];x=int(f['x_star']);comp=[i for i in range(len(f['ideal_values'])) if i!=x]
        assert p.shape==(3,25,1024) and np.all(p>=0)
        np.testing.assert_allclose(p.sum(axis=-1),1.,rtol=0,atol=3e-15)
        means=np.array([[math.fsum(float(w)*float(v) for w,v in zip(probs,values)) for probs in scale] for scale in p])
        variances=np.array([[math.fsum(float(w)*(float(v)-float(m))**2 for w,v in zip(probs,values)) for probs,m in zip(scale,mm)] for scale,mm in zip(p,means)])
        check('mean',f['primitive_mean_unit'],means,1e-13);check('variance',f['primitive_variance_unit'],variances,1e-13)
        for key in differences:differences[key]=max(differences[key],float(np.max(abs(f[key]-old[key]))))
        names=list(f['method_names'])
        for bi,b in enumerate(f['budgets']):
            rawbi=list(raw['budgets']).index(b)
            ints=np.rint(raw['primitive_objective_estimates'][...,rawbi]*b).astype(np.int64)
            np.testing.assert_allclose(ints,raw['primitive_objective_estimates'][...,rawbi]*b,rtol=0,atol=1e-9)
            if previous:
                with np.load(previous/f'results/pilot/a3_audit_evidence/{instance}_B{b}.npz') as case:
                    prior_differences['risks']=max(prior_differences['risks'],float(np.max(abs(case['predicted_risks']-f['risks_pred'][:,bi]))))
                    prior_differences['gradients']=max(prior_differences['gradients'],float(np.max(abs(case['gradients']-f['gradients'][:,bi]))))
            from experiments.a3_gaussianity_sigmahat_audit import method_failures, method_samples
            from scripts.verify_a3_audit import lw_cov
            from daqem.risk import gri_risk
            engine_failures=method_failures(raw,f,bi)
            samples_by_method=method_samples(raw,f,bi)
            for mi,name in enumerate(names):
                coefficients=f['method_coefficients'][mi]
                if name=='Raw':np.testing.assert_array_equal(coefficients,[1.,0.,0.])
                else:np.testing.assert_allclose([coefficients.sum(),coefficients@np.arange(1,4)],[1.,0.],rtol=0,atol=1e-10)
                marginal=(coefficients**2)@variances/b
                sigma=np.diag(marginal[comp])+marginal[x]
                check('covariance',f['sigma_pred'][mi,bi],sigma,3e-12)
                sigma=f['sigma_pred'][mi,bi];grad=f['gradients'][mi,bi]
                check('risk',structured_risk(mu,sigma),f['risks_pred'][mi,bi],2e-6)
                shared=float(np.median(sigma[~np.eye(len(mu),dtype=bool)]));v=np.diag(sigma)-shared
                for direction in (np.diag(.05*v*np.cos(np.arange(len(v)))),np.full_like(sigma,.03*shared)):
                    step=.001
                    deriv=(structured_risk(mu,sigma+step*direction)-structured_risk(mu,sigma-step*direction))/(2*step)
                    check('gradient_direction',deriv,np.sum(grad*direction),2e-9);directions+=1
                unmasked+=int(np.any(abs(grad[~old['active_masks'][mi,bi]])>1e-12))
                flags=[]
                for coefficient_set in (old['method_coefficients'][mi],coefficients):
                    if name=='Raw':weights=[Fraction(1),Fraction(0),Fraction(0)]
                    elif name=='Accuracy-ZNE':weights=[Fraction(4,3),Fraction(1,3),Fraction(-2,3)]
                    else:
                        t=Fraction(float(coefficient_set[2]));weights=[2+t,-1-2*t,t]
                    flags.append(np.array([any(sum(weights[k]*int(r[k,j]-r[k,x]) for k in range(3))<=0 for j in comp) for r in ints]))
                assert np.array_equal(flags[1],engine_failures[name])
                checked+=len(flags[1])
                changed=int(np.count_nonzero(flags[0]!=flags[1]))
                if changed:decision_changes.append(dict(instance=instance,budget=int(b),method=name,changed=changed,old_rate=float(flags[0].mean()),new_rate=float(flags[1].mean())))
                samples=samples_by_method[name]
                score=gri_risk(samples.mean(axis=0),lw_cov(samples),B=1.)
                calibration.append(dict(instance=instance,budget=int(b),method=name,failure_rate=float(flags[1].mean()),
                    sample_mean_covariance_GRI=score,within_tolerance=bool(abs(score-flags[1].mean())<=.05)))
            for pi,pair in enumerate(f['pair_names']):
                left,right=str(pair).split('_vs_');li=names.index(left);ri=names.index(right)
                delta=f['risks_pred'][li,bi]-f['risks_pred'][ri,bi]
                assert abs(delta-f['delta_pred'][pi,bi])<1e-15
                assert abs(.5*abs(delta)-f['tau_flip_projected'][pi,bi])<1e-15
                row=frontier[(frontier.problem_cell==instance)&(frontier.budget==b)&(frontier.pair_id==pair)].iloc[0]
                assert row.active_pair==bool(abs(delta)>=.005)
                def cov(method_index):
                    from scripts.verify_a3_audit import lw_cov
                    primitive=raw['primitive_objective_estimates'][...,rawbi]
                    estimates=np.einsum('s,rsc->rc',f['method_coefficients'][method_index],primitive)
                    # Independent reconstruction of the full estimator.
                    return lw_cov(estimates[:,comp]-estimates[:,[x]])
                projected=abs(np.trace(f['gradients'][li,bi].T@(cov(li)-f['sigma_pred'][li,bi]))-np.trace(f['gradients'][ri,bi].T@(cov(ri)-f['sigma_pred'][ri,bi])))
                check('projected_error',projected,row.delta_rank_projected,1e-11)
    archived=pd.read_csv(package/'inputs/pilot/pullback_frontier.csv')
    merged=frontier.merge(archived,on=['problem_cell','budget','pair_id'],suffixes=('_new','_old'),validate='one_to_one')
    changes={col:int((merged[col+'_new']!=merged[col+'_old']).sum()) for col in ('active_pair','a3_status','ordering_match','predicted_order','empirical_order')}
    result=dict(errors=errors,difference_from_archived_prediction=differences,
        difference_from_previous_corrected_audit=prior_differences,
        decisions_checked=checked,decision_changes=decision_changes,derivative_directions_checked=directions,
        gradients_with_nonzero_entries_outside_old_mask=unmasked,frontier_changes=changes,
        active=int(frontier.active_pair.sum()),statuses=frontier.a3_status.value_counts().to_dict(),
        active_statuses=frontier[frontier.active_pair].a3_status.value_counts().to_dict(),
        calibration_within_tolerance=sum(r['within_tolerance'] for r in calibration),calibration_rates=calibration)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--previous',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=verify(args.package,args.previous)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='calibration_rates'},indent=2))
