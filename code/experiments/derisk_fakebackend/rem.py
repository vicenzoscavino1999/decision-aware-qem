"""Readout error mitigation helpers for the FakeBackend de-risk.

This module is intentionally outside ``src/daqem`` and outside the frozen package.
It implements a tensored per-qubit readout confusion model for the additive
FakeBackend de-risk without changing the frozen QEM methods.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import numpy as np

from daqem.budget import total_cost
from daqem.rng import make_rng


METHOD_NAME = "Raw+REM"
CALIBRATION_STREAM = "rem_calibration"
DEFAULT_CALIBRATION_FRACTION = 0.2


@dataclass(frozen=True)
class REMCalibrationCounts:
    """Per-qubit calibration counts for prepared all-zero/all-one circuits.

    The array has shape ``(2, n_qubits, 2)`` and is indexed as
    ``counts[prepared_bit, qubit, measured_bit]``.
    """

    counts: np.ndarray
    calibration_shots: int

    @property
    def num_qubits(self) -> int:
        return int(self.counts.shape[1])


@dataclass(frozen=True)
class REMBudgetSplit:
    """Matched-total REM budget split.

    ``two_calib`` is the total shot envelope charged to the two calibration
    circuits. At low budgets it can be odd under the pre-registered rounding
    rule; ``calibration_shots`` is the per-circuit floor used by equal-shot
    calibration helpers, and the ledger still charges the full ``two_calib``.
    This deliberately makes low-budget REM calibration noisy rather than giving
    it extra shots outside the matched budget envelope.
    """

    B_nominal: int
    f_calib: float
    two_calib: int
    calibration_shots: int
    C_eval: int


def rem_budget_split(
    *,
    B_nominal: int,
    f_calib: float = DEFAULT_CALIBRATION_FRACTION,
) -> REMBudgetSplit:
    """Split a nominal budget into evaluation and REM calibration shots."""

    budget = int(B_nominal)
    if budget <= 0:
        raise ValueError("B_nominal must be positive")
    fraction = float(f_calib)
    if not 0.0 <= fraction < 1.0:
        raise ValueError("f_calib must satisfy 0 <= f_calib < 1")
    two_calib = int(round(fraction * budget))
    if two_calib < 2:
        raise ValueError("matched REM calibration requires at least two calibration shots")
    C_eval = budget - two_calib
    if C_eval <= 0:
        raise ValueError("REM calibration leaves no evaluation budget")
    return REMBudgetSplit(
        B_nominal=budget,
        f_calib=fraction,
        two_calib=two_calib,
        calibration_shots=two_calib // 2,
        C_eval=C_eval,
    )


def build_tensored_calibration_circuits(
    physical_qubits: Sequence[int],
    *,
    backend_num_qubits: int | None = None,
):
    """Return the all-zero/all-one readout calibration circuits.

    The circuits measure the selected physical qubits into contiguous classical
    bits ordered like ``physical_qubits``. The import is local so unit tests that
    exercise only the linear-algebra REM path do not need to construct Qiskit
    circuits.
    """

    from qiskit import QuantumCircuit

    physical = [int(qubit) for qubit in physical_qubits]
    if not physical:
        raise ValueError("physical_qubits must be non-empty")
    num_qubits = int(backend_num_qubits) if backend_num_qubits is not None else max(physical) + 1
    if min(physical) < 0 or max(physical) >= num_qubits:
        raise ValueError("physical qubit index outside backend range")

    zero = QuantumCircuit(num_qubits, len(physical))
    one = QuantumCircuit(num_qubits, len(physical))
    for classical, physical_qubit in enumerate(physical):
        one.x(physical_qubit)
        zero.measure(physical_qubit, classical)
        one.measure(physical_qubit, classical)
    return zero, one


def calibration_rng(
    *,
    instance_id: str,
    budget: int,
    replicate_id: int,
) -> np.random.Generator:
    """Return the deterministic PAP RNG stream for REM calibration."""

    return make_rng(
        instance_id=instance_id,
        method=METHOD_NAME,
        budget=int(budget),
        replicate_id=int(replicate_id),
        stream=CALIBRATION_STREAM,
    )


def simulate_calibration_counts(
    confusion_matrices: np.ndarray,
    *,
    calibration_shots: int,
    instance_id: str,
    budget: int,
    replicate_id: int,
) -> REMCalibrationCounts:
    """Sample the two REM calibration circuits from known readout matrices.

    ``confusion_matrices[q, measured, prepared]`` gives the per-qubit readout
    confusion matrix. This routine is used by tests and by dry-run accounting;
    production FakeBackend runs can fill the same ``REMCalibrationCounts`` data
    structure from Aer measurement counts.
    """

    matrices = np.asarray(confusion_matrices, dtype=float)
    if matrices.ndim != 3 or matrices.shape[1:] != (2, 2):
        raise ValueError("confusion_matrices must have shape (n_qubits, 2, 2)")
    if calibration_shots <= 0:
        raise ValueError("calibration_shots must be positive")

    rng = calibration_rng(
        instance_id=instance_id,
        budget=budget,
        replicate_id=replicate_id,
    )
    counts = np.zeros((2, matrices.shape[0], 2), dtype=np.int64)
    for prepared in (0, 1):
        for qubit in range(matrices.shape[0]):
            probabilities = matrices[qubit, :, prepared]
            counts[prepared, qubit] = rng.multinomial(
                int(calibration_shots),
                probabilities / probabilities.sum(),
            )
    return REMCalibrationCounts(counts=counts, calibration_shots=int(calibration_shots))


def confusion_matrices_from_calibration(
    calibration: REMCalibrationCounts,
    *,
    min_column_probability: float = 1e-12,
) -> np.ndarray:
    """Estimate per-qubit confusion matrices from all-zero/all-one calibrations."""

    counts = np.asarray(calibration.counts, dtype=float)
    if counts.ndim != 3 or counts.shape[0] != 2 or counts.shape[2] != 2:
        raise ValueError("calibration counts must have shape (2, n_qubits, 2)")

    matrices = np.zeros((counts.shape[1], 2, 2), dtype=float)
    for prepared in (0, 1):
        denom = counts[prepared].sum(axis=1)
        if np.any(denom <= 0):
            raise ValueError("each prepared calibration must contain at least one shot")
        matrices[:, :, prepared] = counts[prepared] / denom[:, None]

    matrices = np.clip(matrices, min_column_probability, None)
    matrices /= matrices.sum(axis=1, keepdims=True)
    return matrices


def project_to_probability_simplex(values: Sequence[float]) -> np.ndarray:
    """Project a vector onto the probability simplex."""

    vector = np.asarray(values, dtype=float)
    if vector.ndim != 1:
        raise ValueError("probability vector must be one-dimensional")
    if vector.size == 0:
        raise ValueError("probability vector must be non-empty")

    sorted_values = np.sort(vector)[::-1]
    cssv = np.cumsum(sorted_values)
    indices = np.arange(1, vector.size + 1)
    support = sorted_values - (cssv - 1.0) / indices > 0
    if not np.any(support):
        return np.full_like(vector, 1.0 / vector.size, dtype=float)
    rho = indices[support][-1]
    theta = (cssv[support][-1] - 1.0) / rho
    projected = np.maximum(vector - theta, 0.0)
    return projected / projected.sum()


def apply_tensor_confusion(
    true_probabilities: Sequence[float],
    confusion_matrices: np.ndarray,
) -> np.ndarray:
    """Apply a tensored readout confusion channel to a probability vector.

    Probability vectors use little-endian integer indexing: bit ``q`` of the
    integer labels qubit ``q``.
    """

    probabilities = np.asarray(true_probabilities, dtype=float)
    matrices = np.asarray(confusion_matrices, dtype=float)
    num_qubits = matrices.shape[0]
    if probabilities.shape != (2**num_qubits,):
        raise ValueError("probability vector length must be 2**num_qubits")

    tensor = probabilities.reshape((2,) * num_qubits, order="F")
    for qubit in range(num_qubits):
        tensor = np.tensordot(matrices[qubit], tensor, axes=([1], [qubit]))
        tensor = np.moveaxis(tensor, 0, qubit)
    return tensor.reshape(2**num_qubits, order="F")


def correct_probabilities_tensored(
    observed_probabilities: Sequence[float],
    confusion_matrices: np.ndarray,
    *,
    project: bool = True,
) -> np.ndarray:
    """Invert a tensored readout confusion model and optionally project to probabilities."""

    observed = np.asarray(observed_probabilities, dtype=float)
    matrices = np.asarray(confusion_matrices, dtype=float)
    num_qubits = matrices.shape[0]
    if observed.shape != (2**num_qubits,):
        raise ValueError("observed probability vector length must be 2**num_qubits")

    tensor = observed.reshape((2,) * num_qubits, order="F")
    for qubit in range(num_qubits):
        inverse = np.linalg.pinv(matrices[qubit])
        tensor = np.tensordot(inverse, tensor, axes=([1], [qubit]))
        tensor = np.moveaxis(tensor, 0, qubit)
    corrected = tensor.reshape(2**num_qubits, order="F")
    if project:
        corrected = project_to_probability_simplex(corrected)
    return corrected


def probabilities_from_counts(
    counts: Mapping[str, int],
    *,
    num_qubits: int,
    qiskit_bit_order: bool = True,
) -> np.ndarray:
    """Convert bitstring counts into the little-endian probability convention."""

    probabilities = np.zeros(2**int(num_qubits), dtype=float)
    total = float(sum(int(v) for v in counts.values()))
    if total <= 0:
        raise ValueError("counts must contain at least one shot")
    for bitstring, value in counts.items():
        compact = bitstring.replace(" ", "")
        if len(compact) != num_qubits:
            raise ValueError(f"bitstring {bitstring!r} does not have {num_qubits} bits")
        little = compact[::-1] if qiskit_bit_order else compact
        index = sum((1 << q) for q, bit in enumerate(little) if bit == "1")
        probabilities[index] += int(value) / total
    return probabilities


def maxcut_values(
    num_qubits: int,
    edges: Iterable[tuple[int, int]],
) -> np.ndarray:
    """Return the MaxCut value for every little-endian computational basis state."""

    edge_list = [(int(u), int(v)) for u, v in edges]
    values = np.zeros(2**int(num_qubits), dtype=float)
    for index in range(values.size):
        cut = 0
        for u, v in edge_list:
            cut += ((index >> u) & 1) != ((index >> v) & 1)
        values[index] = float(cut)
    return values


def rem_corrected_maxcut_expectation(
    observed_probabilities: Sequence[float],
    confusion_matrices: np.ndarray,
    *,
    edges: Iterable[tuple[int, int]],
    project: bool = True,
) -> float:
    """Apply REM and return the corrected MaxCut expectation."""

    corrected = correct_probabilities_tensored(
        observed_probabilities,
        confusion_matrices,
        project=project,
    )
    values = maxcut_values(confusion_matrices.shape[0], edges)
    return float(np.dot(corrected, values))


def rem_budget_ledger_row(
    *,
    B_nominal: int,
    f_calib: float = DEFAULT_CALIBRATION_FRACTION,
    selector: str = "not_applicable",
    task: str = "fakebackend_rem_readout_calibration",
) -> dict:
    """Return a matched-total budget-ledger row for REM calibration."""

    split = rem_budget_split(B_nominal=B_nominal, f_calib=f_calib)
    row = {
        "method": METHOD_NAME,
        "selector": selector,
        "task": task,
        "B_nominal": split.B_nominal,
        "C_train": 0.0,
        "C_select": 0.0,
        "C_eval": float(split.C_eval),
        "C_calib": float(split.two_calib),
        "C_noiselearn": 0.0,
        "C_Sigmahat": 0.0,
        "C_overhead": 0.0,
        "amortization_flag": "non_amortized",
    }
    row["C_total"] = total_cost(row)
    return row
