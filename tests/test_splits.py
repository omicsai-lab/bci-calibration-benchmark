from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from bci_calibration_benchmark.config import SplitSection
from bci_calibration_benchmark.data_types import TargetSplit
from bci_calibration_benchmark.splits import make_target_split


def test_strict_latest_session_is_held_out(
    grouped_metadata: tuple[pd.DataFrame, np.ndarray],
) -> None:
    metadata, y = grouped_metadata
    split = make_target_split(
        metadata,
        y,
        SplitSection(
            policy="latest_session_only",
            test_fraction=0.3,
            repeats=1,
            minimum_test_per_class=5,
            minimum_calibration_per_class=10,
        ),
        seed=1,
    )
    assert split.strategy == "latest_session_holdout"
    assert set(metadata.iloc[split.test_idx]["session"]) == {"1"}
    assert set(metadata.iloc[split.calibration_pool_idx]["session"]) == {"0"}
    assert not set(split.calibration_groups).intersection(split.test_groups)


def test_latest_session_policy_does_not_back_select_an_earlier_session() -> None:
    rows: list[dict[str, str]] = []
    labels: list[int] = []
    trial = 0
    # Sessions 0 and 1 are balanced and individually large enough.  The latest
    # session 2 is deliberately too small; the strict policy must fail rather
    # than choose session 1 because it happens to satisfy eligibility rules.
    for session, n_per_class in (("0", 10), ("1", 10), ("2", 2)):
        for label in (0, 1):
            for _ in range(n_per_class):
                rows.append(
                    {
                        "subject": "1",
                        "session": session,
                        "run": "0",
                        "trial_uid": f"trial-{trial}",
                    }
                )
                labels.append(label)
                trial += 1
    metadata = pd.DataFrame(rows)
    y = np.asarray(labels, dtype=int)
    with pytest.raises(ValueError, match="Unable to form"):
        make_target_split(
            metadata,
            y,
            SplitSection(
                policy="latest_session_only",
                repeats=1,
                minimum_test_per_class=5,
                minimum_calibration_per_class=10,
            ),
            seed=5,
        )


def test_run_suffix_holdout_is_chronological_and_group_disjoint(
    grouped_metadata: tuple[pd.DataFrame, np.ndarray],
) -> None:
    metadata, y = grouped_metadata
    # Preserve four chronologically ordered complete groups in one session.
    metadata = metadata.copy()
    metadata["run"] = metadata["session"].astype(str) + metadata["run"].astype(str)
    metadata["session"] = "0"
    split = make_target_split(
        metadata,
        y,
        SplitSection(
            policy="latest_runs_only",
            test_fraction=0.5,
            repeats=1,
            minimum_test_per_class=5,
            minimum_calibration_per_class=10,
        ),
        seed=7,
    )
    assert split.strategy == "latest_run_suffix_holdout"
    assert split.test_groups == ("0::10", "0::11")
    assert split.calibration_groups == ("0::00", "0::01")
    assert not set(split.calibration_groups).intersection(split.test_groups)
    assert np.intersect1d(split.calibration_pool_idx, split.test_idx).size == 0


def test_overlap_is_rejected(grouped_metadata: tuple[pd.DataFrame, np.ndarray]) -> None:
    _, y = grouped_metadata
    split = TargetSplit(
        calibration_pool_idx=np.asarray([0, 1, 2, 3]),
        test_idx=np.asarray([3, 4, 5, 6]),
        calibration_groups=("a",),
        test_groups=("b",),
        strategy="invalid",
        split_id="invalid",
    )
    with pytest.raises(ValueError, match="overlap"):
        split.validate(len(y), y)
