"""Deterministic calibration and source-subject sampling."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from .config import CalibrationSection, SourceSection
from .data_types import CalibrationSample


def nested_calibration_samples(
    y: np.ndarray,
    calibration_pool_idx: np.ndarray,
    calibration_config: CalibrationSection,
    seed: int,
) -> dict[int, CalibrationSample]:
    y = np.asarray(y, dtype=int)
    pool = np.asarray(calibration_pool_idx, dtype=int)
    if np.unique(pool).size != pool.size:
        raise ValueError("Calibration pool contains duplicate indices")
    rng = np.random.default_rng(seed)
    orderings: dict[int, np.ndarray] = {}
    for label in (0, 1):
        candidates = pool[y[pool] == label].copy()
        rng.shuffle(candidates)
        orderings[label] = candidates

    result: dict[int, CalibrationSample] = {}
    previous: set[int] = set()
    for budget in calibration_config.budgets_per_class:
        if budget == 0:
            sample = CalibrationSample(0, np.asarray([], dtype=int), {0: 0, 1: 0})
            sample.validate(y)
            result[budget] = sample
            continue
        if any(len(orderings[label]) < budget for label in (0, 1)):
            if calibration_config.insufficient_budget == "error":
                available = {label: len(orderings[label]) for label in (0, 1)}
                raise ValueError(f"Insufficient calibration trials for budget {budget}: {available}")
            continue
        indices = np.concatenate([orderings[0][:budget], orderings[1][:budget]])
        # Randomize presentation order without changing nested membership.
        presentation_rng = np.random.default_rng(seed + budget)
        presentation_rng.shuffle(indices)
        sample = CalibrationSample(
            budget_per_class=budget,
            indices=indices.astype(int),
            class_counts={0: budget, 1: budget},
        )
        sample.validate(y)
        current = set(indices.tolist())
        if previous and not previous.issubset(current):
            raise AssertionError("Calibration samples are not nested")
        previous = current
        result[budget] = sample
    return result


def choose_source_subjects(
    all_subjects: Sequence[str],
    target_subject: str,
    source_config: SourceSection,
    seed: int,
) -> list[str]:
    candidates = sorted(str(value) for value in all_subjects if str(value) != str(target_subject))
    if str(target_subject) in candidates:
        raise AssertionError("Target participant leaked into source candidates")
    if not candidates:
        raise ValueError("No source participants are available")
    maximum = source_config.max_subjects
    if maximum is None or maximum >= len(candidates):
        return candidates
    if maximum < 1:
        raise ValueError("source.max_subjects must be positive or null")
    rng = np.random.default_rng(seed)
    selected = rng.choice(np.asarray(candidates, dtype=object), size=maximum, replace=False)
    return sorted(str(value) for value in selected.tolist())


def source_indices_for_subject(
    y: np.ndarray,
    source_config: SourceSection,
    seed: int,
) -> np.ndarray:
    y = np.asarray(y, dtype=int)
    rng = np.random.default_rng(seed)
    by_class = {label: np.flatnonzero(y == label) for label in (0, 1)}
    if any(indices.size == 0 for indices in by_class.values()):
        raise ValueError("Each source participant must contain both classes")

    cap = source_config.max_trials_per_class_per_subject
    if source_config.balance_classes_within_subject:
        n_each = min(len(by_class[0]), len(by_class[1]))
        if cap is not None:
            n_each = min(n_each, cap)
        selected = []
        for label in (0, 1):
            indices = by_class[label].copy()
            rng.shuffle(indices)
            selected.append(indices[:n_each])
    else:
        selected = []
        for label in (0, 1):
            indices = by_class[label].copy()
            rng.shuffle(indices)
            selected.append(indices if cap is None else indices[:cap])
    output = np.concatenate(selected).astype(int)
    rng.shuffle(output)
    return output


def assert_subject_disjointness(source_subjects: Sequence[str], target_subject: str) -> None:
    if str(target_subject) in {str(value) for value in source_subjects}:
        raise ValueError("Target participant appears in source participant list")


def assert_calibration_test_disjoint(calibration_indices: np.ndarray, test_indices: np.ndarray) -> None:
    if np.intersect1d(calibration_indices, test_indices).size:
        raise ValueError("Calibration and target test trials overlap")
