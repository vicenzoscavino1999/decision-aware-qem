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


def _psd_cholesky(Q, jitter: float = 0.0) -> np.ndarray:
    """Spectral square root L with L L.T=Q, retaining null directions.

    The legacy name is retained for compatibility; L need not be triangular.
    Absolute jitter is deliberately disallowed in the exact SOCP.
    """
    if jitter != 0:
        raise ValueError("Absolute jitter changes the optimization problem")
    sym = 0.5 * (np.asarray(Q, dtype=float) + np.asarray(Q, dtype=float).T)
    if not np.all(np.isfinite(sym)):
        raise ValueError("Q must be finite")
    vals, vecs = np.linalg.eigh(sym)
    scale = float(np.max(np.abs(vals)))
    if np.min(vals) < -1e-10 * scale:
        raise ValueError("Q must be positive semidefinite")
    return vecs * np.sqrt(np.maximum(vals, 0.0))


def decision_optimal_zne_coeffs(Q_list, mu_lower, A, rho, *, return_diagnostics=False):
    """Solve a commonly scaled SOCP and check numerical primal/dual residuals.

    Diagnostics are numerical checks, not an exact-arithmetic certificate.
    A common scaling of all normalized forms leaves the minimizer unchanged.
    """

    import cvxpy as cp

    A_arr = np.asarray(A, dtype=float)
    rho_arr = np.asarray(rho, dtype=float)
    q = A_arr.shape[1]
    mu_arr = np.broadcast_to(np.asarray(mu_lower, dtype=float), (len(Q_list),))
    if not Q_list or np.any(~np.isfinite(mu_arr)) or np.any(mu_arr <= 0):
        raise ValueError("mu_lower entries must be positive")

    normalized=[]
    for Q, mu_i in zip(Q_list, mu_arr, strict=True):
        form=np.asarray(Q,dtype=float)/float(mu_i)/float(mu_i)
        if form.shape!=(q,q) or not np.isfinite(form).all():
            raise ValueError('Invalid normalized covariance form')
        normalized.append(form)
    scale=max(float(np.max(np.abs(Q))) for Q in normalized)
    if scale==0:
        coeffs=np.linalg.lstsq(A_arr,rho_arr,rcond=None)[0]
        if not np.allclose(A_arr@coeffs,rho_arr,atol=1e-10,rtol=1e-10):
            raise ValueError('Infeasible Richardson constraints')
        info={'solver':'linear_algebra','status':'all_zero_forms','normalized_primal_objective':0.,
              'normalized_dual_objective':0.,'normalized_gap':0.,'common_scale':0.}
        return (coeffs,info) if return_diagnostics else coeffs
    roots=[_psd_cholesky(Q/scale) for Q in normalized]
    c=cp.Variable(q);u=cp.Variable()
    equality=A_arr@c==rho_arr;nonnegative=u>=0
    cones=[cp.SOC(u,L.T@c) for L in roots]
    problem=cp.Problem(cp.Minimize(u),[equality,nonnegative,*cones])
    attempts=[]
    for solver,options in [('CLARABEL',dict(tol_gap_abs=1e-10,tol_gap_rel=1e-10,tol_feas=1e-10)),
                           ('SCS',dict(eps=1e-8,max_iters=200000))]:
        try:
            problem.solve(solver=solver,**options)
        except cp.error.SolverError as exc:
            attempts.append(str(exc))
            continue
        if c.value is None or problem.status not in {'optimal','optimal_inaccurate'}:
            attempts.append(problem.status);continue
        coeffs=np.asarray(c.value,dtype=float);uv=float(u.value)
        y=np.asarray(equality.dual_value);eta=float(nonnegative.dual_value)
        ts=np.array([float(np.asarray(cone.dual_value[0]).item()) for cone in cones])
        zs=[np.asarray(cone.dual_value[1]).reshape(-1) for cone in cones]
        primal=max(float(np.linalg.norm(L.T@coeffs)) for L in roots)
        dual=-float(rho_arr@y)
        affine=float(np.linalg.norm(A_arr@coeffs-rho_arr,np.inf))
        stationarity=float(np.linalg.norm(A_arr.T@y-sum((L@z for L,z in zip(roots,zs)),start=np.zeros(q)),np.inf))
        cone_error=max([max(0.,np.linalg.norm(z)-t) for z,t in zip(zs,ts)]+[max(0.,-eta)])
        balance=abs(1-ts.sum()-eta)
        feasibility=max(0.,primal-uv,-uv)
        gap=primal-dual
        info={'solver':solver,'status':problem.status,'common_scale':scale,
              'normalized_primal_objective':primal,'normalized_dual_objective':dual,
              'normalized_gap':gap,'affine_residual':affine,'cone_residual':float(feasibility),
              'dual_cone_residual':float(cone_error),'stationarity_residual':stationarity,
              'dual_balance_residual':float(balance)}
        finite=np.isfinite(coeffs).all() and all(np.isfinite(v) for v in info.values() if isinstance(v,(float,int)))
        if (finite and affine<=1e-8*(1+np.linalg.norm(rho_arr,np.inf))
            and max(feasibility,stationarity,cone_error,balance)<=2e-7*(1+abs(primal)+np.linalg.norm(y))
            and abs(gap)<=1e-7+1e-6*max(abs(primal),abs(dual))):
            return (coeffs,info) if return_diagnostics else coeffs
        attempts.append(info)
    raise RuntimeError(f'Decision SOCP failed numerical residual checks: {attempts}')
