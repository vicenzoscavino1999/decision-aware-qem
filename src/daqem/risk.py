"""GRI, empirical risk, and multivariate normal probabilities.

TODO: A2
"""

from __future__ import annotations

import numpy as np
from scipy.stats import multivariate_normal, norm


def gri_risk(mu, Sigma, B: float = 1.0) -> float:
    """Gaussian risk of leaving the positive decision orthant."""

    mu_arr = np.atleast_1d(np.asarray(mu, dtype=float))
    Sigma_arr = np.atleast_2d(np.asarray(Sigma, dtype=float))
    if mu_arr.ndim != 1:
        raise ValueError("mu must be one-dimensional")
    if Sigma_arr.shape != (mu_arr.size, mu_arr.size):
        raise ValueError("Sigma must have shape (len(mu), len(mu))")
    if B < 0:
        raise ValueError("B must be nonnegative")
    threshold = np.sqrt(float(B)) * mu_arr

    zero_var = np.diag(Sigma_arr) <= 0.0
    if np.any(zero_var):
        if np.any(threshold[zero_var] <= 0.0):
            return 1.0
        keep = ~zero_var
        if not np.any(keep):
            return 0.0
        return gri_risk(mu_arr[keep], Sigma_arr[np.ix_(keep, keep)], B=B)

    if mu_arr.size == 1:
        var = float(Sigma_arr[0, 0])
        success = float(norm(loc=0.0, scale=np.sqrt(var)).cdf(threshold[0]))
    else:
        cdf_rng = np.random.Generator(np.random.PCG64DXSM(260616))
        success = float(
            multivariate_normal.cdf(
                threshold,
                mean=np.zeros(mu_arr.size),
                cov=Sigma_arr,
                allow_singular=True,
                rng=cdf_rng,
            )
        )
    return float(np.clip(1.0 - success, 0.0, 1.0))


def signed_exponent(mu, Sigma) -> float:
    """Return the signed diagonal Gaussian exponent from the PAP."""

    mu_arr = np.atleast_1d(np.asarray(mu, dtype=float))
    if np.any(mu_arr <= 0):
        return 0.0
    diag = np.diag(np.asarray(Sigma, dtype=float))
    terms = [
        np.inf if var <= 0 else (margin * margin) / (2.0 * var)
        for margin, var in zip(mu_arr, diag, strict=True)
    ]
    return float(np.min(terms))


def empirical_risk(decision_failures) -> float:
    """Return the mean of 0/1 decision-failure indicators."""

    arr = np.asarray(decision_failures, dtype=float)
    if arr.size == 0:
        raise ValueError("decision_failures must be nonempty")
    return float(np.mean(arr))
