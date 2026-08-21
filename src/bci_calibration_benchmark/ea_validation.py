"""Result-integrity and alignment-provenance audit for the EA sensitivity.

Post-confirmatory exploratory robustness component
(``docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md``). This module only adds new,
EA-specific audit functions; it never modifies ``validation.py``'s existing
(already-audited) confirmatory checks, and it re-derives every stored metric
from stored predictions exactly the way the primary audit does, so a
tampered EA result is caught by the same class of check already trusted for
the primary/prespecified-sensitivity runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import ExperimentConfig
from .ea_runner import ALIGNMENT_MODE
from .io import list_prepared_subjects
from .metrics import METRIC_NAMES, compute_binary_metrics
from .runner import _configured_subjects
from .statistics import validate_metrics_frame
from .validation import _read_csv

CONDITION_KEY = [
    "dataset",
    "target_subject",
    "repeat",
    "method",
    "regime",
    "budget_per_class",
    "split_id",
]


def _primary_output_dir_from_manifest(output_dir: Path) -> Path:
    manifest_path = output_dir / "run_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"EA run manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    primary_dir = (manifest.get("ea_assignment_reuse") or {}).get("primary_output_dir")
    if not primary_dir:
        raise ValueError("EA run manifest does not record ea_assignment_reuse.primary_output_dir")
    return Path(primary_dir)


def _audit_ea_metric_protocol(metrics: pd.DataFrame) -> dict[str, Any]:
    validate_metrics_frame(metrics)
    successful = metrics.loc[metrics["status"] == "ok"].copy()
    successful["target_subject"] = successful["target_subject"].astype(str)

    unknown_regimes = set(successful["regime"]) - {"subject", "source_plus_target"}
    if unknown_regimes:
        raise ValueError(f"EA metrics contain regimes outside the EA design: {sorted(unknown_regimes)}")
    if "population" in set(metrics["regime"]):
        raise ValueError("EA metrics must never contain a 'population' regime row")

    if (metrics["budget_per_class"].astype(int) <= 0).any():
        raise ValueError("EA metrics contain budget_per_class <= 0; budget 0 must be structurally absent")

    if "alignment_mode" not in metrics.columns:
        raise ValueError("EA metrics.csv is missing the alignment_mode column")
    bad_mode = set(metrics["alignment_mode"].astype(str)) - {ALIGNMENT_MODE}
    if bad_mode:
        raise ValueError(f"EA metrics contain unexpected alignment_mode values: {sorted(bad_mode)}")

    split_counts = successful.groupby(["dataset", "target_subject", "repeat"], observed=True)["split_id"].nunique()
    if (split_counts != 1).any():
        bad = split_counts.loc[split_counts != 1].head(10).to_dict()
        raise ValueError(f"EA methods/regimes do not share one target split: {bad}")

    return {
        "successful_conditions": int(len(successful)),
        "failed_conditions": int((metrics["status"] != "ok").sum()),
        "participants": int(successful[["dataset", "target_subject"]].drop_duplicates().shape[0]),
    }


def _audit_ea_predictions(output_dir: Path, successful: pd.DataFrame) -> dict[str, Any]:
    predictions = _read_csv(
        output_dir / "predictions.csv.gz",
        dtype={"target_subject": str, "split_id": str, "trial_uid": str},
    )
    required = {*CONDITION_KEY, "trial_uid", "y_true", "y_score", "y_pred", "alignment_mode"}
    missing = required.difference(predictions.columns)
    if missing:
        raise ValueError(f"EA predictions.csv.gz missing columns: {sorted(missing)}")
    if predictions.empty:
        raise ValueError("EA predictions file is empty despite successful conditions")
    if predictions.duplicated(CONDITION_KEY + ["trial_uid"]).any():
        raise ValueError("Duplicate EA held-out trial predictions within a condition")
    if (pd.to_numeric(predictions["budget_per_class"], errors="raise") <= 0).any():
        raise ValueError("EA predictions contain budget_per_class <= 0")
    scores = pd.to_numeric(predictions["y_score"], errors="raise").to_numpy(dtype=float)
    if not np.isfinite(scores).all() or np.any((scores < 0) | (scores > 1)):
        raise ValueError("EA prediction probabilities are invalid")

    recomputed_rows: list[dict[str, Any]] = []
    for keys, group in predictions.groupby(CONDITION_KEY, observed=True, sort=False):
        values = dict(zip(CONDITION_KEY, keys, strict=True))
        values.update(compute_binary_metrics(group["y_true"].to_numpy(dtype=int), group["y_score"].to_numpy(dtype=float)))
        recomputed_rows.append(values)
    recomputed = pd.DataFrame(recomputed_rows)
    stored = successful[CONDITION_KEY + list(METRIC_NAMES)].copy()
    merged = stored.merge(
        recomputed, on=CONDITION_KEY, how="outer", suffixes=("_stored", "_recomputed"), indicator=True, validate="one_to_one"
    )
    if not (merged["_merge"] == "both").all():
        raise ValueError("EA stored and recomputed metric condition sets differ")
    for metric in METRIC_NAMES:
        stored_values = pd.to_numeric(merged[f"{metric}_stored"], errors="raise").to_numpy(dtype=float)
        recomputed_values = pd.to_numeric(merged[f"{metric}_recomputed"], errors="raise").to_numpy(dtype=float)
        if not np.allclose(stored_values, recomputed_values, rtol=1e-12, atol=1e-12):
            difference = np.abs(stored_values - recomputed_values)
            bad_index = int(np.argmax(difference))
            condition = merged.loc[bad_index, CONDITION_KEY].to_dict()
            raise ValueError(f"EA stored {metric} differs from predictions for {condition}")
    return {"prediction_rows": int(len(predictions)), "metric_conditions_recomputed": int(len(recomputed))}


def _audit_alignment_provenance(output_dir: Path) -> dict[str, Any]:
    source_prov = _read_csv(
        output_dir / "source_alignment_provenance.csv.gz",
        dtype={"target_subject": str, "source_subject": str},
    )
    target_prov = _read_csv(
        output_dir / "target_alignment_provenance.csv.gz",
        dtype={"target_subject": str, "split_id": str},
    )
    if source_prov.duplicated(["dataset", "target_subject", "source_subject"]).any():
        raise ValueError("Duplicate source_alignment_provenance rows")
    if (source_prov["target_subject"].astype(str) == source_prov["source_subject"].astype(str)).any():
        raise ValueError("Target participant appears in source_alignment_provenance")

    target_key = ["dataset", "target_subject", "repeat", "split_id", "budget_per_class"]
    if target_prov.duplicated(target_key).any():
        raise ValueError(
            "Duplicate target_alignment_provenance rows for the same condition group -- this is the "
            "structural guarantee that 'subject' and 'source_plus_target' share one target transform; "
            "a duplicate means that guarantee cannot be verified"
        )
    if (pd.to_numeric(target_prov["budget_per_class"], errors="raise") <= 0).any():
        raise ValueError("target_alignment_provenance contains budget_per_class <= 0")

    config_digests = set(source_prov["alignment_config_digest"].astype(str)) | set(
        target_prov["alignment_config_digest"].astype(str)
    )
    if len(config_digests) != 1:
        raise ValueError(f"Inconsistent alignment_config_digest values across provenance files: {config_digests}")

    return {
        "source_alignment_provenance_rows": int(len(source_prov)),
        "target_alignment_provenance_rows": int(len(target_prov)),
    }


def _audit_ea_condition_completeness(config: ExperimentConfig, metrics: pd.DataFrame) -> dict[str, Any]:
    positive_budgets = tuple(sorted(b for b in config.calibration.budgets_per_class if b > 0))
    total_participants = 0
    for section in config.datasets:
        prepared = list_prepared_subjects(config.processed_dir, section.name)
        total_participants += len(_configured_subjects(section, prepared))
    expected = total_participants * config.split.repeats * len(config.methods) * 2 * len(positive_budgets)
    observed = metrics[CONDITION_KEY].drop_duplicates().shape[0]
    if metrics[CONDITION_KEY].duplicated().any():
        raise ValueError("Duplicate EA metric condition rows")
    if observed != expected:
        raise ValueError(
            f"EA condition grid is incomplete or contains unexpected rows: expected={expected}, observed={observed}"
        )
    return {"expected_conditions": int(expected), "total_participants": int(total_participants)}


def _audit_assignment_reuse_report(output_dir: Path) -> dict[str, Any]:
    path = output_dir / "assignment_reuse_report.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing assignment_reuse_report.json: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("status") != "ok":
        raise ValueError(f"assignment_reuse_report.json does not report status ok: {report}")
    gate = report.get("regeneration_equality_gate") or {}
    if gate.get("status") != "ok":
        raise ValueError(f"Regeneration equality gate did not report status ok: {gate}")
    return {"assignment_reuse_report": report}


def audit_ea_result_integrity(
    config: ExperimentConfig,
    *,
    metrics: pd.DataFrame | None = None,
) -> dict[str, Any]:
    if config.alignment.mode != ALIGNMENT_MODE:
        raise ValueError(f"audit_ea_result_integrity requires alignment.mode == {ALIGNMENT_MODE!r}")
    output_dir = config.output_dir
    try:
        if metrics is None:
            metrics = _read_csv(output_dir / "metrics.csv", dtype={"target_subject": str, "split_id": str})
        else:
            metrics = metrics.copy()
            metrics["target_subject"] = metrics["target_subject"].astype(str)
            metrics["split_id"] = metrics["split_id"].astype(str)
        protocol = _audit_ea_metric_protocol(metrics)
        successful = metrics.loc[metrics["status"] == "ok"].copy()
        prediction_details: dict[str, Any] = {}
        if config.runtime.save_predictions:
            prediction_details = _audit_ea_predictions(output_dir, successful)
        provenance_details = _audit_alignment_provenance(output_dir)
        completeness = _audit_ea_condition_completeness(config, metrics)
        reuse_details = _audit_assignment_reuse_report(output_dir)
        return {
            "status": "ok",
            **protocol,
            **prediction_details,
            **provenance_details,
            **completeness,
            **reuse_details,
            "metrics_checked": list(METRIC_NAMES),
            "classification": "post_confirmatory_exploratory_robustness",
        }
    except Exception as error:
        return {
            "status": "failed",
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
