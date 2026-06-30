import warnings

import numpy as np
from scipy.stats import norm

from daqem.risk import empirical_risk, gri_risk, signed_exponent
from daqem.rng import make_rng


def test_gri_risk_matches_monte_carlo_small_cell():
    mu = np.array([1.2, 0.9])
    Sigma = np.array([[1.5, 0.25], [0.25, 1.1]])
    exact = gri_risk(mu, Sigma, B=1.0)

    rng = make_rng(instance_id="gri", method="Raw", budget=1, stream="mc")
    n = 200_000
    samples = rng.multivariate_normal(np.zeros(2), Sigma, size=n)
    failures = np.any(samples >= mu, axis=1)
    mc = failures.mean()
    sigma = np.sqrt(max(exact * (1.0 - exact), 1e-12) / n)
    assert abs(mc - exact) < 5.0 * sigma + 0.003


def test_signed_exponent_zero_when_any_margin_nonpositive():
    Sigma = np.eye(2)
    assert signed_exponent(np.array([1.0, 0.0]), Sigma) == 0.0
    assert signed_exponent(np.array([1.0, -0.1]), Sigma) == 0.0


def test_gri_risk_zero_variance_treats_tie_as_failure():
    assert gri_risk([1.0], [[0.0]]) == 0.0
    assert gri_risk([0.0], [[0.0]]) == 1.0
    assert gri_risk([-1.0], [[0.0]]) == 1.0


def test_gri_risk_drops_zero_variance_coordinates_without_runtime_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        risk = gri_risk([1.0, 1.0], [[1.0, 0.0], [0.0, 0.0]])
    assert np.isclose(risk, 1.0 - norm.cdf(1.0))
    assert not any(issubclass(item.category, RuntimeWarning) for item in caught)


def test_empirical_risk_mean():
    assert empirical_risk([0, 1, 1, 0]) == 0.5
