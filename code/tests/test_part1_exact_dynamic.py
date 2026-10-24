from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from daqem.decisions import integer_shot_sums, zne_decision_keys
from experiments import e2_dynamic_batch_candidate_optimizer as e2


COEFFS = {
    'Raw': np.array([1., 0., 0.]),
    'Accuracy-ZNE': np.array([1.3333333333333321, .33333333333333276, -.666666666666666]),
    'Decision-ZNE': np.array([1.7, -.4, -.3]),
}
A = np.array([-3138, -3299, -3481])
B = np.array([-3138, -3271, -3467])


@pytest.mark.parametrize('shots', [170, 256, 512, 8192])
@pytest.mark.parametrize('coeff', [None, COEFFS['Decision-ZNE']])
def test_keys_order_matches_fraction_oracle(shots, coeff):
    rng = np.random.default_rng(711)
    sums = rng.integers(-10*shots, -4*shots, size=(40, 3, 5))
    # Include a tie forced by the Richardson constraints, including learned t.
    sums[:, :, 1] = sums[:, :, 0] + np.array([1,2,3])
    keys = zne_decision_keys(sums/shots, shots, coefficients=coeff)
    t = Fraction(-2,3) if coeff is None else Fraction(float(coeff[2]))
    c = [2+t, -1-2*t, t]
    for rep in range(40):
        scores = [sum(c[s]*int(sums[rep,s,k])/shots for s in range(3)) for k in range(5)]
        expected = min(range(5), key=scores.__getitem__)
        assert int(np.argmin(keys[rep])) == expected
        assert keys[rep,0] == keys[rep,1]
    if coeff is not None:
        assert max(abs(x) for x in keys.ravel()) > 2**63


def synthetic_run(monkeypatch, tmp_path, batches, ideal_batches):
    config = e2.load_config('full')
    config.update(trajectories=1, max_rounds=len(batches), candidates_per_round=2,
                  budget_grid=[512], B_max=512, initial_landscape_count=2, epsilon_quantile=.5)
    monkeypatch.setattr(e2, '_static_selector_map', lambda *a:{512:{'MSE':'Accuracy-ZNE','DA':'Accuracy-ZNE','source_budget':'512'}})
    monkeypatch.setattr(e2, '_method_coefficients', lambda *a:COEFFS)
    monkeypatch.setattr(e2, 'landscape_for_instance', lambda *a,**k:SimpleNamespace(angles=np.zeros((2,4)), ideal_values=np.array([-7.,-6.9])))
    ideal_iter=iter(ideal_batches)
    monkeypatch.setattr(e2, '_candidate_ideal_values', lambda *a:np.asarray(next(ideal_iter)))
    data_iter=iter(batches)
    def evaluate(**kwargs):
        means=(np.asarray(next(data_iter))/512)[:,:,None]
        return means,np.zeros_like(means),{'aer_runs':0,'circuits':0,'shots':0}
    monkeypatch.setattr(e2, '_evaluate_candidate_batch', evaluate)
    return e2._run_instance(output_root=tmp_path,instance_id='C001',config=config)


def test_reported_counterexample_selects_first_exact_tie(monkeypatch,tmp_path):
    sums=np.column_stack([A,B])
    floats,_=e2._method_estimates((sums/512)[:,:,None],np.zeros((3,2,1)),COEFFS)
    assert floats['Accuracy-ZNE'][1,0] < floats['Accuracy-ZNE'][0,0]
    results,trace,_=synthetic_run(monkeypatch,tmp_path,[sums],[[-7.,-6.5]])
    assert trace.MSE_candidate.tolist()==[0] and trace.DA_candidate.tolist()==[0]
    assert results.success_decision.tolist()==[True,True]


def test_exact_tie_between_rounds_keeps_earlier_incumbent(monkeypatch,tmp_path):
    batches=[np.column_stack([A,A+16]),np.column_stack([B,B+16])]
    results,_,_=synthetic_run(monkeypatch,tmp_path,batches,[[-7.,-6.],[-6.5,-6.]])
    assert results.final_ideal_value.tolist()==[-7.,-7.]
    assert results.success_decision.tolist()==[True,True]


def test_genuine_improvement_between_rounds_is_not_rounded_to_tie(monkeypatch,tmp_path):
    improved=A.copy();improved[1]-=1
    batches=[np.column_stack([A,A+16]),np.column_stack([improved,improved+16])]
    results,_,_=synthetic_run(monkeypatch,tmp_path,batches,[[-7.,-6.],[-7.5,-6.]])
    assert results.final_ideal_value.tolist()==[-7.5,-7.5]
    assert results.success_decision.tolist()==[True,True]


def test_multiple_budgets_and_raw_ties_preserve_indices():
    means=np.stack([np.column_stack([A,B])/512,np.column_stack([A,A])/1024],axis=-1)
    keys=e2._method_decision_keys(means,[512,1024],COEFFS,[1,2,3])
    assert keys['Raw'].dtype==object
    assert np.argmin(keys['Raw'],axis=0).tolist()==[0,0]
    assert np.argmin(keys['Accuracy-ZNE'],axis=0).tolist()==[0,0]


def test_noninteger_shot_records_and_other_scales_are_rejected():
    with pytest.raises(ValueError,match='integer MaxCut'):
        integer_shot_sums([.1],512)
    with pytest.raises(ValueError,match='scales'):
        e2._method_decision_keys(np.zeros((3,2,1)),[512],COEFFS,[1,2,4])
    with pytest.raises(ValueError,match='constraints'):
        zne_decision_keys(np.zeros((1,3,2)),512,coefficients=[1,1,1])


def test_old_floating_checkpoints_are_not_reused(tmp_path):
    config=e2.load_config('full')
    legacy='sha256:'+hashlib.sha256(json.dumps(config,sort_keys=True,default=str).encode()).hexdigest().upper()
    frame=pd.DataFrame([{'success':True}])
    e2._write_dynamic_instance_outputs(tmp_path,'full','C001',frame,frame,{},
                                      duration_seconds=0.,config_fingerprint=legacy)
    assert e2._completed_dynamic_instance(tmp_path,'full','C001',legacy)
    assert not e2._completed_dynamic_instance(tmp_path,'full','C001',e2._dynamic_config_fingerprint(config))


def test_decision_source_change_invalidates_checkpoint_identity(monkeypatch):
    config=e2.load_config('full');before=e2._dynamic_config_fingerprint(config)
    monkeypatch.setattr(e2,'_sha256_file',lambda p:'sha256:changed')
    assert before != e2._dynamic_config_fingerprint(config)


def test_pilot_epsilon_branch_calls_existing_landscape_helper(monkeypatch):
    monkeypatch.setattr(e2,'landscape_for_instance',lambda *a,**kw:SimpleNamespace(ideal_values=np.array([-7.,-6.])))
    config=e2.load_config('epsilon_sweep')
    values=e2._epsilon_values_by_instance(config)
    for instance in config['instance_ids']:
        for q in config['epsilon_quantile_grid']:
            assert values[instance][q]==pytest.approx(q)
