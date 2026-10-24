"""Dynamic Batch Candidate Optimizer helpers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class DynamicSafeguards:
    """Selector-pairing safeguards for the dynamic endpoint."""

    candidate_generation_independent_of_selector: bool = True
    same_candidates_for_DA_and_MSE: bool = True
    same_initial_points_for_DA_and_MSE: bool = True
    same_budget_grid_for_DA_and_MSE: bool = True
    same_stopping_rule_for_DA_and_MSE: bool = True
    selector_does_not_generate_candidates: bool = True

    def validate(self) -> None:
        if not all(self.__dict__.values()):
            raise ValueError("all dynamic pairing safeguards must be true")


def lexicographic_argmin(values: np.ndarray) -> int:
    """Return the first index attaining the minimum value."""

    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1 or arr.size == 0:
        raise ValueError("values must be a nonempty one-dimensional array")
    return int(np.lexsort((np.arange(arr.size), arr))[0])


def generate_candidate_batch(
    incumbent_angles: np.ndarray,
    *,
    candidates_per_round: int,
    radius: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Generate a selector-independent candidate batch around an incumbent."""

    incumbent = np.asarray(incumbent_angles, dtype=float)
    if incumbent.ndim != 1:
        raise ValueError("incumbent_angles must be one-dimensional")
    if int(candidates_per_round) < 1:
        raise ValueError("candidates_per_round must be positive")
    batch = [incumbent.copy()]
    dim = incumbent.size
    for _ in range(int(candidates_per_round) - 1):
        direction = rng.normal(size=dim)
        norm = float(np.linalg.norm(direction))
        if norm == 0.0:
            direction = np.ones(dim, dtype=float) / np.sqrt(dim)
        else:
            direction = direction / norm
        step = float(rng.uniform(0.25 * float(radius), float(radius)))
        batch.append(incumbent + step * direction)
    return np.vstack(batch)


def epsilon_opt_from_ideal_values(
    ideal_values: np.ndarray,
    *,
    quantile: float,
) -> float:
    """Set epsilon_opt from the quantile of ideal gaps above the best value."""

    values = np.asarray(ideal_values, dtype=float)
    if values.ndim != 1 or values.size == 0:
        raise ValueError("ideal_values must be a nonempty one-dimensional array")
    q = float(quantile)
    if not 0.0 <= q <= 1.0:
        raise ValueError("quantile must be in [0, 1]")
    gaps = np.maximum(values - float(np.min(values)), 0.0)
    return float(np.quantile(gaps, q))


def success_from_regret(regret: float, epsilon_opt: float) -> bool:
    """Return whether final regret is within epsilon_opt."""

    return float(regret) <= float(epsilon_opt)
