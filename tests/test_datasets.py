from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from bci_calibration_benchmark.datasets import (
    DATASET_EXPECTATIONS,
    SUPPORTED_DATASETS,
    _instantiate_public_dataset,
    validate_subject_structure,
)


def _metadata(sessions: int, runs_per_session: int, per_class_per_session: int) -> tuple[pd.DataFrame, np.ndarray]:
    rows: list[dict[str, str]] = []
    labels: list[int] = []
    per_class_per_run = per_class_per_session // runs_per_session
    for session in range(sessions):
        for run in range(runs_per_session):
            for label in (0, 1):
                for _ in range(per_class_per_run):
                    rows.append({"session": str(session), "run": str(run)})
                    labels.append(label)
    return pd.DataFrame(rows), np.asarray(labels, dtype=int)


def test_dataset_registry_is_the_confirmatory_set() -> None:
    assert set(SUPPORTED_DATASETS) == {"Lee2019_MI", "BNCI2014_001", "Zhou2016"}
    assert SUPPORTED_DATASETS["Lee2019_MI"][2] == {
        "train_run": True,
        "test_run": False,
        "resting_state": False,
    }


@pytest.mark.parametrize("dataset_name", sorted(DATASET_EXPECTATIONS))
def test_pinned_dataset_structure_accepts_expected_shape(dataset_name: str) -> None:
    expectation = DATASET_EXPECTATIONS[dataset_name]
    metadata, y = _metadata(
        expectation.sessions,
        expectation.runs_per_session,
        expectation.minimum_trials_per_class_per_session,
    )
    filler_count = expectation.full_eeg_channels - 3
    channels = ("C3", "Cz", "C4", *(f"X{index}" for index in range(filler_count)))
    validate_subject_structure(dataset_name, metadata, y, channels, None)


def test_pinned_dataset_structure_rejects_session_collapse() -> None:
    expectation = DATASET_EXPECTATIONS["Zhou2016"]
    metadata, y = _metadata(
        sessions=2,
        runs_per_session=expectation.runs_per_session,
        per_class_per_session=expectation.minimum_trials_per_class_per_session,
    )
    channels = ("C3", "Cz", "C4", *(f"X{index}" for index in range(11)))
    with pytest.raises(ValueError, match="expected 3 sessions"):
        validate_subject_structure("Zhou2016", metadata, y, channels, None)


def test_three_channel_request_is_checked_exactly() -> None:
    expectation = DATASET_EXPECTATIONS["Lee2019_MI"]
    metadata, y = _metadata(
        expectation.sessions,
        expectation.runs_per_session,
        expectation.minimum_trials_per_class_per_session,
    )
    validate_subject_structure(
        "Lee2019_MI",
        metadata,
        y,
        ("C4", "C3", "Cz"),
        ("C3", "Cz", "C4"),
    )
    with pytest.raises(ValueError, match="requested channels"):
        validate_subject_structure(
            "Lee2019_MI",
            metadata,
            y,
            ("C3", "Cz", "Pz"),
            ("C3", "Cz", "C4"),
        )


class _FakeMoabbDataset:
    """Stands in for the ``_selected_sessions`` behavior moabb.datasets.Lee2019 exhibits."""

    def __init__(self, selected_sessions: list[int] | None) -> None:
        self._selected_sessions = selected_sessions


def test_lee2019_session_workaround_neutralizes_selected_sessions() -> None:
    # Regression test for a MOABB 1.5.0 bug: Lee2019 names each subject's
    # per-session data with 0-indexed keys ("0", "1") but forwards the
    # 1-indexed `sessions` constructor default ((1, 2)) as
    # `_selected_sessions`, so `BaseDataset.get_data` string-matches only
    # key "1" and silently drops the first session. See the WHY comment on
    # `_instantiate_public_dataset` in `datasets.py` for the full trace.
    dataset = _instantiate_public_dataset(
        "Lee2019_MI",
        lambda **_: _FakeMoabbDataset([1, 2]),
        {},
    )
    assert dataset._selected_sessions is None


def test_lee2019_session_workaround_fails_loudly_if_moabb_changes() -> None:
    with pytest.raises(RuntimeError, match="no longer matches"):
        _instantiate_public_dataset(
            "Lee2019_MI",
            lambda **_: _FakeMoabbDataset([1]),
            {},
        )


def test_non_lee2019_datasets_are_untouched_by_the_session_workaround() -> None:
    dataset = _instantiate_public_dataset(
        "BNCI2014_001",
        lambda **_: _FakeMoabbDataset(None),
        {},
    )
    assert dataset._selected_sessions is None
