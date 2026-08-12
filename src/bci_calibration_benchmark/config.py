"""Strict YAML configuration loading and validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from .utils import fingerprint


PROCESSING_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ExperimentSection:
    name: str
    seed: int = 20260811
    output_root: str = "results"
    processed_root: str = "data/processed"
    cache_root: str = "data/moabb-cache"
    continue_on_error: bool = False


@dataclass(frozen=True)
class PreprocessingSection:
    fmin: float = 8.0
    fmax: float = 30.0
    tmin: float = 0.5
    tmax: float = 3.5
    resample: float = 128.0
    channels: tuple[str, ...] | None = None
    dtype: Literal["float32", "float64"] = "float32"


@dataclass(frozen=True)
class DatasetSection:
    name: str
    subjects: tuple[int, ...] | Literal["all"] = "all"
    exclude_subjects: tuple[int, ...] = ()


@dataclass(frozen=True)
class SplitSection:
    policy: Literal[
        "latest_session_only",
        "latest_session_then_latest_runs",
        "latest_runs_only",
    ] = "latest_session_only"
    test_fraction: float = 0.30
    repeats: int = 10
    allow_trial_level_fallback: bool = False
    minimum_test_per_class: int = 10
    minimum_calibration_per_class: int = 40


@dataclass(frozen=True)
class CalibrationSection:
    budgets_per_class: tuple[int, ...] = (0, 5, 10, 20, 40)
    insufficient_budget: Literal["skip", "error"] = "error"
    nested: bool = True


@dataclass(frozen=True)
class SourceSection:
    max_subjects: int | None = None
    max_trials_per_class_per_subject: int | None = None
    balance_classes_within_subject: bool = True


@dataclass(frozen=True)
class MetricsSection:
    primary: str = "roc_auc"
    secondary: tuple[str, ...] = (
        "balanced_accuracy",
        "accuracy",
        "macro_f1",
        "brier",
        "log_loss",
    )


@dataclass(frozen=True)
class ClassicalSection:
    csp_components: int = 8
    csp_reg: str | float | None = "ledoit_wolf"
    logistic_c: float = 1.0
    tangent_mean_max_iter: int = 50
    tangent_mean_tol: float = 1e-9


@dataclass(frozen=True)
class AnalysisSection:
    bootstrap_resamples: int = 2000
    ci_level: float = 0.95
    pairwise_budgets: tuple[int, ...] = (5, 10)
    aucc_max_budget_per_class: int = 40
    roc_auc_threshold: float = 0.75
    balanced_accuracy_threshold: float = 0.70
    fit_mixed_effects: bool = True


@dataclass(frozen=True)
class RuntimeSection:
    n_jobs_data: int = 1
    overwrite_processed: bool = False
    resume: bool = True
    save_predictions: bool = True


@dataclass(frozen=True)
class ExperimentConfig:
    experiment: ExperimentSection
    preprocessing: PreprocessingSection
    datasets: tuple[DatasetSection, ...]
    split: SplitSection = field(default_factory=SplitSection)
    calibration: CalibrationSection = field(default_factory=CalibrationSection)
    source: SourceSection = field(default_factory=SourceSection)
    methods: tuple[str, ...] = ("logvar_lda", "csp_lda", "riemann_lr")
    metrics: MetricsSection = field(default_factory=MetricsSection)
    classical: ClassicalSection = field(default_factory=ClassicalSection)
    analysis: AnalysisSection = field(default_factory=AnalysisSection)
    runtime: RuntimeSection = field(default_factory=RuntimeSection)
    config_path: Path | None = field(default=None, compare=False, repr=False)

    @property
    def preprocessing_fingerprint(self) -> str:
        return fingerprint(
            {"processing_schema_version": PROCESSING_SCHEMA_VERSION, **asdict(self.preprocessing)},
            length=16,
        )

    @property
    def experiment_fingerprint(self) -> str:
        payload = asdict(self)
        payload.pop("config_path", None)
        return fingerprint(payload, length=16)

    @property
    def output_dir(self) -> Path:
        return Path(self.experiment.output_root) / (
            f"{self.experiment.name}-{self.experiment_fingerprint}"
        )

    @property
    def processed_dir(self) -> Path:
        return Path(self.experiment.processed_root) / self.preprocessing_fingerprint

    def validate(self) -> None:
        if not self.experiment.name.strip():
            raise ValueError("experiment.name must be nonempty")
        if self.experiment.seed < 0:
            raise ValueError("experiment.seed must be nonnegative")
        if self.preprocessing.fmin <= 0 or self.preprocessing.fmax <= self.preprocessing.fmin:
            raise ValueError("Require 0 < fmin < fmax")
        if self.preprocessing.tmax <= self.preprocessing.tmin:
            raise ValueError("Require tmax > tmin")
        if self.preprocessing.resample <= 2 * self.preprocessing.fmax:
            raise ValueError("resample must exceed twice fmax to satisfy Nyquist")
        if self.preprocessing.dtype not in {"float32", "float64"}:
            raise ValueError("preprocessing.dtype must be float32 or float64")
        if self.preprocessing.channels is not None:
            if not self.preprocessing.channels:
                raise ValueError("preprocessing.channels cannot be empty")
            if len(self.preprocessing.channels) != len(set(self.preprocessing.channels)):
                raise ValueError("preprocessing.channels must be unique")
        if not 0 < self.split.test_fraction < 1:
            raise ValueError("split.test_fraction must be in (0, 1)")
        if self.split.repeats < 1:
            raise ValueError("split.repeats must be at least 1")
        if self.split.minimum_test_per_class < 1:
            raise ValueError("minimum_test_per_class must be positive")
        if self.split.minimum_calibration_per_class < 1:
            raise ValueError("minimum_calibration_per_class must be positive")

        budgets = self.calibration.budgets_per_class
        if not budgets or budgets[0] != 0:
            raise ValueError("Calibration budgets must begin with zero")
        if tuple(sorted(set(budgets))) != budgets:
            raise ValueError("Calibration budgets must be unique and increasing")
        if any(value < 0 for value in budgets):
            raise ValueError("Calibration budgets cannot be negative")
        if not self.calibration.nested:
            raise ValueError("Version 0.1.0 requires nested calibration samples")
        if self.split.minimum_calibration_per_class < max(budgets):
            raise ValueError(
                "split.minimum_calibration_per_class must cover the largest configured "
                "calibration budget"
            )

        if self.source.max_subjects is not None and self.source.max_subjects < 1:
            raise ValueError("source.max_subjects must be positive or null")
        if (
            self.source.max_trials_per_class_per_subject is not None
            and self.source.max_trials_per_class_per_subject < 1
        ):
            raise ValueError(
                "source.max_trials_per_class_per_subject must be positive or null"
            )

        if not self.datasets:
            raise ValueError("At least one dataset is required")
        dataset_names = [dataset.name for dataset in self.datasets]
        if len(dataset_names) != len(set(dataset_names)):
            raise ValueError("Dataset names must be unique in a configuration")
        for dataset in self.datasets:
            if not dataset.name.strip():
                raise ValueError("Dataset names must be nonempty")
            if dataset.subjects != "all":
                if not dataset.subjects:
                    raise ValueError(f"{dataset.name}: subjects list cannot be empty")
                if len(dataset.subjects) != len(set(dataset.subjects)):
                    raise ValueError(f"{dataset.name}: duplicate subject IDs")
                if any(value < 1 for value in dataset.subjects):
                    raise ValueError(f"{dataset.name}: subject IDs must be positive")
            if any(value < 1 for value in dataset.exclude_subjects):
                raise ValueError(f"{dataset.name}: excluded subject IDs must be positive")
            if set(dataset.exclude_subjects).intersection(
                set() if dataset.subjects == "all" else set(dataset.subjects)
            ):
                raise ValueError(
                    f"{dataset.name}: a subject cannot be both explicitly included and excluded"
                )

        valid_methods = {"logvar_lda", "csp_lda", "riemann_lr", "eegnet"}
        unknown_methods = set(self.methods).difference(valid_methods)
        if unknown_methods:
            raise ValueError(f"Unknown methods: {sorted(unknown_methods)}")
        if not self.methods:
            raise ValueError("At least one method is required")
        if len(self.methods) != len(set(self.methods)):
            raise ValueError("methods must be unique")

        valid_metrics = {
            "roc_auc",
            "balanced_accuracy",
            "accuracy",
            "macro_f1",
            "brier",
            "log_loss",
        }
        requested_metrics = {self.metrics.primary, *self.metrics.secondary}
        unknown_metrics = requested_metrics.difference(valid_metrics)
        if unknown_metrics:
            raise ValueError(f"Unknown metrics: {sorted(unknown_metrics)}")
        if self.metrics.primary in self.metrics.secondary:
            raise ValueError("metrics.primary must not be duplicated in metrics.secondary")
        if len(self.metrics.secondary) != len(set(self.metrics.secondary)):
            raise ValueError("metrics.secondary must be unique")

        if self.classical.csp_components < 1:
            raise ValueError("csp_components must be positive")
        if self.classical.logistic_c <= 0:
            raise ValueError("logistic_c must be positive")
        if self.classical.tangent_mean_max_iter < 1:
            raise ValueError("tangent_mean_max_iter must be positive")
        if self.classical.tangent_mean_tol <= 0:
            raise ValueError("tangent_mean_tol must be positive")

        if self.analysis.bootstrap_resamples < 100:
            raise ValueError("analysis.bootstrap_resamples must be at least 100")
        if not 0 < self.analysis.ci_level < 1:
            raise ValueError("analysis.ci_level must be in (0, 1)")
        if any(value <= 0 for value in self.analysis.pairwise_budgets):
            raise ValueError("analysis.pairwise_budgets must be positive")
        if len(self.analysis.pairwise_budgets) != len(set(self.analysis.pairwise_budgets)):
            raise ValueError("analysis.pairwise_budgets must be unique")
        if not set(self.analysis.pairwise_budgets).issubset(set(budgets)):
            raise ValueError("analysis.pairwise_budgets must be configured calibration budgets")
        if self.analysis.aucc_max_budget_per_class <= 0:
            raise ValueError("analysis.aucc_max_budget_per_class must be positive")
        if self.analysis.aucc_max_budget_per_class not in budgets:
            raise ValueError(
                "analysis.aucc_max_budget_per_class must be a configured calibration budget"
            )
        if not 0 <= self.analysis.roc_auc_threshold <= 1:
            raise ValueError("analysis.roc_auc_threshold must be in [0, 1]")
        if not 0 <= self.analysis.balanced_accuracy_threshold <= 1:
            raise ValueError("analysis.balanced_accuracy_threshold must be in [0, 1]")

        if self.runtime.n_jobs_data < 1:
            raise ValueError("runtime.n_jobs_data must be at least 1")


def _expect_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a mapping")
    return value


def _check_keys(mapping: dict[str, Any], allowed: set[str], name: str) -> None:
    unknown = set(mapping).difference(allowed)
    if unknown:
        raise ValueError(f"Unknown keys in {name}: {sorted(unknown)}")


def _tuple_or_none(value: Any) -> tuple[Any, ...] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)):
        raise TypeError("Expected a list, tuple, or null")
    return tuple(value)


def load_config(path: str | Path) -> ExperimentConfig:
    config_path = Path(path).resolve()
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    top = _expect_mapping(raw, "configuration")
    _check_keys(
        top,
        {
            "experiment",
            "preprocessing",
            "datasets",
            "split",
            "calibration",
            "source",
            "methods",
            "metrics",
            "classical",
            "analysis",
            "runtime",
        },
        "configuration",
    )

    exp = _expect_mapping(top.get("experiment"), "experiment")
    _check_keys(
        exp,
        {"name", "seed", "output_root", "processed_root", "cache_root", "continue_on_error"},
        "experiment",
    )
    experiment = ExperimentSection(**exp)

    pre = _expect_mapping(top.get("preprocessing", {}), "preprocessing")
    _check_keys(
        pre,
        {"fmin", "fmax", "tmin", "tmax", "resample", "channels", "dtype"},
        "preprocessing",
    )
    if "channels" in pre:
        pre["channels"] = _tuple_or_none(pre["channels"])
    preprocessing = PreprocessingSection(**pre)

    datasets_raw = top.get("datasets")
    if not isinstance(datasets_raw, list):
        raise TypeError("datasets must be a list of mappings")
    datasets: list[DatasetSection] = []
    for index, item in enumerate(datasets_raw):
        mapping = _expect_mapping(item, f"datasets[{index}]")
        _check_keys(mapping, {"name", "subjects", "exclude_subjects"}, f"datasets[{index}]")
        if "name" not in mapping:
            raise ValueError(f"datasets[{index}].name is required")
        subjects_raw = mapping.get("subjects", "all")
        if subjects_raw != "all":
            if not isinstance(subjects_raw, (list, tuple)):
                raise TypeError(f"datasets[{index}].subjects must be 'all' or a list")
            subjects_raw = tuple(int(value) for value in subjects_raw)
        exclude_raw = mapping.get("exclude_subjects", [])
        if not isinstance(exclude_raw, (list, tuple)):
            raise TypeError(f"datasets[{index}].exclude_subjects must be a list")
        exclude = tuple(int(value) for value in exclude_raw)
        datasets.append(
            DatasetSection(name=str(mapping["name"]), subjects=subjects_raw, exclude_subjects=exclude)
        )

    split_raw = _expect_mapping(top.get("split", {}), "split")
    _check_keys(
        split_raw,
        {
            "policy",
            "test_fraction",
            "repeats",
            "allow_trial_level_fallback",
            "minimum_test_per_class",
            "minimum_calibration_per_class",
        },
        "split",
    )
    split = SplitSection(**split_raw)

    calibration_raw = _expect_mapping(top.get("calibration", {}), "calibration")
    _check_keys(calibration_raw, {"budgets_per_class", "insufficient_budget", "nested"}, "calibration")
    if "budgets_per_class" in calibration_raw:
        calibration_raw["budgets_per_class"] = tuple(
            int(value) for value in calibration_raw["budgets_per_class"]
        )
    calibration = CalibrationSection(**calibration_raw)

    source_raw = _expect_mapping(top.get("source", {}), "source")
    _check_keys(
        source_raw,
        {"max_subjects", "max_trials_per_class_per_subject", "balance_classes_within_subject"},
        "source",
    )
    source = SourceSection(**source_raw)

    methods_raw = top.get("methods", ["logvar_lda", "csp_lda", "riemann_lr"])
    if not isinstance(methods_raw, (list, tuple)):
        raise TypeError("methods must be a list")
    methods = tuple(str(value) for value in methods_raw)

    metrics_raw = _expect_mapping(top.get("metrics", {}), "metrics")
    _check_keys(metrics_raw, {"primary", "secondary"}, "metrics")
    if "secondary" in metrics_raw:
        metrics_raw["secondary"] = tuple(str(value) for value in metrics_raw["secondary"])
    metrics = MetricsSection(**metrics_raw)

    classical_raw = _expect_mapping(top.get("classical", {}), "classical")
    _check_keys(
        classical_raw,
        {"csp_components", "csp_reg", "logistic_c", "tangent_mean_max_iter", "tangent_mean_tol"},
        "classical",
    )
    classical = ClassicalSection(**classical_raw)

    analysis_raw = _expect_mapping(top.get("analysis", {}), "analysis")
    _check_keys(
        analysis_raw,
        {
            "bootstrap_resamples",
            "ci_level",
            "pairwise_budgets",
            "aucc_max_budget_per_class",
            "roc_auc_threshold",
            "balanced_accuracy_threshold",
            "fit_mixed_effects",
        },
        "analysis",
    )
    if "pairwise_budgets" in analysis_raw:
        analysis_raw["pairwise_budgets"] = tuple(
            int(value) for value in analysis_raw["pairwise_budgets"]
        )
    analysis = AnalysisSection(**analysis_raw)

    runtime_raw = _expect_mapping(top.get("runtime", {}), "runtime")
    _check_keys(
        runtime_raw,
        {"n_jobs_data", "overwrite_processed", "resume", "save_predictions"},
        "runtime",
    )
    runtime = RuntimeSection(**runtime_raw)

    config = ExperimentConfig(
        experiment=experiment,
        preprocessing=preprocessing,
        datasets=tuple(datasets),
        split=split,
        calibration=calibration,
        source=source,
        methods=methods,
        metrics=metrics,
        classical=classical,
        analysis=analysis,
        runtime=runtime,
        config_path=config_path,
    )
    config.validate()
    return config
