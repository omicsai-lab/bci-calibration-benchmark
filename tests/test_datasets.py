from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from bci_calibration_benchmark.datasets import (
    DATASET_EXPECTATIONS,
    SUPPORTED_DATASETS,
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
