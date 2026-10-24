import numpy as np

from experiments import a3_gaussianity_sigmahat_audit as f1c


def test_tail_ratios_are_finite_for_standard_normal_grid():
    sample = np.linspace(-3.0, 3.0, 201)
    ratios = f1c.tail_ratios(sample, [2.0, 3.0])
    assert set(ratios) == {2.0, 3.0}
    assert all(np.isfinite(value) for value in ratios.values())
    assert all(value >= 0.0 for value in ratios.values())


def test_henze_zirkler_returns_none_when_dimension_not_supported():
    assert f1c.henze_zirkler_statistic(np.ones((10, 2))) is None
    assert f1c.henze_zirkler_statistic(np.ones((10, 1))) is None


def test_projected_ratio_for_pair_matches_frobenius_inner_product():
    sigma_pred = np.eye(2)
    sigma_left = sigma_pred + np.array([[0.1, 0.0], [0.0, 0.0]])
    sigma_right = sigma_pred
    grad_left = np.array([[2.0, 0.0], [0.0, 0.0]])
    grad_right = np.zeros((2, 2))
    ratio = f1c.projected_ratio_for_pair(
        sigma_left=sigma_left,
        sigma_right=sigma_right,
        sigma_pred_left=sigma_pred,
        sigma_pred_right=sigma_pred,
        grad_left=grad_left,
        grad_right=grad_right,
        tau=0.5,
        epsilon0=1e-12,
    )
    assert np.isclose(ratio, 0.4)


def test_joint_bootstrap_indices_are_shared_and_deterministic():
    left = f1c.joint_bootstrap_indices(
        n=8,
        count=3,
        instance_id="P001",
        budget=256,
    )
    right = f1c.joint_bootstrap_indices(
        n=8,
        count=3,
        instance_id="P001",
        budget=256,
    )
    other_budget = f1c.joint_bootstrap_indices(
        n=8,
        count=3,
        instance_id="P001",
        budget=512,
    )
    np.testing.assert_array_equal(left, right)
    assert not np.array_equal(left, other_budget)


def test_gaussianity_calibration_uses_sample_mean_without_claiming_validity(monkeypatch, tmp_path):
    class FakeFrozen(dict):
        pass

    class FakeRaw(dict):
        pass

    raw = FakeRaw()
    frozen = FakeFrozen()
    frozen["budgets"] = np.array([1])
    frozen["method_names"] = np.array(["Raw"])
    frozen["mu"] = np.array([10.0])
    frozen["active_masks"] = np.array([[[True]]])
    samples = np.array([[-1.0], [-1.0], [1.0], [1.0]])

    monkeypatch.setattr(f1c, "load_raw_frozen", lambda _root, _instance: (raw, frozen))
    monkeypatch.setattr(f1c, "method_samples", lambda _raw, _frozen, _idx: {"Raw": samples})
    monkeypatch.setattr(f1c, "gri_risk", lambda mu, _sigma, B=1.0: 0.5 if float(np.asarray(mu)[0]) == 0.0 else 0.0)
    monkeypatch.setattr(f1c, "method_failures", lambda _raw, _frozen, _idx: {"Raw": np.array([True,True,False,False])})
    config = {
        "instance_ids": ["P001"],
        "tail_thresholds": [2.0, 3.0],
        "hz_max_dim": 8,
        "skew_abs_flag": 99.0,
        "excess_kurtosis_abs_flag": 99.0,
        "tail_ratio_low_flag": -1.0,
        "tail_ratio_high_flag": 99.0,
        "tau_R": 0.01,
    }
    _gaussian, calibration = f1c.gaussianity_rows(tmp_path, config)
    row = calibration[0]
    assert row["gri_at_sample_mean"] == 0.5
    assert row["gri_at_true_mean"] == 0.0
    assert row["abs_diff_gaussianity"] == 0.0
    assert row["abs_diff_true_mean"] == 0.5
    assert row["calibration_within_tolerance"] is True
