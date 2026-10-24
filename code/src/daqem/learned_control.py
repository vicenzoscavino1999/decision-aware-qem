"""Numerical checks for the uniform-channel covariance diagnostic."""
import numpy as np
from scipy.integrate import quad
from scipy.special import ndtr, roots_hermitenorm
from scipy.stats import norm

_GH = {n: roots_hermitenorm(n) for n in (64, 128)}


def common_incumbent_gradient(mu, sigma):
    """Full Frobenius gradient of risk for Sigma=diag(v)+s*11'.

    Conditional normal CDFs reduce to one dimension. This evaluates every
    covariance direction, including directions outside an archived active mask.
    Off-diagonal entries carry half the symmetric directional derivative.
    """
    mu=np.asarray(mu,dtype=float);sigma=np.asarray(sigma,dtype=float);n=len(mu)
    if mu.ndim!=1 or sigma.shape!=(n,n) or n<1 or not np.isfinite(mu).all() or not np.isfinite(sigma).all():
        raise ValueError('finite compatible means and covariance are required')
    if n == 1:
        variance = float(sigma[0,0])
        if variance <= 0: raise ValueError('a positive variance is required')
        z = float(mu[0]) / np.sqrt(variance)
        return np.array([[z * norm.pdf(z) / (2 * variance)]])
    s=float(np.median(sigma[~np.eye(n,dtype=bool)]))
    v=np.diag(sigma)-s
    expected=np.diag(v)+s
    if s<0 or np.any(v<=0) or not np.allclose(sigma,expected,rtol=1e-11,atol=1e-14*np.max(np.diag(sigma))):
        raise ValueError('requires positive independent variances and common nonnegative covariance')
    def conditional(indices):
        rest=np.array([j for j in range(n) if j not in indices],dtype=int)
        if not len(rest):return 1.
        latent=s/(1+s*np.sum(1/v[indices]))
        mean=latent*np.sum(mu[indices]/v[indices])
        if latent==0:return float(np.prod(ndtr((mu[rest]-mean)/np.sqrt(v[rest]))))
        def f(z):
            return np.prod(ndtr((mu[rest,None]-mean-np.sqrt(latent)*np.atleast_1d(z))/np.sqrt(v[rest,None])),axis=0)
        values=[float(np.dot(w,f(x))/np.sqrt(2*np.pi)) for x,w in _GH.values()]
        if abs(values[0]-values[1])<=1e-12:return values[1]
        return quad(lambda z:float(f(z)[0])*norm.pdf(z),-40,40,epsabs=1e-12,epsrel=1e-11,limit=300)[0]
    sd=np.sqrt(np.diag(sigma));dm=np.array([norm.pdf(mu[i]/sd[i])/sd[i]*conditional([i]) for i in range(n)])
    h=np.zeros_like(sigma)
    for i in range(n):
        for j in range(i+1,n):
            det=sigma[i,i]*sigma[j,j]-s*s
            exponent=(sigma[j,j]*mu[i]**2+sigma[i,i]*mu[j]**2-2*s*mu[i]*mu[j])/(2*det)
            h[i,j]=h[j,i]=np.exp(-exponent)/(2*np.pi*np.sqrt(det))*conditional([i,j])
    g=-h/2
    for i in range(n):g[i,i]=(mu[i]*dm[i]+np.dot(sigma[i],h[i]))/(2*sigma[i,i])
    return g


def diagnostic_interpretation(*, active, true_matches, learned_matches, gaussian_left, gaussian_right, audit):
    """Missing or inactive evidence cannot establish a positive diagnostic."""
    if not active:return 'inactive_pair'
    if gaussian_left is None or gaussian_right is None or audit in {None,'not_reported'}:
        return 'inconclusive_missing_validation'
    if not (gaussian_left and gaussian_right):return 'empirical_fallback_only'
    if 'sampling_sensitive' in audit:return 'inconclusive_sampling'
    if true_matches and not learned_matches:return 'learned_covariance_discrepancy'
    if not true_matches:return 'reference_covariance_discrepancy'
    return 'no_projected_discrepancy_detected'
