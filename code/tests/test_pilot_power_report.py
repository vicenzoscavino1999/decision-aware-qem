import numpy as np
import pandas as pd

from experiments.pilot_power_report import (
    choose_primary_cell,
    method_mse_by_method,
    paired_outcome_counts,
    pooled_observed_effect,
    static_power,
)


def test_choose_primary_cell_prefers_largest_band_margin():
    table = pd.DataFrame(
        [
            {
                "cell": "P001",
                "budget": 256,
                "failure_rate_MSE": 0.20,
                "in_band": True,
                "band_margin": 0.05,
            },
            {
                "cell": "P002",
                "budget": 512,
                "failure_rate_MSE": 0.40,
                "in_band": True,
                "band_margin": 0.25,
            },
            {
                "cell": "P003",
                "budget": 256,
                "failure_rate_MSE": 0.05,
                "in_band": False,
                "band_margin": -0.10,
            },
        ]
    )

    primary = choose_primary_cell(table)

    assert primary["cell"] == "P002"
    assert int(primary["budget"]) == 512


def test_method_mse_by_method_averages_replicates_and_candidates():
    ideal = np.array([1.0, 2.0])
    samples = {
        "A": np.array([[1.0, 2.0], [2.0, 4.0]]),
        "B": np.array([[1.0, 3.0], [1.0, 1.0]]),
    }

    mse = method_mse_by_method(samples, ideal)

    assert mse["A"] == 1.25
    assert mse["B"] == 0.5


def test_paired_outcome_counts_labels_b_as_da_better():
    mse = np.array(
        [
            [1.0, 1.0],    # both ok
            [-1.0, 1.0],   # both fail
            [-1.0, 1.0],   # DA better
            [1.0, 1.0],    # DA worse
        ]
    )
    da = np.array(
        [
            [1.0, 1.0],
            [-1.0, 1.0],
            [1.0, 1.0],
            [-1.0, 1.0],
        ]
    )

    counts = paired_outcome_counts(mse, da)

    assert counts["both_ok"] == 1
    assert counts["both_fail"] == 1
    assert counts["b"] == 1
    assert counts["c"] == 1
    assert counts["observed_rel_reduction"] == 0.0


def test_pooled_observed_effect_uses_only_in_band_rows_at_budget():
    table = pd.DataFrame(
        [
            {
                "cell": "P001",
                "budget": 512,
                "in_band": True,
                "both_fail": 10,
                "both_ok": 80,
                "b": 10,
                "c": 0,
                "paired_n": 100,
            },
            {
                "cell": "P002",
                "budget": 512,
                "in_band": False,
                "both_fail": 10,
                "both_ok": 0,
                "b": 0,
                "c": 90,
                "paired_n": 100,
            },
        ]
    )

    pooled = pooled_observed_effect(table, 512)

    assert pooled["pilot_instances"] == 1
    assert pooled["paired_n_pilot"] == 100
    assert pooled["observed_rel_reduction_pooled"] == 0.5
    assert pooled["observed_effect_meets_target"] is True


def test_static_power_is_deterministic_from_observed_pooled_counts():
    pooled = {
        "both_fail": 60,
        "both_ok": 120,
        "b": 18,
        "c": 2,
    }
    p1 = static_power(
        pooled_counts=pooled,
        paired_decisions=1920,
        alpha=0.05,
        repetitions=200,
    )
    p2 = static_power(
        pooled_counts=pooled,
        paired_decisions=1920,
        alpha=0.05,
        repetitions=200,
    )

    assert p1 == p2
    assert p1 > 0.95
