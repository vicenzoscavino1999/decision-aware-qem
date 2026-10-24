import json

import numpy as np
import pandas as pd
import pytest

from experiments import a3_pullback_frontier as a3
from plot_corrected_e3 import comparison_series, main


LEFT = "Raw<Accuracy-ZNE"
RIGHT = "Accuracy-ZNE<Raw"


@pytest.fixture
def tables():
    comparisons = pd.DataFrame({
        "instance": ["C001", "C002", "C003", "C004"],
        "budget": [256] * 4,
        "pair": ["Raw_vs_Accuracy-ZNE"] * 4,
        "old_covariance_order": [LEFT, LEFT, "tie", LEFT],
        "old_all40_failure_order": [LEFT, RIGHT, "tie", "tie"],
        "method_mean_train_order": [LEFT, RIGHT, "tie", LEFT],
        "test_failure_order": [LEFT, LEFT, "tie", "tie"],
    })
    frontier = pd.DataFrame({
        "problem_cell": comparisons.instance,
        "budget": comparisons.budget,
        "pair_id": comparisons.pair,
        "active_pair": True,
        "predicted_order": comparisons.old_covariance_order,
        "empirical_order": [LEFT, RIGHT, "tie", LEFT],
    })
    return comparisons, frontier


def test_reversals_and_ties_change_real_numerators(tables):
    series = comparison_series(*tables)
    row = series.iloc[0]
    assert row.active_pairs == 4
    assert row.covariance_matches == 2
    assert row.historical_failure_matches == row.method_mean_matches == 1
    assert row.covariance_fraction == .5
    assert row.historical_failure_fraction == row.method_mean_fraction == .25


def test_pair_keys_align_shuffled_inputs_and_string_false_is_excluded(tables):
    comparisons, frontier = tables
    extra = frontier.iloc[[0]].copy()
    extra["problem_cell"] = "C999"
    extra["active_pair"] = "False"
    frontier["active_pair"] = "True"
    frontier = pd.concat([frontier, extra], ignore_index=True).iloc[::-1]
    result = comparison_series(comparisons.iloc[::-1], frontier)
    assert result.iloc[0].covariance_fraction == .5
    assert result.iloc[0].active_pairs == 4


@pytest.mark.parametrize("case", ["duplicate_comparison", "duplicate_frontier", "missing_frontier",
                                 "extra_active", "invalid_order", "mixed_predictions", "invalid_active",
                                 "missing_column", "missing_key", "zero_budget", "fractional_budget"])
def test_malformed_or_mixed_inputs_are_rejected(tables, case):
    comparisons, frontier = tables
    if case == "duplicate_comparison":
        comparisons = pd.concat([comparisons, comparisons.iloc[[0]]])
    elif case == "duplicate_frontier":
        frontier = pd.concat([frontier, frontier.iloc[[0]]])
    elif case == "missing_frontier":
        frontier = frontier.iloc[:-1]
    elif case == "extra_active":
        extra = frontier.iloc[[0]].copy()
        extra["problem_cell"] = "C999"
        frontier = pd.concat([frontier, extra])
    elif case == "invalid_order":
        comparisons.loc[0, "test_failure_order"] = "MSE<DA"
    elif case == "mixed_predictions":
        frontier.loc[0, "predicted_order"] = RIGHT
    elif case == "invalid_active":
        frontier["active_pair"] = "maybe"
    elif case == "missing_column":
        comparisons = comparisons.drop(columns="pair")
    elif case == "missing_key":
        comparisons.loc[0, "instance"] = None
    elif case == "zero_budget":
        comparisons.loc[0, "budget"] = 0
    elif case == "fractional_budget":
        comparisons["budget"] = 256.5
    with pytest.raises(ValueError):
        comparison_series(comparisons, frontier)


def test_cli_rejects_mismatched_files_before_creating_output(tables, tmp_path):
    comparisons, frontier = tables
    comparison_path = tmp_path / "comparison.csv"
    frontier_path = tmp_path / "frontier.csv"
    figure_path = tmp_path / "new-output" / "figure.png"
    comparisons.to_csv(comparison_path, index=False)
    frontier.iloc[:-1].to_csv(frontier_path, index=False)
    with pytest.raises(ValueError, match="same active keys"):
        main(["--input", str(comparison_path), "--frontier", str(frontier_path), "--output", str(figure_path)])
    assert not figure_path.parent.exists()


@pytest.mark.parametrize("risk", [0., .25, 1.])
def test_native_exact_risk_tie_is_not_strict_order(risk):
    assert a3._order_label("Raw", risk, "Accuracy-ZNE", risk) == "tie"


def test_native_resolves_small_real_differences_without_tolerance():
    risk = .25
    greater = np.nextafter(risk, np.inf)
    assert a3._order_label("Raw", risk, "Accuracy-ZNE", greater) == LEFT
    assert a3._order_label("Raw", greater, "Accuracy-ZNE", risk) == RIGHT


@pytest.mark.parametrize("risk", [np.nan, np.inf, -np.inf, -.01, 1.01])
def test_native_rejects_invalid_risk(risk):
    with pytest.raises(ValueError):
        a3._order_label("Raw", risk, "Accuracy-ZNE", .5)


@pytest.mark.parametrize("prediction_tied", [False, True])
def test_native_analysis_does_not_report_tied_scores_as_strict_match(tmp_path, monkeypatch, prediction_tied):
    raw_path = tmp_path / "confirmatory/raw/C001.npz"
    raw_path.parent.mkdir(parents=True)
    np.savez(raw_path,
             metadata_json=json.dumps({"instance_id": "C001", "candidate_count": 3,
                                       "profile": "test", "budget_grid": [256]}),
             budgets=np.array([256]), ideal_values=np.array([0., .4, .6]), x_star=0,
             zne_lambdas=np.array([1.,2.,3.]),
             primitive_objective_estimates=np.repeat(np.round(256*np.array([
                 [[[0.], [.3], [.5]]], [[[.1], [.5], [.8]]],
                 [[[0.], [.5], [.9]]], [[[.1], [.4], [.7]]]]))/256,3,axis=1))
    frozen_path = tmp_path / "frozen.npz"
    np.savez(frozen_path,
             metadata_json=json.dumps(dict(instance_id='C001',gate0_profile='test',rho_flip=.5,mde_absolute=0.)),
             ideal_values=np.array([0.,.4,.6]),x_star=0,
             budgets=np.array([256]), method_names=np.array(["Raw", "Accuracy-ZNE"]),
             method_coefficients=np.array([[1.,0.,0.], [1.,0.,0.]]), pair_names=np.array(["Raw_vs_Accuracy-ZNE"]),
             mu=np.array([.4, .6]), sigma_pred=np.tile(np.eye(2), (2, 1, 1, 1)),
             gradients=np.zeros((2, 1, 2, 2)), risks_pred=np.array([[.2], [.2 if prediction_tied else .3]]),
             delta_pred=np.array([[0. if prediction_tied else -.1]]), tau_flip_projected=np.array([[1.]]),
             # Deliberately retain a historical strict label even when risks tie.
             predicted_order=np.array([[LEFT]]),
             gradient_unstable=np.zeros((2, 1), dtype=bool))
    monkeypatch.setattr(a3, "mean_crosscheck_from_frozen_raw", lambda **kwargs: {})
    # Exact equality of covariance scores is the scientific edge case being tested.
    monkeypatch.setattr(a3, "gri_risk", lambda *args, **kwargs: .25)
    config = {"output_namespace": "confirmatory", "gate0_profile":"test", "rho_flip":.5, "gate0_config": {
        "profile": "test", "candidate_count": 3, "budget_grid": [256],
        "zne_lambdas":[1.,2.,3.],
        "use_ledoit_wolf": False, "bstar_gain_threshold": 1.},
        "method_pairs": [["Raw", "Accuracy-ZNE"]], "epsilon0": 1e-12, "mde_absolute": 0.}
    frame = a3.analyze_cell_from_frozen_prediction(instance_id="C001", frozen_path=frozen_path,
                                                  frozen_hash=a3._sha256(frozen_path), output_root=tmp_path, config=config)
    row = frame.iloc[0]
    assert row.predicted_order == ("tie" if prediction_tied else LEFT)
    assert row.empirical_order == "tie"
    assert not row.ordering_match
    assert row.a3_status == ("ambiguous" if prediction_tied else "fail")
    assert bool(row.active_pair) is (not prediction_tied)
