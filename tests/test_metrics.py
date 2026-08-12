from __future__ import annotations

import numpy as np
import pytest

from bci_calibration_benchmark.metrics import compute_binary_metrics


def test_perfect_binary_metrics() -> None:
    y = np.asarray([0, 0, 1, 1])
    scores = np.asarray([0.01, 0.10, 0.90, 0.99])
    result = compute_binary_metrics(y, scores)
    assert result["roc_auc"] == 1.0
    assert result["balanced_accuracy"] == 1.0
    assert result["accuracy"] == 1.0
    assert result["macro_f1"] == 1.0
    assert 0 <= result["brier"] < 0.02
    assert result["log_loss"] > 0


def test_invalid_probabilities_are_rejected() -> None:
    with pytest.raises(ValueError, match="probabilities"):
        compute_binary_metrics(np.asarray([0, 1]), np.asarray([-0.1, 1.1]))
