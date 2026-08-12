"""Held-out binary-classification metrics."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    roc_auc_score,
)


METRIC_NAMES = (
    "roc_auc",
    "balanced_accuracy",
    "accuracy",
    "macro_f1",
    "brier",
    "log_loss",
)


def compute_binary_metrics(y_true: np.ndarray, y_score: np.ndarray) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=int)
    y_score = np.asarray(y_score, dtype=float).reshape(-1)
    if len(y_true) != len(y_score):
        raise ValueError("y_true and y_score length mismatch")
    if set(np.unique(y_true).tolist()) != {0, 1}:
        raise ValueError("Held-out test labels must contain both classes")
    if not np.isfinite(y_score).all() or np.any((y_score < 0) | (y_score > 1)):
        raise ValueError("y_score must contain finite probabilities in [0, 1]")
    y_pred = (y_score >= 0.5).astype(int)
    clipped = np.clip(y_score, 1e-7, 1 - 1e-7)
    return {
        "roc_auc": float(roc_auc_score(y_true, y_score)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "brier": float(brier_score_loss(y_true, y_score)),
        "log_loss": float(log_loss(y_true, np.column_stack([1 - clipped, clipped]), labels=[0, 1])),
    }
