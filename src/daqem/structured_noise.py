"""Structured amplitude/phase damping noise for R1 de-risk experiments."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml
from qiskit_aer.noise import NoiseModel, amplitude_damping_error, phase_damping_error


REPO_ROOT = Path(__file__).resolve().parents[2]
R1_DERISK_CONFIG_PATH = (
    REPO_ROOT / "reproducibility" / "config" / "r1_structured_noise_derisk.yaml"
)


def load_r1_structured_noise_config(path: Path = R1_DERISK_CONFIG_PATH) -> dict:
    """Load the preregistered R1 structured-noise de-risk config."""

    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _scaled_rate(value: float, scale: float, clip: tuple[float, float]) -> float:
    low, high = clip
    return float(min(max(float(value) * float(scale), float(low)), float(high)))


def single_qubit_ad_pd_error(*, gamma_ad: float, gamma_pd: float):
    """Return amplitude damping followed by phase damping on one qubit."""

    return amplitude_damping_error(float(gamma_ad)).compose(
        phase_damping_error(float(gamma_pd))
    )


def two_qubit_ad_pd_error(*, gamma_ad: float, gamma_pd: float):
    """Return the tensor product structured channel for a two-qubit gate."""

    one_qubit = single_qubit_ad_pd_error(gamma_ad=gamma_ad, gamma_pd=gamma_pd)
    return one_qubit.tensor(one_qubit)


def structured_noise_model(
    *,
    num_qubits: int,
    graph_edges: Iterable[tuple[int, int]],
    gamma_ad: float,
    gamma_pd: float,
    scale: float,
    one_qubit_gates: Iterable[str],
    two_qubit_gates: Iterable[str],
    clipping: tuple[float, float] = (0.0, 0.95),
) -> NoiseModel:
    """Build an Aer NoiseModel for AD+PD noise at a fixed ZNE scale."""

    scaled_ad = _scaled_rate(gamma_ad, scale, clipping)
    scaled_pd = _scaled_rate(gamma_pd, scale, clipping)
    noise_model = NoiseModel()
    one_qubit_error = single_qubit_ad_pd_error(gamma_ad=scaled_ad, gamma_pd=scaled_pd)
    two_qubit_error = two_qubit_ad_pd_error(gamma_ad=scaled_ad, gamma_pd=scaled_pd)
    one_qubit_gate_list = [str(gate) for gate in one_qubit_gates]
    two_qubit_gate_list = [str(gate) for gate in two_qubit_gates]
    for qubit in range(int(num_qubits)):
        noise_model.add_quantum_error(one_qubit_error, one_qubit_gate_list, [qubit])
    for left, right in sorted(tuple(sorted((int(i), int(j)))) for i, j in graph_edges):
        noise_model.add_quantum_error(two_qubit_error, two_qubit_gate_list, [left, right])
    return noise_model


def structured_noise_model_factory(config: dict, graph):
    """Return the A3-compatible noise_model_factory(scale_idx, scale)."""

    channel = config["structured_noise_channel"]
    clipping = tuple(float(value) for value in channel["clipping"])
    graph_edges = tuple(sorted(tuple(sorted((int(i), int(j)))) for i, j in graph.edges()))

    def factory(scale_idx: int, scale: float) -> NoiseModel:
        del scale_idx
        return structured_noise_model(
            num_qubits=int(config["primary_cell"]["num_qubits"]),
            graph_edges=graph_edges,
            gamma_ad=float(channel["gamma_amplitude_damping"]),
            gamma_pd=float(channel["gamma_phase_damping"]),
            scale=float(scale),
            one_qubit_gates=channel["one_qubit_gates"],
            two_qubit_gates=channel["two_qubit_gates"],
            clipping=clipping,
        )

    return factory
