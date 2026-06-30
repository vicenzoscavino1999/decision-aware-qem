from __future__ import annotations

import numpy as np
import pandas as pd

from daqem.budget import validate_ledger
from daqem.noise import ONE_QUBIT_DEPOLARIZING, TWO_QUBIT_DEPOLARIZING
from daqem.pec import (
    circuit_gamma,
    decision_effect_demo,
    inverse_depolarizing_quasiprobabilities,
    load_pec_config,
    one_qubit_gamma_closed_form,
    pec_expectation_aer,
    pec_overhead_ledger_row,
)
from daqem.qaoa import default_angles, maxcut_graph


def test_one_qubit_gamma_matches_closed_form_from_qiskit_probabilities() -> None:
    inverse = inverse_depolarizing_quasiprobabilities(ONE_QUBIT_DEPOLARIZING, 1)
    expected = one_qubit_gamma_closed_form(ONE_QUBIT_DEPOLARIZING)
    assert abs(inverse.gamma - expected) < 1e-12
    assert abs(inverse.channel_probabilities["I"] - 0.9925) < 1e-12
    assert abs(inverse.inferred_p - ONE_QUBIT_DEPOLARIZING) < 1e-12


def test_pec_gamma_squared_is_recorded_in_budget_ledger() -> None:
    graph = maxcut_graph(num_qubits=2, degree=1, seed=260616)
    gammas, betas = default_angles(1)
    gamma = circuit_gamma(
        graph,
        depth=1,
        gammas=gammas,
        betas=betas,
        p1=ONE_QUBIT_DEPOLARIZING,
        p2=TWO_QUBIT_DEPOLARIZING,
    )
    row = pec_overhead_ledger_row(gamma=gamma, B_nominal=128)
    assert abs(row["C_overhead"] - gamma * gamma) < 1e-12
    assert row["C_total"] == row["C_overhead"]
    assert row["amortization_flag"] == "non_amortized"
    assert validate_ledger(pd.DataFrame([row])) == []


def test_pec_sampling_is_deterministic() -> None:
    graph = maxcut_graph(num_qubits=2, degree=1, seed=260616)
    gammas, betas = default_angles(1)
    left = pec_expectation_aer(
        graph,
        depth=1,
        gammas=gammas,
        betas=betas,
        n_samples=80,
        shots_per_sample=32,
        instance_id="PEC_DETERMINISM_TEST",
    )
    right = pec_expectation_aer(
        graph,
        depth=1,
        gammas=gammas,
        betas=betas,
        n_samples=80,
        shots_per_sample=32,
        instance_id="PEC_DETERMINISM_TEST",
    )
    assert left == right


def test_pec_estimator_moves_toward_exact_for_known_noise() -> None:
    config = load_pec_config()
    smoke_cfg = config["smoke"]
    graph = maxcut_graph(
        num_qubits=smoke_cfg["num_qubits"],
        degree=smoke_cfg["degree"],
        seed=smoke_cfg["graph_seed"],
    )
    gammas, betas = default_angles(smoke_cfg["depth"])
    result = pec_expectation_aer(
        graph,
        depth=smoke_cfg["depth"],
        gammas=gammas,
        betas=betas,
        n_samples=smoke_cfg["n_samples"],
        shots_per_sample=smoke_cfg["shots_per_sample"],
        p1=config["true_noise_channel"]["p1"],
        p2=config["true_noise_channel"]["p2"],
        instance_id="PEC_UNBIASEDNESS_TEST",
    )
    raw_error = abs(result.target_raw - result.target_exact)
    pec_error = abs(result.target_pec - result.target_exact)
    assert raw_error > 1e-3
    assert pec_error < raw_error
    assert pec_error < 0.02


def test_pec_changes_representative_gri_risk() -> None:
    demo = decision_effect_demo()
    assert demo["nontrivial"] is True
    assert np.isfinite(demo["risk_raw"])
    assert np.isfinite(demo["risk_pec"])
    assert abs(demo["risk_pec"] - demo["risk_raw"]) > 1e-6
