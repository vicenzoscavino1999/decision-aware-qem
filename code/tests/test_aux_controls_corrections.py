import itertools
import math
import numpy as np
import pytest
from experiments import pilot_power_report as p
from experiments import phase_diagram_grid as g


def test_exact_test_does_not_reject_two_discordant_pairs():
    assert not p.paired_test_rejects(b=2,c=0,n=2,alpha=.05)
    assert not p.paired_test_rejects(b=4,c=0,n=100,alpha=.05)
    assert p.paired_test_rejects(b=5,c=0,n=100,alpha=.05)
    assert not p.paired_test_rejects(b=0,c=0,n=100,alpha=.05)
    with pytest.raises(ValueError): p.paired_test_rejects(b=3,c=1,n=3,alpha=.05)
    with pytest.raises(ValueError): p.paired_test_rejects(b=1.5,c=0,n=3,alpha=.05)


def test_conditional_null_size_never_exceeds_alpha():
    for d in range(1,51):
        size=sum(math.comb(d,b)*.5**d for b in range(d+1)
                 if p.paired_test_rejects(b=b,c=d-b,n=100,alpha=.05))
        assert size <= .05+1e-14


def test_exact_power_against_enumerating_all_outcomes():
    counts=dict(both_fail=1,both_ok=2,b=6,c=1)
    probabilities=np.array([.1,.2,.6,.1]);n=6
    power=0.
    for outcomes in itertools.product(range(4),repeat=n):
        b,c=outcomes.count(2),outcomes.count(3)
        # Independent rational tail under the null, no production test call.
        tail=sum(math.comb(b+c,k) for k in range(b,b+c+1))/2**(b+c)
        if tail <= .05:
            power+=np.prod(probabilities[list(outcomes)])
    assert p.exact_iid_power(pooled_counts=counts,paired_decisions=n,alpha=.05)==pytest.approx(power,abs=1e-14)
    assert p.exact_iid_power(pooled_counts=dict(both_fail=0,both_ok=5,b=0,c=0),paired_decisions=n,alpha=.05)==0


def test_ties_and_undefined_reduction():
    # At all three scales the competitor gap equals +1: extrapolation preserves it.
    primitive=np.array([[[0,0],[0,0],[0,0]],[[0,1],[0,1],[0,1]]],dtype=float)/8
    coeffs={'Decision-ZNE':np.array([4/3,1/3,-2/3])}
    failure=p.exact_method_failures(primitive,0,8,coeffs)
    for value in failure.values(): assert list(value)==[True,False]
    assert p.paired_failure_counts(np.zeros(3,dtype=bool),np.zeros(3,dtype=bool))['observed_rel_reduction'] is None
    with pytest.raises(ValueError): p.paired_outcome_counts([[np.nan]],[[1.]])
    with pytest.raises(ValueError): p.exact_method_failures(primitive+.001,0,8,coeffs)


def test_affine_risk_tie_is_not_separation():
    rows=[dict(budget=768,p1=.01,method='Raw',mse=2.,gri=.2),
          dict(budget=768,p1=.01,method='CDR',mse=1.,gri=.2+1e-7),
          dict(budget=768,p1=.01,method='PEC',mse=None,gri=None,feasible=False)]
    assert g.minimizer_sets(rows)==({'CDR'},{'Raw','CDR'})
    assert g.separation_by_budget(rows)=={768:[]}
    rows[2].update(mse=.1,gri=.9,feasible=True)
    assert g.cell_separations(rows)[0]['forced_separation']


def test_generation_does_not_touch_reference(tmp_path,monkeypatch):
    reference=tmp_path/'reproducibility/reference_extension/phase_diagram/grid.csv'
    reference.parent.mkdir(parents=True);reference.write_text('original')
    monkeypatch.setattr(g,'REPO_ROOT',tmp_path)
    rows=[dict(instance_id='x',p1=.01,p2=.03,budget=768,method='Raw',mse=1.,gri=.2,feasible=True,reason='',gamma_squared=1.,effective_shots=768)]
    g.save_results(rows,tmp_path/'results/phase_diagram')
    assert reference.read_text()=='original'
