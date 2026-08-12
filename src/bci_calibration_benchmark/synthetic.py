"""Synthetic EEG generator used exclusively for software validation.

Synthetic outputs are deliberately labeled and must never be interpreted as
public-data evidence.  The generator creates a stable contralateral mu-rhythm
variance pattern so that data flow and model orientation can be checked.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import roc_auc_score

from .aggregate import aggregate_run
from .config import (
    AnalysisSection,
    CalibrationSection,
    ClassicalSection,
    DatasetSection,
    ExperimentConfig,
    ExperimentSection,
    MetricsSection,
    PreprocessingSection,
    RuntimeSection,
    SourceSection,
    SplitSection,
)
from .data_types import SubjectShard
from .io import save_subject_shard, subject_directory, write_dataset_manifest
from .pipelines import build_estimator, predict_positive_probability
from .plotting import make_all_figures
from .provenance import package_versions
from .runner import run_benchmark
from .utils import atomic_write_text, derive_seed, json_default
from .validation import audit_result_integrity


@dataclass(frozen=True)
class SyntheticSpecification:
    dataset: str = "SyntheticMI"
    n_subjects: int = 3
    n_sessions: int = 2
    n_runs_per_session: int = 1
    trials_per_class_per_run: int = 6
    channels: tuple[str, ...] = ("C3", "Cz", "C4")
    sfreq: float = 128.0
    n_times: int = 128
    seed: int = 20260811

    def validate(self) -> None:
        if self.n_subjects < 3:
            raise ValueError("Synthetic smoke data require at least three participants")
        if self.n_sessions < 2:
            raise ValueError("Synthetic smoke data require at least two sessions")
        if self.trials_per_class_per_run < 5:
            raise ValueError("Synthetic smoke data need at least five trials per class per run")
        if len(self.channels) < 3:
            raise ValueError("Synthetic smoke data require at least three channels")
        if self.n_times < 32 or self.sfreq <= 0:
            raise ValueError("Invalid synthetic sampling specification")


def _colored_noise(rng: np.random.Generator, shape: tuple[int, int]) -> np.ndarray:
    white = rng.normal(size=shape)
    output = np.empty_like(white)
    output[:, 0] = white[:, 0]
    for time_index in range(1, shape[1]):
        output[:, time_index] = 0.72 * output[:, time_index - 1] + white[:, time_index]
    return output / np.std(output, axis=1, keepdims=True)


def _synthetic_epoch(
    rng: np.random.Generator,
    label: int,
    subject: int,
    session: int,
    n_channels: int,
    sfreq: float,
    n_times: int,
) -> np.ndarray:
    time = np.arange(n_times, dtype=float) / sfreq
    phase = rng.uniform(0, 2 * np.pi)
    mu = np.sin(2 * np.pi * (10.0 + 0.12 * subject) * time + phase)
    beta = np.sin(2 * np.pi * 20.0 * time + phase / 2.0)
    # Right-hand imagery suppresses C3-like variance; left-hand imagery suppresses C4-like variance.
    if label == 1:
        mu_amplitudes = np.asarray([0.45, 0.82, 1.15], dtype=float)
    else:
        mu_amplitudes = np.asarray([1.15, 0.82, 0.45], dtype=float)
    if n_channels > 3:
        mu_amplitudes = np.pad(mu_amplitudes, (0, n_channels - 3), constant_values=0.75)
    subject_gain = 1.0 + 0.035 * (subject - 1)
    session_gain = 1.0 + 0.04 * session
    signal = subject_gain * session_gain * mu_amplitudes[:, None] * mu[None, :]
    signal += 0.18 * beta[None, :]
    noise = 0.58 * _colored_noise(rng, (n_channels, n_times))
    common = 0.20 * _colored_noise(rng, (1, n_times))
    epoch = signal + noise + common
    # Store voltage-like magnitudes while retaining numerically comfortable values.
    return (epoch * 1e-6).astype(np.float32)


def generate_synthetic_dataset(
    processed_root: str | Path,
    preprocessing_fingerprint: str,
    preprocessing: PreprocessingSection,
    specification: SyntheticSpecification | None = None,
    *,
    overwrite: bool = True,
) -> Path:
    specification = specification or SyntheticSpecification()
    specification.validate()
    processed_dir = Path(processed_root) / preprocessing_fingerprint
    dataset_dir = processed_dir / specification.dataset
    package_info = {**package_versions(), "synthetic_generator": "1"}
    for subject in range(1, specification.n_subjects + 1):
        rng = np.random.default_rng(derive_seed(specification.seed, "synthetic", subject))
        epochs: list[np.ndarray] = []
        labels: list[int] = []
        metadata_rows: list[dict[str, Any]] = []
        trial_index = 0
        for session in range(specification.n_sessions):
            for run in range(specification.n_runs_per_session):
                run_labels = np.repeat(
                    np.asarray([0, 1], dtype=int),
                    specification.trials_per_class_per_run,
                )
                rng.shuffle(run_labels)
                for label in run_labels:
                    epochs.append(
                        _synthetic_epoch(
                            rng,
                            int(label),
                            subject,
                            session,
                            len(specification.channels),
                            specification.sfreq,
                            specification.n_times,
                        )
                    )
                    labels.append(int(label))
                    metadata_rows.append(
                        {
                            "subject": str(subject),
                            "session": str(session),
                            "run": str(run),
                            "trial_index": trial_index,
                            "trial_uid": (
                                f"{specification.dataset}:{subject}:{session}:{run}:{trial_index:05d}"
                            ),
                            "label": int(label),
                            "label_original": "right_hand" if int(label) == 1 else "left_hand",
                            "synthetic": True,
                        }
                    )
                    trial_index += 1
        shard = SubjectShard(
            dataset=specification.dataset,
            subject=str(subject),
            X=np.stack(epochs, axis=0),
            y=np.asarray(labels, dtype=int),
            metadata=pd.DataFrame(metadata_rows),
            channels=specification.channels,
            sfreq=specification.sfreq,
        )
        save_subject_shard(
            shard,
            subject_directory(processed_dir, specification.dataset, subject),
            preprocessing=asdict(preprocessing),
            package_versions=package_info,
            overwrite=overwrite,
        )
    write_dataset_manifest(
        dataset_dir,
        specification.dataset,
        preprocessing_fingerprint,
        asdict(preprocessing),
        [str(subject) for subject in range(1, specification.n_subjects + 1)],
        package_info,
    )
    atomic_write_text(
        dataset_dir / "SYNTHETIC_DATA_NOTICE.json",
        json.dumps(asdict(specification), indent=2, sort_keys=True, default=json_default) + "\n",
    )
    return dataset_dir


def build_smoke_config(workspace: str | Path, output_name: str) -> ExperimentConfig:
    workspace = Path(workspace).resolve()
    try:
        import mne

        mne.set_log_level("ERROR")
    except ImportError:
        pass
    config = ExperimentConfig(
        experiment=ExperimentSection(
            name="synthetic-smoke",
            seed=20260811,
            output_root=str(workspace / output_name / "results"),
            processed_root=str(workspace / "data" / "processed"),
            cache_root=str(workspace / "data" / "cache"),
            continue_on_error=False,
        ),
        preprocessing=PreprocessingSection(
            fmin=8.0,
            fmax=35.0,
            tmin=0.0,
            tmax=1.0,
            resample=128.0,
            channels=("C3", "Cz", "C4"),
            dtype="float32",
        ),
        datasets=(DatasetSection(name="SyntheticMI", subjects=(1, 2, 3)),),
        split=SplitSection(
            policy="latest_session_only",
            test_fraction=0.5,
            repeats=2,
            allow_trial_level_fallback=False,
            minimum_test_per_class=5,
            minimum_calibration_per_class=5,
        ),
        calibration=CalibrationSection(
            budgets_per_class=(0, 3, 5),
            insufficient_budget="error",
            nested=True,
        ),
        source=SourceSection(
            max_subjects=None,
            max_trials_per_class_per_subject=None,
            balance_classes_within_subject=True,
        ),
        methods=("logvar_lda", "csp_lda", "riemann_lr"),
        metrics=MetricsSection(),
        classical=ClassicalSection(
            csp_components=3,
            csp_reg="ledoit_wolf",
            logistic_c=1.0,
            tangent_mean_max_iter=30,
            tangent_mean_tol=1e-8,
        ),
        analysis=AnalysisSection(
            bootstrap_resamples=200,
            ci_level=0.95,
            pairwise_budgets=(3, 5),
            aucc_max_budget_per_class=5,
            roc_auc_threshold=0.75,
            balanced_accuracy_threshold=0.70,
            fit_mixed_effects=False,
        ),
        runtime=RuntimeSection(
            n_jobs_data=1,
            overwrite_processed=True,
            resume=True,
            save_predictions=True,
        ),
    )
    config.validate()
    return config


def write_config_yaml(config: ExperimentConfig, path: str | Path) -> Path:
    payload = asdict(config)
    payload.pop("config_path", None)
    for dataset in payload["datasets"]:
        if isinstance(dataset["subjects"], tuple):
            dataset["subjects"] = list(dataset["subjects"])
        dataset["exclude_subjects"] = list(dataset["exclude_subjects"])
    for section, key in (
        ("preprocessing", "channels"),
        ("calibration", "budgets_per_class"),
        ("metrics", "secondary"),
        ("analysis", "pairwise_budgets"),
    ):
        value = payload[section][key]
        if isinstance(value, tuple):
            payload[section][key] = list(value)
    payload["methods"] = list(payload["methods"])
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _stable_metrics(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"target_subject": str, "split_id": str})
    drop = [column for column in ("fit_seconds", "predict_seconds") if column in frame.columns]
    frame = frame.drop(columns=drop)
    sort_columns = [
        "dataset",
        "target_subject",
        "repeat",
        "method",
        "regime",
        "budget_per_class",
        "split_id",
    ]
    return frame.sort_values(sort_columns, kind="stable").reset_index(drop=True)


def _negative_control(config: ExperimentConfig) -> dict[str, float]:
    from .io import load_subject_shard

    target = load_subject_shard(
        subject_directory(config.processed_dir, "SyntheticMI", "1"),
        mmap_mode=None,
    )
    sources = [
        load_subject_shard(
            subject_directory(config.processed_dir, "SyntheticMI", str(subject)),
            mmap_mode=None,
        )
        for subject in (2, 3)
    ]
    X_train = np.concatenate([source.X for source in sources], axis=0)
    y_train = np.concatenate([source.y for source in sources], axis=0)
    test_idx = np.flatnonzero(target.metadata["session"].astype(str).to_numpy() == "1")
    scores: list[float] = []
    for permutation in range(16):
        rng = np.random.default_rng(derive_seed(config.experiment.seed, "negative", permutation))
        shuffled = y_train.copy()
        rng.shuffle(shuffled)
        estimator = build_estimator(
            "logvar_lda",
            classical=config.classical,
            seed=derive_seed(config.experiment.seed, "negative-estimator", permutation),
            n_channels=target.X.shape[1],
            n_times=target.X.shape[2],
            sfreq=target.sfreq,
        )
        estimator.fit(X_train, shuffled)
        probabilities = predict_positive_probability(estimator, target.X[test_idx])
        scores.append(float(roc_auc_score(target.y[test_idx], probabilities)))
    return {
        "mean_shuffled_label_roc_auc": float(np.mean(scores)),
        "minimum_shuffled_label_roc_auc": float(np.min(scores)),
        "maximum_shuffled_label_roc_auc": float(np.max(scores)),
        "n_permutations": float(len(scores)),
    }


def run_synthetic_smoke_test(
    workspace: str | Path = ".smoke-work",
    *,
    clean: bool = True,
    make_figures: bool = True,
) -> dict[str, Any]:
    workspace = Path(workspace).resolve()
    if clean and workspace.exists():
        marker = workspace / ".bci-smoke-workspace"
        if not marker.exists():
            raise ValueError(f"Refusing to delete unmarked workspace: {workspace}")
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / ".bci-smoke-workspace").write_text("synthetic validation only\n", encoding="utf-8")

    config_a = build_smoke_config(workspace, "run-a")
    config_b = replace(
        config_a,
        experiment=replace(
            config_a.experiment,
            output_root=str(workspace / "run-b" / "results"),
        ),
    )
    config_b.validate()
    write_config_yaml(config_a, workspace / "synthetic_smoke_a.yaml")
    write_config_yaml(config_b, workspace / "synthetic_smoke_b.yaml")

    generate_synthetic_dataset(
        config_a.experiment.processed_root,
        config_a.preprocessing_fingerprint,
        config_a.preprocessing,
        overwrite=True,
    )

    output_a = run_benchmark(config_a, repository_root=Path(__file__).resolve().parents[2])
    aggregate_run(config_a)
    if make_figures:
        make_all_figures(config_a)
    output_b = run_benchmark(config_b, repository_root=Path(__file__).resolve().parents[2])
    aggregate_run(config_b)

    metrics_a = _stable_metrics(output_a / "metrics.csv")
    metrics_b = _stable_metrics(output_b / "metrics.csv")
    pd.testing.assert_frame_equal(metrics_a, metrics_b, check_exact=True)
    for filename in (
        "split_assignments.csv.gz",
        "calibration_assignments.csv.gz",
        "source_selection.csv",
        "source_trial_assignments.csv.gz",
    ):
        first = pd.read_csv(output_a / filename, dtype=str).sort_values(list(pd.read_csv(output_a / filename, nrows=0).columns), kind="stable").reset_index(drop=True)
        second = pd.read_csv(output_b / filename, dtype=str).sort_values(list(pd.read_csv(output_b / filename, nrows=0).columns), kind="stable").reset_index(drop=True)
        pd.testing.assert_frame_equal(first, second, check_exact=True)

    audit_a = audit_result_integrity(config_a)
    audit_b = audit_result_integrity(config_b)
    if audit_a["status"] != "ok" or audit_b["status"] != "ok":
        raise AssertionError(f"Synthetic result audit failed: {audit_a}, {audit_b}")
    negative = _negative_control(config_a)
    if not 0.30 <= negative["mean_shuffled_label_roc_auc"] <= 0.70:
        raise AssertionError(f"Shuffled-label negative control is implausible: {negative}")

    report = {
        "status": "ok",
        "synthetic_only": True,
        "deterministic_metrics_match": True,
        "run_a": str(output_a),
        "run_b": str(output_b),
        "audit_a": audit_a,
        "audit_b": audit_b,
        "negative_control": negative,
        "successful_metric_rows": int((metrics_a["status"] == "ok").sum()),
    }
    atomic_write_text(
        workspace / "smoke_report.json",
        json.dumps(report, indent=2, sort_keys=True, default=json_default) + "\n",
    )
    return report
