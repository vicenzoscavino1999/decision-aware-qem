from __future__ import annotations

import numpy as np
import pandas as pd

from daqem.budget import validate_ledger
from experiments.derisk_fakebackend.rem import (
    apply_tensor_confusion,
    build_tensored_calibration_circuits,
    confusion_matrices_from_calibration,
    correct_probabilities_tensored,
    rem_budget_ledger_row,
    rem_budget_split,
    rem_corrected_maxcut_expectation,
    simulate_calibration_counts,
)


def _known_readout_matrices() -> np.ndarray:
    matrices = np.zeros((3, 2, 2), dtype=float)
    # matrices[qubit, measured, prepared]
    matrices[0] = np.array([[0.94, 0.08], [0.06, 0.92]])
    matrices[1] = np.array([[0.91, 0.11], [0.09, 0.89]])
    matrices[2] = np.array([[0.96, 0.05], [0.04, 0.95]])
    return matrices


def test_rem_recovers_known_distribution_after_readout_error() -> None:
    true_probabilities = np.array([0.03, 0.16, 0.08, 0.18, 0.10, 0.15, 0.11, 0.19])
    true_probabilities /= true_probabilities.sum()
    matrices = _known_readout_matrices()
    calibration = simulate_calibration_counts(
        matrices,
        calibration_shots=100_000,
        instance_id="REM_CORRECTNESS",
        budget=512,
        replicate_id=7,
    )
    estimated_matrices = confusion_matrices_from_calibration(calibration)
    observed = apply_tensor_confusion(true_probabilities, matrices)
    corrected = correct_probabilities_tensored(observed, estimated_matrices)

    assert np.max(np.abs(corrected - true_probabilities)) < 5e-3

    edges = [(0, 1), (1, 2)]
    corrected_expectation = rem_corrected_maxcut_expectation(
        observed,
        estimated_matrices,
        edges=edges,
    )
    values = np.array([0, 1, 2, 1, 1, 2, 1, 0], dtype=float)
    assert abs(corrected_expectation - float(np.dot(true_probabilities, values))) < 5e-3


def test_rem_builds_two_physical_qubit_calibration_circuits() -> None:
    zero, one = build_tensored_calibration_circuits([16, 22, 25], backend_num_qubits=27)

    assert zero.num_qubits == one.num_qubits == 27
    assert zero.num_clbits == one.num_clbits == 3
    assert zero.count_ops()["measure"] == 3
    assert one.count_ops()["x"] == 3
    assert one.count_ops()["measure"] == 3


def test_rem_calibration_is_deterministic_for_same_identifiers() -> None:
    matrices = _known_readout_matrices()
    left = simulate_calibration_counts(
        matrices,
        calibration_shots=4096,
        instance_id="P004",
        budget=512,
        replicate_id=3,
    )
    right = simulate_calibration_counts(
        matrices,
        calibration_shots=4096,
        instance_id="P004",
        budget=512,
        replicate_id=3,
    )

    assert np.array_equal(left.counts, right.counts)
    assert left.calibration_shots == right.calibration_shots == 4096


def test_rem_calibration_shots_are_charged_to_budget_ledger() -> None:
    split = rem_budget_split(B_nominal=512, f_calib=0.2)
    row = rem_budget_ledger_row(B_nominal=512, f_calib=0.2)

    assert split.two_calib == 102
    assert split.calibration_shots == 51
    assert split.C_eval == 410
    assert row["method"] == "Raw+REM"
    assert row["C_eval"] == 410.0
    assert row["C_calib"] == 102.0
    assert row["C_total"] == 512.0
    assert row["amortization_flag"] == "non_amortized"
    assert validate_ledger(pd.DataFrame([row])) == []
