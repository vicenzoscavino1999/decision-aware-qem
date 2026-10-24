"""Gap kernel utilities: L, K, Sigma = L K L^T.

TODO: A2
"""

from __future__ import annotations

import numpy as np


def contrast_matrix(n: int, ref: int = 0) -> np.ndarray:
    """Return rows e_i - e_ref for all i != ref."""

    if n < 2:
        raise ValueError("n must be at least 2")
    if not 0 <= ref < n:
        raise ValueError("ref must be in {0, ..., n-1}")

    rows = []
    for i in range(n):
        if i == ref:
            continue
        row = np.zeros(n, dtype=float)
        row[i] = 1.0
        row[ref] = -1.0
        rows.append(row)
    return np.vstack(rows)


def gap_kernel(K, L) -> np.ndarray:
    """Compute Sigma = L K L^T."""

    K_arr = np.asarray(K, dtype=float)
    L_arr = np.asarray(L, dtype=float)
    return L_arr @ K_arr @ L_arr.T


def nearest_psd(M, jitter: float = 1e-12) -> np.ndarray:
    """Return a symmetrized PSD matrix by clipping eigenvalues."""

    M_arr = np.asarray(M, dtype=float)
    sym = 0.5 * (M_arr + M_arr.T)
    vals, vecs = np.linalg.eigh(sym)
    floor = max(float(jitter), 0.0)
    vals = np.maximum(vals, floor)
    psd = (vecs * vals) @ vecs.T
    return 0.5 * (psd + psd.T)
