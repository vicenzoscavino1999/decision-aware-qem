"""GRI, empirical risk, and multivariate normal probabilities.

TODO: A2
"""

from __future__ import annotations

import numpy as np
from scipy.stats import multivariate_normal, norm, Covariance
from scipy.integrate import quad
from scipy.special import log_ndtr


def _independent_incumbent_tail(threshold, covariance):
    """Stable rare tail when independent candidates share one incumbent.

    Return None for other covariance structures. For Sigma=diag(v_j)+v_0 11^T,
    condition on the incumbent's single normal variable and integrate failure
    directly. This avoids tiny multivariate-CDF rectangles whose numerical
    values can exceed their own marginal probability.
    """
    n=len(threshold)
    offdiag=covariance[~np.eye(n,dtype=bool)]
    shared=float(np.median(offdiag))
    if shared < 0 or not np.allclose(offdiag,shared,atol=0.,rtol=1e-12):
        return None
    individual=np.diag(covariance)-shared
    if np.any(individual<=0):
        return None
    if shared==0:
        return float(-np.expm1(np.sum(log_ndtr(threshold/np.sqrt(individual)))))
    marginal=norm.sf(threshold/np.sqrt(np.diag(covariance)))
    upper=float(np.sum(marginal))
    if upper==0:
        return 0.
    def integrand(z):
        log_success=np.sum(log_ndtr((threshold-np.sqrt(shared)*z)/np.sqrt(individual)))
        return float(np.exp(-z*z/2)/np.sqrt(2*np.pi)*(-np.expm1(log_success)))
    saddle=threshold*np.sqrt(shared)/(individual+shared)
    points=sorted(set([0.]+[float(z) for z in saddle if -40<z<40]))
    value,_=quad(integrand,-40.,40.,points=points,
        epsabs=max(upper*1e-11,np.finfo(float).tiny),epsrel=1e-9,limit=600)
    return float(value)


def gri_risk(mu, Sigma, B: float = 1.0, *, seed: int = 260616) -> float:
    """Gaussian risk of leaving the positive decision orthant."""

    mu_arr = np.atleast_1d(np.asarray(mu, dtype=float))
    Sigma_arr = np.atleast_2d(np.asarray(Sigma, dtype=float))
    if mu_arr.ndim != 1:
        raise ValueError("mu must be one-dimensional")
    if Sigma_arr.shape != (mu_arr.size, mu_arr.size):
        raise ValueError("Sigma must have shape (len(mu), len(mu))")
    if not np.isfinite(B) or B < 0:
        raise ValueError("B must be nonnegative")
    if not np.all(np.isfinite(mu_arr)) or not np.all(np.isfinite(Sigma_arr)):
        raise ValueError("mu and Sigma must be finite")
    if mu_arr.size == 0:
        return 0.0
    Sigma_arr = (Sigma_arr + Sigma_arr.T) / 2
    eigenvalues = np.linalg.eigvalsh(Sigma_arr)
    if eigenvalues.min() < -1e-10 * np.max(np.abs(eigenvalues)):
        raise ValueError("Sigma must be positive semidefinite")
    threshold = np.sqrt(float(B)) * mu_arr

    zero_var = np.diag(Sigma_arr) <= 0.0
    if np.any(zero_var):
        if np.any(threshold[zero_var] <= 0.0):
            return 1.0
        keep = ~zero_var
        if not np.any(keep):
            return 0.0
        return gri_risk(mu_arr[keep], Sigma_arr[np.ix_(keep, keep)], B=B, seed=seed)

    if mu_arr.size == 1:
        var = float(Sigma_arr[0, 0])
        return float(norm.sf(threshold[0] / np.sqrt(var)))
    else:
        sd = np.sqrt(np.diag(Sigma_arr))
        z = threshold / sd
        corr = Sigma_arr / np.outer(sd, sd)
        cdf_rng = np.random.default_rng(seed)
        success = float(
            multivariate_normal.cdf(
                z,
                mean=np.zeros(mu_arr.size),
                cov=corr,
                allow_singular=True,
                maxpts=1_000_000, abseps=1e-7, releps=1e-7,
                rng=cdf_rng,
            )
        )
    risk = float(np.clip(1.0-success, 0.0, 1.0))
    if risk >= 1e-7:
        return risk
    candidate_tail = _independent_incumbent_tail(threshold, Sigma_arr)
    if candidate_tail is not None:
        return candidate_tail
    # Union and Bonferroni bounds can resolve very rare events without a CDF.
    # {Zi>zi,Zj>zj} implies Zi+Zj>zi+zj, so each sum tail bounds an overlap.
    marginal=norm.sf(z)
    upper=float(np.sum(marginal))
    if upper==0:return 0.
    overlap_bound=0.
    for i in range(len(z)):
        for j in range(i):
            variance_sum=max(2.+2.*corr[i,j],0.)
            sum_bound=float(norm.sf((z[i]+z[j])/np.sqrt(variance_sum))) if variance_sum else 0.
            overlap_bound+=min(float(marginal[i]),float(marginal[j]),sum_bound)
    lower=max(float(np.max(marginal)),upper-overlap_bound)
    if upper-lower<=1e-8*upper:
        return upper  # Relative error bounded by the certified interval width.
    # Integrate each disjoint first crossing conditional on its marginal tail.
    # Pi * integral_0^1 P(Zj<=zj, j<i | Zi=isf(Pi*u)) du. Every conditional
    # probability is O(1) and every term is bounded by Pi, even when Pi is tiny.
    order=np.argsort(-marginal,kind='stable')
    z=z[order];marginal=marginal[order];corr=corr[np.ix_(order,order)]
    terms = [float(marginal[0])]
    for i in range(1,len(z)):
        remaining=float(np.sum(marginal[i:]))
        if remaining<=1e-8*upper:
            terms.append(remaining)  # Bound the omitted contribution above.
            break
        probability=float(marginal[i])
        if probability==0:continue
        conditional_tolerance=min(1e-4,max(1e-9,1e-8*upper/(len(z)*probability)))
        rho=corr[:i,i]
        cov=corr[:i,:i]-np.outer(rho,rho)
        cov=(cov+cov.T)/2
        def conditional(u):
            value=norm.isf(probability*u)
            threshold=z[:i]-rho*value
            if i==1:
                variance=max(float(cov[0,0]),0.)
                return float(norm.cdf(threshold[0]/np.sqrt(variance))) if variance else float(threshold[0]>=0.)
            return float(np.clip(multivariate_normal.cdf(threshold,mean=np.zeros(i),cov=cov,
                allow_singular=True,maxpts=1_000_000,abseps=conditional_tolerance/10,releps=conditional_tolerance/10,
                rng=np.random.default_rng(seed+i)),0.,1.))
        integral,_=quad(conditional,0.,1.,epsabs=conditional_tolerance,epsrel=conditional_tolerance,limit=150)
        terms.append(probability*float(np.clip(integral,0.,1.)))
    return float(np.clip(sum(terms), 0.0, 1.0))


def gri_covariance_gradient(mu, sigma):
    """Frobenius gradient of Gaussian orthant risk for positive definite sigma.

    Analytic conditional-normal derivatives avoid finite-difference noise and
    splitting a symmetric off-diagonal perturbation incorrectly.
    """
    mu=np.asarray(mu,dtype=float); sigma=np.asarray(sigma,dtype=float)
    if mu.ndim!=1 or sigma.shape!=(mu.size,mu.size) or not mu.size:
        raise ValueError('Incompatible nonempty mean and covariance')
    if not np.isfinite(mu).all() or not np.isfinite(sigma).all() or not np.allclose(sigma,sigma.T,rtol=1e-12,atol=0):
        raise ValueError('Covariance must be finite and symmetric')
    if np.any(np.diag(sigma)<=0):
        raise ValueError('Covariance gradient requires positive definiteness')
    sd=np.sqrt(np.diag(sigma)); z=mu/sd; corr=sigma/np.outer(sd,sd); n=len(z)
    corr=(corr+corr.T)/2;np.fill_diagonal(corr,1.)
    try:np.linalg.cholesky(corr)
    except np.linalg.LinAlgError as exc:
        raise ValueError('Covariance is not positive definite at working precision') from exc
    if np.linalg.cond(corr)>1e14:
        raise ValueError('Covariance too ill-conditioned for a double-precision gradient (condition > 1e14)')
    def conditional_cdf(indices, values):
        rest=[k for k in range(n) if k not in indices]
        if not rest: return 1.0
        # Reordering and Cholesky yield a conditional covariance factor without
        # subtracting two almost equal Schur-complement matrices.
        order=indices+rest;k=len(indices)
        factor=np.linalg.cholesky(corr[np.ix_(order,order)])
        mean=factor[k:,:k]@np.linalg.solve(factor[:k,:k],values)
        conditional_factor=factor[k:,k:]
        if len(rest)==1:
            return float(norm.cdf((z[rest][0]-mean[0])/conditional_factor[0,0]))
        # Supply a known full-rank factor instead of SciPy's eigenvalue cutoff.
        covariance=Covariance.from_cholesky(conditional_factor)
        return float(multivariate_normal.cdf(z[rest],mean=mean,cov=covariance,
            rng=np.random.default_rng(260616),maxpts=1_000_000,abseps=1e-9,releps=1e-9))
    dz=np.array([norm.pdf(z[i])*conditional_cdf([i],z[[i]]) for i in range(n)])
    drho=np.zeros_like(corr)
    for i in range(n):
        for j in range(i+1,n):
            rho=corr[i,j]
            # Stable eigen-direction expression for the bivariate log density.
            log_density=(-np.log(2*np.pi)-.5*(np.log1p(-rho)+np.log1p(rho))
                         -(z[i]+z[j])**2/(4*(1+rho))-(z[i]-z[j])**2/(4*(1-rho)))
            drho[i,j]=drho[j,i]=np.exp(log_density)*conditional_cdf([i,j],z[[i,j]])
    grad=-drho/(2*np.outer(sd,sd))
    for i in range(n):
        grad[i,i]=(z[i]*dz[i]+np.dot(corr[i],drho[i]))/(2*sigma[i,i])
    return grad


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
