"""Euclidean Alignment sensitivity benchmark runner.

Post-confirmatory exploratory robustness component
(``docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md``). This module never imports
or edits ``runner.run_benchmark`` itself; it reuses that module's
already-audited private row/writer helpers by reference, so the confirmatory
and prespecified-sensitivity code path is untouched by anything here.

Leakage boundary (enforced by construction, not just by convention):

- Target test trials are only ever read to be *transformed* by an already-
  frozen target reference (``split.test_idx``); they are never passed to
  ``alignment.estimate_ea_reference``.
- Source trials outside the reused, capped source-trial selection are never
  loaded into the source alignment/training pool.
- The target reference for a given (dataset, target_subject, repeat, budget)
  is computed exactly once and applied identically to both the ``subject``
  and ``source_plus_target`` regimes.
- Budget 0 is structurally absent: the loop only ever iterates over
  ``config.calibration.budgets_per_class`` values greater than zero, and
  ``alignment.estimate_ea_reference`` independently raises on an empty
  input, so even a future bug that tried to reach budget 0 would fail
  loudly rather than silently substituting an unspecified reference.
"""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Any

import numpy as np

from .alignment import (
    alignment_config_digest,
    apply_ea_transform,
    estimate_ea_reference,
    reference_digest,
)
from .assignment_reuse import (
    ReusedAssignments,
    calibration_samples_from_reused,
    load_reused_assignments,
    source_indices_from_reused,
    source_subjects_from_reused,
    target_split_from_reused,
    verify_assignment_reuse,
)
from .config import ExperimentConfig
from .data_types import ConditionKey
from .datasets import dataset_manifest_digest
from .io import list_prepared_subjects, load_subject_shard, subject_directory
from .pipelines import build_estimator, validate_training_data
from .provenance import build_run_manifest, write_run_manifest
from .runner import (
    FAILURE_COLUMNS,
    METRICS_COLUMNS,
    PREDICTION_COLUMNS,
    CSVWriter,
    _configured_subjects,
    _failed_metric_row,
    _failure_row,
    _fit_condition,
    _metric_row,
    _prediction_rows,
    _read_completed_keys,
    _read_key_set,
    _read_prediction_counts,
    _validate_compatible_shards,
    _write_predictions_once,
)
from .sampling import assert_calibration_test_disjoint, assert_subject_disjointness
from .utils import atomic_write_text, derive_seed, json_default

ALIGNMENT_MODE = "euclidean_training_only"

EA_METRICS_COLUMNS = [*METRICS_COLUMNS, "alignment_mode"]
EA_PREDICTION_COLUMNS = [*PREDICTION_COLUMNS, "alignment_mode"]

SOURCE_ALIGNMENT_PROVENANCE_COLUMNS = [
    "dataset",
    "target_subject",
    "source_subject",
    "selection_seed",
    "source_trial_count",
    "source_alignment_reference_sha256",
    "alignment_config_digest",
]

TARGET_ALIGNMENT_PROVENANCE_COLUMNS = [
    "dataset",
    "target_subject",
    "repeat",
    "split_id",
    "budget_per_class",
    "target_calibration_trial_count",
    "target_calibration_trial_uid_sha256",
    "target_alignment_reference_sha256",
    "alignment_config_digest",
]

MANAGED_FILES = [
    "metrics.csv",
    "predictions.csv.gz",
    "failures.csv",
    "source_alignment_provenance.csv.gz",
    "target_alignment_provenance.csv.gz",
    "assignment_reuse_report.json",
]


def _trial_uid_digest(uids: list[str]) -> str:
    from .utils import fingerprint

    return fingerprint(sorted(str(uid) for uid in uids), length=None)


def _initialize_or_validate_ea_manifest(
    config: ExperimentConfig,
    output_dir: Path,
    repository_root: str | Path,
    reused: ReusedAssignments,
    verify_report: dict[str, Any],
) -> None:
    manifest_path = output_dir / "run_manifest.json"
    current_dataset_digests = {
        section.name: dataset_manifest_digest(config, section.name) for section in config.datasets
    }
    ea_provenance = {
        "primary_output_dir": str(reused.primary_output_dir),
        "primary_experiment_fingerprint": reused.primary_experiment_fingerprint,
        "primary_git_commit": reused.primary_git_commit,
        "reused_assignment_file_sha256": reused.file_sha256,
        "regeneration_equality_gate": verify_report,
    }
    if not manifest_path.exists():
        manifest = build_run_manifest(config, repository_root=repository_root)
        manifest["dataset_manifest_sha256"] = current_dataset_digests
        manifest["ea_assignment_reuse"] = ea_provenance
        write_run_manifest(manifest_path, manifest)
        return
    existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    if existing.get("experiment_fingerprint") != config.experiment_fingerprint:
        raise ValueError("Existing EA run manifest fingerprint does not match configuration")
    if existing.get("preprocessing_fingerprint") != config.preprocessing_fingerprint:
        raise ValueError("Existing EA run manifest preprocessing fingerprint does not match")
    if existing.get("dataset_manifest_sha256") != current_dataset_digests:
        raise ValueError("Processed dataset manifests changed after this EA run was started")
    existing_ea = existing.get("ea_assignment_reuse") or {}
    if existing_ea.get("reused_assignment_file_sha256") != ea_provenance["reused_assignment_file_sha256"]:
        raise ValueError(
            "Existing EA run manifest reused a different primary assignment source than this invocation"
        )


def run_ea_benchmark(
    config: ExperimentConfig,
    assignment_source: str | Path,
    repository_root: str | Path = ".",
) -> Path:
    if config.alignment.mode != ALIGNMENT_MODE:
        raise ValueError(
            f"run_ea_benchmark requires alignment.mode == {ALIGNMENT_MODE!r}, "
            f"got {config.alignment.mode!r}"
        )
    config.validate()
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    if not config.runtime.resume and any((output_dir / name).exists() for name in MANAGED_FILES):
        raise FileExistsError(
            "runtime.resume is false but managed EA result files already exist; use a new experiment name"
        )

    reused = load_reused_assignments(assignment_source)
    # Fail-closed equality gate: this must complete, and must pass, before
    # any model is fit. See docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md,
    # decision 2.
    verify_report = verify_assignment_reuse(config, reused)
    atomic_write_text(
        output_dir / "assignment_reuse_report.json",
        json.dumps(
            {
                "status": "ok",
                "primary_output_dir": str(reused.primary_output_dir),
                "primary_experiment_fingerprint": reused.primary_experiment_fingerprint,
                "primary_git_commit": reused.primary_git_commit,
                "reused_assignment_file_sha256": reused.file_sha256,
                "regeneration_equality_gate": verify_report,
            },
            indent=2,
            sort_keys=True,
            default=json_default,
        )
        + "\n",
    )
    _initialize_or_validate_ea_manifest(config, output_dir, repository_root, reused, verify_report)

    metrics_path = output_dir / "metrics.csv"
    predictions_path = output_dir / "predictions.csv.gz"
    failures_path = output_dir / "failures.csv"
    source_prov_path = output_dir / "source_alignment_provenance.csv.gz"
    target_prov_path = output_dir / "target_alignment_provenance.csv.gz"

    metrics_writer = CSVWriter(metrics_path, EA_METRICS_COLUMNS)
    predictions_writer = CSVWriter(predictions_path, EA_PREDICTION_COLUMNS, gzip_output=True)
    failures_writer = CSVWriter(failures_path, FAILURE_COLUMNS)
    source_prov_writer = CSVWriter(source_prov_path, SOURCE_ALIGNMENT_PROVENANCE_COLUMNS, gzip_output=True)
    target_prov_writer = CSVWriter(target_prov_path, TARGET_ALIGNMENT_PROVENANCE_COLUMNS, gzip_output=True)

    completed = _read_completed_keys(metrics_path) if config.runtime.resume else set()
    prediction_counts = (
        _read_prediction_counts(predictions_path)
        if config.runtime.resume and config.runtime.save_predictions
        else {}
    )
    source_prov_keys = _read_key_set(source_prov_path, ["dataset", "target_subject", "source_subject"], gzip_input=True)
    target_prov_keys = _read_key_set(
        target_prov_path,
        ["dataset", "target_subject", "repeat", "split_id", "budget_per_class"],
        gzip_input=True,
    )

    positive_budgets = tuple(sorted(b for b in config.calibration.budgets_per_class if b > 0))
    if 0 in positive_budgets:  # pragma: no cover - defensive, cannot occur given the filter above
        raise AssertionError("Budget 0 must never enter the EA condition loop")
    epsilon = config.alignment.epsilon
    config_digest = alignment_config_digest(config.alignment.mode, epsilon)

    for section in config.datasets:
        prepared = list_prepared_subjects(config.processed_dir, section.name)
        all_subjects = _configured_subjects(section, prepared)
        for target_subject in all_subjects:
            target = load_subject_shard(
                subject_directory(config.processed_dir, section.name, target_subject),
                mmap_mode="r",
                verify_checksums=False,
            )
            source_subjects = source_subjects_from_reused(section.name, target_subject, reused.source_selection)
            assert_subject_disjointness(source_subjects, target.subject)

            # Source-side EA: each source participant's reference is estimated
            # from exactly that participant's reused, capped selected trials
            # (never target data, never a different source participant's
            # trials, never trials excluded by the source-selection cap).
            # Source selection does not depend on `repeat`, so this is
            # computed once per (dataset, target_subject).
            source_X_parts: list[np.ndarray] = []
            source_y_parts: list[np.ndarray] = []
            for source_subject in source_subjects:
                shard = load_subject_shard(
                    subject_directory(config.processed_dir, section.name, source_subject),
                    mmap_mode="r",
                    verify_checksums=False,
                )
                _validate_compatible_shards(target, shard)
                indices = source_indices_from_reused(
                    shard, section.name, target_subject, source_subject, reused.source_trial_assignments
                )
                selected_X = np.asarray(shard.X[indices], dtype=np.float64)
                selected_y = np.asarray(shard.y[indices], dtype=int)
                source_ref = estimate_ea_reference(selected_X, epsilon=epsilon)
                aligned = apply_ea_transform(selected_X, source_ref).astype(np.float32)
                source_X_parts.append(aligned)
                source_y_parts.append(selected_y)
                source_prov_key = (section.name, str(target_subject), str(source_subject))
                if source_prov_key not in source_prov_keys:
                    source_prov_writer.append(
                        [
                            {
                                "dataset": section.name,
                                "target_subject": str(target_subject),
                                "source_subject": str(source_subject),
                                "selection_seed": derive_seed(
                                    config.experiment.seed,
                                    section.name,
                                    target_subject,
                                    source_subject,
                                    "source_trials",
                                ),
                                "source_trial_count": int(len(indices)),
                                "source_alignment_reference_sha256": reference_digest(source_ref),
                                "alignment_config_digest": config_digest,
                            }
                        ]
                    )
                    source_prov_keys.add(source_prov_key)
            source_X = np.concatenate(source_X_parts, axis=0)
            source_y = np.concatenate(source_y_parts, axis=0)
            validate_training_data(source_X, source_y)

            for repeat in range(config.split.repeats):
                split = target_split_from_reused(section.name, target, repeat, reused.split_assignments)
                samples = calibration_samples_from_reused(
                    section.name,
                    target,
                    repeat,
                    split.split_id,
                    reused.calibration_assignments,
                    positive_budgets,
                )
                for sample in samples.values():
                    assert_calibration_test_disjoint(sample.indices, split.test_idx)

                X_test_raw = np.asarray(target.X[split.test_idx], dtype=np.float64)
                y_test = np.asarray(target.y[split.test_idx], dtype=int)

                for budget in positive_budgets:
                    sample = samples[budget]
                    X_calibration_raw = np.asarray(target.X[sample.indices], dtype=np.float64)
                    y_calibration = np.asarray(target.y[sample.indices], dtype=int)

                    # Target-side EA: the reference is estimated from exactly
                    # this condition's target calibration subset -- never
                    # from split.test_idx. It is frozen and then applied to
                    # both the calibration trials and the (untouched, still
                    # never used for estimation) test trials, and this exact
                    # same frozen reference is shared by both regimes below.
                    target_ref = estimate_ea_reference(X_calibration_raw, epsilon=epsilon)
                    X_calibration_aligned = apply_ea_transform(X_calibration_raw, target_ref).astype(np.float32)
                    X_test_aligned = apply_ea_transform(X_test_raw, target_ref).astype(np.float32)

                    target_prov_key = (section.name, str(target_subject), str(repeat), split.split_id, str(budget))
                    if target_prov_key not in target_prov_keys:
                        calibration_uids = target.metadata.iloc[sample.indices]["trial_uid"].astype(str).tolist()
                        target_prov_writer.append(
                            [
                                {
                                    "dataset": section.name,
                                    "target_subject": str(target_subject),
                                    "repeat": repeat,
                                    "split_id": split.split_id,
                                    "budget_per_class": int(budget),
                                    "target_calibration_trial_count": int(len(sample.indices)),
                                    "target_calibration_trial_uid_sha256": _trial_uid_digest(calibration_uids),
                                    "target_alignment_reference_sha256": reference_digest(target_ref),
                                    "alignment_config_digest": config_digest,
                                }
                            ]
                        )
                        target_prov_keys.add(target_prov_key)

                    for method in config.methods:
                        for regime in ("subject", "source_plus_target"):
                            key = ConditionKey(
                                dataset=section.name,
                                target_subject=str(target_subject),
                                repeat=repeat,
                                method=method,
                                regime=regime,
                                budget_per_class=budget,
                                split_id=split.split_id,
                            )
                            if key.as_tuple() in completed:
                                continue
                            condition_seed = derive_seed(
                                config.experiment.seed,
                                section.name,
                                target_subject,
                                repeat,
                                method,
                                regime,
                                budget,
                                ALIGNMENT_MODE,
                            )
                            if regime == "subject":
                                X_train, y_train = X_calibration_aligned, y_calibration
                            else:
                                X_train = np.concatenate([source_X, X_calibration_aligned], axis=0)
                                y_train = np.concatenate([source_y, y_calibration], axis=0)
                            estimator = build_estimator(
                                method,
                                classical=config.classical,
                                seed=condition_seed,
                                n_channels=target.X.shape[1],
                                n_times=target.X.shape[2],
                                sfreq=target.sfreq,
                            )
                            try:
                                y_score, metrics, fit_seconds, predict_seconds = _fit_condition(
                                    estimator, X_train, y_train, X_test_aligned, y_test
                                )
                                if config.runtime.save_predictions:
                                    prediction_rows = _prediction_rows(
                                        key, split, target.metadata, split.test_idx, y_test, y_score, condition_seed
                                    )
                                    for row in prediction_rows:
                                        row["alignment_mode"] = ALIGNMENT_MODE
                                    _write_predictions_once(key, prediction_rows, predictions_writer, prediction_counts)
                                metric_row = _metric_row(
                                    key,
                                    split,
                                    condition_seed,
                                    len(source_subjects),
                                    len(source_y),
                                    len(y_train),
                                    len(y_test),
                                    len(y_calibration),
                                    fit_seconds,
                                    predict_seconds,
                                    metrics,
                                    duplicate_of_population=False,
                                    fit_shared_across_repeats=False,
                                )
                                metric_row["alignment_mode"] = ALIGNMENT_MODE
                                metrics_writer.append([metric_row])
                                completed.add(key.as_tuple())
                            except Exception as error:
                                error_traceback = traceback.format_exc()
                                failed_row = _failed_metric_row(
                                    key,
                                    split,
                                    condition_seed,
                                    len(source_subjects),
                                    len(source_y),
                                    len(y_train),
                                    len(y_test),
                                    len(y_calibration),
                                    error,
                                    fit_shared_across_repeats=False,
                                )
                                failed_row["alignment_mode"] = ALIGNMENT_MODE
                                metrics_writer.append([failed_row])
                                failures_writer.append([_failure_row(key, split, error, error_traceback)])
                                completed.add(key.as_tuple())
                                if not config.experiment.continue_on_error:
                                    raise
    return output_dir
