"""QAOA/MaxCut problem cells.

TODO: A2
"""

from __future__ import annotations

from collections.abc import Iterable

import networkx as nx
import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

from daqem.rng import make_rng


def maxcut_graph(num_qubits: int = 10, degree: int = 3, seed: int = 1) -> nx.Graph:
    """Return the deterministic random-regular MaxCut graph used for Phase 0."""

    if num_qubits < 2:
        raise ValueError("num_qubits must be at least 2")
    if degree < 1 or degree >= num_qubits:
        raise ValueError("degree must satisfy 1 <= degree < num_qubits")
    return nx.random_regular_graph(degree, num_qubits, seed=seed)


def default_angles(depth: int) -> tuple[np.ndarray, np.ndarray]:
    """Return deterministic, fixed QAOA angles for executability benchmarks."""

    if depth < 1:
        raise ValueError("depth must be positive")
    gammas = np.linspace(0.6, 0.35, depth, dtype=float)
    betas = np.linspace(0.4, 0.2, depth, dtype=float)
    return gammas, betas


def qaoa_maxcut_circuit(
    graph: nx.Graph,
    depth: int = 2,
    gammas: Iterable[float] | None = None,
    betas: Iterable[float] | None = None,
    *,
    measure: bool = True,
) -> QuantumCircuit:
    """Build a QAOA-MaxCut circuit with RZZ cost layers and RX mixers."""

    n = graph.number_of_nodes()
    if gammas is None or betas is None:
        default_gammas, default_betas = default_angles(depth)
        gammas = default_gammas if gammas is None else gammas
        betas = default_betas if betas is None else betas
    gamma_arr = np.asarray(list(gammas), dtype=float)
    beta_arr = np.asarray(list(betas), dtype=float)
    if gamma_arr.shape != (depth,) or beta_arr.shape != (depth,):
        raise ValueError("gammas and betas must have length depth")

    qc = QuantumCircuit(n)
    qc.h(range(n))
    edges = sorted((int(i), int(j)) for i, j in graph.edges())
    for layer in range(depth):
        gamma = float(gamma_arr[layer])
        beta = float(beta_arr[layer])
        for i, j in edges:
            qc.rzz(2.0 * gamma, i, j)
        for qubit in range(n):
            qc.rx(2.0 * beta, qubit)
    if measure:
        qc.measure_all()
    return qc


def maxcut_value(bitstring: str, graph: nx.Graph) -> int:
    """Compute the MaxCut value for a Qiskit count bitstring."""

    clean = bitstring.replace(" ", "")
    bits = [int(char) for char in clean[::-1]]
    return sum(1 for i, j in graph.edges() if bits[int(i)] != bits[int(j)])


def counts_expectation(counts: dict[str, int], graph: nx.Graph) -> float:
    """Estimate <C> from measurement counts."""

    shots = sum(int(v) for v in counts.values())
    if shots <= 0:
        raise ValueError("counts must contain at least one shot")
    return float(sum(maxcut_value(bitstring, graph) * count for bitstring, count in counts.items()) / shots)


def qaoa_maxcut_expectation_aer(
    graph: nx.Graph,
    *,
    depth: int = 2,
    shots: int = 1024,
    noise_model=None,
    instance_id: str = "phase0_qaoa",
    method: str = "Raw",
    replicate_id: int = 0,
    stream: str = "aer_counts",
) -> float:
    """Run the QAOA circuit on Aer and return the counts-based MaxCut expectation."""

    if shots <= 0:
        raise ValueError("shots must be positive")
    rng = make_rng(
        instance_id=instance_id,
        method=method,
        budget=int(shots),
        replicate_id=int(replicate_id),
        stream=stream,
    )
    seed = int(rng.integers(1, 2**31 - 1))
    simulator = AerSimulator(noise_model=noise_model, seed_simulator=seed)
    circuit = qaoa_maxcut_circuit(graph, depth=depth, measure=True)
    transpiled = transpile(circuit, simulator, seed_transpiler=seed)
    counts = simulator.run(transpiled, shots=int(shots)).result().get_counts()
    return counts_expectation(counts, graph)
