"""Independent moment, covariance, minimax and Gaussian checks of saved controls."""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from scipy.integrate import quad
from scipy.special import log_ndtr


def minimax_excess(coefficients, variances, ideal, optimum):
    competitors=[j for j in range(len(ideal)) if j!=optimum]
    gaps=np.maximum(ideal[competitors]-ideal[optimum],1e-6)
    w=(variances[:,competitors].T+variances[:,optimum])/gaps[:,None]**2
    a=np.array([2.,-1.,0.]);b=np.array([1.,-2.,1.])
    A=w@(b*b);B=w@(2*a*b);C=w@(a*a)
    candidates=list(-B/(2*A))
    for j in range(len(A)):
        for k in range(j):
            roots=np.roots([A[j]-A[k],B[j]-B[k],C[j]-C[k]])
            candidates.extend(float(z.real) for z in roots if abs(z.imag)<1e-9)
    optimum_value=min(float(np.max(A*t*t+B*t+C)) for t in candidates)
    c=np.asarray(coefficients)
    np.testing.assert_allclose(np.array([[1.,1.,1.],[1.,2.,3.]])@c,[1.,0.],atol=1e-8,rtol=0)
    value=float(np.max(w@(c*c)))
    return max(0.,(value-optimum_value)/optimum_value)


def gaussian_risk(mu, candidate_variances, optimum):
    competitors=[i for i in range(len(candidate_variances)) if i!=optimum]
    vx=candidate_variances[optimum];vj=candidate_variances[competitors]
    assert vx>0 and np.all(vj>0)
    def integrand(z):
        log_success=np.sum(log_ndtr((mu-np.sqrt(vx)*z)/np.sqrt(vj)))
        return np.exp(-z*z/2)/np.sqrt(2*np.pi)*(-np.expm1(log_success))
    saddle=mu*np.sqrt(vx)/(vj+vx)
    points=sorted(set([0.]+[float(z) for z in saddle if -40<z<40]))
    return quad(integrand,-40.,40.,points=points,epsabs=1e-100,epsrel=1e-9,limit=600)


def verify(results: Path):
    het=json.loads((results/'het_pec_derisk/derisk_result.json').read_text())
    derisk=json.loads((results/'r1_derisk/derisk_result.json').read_text())
    full=json.loads((results/'r1_full/r1_full_result.json').read_text())
    max_mean=0.;max_var=0.;max_cov=0.;max_minimax=0.;max_gri=0.;max_small_relative=0.
    score_rows=[];variance_rows=0;orders=0
    def moments(path):
        nonlocal max_mean,max_var,variance_rows
        with np.load(path) as f:data={k:f[k] for k in f.files}
        probs=data['probabilities'];values=data['values_by_state']
        assert probs.shape[0]==3 and np.isfinite(probs).all() and np.all(probs>=0)
        np.testing.assert_allclose(probs.sum(axis=-1),1.,atol=2e-15,rtol=0)
        means=np.empty(probs.shape[:2]);variances=np.empty_like(means)
        for s in range(probs.shape[0]):
            for j in range(probs.shape[1]):
                mean=math.fsum(float(p)*float(v) for p,v in zip(probs[s,j],values))
                second=math.fsum(float(p)*float(v)*float(v) for p,v in zip(probs[s,j],values))
                means[s,j]=mean;variances[s,j]=second-mean*mean
        max_mean=max(max_mean,float(np.max(abs(means-data['means']))))
        max_var=max(max_var,float(np.max(abs(variances-data['variances']))))
        variance_rows+=means.size
        return data,means,variances
    def compare_score(cell,budget,method,mu,variances,x,stored):
        nonlocal max_gri,max_small_relative
        value,error=gaussian_risk(mu,variances,x)
        diff=abs(value-stored);max_gri=max(max_gri,diff)
        relative=None if value==0 else diff/value
        if 0<value<1e-7:max_small_relative=max(max_small_relative,relative)
        score_rows.append(dict(cell=cell,budget=budget,method=method,stored=stored,independent=value,
            abs_difference=diff,relative_difference=relative,quadrature_error=error))
        return value
    data,means,variances=moments(results/'het_pec_derisk/primitives/HET_PEC_DERISK_P0.npz')
    x=int(data['x_star']);indices=[i for i in range(len(data['ideal_values'])) if i!=x]
    expected_cov=np.diag(variances[0,indices])+variances[0,x]
    max_cov=max(max_cov,float(np.max(abs(expected_cov-np.asarray(het['sigma_unit_raw'])))))
    raw_mu=means[0,indices]-means[0,x];ideal_mu=data['ideal_values'][indices]-data['ideal_values'][x]
    rates=het['rates'];p1=list(rates['p1_by_qubit'].values());p2=list(rates['p2_by_edge'].values())
    gamma=np.prod([((2+p)/(2*(1-p)))**3 for p in p1])*np.prod([((1+7*p/8)/(1-p))**2 for p in p2])
    assert abs(gamma*gamma-het['gamma_squared_het'])<1e-10
    for row in het['budgets']:
        b=row['budget']
        raw=compare_score('HET',b,'Raw',raw_mu,variances[0]/b,x,row['GRI_raw'])
        pec=compare_score('HET',b,'PEC_proxy',ideal_mu,variances[0]*gamma*gamma/b,x,row['GRI_pec'])
        assert (pec<raw)==row['PEC_wins'];orders+=1
    cases=[('R1_DERISK',derisk,results/'r1_derisk/primitives/R1_STRUCTURED_DERISK_P0.npz')]
    cases.extend((item['instance_id'],item,results/f"r1_full/primitives/{item['instance_id']}.npz") for item in full['phase_a_instances'])
    for name,item,path in cases:
        data,means,variances=moments(path)
        ideal=data['ideal_values'];x=int(data['x_star']);indices=[j for j in range(len(ideal)) if j!=x]
        methods=item['method_data']
        max_minimax=max(max_minimax,minimax_excess(methods['Decision-ZNE']['coefficients'],variances,ideal,x))
        for method,values in methods.items():
            c=np.asarray(values['coefficients']);mean=c@means;v=c*c@variances
            expected_cov=np.diag(v[indices])+v[x]
            max_cov=max(max_cov,float(np.max(abs(expected_cov-np.asarray(values['sigma_unit'])))))
            np.testing.assert_allclose(mean,values['values'],atol=1e-12,rtol=0)
        for row in item['budgets']:
            scores={}
            for method,values in methods.items():
                c=np.asarray(values['coefficients']);mean=c@means;v=c*c@variances
                mu=mean[indices]-mean[x]
                mse=float(np.mean((mean-ideal)**2+v/row['budget']))
                assert abs(mse-row['MSE'][method])<1e-12
                scores[method]=compare_score(name,row['budget'],method,mu,v/row['budget'],x,row['GRI'][method])
            choice=min(scores,key=lambda m:(scores[m],m))
            assert choice==row['DA_selected_method']
            assert (scores[choice]<scores['Raw'])==row['DA_beats_Raw'];orders+=1
            count=len(ideal);b=row['budget']
            assert row['evaluation_shots']['all_candidates']=={'Raw':count*b,'Accuracy-ZNE':3*count*b,'Decision-ZNE':3*count*b}
    for budget,summary in full['phase_a_summary'].items():
        count=sum(next(row for row in item['budgets'] if row['budget']==int(budget))['DA_beats_Raw'] for item in full['phase_a_instances'])
        assert summary['DA_beats_Raw_count']==count and summary['majority']==(count>len(full['phase_a_instances'])/2)
    generalizes=any(row['majority'] for row in full['phase_a_summary'].values())
    assert (full['phase_b_status']=='completed')==generalizes
    assert max_mean<1e-11 and max_var<1e-11 and max_cov<1e-10
    assert max_minimax<1e-7 and max_gri<2e-6 and max_small_relative<1e-4, (
        max_minimax,max_gri,max_small_relative,
        max(score_rows,key=lambda row:row['abs_difference']),
        max((row for row in score_rows if 0<row['independent']<1e-7),key=lambda row:row['relative_difference'],default=None))
    return dict(primitive_moments_verified=variance_rows,gaussian_scores_verified=len(score_rows),method_orders_verified=orders,
        max_mean_difference=max_mean,max_variance_difference=max_var,max_covariance_difference=max_cov,
        max_minimax_relative_excess=max_minimax,max_gaussian_absolute_difference=max_gri,
        max_small_risk_relative_difference=max_small_relative,gamma_squared_independent=float(gamma*gamma),
        phase_b_status=full['phase_b_status'],gaussian_details=score_rows)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--results',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=verify(args.results)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='gaussian_details'},indent=2),flush=True)
