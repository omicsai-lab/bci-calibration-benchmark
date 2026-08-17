"""Fixed decoding pipelines and score extraction."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.validation import check_is_fitted

from .config import ClassicalSection
from .riemann import OASCovariances, RiemannianTangentSpace


class LogVariance(BaseEstimator, TransformerMixin):
    """Channel-wise log variance per epoch."""

    def __init__(self, epsilon: float = 1e-12):
        self.epsilon = epsilon

    def fit(self, X: np.ndarray, y: np.ndarray | None = None) -> LogVariance:
        X = np.asarray(X)
        if X.ndim != 3:
            raise ValueError("X must have shape (epochs, channels, samples)")
        self.n_features_in_ = int(X.shape[1])
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        check_is_fitted(self, "n_features_in_")
        X = np.asarray(X, dtype=float)
        if X.ndim != 3 or X.shape[1] != self.n_features_in_:
            raise ValueError("X shape is incompatible with fitted LogVariance")
        return np.log(np.var(X, axis=2, ddof=1) + self.epsilon)


def _shrinkage_lda() -> LinearDiscriminantAnalysis:
    return LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")


def build_estimator(
    method: str,
    classical: ClassicalSection,
    seed: int,
    n_channels: int,
    n_times: int,
    sfreq: float,
) -> Any:
    if method == "logvar_lda":
        return make_pipeline(LogVariance(), _shrinkage_lda())
    if method == "csp_lda":
        try:
            from mne.decoding import CSP
        except ImportError as error:
            raise RuntimeError("MNE-Python is required for csp_lda") from error
        n_components = min(classical.csp_components, n_channels)
        return make_pipeline(
            CSP(
                n_components=n_components,
                reg=classical.csp_reg,
                log=True,
                norm_trace=False,
                cov_est="concat",
                transform_into="average_power",
            ),
            _shrinkage_lda(),
        )
    if method == "riemann_lr":
        return Pipeline(
            [
                ("covariances", OASCovariances()),
                (
                    "tangent_space",
                    RiemannianTangentSpace(
                        max_iter=classical.tangent_mean_max_iter,
                        tol=classical.tangent_mean_tol,
                    ),
                ),
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        C=classical.logistic_c,
                        solver="lbfgs",
                        class_weight="balanced",
                        max_iter=2000,
                        random_state=seed,
                    ),
                ),
            ]
        )
    if method == "eegnet":
        from .deep import BraindecodeEEGNetClassifier

        return BraindecodeEEGNetClassifier(
            n_channels=n_channels,
            n_times=n_times,
            sfreq=sfreq,
            random_state=seed,
        )
    raise ValueError(f"Unknown method: {method}")


def validate_training_data(X: np.ndarray, y: np.ndarray) -> None:
    X = np.asarray(X)
    y = np.asarray(y, dtype=int)
    if X.ndim != 3:
        raise ValueError("Training X must have shape (epochs, channels, samples)")
    if len(X) != len(y):
        raise ValueError("Training X/y length mismatch")
    if set(np.unique(y).tolist()) != {0, 1}:
        raise ValueError("Training data must contain both classes 0 and 1")
    if not np.isfinite(X).all():
        raise ValueError("Training data contain non-finite values")


def predict_positive_probability(estimator: Any, X: np.ndarray) -> np.ndarray:
    if hasattr(estimator, "predict_proba"):
        probabilities = np.asarray(estimator.predict_proba(X), dtype=float)
        if probabilities.ndim != 2 or probabilities.shape[1] != 2:
            raise ValueError(f"Expected binary predict_proba output, got {probabilities.shape}")
        classes = np.asarray(getattr(estimator, "classes_", [0, 1]))
        matches = np.flatnonzero(classes == 1)
        if matches.size != 1:
            raise ValueError(f"Cannot identify positive class in classes_={classes.tolist()}")
        scores = probabilities[:, int(matches[0])]
    elif hasattr(estimator, "decision_function"):
        decision = np.asarray(estimator.decision_function(X), dtype=float).reshape(-1)
        scores = 1.0 / (1.0 + np.exp(-np.clip(decision, -40, 40)))
    else:
        raise TypeError("Estimator must implement predict_proba or decision_function")
    if not np.isfinite(scores).all() or np.any((scores < 0) | (scores > 1)):
        raise ValueError("Predicted probabilities are invalid")
    return scores
