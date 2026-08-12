from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bci_calibration_benchmark.config import PreprocessingSection
from bci_calibration_benchmark.data_types import SubjectShard
from bci_calibration_benchmark.io import load_subject_shard, save_subject_shard
from bci_calibration_benchmark.provenance import package_versions


def test_subject_shard_roundtrip_and_checksum(tmp_path: Path) -> None:
    rng = np.random.default_rng(1)
    X = rng.normal(size=(8, 3, 32)).astype(np.float32)
    y = np.asarray([0, 1] * 4)
    metadata = pd.DataFrame(
        {
            "subject": ["1"] * 8,
            "session": ["0"] * 4 + ["1"] * 4,
            "run": ["0"] * 8,
            "trial_uid": [f"u{i}" for i in range(8)],
        }
    )
    shard = SubjectShard("Test", "1", X, y, metadata, ("C3", "Cz", "C4"), 128.0)
    directory = tmp_path / "subject-1"
    save_subject_shard(
        shard,
        directory,
        preprocessing=asdict(PreprocessingSection()),
        package_versions=package_versions(),
    )
    loaded = load_subject_shard(directory, mmap_mode=None, verify_checksums=True)
    assert np.array_equal(loaded.X, X)
    assert np.array_equal(loaded.y, y)
    with (directory / "y.npy").open("ab") as handle:
        handle.write(b"corruption")
    with pytest.raises(ValueError, match="Checksum"):
        load_subject_shard(directory, mmap_mode=None, verify_checksums=True)


def test_subject_shard_rejects_blank_identifiers() -> None:
    X = np.zeros((4, 3, 16), dtype=np.float32)
    y = np.asarray([0, 1, 0, 1], dtype=int)
    metadata = pd.DataFrame(
        {
            "subject": ["1"] * 4,
            "session": ["0", "0", " ", "0"],
            "run": ["0"] * 4,
            "trial_uid": [f"u{i}" for i in range(4)],
        }
    )
    shard = SubjectShard("Test", "1", X, y, metadata, ("C3", "Cz", "C4"), 128.0)
    with pytest.raises(ValueError, match="blank"):
        shard.validate()
