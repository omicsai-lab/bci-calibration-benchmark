"""End-to-end benchmark runner with explicit split and result provenance."""

from __future__ import annotations

import csv
import gzip
import json
import time
import traceback
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .config import DatasetSection, ExperimentConfig
from .data_types import ConditionKey, SubjectShard, TargetSplit
from .datasets import dataset_manifest_digest
from .io import list_prepared_subjects, load_subject_shard, subject_directory
from .metrics import METRIC_NAMES, compute_binary_metrics
from .pipelines import build_estimator, predict_positive_probability, validate_training_data
from .provenance import build_run_manifest, write_run_manifest
from .sampling import (
    assert_calibration_test_disjoint,
    assert_subject_disjointness,
    choose_source_subjects,
    nested_calibration_samples,
    source_indices_for_subject,
)
from .splits import make_target_split
from .utils import derive_seed, fingerprint


METRICS_COLUMNS = [
    "dataset",
    "target_subject",
    "repeat",
    "method",
    "regime",
    "budget_per_class",
    "calibration_trials_total",
    "source_subject_count",
    "source_trials",
    "train_trials",
    "test_trials",
    "split_strategy",
    "split_id",
    "condition_seed",
    "duplicate_of_population",
    "fit_shared_across_repeats",
    "status",
    "error_type",
    "error_message",
    "fit_seconds",
    "predict_seconds",
    *METRIC_NAMES,
]

PREDICTION_COLUMNS = [
    "dataset",
    "target_subject",
    "repeat",
    "method",
    "regime",
    "budget_per_class",
    "split_strategy",
    "split_id",
    "condition_seed",
    "trial_uid",
    "session",
    "run",
    "y_true",
    "y_score",
    "y_pred",
]

FAILURE_COLUMNS = [
    "dataset",
    "target_subject",
    "repeat",
    "method",
    "regime",
    "budget_per_class",
    "split_id",
    "error_type",
    "error_message",
    "traceback",
]

SPLIT_ASSIGNMENT_COLUMNS = [
    "dataset",
    "target_subject",
    "repeat",
    "split_strategy",
    "split_id",
    "trial_uid",
    "session",
    "run",
    "group_id",
    "label",
    "role",
]

CALIBRATION_ASSIGNMENT_COLUMNS = [
    "dataset",
    "target_subject",
    "repeat",
    "split_id",
    "budget_per_class",
    "trial_uid",
    "session",
    "run",
    "group_id",
    "label",
    "selected_at_budget",
]

SOURCE_SELECTION_COLUMNS = [
    "dataset",
    "target_subject",
    "source_subject",
    "selection_seed",
    "selected_trials",
    "class_0_trials",
    "class_1_trials",
    "selected_trial_uid_sha256",
]

SOURCE_TRIAL_ASSIGNMENT_COLUMNS = [
    "dataset",
    "target_subject",
    "source_subject",
    "selection_seed",
    "trial_uid",
    "session",
    "run",
    "label",
]


class CSVWriter:
    """Append rows with a stable schema, including concatenated gzip members."""

    def __init__(self, path: Path, columns: list[str], gzip_output: bool = False):
        self.path = path
        self.columns = columns
        self.gzip_output = gzip_output
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, rows: Iterable[dict[str, Any]]) -> None:
        rows_list = list(rows)
        if not rows_list:
            return
        exists = self.path.exists() and self.path.stat().st_size > 0
        opener = gzip.open if self.gzip_output else open
        kwargs: dict[str, Any] = {"mode": "at", "newline": "", "encoding": "utf-8"}
        with opener(self.path, **kwargs) as handle:
            writer = csv.DictWriter(handle, fieldnames=self.columns, extrasaction="ignore")
            if not exists:
                writer.writeheader()
            for row in rows_list:
                writer.writerow({column: row.get(column) for column in self.columns})


def _subject_sort_key(value: str) -> tuple[int, int | str]:
    return (0, int(value)) if value.isdigit() else (1, value)


def _configured_subjects(section: DatasetSection, prepared_subjects: list[str]) -> list[str]:
    prepared_set = set(prepared_subjects)
    if section.subjects == "all":
        selected = sorted(prepared_set, key=_subject_sort_key)
    else:
        selected = [str(value) for value in section.subjects]
        missing = sorted(set(selected).difference(prepared_set), key=_subject_sort_key)
        if missing:
            raise FileNotFoundError(
                f"{section.name}: configured subjects are not prepared: {missing}"
            )
    excluded = {str(value) for value in section.exclude_subjects}
    selected = [value for value in selected if value not in excluded]
    if len(selected) < 2:
        raise ValueError(f"{section.name}: at least two prepared participants are required")
    return selected


def _read_completed_keys(path: Path) -> set[tuple[Any, ...]]:
    if not path.exists():
        return set()
    frame = pd.read_csv(path, dtype={"target_subject": str, "split_id": str})
    if frame.empty:
        return set()
    key_columns = [
        "dataset",
        "target_subject",
        "repeat",
        "method",
        "regime",
        "budget_per_class",
        "split_id",
    ]
    if frame.duplicated(key_columns).any():
        examples = frame.loc[frame.duplicated(key_columns, keep=False), key_columns].head(10)
        raise ValueError(f"Duplicate metric condition rows prevent safe resume: {examples.to_dict('records')}")
    return {
        (
            str(row.dataset),
            str(row.target_subject),
            int(row.repeat),
            str(row.method),
            str(row.regime),
            int(row.budget_per_class),
            str(row.split_id),
        )
        for row in frame.itertuples(index=False)
    }


def _read_key_set(path: Path, columns: list[str], gzip_input: bool = False) -> set[tuple[str, ...]]:
    if not path.exists():
        return set()
    frame = pd.read_csv(path, dtype=str, compression="gzip" if gzip_input else "infer")
    missing = set(columns).difference(frame.columns)
    if missing:
        raise ValueError(f"{path} missing resume-key columns: {sorted(missing)}")
    return {tuple(str(value) for value in row) for row in frame[columns].drop_duplicates().itertuples(index=False, name=None)}


def _read_prediction_counts(path: Path) -> dict[tuple[Any, ...], int]:
    if not path.exists():
        return {}
    frame = pd.read_csv(
        path,
        dtype={"target_subject": str, "split_id": str, "trial_uid": str},
    )
    condition_columns = [
        "dataset",
        "target_subject",
        "repeat",
        "method",
        "regime",
        "budget_per_class",
        "split_id",
    ]
    if frame.duplicated(condition_columns + ["trial_uid"]).any():
        raise ValueError("Duplicate prediction trial rows prevent safe resume")
    counts = frame.groupby(condition_columns, observed=True).size()
    return {
        (
            str(index[0]),
            str(index[1]),
            int(index[2]),
            str(index[3]),
            str(index[4]),
            int(index[5]),
            str(index[6]),
        ): int(value)
        for index, value in counts.items()
    }


def _validate_compatible_shards(target: SubjectShard, source: SubjectShard) -> None:
    if target.dataset != source.dataset:
        raise ValueError("Source and target shards must belong to the same dataset")
    if target.channels != source.channels:
        raise ValueError(
            f"Channel mismatch within {target.dataset}: target={target.subject}, source={source.subject}"
        )
    if target.X.shape[1:] != source.X.shape[1:]:
        raise ValueError("Epoch shape mismatch within dataset")
    if not np.isclose(target.sfreq, source.sfreq):
        raise ValueError("Sampling-rate mismatch within dataset")


def _load_source_training(
    config: ExperimentConfig,
    dataset: str,
    all_subjects: list[str],
    target: SubjectShard,
) -> tuple[
    np.ndarray,
    np.ndarray,
    list[str],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    source_seed = derive_seed(config.experiment.seed, dataset, target.subject, "source_subjects")
    source_subjects = choose_source_subjects(
        all_subjects,
        target_subject=target.subject,
        source_config=config.source,
        seed=source_seed,
    )
    assert_subject_disjointness(source_subjects, target.subject)
    source_X_parts: list[np.ndarray] = []
    source_y_parts: list[np.ndarray] = []
    records: list[dict[str, Any]] = []
    trial_records: list[dict[str, Any]] = []
    for source_subject in source_subjects:
        shard = load_subject_shard(
            subject_directory(config.processed_dir, dataset, source_subject),
            mmap_mode="r",
            verify_checksums=False,
        )
        _validate_compatible_shards(target, shard)
        selection_seed = derive_seed(
            config.experiment.seed, dataset, target.subject, source_subject, "source_trials"
        )
        indices = source_indices_for_subject(shard.y, config.source, seed=selection_seed)
        selected_y = np.asarray(shard.y[indices], dtype=int)
        selected_metadata = shard.metadata.iloc[indices].reset_index(drop=True)
        selected_uids = selected_metadata["trial_uid"].astype(str).tolist()
        source_X_parts.append(np.asarray(shard.X[indices], dtype=np.float32))
        source_y_parts.append(selected_y)
        records.append(
            {
                "dataset": dataset,
                "target_subject": str(target.subject),
                "source_subject": str(source_subject),
                "selection_seed": selection_seed,
                "selected_trials": int(len(indices)),
                "class_0_trials": int(np.sum(selected_y == 0)),
                "class_1_trials": int(np.sum(selected_y == 1)),
                "selected_trial_uid_sha256": fingerprint(sorted(selected_uids), length=None),
            }
        )
        for index, metadata in selected_metadata.iterrows():
            trial_records.append(
                {
                    "dataset": dataset,
                    "target_subject": str(target.subject),
                    "source_subject": str(source_subject),
                    "selection_seed": selection_seed,
                    "trial_uid": str(metadata["trial_uid"]),
                    "session": str(metadata["session"]),
                    "run": str(metadata["run"]),
                    "label": int(selected_y[index]),
                }
            )
    X = np.concatenate(source_X_parts, axis=0)
    y = np.concatenate(source_y_parts, axis=0)
    validate_training_data(X, y)
    return X, y, source_subjects, records, trial_records


def _split_assignment_rows(
    dataset: str,
    target: SubjectShard,
    repeat: int,
    split: TargetSplit,
) -> list[dict[str, Any]]:
    roles = np.full(len(target.y), "", dtype=object)
    roles[split.calibration_pool_idx] = "calibration_pool"
    roles[split.test_idx] = "test"
    if set(roles.tolist()) != {"calibration_pool", "test"}:
        raise ValueError("Target split does not assign every trial exactly one role")
    rows: list[dict[str, Any]] = []
    for index, role in enumerate(roles):
        metadata = target.metadata.iloc[index]
        session = str(metadata["session"])
        run = str(metadata["run"])
        rows.append(
            {
                "dataset": dataset,
                "target_subject": str(target.subject),
                "repeat": repeat,
                "split_strategy": split.strategy,
                "split_id": split.split_id,
                "trial_uid": str(metadata["trial_uid"]),
                "session": session,
                "run": run,
                "group_id": f"{session}::{run}",
                "label": int(target.y[index]),
                "role": str(role),
            }
        )
    return rows


def _calibration_assignment_rows(
    dataset: str,
    target: SubjectShard,
    repeat: int,
    split: TargetSplit,
    samples: dict[int, Any],
) -> list[dict[str, Any]]:
    first_budget: dict[int, int] = {}
    for budget in sorted(samples):
        if budget == 0:
            continue
        for index in samples[budget].indices:
            first_budget.setdefault(int(index), int(budget))
    rows: list[dict[str, Any]] = []
    for budget in sorted(samples):
        if budget == 0:
            continue
        for index in samples[budget].indices:
            metadata = target.metadata.iloc[int(index)]
            session = str(metadata["session"])
            run = str(metadata["run"])
            rows.append(
                {
                    "dataset": dataset,
                    "target_subject": str(target.subject),
                    "repeat": repeat,
                    "split_id": split.split_id,
                    "budget_per_class": int(budget),
                    "trial_uid": str(metadata["trial_uid"]),
                    "session": session,
                    "run": run,
                    "group_id": f"{session}::{run}",
                    "label": int(target.y[int(index)]),
                    "selected_at_budget": first_budget[int(index)],
                }
            )
    return rows


def _prediction_rows(
    key: ConditionKey,
    split: TargetSplit,
    metadata: pd.DataFrame,
    test_idx: np.ndarray,
    y_true: np.ndarray,
    y_score: np.ndarray,
    condition_seed: int,
) -> list[dict[str, Any]]:
    y_pred = (y_score >= 0.5).astype(int)
    test_meta = metadata.iloc[test_idx].reset_index(drop=True)
    return [
        {
            "dataset": key.dataset,
            "target_subject": key.target_subject,
            "repeat": key.repeat,
            "method": key.method,
            "regime": key.regime,
            "budget_per_class": key.budget_per_class,
            "split_strategy": split.strategy,
            "split_id": split.split_id,
            "condition_seed": condition_seed,
            "trial_uid": str(test_meta.loc[index, "trial_uid"]),
            "session": str(test_meta.loc[index, "session"]),
            "run": str(test_meta.loc[index, "run"]),
            "y_true": int(y_true[index]),
            "y_score": float(y_score[index]),
            "y_pred": int(y_pred[index]),
        }
        for index in range(len(test_idx))
    ]


def _metric_row(
    key: ConditionKey,
    split: TargetSplit,
    condition_seed: int,
    source_subject_count: int,
    source_trials: int,
    train_trials: int,
    test_trials: int,
    calibration_trials_total: int,
    fit_seconds: float,
    predict_seconds: float,
    metrics: dict[str, float],
    *,
    duplicate_of_population: bool,
    fit_shared_across_repeats: bool,
) -> dict[str, Any]:
    return {
        "dataset": key.dataset,
        "target_subject": key.target_subject,
        "repeat": key.repeat,
        "method": key.method,
        "regime": key.regime,
        "budget_per_class": key.budget_per_class,
        "calibration_trials_total": calibration_trials_total,
        "source_subject_count": source_subject_count,
        "source_trials": source_trials,
        "train_trials": train_trials,
        "test_trials": test_trials,
        "split_strategy": split.strategy,
        "split_id": split.split_id,
        "condition_seed": condition_seed,
        "duplicate_of_population": duplicate_of_population,
        "fit_shared_across_repeats": fit_shared_across_repeats,
        "status": "ok",
        "error_type": None,
        "error_message": None,
        "fit_seconds": fit_seconds,
        "predict_seconds": predict_seconds,
        **metrics,
    }


def _failure_row(
    key: ConditionKey,
    split: TargetSplit,
    error: Exception,
    traceback_text: str,
) -> dict[str, Any]:
    return {
        "dataset": key.dataset,
        "target_subject": key.target_subject,
        "repeat": key.repeat,
        "method": key.method,
        "regime": key.regime,
        "budget_per_class": key.budget_per_class,
        "split_id": split.split_id,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "traceback": traceback_text,
    }


def _failed_metric_row(
    key: ConditionKey,
    split: TargetSplit,
    condition_seed: int,
    source_subject_count: int,
    source_trials: int,
    train_trials: int,
    test_trials: int,
    calibration_trials_total: int,
    error: Exception,
    *,
    fit_shared_across_repeats: bool,
) -> dict[str, Any]:
    row = {
        "dataset": key.dataset,
        "target_subject": key.target_subject,
        "repeat": key.repeat,
        "method": key.method,
        "regime": key.regime,
        "budget_per_class": key.budget_per_class,
        "calibration_trials_total": calibration_trials_total,
        "source_subject_count": source_subject_count,
        "source_trials": source_trials,
        "train_trials": train_trials,
        "test_trials": test_trials,
        "split_strategy": split.strategy,
        "split_id": split.split_id,
        "condition_seed": condition_seed,
        "duplicate_of_population": False,
        "fit_shared_across_repeats": fit_shared_across_repeats,
        "status": "failed",
        "error_type": type(error).__name__,
        "error_message": str(error),
        "fit_seconds": None,
        "predict_seconds": None,
    }
    row.update({metric: None for metric in METRIC_NAMES})
    return row


def _fit_condition(
    estimator: Any,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
) -> tuple[np.ndarray, dict[str, float], float, float]:
    validate_training_data(X_train, y_train)
    if not np.isfinite(X_test).all():
        raise ValueError("Held-out X contains non-finite values")
    fit_start = time.perf_counter()
    estimator.fit(X_train, y_train)
    fit_seconds = time.perf_counter() - fit_start
    predict_start = time.perf_counter()
    y_score = predict_positive_probability(estimator, X_test)
    predict_seconds = time.perf_counter() - predict_start
    metrics = compute_binary_metrics(y_test, y_score)
    return y_score, metrics, fit_seconds, predict_seconds


def _write_predictions_once(
    key: ConditionKey,
    rows: list[dict[str, Any]],
    writer: CSVWriter,
    existing_counts: dict[tuple[Any, ...], int],
) -> None:
    condition = key.as_tuple()
    observed = existing_counts.get(condition, 0)
    expected = len(rows)
    if observed not in {0, expected}:
        raise ValueError(
            f"Partial predictions exist for {condition}: observed={observed}, expected={expected}"
        )
    if observed == 0:
        writer.append(rows)
        existing_counts[condition] = expected


def _initialize_or_validate_manifest(
    config: ExperimentConfig,
    output_dir: Path,
    repository_root: str | Path,
) -> None:
    manifest_path = output_dir / "run_manifest.json"
    current_dataset_digests = {
        section.name: dataset_manifest_digest(config, section.name) for section in config.datasets
    }
    if not manifest_path.exists():
        manifest = build_run_manifest(config, repository_root=repository_root)
        manifest["dataset_manifest_sha256"] = current_dataset_digests
        write_run_manifest(manifest_path, manifest)
        return
    existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    if existing.get("experiment_fingerprint") != config.experiment_fingerprint:
        raise ValueError("Existing run manifest fingerprint does not match configuration")
    if existing.get("preprocessing_fingerprint") != config.preprocessing_fingerprint:
        raise ValueError("Existing run manifest preprocessing fingerprint does not match")
    if existing.get("dataset_manifest_sha256") != current_dataset_digests:
        raise ValueError("Processed dataset manifests changed after this run was started")
    current = build_run_manifest(config, repository_root=repository_root)
    if existing.get("package_versions") != current.get("package_versions"):
        raise ValueError("Package versions changed after this run was started")
    existing_source = existing.get("repository_source_sha256")
    current_source = current.get("repository_source_sha256")
    if existing_source is not None and current_source is not None and existing_source != current_source:
        raise ValueError("Repository source changed after this run was started")


def run_benchmark(config: ExperimentConfig, repository_root: str | Path = ".") -> Path:
    config.validate()
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    managed_files = [
        "metrics.csv",
        "predictions.csv.gz",
        "failures.csv",
        "split_assignments.csv.gz",
        "calibration_assignments.csv.gz",
        "source_selection.csv",
        "source_trial_assignments.csv.gz",
    ]
    if not config.runtime.resume and any((output_dir / name).exists() for name in managed_files):
        raise FileExistsError(
            "runtime.resume is false but managed result files already exist; use a new experiment name"
        )
    _initialize_or_validate_manifest(config, output_dir, repository_root)

    metrics_path = output_dir / "metrics.csv"
    predictions_path = output_dir / "predictions.csv.gz"
    failures_path = output_dir / "failures.csv"
    split_assignments_path = output_dir / "split_assignments.csv.gz"
    calibration_assignments_path = output_dir / "calibration_assignments.csv.gz"
    source_selection_path = output_dir / "source_selection.csv"
    source_trial_assignments_path = output_dir / "source_trial_assignments.csv.gz"

    metrics_writer = CSVWriter(metrics_path, METRICS_COLUMNS)
    predictions_writer = CSVWriter(predictions_path, PREDICTION_COLUMNS, gzip_output=True)
    failures_writer = CSVWriter(failures_path, FAILURE_COLUMNS)
    split_writer = CSVWriter(split_assignments_path, SPLIT_ASSIGNMENT_COLUMNS, gzip_output=True)
    calibration_writer = CSVWriter(
        calibration_assignments_path,
        CALIBRATION_ASSIGNMENT_COLUMNS,
        gzip_output=True,
    )
    source_writer = CSVWriter(source_selection_path, SOURCE_SELECTION_COLUMNS)
    source_trial_writer = CSVWriter(
        source_trial_assignments_path,
        SOURCE_TRIAL_ASSIGNMENT_COLUMNS,
        gzip_output=True,
    )

    completed = _read_completed_keys(metrics_path) if config.runtime.resume else set()
    prediction_counts = (
        _read_prediction_counts(predictions_path)
        if config.runtime.resume and config.runtime.save_predictions
        else {}
    )
    split_keys = _read_key_set(
        split_assignments_path,
        ["dataset", "target_subject", "repeat", "split_id"],
        gzip_input=True,
    )
    calibration_keys = _read_key_set(
        calibration_assignments_path,
        ["dataset", "target_subject", "repeat", "split_id"],
        gzip_input=True,
    )
    source_keys = _read_key_set(
        source_selection_path,
        ["dataset", "target_subject"],
    )
    source_trial_keys = _read_key_set(
        source_trial_assignments_path,
        ["dataset", "target_subject"],
        gzip_input=True,
    )

    for section in config.datasets:
        prepared = list_prepared_subjects(config.processed_dir, section.name)
        all_subjects = _configured_subjects(section, prepared)
        for target_subject in all_subjects:
            target = load_subject_shard(
                subject_directory(config.processed_dir, section.name, target_subject),
                mmap_mode="r",
                verify_checksums=False,
            )
            (
                source_X,
                source_y,
                source_subjects,
                source_records,
                source_trial_records,
            ) = _load_source_training(config, section.name, all_subjects, target)
            source_trials = len(source_y)
            source_key = (section.name, str(target_subject))
            if source_key not in source_keys:
                source_writer.append(source_records)
                source_keys.add(source_key)
            if source_key not in source_trial_keys:
                source_trial_writer.append(source_trial_records)
                source_trial_keys.add(source_key)

            splits: list[tuple[int, TargetSplit, dict[int, Any]]] = []
            for repeat in range(config.split.repeats):
                split_seed = derive_seed(
                    config.experiment.seed, section.name, target_subject, repeat, "split"
                )
                split = make_target_split(target.metadata, target.y, config.split, split_seed)
                calibration_seed = derive_seed(
                    config.experiment.seed, section.name, target_subject, repeat, "calibration"
                )
                samples = nested_calibration_samples(
                    target.y,
                    split.calibration_pool_idx,
                    config.calibration,
                    calibration_seed,
                )
                for sample in samples.values():
                    assert_calibration_test_disjoint(sample.indices, split.test_idx)
                assignment_key = (
                    section.name,
                    str(target_subject),
                    str(repeat),
                    split.split_id,
                )
                if assignment_key not in split_keys:
                    split_writer.append(
                        _split_assignment_rows(section.name, target, repeat, split)
                    )
                    split_keys.add(assignment_key)
                if assignment_key not in calibration_keys:
                    calibration_writer.append(
                        _calibration_assignment_rows(
                            section.name,
                            target,
                            repeat,
                            split,
                            samples,
                        )
                    )
                    calibration_keys.add(assignment_key)
                splits.append((repeat, split, samples))

            for method in config.methods:
                zero_conditions = [
                    ConditionKey(
                        dataset=section.name,
                        target_subject=str(target_subject),
                        repeat=repeat,
                        method=method,
                        regime=regime,
                        budget_per_class=0,
                        split_id=split.split_id,
                    )
                    for repeat, split, _ in splits
                    for regime in ("population", "source_plus_target")
                ]
                need_population_fit = any(key.as_tuple() not in completed for key in zero_conditions)
                population_seed = derive_seed(
                    config.experiment.seed, section.name, target_subject, method, "population"
                )
                population_estimator: Any | None = None
                population_fit_error: Exception | None = None
                population_fit_traceback = ""
                population_fit_seconds = 0.0
                if need_population_fit:
                    population_estimator = build_estimator(
                        method,
                        classical=config.classical,
                        seed=population_seed,
                        n_channels=target.X.shape[1],
                        n_times=target.X.shape[2],
                        sfreq=target.sfreq,
                    )
                    try:
                        validate_training_data(source_X, source_y)
                        start = time.perf_counter()
                        population_estimator.fit(source_X, source_y)
                        population_fit_seconds = time.perf_counter() - start
                    except Exception as error:
                        population_fit_error = error
                        population_fit_traceback = traceback.format_exc()

                for repeat, split, samples in splits:
                    X_test = np.asarray(target.X[split.test_idx], dtype=np.float32)
                    y_test = np.asarray(target.y[split.test_idx], dtype=int)
                    population_scores: np.ndarray | None = None
                    population_metrics: dict[str, float] | None = None
                    population_predict_seconds = 0.0

                    for regime in ("population", "source_plus_target"):
                        zero_key = ConditionKey(
                            dataset=section.name,
                            target_subject=str(target_subject),
                            repeat=repeat,
                            method=method,
                            regime=regime,
                            budget_per_class=0,
                            split_id=split.split_id,
                        )
                        if zero_key.as_tuple() in completed:
                            continue
                        if population_fit_error is not None:
                            metrics_writer.append(
                                [
                                    _failed_metric_row(
                                        zero_key,
                                        split,
                                        population_seed,
                                        len(source_subjects),
                                        source_trials,
                                        source_trials,
                                        len(y_test),
                                        0,
                                        population_fit_error,
                                        fit_shared_across_repeats=True,
                                    )
                                ]
                            )
                            failures_writer.append(
                                [
                                    _failure_row(
                                        zero_key,
                                        split,
                                        population_fit_error,
                                        population_fit_traceback,
                                    )
                                ]
                            )
                            completed.add(zero_key.as_tuple())
                            if not config.experiment.continue_on_error:
                                raise population_fit_error
                            continue
                        if population_estimator is None:
                            raise RuntimeError("Population estimator was not fitted for an incomplete row")
                        if population_scores is None:
                            start = time.perf_counter()
                            population_scores = predict_positive_probability(
                                population_estimator, X_test
                            )
                            population_predict_seconds = time.perf_counter() - start
                            population_metrics = compute_binary_metrics(y_test, population_scores)
                        if population_metrics is None:
                            raise RuntimeError("Population metrics were not computed")
                        if config.runtime.save_predictions:
                            _write_predictions_once(
                                zero_key,
                                _prediction_rows(
                                    zero_key,
                                    split,
                                    target.metadata,
                                    split.test_idx,
                                    y_test,
                                    population_scores,
                                    population_seed,
                                ),
                                predictions_writer,
                                prediction_counts,
                            )
                        metrics_writer.append(
                            [
                                _metric_row(
                                    zero_key,
                                    split,
                                    population_seed,
                                    len(source_subjects),
                                    source_trials,
                                    source_trials,
                                    len(y_test),
                                    0,
                                    population_fit_seconds if regime == "population" else 0.0,
                                    population_predict_seconds,
                                    population_metrics,
                                    duplicate_of_population=(regime == "source_plus_target"),
                                    fit_shared_across_repeats=True,
                                )
                            ]
                        )
                        completed.add(zero_key.as_tuple())

                    for budget, sample in samples.items():
                        if budget == 0:
                            continue
                        calibration_idx = sample.indices
                        X_calibration = np.asarray(target.X[calibration_idx], dtype=np.float32)
                        y_calibration = np.asarray(target.y[calibration_idx], dtype=int)
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
                            )
                            if regime == "subject":
                                X_train = X_calibration
                                y_train = y_calibration
                            else:
                                X_train = np.concatenate([source_X, X_calibration], axis=0)
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
                                    estimator, X_train, y_train, X_test, y_test
                                )
                                if config.runtime.save_predictions:
                                    _write_predictions_once(
                                        key,
                                        _prediction_rows(
                                            key,
                                            split,
                                            target.metadata,
                                            split.test_idx,
                                            y_test,
                                            y_score,
                                            condition_seed,
                                        ),
                                        predictions_writer,
                                        prediction_counts,
                                    )
                                metrics_writer.append(
                                    [
                                        _metric_row(
                                            key,
                                            split,
                                            condition_seed,
                                            len(source_subjects),
                                            source_trials,
                                            len(y_train),
                                            len(y_test),
                                            len(y_calibration),
                                            fit_seconds,
                                            predict_seconds,
                                            metrics,
                                            duplicate_of_population=False,
                                            fit_shared_across_repeats=False,
                                        )
                                    ]
                                )
                                completed.add(key.as_tuple())
                            except Exception as error:
                                error_traceback = traceback.format_exc()
                                metrics_writer.append(
                                    [
                                        _failed_metric_row(
                                            key,
                                            split,
                                            condition_seed,
                                            len(source_subjects),
                                            source_trials,
                                            len(y_train),
                                            len(y_test),
                                            len(y_calibration),
                                            error,
                                            fit_shared_across_repeats=False,
                                        )
                                    ]
                                )
                                failures_writer.append(
                                    [_failure_row(key, split, error, error_traceback)]
                                )
                                completed.add(key.as_tuple())
                                if not config.experiment.continue_on_error:
                                    raise
    return output_dir
