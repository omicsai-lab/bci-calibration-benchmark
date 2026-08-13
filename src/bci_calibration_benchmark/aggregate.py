"""Orchestration for deterministic benchmark-result aggregation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .config import ExperimentConfig
from .io import write_dataframe_atomic
from .statistics import (
    aggregate_repeats,
    build_aucc_table,
    build_pairwise_tests,
    fit_mixed_effects,
    summarize_curves,
)
from .utils import atomic_write_text, json_default, sha256_file
from .validation import audit_result_integrity


def _participant_flow(metrics: pd.DataFrame, subject_summary: pd.DataFrame) -> pd.DataFrame:
    metrics = metrics.copy()
    metrics["target_subject"] = metrics["target_subject"].astype(str)
    rows: list[dict[str, Any]] = []
    for dataset, group in metrics.groupby("dataset", sort=True, observed=True):
        successful = group.loc[group["status"] == "ok"]
        failed = group.loc[group["status"] != "ok"]
        summary_dataset = subject_summary.loc[subject_summary["dataset"] == dataset]
        rows.append(
            {
                "dataset": str(dataset),
                "participants_attempted": int(group["target_subject"].nunique()),
                "participants_with_any_success": int(successful["target_subject"].nunique()),
                "participants_with_any_failure": int(failed["target_subject"].nunique()),
                "successful_condition_rows": int(len(successful)),
                "failed_condition_rows": int(len(failed)),
                "participant_condition_summaries": int(len(summary_dataset)),
            }
        )
    return pd.DataFrame(rows)


def aggregate_run(config: ExperimentConfig) -> Path:
    output_dir = config.output_dir
    metrics_path = output_dir / "metrics.csv"
    if not metrics_path.exists():
        raise FileNotFoundError(f"Benchmark metrics not found: {metrics_path}")
    # float_precision="round_trip": pandas' default fast float parser is not
    # guaranteed bit-exact, and audit_result_integrity below recomputes
    # metrics from predictions.csv.gz (read the same way in validation.py)
    # and compares them against these values; see the note in
    # validation.py's _read_csv for how a 1-ULP parsing gap turns into a
    # spurious audit failure via log_loss's probability clipping.
    metrics = pd.read_csv(
        metrics_path,
        dtype={"target_subject": str, "split_id": str},
        float_precision="round_trip",
    )

    audit = audit_result_integrity(config, metrics=metrics)
    if audit["status"] != "ok":
        raise ValueError(f"Result-integrity audit failed: {audit}")

    subject_summary = aggregate_repeats(metrics)
    curve_summary = summarize_curves(subject_summary, config)
    aucc_subject = build_aucc_table(subject_summary, config)
    pairwise = build_pairwise_tests(subject_summary, aucc_subject, config)
    mixed_coefficients, mixed_diagnostics = fit_mixed_effects(subject_summary, config)
    flow = _participant_flow(metrics, subject_summary)

    write_dataframe_atomic(subject_summary, output_dir / "summary_subject.csv")
    write_dataframe_atomic(curve_summary, output_dir / "curve_summary.csv")
    write_dataframe_atomic(aucc_subject, output_dir / "aucc_subject.csv")
    write_dataframe_atomic(pairwise, output_dir / "pairwise_tests.csv")
    write_dataframe_atomic(mixed_coefficients, output_dir / "mixed_effects_coefficients.csv")
    write_dataframe_atomic(flow, output_dir / "participant_flow.csv")
    atomic_write_text(
        output_dir / "mixed_effects_diagnostics.json",
        json.dumps(mixed_diagnostics, indent=2, sort_keys=True, default=json_default) + "\n",
    )
    atomic_write_text(
        output_dir / "result_audit.json",
        json.dumps(audit, indent=2, sort_keys=True, default=json_default) + "\n",
    )
    manifest = {
        "schema_version": 1,
        "created_utc": datetime.now(UTC).isoformat(),
        "experiment_fingerprint": config.experiment_fingerprint,
        "input_metrics_sha256": sha256_file(metrics_path),
        "outputs": {
            filename: sha256_file(output_dir / filename)
            for filename in (
                "summary_subject.csv",
                "curve_summary.csv",
                "aucc_subject.csv",
                "pairwise_tests.csv",
                "mixed_effects_coefficients.csv",
                "mixed_effects_diagnostics.json",
                "participant_flow.csv",
                "result_audit.json",
            )
        },
    }
    atomic_write_text(
        output_dir / "aggregation_manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True, default=json_default) + "\n",
    )
    return output_dir
