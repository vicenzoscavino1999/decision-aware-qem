import numpy as np

from daqem.gap_kernel import contrast_matrix


def test_contrast_matrix_shape_and_annihilates_ones():
    L = contrast_matrix(5, ref=0)
    assert L.shape == (4, 5)
    assert np.allclose(L @ np.ones(5), 0.0)


def test_contrast_matrix_row_order_ref_zero():
    L = contrast_matrix(4, ref=0)
    expected = np.array(
        [
            [-1.0, 1.0, 0.0, 0.0],
            [-1.0, 0.0, 1.0, 0.0],
            [-1.0, 0.0, 0.0, 1.0],
        ]
    )
    assert np.allclose(L, expected)
