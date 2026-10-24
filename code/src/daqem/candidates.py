"""Frozen pilot candidate sets and noiseless QAOA-MaxCut landscapes."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import networkx as nx
import numpy as np
from qiskit.quantum_info import Statevector

from daqem.qaoa import default_angles, maxcut_graph, qaoa_maxcut_circuit
from daqem.rng import make_rng


PILOT_INSTANCE_IDS = tuple(f"P{i:03d}" for i in range(1, 9))
CONFIRMATORY_INSTANCE_IDS = tuple(f"C{i:03d}" for i in range(1, 49))
CONFIRMATORY_E2_INSTANCE_IDS = tuple(f"C{i:03d}" for i in range(1, 33))


@dataclass(frozen=True)
class CandidateLandscape:
    """Candidate angles and exact noiseless minimization truth for one instance."""

    instance_id: str
    graph_seed: int
    depth: int
    angles: np.ndarray
    ideal_values: np.ndarray
    x_star: int
    graph_edges: tuple[tuple[int, int], ...]


def graph_seed_for_instance(instance_id: str) -> int:
    """Return a stable NetworkX seed for a PAP instance id."""

    digest = hashlib.sha256(instance_id.encode("utf-8")).digest()
    return 1 + int.from_bytes(digest[:4], byteorder="big", signed=False) % (2**31 - 2)


def is_pilot_instance(instance_id: str) -> bool:
    """Return True when an id is in the held-out pilot split."""

    return instance_id in PILOT_INSTANCE_IDS


def is_confirmatory_instance(instance_id: str) -> bool:
    """Return True when an id is in the confirmatory split."""

    return instance_id in CONFIRMATORY_INSTANCE_IDS


def is_known_instance(instance_id: str) -> bool:
    """Return True when an id belongs to a declared PAP split."""

    return is_pilot_instance(instance_id) or is_confirmatory_instance(instance_id)


def assert_pilot_instance(instance_id: str) -> None:
    """Enforce the PAP firewall: F1a may use pilot ids only."""

    if not is_pilot_instance(instance_id):
        raise ValueError(
            f"F1a uses pilot instances only; got {instance_id!r}, "
            f"confirmatory ids are disjoint"
        )


def assert_known_instance(instance_id: str) -> None:
    """Enforce that helper code only builds declared PAP instances."""

    if not is_known_instance(instance_id):
        raise ValueError(
            f"unknown PAP instance id {instance_id!r}; expected pilot P001..P008 "
            "or confirmatory C001..C048"
        )


def maxcut_graph_for_instance(
    instance_id: str,
    *,
    num_qubits: int = 10,
    degree: int = 3,
) -> nx.Graph:
    """Return the deterministic MaxCut graph for a pilot or confirmatory instance."""

    assert_known_instance(instance_id)
    return maxcut_graph(
        num_qubits=int(num_qubits),
        degree=int(degree),
        seed=graph_seed_for_instance(instance_id),
    )


def pilot_maxcut_graph(
    instance_id: str,
    *,
    num_qubits: int = 10,
    degree: int = 3,
) -> nx.Graph:
    """Return the deterministic MaxCut graph for a pilot instance."""

    assert_pilot_instance(instance_id)
    return maxcut_graph_for_instance(
        instance_id,
        num_qubits=num_qubits,
        degree=degree,
    )


def maxcut_values_for_graph(graph: nx.Graph) -> np.ndarray:
    """Return MaxCut values indexed by computational-basis integer."""

    n = graph.number_of_nodes()
    values = np.empty(2**n, dtype=float)
    edges = [(int(i), int(j)) for i, j in graph.edges()]
    for state in range(2**n):
        values[state] = sum(
            1 for i, j in edges if ((state >> i) & 1) != ((state >> j) & 1)
        )
    return values


def noiseless_qaoa_maxcut_expectation(
    graph: nx.Graph,
    *,
    depth: int,
    angles: np.ndarray,
) -> float:
    """Compute the exact noiseless QAOA MaxCut expectation by statevector."""

    arr = np.asarray(angles, dtype=float)
    if arr.shape != (2 * int(depth),):
        raise ValueError("angles must have shape (2 * depth,)")
    gammas = arr[:depth]
    betas = arr[depth:]
    circuit = qaoa_maxcut_circuit(
        graph,
        depth=int(depth),
        gammas=gammas,
        betas=betas,
        measure=False,
    )
    probabilities = Statevector.from_instruction(circuit).probabilities()
    return float(np.dot(probabilities, maxcut_values_for_graph(graph)))


def build_candidate_landscape(
    instance_id: str,
    *,
    candidate_count: int = 25,
    depth: int = 2,
    num_qubits: int = 10,
    graph_degree: int = 3,
    local_radius: float = 0.16,
    search_radius: float = 0.55,
    search_count: int | None = None,
) -> CandidateLandscape:
    """Build a deterministic local grid around the best noiseless pilot point.

    The paper's decision convention is minimization, so the stored ideal values
    are negative MaxCut expectations. The best candidate is sorted to index 0.
    """

    assert_pilot_instance(instance_id)
    return landscape_for_instance(
        instance_id,
        candidate_count=candidate_count,
        depth=depth,
        num_qubits=num_qubits,
        graph_degree=graph_degree,
        local_radius=local_radius,
        search_radius=search_radius,
        search_count=search_count,
    )


def build_candidate_landscape_for_graph(
    instance_id: str,
    graph: nx.Graph,
    *,
    candidate_count: int = 25,
    depth: int = 2,
    local_radius: float = 0.16,
    search_radius: float = 0.55,
    search_count: int | None = None,
) -> CandidateLandscape:
    """Build the shared deterministic candidate landscape for a fixed graph."""

    if candidate_count < 2:
        raise ValueError("candidate_count must be at least 2")
    if depth < 1:
        raise ValueError("depth must be positive")

    default_gammas, default_betas = default_angles(depth)
    base = np.concatenate([default_gammas, default_betas])
    dim = base.size
    rng = make_rng(
        instance_id=instance_id,
        method="candidate_grid",
        budget=0,
        replicate_id=0,
        stream="ideal_search",
    )

    n_search = int(search_count or max(64, 4 * candidate_count))
    search_angles = [base]
    for _ in range(n_search - 1):
        search_angles.append(base + rng.uniform(-search_radius, search_radius, size=dim))
    search_expectations = np.array(
        [
            noiseless_qaoa_maxcut_expectation(graph, depth=depth, angles=angles)
            for angles in search_angles
        ],
        dtype=float,
    )
    center = np.asarray(search_angles[int(np.argmax(search_expectations))], dtype=float)

    offsets = [np.zeros(dim, dtype=float)]
    for axis in range(dim):
        if len(offsets) >= candidate_count:
            break
        plus = np.zeros(dim, dtype=float)
        plus[axis] = local_radius
        offsets.append(plus)
        if len(offsets) >= candidate_count:
            break
        minus = np.zeros(dim, dtype=float)
        minus[axis] = -local_radius
        offsets.append(minus)
    while len(offsets) < candidate_count:
        direction = rng.normal(size=dim)
        norm = float(np.linalg.norm(direction))
        if norm == 0.0:
            continue
        offsets.append(
            direction / norm * float(rng.uniform(0.25 * local_radius, local_radius))
        )

    angles = np.vstack([center + offset for offset in offsets[:candidate_count]])
    expectations = np.array(
        [
            noiseless_qaoa_maxcut_expectation(graph, depth=depth, angles=row)
            for row in angles
        ],
        dtype=float,
    )
    ideal_values = -expectations
    order = np.argsort(ideal_values, kind="mergesort")
    sorted_angles = angles[order]
    sorted_values = ideal_values[order]
    edges = tuple(sorted((int(i), int(j)) for i, j in graph.edges()))
    return CandidateLandscape(
        instance_id=instance_id,
        graph_seed=graph_seed_for_instance(instance_id),
        depth=int(depth),
        angles=sorted_angles,
        ideal_values=sorted_values,
        x_star=0,
        graph_edges=edges,
    )


def landscape_for_instance(
    instance_id: str,
    *,
    candidate_count: int = 25,
    depth: int = 2,
    num_qubits: int = 10,
    graph_degree: int = 3,
    local_radius: float = 0.16,
    search_radius: float = 0.55,
    search_count: int | None = None,
) -> CandidateLandscape:
    """Build the deterministic candidate landscape for a declared PAP instance."""

    graph = maxcut_graph_for_instance(
        instance_id,
        num_qubits=num_qubits,
        degree=graph_degree,
    )
    return build_candidate_landscape_for_graph(
        instance_id,
        graph,
        candidate_count=candidate_count,
        depth=depth,
        local_radius=local_radius,
        search_radius=search_radius,
        search_count=search_count,
    )
