"""MSE and decision-aware selector logic.

TODO: A2
"""

from __future__ import annotations


def _argmin_with_lex_tiebreak(values: dict) -> str:
    if not values:
        raise ValueError("values must be nonempty")
    return min(values, key=lambda name: (values[name], name))


def mse_selector(mse_by_method: dict) -> str:
    """Select the method with minimum MSE, lexicographic tie-break."""

    return _argmin_with_lex_tiebreak(mse_by_method)


def da_selector(
    gri_by_method: dict,
    empirical_by_method: dict | None = None,
    gri_valid: bool = True,
) -> str:
    """Select by GRI, or by empirical-risk fallback when GRI is invalid."""

    if gri_valid:
        return _argmin_with_lex_tiebreak(gri_by_method)
    if empirical_by_method is None:
        raise ValueError("empirical_by_method is required when gri_valid=False")
    return _argmin_with_lex_tiebreak(empirical_by_method)
