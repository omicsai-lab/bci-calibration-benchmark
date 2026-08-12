"""Typed data containers for processed EEG and split provenance."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SubjectShard:
    dataset: str
    subject: str
    X: np.ndarray
    y: np.ndarray
    metadata: pd.DataFrame
    channels: tuple[str, ...]
    sfreq: float
    source_dir: Path | None = None

    def validate(self) -> None:
        if not str(self.dataset).strip():
            raise ValueError("dataset must be nonempty")
        if not str(self.subject).strip():
            raise ValueError("subject must be nonempty")
        if self.X.ndim != 3:
            raise ValueError(f"X must have shape (trials, channels, samples), got {self.X.shape}")
        if self.y.ndim != 1:
            raise ValueError(f"y must be one-dimensional, got {self.y.shape}")
        n_trials = self.X.shape[0]
        if len(self.y) != n_trials or len(self.metadata) != n_trials:
            raise ValueError(
                f"Mismatched trial counts: X={n_trials}, y={len(self.y)}, metadata={len(self.metadata)}"
            )
        if self.X.shape[1] != len(self.channels):
            raise ValueError("Channel-name count does not match X")
        if not np.isfinite(self.X).all():
            raise ValueError("X contains non-finite values")
        if not np.issubdtype(np.asarray(self.y).dtype, np.integer):
            raise ValueError("y must contain integer labels")
        if not np.isfinite(np.asarray(self.y, dtype=float)).all():
            raise ValueError("y contains non-finite values")
        unique_labels = set(np.unique(self.y).tolist())
        if unique_labels != {0, 1}:
            raise ValueError(f"Expected binary labels {{0, 1}}, got {sorted(unique_labels)}")
        required = {"subject", "session", "run", "trial_uid"}
        missing = required.difference(self.metadata.columns)
        if missing:
            raise ValueError(f"Metadata missing required columns: {sorted(missing)}")
        identifier_columns = ["subject", "session", "run", "trial_uid"]
        if self.metadata[identifier_columns].isna().any().any():
            raise ValueError("Metadata identifiers cannot be missing")
        normalized = self.metadata[identifier_columns].astype(str).apply(
            lambda column: column.str.strip()
        )
        if (normalized == "").any().any():
            raise ValueError("Metadata identifiers cannot be blank")
        if self.metadata["trial_uid"].duplicated().any():
            raise ValueError("trial_uid values must be unique within a subject shard")
        metadata_subjects = set(normalized["subject"].unique())
        if metadata_subjects != {str(self.subject)}:
            raise ValueError(
                f"Metadata subject mismatch: expected {self.subject}, got {sorted(metadata_subjects)}"
            )


@dataclass(frozen=True)
class TargetSplit:
    calibration_pool_idx: np.ndarray
    test_idx: np.ndarray
    calibration_groups: tuple[str, ...]
    test_groups: tuple[str, ...]
    strategy: str
    split_id: str
    details: dict[str, Any] = field(default_factory=dict)

    def validate(self, n_trials: int, y: np.ndarray) -> None:
        cal = np.asarray(self.calibration_pool_idx, dtype=int)
        test = np.asarray(self.test_idx, dtype=int)
        if cal.size == 0 or test.size == 0:
            raise ValueError("Calibration pool and test set must both be nonempty")
        if cal.min() < 0 or test.min() < 0 or cal.max() >= n_trials or test.max() >= n_trials:
            raise ValueError("Split indices are out of range")
        if np.intersect1d(cal, test).size:
            raise ValueError("Calibration and test indices overlap")
        if set(self.calibration_groups).intersection(self.test_groups):
            raise ValueError("Calibration and test groups overlap")
        if set(np.unique(y[cal]).tolist()) != {0, 1}:
            raise ValueError("Calibration pool must contain both classes")
        if set(np.unique(y[test]).tolist()) != {0, 1}:
            raise ValueError("Test set must contain both classes")


@dataclass(frozen=True)
class CalibrationSample:
    budget_per_class: int
    indices: np.ndarray
    class_counts: dict[int, int]

    def validate(self, y: np.ndarray) -> None:
        indices = np.asarray(self.indices, dtype=int)
        if self.budget_per_class == 0:
            if indices.size:
                raise ValueError("Zero-budget calibration sample must be empty")
            return
        values, counts = np.unique(y[indices], return_counts=True)
        observed = dict(zip(values.astype(int).tolist(), counts.astype(int).tolist(), strict=True))
        expected = {0: self.budget_per_class, 1: self.budget_per_class}
        if observed != expected:
            raise ValueError(f"Calibration class counts {observed} do not match {expected}")


@dataclass(frozen=True)
class ConditionKey:
    dataset: str
    target_subject: str
    repeat: int
    method: str
    regime: str
    budget_per_class: int
    split_id: str

    def as_tuple(self) -> tuple[Any, ...]:
        return (
            self.dataset,
            self.target_subject,
            self.repeat,
            self.method,
            self.regime,
            self.budget_per_class,
            self.split_id,
        )
