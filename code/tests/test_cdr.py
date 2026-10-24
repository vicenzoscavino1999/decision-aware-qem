from __future__ import annotations

import numpy as np
import pandas as pd

from daqem.budget import validate_ledger
from daqem.cdr import (
    cdr_training_ledger_row,
    exact_maxcut_expectation_from_gate_angles,
    fit_linear_cdr,
    generate_near_clifford_training_set,
    load_cdr_config,
    qaoa_gate_specs_and_angles,
    run_cdr,
)
from daqem.candidates import noiseless_qaoa_maxcut_expectation
from daqem.noise import depolarizing_noise_model
from daqem.qaoa import default_angles, maxcut_graph


def test_cdr_exact_truth_matches_statevector_reference_on_clifford_case() -> None:
    graph = maxcut_graph(num_qubits=4, degree=2, seed=7)
    depth = 1
    gammas = np.array([0.0])
    betas = np.array([np.pi / 4.0])
    specs, gate_angles = qaoa_gate_specs_and_angles(
        graph,
        depth=depth,
        gammas=gammas,
        betas=betas,
    )
    exact = exact_maxcut_expectation_from_gate_angles(graph, specs, gate_angles)
    reference = noiseless_qaoa_maxcut_expectation(
        graph,
        depth=depth,
        angles=np.concatenate([gammas, betas]),
    )
    assert abs(exact - reference) < 1e-12


def test_cdr_regression_recovers_known_linear_correction() -> None:
    ideal = np.array([0.5, 1.0, 1.5, 2.0, 2.5], dtype=float)
    noisy = 0.5 * ideal + 1.0
    fit = fit_linear_cdr(noisy, ideal)
    assert abs(fit.a - 2.0) < 1e-12
    assert abs(fit.b + 2.0) < 1e-12


def test_cdr_training_generation_and_fit_are_deterministic() -> None:
    graph = maxcut_graph(num_qubits=4, degree=2, seed=11)
    depth = 1
    gammas = np.array([0.6])
    betas = np.array([0.4])
    specs, gate_angles = qaoa_gate_specs_and_angles(
        graph,
        depth=depth,
        gammas=gammas,
        betas=betas,
    )
    left = generate_near_clifford_training_set(
        gate_angles,
        training_set_size=6,
        rounded_gate_counts=[1, 2, 3],
        endpoint_modes=["lower", "upper"],
        instance_id="CDR_TEST",
    )
    right = generate_near_clifford_training_set(
        gate_angles,
        training_set_size=6,
        rounded_gate_counts=[1, 2, 3],
        endpoint_modes=["lower", "upper"],
        instance_id="CDR_TEST",
    )
    assert [x.rounded_mask.tolist() for x in left] == [
        x.rounded_mask.tolist() for x in right
    ]
    assert np.allclose(
        np.vstack([x.gate_angles for x in left]),
        np.vstack([x.gate_angles for x in right]),
    )

    config = {
        "training_set": {"training_set_size": 5, "shots_per_training_circuit": 64},
        "target_local_perturbation_rule": {
            "rounded_gate_counts": [1, 2, 3],
            "endpoint_modes": ["lower", "upper"],
            "mask_stride": 3,
        },
    }
    result_a = run_cdr(
        graph,
        depth=depth,
        gammas=gammas,
        betas=betas,
        instance_id="CDR_TEST_RUN",
        config=config,
        noise_model=depolarizing_noise_model(),
    )
    result_b = run_cdr(
        graph,
        depth=depth,
        gammas=gammas,
        betas=betas,
        instance_id="CDR_TEST_RUN",
        config=config,
        noise_model=depolarizing_noise_model(),
    )
    assert result_a.fit == result_b.fit
    assert result_a.target_mitigated == result_b.target_mitigated
    assert np.array_equal(result_a.training_noisy, result_b.training_noisy)


def test_cdr_smoke_training_exact_is_non_degenerate_and_brackets_target() -> None:
    config = load_cdr_config()
    graph = maxcut_graph(num_qubits=10, degree=3, seed=260616)
    depth = 2
    gammas, betas = default_angles(depth)
    specs, target_angles = qaoa_gate_specs_and_angles(
        graph,
        depth=depth,
        gammas=gammas,
        betas=betas,
    )
    training = generate_near_clifford_training_set(
        target_angles,
        training_set_size=config["training_set"]["training_set_size"],
        rounded_gate_counts=config["target_local_perturbation_rule"]["rounded_gate_counts"],
        endpoint_modes=config["target_local_perturbation_rule"]["endpoint_modes"],
        instance_id="CDR_SMOKE_P0",
        mask_stride=config["target_local_perturbation_rule"]["mask_stride"],
    )
    exact_values = np.array(
        [
            exact_maxcut_expectation_from_gate_angles(graph, specs, item.gate_angles)
            for item in training
        ],
        dtype=float,
    )
    target_exact = exact_maxcut_expectation_from_gate_angles(graph, specs, target_angles)
    assert float(np.std(exact_values)) > config["validity_bar"]["training_exact_std_min"]
    assert float(np.min(exact_values)) <= target_exact <= float(np.max(exact_values))
    assert not np.allclose(exact_values, 7.5)


def test_cdr_config_training_set_size_matches_declared_grid() -> None:
    config = load_cdr_config()
    perturbation = config["target_local_perturbation_rule"]
    expected = len(perturbation["rounded_gate_counts"]) * len(
        perturbation["endpoint_modes"]
    )
    assert config["training_set"]["training_set_size"] == expected
    assert config["training_set"]["composition_guardrail"][
        "expected_training_set_size"
    ] == expected


def test_cdr_c_train_is_recorded_in_budget_ledger_row() -> None:
    row = cdr_training_ledger_row(
        training_set_size=24,
        shots_per_training_circuit=1024,
    )
    assert row["C_train"] == 24 * 1024
    assert row["C_total"] == 24 * 1024
    assert row["amortization_flag"] == "non_amortized"
    errors = validate_ledger(pd.DataFrame([row]))
    assert errors == []
