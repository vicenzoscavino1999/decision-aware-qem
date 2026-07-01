from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import networkx as nx
import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.transpiler import CouplingMap
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from daqem.candidates import build_candidate_landscape_for_graph, maxcut_values_for_graph
from daqem.gap_kernel import contrast_matrix, nearest_psd
from daqem.qaoa import maxcut_value, qaoa_maxcut_circuit
from daqem.qem_methods import accuracy_zne_coeffs, decision_optimal_zne_coeffs, richardson_constraints
from daqem.risk import gri_risk
from daqem.rng import make_rng


INSTANCE_ID = "HSMC001"
BACKEND_NAME = "ibm_marrakesh"
PHYSICAL_QUBITS = (14, 15, 19, 35)
OPTIMIZATION_LEVEL = 1
SEED_TRANSPILE = 260616
B_NOMINAL = 4096
SCALES_NOMINAL = (1.0, 2.0, 3.0)
METHODS = ("Raw", "Accuracy-ZNE", "DA-ZNE")
R_FINAL = 70
EPOCHS = 10
REPS_PER_EPOCH = 7
BOOTSTRAP_REPETITIONS = 10_000
RHO_C = 0.25
FROBENIUS_TOLERANCE = 0.20
CHARACTERIZATION_CIRCUITS_TARGET = 200
CHARACTERIZATION_SHOTS = 4096
ZNE_SHOTS_PER_SCALE = B_NOMINAL // 3
DECISION_ZNE_MU_FLOOR = 1e-6
TOTAL_QUANTUM_TIME_CAP_MINUTES = 50.0
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "dry_run_outputs"
TOKEN_PATH = Path(r"D:\paper fisica cuantica\apikey (1).json")
FEASIBILITY_RECORD = Path(__file__).resolve().parent / "feasibility_result.json"
ISA_OPTIMIZATION_LEVEL = 0
ISA_IMPLEMENTATION_NOTE = (
    "Main-run circuits are transpiled to ibm_marrakesh ISA with optimization_level=0 "
    "after folding/characterization construction. Level 0 preserves folded/self-inverse "
    "blocks; the level-1 feasibility transpilation was used only to derive the blind mapping."
)
LAMBDA2_RULE = (
    "partial folding from_left over two-qubit gates with ceil(n_2q/2) folds; "
    "ties such as 5/3 vs 7/3 are resolved upward. This is fixed before execution."
)
RZ_NOISE_CONVENTION = "rz_virtual_no_noise; learned sparse-PL rates are applied to physical sx/x and cz gate instances only."


@dataclass(frozen=True)
class CircuitTask:
    epoch: int
    replicate: int
    method: str
    candidate: int
    scale_nominal: float
    scale_effective: float
    shots: int
    circuit: QuantumCircuit


@dataclass(frozen=True)
class CharacterizationTask:
    index: int
    generator_index: int
    kind: str
    qubits: tuple[int, ...]
    length: int
    feature_value: float
    shots: int
    circuit: QuantumCircuit


@dataclass(frozen=True)
class RunConfig:
    r_final: int = R_FINAL
    epochs: int = EPOCHS
    reps_per_epoch: int = REPS_PER_EPOCH
    shots: int = B_NOMINAL
    bootstrap_repetitions: int = BOOTSTRAP_REPETITIONS
    output_dir: Path = DEFAULT_OUTPUT_DIR
    budget_cap_minutes: float = TOTAL_QUANTUM_TIME_CAP_MINUTES


class SamplerAdapter(Protocol):
    submitted_batches: int

    def run(self, tasks: list[Any], *, epoch: int) -> list[dict[str, int]]:
        ...


def microcell_graph() -> nx.Graph:
    graph = nx.Graph()
    graph.add_nodes_from(range(4))
    graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
    return graph


def microcell_landscape():
    return build_candidate_landscape_for_graph(
        INSTANCE_ID,
        microcell_graph(),
        candidate_count=4,
        depth=1,
        local_radius=0.16,
        search_radius=0.55,
        search_count=64,
    )


def remove_measurements(circuit: QuantumCircuit) -> QuantumCircuit:
    return circuit.remove_final_measurements(inplace=False)


def count_two_qubit_gates(circuit: QuantumCircuit) -> int:
    return int(sum(1 for inst in circuit.data if len(inst.qubits) == 2 and inst.operation.name != "barrier"))


def circuit_signature(circuit: QuantumCircuit) -> tuple[tuple[str, tuple[float, ...], tuple[int, ...]], ...]:
    rows = []
    for inst in circuit.data:
        qargs = tuple(circuit.find_bit(qubit).index for qubit in inst.qubits)
        params = tuple(round(float(param), 12) for param in inst.operation.params)
        rows.append((inst.operation.name, params, qargs))
    return tuple(rows)


def _feasibility_backend_record() -> dict[str, Any]:
    return json.loads(FEASIBILITY_RECORD.read_text(encoding="utf-8"))


def ibm_marrakesh_basis_gates() -> list[str]:
    return list(_feasibility_backend_record()["backend"]["basis_gates"])


def ibm_marrakesh_coupling_map() -> CouplingMap:
    edges = [tuple(int(x) for x in edge) for edge in _feasibility_backend_record()["backend"]["coupling_edges"]]
    return CouplingMap(edges)


def transpile_to_isa(circuit: QuantumCircuit, *, optimization_level: int = ISA_OPTIMIZATION_LEVEL) -> QuantumCircuit:
    return transpile(
        circuit,
        basis_gates=ibm_marrakesh_basis_gates(),
        coupling_map=ibm_marrakesh_coupling_map(),
        initial_layout=list(PHYSICAL_QUBITS),
        optimization_level=int(optimization_level),
        seed_transpiler=SEED_TRANSPILE,
    )


def cz_count(circuit: QuantumCircuit) -> int:
    return int(dict(circuit.count_ops()).get("cz", 0))


def measurement_physical_by_clbit(isa_circuit: QuantumCircuit) -> dict[int, int]:
    mapping: dict[int, int] = {}
    for inst in isa_circuit.data:
        if inst.operation.name != "measure":
            continue
        if len(inst.qubits) != 1 or len(inst.clbits) != 1:
            raise RuntimeError("unexpected multi-qubit measurement in ISA circuit")
        physical = isa_circuit.find_bit(inst.qubits[0]).index
        clbit = isa_circuit.find_bit(inst.clbits[0]).index
        mapping[int(clbit)] = int(physical)
    expected = {idx: physical for idx, physical in enumerate(PHYSICAL_QUBITS)}
    if mapping != expected:
        raise RuntimeError(f"ISA measurement/clbit mapping mismatch: expected {expected}, got {mapping}")
    return mapping


def compact_isa_circuit(isa_circuit: QuantumCircuit) -> QuantumCircuit:
    measurement_physical_by_clbit(isa_circuit)
    physical_to_compact = {physical: idx for idx, physical in enumerate(PHYSICAL_QUBITS)}
    compact = QuantumCircuit(4)
    compact.global_phase = isa_circuit.global_phase
    for inst in isa_circuit.data:
        name = inst.operation.name
        if name in {"measure", "barrier", "delay"}:
            continue
        physical_qargs = [isa_circuit.find_bit(qubit).index for qubit in inst.qubits]
        if not all(q in physical_to_compact for q in physical_qargs):
            raise RuntimeError(f"ISA operation uses non-selected physical qubit(s): {name} {physical_qargs}")
        compact_qargs = [physical_to_compact[q] for q in physical_qargs]
        compact.append(inst.operation.copy(), compact_qargs, [])
    compact.measure_all()
    return compact


def assert_isa_mapping(circuit: QuantumCircuit) -> None:
    measurement_physical_by_clbit(circuit)
    for inst in circuit.data:
        if inst.operation.name in {"measure", "barrier", "delay"}:
            continue
        physical_qargs = [circuit.find_bit(q).index for q in inst.qubits]
        if not all(q in PHYSICAL_QUBITS for q in physical_qargs):
            raise RuntimeError(f"ISA circuit touches non-frozen physical qubit(s): {physical_qargs}")


def _append_without_clbits(target: QuantumCircuit, source: QuantumCircuit, inverse: bool = False) -> None:
    instructions = list(source.data)
    if inverse:
        instructions = list(reversed(instructions))
    for inst in instructions:
        op = inst.operation.inverse() if inverse else inst.operation.copy()
        if op.name in {"measure", "barrier"}:
            continue
        qargs = [source.find_bit(qubit).index for qubit in inst.qubits]
        target.append(op, qargs, [])


def global_fold_lambda3(circuit: QuantumCircuit) -> tuple[QuantumCircuit, float]:
    base = remove_measurements(circuit)
    base_twoq = count_two_qubit_gates(base)
    folded = QuantumCircuit(base.num_qubits)
    _append_without_clbits(folded, base, inverse=False)
    folded.barrier(range(base.num_qubits))
    _append_without_clbits(folded, base, inverse=True)
    folded.barrier(range(base.num_qubits))
    _append_without_clbits(folded, base, inverse=False)
    folded.measure_all()
    effective = count_two_qubit_gates(folded) / max(base_twoq, 1)
    return folded, float(effective)


def partial_fold_lambda2_from_left(circuit: QuantumCircuit) -> tuple[QuantumCircuit, float]:
    base = remove_measurements(circuit)
    base_twoq = count_two_qubit_gates(base)
    folds_to_apply = int(math.ceil(base_twoq / 2.0))
    folded = QuantumCircuit(base.num_qubits)
    folded_twoq_seen = 0
    for inst in base.data:
        op = inst.operation.copy()
        if op.name == "barrier":
            continue
        qargs = [base.find_bit(qubit).index for qubit in inst.qubits]
        folded.append(op, qargs, [])
        if len(inst.qubits) == 2 and folded_twoq_seen < folds_to_apply:
            folded.barrier(*qargs)
            folded.append(inst.operation.inverse(), qargs, [])
            folded.barrier(*qargs)
            folded.append(inst.operation.copy(), qargs, [])
            folded_twoq_seen += 1
    folded.measure_all()
    effective = count_two_qubit_gates(folded) / max(base_twoq, 1)
    return folded, float(effective)


def folded_circuit_for_scale(circuit: QuantumCircuit, scale: float) -> tuple[QuantumCircuit, float]:
    if abs(float(scale) - 1.0) < 1e-12:
        return circuit.copy(), 1.0
    if abs(float(scale) - 2.0) < 1e-12:
        return partial_fold_lambda2_from_left(circuit)
    if abs(float(scale) - 3.0) < 1e-12:
        return global_fold_lambda3(circuit)
    raise ValueError(f"unsupported sealed scale {scale}")


def zne_coefficients_from_effective_scales(scales: tuple[float, float, float]) -> np.ndarray:
    return accuracy_zne_coeffs(np.asarray(scales, dtype=float), 1)


def primitive_shot_vector(method: str) -> np.ndarray:
    shots = np.zeros(12, dtype=float)
    per_scale = B_NOMINAL if method == "Raw" else ZNE_SHOTS_PER_SCALE
    for candidate in range(4):
        for scale_idx in range(3):
            shots[candidate * 3 + scale_idx] = float(per_scale)
    return shots


def method_maps(effective_scales: tuple[float, float, float], da_coeffs: np.ndarray | None = None) -> dict[str, np.ndarray]:
    n_candidates = 4
    n_scales = 3
    raw = np.zeros((n_candidates, n_candidates * n_scales), dtype=float)
    acc = np.zeros_like(raw)
    dec = np.zeros_like(raw)
    coeffs = zne_coefficients_from_effective_scales(effective_scales)
    decision_coeffs = np.asarray(da_coeffs if da_coeffs is not None else coeffs, dtype=float)
    for candidate in range(n_candidates):
        raw[candidate, candidate * n_scales] = 1.0
        for scale_idx, coeff in enumerate(coeffs):
            acc[candidate, candidate * n_scales + scale_idx] = float(coeff)
        for scale_idx, coeff in enumerate(decision_coeffs):
            dec[candidate, candidate * n_scales + scale_idx] = float(coeff)
    return {"Raw": raw, "Accuracy-ZNE": acc, "DA-ZNE": dec}


def build_candidate_circuits() -> list[QuantumCircuit]:
    graph = microcell_graph()
    landscape = microcell_landscape()
    circuits: list[QuantumCircuit] = []
    for angles in landscape.angles:
        circuits.append(
            qaoa_maxcut_circuit(
                graph,
                depth=1,
                gammas=np.asarray(angles[:1], dtype=float),
                betas=np.asarray(angles[1:], dtype=float),
                measure=True,
            )
        )
    return circuits


def isa_for_candidate_scale(circuit: QuantumCircuit, scale: float) -> tuple[QuantumCircuit, float]:
    folded, effective = folded_circuit_for_scale(circuit, scale)
    isa = transpile_to_isa(folded, optimization_level=ISA_OPTIMIZATION_LEVEL)
    assert_isa_mapping(isa)
    return isa, float(effective)


def assert_folded_isa_anti_cancellation(
    isa_by_scale: dict[float, QuantumCircuit],
    effective_by_scale: dict[float, float],
    *,
    tolerance: float = 1e-9,
) -> dict[str, float]:
    base_cz = cz_count(isa_by_scale[1.0])
    if base_cz <= 0:
        raise RuntimeError("anti-cancellation check requires a positive lambda=1 CZ count")
    ratios = {float(scale): cz_count(circuit) / float(base_cz) for scale, circuit in isa_by_scale.items()}
    if abs(ratios[2.0] - effective_by_scale[2.0]) > tolerance:
        raise RuntimeError(
            f"lambda=2 ISA CZ ratio was {ratios[2.0]} but effective scale is {effective_by_scale[2.0]}"
        )
    if abs(ratios[3.0] - 3.0) > tolerance:
        raise RuntimeError(f"lambda=3 ISA CZ ratio was {ratios[3.0]} but expected 3.0")
    return {"cz_lambda1": float(base_cz), "cz_ratio_lambda2": ratios[2.0], "cz_ratio_lambda3": ratios[3.0]}


def effective_scale_tuple() -> tuple[float, float, float]:
    base = build_candidate_circuits()[0]
    isa_by_scale: dict[float, QuantumCircuit] = {}
    effective_by_scale: dict[float, float] = {}
    for scale in SCALES_NOMINAL:
        isa, effective = isa_for_candidate_scale(base, scale)
        isa_by_scale[float(scale)] = isa
        effective_by_scale[float(scale)] = effective
    assert_folded_isa_anti_cancellation(isa_by_scale, effective_by_scale)
    return tuple(float(effective_by_scale[float(scale)]) for scale in SCALES_NOMINAL)


def shots_for_task(method: str, scale: float) -> int:
    del scale
    return B_NOMINAL if method == "Raw" else ZNE_SHOTS_PER_SCALE


def build_epoch_tasks(epoch: int, reps_per_epoch: int = REPS_PER_EPOCH) -> list[CircuitTask]:
    base_circuits = build_candidate_circuits()
    folded_by_candidate: dict[tuple[int, float], tuple[QuantumCircuit, float]] = {}
    for candidate, circuit in enumerate(base_circuits):
        isa_by_scale: dict[float, QuantumCircuit] = {}
        effective_by_scale: dict[float, float] = {}
        for scale in SCALES_NOMINAL:
            isa, effective = isa_for_candidate_scale(circuit, scale)
            isa_by_scale[float(scale)] = isa
            effective_by_scale[float(scale)] = effective
            folded_by_candidate[(candidate, scale)] = (isa, effective)
        assert_folded_isa_anti_cancellation(isa_by_scale, effective_by_scale)

    tasks: list[CircuitTask] = []
    methods = list(METHODS)
    for rep_local in range(reps_per_epoch):
        replicate = epoch * reps_per_epoch + rep_local
        rotation = (epoch + rep_local) % len(methods)
        method_order = methods[rotation:] + methods[:rotation]
        for method in method_order:
            scales = (1.0,) if method == "Raw" else SCALES_NOMINAL
            for candidate in range(4):
                for scale in scales:
                    circuit, effective = folded_by_candidate[(candidate, scale)]
                    tasks.append(
                        CircuitTask(
                            epoch=epoch,
                            replicate=replicate,
                            method=method,
                            candidate=candidate,
                            scale_nominal=float(scale),
                            scale_effective=float(effective),
                            shots=shots_for_task(method, scale),
                            circuit=circuit,
                        )
                    )
    return tasks


def all_epoch_tasks(config: RunConfig) -> list[list[CircuitTask]]:
    return [build_epoch_tasks(epoch, config.reps_per_epoch) for epoch in range(config.epochs)]


def maxcut_minimization_value_from_counts(counts: dict[str, int]) -> float:
    graph = microcell_graph()
    shots = sum(int(count) for count in counts.values())
    if shots <= 0:
        raise ValueError("empty counts")
    mean = sum(maxcut_value(bitstring, graph) * int(count) for bitstring, count in counts.items()) / shots
    return float(-mean)


def probabilities_to_counts(probabilities: np.ndarray, shots: int, *, width: int = 4) -> dict[str, int]:
    probs = np.asarray(probabilities, dtype=float)
    probs = np.maximum(probs, 0.0)
    probs = probs / probs.sum()
    raw = probs * int(shots)
    counts = np.floor(raw).astype(int)
    remainder = int(shots) - int(counts.sum())
    if remainder > 0:
        order = np.argsort(raw - counts)[::-1]
        counts[order[:remainder]] += 1
    return {format(idx, f"0{width}b"): int(c) for idx, c in enumerate(counts) if int(c) > 0}


def ordering_gate_end_to_end() -> dict[str, Any]:
    true_probs = np.arange(1, 17, dtype=float)
    true_probs = true_probs / true_probs.sum()
    p01 = np.array([0.01, 0.02, 0.015, 0.025])
    p10 = np.array([0.03, 0.01, 0.02, 0.015])
    observed = np.zeros_like(true_probs)
    for state, p in enumerate(true_probs):
        for observed_state in range(16):
            prob = 1.0
            for q in range(4):
                bit = (state >> q) & 1
                obs = (observed_state >> q) & 1
                if bit == 0:
                    prob *= (1.0 - p01[q]) if obs == 0 else p01[q]
                else:
                    prob *= p10[q] if obs == 0 else (1.0 - p10[q])
            observed[observed_state] += p * prob
    matrices = np.zeros((4, 2, 2), dtype=float)
    for q in range(4):
        matrices[q] = np.array([[1.0 - p01[q], p10[q]], [p01[q], 1.0 - p10[q]]])
    full = matrices[0]
    for q in range(1, 4):
        full = np.kron(matrices[q], full)
    corrected = np.linalg.solve(full, observed)
    corrected = np.maximum(corrected, 0.0)
    corrected = corrected / corrected.sum()
    shots = 1_000_000
    expected = maxcut_minimization_value_from_counts(probabilities_to_counts(true_probs, shots))
    recovered = maxcut_minimization_value_from_counts(probabilities_to_counts(corrected, shots))
    error = abs(expected - recovered)
    return {
        "expected_observable": expected,
        "recovered_observable": recovered,
        "abs_error": error,
        "tolerance": 1e-5,
        "passed": bool(error <= 1e-5),
    }


def _measure_bit(bitstring: str, qubit: int) -> int:
    clean = str(bitstring).replace(" ", "")
    return int(clean[::-1][int(qubit)])


def build_characterization_tasks() -> list[CharacterizationTask]:
    lengths = (1, 2, 3, 4, 6, 8, 12)
    generator_specs: list[tuple[str, tuple[int, ...]]] = [
        ("1q", (0,)),
        ("1q", (1,)),
        ("1q", (2,)),
        ("1q", (3,)),
        ("2q", (0, 1)),
        ("2q", (1, 2)),
        ("2q", (2, 3)),
    ]
    tasks: list[CharacterizationTask] = []
    index = 0
    for generator_index, (kind, qubits) in enumerate(generator_specs):
        for rep in range(29):
            length = int(lengths[rep % len(lengths)])
            qc = QuantumCircuit(4)
            if kind == "1q":
                (q,) = qubits
                qc.x(q)
                for _ in range(length):
                    qc.x(q)
                    qc.barrier(q)
                    qc.x(q)
                    qc.barrier(q)
            else:
                a, b = qubits
                qc.h(a)
                qc.h(b)
                for _ in range(length):
                    qc.cz(a, b)
                    qc.barrier(a, b)
                    qc.cz(a, b)
                    qc.barrier(a, b)
                qc.h(a)
                qc.h(b)
            qc.measure_all()
            isa = transpile_to_isa(qc, optimization_level=ISA_OPTIMIZATION_LEVEL)
            assert_isa_mapping(isa)
            expected_cz = 0 if kind == "1q" else 2 * length
            actual_cz = cz_count(isa)
            if actual_cz != expected_cz:
                raise RuntimeError(
                    f"characterization anti-cancellation check failed for generator {generator_index}: "
                    f"expected cz={expected_cz}, got cz={actual_cz}"
                )
            tasks.append(
                CharacterizationTask(
                    index=index,
                    generator_index=generator_index,
                    kind=kind,
                    qubits=tuple(int(q) for q in qubits),
                    length=length,
                    feature_value=float(2 * length),
                    shots=CHARACTERIZATION_SHOTS,
                    circuit=isa,
                )
            )
            index += 1
    return tasks


def characterization_rate_design(tasks: list[CharacterizationTask] | None = None) -> np.ndarray:
    tasks = build_characterization_tasks() if tasks is None else list(tasks)
    design = np.zeros((len(tasks), 7), dtype=float)
    for task in tasks:
        design[task.index, task.generator_index] = task.feature_value
    return design


def characterization_design(tasks: list[CharacterizationTask] | None = None) -> np.ndarray:
    tasks = build_characterization_tasks() if tasks is None else list(tasks)
    design = np.zeros((len(tasks), 14), dtype=float)
    for task in tasks:
        design[task.index, task.generator_index] = 1.0
        design[task.index, 7 + task.generator_index] = task.feature_value
    return design


def characterization_observations_from_counts(
    tasks: list[CharacterizationTask],
    counts_list: list[dict[str, int]],
) -> np.ndarray:
    observations = np.zeros(len(tasks), dtype=float)
    for task, counts in zip(tasks, counts_list, strict=True):
        shots = sum(int(v) for v in counts.values())
        if shots <= 0:
            raise ValueError("empty characterization counts")
        if task.kind == "1q":
            (q,) = task.qubits
            good = sum(int(v) for bitstring, v in counts.items() if _measure_bit(bitstring, q) == 1)
            signal = 2.0 * (good / shots) - 1.0
        else:
            a, b = task.qubits
            good = sum(
                int(v)
                for bitstring, v in counts.items()
                if _measure_bit(bitstring, a) == 0 and _measure_bit(bitstring, b) == 0
            )
            signal = (4.0 * (good / shots) - 1.0) / 3.0
        observations[task.index] = -math.log(max(float(signal), 1e-9))
    return observations


def split_characterization(design: np.ndarray, *, offset: int = 0, modulus: int = 5) -> tuple[np.ndarray, np.ndarray]:
    indices = np.arange(design.shape[0])
    heldout = indices[indices % int(modulus) == int(offset)]
    train = indices[indices % int(modulus) != int(offset)]
    return train, heldout


def learn_sparse_pl_rates(design: np.ndarray, observations: np.ndarray) -> np.ndarray:
    model = learn_sparse_pl_model(design, observations)
    return model["rates"]


def learn_sparse_pl_model(design: np.ndarray, observations: np.ndarray) -> dict[str, np.ndarray]:
    x = np.asarray(design, dtype=float)
    y = np.asarray(observations, dtype=float)
    params, *_ = np.linalg.lstsq(x, y, rcond=None)
    params = np.asarray(params, dtype=float)
    if x.shape[1] == 14:
        intercepts = params[:7]
        rates = np.maximum(params[7:], 0.0)
        full_params = np.concatenate([intercepts, rates])
    elif x.shape[1] == 7:
        intercepts = np.zeros(7, dtype=float)
        rates = np.maximum(params, 0.0)
        full_params = rates
    else:
        raise ValueError(f"unsupported sparse-PL design width {x.shape[1]}")
    return {"params": full_params, "intercepts": intercepts, "rates": rates}


def learn_sparse_pl_rates_no_intercept_test_only(design: np.ndarray, observations: np.ndarray) -> np.ndarray:
    rates, *_ = np.linalg.lstsq(np.asarray(design, dtype=float), np.asarray(observations, dtype=float), rcond=None)
    return np.maximum(np.asarray(rates, dtype=float), 0.0)


def support_f1(predicted: np.ndarray, truth: np.ndarray, threshold: float = 1e-8) -> float:
    pred = np.asarray(predicted) > threshold
    true = np.asarray(truth) > threshold
    tp = int(np.sum(pred & true))
    fp = int(np.sum(pred & ~true))
    fn = int(np.sum(~pred & true))
    if tp == fp == fn == 0:
        return 1.0
    return float(2 * tp / max(2 * tp + fp + fn, 1))


def gate_c1_metrics(
    design: np.ndarray,
    observations: np.ndarray,
    learned_model_or_rates: dict[str, np.ndarray] | np.ndarray,
) -> dict[str, Any]:
    if isinstance(learned_model_or_rates, dict):
        model = learned_model_or_rates
    else:
        rates = np.asarray(learned_model_or_rates, dtype=float)
        design_width = np.asarray(design, dtype=float).shape[1]
        params = np.concatenate([np.zeros(7, dtype=float), rates]) if design_width == 14 else rates
        model = {"params": params, "rates": rates, "intercepts": np.zeros(7, dtype=float)}
    _, heldout = split_characterization(design)
    y = np.asarray(observations, dtype=float)[heldout]
    pred = np.asarray(design, dtype=float)[heldout] @ np.asarray(model["params"], dtype=float)
    denom = max(float(np.linalg.norm(y)), 1e-12)
    gen_error = float(np.linalg.norm(pred - y) / denom)
    train_a, _ = split_characterization(design, offset=0, modulus=2)
    train_b, _ = split_characterization(design, offset=1, modulus=2)
    rates_a = learn_sparse_pl_model(np.asarray(design)[train_a], np.asarray(observations)[train_a])["rates"]
    rates_b = learn_sparse_pl_model(np.asarray(design)[train_b], np.asarray(observations)[train_b])["rates"]
    support = support_f1(rates_a, rates_b, threshold=1e-7)
    passed = bool(gen_error <= 0.20 and support >= 0.90)
    return {
        "heldout_relative_generalization_error": gen_error,
        "support_f1_stability": support,
        "passed": passed,
        "thresholds": {"gen_error_max": 0.20, "support_f1_min": 0.90},
    }


def synthetic_characterization_counts_test_only(
    true_rates: np.ndarray,
    *,
    shots: int = CHARACTERIZATION_SHOTS,
    tasks: list[CharacterizationTask] | None = None,
    intercepts: np.ndarray | None = None,
) -> tuple[list[CharacterizationTask], list[dict[str, int]]]:
    tasks = build_characterization_tasks() if tasks is None else list(tasks)
    rates = np.asarray(true_rates, dtype=float)
    offset = np.zeros(7, dtype=float) if intercepts is None else np.asarray(intercepts, dtype=float)
    counts_list: list[dict[str, int]] = []
    for task in tasks:
        decay = float(offset[task.generator_index]) + task.feature_value * float(rates[task.generator_index])
        signal = float(np.exp(-decay))
        if task.kind == "1q":
            p_good = (1.0 + signal) / 2.0
            q = task.qubits[0]
            good_state = 1 << q
            bad_state = 0
        else:
            p_good = (1.0 + 3.0 * signal) / 4.0
            good_state = 0
            a, b = task.qubits
            bad_state = (1 << a) | (1 << b)
        good = int(round(p_good * shots))
        good = min(max(good, 0), shots)
        counts = {
            format(good_state, "04b"): good,
            format(bad_state, "04b"): int(shots - good),
        }
        counts_list.append({k: v for k, v in counts.items() if v > 0})
    return tasks, counts_list


def sparse_pl_noise_model_from_rates(rates: np.ndarray) -> NoiseModel:
    rates = np.maximum(np.asarray(rates, dtype=float), 0.0)
    model = NoiseModel()
    for q in range(4):
        if rates[q] > 0:
            # RZ is virtual in the ISA path and is intentionally noiseless.
            model.add_quantum_error(depolarizing_error(min(float(rates[q]), 0.95), 1), ["sx", "x"], [q])
    for edge_idx, edge in enumerate(((0, 1), (1, 2), (2, 3))):
        rate = rates[4 + edge_idx]
        if rate > 0:
            model.add_quantum_error(depolarizing_error(min(float(rate), 0.95), 2), ["cz"], list(edge))
    return model


def noisy_probabilities(circuit: QuantumCircuit, noise_model: NoiseModel | None) -> np.ndarray:
    compact = compact_isa_circuit(circuit)
    bare = remove_measurements(compact)
    bare.save_probabilities()
    simulator = AerSimulator(method="density_matrix", noise_model=noise_model)
    data = simulator.run(bare).result().data(0)
    probs = np.asarray(data["probabilities"], dtype=float)
    return probs / probs.sum()


def primitive_variance_unit_from_rates(rates: np.ndarray) -> np.ndarray:
    noise_model = sparse_pl_noise_model_from_rates(rates)
    values = -maxcut_values_for_graph(microcell_graph())
    variances = np.zeros(12, dtype=float)
    idx = 0
    for circuit in build_candidate_circuits():
        for scale in SCALES_NOMINAL:
            isa, _ = isa_for_candidate_scale(circuit, scale)
            probs = noisy_probabilities(isa, noise_model)
            mean = float(np.dot(probs, values))
            second = float(np.dot(probs, values * values))
            variances[idx] = max(0.0, second - mean * mean)
            idx += 1
    return variances


def sigma_pred(cdev: np.ndarray, method_map: np.ndarray, L: np.ndarray) -> np.ndarray:
    return nearest_psd(L @ method_map @ cdev @ method_map.T @ L.T, jitter=1e-12)


def sigma_pred_from_primitive_variances(
    primitive_variance_unit: np.ndarray,
    method: str,
    method_map: np.ndarray,
    L: np.ndarray,
) -> np.ndarray:
    diag = np.asarray(primitive_variance_unit, dtype=float) / primitive_shot_vector(method)
    return sigma_pred(np.diag(diag), method_map, L)


def decision_zne_coefficients_from_prediction(
    primitive_variance_unit: np.ndarray,
    ideal_values: np.ndarray,
    effective_scales: tuple[float, float, float],
) -> np.ndarray:
    q_list = []
    shot = float(ZNE_SHOTS_PER_SCALE)
    for competitor in range(1, 4):
        diag = []
        for scale_idx in range(3):
            comp_idx = competitor * 3 + scale_idx
            ref_idx = scale_idx
            diag.append((primitive_variance_unit[comp_idx] + primitive_variance_unit[ref_idx]) / shot)
        q_list.append(np.diag(diag))
    true_mu = np.asarray(ideal_values[1:], dtype=float) - float(ideal_values[0])
    mu_lower = np.maximum(true_mu, DECISION_ZNE_MU_FLOOR)
    A, rho = richardson_constraints(np.asarray(effective_scales, dtype=float), 1)
    return decision_optimal_zne_coeffs(q_list, mu_lower, A, rho)


def primitive_vector_from_counts(tasks: list[CircuitTask], counts_list: list[dict[str, int]]) -> dict[int, np.ndarray]:
    values_by_rep: dict[int, np.ndarray] = {}
    for task, counts in zip(tasks, counts_list, strict=True):
        if task.method == "Raw" and abs(task.scale_nominal - 1.0) > 1e-12:
            continue
        arr = values_by_rep.setdefault(task.replicate, np.full(12, np.nan, dtype=float))
        scale_idx = SCALES_NOMINAL.index(float(task.scale_nominal))
        arr[task.candidate * 3 + scale_idx] = maxcut_minimization_value_from_counts(counts)
    return values_by_rep


def gap_vectors_for_epoch(tasks: list[CircuitTask], counts_list: list[dict[str, int]], maps: dict[str, np.ndarray], L: np.ndarray) -> dict[str, list[np.ndarray]]:
    by_method_rep: dict[tuple[str, int], np.ndarray] = {}
    for task, counts in zip(tasks, counts_list, strict=True):
        key = (task.method, task.replicate)
        arr = by_method_rep.setdefault(key, np.full(12, np.nan, dtype=float))
        scale_idx = SCALES_NOMINAL.index(float(task.scale_nominal))
        arr[task.candidate * 3 + scale_idx] = maxcut_minimization_value_from_counts(counts)
    out = {method: [] for method in METHODS}
    for (method, _rep), primitive in sorted(by_method_rep.items()):
        if method == "Raw":
            for candidate in range(4):
                primitive[candidate * 3 + 1] = primitive[candidate * 3]
                primitive[candidate * 3 + 2] = primitive[candidate * 3]
        if np.any(~np.isfinite(primitive)):
            raise RuntimeError(f"incomplete primitive vector for {method}")
        values = maps[method] @ primitive
        out[method].append(L @ values)
    return out


def covariance_from_gap_vectors(vectors: list[np.ndarray]) -> np.ndarray:
    arr = np.asarray(vectors, dtype=float)
    if arr.shape[0] < 2:
        return nearest_psd(np.zeros((arr.shape[1], arr.shape[1])), jitter=1e-12)
    return nearest_psd(np.cov(arr, rowvar=False, ddof=1), jitter=1e-12)


def gri_score(mu: np.ndarray, sigma: np.ndarray) -> float:
    return float(gri_risk(np.asarray(mu, dtype=float), nearest_psd(sigma, jitter=1e-12), B=1.0))


def gri_sigma_gradient(mu: np.ndarray, sigma: np.ndarray, *, rel_step: float = 1e-4) -> np.ndarray:
    sigma = nearest_psd(np.asarray(sigma, dtype=float), jitter=1e-12)
    grad = np.zeros_like(sigma)
    n = sigma.shape[0]
    for i in range(n):
        for j in range(i, n):
            step = rel_step * max(1.0, abs(float(sigma[i, j])))
            direction = np.zeros_like(sigma)
            direction[i, j] = step
            direction[j, i] = step
            plus = gri_score(mu, sigma + direction)
            minus = gri_score(mu, sigma - direction)
            value = (plus - minus) / (2.0 * step)
            grad[i, j] = value
            grad[j, i] = value
    return grad


def endpoint_projected_ranking(
    *,
    mu: np.ndarray,
    sigma_pred_by_method: dict[str, np.ndarray],
    sigma_hat_by_method: dict[str, np.ndarray],
    bootstrap_sigmas: list[dict[str, np.ndarray]] | None = None,
) -> dict[str, Any]:
    risks: dict[str, float] = {}
    gradients: dict[str, np.ndarray] = {}
    for method, sigma in sigma_pred_by_method.items():
        risks[method] = gri_score(mu, sigma)
        gradients[method] = gri_sigma_gradient(mu, sigma)
    pairs = []
    methods = list(sigma_pred_by_method)
    for i, m in enumerate(methods):
        for n in methods[i + 1 :]:
            delta_pred = risks[m] - risks[n]
            if abs(delta_pred) <= 1e-12:
                continue
            err_m = sigma_pred_by_method[m] - sigma_hat_by_method[m]
            err_n = sigma_pred_by_method[n] - sigma_hat_by_method[n]
            delta_rank = abs(float(np.sum(gradients[m] * err_m) - np.sum(gradients[n] * err_n)))
            boot_values = []
            if bootstrap_sigmas is not None:
                for boot in bootstrap_sigmas:
                    b_err_m = sigma_pred_by_method[m] - boot[m]
                    b_err_n = sigma_pred_by_method[n] - boot[n]
                    boot_values.append(abs(float(np.sum(gradients[m] * b_err_m) - np.sum(gradients[n] * b_err_n))))
            ucb95 = float(np.quantile(boot_values, 0.95)) if boot_values else delta_rank
            threshold = RHO_C * abs(float(delta_pred))
            pairs.append(
                {
                    "pair": [m, n],
                    "delta_pred": float(delta_pred),
                    "delta_rank": delta_rank,
                    "ucb95": ucb95,
                    "threshold": threshold,
                    "passed": bool(ucb95 < threshold),
                }
            )
    primary_pass = bool(pairs and all(row["passed"] for row in pairs))
    return {"risks": risks, "pairs": pairs, "primary_pass": primary_pass}


def frobenius_secondary(sigma_pred_by_method: dict[str, np.ndarray], sigma_hat_by_method: dict[str, np.ndarray]) -> dict[str, Any]:
    rows = {}
    for method in sigma_pred_by_method:
        denom = float(np.linalg.norm(sigma_hat_by_method[method], ord="fro") + 1e-12)
        rel = float(np.linalg.norm(sigma_pred_by_method[method] - sigma_hat_by_method[method], ord="fro") / denom)
        rows[method] = {"relative_frobenius_error": rel, "passed": bool(rel <= FROBENIUS_TOLERANCE)}
    return {"methods": rows, "secondary_pass": bool(all(row["passed"] for row in rows.values()))}


def bootstrap_sigma_by_epoch(
    epoch_vectors: list[dict[str, list[np.ndarray]]],
    *,
    repetitions: int,
) -> list[dict[str, np.ndarray]]:
    rng = make_rng(instance_id=INSTANCE_ID, method="hardware_sigma", budget=B_NOMINAL, replicate_id=0, stream="hardware_sigma_epoch_bootstrap")
    boot = []
    for _ in range(int(repetitions)):
        selected = rng.integers(0, len(epoch_vectors), size=len(epoch_vectors))
        merged = {method: [] for method in METHODS}
        for idx in selected:
            for method in METHODS:
                merged[method].extend(epoch_vectors[int(idx)][method])
        boot.append({method: covariance_from_gap_vectors(merged[method]) for method in METHODS})
    return boot


class AerSamplerAdapter:
    def __init__(self, *, noise_model: NoiseModel | None = None, seed: int = 260616):
        self.noise_model = noise_model
        self.seed = int(seed)
        self.submitted_batches = 0

    def run(self, tasks: list[Any], *, epoch: int) -> list[dict[str, int]]:
        simulator = AerSimulator(noise_model=self.noise_model, seed_simulator=self.seed + int(epoch))
        counts_out: list[dict[str, int] | None] = [None] * len(tasks)
        by_shots: dict[int, list[tuple[int, QuantumCircuit]]] = {}
        for idx, task in enumerate(tasks):
            by_shots.setdefault(int(task.shots), []).append((idx, compact_isa_circuit(task.circuit)))
        for shots, indexed in by_shots.items():
            result = simulator.run([circuit for _, circuit in indexed], shots=int(shots)).result()
            for local_idx, (global_idx, _) in enumerate(indexed):
                counts_out[global_idx] = {str(k): int(v) for k, v in result.get_counts(local_idx).items()}
        self.submitted_batches += 1
        return [counts for counts in counts_out if counts is not None]


class DeterministicProbabilitySampler:
    def __init__(self, *, bias: float = 0.03):
        self.bias = float(bias)
        self.submitted_batches = 0

    def run(self, tasks: list[Any], *, epoch: int) -> list[dict[str, int]]:
        n_circuits = len(tasks)
        self.submitted_batches += 1
        out = []
        base = np.arange(1, 17, dtype=float)
        # The caller only needs one count dict per circuit; rebuild from the
        # requested length without relying on circuit internals.
        for idx in range(n_circuits):
            probs = base + self.bias * (idx + 1 + epoch) * np.roll(base, idx % 16)
            probs = probs / probs.sum()
            out.append(probabilities_to_counts(probs, int(tasks[idx].shots)))
        return out


class RuntimeSamplerAdapter:
    """Phase-B adapter. Constructing it is the only path that reads Runtime state."""

    def __init__(self, service: Any, backend_name: str = BACKEND_NAME):
        self.service = service
        self.backend = service.backend(backend_name)
        self.submitted_batches = 0
        self.job_metadata: list[dict[str, Any]] = []

    def run(self, tasks: list[Any], *, epoch: int) -> list[dict[str, int]]:
        from qiskit_ibm_runtime import SamplerV2 as Sampler

        sampler = Sampler(mode=self.backend)
        pubs = [(task.circuit, None, int(task.shots)) for task in tasks]
        before = self.usage_minutes()
        submitted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        job = sampler.run(pubs)
        result = job.result()
        after = self.usage_minutes()
        completed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.submitted_batches += 1
        self.job_metadata.append(
            {
                "epoch": int(epoch),
                "job_id": job.job_id(),
                "submitted_utc": submitted_at,
                "completed_utc": completed_at,
                "usage_before_minutes": before,
                "usage_after_minutes": after,
            }
        )
        return [_extract_pub_counts(result[idx]) for idx in range(len(tasks))]

    def usage_minutes(self) -> float | None:
        try:
            usage = self.service.usage()
            consumed = usage.get("usage_consumed_seconds")
            return None if consumed is None else float(consumed) / 60.0
        except Exception:
            return None


def _extract_pub_counts(pub_result: Any) -> dict[str, int]:
    data = getattr(pub_result, "data", None)
    if data is None:
        raise RuntimeError("Sampler result does not expose a data field")
    for register_name in ("meas", "c"):
        register = getattr(data, register_name, None)
        if register is not None and hasattr(register, "get_counts"):
            return {str(key): int(value) for key, value in register.get_counts().items()}
    if hasattr(data, "items"):
        for _, register in data.items():
            if hasattr(register, "get_counts"):
                return {str(key): int(value) for key, value in register.get_counts().items()}
    for register_name in dir(data):
        if register_name.startswith("_"):
            continue
        register = getattr(data, register_name, None)
        if hasattr(register, "get_counts"):
            return {str(key): int(value) for key, value in register.get_counts().items()}
    raise RuntimeError("Sampler result does not contain counts")


def dry_run_noise_model() -> NoiseModel:
    model = NoiseModel()
    model.add_all_qubit_quantum_error(depolarizing_error(0.002, 1), ["h", "rx", "rz", "sx", "x"])
    model.add_all_qubit_quantum_error(depolarizing_error(0.01, 2), ["rzz", "cx", "cz"])
    return model


def load_ibm_service_phase_b_only():
    payload = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    token = None
    for key in ("apikey", "api_key", "token", "key"):
        if payload.get(key):
            token = str(payload[key])
            break
    if not token:
        raise RuntimeError("IBM token JSON is missing a supported key")
    from qiskit_ibm_runtime import QiskitRuntimeService

    return QiskitRuntimeService(channel="ibm_quantum_platform", token=token, region="us-east", plans_preference=["open"])


def checkpoint_path(output_dir: Path, epoch: int) -> Path:
    return output_dir / "checkpoints" / f"epoch_{epoch:02d}.json"


def characterization_checkpoint_path(output_dir: Path) -> Path:
    return output_dir / "checkpoints" / "characterization.json"


def _task_metadata(task: Any) -> dict[str, Any]:
    meta = {
        "epoch": int(getattr(task, "epoch", -1)),
        "shots": int(task.shots),
        "circuit_depth": int(task.circuit.depth() or 0),
        "circuit_size": int(task.circuit.size()),
    }
    for attr in ("replicate", "method", "candidate", "scale_nominal", "scale_effective"):
        if hasattr(task, attr):
            value = getattr(task, attr)
            if isinstance(value, np.generic):
                value = value.item()
            meta[attr] = value
    return meta


def save_counts_checkpoint(
    path: Path,
    *,
    kind: str,
    tasks: list[Any],
    counts_list: list[dict[str, int]],
    metadata: dict[str, Any] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "kind": kind,
        "metadata": metadata or {},
        "tasks": [_task_metadata(task) for task in tasks],
        "raw_counts": [{str(k): int(v) for k, v in counts.items()} for counts in counts_list],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_counts_checkpoint(path: Path) -> list[dict[str, int]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [{str(k): int(v) for k, v in counts.items()} for counts in payload["raw_counts"]]


def save_epoch_checkpoint(
    path: Path,
    epoch_vectors: dict[str, list[np.ndarray]],
    *,
    epoch: int,
    tasks: list[Any],
    counts_list: list[dict[str, int]],
    job_metadata: dict[str, Any] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "epoch": int(epoch),
        "job_metadata": job_metadata or {},
        "tasks": [_task_metadata(task) for task in tasks],
        "raw_counts": [{str(k): int(v) for k, v in counts.items()} for counts in counts_list],
        "gap_vectors": {
            method: [np.asarray(vec, dtype=float).tolist() for vec in vectors]
            for method, vectors in epoch_vectors.items()
        },
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_epoch_checkpoint(path: Path) -> dict[str, list[np.ndarray]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        method: [np.asarray(vec, dtype=float) for vec in vectors]
        for method, vectors in payload["gap_vectors"].items()
    }


class BudgetGuard:
    def __init__(self, *, consumed_minutes: float = 0.0, per_epoch_minutes: float = 0.0, cap_minutes: float = TOTAL_QUANTUM_TIME_CAP_MINUTES):
        self.consumed_minutes = float(consumed_minutes)
        self.per_epoch_minutes = float(per_epoch_minutes)
        self.cap_minutes = float(cap_minutes)

    def can_start_epoch(self) -> bool:
        return self.consumed_minutes + self.per_epoch_minutes <= self.cap_minutes

    def record_epoch(self) -> None:
        self.consumed_minutes += self.per_epoch_minutes


def run_pipeline(
    *,
    config: RunConfig,
    sampler: SamplerAdapter,
    resume: bool = False,
    stop_after_epoch: int | None = None,
    budget_guard: BudgetGuard | None = None,
    true_rates: np.ndarray | None = None,
    force_gate_c1_fail: bool = False,
) -> dict[str, Any]:
    start = time.perf_counter()
    output_dir = Path(config.output_dir)
    if output_dir.exists() and not resume and any(output_dir.iterdir()):
        raise RuntimeError(f"output_dir {output_dir} already contains data; pass --resume or choose a fresh directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "hsmc_result.json"

    landscape = microcell_landscape()
    L = contrast_matrix(4, ref=0)
    mu = L @ landscape.ideal_values
    effective_scales = effective_scale_tuple()

    if true_rates is None:
        true_rates = np.array([0.004, 0.003, 0.0025, 0.0035, 0.0015, 0.0012, 0.0018], dtype=float)
        char_tasks = build_characterization_tasks()
        char_cp = characterization_checkpoint_path(output_dir)
        if resume and char_cp.exists():
            char_counts = load_counts_checkpoint(char_cp)
        else:
            char_counts = sampler.run(char_tasks, epoch=-1)
            save_counts_checkpoint(
                char_cp,
                kind="characterization_sparse_pl",
                tasks=char_tasks,
                counts_list=char_counts,
                metadata={
                    "job_id": "offline_characterization" if not isinstance(sampler, RuntimeSamplerAdapter) else "runtime_characterization",
                    "submitted_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "mode": "offline_or_injected_sampler",
                },
            )
        char_source = "physical_characterization_circuits"
    else:
        char_tasks, char_counts = synthetic_characterization_counts_test_only(true_rates)
        char_source = "test_only_synthetic_counts"
    design = characterization_design(char_tasks)
    observations = characterization_observations_from_counts(char_tasks, char_counts)
    learned_model = learn_sparse_pl_model(design, observations)
    learned = learned_model["rates"]
    gate_c1 = gate_c1_metrics(design, observations, learned_model)
    if force_gate_c1_fail:
        gate_c1 = {**gate_c1, "passed": False, "forced_offline_test_failure": True}
    if not gate_c1["passed"]:
        payload = {
            "status": "stopped_gate_c1",
            "characterization": {
                "source": char_source,
                "circuit_count": len(char_tasks),
                "shots_per_circuit": CHARACTERIZATION_SHOTS,
                "learned_rates": learned.tolist(),
                "learned_intercepts": learned_model["intercepts"].tolist(),
            },
            "gate_c1": gate_c1,
            "forbidden_outputs_computed": [],
        }
        result_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return payload

    primitive_variance_unit = primitive_variance_unit_from_rates(learned)
    da_coeffs = decision_zne_coefficients_from_prediction(
        primitive_variance_unit,
        landscape.ideal_values,
        effective_scales,
    )
    maps = method_maps(effective_scales, da_coeffs=da_coeffs)
    sigma_pred_by_method = {
        method: sigma_pred_from_primitive_variances(primitive_variance_unit, method, maps[method], L)
        for method in METHODS
    }

    epoch_vectors: list[dict[str, list[np.ndarray]]] = []
    completed_epochs = []
    stopped_for_budget = False
    for epoch in range(config.epochs):
        cp = checkpoint_path(output_dir, epoch)
        if cp.exists():
            epoch_data = load_epoch_checkpoint(cp)
            epoch_vectors.append(epoch_data)
            completed_epochs.append(epoch)
            continue
        if budget_guard is not None and not budget_guard.can_start_epoch():
            stopped_for_budget = True
            break
        tasks = build_epoch_tasks(epoch, config.reps_per_epoch)
        counts = sampler.run(tasks, epoch=epoch)
        epoch_data = gap_vectors_for_epoch(tasks, counts, maps, L)
        metadata = {
            "job_id": f"offline_epoch_{epoch:02d}",
            "submitted_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mode": "offline_or_injected_sampler",
        }
        if hasattr(sampler, "job_metadata") and getattr(sampler, "job_metadata"):
            metadata = dict(getattr(sampler, "job_metadata")[-1])
        save_epoch_checkpoint(
            cp,
            epoch_data,
            epoch=epoch,
            tasks=tasks,
            counts_list=counts,
            job_metadata=metadata,
        )
        epoch_vectors.append(epoch_data)
        completed_epochs.append(epoch)
        if budget_guard is not None:
            budget_guard.record_epoch()
        if stop_after_epoch is not None and epoch >= int(stop_after_epoch):
            break

    complete = len(completed_epochs) == config.epochs and not stopped_for_budget
    if not epoch_vectors:
        payload = {
            "status": "stopped_budget_guard" if stopped_for_budget else "incomplete_checkpointed",
            "backend_frozen": BACKEND_NAME,
            "physical_qubits": list(PHYSICAL_QUBITS),
            "instance_id": INSTANCE_ID,
            "gate_c1": gate_c1,
            "characterization": {
                "source": char_source,
                "circuit_count": len(char_tasks),
                "shots_per_circuit": CHARACTERIZATION_SHOTS,
                "learned_rates": learned.tolist(),
                "learned_intercepts": learned_model["intercepts"].tolist(),
            },
            "completed_epochs": completed_epochs,
            "sampler_submitted_batches": int(getattr(sampler, "submitted_batches", -1)),
            "stopped_for_budget": stopped_for_budget,
            "forbidden_outputs_computed": [],
            "duration_seconds": time.perf_counter() - start,
        }
        result_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return payload
    merged = {method: [] for method in METHODS}
    for epoch_data in epoch_vectors:
        for method in METHODS:
            merged[method].extend(epoch_data[method])
    sigma_hat_by_method = {method: covariance_from_gap_vectors(merged[method]) for method in METHODS}
    bootstrap = (
        bootstrap_sigma_by_epoch(epoch_vectors, repetitions=config.bootstrap_repetitions)
        if complete and epoch_vectors
        else []
    )
    endpoint = endpoint_projected_ranking(
        mu=mu,
        sigma_pred_by_method=sigma_pred_by_method,
        sigma_hat_by_method=sigma_hat_by_method,
        bootstrap_sigmas=bootstrap,
    )
    secondary = frobenius_secondary(sigma_pred_by_method, sigma_hat_by_method)
    if endpoint["primary_pass"] and secondary["secondary_pass"]:
        label = "Frobenius-conservative_pass"
    elif endpoint["primary_pass"]:
        label = "directionally-sensitive_pass"
    else:
        label = "failed_or_inconclusive"
    payload = {
        "status": "complete" if complete else ("stopped_budget_guard" if stopped_for_budget else "incomplete_checkpointed"),
        "backend_frozen": BACKEND_NAME,
        "physical_qubits": list(PHYSICAL_QUBITS),
        "instance_id": INSTANCE_ID,
        "config": {
            "B_nominal": config.shots,
            "R_final": config.r_final,
            "epochs": config.epochs,
            "reps_per_epoch": config.reps_per_epoch,
            "methods": list(METHODS),
            "nominal_scales": list(SCALES_NOMINAL),
            "effective_scales": list(effective_scales),
            "shots_per_scale": {"Raw": B_NOMINAL, "Accuracy-ZNE": ZNE_SHOTS_PER_SCALE, "DA-ZNE": ZNE_SHOTS_PER_SCALE},
            "accuracy_zne_coefficients": zne_coefficients_from_effective_scales(effective_scales).tolist(),
            "decision_zne_coefficients": da_coeffs.tolist(),
            "bootstrap_repetitions": config.bootstrap_repetitions,
            "isa_transpilation": {
                "backend": BACKEND_NAME,
                "physical_qubits": list(PHYSICAL_QUBITS),
                "optimization_level_for_main_circuits": ISA_OPTIMIZATION_LEVEL,
                "seed_transpiler": SEED_TRANSPILE,
                "implementation_note": ISA_IMPLEMENTATION_NOTE,
                "lambda2_rule": LAMBDA2_RULE,
                "rz_noise_convention": RZ_NOISE_CONVENTION,
            },
        },
        "ordering_gate": ordering_gate_end_to_end(),
        "characterization": {
            "source": char_source,
            "circuit_count": len(char_tasks),
            "shots_per_circuit": CHARACTERIZATION_SHOTS,
            "learned_rates": learned.tolist(),
            "learned_intercepts": learned_model["intercepts"].tolist(),
            "observations_minmax": [float(np.min(observations)), float(np.max(observations))],
        },
        "gate_c1": gate_c1,
        "completed_epochs": completed_epochs,
        "sampler_submitted_batches": int(getattr(sampler, "submitted_batches", -1)),
        "stopped_for_budget": stopped_for_budget,
        "sigma_pred": {method: sigma_pred_by_method[method].tolist() for method in METHODS},
        "sigma_hat": {method: sigma_hat_by_method[method].tolist() for method in METHODS},
        "ledger": {
            "C_noiselearn": int(len(char_tasks) * CHARACTERIZATION_SHOTS),
            "C_Sigmahat": int(
                sum(
                    sum(int(task.shots) for task in build_epoch_tasks(epoch, config.reps_per_epoch))
                    for epoch in completed_epochs
                )
            ),
            "C_total": int(
                len(char_tasks) * CHARACTERIZATION_SHOTS
                + sum(
                    sum(int(task.shots) for task in build_epoch_tasks(epoch, config.reps_per_epoch))
                    for epoch in completed_epochs
                )
            ),
            "amortization_flag": "non_amortized",
        },
        "primary_projected_ranking": endpoint,
        "secondary_frobenius": secondary,
        "result_label": label,
        "forbidden_outputs_computed": [],
        "duration_seconds": time.perf_counter() - start,
    }
    result_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Hardware-Sigma main runner, offline dry-run by default.")
    parser.add_argument("--dry-run", action="store_true", help="Run the complete pipeline with an injected Aer sampler.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--bootstrap-repetitions", type=int, default=BOOTSTRAP_REPETITIONS)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if not args.dry_run:
        raise SystemExit("Phase A forbids hardware submission. Use --dry-run for offline validation.")
    config = RunConfig(output_dir=args.output_dir, bootstrap_repetitions=int(args.bootstrap_repetitions))
    sampler = AerSamplerAdapter(noise_model=dry_run_noise_model())
    result = run_pipeline(config=config, sampler=sampler, resume=bool(args.resume))
    print("HARDWARE_SIGMA_DRY_RUN_COMPLETE")
    print(f"status={result['status']}")
    print(f"result_label={result['result_label']}")
    print(f"completed_epochs={len(result['completed_epochs'])}")
    print(f"sampler_submitted_batches={result['sampler_submitted_batches']}")
    print(f"output={Path(args.output_dir) / 'hsmc_result.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
