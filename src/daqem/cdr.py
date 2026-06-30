"""Isolated Clifford Data Regression prototype for the pre-registered CDR arm."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import networkx as nx
import numpy as np
import yaml
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector
from qiskit_aer import AerSimulator

from daqem.budget import total_cost
from daqem.candidates import maxcut_values_for_graph
from daqem.noise import depolarizing_noise_model
from daqem.qaoa import counts_expectation, default_angles, maxcut_graph
from daqem.rng import make_rng


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "reproducibility" / "config" / "cdr_method.yaml"
CLIFFORD_ANGLES = np.array(
    [0.0, np.pi / 2.0, -np.pi / 2.0, np.pi],
    dtype=float,
)


@dataclass(frozen=True)
class GateSpec:
    """One parameterized QAOA gate in gate-level CDR coordinates."""

    name: str
    qubits: tuple[int, ...]


@dataclass(frozen=True)
class CDRTrainingCircuit:
    """Target-local Clifford-perturbed training circuit."""

    gate_angles: np.ndarray
    rounded_mask: np.ndarray
    endpoint_mode: str
    rounded_count: int


@dataclass(frozen=True)
class CDRFit:
    """Linear CDR fit exact ~= a * noisy + b."""

    a: float
    b: float


@dataclass(frozen=True)
class CDRResult:
    """End-to-end isolated CDR result for one target circuit."""

    fit: CDRFit
    target_noisy: float
    target_exact: float
    target_mitigated: float
    c_train: int
    training_noisy: np.ndarray
    training_exact: np.ndarray


def load_cdr_config(path: Path = CONFIG_PATH) -> dict:
    """Load the pre-registered isolated CDR method config."""

    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def qaoa_gate_specs_and_angles(
    graph: nx.Graph,
    *,
    depth: int,
    gammas: Iterable[float],
    betas: Iterable[float],
) -> tuple[list[GateSpec], np.ndarray]:
    """Expand layer-level QAOA angles into gate-level CDR coordinates."""

    gamma_arr = np.asarray(list(gammas), dtype=float)
    beta_arr = np.asarray(list(betas), dtype=float)
    if gamma_arr.shape != (int(depth),) or beta_arr.shape != (int(depth),):
        raise ValueError("gammas and betas must have length depth")
    edges = sorted((int(i), int(j)) for i, j in graph.edges())
    specs: list[GateSpec] = []
    angles: list[float] = []
    for layer in range(int(depth)):
        for i, j in edges:
            specs.append(GateSpec("rzz", (i, j)))
            angles.append(2.0 * float(gamma_arr[layer]))
        for qubit in range(graph.number_of_nodes()):
            specs.append(GateSpec("rx", (int(qubit),)))
            angles.append(2.0 * float(beta_arr[layer]))
    return specs, np.asarray(angles, dtype=float)


def circuit_from_gate_angles(
    graph: nx.Graph,
    specs: list[GateSpec],
    gate_angles: np.ndarray,
    *,
    measure: bool,
) -> QuantumCircuit:
    """Build a QAOA-like circuit from gate-level angles."""

    angle_arr = np.asarray(gate_angles, dtype=float)
    if angle_arr.shape != (len(specs),):
        raise ValueError("gate_angles length must match specs")
    circuit = QuantumCircuit(graph.number_of_nodes())
    circuit.h(range(graph.number_of_nodes()))
    for spec, angle in zip(specs, angle_arr, strict=True):
        if spec.name == "rzz":
            circuit.rzz(float(angle), spec.qubits[0], spec.qubits[1])
        elif spec.name == "rx":
            circuit.rx(float(angle), spec.qubits[0])
        else:
            raise ValueError(f"unsupported gate spec: {spec.name}")
    if measure:
        circuit.measure_all()
    return circuit


def nearest_clifford_angles(
    gate_angles: np.ndarray,
    clifford_angles: np.ndarray = CLIFFORD_ANGLES,
) -> tuple[np.ndarray, np.ndarray]:
    """Round each gate angle to the nearest configured Clifford angle."""

    arr = np.asarray(gate_angles, dtype=float)
    candidates = np.asarray(clifford_angles, dtype=float)
    rounded = np.empty_like(arr, dtype=float)
    min_dist = np.empty_like(arr, dtype=float)
    for idx, angle in enumerate(arr):
        distances = np.abs(float(angle) - candidates)
        min_value = float(np.min(distances))
        tied = candidates[np.isclose(distances, min_value, atol=1e-15, rtol=0.0)]
        tied = sorted(float(value) for value in tied)
        rounded_value = min(tied, key=lambda value: (abs(value), value))
        rounded[idx] = rounded_value
        min_dist[idx] = abs(float(angle) - rounded_value)
    return rounded, min_dist


def bracketing_clifford_endpoint_angles(
    gate_angles: np.ndarray,
    clifford_angles: np.ndarray = CLIFFORD_ANGLES,
) -> tuple[np.ndarray, np.ndarray]:
    """Return lower/upper Clifford endpoints bracketing each target angle."""

    arr = np.asarray(gate_angles, dtype=float)
    grid = np.sort(np.asarray(clifford_angles, dtype=float))
    lower = np.empty_like(arr, dtype=float)
    upper = np.empty_like(arr, dtype=float)
    for idx, angle in enumerate(arr):
        below = grid[grid <= float(angle) + 1e-15]
        above = grid[grid >= float(angle) - 1e-15]
        lo = float(below[-1]) if below.size else float(grid[0])
        hi = float(above[0]) if above.size else float(grid[-1])
        if abs(float(angle) - lo) < 1e-15 and above.size > 1:
            hi = float(above[1])
        if abs(float(angle) - hi) < 1e-15 and below.size > 1:
            lo = float(below[-2])
        lower[idx] = lo
        upper[idx] = hi
    return lower, upper


def generate_near_clifford_training_set(
    gate_angles: np.ndarray,
    *,
    training_set_size: int,
    rounded_gate_counts: Iterable[int],
    endpoint_modes: Iterable[str],
    instance_id: str,
    rng_budget: int = 0,
    mask_stride: int = 7,
) -> list[CDRTrainingCircuit]:
    """Generate target-local Clifford perturbations with deterministic masks."""

    if training_set_size <= 0:
        raise ValueError("training_set_size must be positive")
    arr = np.asarray(gate_angles, dtype=float)
    counts = [int(value) for value in rounded_gate_counts]
    modes = [str(value) for value in endpoint_modes]
    if not counts:
        raise ValueError("rounded_gate_counts must be non-empty")
    if any(value <= 0 or value > arr.size for value in counts):
        raise ValueError("rounded_gate_counts entries must be in [1, number of gates]")
    if any(value not in {"lower", "upper"} for value in modes):
        raise ValueError("endpoint_modes entries must be 'lower' or 'upper'")
    lower, upper = bracketing_clifford_endpoint_angles(arr)
    rng = make_rng(
        instance_id=instance_id,
        method="CDR",
        budget=int(rng_budget),
        replicate_id=0,
        stream="cdr_training",
    )
    base_order = rng.permutation(arr.size)
    circuits: list[CDRTrainingCircuit] = []
    seen: set[tuple[int, ...]] = set()
    sequence = [(count, mode) for count in counts for mode in modes]
    cycle = 0
    while len(circuits) < training_set_size and cycle < max(4, training_set_size):
        for count, mode in sequence:
            if len(circuits) >= training_set_size:
                break
            offset = (len(circuits) * int(mask_stride) + cycle) % arr.size
            selected = np.roll(base_order, -offset)[:count]
            rounded_mask = np.zeros(arr.size, dtype=bool)
            rounded_mask[selected] = True
            key = (count, mode, *np.sort(selected).tolist())
            if key in seen:
                continue
            seen.add(key)
            candidate = arr.copy()
            endpoints = lower if mode == "lower" else upper
            candidate[rounded_mask] = endpoints[rounded_mask]
            circuits.append(
                CDRTrainingCircuit(
                    candidate,
                    rounded_mask,
                    endpoint_mode=mode,
                    rounded_count=count,
                )
            )
        cycle += 1
    if len(circuits) != training_set_size:
        raise RuntimeError("could not generate enough distinct CDR training circuits")
    return circuits


def exact_maxcut_expectation_from_gate_angles(
    graph: nx.Graph,
    specs: list[GateSpec],
    gate_angles: np.ndarray,
) -> float:
    """Compute noiseless exact MaxCut expectation by statevector."""

    circuit = circuit_from_gate_angles(graph, specs, gate_angles, measure=False)
    probabilities = Statevector.from_instruction(circuit).probabilities()
    return float(np.dot(probabilities, maxcut_values_for_graph(graph)))


def noisy_maxcut_expectation_from_gate_angles(
    graph: nx.Graph,
    specs: list[GateSpec],
    gate_angles: np.ndarray,
    *,
    shots: int,
    noise_model,
    instance_id: str,
    replicate_id: int,
    stream: str,
) -> float:
    """Compute noisy MaxCut expectation from Aer counts."""

    if shots <= 0:
        raise ValueError("shots must be positive")
    rng = make_rng(
        instance_id=instance_id,
        method="CDR",
        budget=int(shots),
        replicate_id=int(replicate_id),
        stream=stream,
    )
    seed = int(rng.integers(1, 2**31 - 1))
    simulator = AerSimulator(noise_model=noise_model, seed_simulator=seed)
    circuit = circuit_from_gate_angles(graph, specs, gate_angles, measure=True)
    transpiled = transpile(circuit, simulator, seed_transpiler=seed)
    counts = simulator.run(transpiled, shots=int(shots)).result().get_counts()
    return counts_expectation(counts, graph)


def fit_linear_cdr(noisy: np.ndarray, exact: np.ndarray) -> CDRFit:
    """Fit exact ~= a * noisy + b by ordinary least squares."""

    noisy_arr = np.asarray(noisy, dtype=float)
    exact_arr = np.asarray(exact, dtype=float)
    if noisy_arr.shape != exact_arr.shape or noisy_arr.ndim != 1:
        raise ValueError("noisy and exact must be one-dimensional arrays with same shape")
    if noisy_arr.size < 2:
        raise ValueError("at least two training points are required")
    design = np.column_stack([noisy_arr, np.ones(noisy_arr.size)])
    a, b = np.linalg.lstsq(design, exact_arr, rcond=None)[0]
    return CDRFit(float(a), float(b))


def apply_cdr_fit(noisy_value: float, fit: CDRFit) -> float:
    """Apply a fitted linear CDR correction."""

    return float(fit.a * float(noisy_value) + fit.b)


def cdr_training_ledger_row(
    *,
    training_set_size: int,
    shots_per_training_circuit: int,
    task: str = "cdr_training",
) -> dict:
    """Return a budget-ledger row for the CDR training cost."""

    c_train = int(training_set_size) * int(shots_per_training_circuit)
    row = {
        "method": "CDR",
        "selector": "not_applicable",
        "task": task,
        "B_nominal": int(shots_per_training_circuit),
        "C_train": float(c_train),
        "C_select": 0.0,
        "C_eval": 0.0,
        "C_calib": 0.0,
        "C_noiselearn": 0.0,
        "C_Sigmahat": 0.0,
        "C_overhead": 0.0,
        "amortization_flag": "non_amortized",
    }
    row["C_total"] = total_cost(row)
    return row


def run_cdr(
    graph: nx.Graph,
    *,
    depth: int,
    gammas: Iterable[float],
    betas: Iterable[float],
    instance_id: str,
    config: dict,
    noise_model=None,
) -> CDRResult:
    """Run isolated CDR training and correction for one target circuit."""

    training_cfg = config["training_set"]
    perturbation_cfg = config["target_local_perturbation_rule"]
    training_set_size = int(training_cfg["training_set_size"])
    shots = int(training_cfg["shots_per_training_circuit"])
    if noise_model is None:
        noise_model = depolarizing_noise_model()
    specs, target_angles = qaoa_gate_specs_and_angles(
        graph,
        depth=int(depth),
        gammas=gammas,
        betas=betas,
    )
    training = generate_near_clifford_training_set(
        target_angles,
        training_set_size=training_set_size,
        rounded_gate_counts=perturbation_cfg["rounded_gate_counts"],
        endpoint_modes=perturbation_cfg["endpoint_modes"],
        instance_id=instance_id,
        rng_budget=0,
        mask_stride=int(perturbation_cfg.get("mask_stride", 7)),
    )
    exact_values = np.array(
        [
            exact_maxcut_expectation_from_gate_angles(graph, specs, item.gate_angles)
            for item in training
        ],
        dtype=float,
    )
    noisy_values = np.array(
        [
            noisy_maxcut_expectation_from_gate_angles(
                graph,
                specs,
                item.gate_angles,
                shots=shots,
                noise_model=noise_model,
                instance_id=instance_id,
                replicate_id=idx,
                stream="cdr_training_shots",
            )
            for idx, item in enumerate(training)
        ],
        dtype=float,
    )
    fit = fit_linear_cdr(noisy_values, exact_values)
    target_exact = exact_maxcut_expectation_from_gate_angles(graph, specs, target_angles)
    target_noisy = noisy_maxcut_expectation_from_gate_angles(
        graph,
        specs,
        target_angles,
        shots=shots,
        noise_model=noise_model,
        instance_id=instance_id,
        replicate_id=10_000,
        stream="cdr_target_shots",
    )
    target_mitigated = apply_cdr_fit(target_noisy, fit)
    c_train = int(cdr_training_ledger_row(
        training_set_size=training_set_size,
        shots_per_training_circuit=shots,
    )["C_train"])
    return CDRResult(
        fit=fit,
        target_noisy=target_noisy,
        target_exact=target_exact,
        target_mitigated=target_mitigated,
        c_train=c_train,
        training_noisy=noisy_values,
        training_exact=exact_values,
    )


def smoke() -> CDRResult:
    """Run a small non-confirmatory smoke case for review."""

    config = load_cdr_config()
    graph = maxcut_graph(num_qubits=10, degree=3, seed=260616)
    depth = 2
    gammas, betas = default_angles(depth)
    return run_cdr(
        graph,
        depth=depth,
        gammas=gammas,
        betas=betas,
        instance_id="CDR_SMOKE_P0",
        config=config,
        noise_model=depolarizing_noise_model(),
    )


def smoke_validity_checks(result: CDRResult, config: dict) -> dict[str, bool]:
    """Evaluate the pre-fixed P0 validity bar for the CDR smoke."""

    bar = config["validity_bar"]
    exact_min = float(np.min(result.training_exact))
    exact_max = float(np.max(result.training_exact))
    exact_std = float(np.std(result.training_exact))
    noisy_error = abs(result.target_noisy - result.target_exact)
    mitigated_error = abs(result.target_mitigated - result.target_exact)
    return {
        "training_spread": exact_std >= float(bar["training_exact_std_min"]),
        "target_bracketed": exact_min <= result.target_exact <= exact_max,
        "cdr_improves": mitigated_error < noisy_error,
        "slope_nondegenerate": abs(result.fit.a) >= float(bar["abs_slope_min"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="run the P0 small smoke")
    args = parser.parse_args(argv)
    if not args.smoke:
        parser.error("only --smoke is available in P0")
    config = load_cdr_config()
    result = smoke()
    checks = smoke_validity_checks(result, config)
    exact_min = float(np.min(result.training_exact))
    exact_max = float(np.max(result.training_exact))
    exact_std = float(np.std(result.training_exact))
    noisy_error = abs(result.target_noisy - result.target_exact)
    mitigated_error = abs(result.target_mitigated - result.target_exact)
    passed = all(checks.values())
    print("CDR SMOKE PASS" if passed else "CDR SMOKE FAIL")
    print(f"training_exact_min={exact_min:.12g}")
    print(f"training_exact_max={exact_max:.12g}")
    print(f"training_exact_std={exact_std:.12g}")
    print(f"target_in_training_range={checks['target_bracketed']}")
    print(f"a={result.fit.a:.12g}")
    print(f"b={result.fit.b:.12g}")
    print(f"C_train={result.c_train}")
    print(f"target_noisy={result.target_noisy:.12g}")
    print(f"target_mitigated={result.target_mitigated:.12g}")
    print(f"target_exact={result.target_exact:.12g}")
    print(f"error_noisy={noisy_error:.12g}")
    print(f"error_mitigated={mitigated_error:.12g}")
    for name, ok in checks.items():
        print(f"validity_{name}={'PASS' if ok else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
