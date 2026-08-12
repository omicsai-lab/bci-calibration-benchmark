from __future__ import annotations

import numpy as np
import pytest

from bci_calibration_benchmark.config import CalibrationSection, SourceSection
from bci_calibration_benchmark.sampling import (
    choose_source_subjects,
    nested_calibration_samples,
    source_indices_for_subject,
)


def test_nested_calibration_samples_are_balanced_and_nested() -> None:
    y = np.repeat([0, 1], 20)
    samples = nested_calibration_samples(
        y,
        np.arange(len(y)),
        CalibrationSection(budgets_per_class=(0, 3, 7, 12)),
        seed=123,
    )
    assert set(samples) == {0, 3, 7, 12}
    prior: set[int] = set()
    for budget in (3, 7, 12):
        current = set(samples[budget].indices.tolist())
        assert prior.issubset(current)
        assert np.sum(y[samples[budget].indices] == 0) == budget
        assert np.sum(y[samples[budget].indices] == 1) == budget
        prior = current


def test_insufficient_budget_skip_and_error() -> None:
    y = np.repeat([0, 1], 4)
    skipped = nested_calibration_samples(
        y,
        np.arange(len(y)),
        CalibrationSection(budgets_per_class=(0, 3, 5), insufficient_budget="skip"),
        seed=1,
    )
    assert set(skipped) == {0, 3}
    with pytest.raises(ValueError, match="Insufficient"):
        nested_calibration_samples(
            y,
            np.arange(len(y)),
            CalibrationSection(budgets_per_class=(0, 5), insufficient_budget="error"),
            seed=1,
        )


def test_source_selection_excludes_target_and_balances() -> None:
    selected = choose_source_subjects(
        ["1", "2", "3", "4"],
        "2",
        SourceSection(max_subjects=2),
        seed=2,
    )
    assert "2" not in selected
    assert len(selected) == 2
    y = np.asarray([0] * 10 + [1] * 6)
    indices = source_indices_for_subject(
        y,
        SourceSection(max_trials_per_class_per_subject=5, balance_classes_within_subject=True),
        seed=3,
    )
    assert np.sum(y[indices] == 0) == 5
    assert np.sum(y[indices] == 1) == 5
