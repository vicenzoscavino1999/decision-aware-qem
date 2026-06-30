"""Isolated Probabilistic Error Cancellation prototype for the PEC arm."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import networkx as nx
import numpy as np
import yaml
from qiskit import QuantumCircuit
from qiskit.circuit.library import UnitaryGate
from qiskit.quantum_info import Statevector
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error

from daqem.budget import total_cost
from daqem.candidates import maxcut_values_for_graph
from daqem.noise import (
    ONE_QUBIT_DEPOLARIZING,
    TWO_QUBIT_DEPOLARIZING,
    depolarizing_noise_model,
)
from daqem.qaoa import (
    counts_expectation,
    default_angles,
    maxcut_graph,
    qaoa_maxcut_circuit,
)
from daqem.risk import gri_risk
from daqem.rng import make_rng


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "reproducibility" / "config" / "pec_method.yaml"
HET_DERISK_CONFIG_PATH = (
    REPO_ROOT / "reproducibility" / "config" / "het_pec_derisk.yaml"
)

PAULI_MATRICES = {
    "I": np.eye(2, dtype=complex),
    "X": np.array([[0, 1], [1, 0]], dtype=complex),
    "Y": np.array([[0, -1j], [1j, 0]], dtype=complex),
    "Z": np.array([[1, 0], [0, -1]], dtype=complex),
}


@dataclass(frozen=True)
class PauliInverseChannel:
    """Inverse quasi-probability data for a depolarizing Pauli channel."""

    num_qubits: int
    channel_probabilities: dict[str, float]
    quasi_probabilities: dict[str, float]
    sampling_probabilities: dict[str, float]
    gamma: float
    inferred_p: float
    lambda_pauli: float


@dataclass(frozen=True)
class PECResult:
    """PEC smoke result for one QAOA-MaxCut circuit."""

    target_exact: float
    target_raw: float
    target_pec: float
    gamma: float
    gamma_squared: float
    n_samples: int
    shots_per_sample: int


def load_pec_config(path: Path = CONFIG_PATH) -> dict:
    """Load the isolated PEC method config."""

    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_het_pec_derisk_config(path: Path = HET_DERISK_CONFIG_PATH) -> dict:
    """Load the locked heterogeneous-PEC de-risk config."""

    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _primary_cell_graph(config: dict) -> nx.Graph:
    cell = config["primary_cell"]
    return maxcut_graph(
        num_qubits=int(cell["num_qubits"]),
        degree=int(cell["degree"]),
        seed=int(cell["graph_seed"]),
    )


def heterogeneous_depolarizing_rates(config: dict) -> tuple[dict[int, float], dict[tuple[int, int], float]]:
    """Sample locked heterogeneous depolarizing rates from the preregistered config."""

    channel = config["heterogeneous_channel"]
    seed_policy = channel["seed_policy"]
    rng = make_rng(
        instance_id=str(seed_policy["instance_id"]),
        method=str(seed_policy["method"]),
        budget=int(seed_policy["budget"]),
        replicate_id=int(seed_policy["replicate_id"]),
        stream=str(seed_policy["stream"]),
    )
    graph = _primary_cell_graph(config)
    clip_low, clip_high = [float(value) for value in channel["clipping"]]
    p1_cfg = channel["p1_per_qubit"]
    p2_cfg = channel["p2_per_edge"]
    p1_values = rng.lognormal(
        mean=float(np.log(float(p1_cfg["median"]))),
        sigma=float(p1_cfg["sigma_log"]),
        size=graph.number_of_nodes(),
    )
    edges = sorted(tuple(sorted((int(i), int(j)))) for i, j in graph.edges())
    p2_values = rng.lognormal(
        mean=float(np.log(float(p2_cfg["median"]))),
        sigma=float(p2_cfg["sigma_log"]),
        size=len(edges),
    )
    p1_values = np.clip(p1_values, clip_low, clip_high)
    p2_values = np.clip(p2_values, clip_low, clip_high)
    p1_by_qubit = {int(qubit): float(p1_values[qubit]) for qubit in range(graph.number_of_nodes())}
    p2_by_edge = {edge: float(value) for edge, value in zip(edges, p2_values, strict=True)}
    return p1_by_qubit, p2_by_edge


def heterogeneous_depolarizing_noise_model(
    *,
    p1_by_qubit: dict[int, float],
    p2_by_edge: dict[tuple[int, int], float],
    one_qubit_gates: Iterable[str],
    two_qubit_gates: Iterable[str],
) -> NoiseModel:
    """Build an Aer NoiseModel with qubit- and edge-specific depolarizing rates."""

    noise_model = NoiseModel()
    one_qubit_gate_list = [str(gate) for gate in one_qubit_gates]
    two_qubit_gate_list = [str(gate) for gate in two_qubit_gates]
    for qubit, p1 in sorted(p1_by_qubit.items()):
        noise_model.add_quantum_error(
            depolarizing_error(float(p1), 1),
            one_qubit_gate_list,
            [int(qubit)],
        )
    for (left, right), p2 in sorted(p2_by_edge.items()):
        noise_model.add_quantum_error(
            depolarizing_error(float(p2), 2),
            two_qubit_gate_list,
            [int(left), int(right)],
        )
    return noise_model


def heterogeneous_noise_model_from_config(
    config: dict,
) -> tuple[nx.Graph, dict[int, float], dict[tuple[int, int], float], NoiseModel]:
    """Construct the locked heterogeneous channel without computing decision metrics."""

    graph = _primary_cell_graph(config)
    p1_by_qubit, p2_by_edge = heterogeneous_depolarizing_rates(config)
    channel = config["heterogeneous_channel"]
    noise_model = heterogeneous_depolarizing_noise_model(
        p1_by_qubit=p1_by_qubit,
        p2_by_edge=p2_by_edge,
        one_qubit_gates=channel["p1_per_qubit"]["applies_to_gates"],
        two_qubit_gates=channel["p2_per_edge"]["applies_to_gates"],
    )
    return graph, p1_by_qubit, p2_by_edge, noise_model


def _label_from_qiskit_instruction(instruction: list[dict], num_qubits: int) -> str:
    if len(instruction) == 1 and instruction[0]["name"] == "pauli":
        label = str(instruction[0]["params"][0]).upper()
        if len(label) != num_qubits:
            raise ValueError(f"invalid Pauli label length: {label}")
        return label
    labels = ["I"] * num_qubits
    for item in instruction:
        name = str(item["name"]).upper()
        if name == "ID":
            name = "I"
        if name not in PAULI_MATRICES:
            raise ValueError(f"unsupported depolarizing instruction: {item}")
        qubits = item.get("qubits", [])
        if len(qubits) != 1:
            raise ValueError(f"unsupported one-qubit instruction shape: {item}")
        labels[int(qubits[0])] = name
    return "".join(labels)


def pauli_probabilities_from_qiskit_depolarizing(p: float, num_qubits: int) -> dict[str, float]:
    """Extract Pauli probabilities from Qiskit's depolarizing_error object."""

    error = depolarizing_error(float(p), int(num_qubits)).to_dict()
    probabilities: dict[str, float] = {}
    for instruction, probability in zip(
        error["instructions"],
        error["probabilities"],
        strict=True,
    ):
        label = _label_from_qiskit_instruction(instruction, int(num_qubits))
        probabilities[label] = float(probability)
    expected_size = 4 ** int(num_qubits)
    if len(probabilities) != expected_size:
        raise ValueError(f"expected {expected_size} Pauli probabilities")
    if abs(sum(probabilities.values()) - 1.0) > 1e-12:
        raise ValueError("Pauli probabilities do not sum to one")
    return probabilities


def inverse_depolarizing_quasiprobabilities(p: float, num_qubits: int) -> PauliInverseChannel:
    """Build inverse quasi-probabilities from extracted Qiskit Pauli probabilities."""

    probabilities = pauli_probabilities_from_qiskit_depolarizing(p, num_qubits)
    identity = "I" * int(num_qubits)
    non_identity_probs = [
        value for label, value in probabilities.items() if label != identity
    ]
    if not non_identity_probs:
        raise ValueError("depolarizing channel must have non-identity Paulis")
    non_identity_prob = float(np.mean(non_identity_probs))
    if max(abs(value - non_identity_prob) for value in non_identity_probs) > 1e-12:
        raise ValueError("expected uniform non-identity depolarizing probabilities")
    lambda_pauli = float(probabilities[identity] - non_identity_prob)
    if lambda_pauli <= 0.0:
        raise ValueError("channel is not invertible")
    dimension = 4 ** int(num_qubits)
    q_non_identity = (1.0 - 1.0 / lambda_pauli) / float(dimension)
    q_identity = 1.0 - (dimension - 1) * q_non_identity
    quasi = {
        label: (q_identity if label == identity else q_non_identity)
        for label in probabilities
    }
    gamma = float(sum(abs(value) for value in quasi.values()))
    sampling = {label: abs(value) / gamma for label, value in quasi.items()}
    inferred_p = float(dimension * non_identity_prob)
    return PauliInverseChannel(
        num_qubits=int(num_qubits),
        channel_probabilities=probabilities,
        quasi_probabilities=quasi,
        sampling_probabilities=sampling,
        gamma=gamma,
        inferred_p=inferred_p,
        lambda_pauli=lambda_pauli,
    )


def one_qubit_gamma_closed_form(p: float) -> float:
    """Closed-form one-qubit depolarizing inverse one-norm."""

    return float((2.0 + float(p)) / (2.0 * (1.0 - float(p))))


def _append_ideal_pauli(circuit: QuantumCircuit, label: str, qubits: tuple[int, ...]) -> None:
    for char, qubit in zip(label, qubits, strict=True):
        if char == "I":
            continue
        gate = UnitaryGate(PAULI_MATRICES[char], label=f"pec_{char.lower()}")
        circuit.append(gate, [int(qubit)])


def qaoa_gate_events(
    graph: nx.Graph,
    *,
    depth: int,
    gammas: Iterable[float],
    betas: Iterable[float],
) -> list[tuple[str, tuple[int, ...], float | None]]:
    """Return target noisy-gate events in the frozen QAOA order."""

    gamma_arr = np.asarray(list(gammas), dtype=float)
    beta_arr = np.asarray(list(betas), dtype=float)
    if gamma_arr.shape != (int(depth),) or beta_arr.shape != (int(depth),):
        raise ValueError("gammas and betas must have length depth")
    events: list[tuple[str, tuple[int, ...], float | None]] = []
    for qubit in range(graph.number_of_nodes()):
        events.append(("h", (int(qubit),), None))
    edges = sorted((int(i), int(j)) for i, j in graph.edges())
    for layer in range(int(depth)):
        for i, j in edges:
            events.append(("rzz", (i, j), 2.0 * float(gamma_arr[layer])))
        for qubit in range(graph.number_of_nodes()):
            events.append(("rx", (int(qubit),), 2.0 * float(beta_arr[layer])))
    return events


def circuit_gamma(
    graph: nx.Graph,
    *,
    depth: int,
    gammas: Iterable[float],
    betas: Iterable[float],
    p1: float = ONE_QUBIT_DEPOLARIZING,
    p2: float = TWO_QUBIT_DEPOLARIZING,
) -> float:
    """Return the PEC one-norm product for the QAOA circuit."""

    inv1 = inverse_depolarizing_quasiprobabilities(p1, 1)
    inv2 = inverse_depolarizing_quasiprobabilities(p2, 2)
    gamma = 1.0
    for _, qubits, _ in qaoa_gate_events(graph, depth=depth, gammas=gammas, betas=betas):
        gamma *= inv1.gamma if len(qubits) == 1 else inv2.gamma
    return float(gamma)


def heterogeneous_circuit_gamma(
    graph: nx.Graph,
    *,
    depth: int,
    gammas: Iterable[float],
    betas: Iterable[float],
    p1_by_qubit: dict[int, float],
    p2_by_edge: dict[tuple[int, int], float],
) -> float:
    """Return the PEC one-norm product for qubit/edge-specific depolarizing rates."""

    gamma = 1.0
    for _, qubits, _ in qaoa_gate_events(graph, depth=depth, gammas=gammas, betas=betas):
        if len(qubits) == 1:
            p = p1_by_qubit[int(qubits[0])]
            inverse = inverse_depolarizing_quasiprobabilities(p, 1)
        else:
            edge = tuple(sorted((int(qubits[0]), int(qubits[1]))))
            p = p2_by_edge[edge]
            inverse = inverse_depolarizing_quasiprobabilities(p, 2)
        gamma *= inverse.gamma
    return float(gamma)


def sampled_pec_circuit(
    graph: nx.Graph,
    *,
    depth: int,
    gammas: Iterable[float],
    betas: Iterable[float],
    inverse_1q: PauliInverseChannel,
    inverse_2q: PauliInverseChannel,
    rng: np.random.Generator,
) -> tuple[QuantumCircuit, int, float]:
    """Sample one PEC-corrected noisy circuit and return circuit, sign, gamma."""

    n = graph.number_of_nodes()
    circuit = QuantumCircuit(n)
    sign = 1
    gamma_total = 1.0
    events = qaoa_gate_events(graph, depth=depth, gammas=gammas, betas=betas)
    for name, qubits, angle in events:
        if name == "h":
            circuit.h(qubits[0])
        elif name == "rzz":
            circuit.rzz(float(angle), qubits[0], qubits[1])
        elif name == "rx":
            circuit.rx(float(angle), qubits[0])
        else:
            raise ValueError(f"unsupported QAOA event: {name}")
        inverse = inverse_1q if len(qubits) == 1 else inverse_2q
        labels = list(inverse.sampling_probabilities)
        probs = np.array([inverse.sampling_probabilities[label] for label in labels], dtype=float)
        label = labels[int(rng.choice(len(labels), p=probs))]
        if inverse.quasi_probabilities[label] < 0.0:
            sign *= -1
        gamma_total *= inverse.gamma
        _append_ideal_pauli(circuit, label, qubits)
    circuit.measure_all()
    return circuit, sign, float(gamma_total)


def exact_qaoa_expectation(
    graph: nx.Graph,
    *,
    depth: int,
    gammas: Iterable[float],
    betas: Iterable[float],
) -> float:
    """Exact noiseless MaxCut expectation for the target QAOA circuit."""

    circuit = qaoa_maxcut_circuit(
        graph,
        depth=depth,
        gammas=gammas,
        betas=betas,
        measure=False,
    )
    probabilities = Statevector.from_instruction(circuit).probabilities()
    return float(np.dot(probabilities, maxcut_values_for_graph(graph)))


def noisy_qaoa_expectation_aer(
    graph: nx.Graph,
    *,
    depth: int,
    gammas: Iterable[float],
    betas: Iterable[float],
    shots: int,
    p1: float,
    p2: float,
    instance_id: str,
    replicate_id: int,
) -> float:
    """Noisy QAOA expectation with explicit angles for the PEC arm."""

    rng = make_rng(
        instance_id=instance_id,
        method="Raw",
        budget=int(shots),
        replicate_id=int(replicate_id),
        stream="pec_raw_reference",
    )
    seed = int(rng.integers(1, 2**31 - 1))
    simulator = AerSimulator(
        noise_model=depolarizing_noise_model(p1=p1, p2=p2),
        seed_simulator=seed,
    )
    circuit = qaoa_maxcut_circuit(
        graph,
        depth=depth,
        gammas=gammas,
        betas=betas,
        measure=True,
    )
    counts = simulator.run(circuit, shots=int(shots)).result().get_counts()
    return counts_expectation(counts, graph)


def pec_expectation_aer(
    graph: nx.Graph,
    *,
    depth: int,
    gammas: Iterable[float],
    betas: Iterable[float],
    n_samples: int,
    shots_per_sample: int,
    p1: float = ONE_QUBIT_DEPOLARIZING,
    p2: float = TWO_QUBIT_DEPOLARIZING,
    instance_id: str = "PEC_SMOKE_P0",
    replicate_id: int = 0,
) -> PECResult:
    """Estimate the ideal expectation by PEC sampling and noisy Aer execution."""

    if n_samples <= 0 or shots_per_sample <= 0:
        raise ValueError("n_samples and shots_per_sample must be positive")
    inverse_1q = inverse_depolarizing_quasiprobabilities(p1, 1)
    inverse_2q = inverse_depolarizing_quasiprobabilities(p2, 2)
    sample_rng = make_rng(
        instance_id=instance_id,
        method="PEC",
        budget=int(shots_per_sample),
        replicate_id=int(replicate_id),
        stream="pec_quasiprob_sampling",
    )
    circuits: list[QuantumCircuit] = []
    signs: list[int] = []
    gammas_total: list[float] = []
    for _ in range(int(n_samples)):
        circuit, sign, gamma = sampled_pec_circuit(
            graph,
            depth=depth,
            gammas=gammas,
            betas=betas,
            inverse_1q=inverse_1q,
            inverse_2q=inverse_2q,
            rng=sample_rng,
        )
        circuits.append(circuit)
        signs.append(sign)
        gammas_total.append(gamma)
    aer_rng = make_rng(
        instance_id=instance_id,
        method="PEC",
        budget=int(shots_per_sample),
        replicate_id=int(replicate_id),
        stream="pec_aer_counts",
    )
    seed = int(aer_rng.integers(1, 2**31 - 1))
    simulator = AerSimulator(
        noise_model=depolarizing_noise_model(p1=p1, p2=p2),
        seed_simulator=seed,
    )
    result = simulator.run(circuits, shots=int(shots_per_sample)).result()
    values = []
    for index, (sign, gamma) in enumerate(zip(signs, gammas_total, strict=True)):
        counts = result.get_counts(index)
        values.append(float(sign) * float(gamma) * counts_expectation(counts, graph))
    target_exact = exact_qaoa_expectation(
        graph,
        depth=depth,
        gammas=gammas,
        betas=betas,
    )
    target_raw = noisy_qaoa_expectation_aer(
        graph,
        depth=depth,
        gammas=gammas,
        betas=betas,
        shots=int(n_samples) * int(shots_per_sample),
        p1=p1,
        p2=p2,
        instance_id=instance_id,
        replicate_id=replicate_id,
    )
    gamma = circuit_gamma(graph, depth=depth, gammas=gammas, betas=betas, p1=p1, p2=p2)
    return PECResult(
        target_exact=target_exact,
        target_raw=target_raw,
        target_pec=float(np.mean(values)),
        gamma=gamma,
        gamma_squared=float(gamma * gamma),
        n_samples=int(n_samples),
        shots_per_sample=int(shots_per_sample),
    )


def pec_overhead_ledger_row(
    *,
    gamma: float,
    B_nominal: int = 0,
    task: str = "pec_quasiprobability_overhead",
) -> dict:
    """Return a budget-ledger row recording C_overhead = gamma^2."""

    overhead = float(gamma) * float(gamma)
    row = {
        "method": "PEC",
        "selector": "not_applicable",
        "task": task,
        "B_nominal": int(B_nominal),
        "C_train": 0.0,
        "C_select": 0.0,
        "C_eval": 0.0,
        "C_calib": 0.0,
        "C_noiselearn": 0.0,
        "C_Sigmahat": 0.0,
        "C_overhead": overhead,
        "amortization_flag": "non_amortized",
    }
    row["C_total"] = total_cost(row)
    return row


def decision_effect_demo() -> dict:
    """Demonstrate PEC is not affine decision-trivial under gri_risk."""

    mu_ideal = np.array([0.45, 0.7], dtype=float)
    sigma_raw = np.diag([0.18, 0.24])
    lambda_raw = 0.82
    gamma = 1.35
    risk_raw = gri_risk(lambda_raw * mu_ideal, sigma_raw, B=32)
    risk_pec = gri_risk(mu_ideal, (gamma * gamma) * sigma_raw, B=32)
    return {
        "risk_raw": float(risk_raw),
        "risk_pec": float(risk_pec),
        "absolute_difference": float(abs(risk_pec - risk_raw)),
        "nontrivial": bool(abs(risk_pec - risk_raw) > 1e-6),
    }


def smoke() -> tuple[PECResult, dict]:
    """Run a small non-confirmatory PEC smoke."""

    config = load_pec_config()
    smoke_cfg = config["smoke"]
    graph = maxcut_graph(
        num_qubits=int(smoke_cfg["num_qubits"]),
        degree=int(smoke_cfg["degree"]),
        seed=int(smoke_cfg["graph_seed"]),
    )
    depth = int(smoke_cfg["depth"])
    gammas, betas = default_angles(depth)
    result = pec_expectation_aer(
        graph,
        depth=depth,
        gammas=gammas,
        betas=betas,
        n_samples=int(smoke_cfg["n_samples"]),
        shots_per_sample=int(smoke_cfg["shots_per_sample"]),
        p1=float(config["true_noise_channel"]["p1"]),
        p2=float(config["true_noise_channel"]["p2"]),
        instance_id="PEC_SMOKE_P0",
    )
    return result, decision_effect_demo()


def heterogeneous_construction_smoke(
    path: Path = HET_DERISK_CONFIG_PATH,
) -> dict[str, float | int | bool]:
    """Build the locked heterogeneous channel and report construction-only diagnostics."""

    config = load_het_pec_derisk_config(path)
    graph, p1_by_qubit, p2_by_edge, noise_model = heterogeneous_noise_model_from_config(config)
    depth = int(config["primary_cell"]["depth"])
    gammas, betas = default_angles(depth)
    gamma = heterogeneous_circuit_gamma(
        graph,
        depth=depth,
        gammas=gammas,
        betas=betas,
        p1_by_qubit=p1_by_qubit,
        p2_by_edge=p2_by_edge,
    )
    p1_values = np.array(list(p1_by_qubit.values()), dtype=float)
    p2_values = np.array(list(p2_by_edge.values()), dtype=float)
    return {
        "noise_model_built": isinstance(noise_model, NoiseModel),
        "decision_metric_computed": False,
        "num_qubits": int(graph.number_of_nodes()),
        "num_edges": int(graph.number_of_edges()),
        "p1_min": float(np.min(p1_values)),
        "p1_max": float(np.max(p1_values)),
        "p2_min": float(np.min(p2_values)),
        "p2_max": float(np.max(p2_values)),
        "gamma": float(gamma),
        "gamma_squared": float(gamma * gamma),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="run the P0 PEC smoke")
    parser.add_argument(
        "--het-smoke",
        action="store_true",
        help="build the locked heterogeneous channel without decision metrics",
    )
    args = parser.parse_args(argv)
    if args.smoke == args.het_smoke:
        parser.error("choose exactly one of --smoke or --het-smoke")
    if args.het_smoke:
        report = heterogeneous_construction_smoke()
        print("HET PEC CONSTRUCTION SMOKE PASS")
        print(f"noise_model_built={report['noise_model_built']}")
        print(f"decision_metric_computed={report['decision_metric_computed']}")
        print(f"num_qubits={report['num_qubits']}")
        print(f"num_edges={report['num_edges']}")
        print(f"p1_min={report['p1_min']:.12g}")
        print(f"p1_max={report['p1_max']:.12g}")
        print(f"p2_min={report['p2_min']:.12g}")
        print(f"p2_max={report['p2_max']:.12g}")
        print(f"gamma_heterogeneous={report['gamma']:.12g}")
        print(f"gamma_squared_heterogeneous={report['gamma_squared']:.12g}")
        return 0
    if args.smoke:
        result, decision_demo = smoke()
        print("PEC SMOKE PASS")
        print(f"target_exact={result.target_exact:.12g}")
        print(f"target_raw={result.target_raw:.12g}")
        print(f"target_pec={result.target_pec:.12g}")
        print(f"error_raw={abs(result.target_raw - result.target_exact):.12g}")
        print(f"error_pec={abs(result.target_pec - result.target_exact):.12g}")
        print(f"gamma={result.gamma:.12g}")
        print(f"gamma_squared={result.gamma_squared:.12g}")
        print(f"n_samples={result.n_samples}")
        print(f"shots_per_sample={result.shots_per_sample}")
        print(f"decision_risk_raw={decision_demo['risk_raw']:.12g}")
        print(f"decision_risk_pec={decision_demo['risk_pec']:.12g}")
        print(f"decision_effect_nontrivial={decision_demo['nontrivial']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
