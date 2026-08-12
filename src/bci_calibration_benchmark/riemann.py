"""Auditable Riemannian covariance and tangent-space transformers."""

from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.covariance import OAS
from sklearn.utils.validation import check_is_fitted


def _symmetrize(matrix: np.ndarray) -> np.ndarray:
    return (matrix + matrix.T) / 2.0


def _eigh_spd(matrix: np.ndarray, epsilon: float) -> tuple[np.ndarray, np.ndarray]:
    values, vectors = np.linalg.eigh(_symmetrize(matrix))
    values = np.clip(values, epsilon, None)
    return values, vectors


def matrix_power_spd(matrix: np.ndarray, power: float, epsilon: float = 1e-12) -> np.ndarray:
    values, vectors = _eigh_spd(matrix, epsilon)
    return _symmetrize((vectors * (values**power)) @ vectors.T)


def logm_spd(matrix: np.ndarray, epsilon: float = 1e-12) -> np.ndarray:
    values, vectors = _eigh_spd(matrix, epsilon)
    return _symmetrize((vectors * np.log(values)) @ vectors.T)


def expm_symmetric(matrix: np.ndarray) -> np.ndarray:
    values, vectors = np.linalg.eigh(_symmetrize(matrix))
    return _symmetrize((vectors * np.exp(values)) @ vectors.T)


def riemannian_mean(
    covariances: np.ndarray,
    max_iter: int = 50,
    tol: float = 1e-9,
    epsilon: float = 1e-12,
) -> np.ndarray:
    covariances = np.asarray(covariances, dtype=float)
    if covariances.ndim != 3 or covariances.shape[1] != covariances.shape[2]:
        raise ValueError("covariances must have shape (epochs, channels, channels)")
    if covariances.shape[0] < 1:
        raise ValueError("At least one covariance matrix is required")
    mean = _symmetrize(np.mean(covariances, axis=0))
    mean += np.eye(mean.shape[0]) * epsilon
    for _ in range(max_iter):
        sqrt_mean = matrix_power_spd(mean, 0.5, epsilon)
        invsqrt_mean = matrix_power_spd(mean, -0.5, epsilon)
        tangent = np.mean(
            [logm_spd(invsqrt_mean @ covariance @ invsqrt_mean, epsilon) for covariance in covariances],
            axis=0,
        )
        norm = float(np.linalg.norm(tangent, ord="fro"))
        mean = _symmetrize(sqrt_mean @ expm_symmetric(tangent) @ sqrt_mean)
        if norm < tol:
            break
    return mean


def vectorize_symmetric(matrix: np.ndarray) -> np.ndarray:
    n_channels = matrix.shape[0]
    rows, cols = np.triu_indices(n_channels)
    values = matrix[rows, cols].copy()
    values[rows != cols] *= np.sqrt(2.0)
    return values


class OASCovariances(BaseEstimator, TransformerMixin):
    """Estimate one shrinkage covariance matrix per EEG epoch."""

    def __init__(self, epsilon: float = 1e-12):
        self.epsilon = epsilon

    def fit(self, X: np.ndarray, y: np.ndarray | None = None) -> "OASCovariances":
        X = np.asarray(X)
        if X.ndim != 3:
            raise ValueError("X must have shape (epochs, channels, samples)")
        self.n_features_in_ = int(X.shape[1])
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        check_is_fitted(self, "n_features_in_")
        X = np.asarray(X, dtype=float)
        if X.ndim != 3 or X.shape[1] != self.n_features_in_:
            raise ValueError("X shape is incompatible with fitted covariance transformer")
        covariances = np.empty((len(X), X.shape[1], X.shape[1]), dtype=float)
        identity = np.eye(X.shape[1])
        for index, epoch in enumerate(X):
            covariance = OAS(assume_centered=False).fit(epoch.T).covariance_
            covariances[index] = _symmetrize(covariance) + identity * self.epsilon
        return covariances


class RiemannianTangentSpace(BaseEstimator, TransformerMixin):
    """Project SPD matrices to the tangent space at the training Riemannian mean."""

    def __init__(self, max_iter: int = 50, tol: float = 1e-9, epsilon: float = 1e-12):
        self.max_iter = max_iter
        self.tol = tol
        self.epsilon = epsilon

    def fit(self, X: np.ndarray, y: np.ndarray | None = None) -> "RiemannianTangentSpace":
        X = np.asarray(X, dtype=float)
        if X.ndim != 3 or X.shape[1] != X.shape[2]:
            raise ValueError("X must contain square covariance matrices")
        self.reference_ = riemannian_mean(
            X,
            max_iter=self.max_iter,
            tol=self.tol,
            epsilon=self.epsilon,
        )
        self.reference_invsqrt_ = matrix_power_spd(self.reference_, -0.5, self.epsilon)
        self.n_features_in_ = int(X.shape[1])
        self.n_output_features_ = self.n_features_in_ * (self.n_features_in_ + 1) // 2
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        check_is_fitted(self, ("reference_", "reference_invsqrt_"))
        X = np.asarray(X, dtype=float)
        if X.ndim != 3 or X.shape[1:] != (self.n_features_in_, self.n_features_in_):
            raise ValueError("Covariance shape is incompatible with fitted tangent space")
        output = np.empty((len(X), self.n_output_features_), dtype=float)
        for index, covariance in enumerate(X):
            centered = self.reference_invsqrt_ @ covariance @ self.reference_invsqrt_
            output[index] = vectorize_symmetric(logm_spd(centered, self.epsilon))
        return output
