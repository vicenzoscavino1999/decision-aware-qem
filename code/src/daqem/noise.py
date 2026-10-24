"""Noise families and parameter conventions.

TODO: A2
"""

from __future__ import annotations

from qiskit_aer.noise import NoiseModel, depolarizing_error


ONE_QUBIT_DEPOLARIZING = 0.01
TWO_QUBIT_DEPOLARIZING = 0.03


def depolarizing_noise_model(
    p1: float = ONE_QUBIT_DEPOLARIZING,
    p2: float = TWO_QUBIT_DEPOLARIZING,
) -> NoiseModel:
    """Return the smoke-tested 1q/2q depolarizing Aer noise model."""

    noise_model = NoiseModel()
    noise_model.add_all_qubit_quantum_error(
        depolarizing_error(float(p1), 1),
        ["h", "rx", "rz", "sx", "x", "u", "u1", "u2", "u3"],
    )
    noise_model.add_all_qubit_quantum_error(
        depolarizing_error(float(p2), 2),
        ["cx", "cz", "rzz"],
    )
    return noise_model
