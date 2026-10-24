"""Independently replay saved auxiliary evidence, without new physical simulation."""
import argparse
import csv
import json
import math
from fractions import Fraction
from pathlib import Path
import numpy as np
from scipy.integrate import quad
from scipy.special import log_ndtr
from scipy.stats import norm, binom


def independent_gri(means, variances, xstar):
    comp=[i for i in range(len(means)) if i!=xstar]
    gaps=means[comp]-means[xstar]
    def integrand(t):
        z=(gaps-np.sqrt(variances[xstar])*t)/np.sqrt(variances[comp])
        return norm.pdf(t)*(-np.expm1(np.sum(log_ndtr(z))))
    return quad(integrand,-12,12,epsabs=2e-11,epsrel=2e-11,limit=200)[0]


def verify(package: Path):
    errors={k:0. for k in ('probability_normalization','moment_mean','moment_variance','gamma_relative','grid_mse','grid_gri','pilot_mse')}
    def check(key,a,b,tol):
        error=float(np.max(np.abs(np.asarray(a)-np.asarray(b))))
        errors[key]=max(errors[key],error)
        assert error<=tol,(key,error,tol)
    grid=list(csv.DictReader((package/'results/phase_diagram/grid.csv').open()))
    bykey={(float(r['p1']),int(r['budget']),r['method']):r for r in grid}
    assert len(bykey)==len(grid)==96
    checked_grid=unavailable=distributions=0
    for folder in sorted((package/'results/phase_diagram/evidence').iterdir()):
        record=json.loads((folder/'instance_analytics.json').read_text())[0]
        cfg=json.loads((folder/'config_used.json').read_text())
        p1,p2=cfg['noise']['p1'],cfg['noise']['p2'];cell=cfg['cell']
        g1=1+1.5*p1/(1-p1);g2=1+1.875*p2/(1-p2)
        gamma2=(g1**(cell['num_qubits']*(cell['depth']+1))*g2**(cell['num_qubits']*cell['degree']//2*cell['depth']))**2
        check('gamma_relative',gamma2/record['gamma_squared'],1.,2e-12)
        with np.load(folder/'probabilities/POM_001_probabilities.npz') as data:
            probs=data['noisy_probs'];ideal_probs=data['ideal_probs'];values=data['values_by_state'];ideal=data['ideal_values'];xstar=int(data['x_star'])
        all_probs=np.concatenate([probs,ideal_probs[None]],axis=0)
        assert np.min(all_probs)>=0
        check('probability_normalization',all_probs.sum(axis=-1),1.,2e-12)
        means=np.sum(probs*values,axis=-1)
        variances=np.sum(probs*(values-means[:,:,None])**2,axis=-1)
        ideal_var=np.sum(ideal_probs*(values-ideal[:,None])**2,axis=-1)
        check('moment_mean',means,record['noisy_means'],2e-12)
        check('moment_variance',variances,record['noisy_vars'],2e-12)
        check('moment_variance',ideal_var,record['ideal_vars'],2e-12)
        distributions+=int(np.prod(all_probs.shape[:-1]))
        slope,intercept=np.linalg.lstsq(np.column_stack([means[0],np.ones(len(ideal))]),ideal,rcond=None)[0]
        assert slope>0
        for budget in cfg['budget_grid']:
            eff=math.floor(budget/gamma2)
            for method in ('Raw','CDR','PEC'):
                row=bykey[p1,budget,method]
                if method=='PEC' and eff==0:
                    assert row['feasible']=='False' and row['gri']==row['mse']=='' and row['effective_shots']=='0'
                    unavailable+=1
                    continue
                assert row['feasible']=='True'
                if method=='Raw':mu=means[0];var=variances[0]/budget
                elif method=='CDR':mu=slope*means[0]+intercept;var=slope*slope*variances[0]/budget
                else:mu=ideal;var=ideal_var/eff
                mse=np.mean((mu-ideal)**2+var);risk=independent_gri(mu,var,xstar)
                check('grid_mse',mse,float(row['mse']),2e-11)
                check('grid_gri',risk,float(row['gri']),2e-6)
                checked_grid+=1
    # Rebuild every strict decision using Fraction, independently of integer-key helpers.
    table=json.loads((package/'results/pilot/power_table.json').read_text())
    checked_decisions=0
    for row in table:
        path=package/f"results/pilot/power_evidence/{row['cell']}_B{row['budget']}.npz"
        with np.load(path) as d:
            sums=d['shot_sums'];coeffs=d['coefficients'];methods=list(d['methods']);failures=d['failures'];ideal=d['ideal_values'];x=int(d['x_star']);budget=int(d['budget'])
            saved_mse=d['mse'];selected=list(d['selected'])
        with np.load(package/f"inputs/pilot/raw/{row['cell']}.npz") as raw:
            idx=list(raw['budgets']).index(budget)
            assert np.array_equal(sums,raw['primitive_objective_estimates'][:,:,:,idx]*budget)
            assert np.array_equal(ideal,raw['ideal_values'])
        replay=[]
        for m,c,fs,mse in zip(methods,coeffs,failures,saved_mse,strict=True):
            if m=='Raw':weights=[Fraction(1),Fraction(0),Fraction(0)]
            elif m=='Accuracy-ZNE':weights=[Fraction(4,3),Fraction(1,3),Fraction(-2,3)]
            else:
                t=Fraction(float(c[2]));weights=[2+t,-1-2*t,t]
            exact=[]
            for r in sums:
                exact.append(any(sum(weights[s]*int(r[s,j]-r[s,x]) for s in range(3))<=0 for j in range(r.shape[1]) if j!=x))
            assert np.array_equal(exact,fs),(row['cell'],budget,m)
            replay.append(np.array(exact))
            check('pilot_mse',np.mean((np.einsum('s,rsc->rc',c,sums/budget)-ideal)**2),mse,2e-12)
            checked_decisions+=len(exact)
        mse_fail=replay[methods.index(selected[0])];da_fail=replay[methods.index(selected[1])]
        assert (np.sum(mse_fail & da_fail),np.sum(~mse_fail & ~da_fail),np.sum(mse_fail & ~da_fail),np.sum(~mse_fail & da_fail))==tuple(row[k] for k in ('both_fail','both_ok','b','c'))
        assert np.mean(mse_fail)==row['failure_rate_MSE'] and np.mean(da_fail)==row['failure_rate_DA']
        assert row['MSE_selected_method']==min(zip(methods,saved_mse),key=lambda p:(p[1],p[0]))[0]
    summary=json.loads((package/'results/pilot/power_summary.json').read_text())
    pool=summary['pooled'];n=summary['planned_pairs'];alpha=summary['alpha']
    prob_discord=(pool['b']+pool['c'])/pool['paired_n_pilot'];prob_b=pool['b']/(pool['b']+pool['c'])
    terms=[]
    for d in range(n+1):
        # Binary search the smallest rejecting number of DA-better pairs.
        lo,hi=0,d+1
        while lo<hi:
            mid=(lo+hi)//2
            if binom.sf(mid-1,d,.5)<=alpha:hi=mid
            else:lo=mid+1
        terms.append(binom.pmf(d,n,prob_discord)*binom.sf(lo-1,d,prob_b))
    power=math.fsum(terms)
    assert abs(power-summary['exact_iid_plugin_power'])<1e-13
    return dict(probability_distributions=distributions,grid_rows=checked_grid,infeasible_rows=unavailable,
                pilot_cells=len(table),strict_decisions=checked_decisions,exact_iid_power_independent=power,max_errors=errors)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=verify(args.package)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
