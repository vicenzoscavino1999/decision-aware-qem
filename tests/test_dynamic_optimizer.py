import numpy as np
import pandas as pd
import pytest

from daqem.dynamic import (
    DynamicSafeguards,
    epsilon_opt_from_ideal_values,
    generate_candidate_batch,
    lexicographic_argmin,
    success_from_regret,
)
from daqem.rng import make_rng
from experiments.e2_dynamic_batch_candidate_optimizer import (
    _advantage_label,
    _completed_dynamic_instance,
    _dynamic_config_fingerprint,
    _dynamic_instance_paths,
    _epsilon_selection_table,
    _metric_discrimination_diagnostic,
    _radius_selection_table,
    _robustness_counts,
    _summary_with_success_column,
    _write_dynamic_instance_outputs,
    load_config,
)


def test_dynamic_safeguards_reject_any_disabled_flag():
    DynamicSafeguards().validate()
    with pytest.raises(ValueError, match="all dynamic pairing safeguards"):
        DynamicSafeguards(same_candidates_for_DA_and_MSE=False).validate()


def test_candidate_batch_is_deterministic_and_keeps_incumbent_first():
    incumbent = np.array([0.1, 0.2, 0.3, 0.4])
    rng1 = make_rng(
        instance_id="P001",
        method="dynamic_candidates",
        budget=1024,
        replicate_id=7,
        stream="round_0",
    )
    rng2 = make_rng(
        instance_id="P001",
        method="dynamic_candidates",
        budget=1024,
        replicate_id=7,
        stream="round_0",
    )

    batch1 = generate_candidate_batch(
        incumbent, candidates_per_round=5, radius=0.16, rng=rng1
    )
    batch2 = generate_candidate_batch(
        incumbent, candidates_per_round=5, radius=0.16, rng=rng2
    )

    assert batch1.shape == (5, 4)
    np.testing.assert_allclose(batch1, batch2)
    np.testing.assert_allclose(batch1[0], incumbent)


def test_lexicographic_argmin_uses_first_minimum():
    assert lexicographic_argmin(np.array([2.0, 1.0, 1.0])) == 1


def test_epsilon_success_definition():
    eps = epsilon_opt_from_ideal_values(np.array([1.0, 2.0, 4.0]), quantile=0.5)
    assert eps == 1.0
    assert success_from_regret(1.0, eps)
    assert not success_from_regret(1.01, eps)


def test_dynamic_smoke_config_is_review_scoped_and_paired():
    config = load_config("smoke")

    assert config["instance_ids"] == ["P001"]
    assert config["budget_grid"] == [256, 1024]
    assert int(config["B_max"]) == 1024
    assert int(config["candidates_per_round"]) == 5
    assert int(config["max_rounds"]) == 5
    assert "decision_score_z" not in config
    assert all(
        bool(config[key])
        for key in [
            "candidate_generation_independent_of_selector",
            "same_candidates_for_DA_and_MSE",
            "same_initial_points_for_DA_and_MSE",
            "same_budget_grid_for_DA_and_MSE",
            "same_stopping_rule_for_DA_and_MSE",
            "selector_does_not_generate_candidates",
        ]
    )


def test_dynamic_regime_probe_uses_low_budget_grid():
    config = load_config("regime_probe")

    assert config["instance_ids"] == ["P001"]
    assert config["budget_grid"] == [32, 64, 128, 256, 512, 1024]
    assert int(config["B_max"]) == 1024
    assert float(config["candidate_radius"]) == 0.08


def test_dynamic_high_budget_probe_is_not_full():
    config = load_config("regime_probe_highB")

    assert config["instance_ids"] == ["P001"]
    assert int(config["trajectories"]) == 20
    assert int(config["max_rounds"]) == 4
    assert config["budget_grid"] == [256, 512, 1024, 2048, 4096, 8192]
    assert int(config["B_max"]) == 8192
    assert float(config["candidate_radius"]) == 0.08


def test_dynamic_radius_sweep_profile_and_neutral_selection_rule():
    config = load_config("radius_sweep")
    assert config["candidate_radius_grid"] == [0.12, 0.16, 0.24, 0.32]
    assert int(config["trajectories"]) == 20
    assert config["budget_grid"] == [256, 512, 1024, 2048, 4096, 8192]

    summary = pd.DataFrame(
        [
            {"radius": 0.12, "selector": "DA", "budget": 256, "P_success": 0.4},
            {"radius": 0.12, "selector": "DA", "budget": 8192, "P_success": 0.84},
            {"radius": 0.12, "selector": "MSE", "budget": 256, "P_success": 0.3},
            {"radius": 0.12, "selector": "MSE", "budget": 8192, "P_success": 0.9},
            {"radius": 0.16, "selector": "DA", "budget": 256, "P_success": 0.5},
            {"radius": 0.16, "selector": "DA", "budget": 8192, "P_success": 0.86},
            {"radius": 0.16, "selector": "MSE", "budget": 256, "P_success": 0.6},
            {"radius": 0.16, "selector": "MSE", "budget": 8192, "P_success": 0.86},
            {"radius": 0.24, "selector": "DA", "budget": 256, "P_success": 0.9},
            {"radius": 0.24, "selector": "DA", "budget": 8192, "P_success": 0.95},
            {"radius": 0.24, "selector": "MSE", "budget": 256, "P_success": 0.9},
            {"radius": 0.24, "selector": "MSE", "budget": 8192, "P_success": 0.95},
        ]
    )

    table, chosen = _radius_selection_table(
        summary,
        ceiling_min=0.85,
        mse_rise_min=0.15,
    )

    assert chosen == 0.16
    elig = dict(zip(table["radius"], table["eligible_by_rule"], strict=True))
    assert not elig[0.12]
    assert elig[0.16]
    assert not elig[0.24]


def test_dynamic_decision_quality_probe_profile_and_metric_split():
    config = load_config("decision_quality_probe")
    assert config["instance_ids"] == ["P001"]
    assert int(config["trajectories"]) == 30
    assert int(config["max_rounds"]) == 4
    assert float(config["candidate_radius"]) == 0.24
    assert config["budget_grid"] == [256, 512, 1024, 2048, 4096, 8192]

    results = pd.DataFrame(
        [
            {
                "instance": "P001",
                "selector": "DA",
                "budget": 256,
                "selected_method": "Raw",
                "success_decision": True,
                "success_global": False,
                "selector_source_budget": "256",
                "active_scales": 1,
                "cost_per_candidate_shots": 256,
            },
            {
                "instance": "P001",
                "selector": "DA",
                "budget": 256,
                "selected_method": "Raw",
                "success_decision": True,
                "success_global": True,
                "selector_source_budget": "256",
                "active_scales": 1,
                "cost_per_candidate_shots": 256,
            },
        ]
    )

    decision = _summary_with_success_column(results, 0.8, "success_decision")
    global_opt = _summary_with_success_column(results, 0.8, "success_global")

    assert float(decision.iloc[0]["P_success"]) == 1.0
    assert float(global_opt.iloc[0]["P_success"]) == 0.5


def test_dynamic_epsilon_sweep_profile_and_neutral_mse_rule():
    config = load_config("epsilon_sweep")
    assert config["instance_ids"] == ["P001"]
    assert int(config["trajectories"]) == 30
    assert int(config["max_rounds"]) == 4
    assert float(config["candidate_radius"]) == 0.24
    assert config["epsilon_quantile_grid"] == [0.10, 0.05, 0.02, 0.01]
    assert config["budget_grid"] == [256, 512, 1024, 2048, 4096, 8192]
    assert int(config["B_max"]) == 8192

    decision_summary = pd.DataFrame(
        [
            {"epsilon_quantile": 0.10, "selector": "MSE", "budget": 256, "P_success": 0.70},
            {"epsilon_quantile": 0.10, "selector": "MSE", "budget": 8192, "P_success": 0.95},
            {"epsilon_quantile": 0.05, "selector": "MSE", "budget": 256, "P_success": 0.60},
            {"epsilon_quantile": 0.05, "selector": "MSE", "budget": 8192, "P_success": 0.83},
            {"epsilon_quantile": 0.02, "selector": "MSE", "budget": 256, "P_success": 0.40},
            {"epsilon_quantile": 0.02, "selector": "MSE", "budget": 8192, "P_success": 0.82},
            {"epsilon_quantile": 0.01, "selector": "MSE", "budget": 256, "P_success": 0.30},
            {"epsilon_quantile": 0.01, "selector": "MSE", "budget": 8192, "P_success": 0.70},
            {"epsilon_quantile": 0.10, "selector": "DA", "budget": 256, "P_success": 0.99},
            {"epsilon_quantile": 0.10, "selector": "DA", "budget": 8192, "P_success": 0.99},
        ]
    )

    table, chosen = _epsilon_selection_table(
        decision_summary,
        p_target=0.80,
        mse_p256_max=0.60,
        mse_rise_min=0.20,
    )

    assert chosen == 0.05
    elig = dict(zip(table["epsilon_quantile"], table["eligible"], strict=True))
    assert not elig[0.10]
    assert elig[0.05]
    assert elig[0.02]
    assert not elig[0.01]


def test_dynamic_pilot_full_profile_is_checkpointed_and_review_scoped():
    config = load_config("dynamic_pilot_full")

    assert config["instance_ids"] == ["P001", "P002", "P003", "P004"]
    assert int(config["trajectories"]) == 100
    assert int(config["max_rounds"]) == 20
    assert float(config["candidate_radius"]) == 0.24
    assert float(config["epsilon_quantile"]) == 0.01
    assert config["budget_grid"] == [256, 512, 1024, 2048, 4096, 8192]
    assert int(config["B_max"]) == 8192
    assert bool(config["checkpoint_by_instance"])


def test_dynamic_instance_checkpoint_requires_matching_hashes(tmp_path):
    profile = "dynamic_pilot_full"
    instance_id = "P001"
    config = load_config(profile)
    fingerprint = _dynamic_config_fingerprint(config)
    results = pd.DataFrame(
        [
            {
                "instance": instance_id,
                "trajectory": 0,
                "selector": "DA",
                "budget": 256,
                "selected_method": "Raw",
                "selector_source_budget": "256",
                "final_ideal_value": 0.0,
                "best_seen_ideal_value": 0.0,
                "reference_best_ideal_value": 0.0,
                "epsilon_opt": 0.01,
                "regret": 0.0,
                "regret_decision": 0.0,
                "regret_global": 0.0,
                "active_scales": 1,
                "cost_per_candidate_shots": 256,
                "success": True,
                "success_decision": True,
                "success_global": True,
            }
        ]
    )
    trace = pd.DataFrame(
        [
            {
                "instance": instance_id,
                "trajectory": 0,
                "round": 0,
                "budget": 256,
                "reference_candidate": 0,
                "MSE_method": "Raw",
                "MSE_candidate": 0,
                "MSE_score": 0.0,
                "DA_method": "Raw",
                "DA_candidate": 0,
                "DA_score": 0.0,
                "round_best_ideal": 0.0,
            }
        ]
    )
    cost = {"aer_runs": 1, "circuits": 5, "shots": 40960}

    _write_dynamic_instance_outputs(
        tmp_path,
        profile,
        instance_id,
        results,
        trace,
        cost,
        duration_seconds=0.1,
        config_fingerprint=fingerprint,
    )

    assert _completed_dynamic_instance(tmp_path, profile, instance_id, fingerprint)
    paths = _dynamic_instance_paths(tmp_path, profile, instance_id)
    paths["results"].write_text("corrupted\n", encoding="utf-8")
    assert not _completed_dynamic_instance(tmp_path, profile, instance_id, fingerprint)


def test_dynamic_advantage_label_requires_clean_accuracy_advantage():
    mixed = pd.DataFrame(
        [
            {"selector": "DA", "budget": 256, "P_success": 0.7},
            {"selector": "MSE", "budget": 256, "P_success": 0.6},
            {"selector": "DA", "budget": 512, "P_success": 0.76},
            {"selector": "MSE", "budget": 512, "P_success": 0.8},
        ]
    )
    clean = pd.DataFrame(
        [
            {"selector": "DA", "budget": 256, "P_success": 0.7},
            {"selector": "MSE", "budget": 256, "P_success": 0.6},
            {"selector": "DA", "budget": 512, "P_success": 0.8},
            {"selector": "MSE", "budget": 512, "P_success": 0.8},
        ]
    )

    assert _advantage_label(mixed, ratio=1.5) == "cost_only"
    assert _advantage_label(clean, ratio=1.5) == "cost_plus_accuracy"


def test_dynamic_robustness_counts_tracks_marginal_no_cross():
    rows = [
        {"selector": "DA", "reaches_target": True, "marginal_no_cross": False},
        {"selector": "DA", "reaches_target": False, "marginal_no_cross": True},
        {"selector": "MSE", "reaches_target": False, "marginal_no_cross": False},
    ]

    counts = _robustness_counts(rows)

    assert counts["DA"] == {"total": 2, "reaches": 1, "marginal": 1}
    assert counts["MSE"] == {"total": 1, "reaches": 0, "marginal": 0}


def test_metric_discrimination_requires_selector_separation():
    summary = pd.DataFrame(
        [
            {"instance": "P001", "selector": "DA", "budget": 256, "P_success": 0.9},
            {"instance": "P001", "selector": "MSE", "budget": 256, "P_success": 0.9},
            {"instance": "P001", "selector": "DA", "budget": 512, "P_success": 1.0},
            {"instance": "P001", "selector": "MSE", "budget": 512, "P_success": 1.0},
        ]
    )

    diag = _metric_discrimination_diagnostic(summary)

    assert diag["low_budget_below_one"]
    assert diag["rises_with_budget_any_selector"]
    assert not diag["selector_separated_any_budget"]
    assert not diag["discriminates_da_vs_mse"]
