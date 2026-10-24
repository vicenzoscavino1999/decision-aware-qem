"""Strict decisions from integer shot sums, without floating-point tie tests."""
import numpy as np


def integer_shot_sums(means, shots):
    """Recover integer-valued MaxCut shot sums, rejecting incompatible records."""
    x = np.asarray(means, dtype=float)
    n = int(shots)
    if n <= 0 or n != shots:
        raise ValueError('Expected positive integer shots')
    sums = x * n
    rounded = np.rint(sums)
    if not np.isfinite(sums).all() or np.any(np.abs(sums) >= 2**50):
        raise ValueError('Shot sums must be finite and exactly recoverable')
    if np.any(np.abs(sums-rounded) > 16*np.finfo(float).eps*np.maximum(1,np.abs(sums))):
        raise ValueError('Primitive records are not means of integer MaxCut shot sums')
    return rounded.astype(np.int64)


def zne_decision_keys(primitive_means, shots_per_scale, *, coefficients=None):
    """Integer comparison keys for three-scale, order-one MaxCut ZNE.

    None denotes the exact minimum-norm Accuracy-ZNE weights (4,1,-2)/3.
    For learned weights use the feasible parameterization (2+t,-1-2t,t),
    where t is the stored binary floating-point coefficient. Integer arithmetic
    also preserves ties imposed by the Richardson constraints.

    Returns repetitions x candidates Python integers. A common positive
    denominator is omitted: keys can be compared across batches/rounds only
    for the SAME coefficients and per-scale shot count. They are not objective
    estimates and must not be compared across different methods or budgets.
    """
    x=np.asarray(primitive_means,dtype=float)
    if x.ndim!=3 or x.shape[1]!=3 or x.shape[2]==0:
        raise ValueError('Expected repetitions x 3 scales x candidates and positive integer shots')
    counts=integer_shot_sums(x,shots_per_scale)
    if coefficients is None:
        weights=(4,1,-2)
    else:
        c=np.asarray(coefficients,dtype=float)
        if c.shape!=(3,) or not np.isfinite(c).all() or not np.allclose(
                np.array([[1.,1.,1.],[1.,2.,3.]])@c,[1.,0.],atol=1e-8,rtol=0):
            raise ValueError('Coefficients must satisfy the order-one Richardson constraints')
        numerator,denominator=float(c[2]).as_integer_ratio()
        weights=(2*denominator+numerator,-denominator-2*numerator,numerator)
    # Python integers prevent overflow for binary-rational learned weights.
    keys=np.zeros((x.shape[0],x.shape[2]),dtype=object)
    for scale,weight in enumerate(weights):
        keys += weight * counts[:,scale,:].astype(object)
    return keys


def zne_failures(primitive_means, optimum, shots_per_scale, *, coefficients=None):
    """Count every nonpositive gap, including an exact tie, as a failure."""
    keys=zne_decision_keys(primitive_means,shots_per_scale,coefficients=coefficients)
    if int(optimum)!=optimum or not 0<=int(optimum)<keys.shape[1]:
        raise ValueError('Optimum must index a candidate')
    optimum=int(optimum)
    competitors=[i for i in range(keys.shape[1]) if i!=optimum]
    return np.any(keys[:,competitors]<=keys[:,[optimum]],axis=1)
