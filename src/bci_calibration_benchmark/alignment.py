"""Training-only Euclidean Alignment (He & Wu, 2020).

Post-confirmatory exploratory robustness component. See
``docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md`` for the estimand, leakage
boundary, and the human-reviewed decisions that fixed this module's exact
mathematical form (in particular: the literal, unnormalized He-Wu
covariance ``R = mean_i(X_i X_i^T)``, with no additional per-trial
centering and no ``/n_samples`` normalization).

This module is intentionally generic: it operates on plain
``(trials, channels, samples)`` arrays and contains no dataset name,
subject ID, channel name, method name, or budget value. It is deterministic
(no random-number generator is used anywhere in this module).
"""

from __future__ import annotations

import numpy as np

from .riemann import matrix_power_spd
from .utils import fingerprint


def estimate_ea_reference(X: np.ndarray, epsilon: float = 1e-12) -> np.ndarray:
    """Estimate the Euclidean Alignment whitening reference ``R^(-1/2)``.

    ``R = mean_i(X_i X_i^T)`` over the trial axis, with no per-trial
    centering and no normalization by the number of time samples (the
    literal He-Wu formulation). The inverse square root is computed via
    ``riemann.matrix_power_spd``, which symmetrizes ``R``, floors its
    eigenvalues at ``epsilon``, and reconstructs from the eigendecomposition
    -- the same numerically audited routine already used by the confirmatory
    Riemannian tangent-space pipeline.

    Raises ``ValueError`` on an empty trial axis: a reference cannot be
    estimated from zero trials, and this must fail loudly rather than
    silently returning an identity/no-op transform. This is the concrete
    mechanism behind rejecting budget 0 for training-only target alignment.
    """
    X = np.asarray(X, dtype=float)
    if X.ndim != 3:
        raise ValueError("X must have shape (trials, channels, samples)")
    if X.shape[0] == 0:
        raise ValueError(
            "Cannot estimate a Euclidean Alignment reference from zero trials "
            "(e.g. budget 0 target calibration data is not a valid input)"
        )
    if X.shape[1] == 0:
        raise ValueError("X must have at least one channel")
    trial_covariances = np.matmul(X, np.transpose(X, (0, 2, 1)))
    R = np.mean(trial_covariances, axis=0)
    return matrix_power_spd(R, -0.5, epsilon)


def apply_ea_transform(X: np.ndarray, reference_invsqrt: np.ndarray) -> np.ndarray:
    """Apply a frozen whitening reference to every trial: ``R^(-1/2) X_i``."""
    X = np.asarray(X, dtype=float)
    if X.ndim != 3:
        raise ValueError("X must have shape (trials, channels, samples)")
    reference_invsqrt = np.asarray(reference_invsqrt, dtype=float)
    if reference_invsqrt.ndim != 2 or reference_invsqrt.shape[0] != reference_invsqrt.shape[1]:
        raise ValueError("reference_invsqrt must be a square channels x channels matrix")
    if X.shape[1] != reference_invsqrt.shape[0]:
        raise ValueError("Channel count mismatch between X and the alignment reference")
    return np.einsum("cd,ndt->nct", reference_invsqrt, X)


def reference_digest(reference_invsqrt: np.ndarray) -> str:
    """Deterministic content digest of an alignment reference matrix.

    Used for compact provenance rather than storing the (small, but
    per-participant-per-condition) matrices themselves.
    """
    matrix = np.asarray(reference_invsqrt, dtype=float)
    payload = {
        "shape": list(matrix.shape),
        # Round-trip through repr of the raw bytes so the digest is a pure
        # function of content, not of transient float formatting choices.
        "bytes_sha256": fingerprint(matrix.tobytes().hex(), length=None),
    }
    return fingerprint(payload, length=None)


def alignment_config_digest(mode: str, epsilon: float) -> str:
    return fingerprint({"mode": mode, "epsilon": float(epsilon)}, length=None)
