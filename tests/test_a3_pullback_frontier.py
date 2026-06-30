from pathlib import Path

import numpy as np

from experiments import a3_pullback_frontier as a3


def test_gap_map_applies_method_coefficients_as_LM():
    coeffs = np.array([1.0, -0.5])
    gap_map = a3._gap_map(coeffs, candidate_count=3, x_star=0)
    primitive = np.array([10.0, 12.0, 15.0, 20.0, 25.0, 29.0])
    gaps = gap_map @ primitive
    expected = np.array(
        [
            (12.0 - 10.0) - 0.5 * (25.0 - 20.0),
            (15.0 - 10.0) - 0.5 * (29.0 - 20.0),
        ]
    )
    np.testing.assert_allclose(gaps, expected)


def test_risk_gradient_central_is_symmetric_and_active_only():
    mu = np.array([0.4, 0.5, 2.0])
    sigma = np.array(
        [
            [0.08, 0.01, 0.0],
            [0.01, 0.09, 0.0],
            [0.0, 0.0, 0.2],
        ]
    )
    active = np.array([True, True, False])
    grad, unstable, step = a3.risk_gradient_central(
        mu,
        sigma,
        active,
        perturbation_relative=1e-4,
        perturbation_floor=1e-8,
        stability_relative=10.0,
        stability_absolute=1e-6,
    )
    assert step > 0.0
    assert unstable is False
    np.testing.assert_allclose(grad, grad.T)
    assert np.allclose(grad[2, :], 0.0)
    assert np.allclose(grad[:, 2], 0.0)


def test_frozen_npz_is_written_before_analysis_loads_raw(tmp_path, monkeypatch):
    config = {
        "profile": "smoke",
        "instance_ids": ["P001"],
        "gate0_profile": "full",
        "gate0_config": {"placeholder": True},
    }

    def fake_build(*, instance_id, output_root, config):
        path = output_root / a3.FROZEN_REL_DIR / f"{instance_id}.npz"
        a3._write_deterministic_npz(path, value=np.array([1.0]))
        return path

    observed = {}

    def fake_analyze(*, instance_id, frozen_path, frozen_hash, output_root, config):
        observed["frozen_exists_before_raw_stage"] = frozen_path.exists()
        observed["hash"] = frozen_hash
        frame = a3.pd.DataFrame(
            [
                {
                    "problem_cell": instance_id,
                    "pair_id": "Raw_vs_Accuracy-ZNE",
                    "budget": 256,
                    "active_pair": True,
                    "delta_rank_projected": 0.0,
                    "tau_flip_projected": 1.0,
                    "projected_error_over_tolerance": 0.0,
                    "frobenius_error_over_tolerance": 0.0,
                    "predicted_order": "Raw<Accuracy-ZNE",
                    "empirical_order": "Raw<Accuracy-ZNE",
                    "ordering_match": True,
                    "a3_status": "pass",
                    "pass_label": "directionally_sensitive_pass",
                    "_frozen_hash": frozen_hash,
                }
            ]
        )
        frame.attrs["mean_crosscheck"] = {
            "problem_cell": instance_id,
            "B_max": 256,
            "replicates": 2,
            "max_abs_empirical_minus_analytic": 0.0,
            "max_abs_diff_scale_index": 0,
            "max_abs_diff_candidate_index": 0,
            "max_z_score": 0.0,
            "max_z_scale_index": 0,
            "max_z_candidate_index": 0,
            "means_ok": True,
        }
        return frame

    monkeypatch.setattr(a3, "load_config", lambda profile: config)
    monkeypatch.setattr(a3, "build_frozen_prediction_for_cell", fake_build)
    monkeypatch.setattr(a3, "analyze_cell_from_frozen_prediction", fake_analyze)
    df = a3.run(tmp_path, profile="smoke")
    assert observed["frozen_exists_before_raw_stage"] is True
    assert observed["hash"].startswith("sha256:")
    assert (tmp_path / a3.CSV_REL).exists()
    assert "_frozen_hash" not in df.columns


def test_status_and_label_distinguishes_projected_and_frobenius_pass():
    assert a3._status_and_label(
        ambiguous=True,
        projected_ratio=0.1,
        frob_ratio=0.1,
        ordering_match=True,
    ) == ("ambiguous", "ambiguous")
    assert a3._status_and_label(
        ambiguous=False,
        projected_ratio=0.5,
        frob_ratio=0.5,
        ordering_match=True,
    ) == ("pass", "frobenius_proxy_only")
    assert a3._status_and_label(
        ambiguous=False,
        projected_ratio=0.5,
        frob_ratio=2.0,
        ordering_match=True,
    ) == ("pass", "directionally_sensitive_pass")
    assert a3._status_and_label(
        ambiguous=False,
        projected_ratio=1.5,
        frob_ratio=0.5,
        ordering_match=True,
    ) == ("fail", "fail")
