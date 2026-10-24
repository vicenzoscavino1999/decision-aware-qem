import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from e1_reanalysis import (POLICIES, analyse_instance, block_mean, budget_ledger,
                           split_replicates, summarize)


def test_exact_block_reconstruction_matches_individual_shots():
    rng = np.random.default_rng(10)
    shots = rng.integers(-15, 1, (2, 3, 4, 8192))
    budgets = np.array([256,512,1024,2048,4096,8192])
    prefix = np.stack([shots[..., :b].mean(axis=-1) for b in budgets],axis=-1)
    for t in (512,1024):
        np.testing.assert_allclose(block_mean(prefix,budgets,[(t,4*t)]),shots[...,t:4*t].mean(axis=-1))
        np.testing.assert_allclose(block_mean(prefix,budgets,[(t//2,8*t)]),shots[...,t//2:8*t].mean(axis=-1))
        direct=np.concatenate([shots[...,t//2:t],shots[...,2*t:4*t]],axis=-1).mean(axis=-1)
        np.testing.assert_allclose(block_mean(prefix,budgets,[(t//2,t),(2*t,4*t)]),direct)
    with pytest.raises(ValueError,match="overlap"):
        block_mean(prefix,budgets,[(0,512),(256,1024)])


def test_all_cohort_costs_equal_including_pilots():
    for t in (512,1024):
        costs=[budget_ledger(t,25,p,"end_to_end") for p in POLICIES]
        assert {x["total_shots_20_decisions"] for x in costs} == {150*t*25}
        assert costs[-1]["fit_shots"]+costs[-1]["selection_shots"] == 90*t*25
        eval_costs=[budget_ledger(t,25,p,"evaluation")["evaluation_shots"] for p in POLICIES]
        assert len(set(eval_costs)) == 1


def test_splits_disjoint_complete_reproducible():
    for i in range(1,49):
        a=split_replicates(f"C{i:03d}")
        assert [len(a[k]) for k in ("fit","select","test")] == [10,10,20]
        assert sorted(np.concatenate(list(a.values())).tolist()) == list(range(40))
        b=split_replicates(f"C{i:03d}")
        assert all(np.array_equal(a[k],b[k]) for k in a)


def test_test_data_cannot_change_coefficients_or_selection(tmp_path):
    rng=np.random.default_rng(101)
    budgets=np.array([256,512,1024,2048,4096,8192])
    probs=np.linspace(.8,.2,25)
    cumulative=np.zeros((40,3,25))
    estimates=[]
    previous=0
    for b in budgets:
        cumulative-=rng.binomial(int(b-previous),probs,size=(40,3,25))
        estimates.append(cumulative/b)
        previous=b
    estimates=np.stack(estimates,axis=-1)
    path=tmp_path/"C001.npz"
    def save(x):
        np.savez(path,instance_id=np.array("C001"),budgets=budgets,
                 primitive_objective_estimates=x,ideal_values=-probs,x_star=np.array(0))
    save(estimates)
    records_a,diag_a,_=analyse_instance(path,[512])
    changed=estimates.copy()
    changed[split_replicates("C001")["test"],:,:, :]-=10*np.arange(25)[None,None,:,None]
    save(changed)
    records_b,diag_b,_=analyse_instance(path,[512])
    assert diag_a == diag_b
    assert records_a != records_b


def test_gaussian_pair_minimax_is_not_plugin_pointwise_exponent():
    for B in (4,16,64):
        pointwise=norm.cdf(-np.sqrt(B))
        minimax=norm.cdf(-np.sqrt(B)/2)
        kl_lower=.25*np.exp(-B/2)
        assert kl_lower <= minimax < .5
        assert pointwise < minimax
    # Limit rates are respectively 1/2 and 1/8; the plug-in has 1/2 error at Q.
    B=10000
    assert -norm.logcdf(-np.sqrt(B))/B == pytest.approx(.5,abs=.001)
    assert -norm.logcdf(-np.sqrt(B)/2)/B == pytest.approx(.125,abs=.001)


def test_cluster_bootstrap_preserves_paired_instance_differences():
    records=[]
    for i in range(4):
        for p in POLICIES:
            for r in range(20):
                count=5 if p=="GRI-selector" else 10
                records.append(dict(instance=f"C{i:03d}",base_t=512,comparison="end_to_end",
                                    policy=p,replicate_id=r,failure=int(r<count)))
    s=summarize(pd.DataFrame(records))
    row=s[(s.kind=="paired_difference") & (s.reference=="Raw")].iloc[0]
    assert row.estimate == row.ci_low == row.ci_high == -.25
