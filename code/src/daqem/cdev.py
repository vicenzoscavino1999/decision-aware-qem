"""Uniform depolarizing channel diagnostics; legacy basis names are retained."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer.noise import NoiseModel

from daqem.noise import depolarizing_noise_model


@dataclass(frozen=True)
class PauliLindbladGenerator:
    """Legacy label for a replicate of a 1q or 2q uniform-channel probe."""

    name: str
    kind: str
    qubits: tuple[int, ...]


def sparse_pl_basis(
    *,
    num_qubits: int,
    graph_edges: Iterable[tuple[int, int]],
    include_one_qubit: bool = True,
    include_graph_edges: bool = True,
) -> list[PauliLindbladGenerator]:
    """Return probe labels; these are not spatially resolved Pauli generators."""

    if int(num_qubits)!=num_qubits or num_qubits<1:
        raise ValueError("num_qubits must be a positive integer")
    edges=set()
    for i,j in graph_edges:
        if int(i)!=i or int(j)!=j or i==j or min(i,j)<0 or max(i,j)>=num_qubits:
            raise ValueError("invalid graph edge")
        edges.add(tuple(sorted((int(i),int(j)))))
    graph_edges=edges

    generators: list[PauliLindbladGenerator] = []
    if include_one_qubit:
        for qubit in range(int(num_qubits)):
            generators.append(
                PauliLindbladGenerator(
                    name=f"1q:{qubit}",
                    kind="one_qubit",
                    qubits=(int(qubit),),
                )
            )
    if include_graph_edges:
        for left, right in sorted((int(i), int(j)) for i, j in graph_edges):
            generators.append(
                PauliLindbladGenerator(
                    name=f"2q:{left}-{right}",
                    kind="two_qubit",
                    qubits=(int(left), int(right)),
                )
            )
    return generators


def characterization_circuit(generator: PauliLindbladGenerator, depth: int) -> QuantumCircuit:
    """Build a small decay circuit for one generator and one depth."""

    if not np.isfinite(depth) or int(depth)!=depth or depth < 1:
        raise ValueError("depth must be positive")
    if generator.kind == "one_qubit":
        qc = QuantumCircuit(1, 1)
        for _ in range(int(depth)):
            qc.x(0)
            qc.barrier()
        qc.measure(0, 0)
        return qc
    if generator.kind == "two_qubit":
        qc = QuantumCircuit(2, 2)
        for _ in range(int(depth)):
            qc.cx(0, 1)
            qc.barrier()
        qc.measure([0, 1], [0, 1])
        return qc
    raise ValueError(f"unknown generator kind: {generator.kind}")


def decay_expectation_from_counts(
    counts: dict[str, int],
    generator: PauliLindbladGenerator,
    depth: int,
) -> float:
    """Estimate the signed Pauli-survival expectation from counts."""

    if not counts or any(not isinstance(v,(int,np.integer)) or v<0 for v in counts.values()):
        raise ValueError("counts must be nonnegative integers")
    width=1 if generator.kind=="one_qubit" else 2
    if any(len(str(k).replace(" ",""))!=width or set(str(k).replace(" ",""))-{'0','1'} for k in counts):
        raise ValueError("count bitstrings must match the probe width")
    shots = sum(int(value) for value in counts.values())
    if shots <= 0:
        raise ValueError("counts must contain at least one shot")
    total = 0.0
    if generator.kind == "one_qubit":
        expected = int(depth) % 2
        for bitstring, count in counts.items():
            observed = int(str(bitstring).replace(" ", "")[-1])
            total += (1.0 if observed == expected else -1.0) * int(count)
        return float(total / shots)
    if generator.kind == "two_qubit":
        for bitstring, count in counts.items():
            bits = [int(char) for char in str(bitstring).replace(" ", "")]
            parity = sum(bits) % 2
            total += (1.0 if parity == 0 else -1.0) * int(count)
        return float(total / shots)
    raise ValueError(f"unknown generator kind: {generator.kind}")


def fit_depolarizing_rate(depths: np.ndarray, expectations: np.ndarray) -> float:
    """Fit p in E[Pauli] ~= (1-p)^depth by log-linear regression."""

    d = np.asarray(depths, dtype=float)
    y = np.asarray(expectations, dtype=float)
    if d.ndim != 1 or y.ndim != 1 or d.shape != y.shape:
        raise ValueError("depths and expectations must be one-dimensional arrays with same shape")
    if not len(d) or not np.isfinite(d).all() or not np.isfinite(y).all() or np.any(abs(y)>1):
        raise ValueError("finite nonempty depths and expectations in [-1,1] required")
    if np.any(d <= 0.0) or np.any(d!=np.floor(d)):
        raise ValueError("all depths must be positive")
    clipped = np.clip(y, 1e-6, 1.0)
    slope = float(np.sum(d * np.log(clipped)) / np.sum(d * d))
    lam = float(np.exp(slope))
    return float(np.clip(1.0 - lam, 0.0, 0.95))


def aggregate_learned_rates(
    generators: list[PauliLindbladGenerator],
    learned_rates: np.ndarray,
) -> tuple[float, float]:
    """Average learned generator rates into the depolarizing p1/p2 parameters."""

    rates = np.asarray(learned_rates, dtype=float)
    if rates.shape != (len(generators),):
        raise ValueError("learned_rates shape must match generators")
    if not np.isfinite(rates).all() or np.any((rates<0)|(rates>1)):
        raise ValueError("learned rates must be finite and between zero and one")
    one = [idx for idx, gen in enumerate(generators) if gen.kind == "one_qubit"]
    two = [idx for idx, gen in enumerate(generators) if gen.kind == "two_qubit"]
    if not one or not two:
        raise ValueError("both one_qubit and two_qubit generators are required")
    return float(np.mean(rates[one])), float(np.mean(rates[two]))


def learned_depolarizing_noise_model(
    *,
    p1: float,
    p2: float,
    scale: float = 1.0,
) -> NoiseModel:
    """Build the Aer noise model induced by learned base depolarizing rates."""

    if not np.isfinite([p1,p2,scale]).all() or min(p1,p2,scale)<0 or max(p1,p2)>1:
        raise ValueError("invalid base rate or scale")
    return depolarizing_noise_model(
        p1=min(max(float(p1) * float(scale), 0.0), 0.95),
        p2=min(max(float(p2) * float(scale), 0.0), 0.95),
    )


def support_f1_score(
    true_rates: np.ndarray,
    learned_rates: np.ndarray,
    *,
    threshold: float,
) -> tuple[float, float, float]:
    """Return precision, recall, F1 for active generator support."""

    t=np.asarray(true_rates,dtype=float);l=np.asarray(learned_rates,dtype=float)
    if t.ndim!=1 or not t.size or t.shape!=l.shape or not np.isfinite(t).all() or not np.isfinite(l).all() or np.any(t<0) or np.any(l<0) or not np.isfinite(threshold) or threshold<0:
        raise ValueError("support comparison requires matching finite nonnegative vectors and threshold")
    true_active = t > float(threshold)
    learned_active = np.asarray(learned_rates, dtype=float) > float(threshold)
    tp = int(np.sum(true_active & learned_active))
    fp = int(np.sum(~true_active & learned_active))
    fn = int(np.sum(true_active & ~learned_active))
    precision = tp / float(tp + fp) if tp + fp else 1.0
    recall = tp / float(tp + fn) if tp + fn else 1.0
    if precision + recall == 0.0:
        return precision, recall, 0.0
    return precision, recall, 2.0 * precision * recall / (precision + recall)


def weighted_relative_l1_error(
    learned: np.ndarray,
    true: np.ndarray,
    weights: np.ndarray,
    *,
    eps0: float,
) -> float:
    """Weighted relative L1 error used for Gate C1."""

    learned_arr = np.asarray(learned, dtype=float)
    true_arr = np.asarray(true, dtype=float)
    weight_arr = np.asarray(weights, dtype=float)
    if learned_arr.shape != true_arr.shape or learned_arr.shape != weight_arr.shape:
        raise ValueError("learned, true, and weights must have identical shape")
    if learned_arr.ndim!=1 or not learned_arr.size or not np.isfinite(learned_arr).all() or not np.isfinite(true_arr).all() or not np.isfinite(weight_arr).all() or np.any(weight_arr<0) or not np.isfinite(eps0) or eps0<=0:
        raise ValueError("finite vectors, nonnegative weights and positive eps0 required")
    weight_sum = float(np.sum(weight_arr))
    if weight_sum <= 0.0:
        raise ValueError("weights must have positive total mass")
    normalized = weight_arr / weight_sum
    numerator = float(np.sum(normalized * np.abs(learned_arr - true_arr)))
    denominator = float(np.sum(normalized * np.abs(true_arr))) + float(eps0)
    return numerator / denominator
