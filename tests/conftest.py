from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def binary_epochs() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(1234)
    n_per_class = 12
    n_times = 96
    time = np.arange(n_times) / 128.0
    X = rng.normal(scale=0.5, size=(2 * n_per_class, 3, n_times))
    y = np.repeat([0, 1], n_per_class)
    for index, label in enumerate(y):
        wave = np.sin(2 * np.pi * 10 * time + rng.uniform(0, 2 * np.pi))
        if label == 0:
            X[index, 0] += 1.2 * wave
            X[index, 2] += 0.4 * wave
        else:
            X[index, 0] += 0.4 * wave
            X[index, 2] += 1.2 * wave
    return X.astype(np.float32), y.astype(int)


@pytest.fixture
def grouped_metadata() -> tuple[pd.DataFrame, np.ndarray]:
    rows = []
    labels = []
    index = 0
    for session in ("0", "1"):
        for run in ("0", "1"):
            for label in (0, 1):
                for _ in range(6):
                    rows.append(
                        {
                            "subject": "1",
                            "session": session,
                            "run": run,
                            "trial_uid": f"trial-{index}",
                        }
                    )
                    labels.append(label)
                    index += 1
    return pd.DataFrame(rows), np.asarray(labels, dtype=int)
