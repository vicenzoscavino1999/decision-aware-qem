import numpy as np
import pytest
from experiments.a3_pullback_frontier import _matched_budget_indices


def test_reordered_budgets_keep_their_measurements():
    assert _matched_budget_indices([256, 512, 1024], [1024, 256, 512]) == [
        (0, 1, 256), (1, 2, 512), (2, 0, 1024)]


def test_subset_requires_explicit_support():
    with pytest.raises(ValueError):
        _matched_budget_indices([256, 512], [512])
    assert _matched_budget_indices([256, 512], [512], allow_subset=True) == [(1, 0, 512)]


@pytest.mark.parametrize('bad', [[256,256], [0], [-1], [256.5], [np.nan], [np.inf], [], [[256]]])
def test_invalid_budget_axes_are_rejected(bad):
    with pytest.raises(ValueError):
        _matched_budget_indices(bad, [256])
    with pytest.raises(ValueError):
        _matched_budget_indices([256], bad)


def test_subset_without_overlap_is_rejected():
    with pytest.raises(ValueError):
        _matched_budget_indices([256], [512], allow_subset=True)
