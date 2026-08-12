from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd

from bci_calibration_benchmark.runner import run_benchmark
from bci_calibration_benchmark.synthetic import build_smoke_config, generate_synthetic_dataset
from bci_calibration_benchmark.validation import _read_csv, audit_result_integrity


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


def test_read_csv_round_trips_floats_exactly(tmp_path: Path) -> None:
    # Regression test: pandas' default C float parser is not guaranteed to
    # round-trip a decimal literal to its exact original float64 bit
    # pattern. For a probability near 1.0 that is clipped and log-scaled by
    # log_loss, a single 1-ULP parsing error is amplified (1/p derivative
    # near the clip boundary) into a spurious audit mismatch. See the note
    # on validation._read_csv.
    text = "0.9999999999999707"
    value = float(text)
    path = tmp_path / "floats.csv"
    path.write_text(f"y_score\n{text}\n", encoding="utf-8")

    default_parsed = float(pd.read_csv(path)["y_score"].iloc[0])
    exact_parsed = float(_read_csv(path)["y_score"].iloc[0])

    assert default_parsed != value, "fixture no longer reproduces the pandas parsing gap"
    assert exact_parsed == value
