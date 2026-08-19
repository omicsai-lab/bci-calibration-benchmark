"""Leakage-resistant target-participant split construction.

The confirmatory protocol uses a fixed prospective split: the chronologically
latest complete target-participant session is held out.  Earlier sessions form
the calibration pool.  Run-level and trial-level fallbacks are available only
when a configuration explicitly requests them; neither is enabled in the
primary analysis.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedShuffleSplit

from .config import SplitSection
from .data_types import TargetSplit
from .utils import fingerprint


def _natural_key(value: object) -> tuple[object, ...]:
    text = str(value)
    parts = re.split(r"(\d+)", text)
    return tuple(int(part) if part.isdigit() else part.lower() for part in parts)


def _class_counts(y: np.ndarray, indices: np.ndarray) -> dict[int, int]:
    values, counts = np.unique(y[indices], return_counts=True)
    return dict(zip(values.astype(int).tolist(), counts.astype(int).tolist(), strict=True))


def _valid_partition(
    y: np.ndarray,
    calibration_idx: np.ndarray,
    test_idx: np.ndarray,
    minimum_test_per_class: int,
    minimum_calibration_per_class: int,
) -> bool:
    if calibration_idx.size == 0 or test_idx.size == 0:
        return False
    calibration_counts = _class_counts(y, calibration_idx)
    test_counts = _class_counts(y, test_idx)
    return (
        set(calibration_counts) == {0, 1}
        and set(test_counts) == {0, 1}
        and min(calibration_counts.values()) >= minimum_calibration_per_class
        and min(test_counts.values()) >= minimum_test_per_class
    )


def _build_split(
    metadata: pd.DataFrame,
    y: np.ndarray,
    calibration_idx: np.ndarray,
    test_idx: np.ndarray,
    strategy: str,
    details: dict[str, object],
) -> TargetSplit:
    group_id = metadata["session"].astype(str) + "::" + metadata["run"].astype(str)
    cal_groups = tuple(sorted(group_id.iloc[calibration_idx].unique().tolist(), key=_natural_key))
    test_groups = tuple(sorted(group_id.iloc[test_idx].unique().tolist(), key=_natural_key))
    if set(cal_groups).intersection(test_groups):
        raise ValueError("Internal error: group overlap while constructing split")
    payload = {
        "strategy": strategy,
        "calibration_trial_uids": sorted(metadata.iloc[calibration_idx]["trial_uid"].astype(str)),
        "test_trial_uids": sorted(metadata.iloc[test_idx]["trial_uid"].astype(str)),
        "details": details,
    }
    split = TargetSplit(
        calibration_pool_idx=np.asarray(calibration_idx, dtype=int),
        test_idx=np.asarray(test_idx, dtype=int),
        calibration_groups=cal_groups,
        test_groups=test_groups,
        strategy=strategy,
        split_id=fingerprint(payload, length=20),
        details=details,
    )
    split.validate(len(metadata), y)
    return split


def _latest_session_holdout(
    metadata: pd.DataFrame,
    y: np.ndarray,
    minimum_test_per_class: int,
    minimum_calibration_per_class: int,
) -> TargetSplit | None:
    """Hold out the strictly latest session; never search for a favorable session."""

    sessions = sorted(metadata["session"].astype(str).unique().tolist(), key=_natural_key)
    if len(sessions) < 2:
        return None
    test_session = sessions[-1]
    session_values = metadata["session"].astype(str).to_numpy()
    test_idx = np.flatnonzero(session_values == test_session)
    calibration_idx = np.flatnonzero(session_values != test_session)
    if not _valid_partition(
        y,
        calibration_idx,
        test_idx,
        minimum_test_per_class,
        minimum_calibration_per_class,
    ):
        return None
    return _build_split(
        metadata,
        y,
        calibration_idx,
        test_idx,
        strategy="latest_session_holdout",
        details={
            "test_session": test_session,
            "calibration_sessions": sessions[:-1],
            "chronological": True,
        },
    )


def _latest_run_suffix_holdout(
    metadata: pd.DataFrame,
    y: np.ndarray,
    test_fraction: float,
    minimum_test_per_class: int,
    minimum_calibration_per_class: int,
) -> TargetSplit | None:
    """Hold out a deterministic suffix of complete session/run groups.

    Among valid chronological suffixes, the selected suffix is the smallest one
    meeting the requested test fraction.  If no valid suffix reaches the target,
    the largest valid suffix below it is used.  The selection never depends on
    decoder performance.
    """

    groups = (metadata["session"].astype(str) + "::" + metadata["run"].astype(str)).to_numpy()
    ordered_groups = sorted(np.unique(groups).tolist(), key=_natural_key)
    if len(ordered_groups) < 2:
        return None

    candidates: list[tuple[float, int, np.ndarray, np.ndarray, list[str]]] = []
    for suffix_size in range(1, len(ordered_groups)):
        test_groups = ordered_groups[-suffix_size:]
        is_test = np.isin(groups, test_groups)
        test_idx = np.flatnonzero(is_test)
        calibration_idx = np.flatnonzero(~is_test)
        if not _valid_partition(
            y,
            calibration_idx,
            test_idx,
            minimum_test_per_class,
            minimum_calibration_per_class,
        ):
            continue
        observed_fraction = float(test_idx.size / len(y))
        candidates.append(
            (observed_fraction, suffix_size, calibration_idx, test_idx, test_groups)
        )

    if not candidates:
        return None
    at_or_above = [candidate for candidate in candidates if candidate[0] >= test_fraction]
    if at_or_above:
        selected = min(at_or_above, key=lambda value: (value[0] - test_fraction, value[1]))
    else:
        selected = max(candidates, key=lambda value: (value[0], -value[1]))
    observed_fraction, suffix_size, calibration_idx, test_idx, test_groups = selected
    return _build_split(
        metadata,
        y,
        calibration_idx,
        test_idx,
        strategy="latest_run_suffix_holdout",
        details={
            "test_fraction_requested": float(test_fraction),
            "test_fraction_observed": observed_fraction,
            "test_groups": test_groups,
            "suffix_group_count": int(suffix_size),
            "chronological": True,
        },
    )


def _trial_level_fallback(
    metadata: pd.DataFrame,
    y: np.ndarray,
    test_fraction: float,
    minimum_test_per_class: int,
    minimum_calibration_per_class: int,
    seed: int,
) -> TargetSplit | None:
    splitter = StratifiedShuffleSplit(n_splits=64, test_size=test_fraction, random_state=seed)
    dummy = np.zeros(len(y), dtype=np.int8)
    for calibration_idx, test_idx in splitter.split(dummy, y):
        calibration_idx = np.asarray(calibration_idx, dtype=int)
        test_idx = np.asarray(test_idx, dtype=int)
        if not _valid_partition(
            y,
            calibration_idx,
            test_idx,
            minimum_test_per_class,
            minimum_calibration_per_class,
        ):
            continue
        # Trial-level fallback cannot satisfy original group disjointness. Encode
        # each trial as its own synthetic group so the exception is unmistakable.
        metadata_copy = metadata.copy()
        metadata_copy["session"] = "trial_fallback"
        metadata_copy["run"] = metadata_copy["trial_uid"].astype(str)
        return _build_split(
            metadata_copy,
            y,
            calibration_idx,
            test_idx,
            strategy="trial_level_fallback",
            details={"test_fraction_requested": float(test_fraction), "seed": int(seed)},
        )
    return None


def make_target_split(
    metadata: pd.DataFrame,
    y: np.ndarray,
    split_config: SplitSection,
    seed: int,
) -> TargetSplit:
    required = {"session", "run", "trial_uid"}
    missing = required.difference(metadata.columns)
    if missing:
        raise ValueError(f"Metadata missing split columns: {sorted(missing)}")
    y = np.asarray(y, dtype=int)
    if len(metadata) != len(y):
        raise ValueError("metadata and y length mismatch")

    split: TargetSplit | None = None
    if split_config.policy in {
        "latest_session_only",
        "latest_session_then_latest_runs",
    }:
        split = _latest_session_holdout(
            metadata,
            y,
            split_config.minimum_test_per_class,
            split_config.minimum_calibration_per_class,
        )
    if split is None and split_config.policy in {
        "latest_session_then_latest_runs",
        "latest_runs_only",
    }:
        split = _latest_run_suffix_holdout(
            metadata,
            y,
            test_fraction=split_config.test_fraction,
            minimum_test_per_class=split_config.minimum_test_per_class,
            minimum_calibration_per_class=split_config.minimum_calibration_per_class,
        )
    if split is None and split_config.allow_trial_level_fallback:
        split = _trial_level_fallback(
            metadata,
            y,
            test_fraction=split_config.test_fraction,
            minimum_test_per_class=split_config.minimum_test_per_class,
            minimum_calibration_per_class=split_config.minimum_calibration_per_class,
            seed=seed,
        )
    if split is None:
        counts = {
            "sessions": int(metadata["session"].nunique()),
            "runs": int(
                (
                    metadata["session"].astype(str)
                    + "::"
                    + metadata["run"].astype(str)
                ).nunique()
            ),
            "class_counts": _class_counts(y, np.arange(len(y), dtype=int)),
            "split_config": asdict(split_config),
        }
        raise ValueError(f"Unable to form a valid group-disjoint target split: {counts}")
    if split.strategy == "trial_level_fallback" and not split_config.allow_trial_level_fallback:
        raise AssertionError("Trial-level fallback occurred despite being disabled")
    return split


def assert_shared_split_ids(split_ids: Iterable[str]) -> None:
    values = set(split_ids)
    if len(values) != 1:
        raise ValueError(f"Methods do not share a single split_id: {sorted(values)}")
