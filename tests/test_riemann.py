from __future__ import annotations

import numpy as np

from bci_calibration_benchmark.riemann import (
    OASCovariances,
    RiemannianTangentSpace,
    matrix_power_spd,
    riemannian_mean,
    vectorize_symmetric,
)


def test_spd_operations_preserve_positive_eigenvalues() -> None:
    matrix = np.asarray([[2.0, 0.4], [0.4, 1.0]])
    root = matrix_power_spd(matrix, 0.5)
    reconstructed = root @ root
    assert np.allclose(reconstructed, matrix, atol=1e-10)
    assert np.all(np.linalg.eigvalsh(root) > 0)


def test_covariance_tangent_pipeline_is_deterministic(binary_epochs: tuple[np.ndarray, np.ndarray]) -> None:
    X, _ = binary_epochs
    covariances = OASCovariances().fit_transform(X)
    assert covariances.shape == (len(X), 3, 3)
    assert np.all(np.linalg.eigvalsh(covariances) > 0)
    mean = riemannian_mean(covariances, max_iter=30, tol=1e-8)
    assert np.all(np.linalg.eigvalsh(mean) > 0)
    tangent = RiemannianTangentSpace(max_iter=30, tol=1e-8)
    first = tangent.fit_transform(covariances)
    second = tangent.transform(covariances)
    assert first.shape == (len(X), 6)
    assert np.allclose(first, second)
    assert vectorize_symmetric(np.eye(3)).shape == (6,)
