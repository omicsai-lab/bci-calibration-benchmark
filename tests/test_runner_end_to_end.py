from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd

from bci_calibration_benchmark.aggregate import aggregate_run
from bci_calibration_benchmark.runner import run_benchmark
from bci_calibration_benchmark.synthetic import build_smoke_config, generate_synthetic_dataset
from bci_calibration_benchmark.validation import audit_result_integrity


def test_small_end_to_end_run(tmp_path: Path) -> None:
    config = build_smoke_config(tmp_path, "single")
    config = replace(
        config,
        methods=("logvar_lda", "riemann_lr"),
        analysis=replace(config.analysis, bootstrap_resamples=100),
    )
    config.validate()
    generate_synthetic_dataset(
        config.experiment.processed_root,
        config.preprocessing_fingerprint,
        config.preprocessing,
    )
    output = run_benchmark(config, repository_root=Path.cwd())
    aggregate_run(config)
    audit = audit_result_integrity(config)
    assert audit["status"] == "ok"
    metrics = pd.read_csv(output / "metrics.csv")
    assert (metrics["status"] == "ok").all()
    assert audit["metric_conditions_recomputed"] == len(metrics)
    assert audit["source_trial_assignment_rows"] > 0
    assert audit["expected_conditions"] == len(metrics)
    assert (output / "summary_subject.csv").exists()
    assert (output / "pairwise_tests.csv").exists()
