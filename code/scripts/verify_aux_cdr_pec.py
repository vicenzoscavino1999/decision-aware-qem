"""Recheck saved auxiliary results from integer shot sums and independent math.

This verifies the finite-shot calculation and saved Gaussian model. Use the
experiment runners to regenerate physical probabilities and CDR training shots.
"""
from __future__ import annotations

import argparse
import json
from fractions import Fraction
from pathlib import Path
import sys
CODE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(CODE / 'src'), str(CODE)]

import numpy as np
from scipy.integrate import quad
from scipy.special import ndtr


def verify(results_dir: Path) -> dict:
    proof = results_dir / "proof_of_mechanism"
    result = json.loads((proof / "result.json").read_text(encoding="utf-8"))
    analytics = json.loads((proof / "instance_analytics.json").read_text(encoding="utf-8"))
    observations = json.loads((proof / "observations.json").read_text(encoding="utf-8"))
    observations_by_key = {(r['instance_id'], r['budget'], r['replicate'], r['method']): r for r in observations}
    if len(observations_by_key) != len(observations):
        raise AssertionError("duplicate observations")
    compared = 0
    max_mse_error = 0.
    max_quad_error = 0.
    min_ordering_margin = float('inf')
    coexistence = {}
    quadrature_count = 0
    max_moment_error = 0.
    max_covariance_error = 0.
    for item in analytics:
        x = item['x_star']
        ideal = np.asarray(item['ideal_values'])
        competitors = [j for j in range(len(ideal)) if j != x]
        slope, intercept = item['cdr_fit']['a'], item['cdr_fit']['b']
        assert slope > 0
        with np.load(proof / 'probabilities' / f"{item['instance_id']}_probabilities.npz") as data:
            values=data['values_by_state'];probabilities=data['noisy_probs'];ideal_probs=data['ideal_probs']
            for probs in (probabilities,ideal_probs):
                assert np.isfinite(probs).all() and np.all(probs>=0)
                np.testing.assert_allclose(probs.sum(axis=-1),1.,atol=2e-15,rtol=0)
            means=probabilities @ values
            variances=np.sum(probabilities*(values-means[...,None])**2,axis=-1)
            ideal_means=ideal_probs @ values
            ideal_variances=np.sum(ideal_probs*(values-ideal_means[...,None])**2,axis=-1)
            max_moment_error=max(max_moment_error,float(np.max(abs(variances-np.asarray(item['noisy_vars'])))),float(np.max(abs(ideal_means-ideal))))
            centered=means[0]-means[0].mean()
            independent_slope=float(np.dot(centered,ideal-ideal.mean())/np.dot(centered,centered))
            assert abs(independent_slope-slope)<1e-12
        # Independent gate-count formula (10 initial H, 20 RX, 30 RZZ).
        gamma1=(2+.01)/(2*(1-.01))
        gamma2=(1+7*.03/8)/(1-.03)
        assert abs(item['gamma_squared']-(gamma1**30*gamma2**30)**2)<1e-10
        with np.load(proof / 'samples' / f"{item['instance_id']}_samples.npz") as samples:
            for index, budget in enumerate(samples['budget']):
                rep = int(samples['replicate'][index]); budget = int(budget)
                raw = samples['raw_sums'][index]; zne = samples['zne_sums'][index]; pec = samples['pec_sums'][index]
                for sums in (raw, zne, pec):
                    assert np.issubdtype(sums.dtype, np.integer)
                t = Fraction.from_float(item['coefficients']['Decision-ZNE'][2])
                exact_weights = [2+t, -1-2*t, t]
                keys = {
                    'Raw': list(map(int, raw)), 'CDR': list(map(int, raw)), 'PEC': list(map(int, pec)),
                    'Accuracy-ZNE': [sum(w*int(zne[s,j]) for s,w in enumerate([4,1,-2])) for j in range(len(ideal))],
                    'Decision-ZNE': [sum(w*int(zne[s,j]) for s,w in enumerate(exact_weights)) for j in range(len(ideal))],
                }
                estimates = {'Raw': raw/budget, 'CDR': slope*raw/budget+intercept,
                    'PEC': pec/int(samples['pec_effective_shots'][index])}
                for method in ('Accuracy-ZNE','Decision-ZNE'):
                    estimates[method]=np.asarray(item['coefficients'][method]) @ (zne/(budget//3))
                for method, method_keys in keys.items():
                    failure = int(any(method_keys[j] <= method_keys[x] for j in competitors))
                    row = observations_by_key[(item['instance_id'],budget,rep,method)]
                    assert row['decision_failure'] == failure
                    mse=float(np.mean((estimates[method]-ideal)**2))
                    max_mse_error=max(max_mse_error,abs(mse-row['mse']))
                    compared+=1
        for budget, methods in item['analytic_by_budget'].items():
            quad_scores = {}
            for name, data in methods.items():
                # The common incumbent induces this rank-one off-diagonal term.
                covariance = np.asarray(data['covariance'])
                if name in ('Raw','Accuracy-ZNE','Decision-ZNE'):
                    weights=np.asarray(item['coefficients'][name])
                    shot_counts=np.array([float(budget),1.,1.]) if name=='Raw' else np.full(3,int(budget)/3)
                    expected_means=weights @ means
                    candidate_variances=(weights**2/shot_counts) @ variances
                elif name=='CDR':
                    expected_means=slope*means[0]+intercept
                    candidate_variances=slope*slope*variances[0]/int(budget)
                else:
                    expected_means=ideal
                    effective=int(int(budget)//item['gamma_squared'])
                    assert data['effective_shots']==effective
                    candidate_variances=ideal_variances/effective
                expected_covariance=np.diag(candidate_variances[competitors])+candidate_variances[x]
                max_covariance_error=max(max_covariance_error,float(np.max(abs(covariance-expected_covariance))))
                expected_mse=float(np.mean((expected_means-ideal)**2+candidate_variances))
                assert abs(expected_mse-data['MSE_expected'])<1e-12
                vx = float(covariance[0,1]); vj = np.diag(covariance)-vx
                assert vx > 0 and np.all(vj > 0)
                np.testing.assert_allclose(covariance,np.diag(vj)+vx,atol=1e-12,rtol=0)
                values=np.asarray(data['mean_values']); mu=values[competitors]-values[x]
                integrand=lambda z: np.exp(-z*z/2)/np.sqrt(2*np.pi)*np.prod(ndtr((mu-np.sqrt(vx)*z)/np.sqrt(vj)))
                success,error=quad(integrand,-12,12,epsabs=2e-11,epsrel=2e-11,limit=250)
                risk=1-success
                assert error<1e-9
                max_quad_error=max(max_quad_error,abs(risk-data['GRI']))
                quadrature_count+=1
                quad_scores[name]=risk
            gap=quad_scores['PEC']-quad_scores['Raw']
            min_ordering_margin=min(min_ordering_margin,abs(gap))
            assert (gap>0)==(methods['PEC']['GRI']>methods['Raw']['GRI'])
            coexistence.setdefault(budget,0)
            coexistence[budget]+=int(gap>0 and methods['PEC']['MSE_expected']<methods['Raw']['MSE_expected'])
    assert compared==len(observations)
    assert max_mse_error<1e-12 and max_quad_error<1e-6
    assert max_moment_error<1e-11 and max_covariance_error<3e-12, (max_moment_error,max_covariance_error)
    # Independent aggregate and conditional paired bootstrap (no production imports).
    config=json.loads((proof/'config_used.json').read_text(encoding='utf-8'))
    from daqem.rng import make_rng
    rng=make_rng(instance_id='proof_of_mechanism',method='bootstrap',budget=0,replicate_id=0,stream='ci')
    summary_by_key={(r['budget'],r['method']):r for r in result['aggregate']['table']}
    for budget in config['budget_grid']:
        draws=rng.integers(0,config['replicates'],size=(config['bootstrap_repetitions'],len(analytics),config['replicates']))
        for method in ('Raw','Accuracy-ZNE','Decision-ZNE','CDR','PEC'):
            expected=summary_by_key[(budget,method)]
            for field,summary_field,ci_field in [('decision_failure','R_empirical','R_ci'),('mse','MSE_mean','MSE_ci')]:
                values=np.array([[observations_by_key[(i['instance_id'],budget,r,method)][field]
                    for r in range(config['replicates'])] for i in analytics])
                assert abs(values.mean()-expected[summary_field])<1e-14
                statistics=[]
                for indices in draws:
                    statistics.append(np.mean([np.mean(values[j,indices[j]]) for j in range(len(analytics))]))
                ci=np.quantile(statistics,[config['ci_alpha']/2,1-config['ci_alpha']/2])
                np.testing.assert_allclose(ci,expected[ci_field],atol=1e-13,rtol=0)
    p0=json.loads((results_dir/'cdr_p0/p0_validity_evidence.json').read_text(encoding='utf-8'))
    max_fit_error=0.
    for row in p0['instances']:
        x=np.array(row['training_noisy']);y=np.array(row['training_exact'])
        a=float(np.dot(x-x.mean(),y-y.mean())/np.dot(x-x.mean(),x-x.mean()))
        b=float(y.mean()-a*x.mean())
        max_fit_error=max(max_fit_error,abs(a-row['fit_a']),abs(b-row['fit_b']))
        assert row['C_train']==len(x)*1024
    assert max_fit_error<1e-12
    return dict(decisions_verified=compared,gaussian_integrals=quadrature_count,
        max_mse_error=max_mse_error,max_gaussian_error=max_quad_error,
        max_probability_moment_error=max_moment_error,max_gap_covariance_error=max_covariance_error,
        min_PEC_Raw_gaussian_order_margin=min_ordering_margin,
        coexistence_counts=coexistence,conditional_bootstrap_intervals_verified=40,
        cdr_p0_training_fits_verified=len(p0['instances']),max_cdr_fit_error=max_fit_error)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--results',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    report=verify(args.results)
    text=json.dumps(report,indent=2,sort_keys=True)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text,encoding='utf-8')
    print(text)
