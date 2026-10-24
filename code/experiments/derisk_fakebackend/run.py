from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Kraus, SuperOp
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, kraus_error
from qiskit_ibm_runtime.fake_provider import FakeKolkataV2

from daqem.candidates import (
    landscape_for_instance,
    maxcut_values_for_graph,
    maxcut_graph_for_instance,
)
from daqem.cdr import cdr_training_ledger_row, fit_linear_cdr, load_cdr_config
from daqem.qaoa import qaoa_maxcut_circuit
from daqem.qem_methods import (
    accuracy_zne_coeffs,
    decision_optimal_zne_coeffs,
    richardson_constraints,
)
from daqem.risk import gri_risk
from daqem.rng import make_rng
from daqem.selectors import da_selector, mse_selector

from experiments.derisk_fakebackend.rem import (
    apply_tensor_confusion,
    confusion_matrices_from_calibration,
    correct_probabilities_tensored,
    maxcut_values,
    probabilities_from_counts,
    rem_budget_split,
    simulate_calibration_counts,
)
from experiments.gate0_pilot_full_vs_diagonal import (
    _covariance,
    empirical_decision_failure_rate,
)
from experiments.pilot_power_report import paired_outcome_counts


OUTPUT_DIR = REPO_ROOT / "results" / "derisk_fakebackend"
CELLS = ("P004", "P001", "P002")
METHODS = ("Raw", "Raw+REM", "Accuracy-ZNE", "Decision-ZNE", "CDR")
BUDGETS = (256, 512, 1024, 2048, 4096, 8192)
B_STAR = 512
REPLICATES = 40
DEPTH = 2
CANDIDATE_COUNT = 25
ZNE_LAMBDAS = np.array([1.0, 2.0, 3.0], dtype=float)
ZNE_ORDER = 1
DECISION_ZNE_MU_FLOOR = 1e-6
USE_LEDOIT_WOLF = True
SEED_TRANSPILE = 260616
REM_F_CALIB = 0.2
P004_FROZEN_INITIAL_LAYOUT = [16, 22, 25, 19, 20, 24, 23, 14, 26, 13]
AER_MAX_PARALLEL_THREADS = 0


@dataclass(frozen=True)
class CellData:
    instance_id: str
    graph_edges: tuple[tuple[int, int], ...]
    x_star: int
    ideal_values: np.ndarray
    values_by_state: np.ndarray
    noisy_observed_probs: np.ndarray
    raw_gate_probs: np.ndarray
    readout_matrices: np.ndarray
    mappings: dict[str, object]


def _state_index(key) -> int:
    clean = str(key).replace(" ", "")
    if isinstance(key, (int, np.integer)):
        return int(key)
    if clean.startswith("0x"):
        return int(clean, 16)
    return int(clean, 2)


def _counts_from_probabilities(probabilities: np.ndarray, shots: int) -> dict[str, int]:
    probs = np.asarray(probabilities, dtype=float)
    raw = probs * int(shots)
    counts = np.floor(raw).astype(int)
    remainder = int(shots) - int(counts.sum())
    if remainder > 0:
        order = np.argsort(raw - counts)[::-1]
        counts[order[:remainder]] += 1
    width = int(np.log2(probs.size))
    return {
        format(index, f"0{width}b"): int(count)
        for index, count in enumerate(counts)
        if int(count) > 0
    }


def _ordering_gate(instance_id: str, graph_edges: tuple[tuple[int, int], ...]) -> dict[str, object]:
    n = 10
    states = np.arange(2**n, dtype=float)
    true_probs = (1.0 + ((states * 37.0 + 11.0) % 101.0)).astype(float)
    true_probs /= true_probs.sum()
    matrices = np.zeros((n, 2, 2), dtype=float)
    for qubit in range(n):
        p01 = 0.015 + 0.002 * qubit
        p10 = 0.025 + 0.001 * qubit
        matrices[qubit] = np.array([[1.0 - p01, p10], [p01, 1.0 - p10]])
    observed = apply_tensor_confusion(true_probs, matrices)
    counts = _counts_from_probabilities(observed, shots=10_000_000)
    measured = probabilities_from_counts(counts, num_qubits=n, qiskit_bit_order=True)
    corrected = correct_probabilities_tensored(measured, matrices)
    values = maxcut_values(n, graph_edges)
    expected = float(np.dot(true_probs, values))
    recovered = float(np.dot(corrected, values))
    error = abs(recovered - expected)
    tolerance = 5e-5
    passed = bool(error <= tolerance)
    if not passed:
        raise RuntimeError(
            f"ordering gate failed for {instance_id}: expected={expected}, "
            f"recovered={recovered}, abs_error={error}"
        )
    return {
        "instance_id": instance_id,
        "passed": passed,
        "expected_maxcut": expected,
        "recovered_maxcut": recovered,
        "abs_error": error,
        "tolerance": tolerance,
    }


def _scaled_reduced_noise_model(
    full_noise_model: NoiseModel,
    physical_to_compact: dict[int, int],
    *,
    scale: float,
) -> NoiseModel:
    model = NoiseModel()
    model.add_basis_gates(full_noise_model.basis_gates)
    integer_scale = int(round(float(scale)))
    for instruction, errors in full_noise_model._local_quantum_errors.items():
        for qubits, error in errors.items():
            if all(int(qubit) in physical_to_compact for qubit in qubits):
                mapped = tuple(physical_to_compact[int(qubit)] for qubit in qubits)
                # Compose the calibrated channel exactly, then compress it to a
                # single Kraus instruction. QuantumError.power expands the
                # backend mixture combinatorially although the channel is small.
                if integer_scale == 1:
                    scaled_error = error
                else:
                    scaled_channel = SuperOp(error).power(integer_scale)
                    scaled_error = kraus_error(Kraus(scaled_channel).data)
                model.add_quantum_error(scaled_error, instruction, mapped)
    return model


def _compact_circuit_and_mapping(transpiled_circuit) -> tuple[QuantumCircuit, dict[str, object]]:
    measured_physical_by_logical: dict[int, int] = {}
    used: set[int] = set()
    for item in transpiled_circuit.data:
        op_name = item.operation.name
        q_indices = [transpiled_circuit.find_bit(qubit).index for qubit in item.qubits]
        if op_name == "measure":
            clbit = transpiled_circuit.find_bit(item.clbits[0]).index
            measured_physical_by_logical[int(clbit)] = int(q_indices[0])
            used.add(int(q_indices[0]))
        elif op_name != "barrier":
            used.update(int(idx) for idx in q_indices)
    if sorted(measured_physical_by_logical) != list(range(10)):
        raise RuntimeError(f"unexpected measurement map: {measured_physical_by_logical}")
    sorted_used = sorted(used)
    physical_to_compact = {physical: idx for idx, physical in enumerate(sorted_used)}
    compact = QuantumCircuit(len(sorted_used))
    compact.global_phase = transpiled_circuit.global_phase
    for item in transpiled_circuit.data:
        op = item.operation
        if op.name in {"measure", "barrier"}:
            continue
        q_indices = [physical_to_compact[transpiled_circuit.find_bit(q).index] for q in item.qubits]
        compact.append(op.copy(), q_indices, [])
    measured_compact_by_logical = [
        physical_to_compact[measured_physical_by_logical[logical]] for logical in range(10)
    ]
    return compact, {
        "used_physical_qubits": sorted_used,
        "physical_to_compact": physical_to_compact,
        "measured_physical_by_logical": [
            measured_physical_by_logical[logical] for logical in range(10)
        ],
        "measured_compact_by_logical": measured_compact_by_logical,
    }


def _logical_marginal_from_compact(
    compact_probs: np.ndarray,
    measured_compact_by_logical: list[int],
) -> np.ndarray:
    logical = np.zeros(2 ** len(measured_compact_by_logical), dtype=float)
    for state, probability in enumerate(np.asarray(compact_probs, dtype=float)):
        logical_state = 0
        for logical_idx, compact_idx in enumerate(measured_compact_by_logical):
            logical_state |= ((state >> compact_idx) & 1) << logical_idx
        logical[logical_state] += float(probability)
    total = logical.sum()
    if total <= 0.0:
        raise RuntimeError("empty logical probability distribution")
    return logical / total


def _readout_matrix(full_noise_model: NoiseModel, physical_qubit: int) -> np.ndarray:
    error = full_noise_model._local_readout_errors[(int(physical_qubit),)]
    return np.asarray(error.probabilities, dtype=float).T


def _probability_array_for_cell(
    instance_id: str,
    backend,
    full_noise_model: NoiseModel,
) -> CellData:
    graph = maxcut_graph_for_instance(instance_id, num_qubits=10, degree=3)
    landscape = landscape_for_instance(
        instance_id,
        candidate_count=CANDIDATE_COUNT,
        depth=DEPTH,
        num_qubits=10,
        graph_degree=3,
        local_radius=0.16,
        search_radius=0.55,
        search_count=64,
    )
    graph_edges = tuple((int(u), int(v)) for u, v in sorted(graph.edges()))
    values_by_state = -maxcut_values_for_graph(graph)
    raw_gate_probs = np.empty((len(ZNE_LAMBDAS), CANDIDATE_COUNT, 2**10), dtype=float)
    observed_probs = np.empty_like(raw_gate_probs)
    mappings: dict[str, object] | None = None
    readout_matrices: np.ndarray | None = None

    compact_by_candidate = []
    mapping_by_candidate = []
    expected_initial_layout = list(P004_FROZEN_INITIAL_LAYOUT) if instance_id == "P004" else None
    fixed_initial_layout = None
    for candidate_idx, angles in enumerate(landscape.angles):
        measured = qaoa_maxcut_circuit(
            graph,
            depth=DEPTH,
            gammas=angles[:DEPTH],
            betas=angles[DEPTH:],
            measure=True,
        )
        transpiled = transpile(
            measured,
            target=backend.target,
            optimization_level=1,
            seed_transpiler=SEED_TRANSPILE,
        )
        compact, this_mapping = _compact_circuit_and_mapping(transpiled)
        initial_virtual_to_physical = [
            int(transpiled.layout.initial_layout[measured.qubits[logical]])
            for logical in range(10)
        ]
        if fixed_initial_layout is None:
            if expected_initial_layout is not None and initial_virtual_to_physical != expected_initial_layout:
                raise RuntimeError(
                    f"{instance_id}: auto-selected initial layout differs from sealed mapping"
                )
            fixed_initial_layout = initial_virtual_to_physical
        elif initial_virtual_to_physical != fixed_initial_layout:
            raise RuntimeError(f"{instance_id}: candidate-dependent initial layout")
        this_mapping["initial_virtual_to_physical"] = initial_virtual_to_physical
        this_mapping["final_measured_physical_by_logical"] = list(
            this_mapping["measured_physical_by_logical"]
        )
        compact_by_candidate.append(compact)
        mapping_by_candidate.append(this_mapping)
        if mappings is None:
            mappings = dict(this_mapping)
            mappings.update(
                {
                    "transpiled_depth": int(transpiled.depth()),
                    "transpiled_size": int(transpiled.size()),
                    "transpiled_ops": {
                        key: int(value) for key, value in transpiled.count_ops().items()
                    },
                    "swap_count": int(transpiled.count_ops().get("swap", 0)),
                }
            )
            readout_matrices = np.asarray(
                [
                    _readout_matrix(full_noise_model, physical)
                    for physical in mappings["measured_physical_by_logical"]
                ],
                dtype=float,
            )
        elif (
            this_mapping["measured_physical_by_logical"] != mappings["measured_physical_by_logical"]
            or this_mapping["initial_virtual_to_physical"] != mappings["initial_virtual_to_physical"]
        ):
            raise RuntimeError(f"{instance_id}: candidate-dependent transpiler mapping")

    reference_compact_mapping = mapping_by_candidate[0]["physical_to_compact"]
    for candidate_idx, this_mapping in enumerate(mapping_by_candidate[1:], start=1):
        if this_mapping["physical_to_compact"] != reference_compact_mapping:
            raise RuntimeError(
                f"{instance_id}: candidate-dependent compact mapping at candidate {candidate_idx}"
            )

    for scale_idx, scale in enumerate(ZNE_LAMBDAS):
        print(f"{instance_id}: probability scale {scale:g}", flush=True)
        reduced = _scaled_reduced_noise_model(
            full_noise_model,
            reference_compact_mapping,
            scale=scale,
        )
        # Reuse one simulator per scale. Creating one AerSimulator per candidate
        # retains native density-matrix workspaces and causes pathological paging.
        simulator = AerSimulator(
            method="density_matrix",
            noise_model=reduced,
            max_parallel_experiments=1,
            max_parallel_threads=AER_MAX_PARALLEL_THREADS,
        )
        scale_probs = []
        for candidate_idx, compact_base in enumerate(compact_by_candidate):
            this_mapping = mapping_by_candidate[candidate_idx]
            compact = compact_base.copy()
            compact.save_probabilities_dict()
            result = simulator.run(compact).result()
            compact_arr = np.zeros(2 ** compact.num_qubits, dtype=float)
            for key, probability in result.data(0)["probabilities"].items():
                compact_arr[_state_index(key)] = float(probability)
            logical_probs = _logical_marginal_from_compact(
                compact_arr / compact_arr.sum(),
                this_mapping["measured_compact_by_logical"],
            )
            scale_probs.append(logical_probs)
            raw_gate_probs[scale_idx, candidate_idx] = logical_probs
            observed_probs[scale_idx, candidate_idx] = apply_tensor_confusion(
                logical_probs,
                readout_matrices,
            )
            if (candidate_idx + 1) % 5 == 0:
                print(
                    f"{instance_id}: scale {scale:g} candidates {candidate_idx + 1}/{CANDIDATE_COUNT}",
                    flush=True,
                )
        if len(scale_probs) != CANDIDATE_COUNT:
            raise RuntimeError(f"{instance_id}: incomplete probability array for scale {scale}")

    if mappings is None or readout_matrices is None:
        raise RuntimeError(f"{instance_id}: no mapping produced")
    mappings["virtual_to_physical"] = mappings["initial_virtual_to_physical"]
    return CellData(
        instance_id=instance_id,
        graph_edges=graph_edges,
        x_star=int(landscape.x_star),
        ideal_values=np.asarray(landscape.ideal_values, dtype=float),
        values_by_state=values_by_state,
        noisy_observed_probs=observed_probs,
        raw_gate_probs=raw_gate_probs,
        readout_matrices=readout_matrices,
        mappings=mappings,
    )


def _sample_expectation(
    probabilities: np.ndarray,
    values_by_state: np.ndarray,
    *,
    shots: int,
    instance_id: str,
    method: str,
    budget: int,
    replicate_id: int,
    stream: str,
) -> float:
    rng = make_rng(
        instance_id=instance_id,
        method=method,
        budget=int(budget),
        replicate_id=int(replicate_id),
        stream=stream,
    )
    counts = rng.multinomial(int(shots), np.asarray(probabilities, dtype=float))
    return float(np.dot(counts / float(shots), values_by_state))


def _sample_rem_expectation(
    cell: CellData,
    candidate_idx: int,
    *,
    budget: int,
    replicate_id: int,
) -> float:
    split = rem_budget_split(B_nominal=int(budget), f_calib=REM_F_CALIB)
    rng = make_rng(
        instance_id=cell.instance_id,
        method="Raw+REM",
        budget=int(budget),
        replicate_id=int(replicate_id),
        stream="rem_eval_counts",
    )
    observed_counts = rng.multinomial(
        int(split.C_eval),
        cell.noisy_observed_probs[0, candidate_idx],
    )
    observed = observed_counts / float(split.C_eval)
    calibration = simulate_calibration_counts(
        cell.readout_matrices,
        calibration_shots=int(split.calibration_shots),
        instance_id=cell.instance_id,
        budget=int(budget),
        replicate_id=int(replicate_id),
    )
    estimated = confusion_matrices_from_calibration(calibration)
    corrected = correct_probabilities_tensored(observed, estimated)
    return float(np.dot(corrected, cell.values_by_state))


def _primitive_samples(
    cell: CellData,
    budgets: tuple[int, ...],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    raw = np.empty((REPLICATES, CANDIDATE_COUNT, len(budgets)), dtype=float)
    primitive = np.empty((REPLICATES, len(ZNE_LAMBDAS), CANDIDATE_COUNT, len(budgets)), dtype=float)
    rem = np.empty((REPLICATES, CANDIDATE_COUNT, len(budgets)), dtype=float)
    for budget_idx, budget in enumerate(budgets):
        per_scale_shots = max(1, int(budget) // len(ZNE_LAMBDAS))
        for replicate_id in range(REPLICATES):
            for candidate_idx in range(CANDIDATE_COUNT):
                raw[replicate_id, candidate_idx, budget_idx] = _sample_expectation(
                    cell.noisy_observed_probs[0, candidate_idx],
                    cell.values_by_state,
                    shots=int(budget),
                    instance_id=cell.instance_id,
                    method="Raw",
                    budget=int(budget),
                    replicate_id=replicate_id * CANDIDATE_COUNT + candidate_idx,
                    stream="derisk_multinomial",
                )
                rem[replicate_id, candidate_idx, budget_idx] = _sample_rem_expectation(
                    cell,
                    candidate_idx,
                    budget=int(budget),
                    replicate_id=replicate_id * CANDIDATE_COUNT + candidate_idx,
                )
            for scale_idx, scale in enumerate(ZNE_LAMBDAS):
                for candidate_idx in range(CANDIDATE_COUNT):
                    primitive[replicate_id, scale_idx, candidate_idx, budget_idx] = _sample_expectation(
                        cell.noisy_observed_probs[scale_idx, candidate_idx],
                        cell.values_by_state,
                        shots=per_scale_shots,
                        instance_id=cell.instance_id,
                        method="ZNE",
                        budget=int(budget),
                        replicate_id=replicate_id * CANDIDATE_COUNT + candidate_idx,
                        stream=f"derisk_multinomial_scale_{scale:g}",
                    )
    return raw, primitive, rem


def _method_samples_for_budget(
    cell: CellData,
    raw: np.ndarray,
    primitive: np.ndarray,
    rem: np.ndarray,
    budget_idx: int,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], dict[str, object]]:
    estimates = primitive[:, :, :, budget_idx]
    raw_estimates = raw[:, :, budget_idx]
    competitors = [idx for idx in range(CANDIDATE_COUNT) if idx != cell.x_star]
    primitive_gaps = estimates[:, :, competitors] - estimates[:, :, [cell.x_star]]
    acc_coeffs = accuracy_zne_coeffs(ZNE_LAMBDAS, p=ZNE_ORDER)
    true_mu = cell.ideal_values[competitors] - cell.ideal_values[cell.x_star]
    mu_lower = np.maximum(true_mu, DECISION_ZNE_MU_FLOOR)
    q_list = [_covariance(primitive_gaps[:, :, gap_idx], shrinkage=False) for gap_idx in range(len(competitors))]
    A, rho = richardson_constraints(ZNE_LAMBDAS, p=ZNE_ORDER)
    dec_coeffs = decision_optimal_zne_coeffs(q_list, mu_lower, A, rho)

    raw_gate_means = np.einsum("ck,k->c", cell.noisy_observed_probs[0], cell.values_by_state)
    cdr_fit = fit_linear_cdr(raw_gate_means, cell.ideal_values)

    objective = {
        "Raw": raw_estimates,
        "Raw+REM": rem[:, :, budget_idx],
        "Accuracy-ZNE": np.einsum("s,rsc->rc", acc_coeffs, estimates),
        "Decision-ZNE": np.einsum("s,rsc->rc", dec_coeffs, estimates),
        "CDR": cdr_fit.a * raw_estimates + cdr_fit.b,
    }
    gaps = {
        method: values[:, competitors] - values[:, [cell.x_star]]
        for method, values in objective.items()
    }
    metadata = {
        "Accuracy-ZNE_coefficients": [float(x) for x in acc_coeffs],
        "Decision-ZNE_coefficients": [float(x) for x in dec_coeffs],
        "CDR_fit": {"a": float(cdr_fit.a), "b": float(cdr_fit.b)},
    }
    return objective, gaps, metadata


def _mse_by_method(objective: dict[str, np.ndarray], ideal_values: np.ndarray) -> dict[str, float]:
    return {
        method: float(np.mean((values - ideal_values[None, :]) ** 2))
        for method, values in objective.items()
    }


def _gri_by_method(gaps: dict[str, np.ndarray], *, diagonal: bool = False) -> dict[str, float]:
    out = {}
    for method, samples in gaps.items():
        arr = np.asarray(samples, dtype=float)
        mu = np.mean(arr, axis=0)
        sigma = _covariance(arr, shrinkage=USE_LEDOIT_WOLF)
        if diagonal:
            sigma = np.diag(np.diag(sigma))
        out[method] = gri_risk(mu, sigma, B=1.0)
    return out


def _analyze_cell(cell: CellData, budgets: tuple[int, ...]) -> tuple[list[dict[str, object]], dict[str, object]]:
    raise RuntimeError("Historical fit/select/test reuse is disabled in v20. Run run_fakekolkata_v20.py for independent evaluation.")
    raw, primitive, rem = _primitive_samples(cell, budgets)
    rows: list[dict[str, object]] = []
    per_budget_metadata = {}
    cdr_config = load_cdr_config()
    cdr_training = cdr_config["training_set"]
    cdr_cost = cdr_training_ledger_row(
        training_set_size=int(cdr_training["training_set_size"]),
        shots_per_training_circuit=int(cdr_training["shots_per_training_circuit"]),
        task="fakebackend_derisk_affine_control",
    )
    for budget_idx, budget in enumerate(budgets):
        print(f"{cell.instance_id}: analyze budget {budget}", flush=True)
        objective, gaps, metadata = _method_samples_for_budget(
            cell,
            raw,
            primitive,
            rem,
            budget_idx,
        )
        per_budget_metadata[str(budget)] = metadata
        mse_values = _mse_by_method(objective, cell.ideal_values)
        gri_full = _gri_by_method(gaps, diagonal=False)
        gri_diag = _gri_by_method(gaps, diagonal=True)
        mse_method = mse_selector(mse_values)
        da_method = da_selector(gri_full, gri_valid=True)
        diag_da_method = da_selector(gri_diag, gri_valid=True)
        paired = paired_outcome_counts(gaps[mse_method], gaps[da_method])
        rem_split = rem_budget_split(B_nominal=int(budget), f_calib=REM_F_CALIB)
        zne_per_scale = int(budget) // len(ZNE_LAMBDAS)
        row = {
            "cell": cell.instance_id,
            "budget": int(budget),
            "DA_selected_method": da_method,
            "MSE_selected_method": mse_method,
            "DA_selected_gri": float(gri_full[da_method]),
            "MSE_selected_mse": float(mse_values[mse_method]),
            "failure_rate_DA": empirical_decision_failure_rate(gaps[da_method]),
            "failure_rate_MSE": empirical_decision_failure_rate(gaps[mse_method]),
            "failure_rate_Raw": empirical_decision_failure_rate(gaps["Raw"]),
            "failure_rate_Raw_REM": empirical_decision_failure_rate(gaps["Raw+REM"]),
            "failure_rate_Accuracy_ZNE": empirical_decision_failure_rate(gaps["Accuracy-ZNE"]),
            "failure_rate_Decision_ZNE": empirical_decision_failure_rate(gaps["Decision-ZNE"]),
            "failure_rate_CDR": empirical_decision_failure_rate(gaps["CDR"]),
            "both_fail": paired["both_fail"],
            "both_ok": paired["both_ok"],
            "b_DA_better": paired["b"],
            "c_DA_worse": paired["c"],
            "paired_n": paired["paired_n"],
            "observed_rel_reduction": paired["observed_rel_reduction"],
            "primary_diff_DA_minus_MSE": float(
                empirical_decision_failure_rate(gaps[da_method])
                - empirical_decision_failure_rate(gaps[mse_method])
            ),
            "selector_full": da_method,
            "selector_diagonal": diag_da_method,
            "selector_changed_full_vs_diagonal": bool(da_method != diag_da_method),
            "gri_raw_full": float(gri_full["Raw"]),
            "gri_raw_diagonal": float(gri_diag["Raw"]),
            "gri_full_by_method_json": json.dumps(gri_full, sort_keys=True),
            "gri_diagonal_by_method_json": json.dumps(gri_diag, sort_keys=True),
            "mse_by_method_json": json.dumps(mse_values, sort_keys=True),
            "shots_Raw_eval": int(budget),
            "shots_ZNE_per_scale": zne_per_scale,
            "shots_ZNE_total": zne_per_scale * len(ZNE_LAMBDAS),
            "shots_REM_eval": int(rem_split.C_eval),
            "shots_REM_calib": int(rem_split.two_calib),
            "shots_REM_total": int(rem_split.C_eval + rem_split.two_calib),
            "shots_CDR_eval": int(budget),
            "shots_CDR_train_reported_separately": int(cdr_cost["C_train"]),
        }
        rows.append(row)
    return rows, {
        "raw_shape": list(raw.shape),
        "primitive_shape": list(primitive.shape),
        "rem_shape": list(rem.shape),
        "zne_shots_per_scale_by_budget": {
            str(budget): int(budget) // len(ZNE_LAMBDAS) for budget in budgets
        },
        "cdr_cost": cdr_cost,
        "cdr_cost_note": (
            "CDR shares Raw evaluation shots as the frozen affine control; "
            "non-amortized C_train is reported separately and is not used to claim a matched-cost advantage."
        ),
        "per_budget": per_budget_metadata,
    }


def _determinism_check(cell: CellData) -> dict[str, object]:
    left = _primitive_samples(cell, (B_STAR,))
    right = _primitive_samples(cell, (B_STAR,))
    raw_equal = bool(np.array_equal(left[0], right[0]))
    primitive_equal = bool(np.array_equal(left[1], right[1]))
    rem_equal = bool(np.array_equal(left[2], right[2]))
    if not (raw_equal and primitive_equal and rem_equal):
        raise RuntimeError(f"determinism check failed for {cell.instance_id} B={B_STAR}")
    return {
        "cell": cell.instance_id,
        "budget": B_STAR,
        "raw_equal": raw_equal,
        "primitive_equal": primitive_equal,
        "rem_equal": rem_equal,
    }


def _summaries(table: pd.DataFrame) -> dict[str, object]:
    p004 = table[table["cell"] == "P004"].copy()
    primary_row = p004[p004["budget"] == B_STAR].iloc[0].to_dict()
    auc_da = float(p004["failure_rate_DA"].mean())
    auc_mse = float(p004["failure_rate_MSE"].mean())
    auc_raw = float(p004["failure_rate_Raw"].mean())
    qualitative_gate = bool((table["DA_selected_method"] != "Raw").any())
    primary_positive = bool(float(primary_row["failure_rate_DA"]) < float(primary_row["failure_rate_MSE"]))
    signal = bool(primary_positive and qualitative_gate)
    raw_saturated = bool((table["failure_rate_Raw"] >= 0.95).all())
    d1_changed_rows = int(table["selector_changed_full_vs_diagonal"].sum())
    return {
        "primary": {
            "cell": "P004",
            "budget": B_STAR,
            "DA_selected_method": primary_row["DA_selected_method"],
            "MSE_selected_method": primary_row["MSE_selected_method"],
            "failure_rate_DA": float(primary_row["failure_rate_DA"]),
            "failure_rate_MSE": float(primary_row["failure_rate_MSE"]),
            "diff_DA_minus_MSE": float(primary_row["primary_diff_DA_minus_MSE"]),
            "observed_rel_reduction": float(primary_row["observed_rel_reduction"]),
            "b_DA_better": int(primary_row["b_DA_better"]),
            "c_DA_worse": int(primary_row["c_DA_worse"]),
            "paired_n": int(primary_row["paired_n"]),
        },
        "secondary_auc_p004": {
            "failure_auc_DA": auc_da,
            "failure_auc_MSE": auc_mse,
            "failure_auc_Raw": auc_raw,
            "diff_auc_DA_minus_MSE": auc_da - auc_mse,
        },
        "mechanism_D1": {
            "selector_changed_rows": d1_changed_rows,
            "total_rows": int(len(table)),
            "any_selector_changed": bool(d1_changed_rows > 0),
        },
        "qualitative_gate": {
            "DA_selects_non_raw_any_in_band_cell": qualitative_gate,
            "rows_DA_non_raw": int((table["DA_selected_method"] != "Raw").sum()),
        },
        "signal_for_go": signal,
        "raw_saturation_all_rows": raw_saturated,
        "framing": (
            "inconclusive, regime too hard"
            if raw_saturated
            else ("signal under this backend/menu/budget regime" if signal else "no signal under this backend/menu/budget regime")
        ),
    }


def _markdown_table(frame: pd.DataFrame) -> str:
    """Render the small report table without pandas' optional tabulate dependency."""

    def cell(value: object) -> str:
        if isinstance(value, (float, np.floating)):
            return f"{float(value):.6g}"
        return str(value)

    headers = [str(column) for column in frame.columns]
    rows = [[cell(value) for value in row] for row in frame.itertuples(index=False, name=None)]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def _write_outputs(
    *,
    rows: list[dict[str, object]],
    ordering_gates: list[dict[str, object]],
    mappings: dict[str, object],
    determinism: dict[str, object],
    metadata: dict[str, object],
    duration_seconds: float,
) -> dict[str, object]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame(rows)
    table = table.sort_values(["cell", "budget"]).reset_index(drop=True)
    summaries = _summaries(table)
    table.to_csv(OUTPUT_DIR / "per_cell_budget_table.csv", index=False)
    result = {
        "status": "completed",
        "note": "calibrated fake-backend stress test, NOT hardware",
        "pre_registration": {
            "file": "DERISK_FAKEBACKEND_v1.md",
            "sha256": "6210C6F1...",
        },
        "backend": "FakeKolkataV2",
        "cells": list(CELLS),
        "budgets": list(BUDGETS),
        "replicates": REPLICATES,
        "method_menu": list(METHODS),
        "budget_accounting": {
            "Raw": "C_eval=B",
            "Accuracy-ZNE": "three scales with floor(B/3) shots each",
            "Decision-ZNE": "three scales with floor(B/3) shots each",
            "Raw+REM": "matched_total: C_calib=round(0.2*B), C_eval=B-C_calib",
            "CDR": (
                "C_eval=B as affine control; non-amortized C_train=24576 is reported "
                "separately and is not used to claim a matched-cost advantage"
            ),
        },
        "ordering_gates": ordering_gates,
        "mappings": mappings,
        "determinism_check": determinism,
        "summaries": summaries,
        "metadata": metadata,
        "duration_seconds": float(duration_seconds),
    }
    (OUTPUT_DIR / "derisk_result.json").write_text(json.dumps(result, indent=2, sort_keys=True))
    lines = [
        "# FakeBackend de-risk result",
        "",
        "**Scope:** calibrated fake-backend stress test, NOT hardware.",
        "",
        "## Ordering gate",
    ]
    for gate in ordering_gates:
        lines.append(
            f"- {gate['instance_id']}: PASS, abs_error={gate['abs_error']:.3e}, "
            f"tol={gate['tolerance']:.1e}"
        )
    lines += [
        "",
        "## Mappings",
    ]
    for cell, mapping in mappings.items():
        lines.append(
            f"- {cell}: virtual_to_physical={mapping['virtual_to_physical']}, "
            f"final_measurement={mapping['final_measured_physical_by_logical']}, "
            f"depth={mapping['transpiled_depth']}, size={mapping['transpiled_size']}, "
            f"swap_count={mapping['swap_count']}"
        )
    lines += [
        "",
        "## Budget accounting",
        "- Raw: `C_eval=B`.",
        "- Accuracy-ZNE / Decision-ZNE: three scales with `floor(B/3)` shots each.",
        "- Raw+REM: matched-total split with `f_calib=0.2`; calibration is paid from `B`.",
        "- CDR: shares Raw evaluation shots; non-amortized `C_train=24576` is reported separately, "
        "so no matched-cost CDR advantage is claimed.",
    ]
    primary = summaries["primary"]
    secondary = summaries["secondary_auc_p004"]
    d1 = summaries["mechanism_D1"]
    gate = summaries["qualitative_gate"]
    lines += [
        "",
        "## Primary endpoint",
        (
            f"P004, B*=512: DA={primary['DA_selected_method']} failure={primary['failure_rate_DA']:.3f}; "
            f"MSE={primary['MSE_selected_method']} failure={primary['failure_rate_MSE']:.3f}; "
            f"DA-MSE={primary['diff_DA_minus_MSE']:.3f}; "
            f"rel_reduction={primary['observed_rel_reduction']:.3f}; "
            f"b={primary['b_DA_better']}, c={primary['c_DA_worse']}, n={primary['paired_n']}."
        ),
        "",
        "## Secondary endpoint",
        (
            f"P004 budget-band mean failure: DA={secondary['failure_auc_DA']:.3f}, "
            f"MSE={secondary['failure_auc_MSE']:.3f}, Raw={secondary['failure_auc_Raw']:.3f}, "
            f"DA-MSE={secondary['diff_auc_DA_minus_MSE']:.3f}."
        ),
        "",
        "## D1 and qualitative gate",
        f"- Full-vs-diagonal selector changed in {d1['selector_changed_rows']}/{d1['total_rows']} rows.",
        f"- DA selected a non-Raw method in {gate['rows_DA_non_raw']} rows.",
        "",
        "## Signal",
        f"- SIGNAL_FOR_GO: {'YES' if summaries['signal_for_go'] else 'NO'}",
        f"- Framing: {summaries['framing']}.",
        "",
        "## Panel",
        _markdown_table(table[
            [
                "cell",
                "budget",
                "DA_selected_method",
                "MSE_selected_method",
                "failure_rate_DA",
                "failure_rate_MSE",
                "failure_rate_Raw",
                "observed_rel_reduction",
                "selector_changed_full_vs_diagonal",
            ]
        ]),
        "",
        f"Duration seconds: {duration_seconds:.1f}",
    ]
    (OUTPUT_DIR / "derisk_result.md").write_text("\n".join(lines) + "\n")
    return result


def run() -> dict[str, object]:
    start = time.perf_counter()
    backend = FakeKolkataV2()
    full_noise_model = NoiseModel.from_backend(backend)
    ordering_gates = []
    cell_data: dict[str, CellData] = {}
    mappings: dict[str, object] = {}
    metadata: dict[str, object] = {}
    rows: list[dict[str, object]] = []

    for cell in CELLS:
        print(f"{cell}: ordering gate", flush=True)
        graph = maxcut_graph_for_instance(cell, num_qubits=10, degree=3)
        gate = _ordering_gate(cell, tuple((int(u), int(v)) for u, v in sorted(graph.edges())))
        ordering_gates.append(gate)
        print(f"{cell}: probabilities", flush=True)
        data = _probability_array_for_cell(cell, backend, full_noise_model)
        cell_data[cell] = data
        mappings[cell] = data.mappings
        print(f"{cell}: samples/selectors", flush=True)
        cell_rows, cell_meta = _analyze_cell(data, BUDGETS)
        rows.extend(cell_rows)
        metadata[cell] = cell_meta
    determinism = _determinism_check(cell_data["P004"])
    return _write_outputs(
        rows=rows,
        ordering_gates=ordering_gates,
        mappings=mappings,
        determinism=determinism,
        metadata=metadata,
        duration_seconds=time.perf_counter() - start,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    result = run()
    summary = result["summaries"]
    print("FAKEBACKEND DERISK COMPLETE")
    print(f"ordering_gates={[(g['instance_id'], g['passed']) for g in result['ordering_gates']]}")
    print(f"primary={summary['primary']}")
    print(f"secondary_auc_p004={summary['secondary_auc_p004']}")
    print(f"mechanism_D1={summary['mechanism_D1']}")
    print(f"qualitative_gate={summary['qualitative_gate']}")
    print(f"SIGNAL_FOR_GO={summary['signal_for_go']}")
    print(f"outputs={OUTPUT_DIR}")


if __name__ == "__main__":
    main()
