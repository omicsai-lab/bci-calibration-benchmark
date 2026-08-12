from __future__ import annotations

import numpy as np
import pytest

from bci_calibration_benchmark.config import ClassicalSection
from bci_calibration_benchmark.pipelines import build_estimator, predict_positive_probability


@pytest.mark.parametrize("method", ["logvar_lda", "csp_lda", "riemann_lr"])
def test_classical_pipelines_fit_and_score(
    method: str,
    binary_epochs: tuple[np.ndarray, np.ndarray],
) -> None:
    X, y = binary_epochs
    estimator = build_estimator(
        method,
        classical=ClassicalSection(csp_components=3, tangent_mean_max_iter=20, tangent_mean_tol=1e-7),
        seed=11,
        n_channels=X.shape[1],
        n_times=X.shape[2],
        sfreq=128.0,
    )
    estimator.fit(X, y)
    scores = predict_positive_probability(estimator, X)
    assert scores.shape == (len(X),)
    assert np.isfinite(scores).all()
    assert np.all((scores >= 0) & (scores <= 1))
    assert np.asarray(estimator.classes_).tolist() == [0, 1]
