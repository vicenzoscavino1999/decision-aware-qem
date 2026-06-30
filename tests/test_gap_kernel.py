import numpy as np

from daqem.gap_kernel import contrast_matrix, gap_kernel, nearest_psd


def test_gap_kernel_matches_matrix_formula_and_is_psd():
    rng = np.random.default_rng(0)
    M = rng.standard_normal((5, 5))
    K = M @ M.T
    L = contrast_matrix(5)
    Sigma = gap_kernel(K, L)
    assert np.allclose(Sigma, L @ K @ L.T)
    assert np.min(np.linalg.eigvalsh(Sigma)) > -1e-9


def test_gap_variance_identity_ref_zero():
    rng = np.random.default_rng(1)
    M = rng.standard_normal((4, 4))
    K = M @ M.T
    L = contrast_matrix(4, ref=0)
    Sigma = gap_kernel(K, L)
    for gap_index, i in enumerate(range(1, 4)):
        expected = K[i, i] + K[0, 0] - 2 * K[i, 0]
        assert np.isclose(Sigma[gap_index, gap_index], expected)


def test_nearest_psd_clips_negative_eigenvalues():
    M = np.array([[1.0, 2.0], [2.0, 1.0]])
    P = nearest_psd(M)
    assert np.min(np.linalg.eigvalsh(P)) >= -1e-12
