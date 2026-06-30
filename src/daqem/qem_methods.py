"""Raw, Accuracy-ZNE, Decision-ZNE, optional CDR/PEC methods.

TODO: A2
"""

from __future__ import annotations

import numpy as np


def richardson_constraints(lambdas, p: int):
    """Return A, rho for Richardson constraints through order p."""

    if p < 0:
        raise ValueError("p must be nonnegative")
    lam = np.asarray(lambdas, dtype=float)
    if lam.ndim != 1:
        raise ValueError("lambdas must be one-dimensional")
    A = np.vstack([np.ones_like(lam)] + [lam**r for r in range(1, p + 1)])
    rho = np.zeros(p + 1, dtype=float)
    rho[0] = 1.0
    return A, rho


def accuracy_zne_coeffs(lambdas, p: int) -> np.ndarray:
    """Minimum-norm coefficients satisfying Richardson constraints."""

    A, rho = richardson_constraints(lambdas, p)
    coeffs = np.linalg.pinv(A) @ rho
    if not np.allclose(A @ coeffs, rho, atol=1e-10, rtol=1e-10):
        raise ValueError("Richardson constraints are infeasible for the given lambdas and p")
    return coeffs


def _psd_cholesky(Q, jitter: float = 1e-9) -> np.ndarray:
    sym = 0.5 * (np.asarray(Q, dtype=float) + np.asarray(Q, dtype=float).T)
    vals, vecs = np.linalg.eigh(sym)
    vals = np.maximum(vals, jitter)
    return np.linalg.cholesky((vecs * vals) @ vecs.T)


def decision_optimal_zne_coeffs(Q_list, mu_lower, A, rho) -> np.ndarray:
    """Solve the decision-optimal ZNE SOCP."""

    import cvxpy as cp

    A_arr = np.asarray(A, dtype=float)
    rho_arr = np.asarray(rho, dtype=float)
    q = A_arr.shape[1]
    mu_arr = np.broadcast_to(np.asarray(mu_lower, dtype=float), (len(Q_list),))
    if np.any(mu_arr <= 0):
        raise ValueError("mu_lower entries must be positive")

    c = cp.Variable(q)
    u = cp.Variable(nonneg=True)
    constraints = [A_arr @ c == rho_arr]
    for Q, mu_i in zip(Q_list, mu_arr, strict=True):
        Lc = _psd_cholesky(Q)
        constraints.append(cp.norm(Lc.T @ c, 2) <= u * float(mu_i))

    problem = cp.Problem(cp.Minimize(u), constraints)
    for solver in ("CLARABEL", "SCS", None):
        try:
            problem.solve(solver=solver) if solver else problem.solve()
        except cp.error.SolverError:
            continue
        if c.value is not None and problem.status in {"optimal", "optimal_inaccurate"}:
            coeffs = np.asarray(c.value, dtype=float)
            if not np.allclose(A_arr @ coeffs, rho_arr, atol=1e-5):
                raise ValueError("SOCP solution violates Richardson constraints")
            return coeffs
    raise RuntimeError("Decision-optimal ZNE SOCP did not solve")
