import numpy as np
import pytest

from daqem.qem_methods import (
    accuracy_zne_coeffs,
    decision_optimal_zne_coeffs,
    richardson_constraints,
)


def test_accuracy_zne_coeffs_satisfy_richardson_order_one():
    lambdas = np.array([1.0, 2.0, 3.0])
    A, rho = richardson_constraints(lambdas, p=1)
    c = accuracy_zne_coeffs(lambdas, p=1)
    assert np.allclose(A @ c, rho)
    assert np.isclose(c.sum(), 1.0)
    assert np.isclose(c @ lambdas, 0.0)


def test_accuracy_zne_coeffs_reject_infeasible_richardson_constraints():
    with pytest.raises(ValueError, match="Richardson constraints are infeasible"):
        accuracy_zne_coeffs([1.0, 2.0], p=2)


def test_decision_optimal_zne_coeffs_satisfy_richardson_order_one():
    lambdas = np.array([1.0, 2.0, 3.0])
    A, rho = richardson_constraints(lambdas, p=1)
    Q = np.diag([1.0, 0.5, 0.25]) + 1e-6 * np.eye(3)
    c = decision_optimal_zne_coeffs([Q], np.array([1.0]), A, rho)
    assert np.allclose(A @ c, rho, atol=1e-5)
    assert np.isclose(c.sum(), 1.0, atol=1e-5)
    assert np.isclose(c @ lambdas, 0.0, atol=1e-5)
