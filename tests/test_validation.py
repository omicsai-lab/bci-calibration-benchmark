from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd

from bci_calibration_benchmark.runner import run_benchmark
from bci_calibration_benchmark.synthetic import build_smoke_config, generate_synthetic_dataset
from bci_calibration_benchmark.validation import audit_result_integrity


def _small_run(tmp_path: Path, name: str):
    config = build_smoke_config(tmp_path, name)
    config = replace(
        config,
        methods=("logvar_lda",),
        split=replace(config.split, repeats=1),
    )
    config.validate()
    generate_synthetic_dataset(
        config.experiment.processed_root,
        config.preprocessing_fingerprint,
        config.preprocessing,
    )
    output = run_benchmark(config, repository_root=Path.cwd())
    return config, output


def test_audit_detects_metric_tampering(tmp_path: Path) -> None:
    config, output = _small_run(tmp_path, "metric-tampering")
    metrics_path = output / "metrics.csv"
    metrics = pd.read_csv(metrics_path)
    metrics.loc[0, "roc_auc"] = float(metrics.loc[0, "roc_auc"]) - 0.01
    metrics.to_csv(metrics_path, index=False)

    audit = audit_result_integrity(config)

    assert audit["status"] == "failed"
    assert "Stored roc_auc differs" in audit["error_message"]


def test_audit_detects_source_assignment_tampering(tmp_path: Path) -> None:
    config, output = _small_run(tmp_path, "source-tampering")
    assignments_path = output / "source_trial_assignments.csv.gz"
    assignments = pd.read_csv(assignments_path, dtype=str)
    assignments.loc[0, "trial_uid"] = f"{assignments.loc[0, 'trial_uid']}:tampered"
    assignments.to_csv(assignments_path, index=False, compression="gzip")

    audit = audit_result_integrity(config)

    assert audit["status"] == "failed"
    assert "digests do not match" in audit["error_message"]
