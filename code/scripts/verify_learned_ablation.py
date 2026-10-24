"""Reconstruct channel fits, propagation and covariance ablations from evidence.

No imports of production estimators, gradients or optimizers are used.
"""
import argparse,json,math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.integrate import quad
from scipy.special import log_ndtr
from scipy.stats import norm,multivariate_normal


def structured_risk(mu,sigma):
    n=len(mu);s=float(np.median(sigma[~np.eye(n,dtype=bool)]));v=np.diag(sigma)-s
    saddle=mu*np.sqrt(s)/(v+s)
    return quad(lambda z:norm.pdf(z)*(-np.expm1(np.sum(log_ndtr((mu-np.sqrt(s)*z)/np.sqrt(v))))),
        -40,40,points=sorted(set([0.]+[float(t) for t in saddle if -40<t<40])),epsabs=1e-100,epsrel=1e-9,limit=500)[0]


def structured_direction(mu,sigma,error):
    n=len(mu);s=float(np.median(sigma[~np.eye(n,dtype=bool)]));v=np.diag(sigma)-s
    ds=float(np.median(error[~np.eye(n,dtype=bool)]));dv=np.diag(error)-ds
    np.testing.assert_allclose(error,np.diag(dv)+ds,atol=1e-15,rtol=1e-9)
    def f(z):
        a=(mu-np.sqrt(s)*z)/np.sqrt(v)
        da=-ds*z/(2*np.sqrt(s*v))-a*dv/(2*v)
        lp=log_ndtr(a)
        return -norm.pdf(z)*np.sum(np.exp(-a*a/2-np.log(2*np.pi)/2+sum(lp)-lp)*da)
    return quad(f,-14,14,epsabs=1e-13,epsrel=1e-9,limit=300)[0]


def sample_covariance(x,shrink):
    n,p=x.shape;y=x-x.mean(axis=0);emp=y.T@y/n
    if not shrink:return y.T@y/(n-1)
    mu=np.trace(emp)/p
    delta=np.sum((emp-mu*np.eye(p))**2)/p
    beta=(np.sum((y*y).T@(y*y))/n-np.sum(emp*emp))/(p*n)
    alpha=np.clip(beta/delta,0,1) if delta>0 else 0.
    return (1-alpha)*emp+alpha*mu*np.eye(p)


def minimax_check(raw,budget_index,c):
    x=int(raw['x_star']);others=[i for i in range(len(raw['ideal_values'])) if i!=x]
    data=raw['primitive_objective_estimates'][:,:,:,budget_index]
    gaps=data[:,:,others]-data[:,:,[x]]
    margins=np.maximum(raw['ideal_values'][others]-raw['ideal_values'][x],1e-6)
    q=np.array([sample_covariance(gaps[:,:,j],False)/margins[j]**2 for j in range(len(others))])
    a=np.array([2.,-1.,0.]);b=np.array([1.,-2.,1.])
    A=np.einsum('i,kij,j->k',b,q,b);B=2*np.einsum('i,kij,j->k',a,q,b);C=np.einsum('i,kij,j->k',a,q,a)
    candidates=list(-B/(2*A))
    for i in range(len(A)):
        for j in range(i):
            candidates.extend(float(z.real) for z in np.roots([A[i]-A[j],B[i]-B[j],C[i]-C[j]]) if abs(z.imag)<1e-9)
    best=min(float(np.max(A*t*t+B*t+C)) for t in candidates)
    actual=float(np.max(np.einsum('i,kij,j->k',c,q,c)))
    return max(0.,(actual-best)/best)


def verify(root):
    pilot=root/'results/pilot';ev=pilot/'cdev_evidence'
    learning=json.loads((ev/'characterization.json').read_text())
    weights=np.array(json.loads((ev/'weights_before_learning.json').read_text())['weights'])
    diag=json.loads((ev/'diagnostics.json').read_text())
    depths=np.array(learning['depths']);ys=np.zeros((25,len(depths)));counts=np.zeros_like(ys,dtype=int)
    total_shots=0
    for row in learning['count_records']:
        i=row['probe_index'];depth=row['depth'];index=list(depths).index(depth);bits=row['counts'];total=sum(bits.values());total_shots+=total
        assert total==learning['shots_per_circuit']
        if i<10:expectation=sum((1 if int(k,2)==depth%2 else -1)*v for k,v in bits.items())/total
        else:expectation=sum((1 if k.count('1')%2==0 else -1)*v for k,v in bits.items())/total
        ys[i,index]+=expectation;counts[i,index]+=1
    assert np.all(counts==learning['twirls']) and total_shots==learning['characterization_shots']==4096000
    ys/=counts
    rates=1-np.exp(np.sum(depths*np.log(np.clip(ys,1e-6,1)),axis=1)/sum(depths**2))
    np.testing.assert_allclose(rates,learning['learned_rates'],rtol=0,atol=1e-15)
    p1=float(rates[:10].mean());p2=float(rates[10:].mean())
    assert abs(p1-learning['learned_p1'])<1e-15 and abs(p2-learning['learned_p2'])<1e-15
    true=np.r_[np.full(10,.01),np.full(15,.03)];aggregated=np.r_[np.full(10,p1),np.full(15,p2)]
    e=float(np.dot(weights,abs(rates-true))/(np.dot(weights,true)+1e-12))
    ea=float(np.dot(weights,abs(aggregated-true))/(np.dot(weights,true)+1e-12))
    assert abs(e-diag['c1']['e_C'])<1e-14 and abs(ea-diag['c1']['e_C_aggregated'])<1e-14
    max_cov=0.;max_grad=0.;max_gri=0.;moments=0;directions=0
    c2_expected={}
    for cell in ['P001','P002','P003','P004']:
        data=np.load(pilot/f'cdev_primitives/{cell}.npz');f=np.load(pilot/f'a3_frozen_prediction/{cell}.npz');prop=np.load(ev/f'{cell}_propagation.npz')
        probs=data['probabilities'];values=data['values_by_state'];np.testing.assert_allclose(probs.sum(axis=-1),1,atol=2e-15,rtol=0)
        means=np.array([[math.fsum(float(p)*float(y) for p,y in zip(row,values)) for row in scale] for scale in probs])
        var=np.array([[math.fsum(float(p)*float(y)**2 for p,y in zip(row,values)) for row in scale] for scale in probs])-means**2
        np.testing.assert_allclose(means,data['means'],atol=1e-13,rtol=0);np.testing.assert_allclose(var,data['variances'],atol=1e-12,rtol=0);moments+=means.size
        names=list(f['method_names']);derivatives=np.empty(prop['risks'].shape)
        for mi,m in enumerate(names):
            cov=(f['gap_maps'][mi]*var.flatten())@f['gap_maps'][mi].T
            for bi,budget in enumerate(f['budgets']):
                learned=cov/budget;max_cov=max(max_cov,float(np.max(abs(learned-prop['sigma_learned'][mi,bi]))))
                error=learned-f['sigma_pred'][mi,bi]
                derivative=structured_direction(f['mu'],f['sigma_pred'][mi,bi],error)
                contract=float(np.sum(prop['gradients'][mi,bi]*error))
                max_grad=max(max_grad,abs(contract-derivative));directions+=1;derivatives[mi,bi]=derivative
                max_gri=max(max_gri,abs(structured_risk(f['mu'],f['sigma_pred'][mi,bi])-prop['risks'][mi,bi]))
        for pi,pair in enumerate(f['pair_names']):
            left,right=pair.split('_vs_');li=names.index(left);ri=names.index(right)
            for bi,budget in enumerate(f['budgets']):
                c2_expected[(cell,pair,int(budget))]=abs(derivatives[li,bi]-derivatives[ri,bi])
    for row in diag['c2']:
        np.testing.assert_allclose(row['delta_rank_C'],c2_expected[(row['cell'],row['pair_id'],row['budget'])],rtol=1e-6,atol=1e-11)
        assert row['c2_status']==('inactive' if not row['active_pair'] else 'pass' if row['projected_error_over_tolerance']<1 else 'fail')
    assert max_cov<1e-12 and max_grad<1e-10 and max_gri<3e-6
    table=pd.read_csv(pilot/'gate0_full_vs_diagonal.csv');max_gate_cov=0.;max_diag=0.;max_full=0.;max_minimax=0.;rare=[]
    for path in sorted((pilot/'gate0_evidence').glob('*.npz')):
        cell=path.stem.split('_')[0];d=np.load(path);budget=int(d['budget']);raw=np.load(pilot/f'raw/{cell}.npz');bi=list(raw['budgets']).index(budget)
        max_minimax=max(max_minimax,minimax_check(raw,bi,d['coefficients'][2]))
        np.testing.assert_allclose(d['coefficients']@np.array([[1,1],[1,2],[1,3]]),[[1,1],[1,0],[1,0]],atol=1e-8,rtol=0)
        scores={}
        for mi,m in enumerate(d['method_names']):
            sample=d['gap_samples'][mi];mu=sample.mean(axis=0);cov=sample_covariance(sample,bool(d['use_ledoit_wolf']));max_gate_cov=max(max_gate_cov,float(np.max(abs(cov-d['covariances'][mi]))))
            row=table[(table.problem_cell==cell)&(table.method==m)&(table.budget==budget)].iloc[0]
            z=mu/np.sqrt(np.diag(cov));diagonal=float(-np.expm1(sum(log_ndtr(z))))
            max_diag=max(max_diag,abs(diagonal-row.gri_diagonal));scores[str(m)]=(row.gri_full,diagonal)
            marginal=norm.sf(z);upper=float(marginal.sum())
            if upper<1e-7:
                lower=float(marginal.max())
                assert lower*(1-1e-10)<=row.gri_full<=upper*(1+1e-10)
                rare.append(dict(cell=cell,method=str(m),budget=budget,value=row.gri_full,lower=lower,upper=upper))
            else:
                full=1-float(multivariate_normal.cdf(mu,mean=np.zeros(len(mu)),cov=cov,rng=np.random.default_rng(8716),maxpts=2000000,abseps=1e-8,releps=1e-8))
                max_full=max(max_full,abs(full-row.gri_full))
            assert row.mechanism_relevant==(abs(row.delta_gri_full_minus_diagonal)>.005 or row.selector_changed)
        first=table[(table.problem_cell==cell)&(table.budget==budget)].iloc[0]
        assert first.selector_full==min(scores,key=lambda m:(scores[m][0],m))
        assert first.selector_diagonal==min(scores,key=lambda m:(scores[m][1],m))
    assert len(table)==72 and len(list((pilot/'gate0_evidence').glob('*.npz')))==24
    assert max_gate_cov<1e-12 and max_diag<1e-7 and max_full<3e-6 and max_minimax<1e-7,(max_gate_cov,max_diag,max_full,max_minimax)
    return dict(characterization_records=len(learning['count_records']),shots_verified=total_shots,primitive_moments=moments,
        directional_derivatives=directions,channel_covariance_max_error=max_cov,gradient_contraction_max_error=max_grad,
        channel_gaussian_max_error=max_gri,gate0_method_rows=72,gate0_selectors=24,gate0_covariance_max_error=max_gate_cov,
        diagonal_max_error=max_diag,full_cdf_crosscheck_max_error=max_full,minimax_relative_excess=max_minimax,rare_tail_bounds=rare,
        e_C_replicates=e,e_C_aggregated=ea)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    report=verify(args.package);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='rare_tail_bounds'},indent=2),flush=True)
