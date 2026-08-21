"""MOABB dataset preparation and processed-data validation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import PROCESSING_SCHEMA_VERSION, DatasetSection, ExperimentConfig
from .data_types import SubjectShard
from .io import (
    DATASET_MANIFEST,
    SUBJECT_MANIFEST,
    list_prepared_subjects,
    load_subject_shard,
    read_manifest,
    save_subject_shard,
    subject_directory,
    write_dataset_manifest,
)
from .provenance import package_versions
from .splits import make_target_split
from .utils import derive_seed, sha256_file


@dataclass(frozen=True)
class DatasetExpectation:
    """Pinned adapter-level expectations checked before a shard is accepted."""

    sessions: int
    runs_per_session: int
    full_eeg_channels: int
    minimum_trials_per_class_per_session: int
    required_sensorimotor_channels: tuple[str, ...] = ("C3", "Cz", "C4")


SUPPORTED_DATASETS: dict[str, tuple[str, str, dict[str, Any]]] = {
    # The Lee adapter is pinned to the labeled offline training phase. Its
    # unlabeled online-feedback run is deliberately excluded.
    "Lee2019_MI": (
        "moabb.datasets",
        "Lee2019_MI",
        {"train_run": True, "test_run": False, "resting_state": False},
    ),
    "BNCI2014_001": ("moabb.datasets", "BNCI2014_001", {}),
    "Zhou2016": ("moabb.datasets", "Zhou2016", {}),
}

DATASET_EXPECTATIONS: dict[str, DatasetExpectation] = {
    "Lee2019_MI": DatasetExpectation(
        sessions=2,
        runs_per_session=1,
        full_eeg_channels=62,
        minimum_trials_per_class_per_session=50,
    ),
    "BNCI2014_001": DatasetExpectation(
        sessions=2,
        runs_per_session=6,
        full_eeg_channels=22,
        minimum_trials_per_class_per_session=72,
    ),
    "Zhou2016": DatasetExpectation(
        sessions=3,
        runs_per_session=2,
        full_eeg_channels=14,
        minimum_trials_per_class_per_session=50,
    ),
}

LABEL_MAPPING = {"left_hand": 0, "right_hand": 1}


def _subject_sort_key(value: str) -> tuple[int, int | str]:
    return (0, int(value)) if value.isdigit() else (1, value)


def _import_moabb_objects(dataset_name: str) -> tuple[Any, Any, Any, dict[str, Any]]:
    if dataset_name not in SUPPORTED_DATASETS:
        raise ValueError(
            f"Unsupported public dataset {dataset_name!r}; supported: {sorted(SUPPORTED_DATASETS)}"
        )
    try:
        import importlib

        import moabb
        from moabb.paradigms import LeftRightImagery
    except ImportError as error:
        raise RuntimeError(
            "MOABB is required to prepare public datasets. Install the project dependencies."
        ) from error
    module_name, class_name, constructor_kwargs = SUPPORTED_DATASETS[dataset_name]
    dataset_class = getattr(importlib.import_module(module_name), class_name)
    return moabb, LeftRightImagery, dataset_class, dict(constructor_kwargs)


def _instantiate_public_dataset(
    dataset_name: str, dataset_class: Any, constructor_kwargs: dict[str, Any]
) -> Any:
    dataset = dataset_class(**constructor_kwargs)
    if dataset_name == "Lee2019_MI":
        # MOABB 1.5.0 workaround (not a protocol change): moabb.datasets.Lee2019
        # names each subject's per-session data with the 0-indexed string
        # `str(session - 1)` (i.e. "0", "1"), but its constructor forwards the
        # *1-indexed* `sessions` argument ((1, 2) by default) to
        # `BaseDataset.__init__(selected_sessions=...)`. `BaseDataset.get_data`
        # then keeps only session keys in `{str(s) for s in _selected_sessions}`
        # == {"1", "2"}, which matches only key "1" and silently drops the
        # entire first session for every subject (verified by direct
        # introspection: `Lee2019_MI()._get_single_subject_data(1)` returns
        # sessions {"0", "1"}, but `Lee2019_MI().get_data([1])` returns only
        # {"1"}). DATASET_EXPECTATIONS requires the full two-session protocol,
        # so we neutralize this buggy post-hoc filter rather than narrow
        # sessions. If a future MOABB release changes this representation, the
        # guard below fails loudly instead of silently re-dropping data.
        if dataset._selected_sessions != [1, 2]:
            raise RuntimeError(
                "Lee2019_MI._selected_sessions no longer matches the known MOABB "
                "1.5.0 session-filtering bug this workaround targets; re-verify "
                "moabb.datasets.Lee2019 session-key behavior before proceeding."
            )
        dataset._selected_sessions = None
    return dataset


def resolve_subjects(dataset: Any, section: DatasetSection) -> list[int]:
    available = [int(value) for value in dataset.subject_list]
    if section.subjects == "all":
        selected = available
    else:
        requested = [int(value) for value in section.subjects]
        missing = sorted(set(requested).difference(available))
        if missing:
            raise ValueError(f"{section.name}: requested subjects unavailable: {missing}")
        selected = requested
    excluded = {int(value) for value in section.exclude_subjects}
    selected = [value for value in selected if value not in excluded]
    if not selected:
        raise ValueError(f"{section.name}: no subjects remain after exclusions")
    return selected


def encode_labels(labels: np.ndarray | list[Any]) -> np.ndarray:
    normalized = np.asarray([str(value).strip().lower() for value in labels], dtype=object)
    observed = set(normalized.tolist())
    expected = set(LABEL_MAPPING)
    if observed != expected:
        raise ValueError(
            f"Expected exactly {sorted(expected)} after MOABB task selection, got {sorted(observed)}"
        )
    return np.asarray([LABEL_MAPPING[value] for value in normalized], dtype=np.int8)




def validate_subject_structure(
    dataset_name: str,
    metadata: pd.DataFrame,
    y: np.ndarray,
    channels: tuple[str, ...],
    configured_channels: tuple[str, ...] | None,
) -> None:
    """Fail closed when the pinned MOABB adapter no longer matches the protocol.

    These checks are intentionally stricter than generic shape validation. A
    silently changed adapter, missing session, unexpected run collapse, or
    altered montage would invalidate a prospective cross-session comparison.
    """

    try:
        expectation = DATASET_EXPECTATIONS[dataset_name]
    except KeyError as error:
        raise ValueError(f"No structural expectation registered for {dataset_name}") from error

    sessions = sorted(metadata["session"].astype(str).unique().tolist())
    if len(sessions) != expectation.sessions:
        raise ValueError(
            f"{dataset_name}: expected {expectation.sessions} sessions, observed {len(sessions)}: "
            f"{sessions}"
        )

    for session, group in metadata.groupby("session", sort=False, observed=True):
        run_count = int(group["run"].astype(str).nunique())
        if run_count != expectation.runs_per_session:
            raise ValueError(
                f"{dataset_name} session {session}: expected "
                f"{expectation.runs_per_session} runs, observed {run_count}"
            )
        session_indices = group.index.to_numpy(dtype=int)
        values, counts = np.unique(y[session_indices], return_counts=True)
        class_counts = dict(
            zip(values.astype(int).tolist(), counts.astype(int).tolist(), strict=True)
        )
        if set(class_counts) != {0, 1}:
            raise ValueError(
                f"{dataset_name} session {session}: missing a left/right class: {class_counts}"
            )
        if min(class_counts.values()) < expectation.minimum_trials_per_class_per_session:
            raise ValueError(
                f"{dataset_name} session {session}: expected at least "
                f"{expectation.minimum_trials_per_class_per_session} trials per class, "
                f"observed {class_counts}"
            )

    observed_channels = tuple(str(value) for value in channels)
    if configured_channels is None:
        if len(observed_channels) != expectation.full_eeg_channels:
            raise ValueError(
                f"{dataset_name}: expected {expectation.full_eeg_channels} EEG channels in the "
                f"full-montage adapter, observed {len(observed_channels)}"
            )
        missing = set(expectation.required_sensorimotor_channels).difference(observed_channels)
        if missing:
            raise ValueError(
                f"{dataset_name}: full montage omits required sensorimotor channels "
                f"{sorted(missing)}"
            )
    else:
        if len(observed_channels) != len(configured_channels) or set(observed_channels) != set(
            configured_channels
        ):
            raise ValueError(
                f"{dataset_name}: requested channels {list(configured_channels)}, observed "
                f"{list(observed_channels)}"
            )


def _existing_subject_compatible(
    directory: Path,
    config: ExperimentConfig,
    dataset: str,
    subject: int,
) -> bool:
    manifest_path = directory / SUBJECT_MANIFEST
    if not manifest_path.exists():
        return False
    manifest = read_manifest(manifest_path)
    if int(manifest.get("processing_schema_version", -1)) != PROCESSING_SCHEMA_VERSION:
        raise ValueError(f"Processed schema changed for {directory}; explicitly overwrite")
    if str(manifest.get("dataset")) != dataset or str(manifest.get("subject")) != str(subject):
        raise ValueError(f"Processed shard identity mismatch in {directory}")
    if manifest.get("preprocessing") != asdict(config.preprocessing):
        raise ValueError(f"Processed preprocessing mismatch in {directory}")
    current_versions = package_versions()
    for package in ("numpy", "mne", "moabb"):
        if manifest.get("package_versions", {}).get(package) != current_versions.get(package):
            raise ValueError(
                f"{directory} was generated with a different {package} version; "
                "explicitly overwrite only after documenting the protocol change"
            )
    for filename in ("X.npy", "y.npy", "metadata.csv.gz"):
        if not (directory / filename).exists():
            raise FileNotFoundError(directory / filename)
    return True


def prepare_subject(
    config: ExperimentConfig,
    dataset_section: DatasetSection,
    subject: int,
    overwrite: bool | None = None,
) -> Path:
    overwrite_effective = config.runtime.overwrite_processed if overwrite is None else overwrite
    target_dir = subject_directory(config.processed_dir, dataset_section.name, subject)
    if not overwrite_effective and _existing_subject_compatible(
        target_dir, config, dataset_section.name, subject
    ):
        return target_dir

    moabb, LeftRightImagery, dataset_class, constructor_kwargs = _import_moabb_objects(
        dataset_section.name
    )
    cache_root = Path(config.experiment.cache_root).resolve()
    cache_root.mkdir(parents=True, exist_ok=True)
    if hasattr(moabb, "set_download_dir"):
        moabb.set_download_dir(str(cache_root))
    if hasattr(moabb, "set_log_level"):
        moabb.set_log_level("warning")

    dataset = _instantiate_public_dataset(dataset_section.name, dataset_class, constructor_kwargs)
    paradigm = LeftRightImagery(
        fmin=config.preprocessing.fmin,
        fmax=config.preprocessing.fmax,
        tmin=config.preprocessing.tmin,
        tmax=config.preprocessing.tmax,
        channels=(
            None if config.preprocessing.channels is None else list(config.preprocessing.channels)
        ),
        resample=config.preprocessing.resample,
        baseline=None,
    )
    epochs, labels, metadata = paradigm.get_data(
        dataset=dataset,
        subjects=[int(subject)],
        return_epochs=True,
    )
    if not hasattr(epochs, "get_data"):
        raise TypeError(f"Expected an MNE Epochs-like object, got {type(epochs)!r}")
    X = epochs.get_data(copy=True)
    dtype = np.float32 if config.preprocessing.dtype == "float32" else np.float64
    X = np.asarray(X, dtype=dtype, order="C")
    y = encode_labels(labels)
    metadata = pd.DataFrame(metadata).reset_index(drop=True)
    required = {"subject", "session", "run"}
    missing = required.difference(metadata.columns)
    if missing:
        raise ValueError(f"MOABB metadata missing columns: {sorted(missing)}")
    if metadata[["subject", "session", "run"]].isna().any().any():
        raise ValueError("MOABB returned missing subject/session/run metadata")

    def normalize_identifier(value: Any) -> str:
        if isinstance(value, (int, np.integer)):
            return str(int(value))
        if isinstance(value, (float, np.floating)) and float(value).is_integer():
            return str(int(value))
        return str(value).strip()

    for column in ("subject", "session", "run"):
        metadata[column] = metadata[column].map(normalize_identifier)
        if (metadata[column] == "").any():
            raise ValueError(f"MOABB returned blank {column} metadata")
    if set(metadata["subject"].unique()) != {str(subject)}:
        raise ValueError(
            f"MOABB returned unexpected subject values for target {subject}: "
            f"{sorted(metadata['subject'].unique())}"
        )
    validate_subject_structure(
        dataset_section.name,
        metadata,
        y,
        tuple(str(value) for value in epochs.ch_names),
        config.preprocessing.channels,
    )
    metadata["label_original"] = np.asarray(labels, dtype=str)
    metadata["label"] = y.astype(int)
    metadata["trial_index"] = np.arange(len(metadata), dtype=int)
    metadata["trial_uid"] = [
        f"{dataset_section.name}:{subject}:{session}:{run}:{index:05d}"
        for index, (session, run) in enumerate(
            zip(metadata["session"], metadata["run"], strict=True)
        )
    ]

    shard = SubjectShard(
        dataset=dataset_section.name,
        subject=str(subject),
        X=X,
        y=y.astype(int),
        metadata=metadata,
        channels=tuple(str(value) for value in epochs.ch_names),
        sfreq=float(epochs.info["sfreq"]),
    )
    shard.validate()
    return save_subject_shard(
        shard=shard,
        directory=target_dir,
        preprocessing=asdict(config.preprocessing),
        package_versions=package_versions(),
        overwrite=overwrite_effective,
    )


def _discover_subjects(dataset_dir: Path) -> list[str]:
    return sorted(
        (
            path.name.removeprefix("subject-")
            for path in dataset_dir.glob("subject-*")
            if (path / SUBJECT_MANIFEST).exists()
        ),
        key=_subject_sort_key,
    )


def prepare_dataset(config: ExperimentConfig, section: DatasetSection) -> Path:
    _, _, dataset_class, constructor_kwargs = _import_moabb_objects(section.name)
    dataset = _instantiate_public_dataset(section.name, dataset_class, constructor_kwargs)
    requested_subjects = resolve_subjects(dataset, section)
    for subject in requested_subjects:
        prepare_subject(config, section, subject)
    dataset_dir = config.processed_dir / section.name
    # The manifest describes every compatible shard currently present.  A pilot
    # run therefore cannot make previously prepared full-cohort subjects vanish.
    all_prepared_subjects = _discover_subjects(dataset_dir)
    write_dataset_manifest(
        dataset_dir=dataset_dir,
        dataset=section.name,
        preprocessing_fingerprint=config.preprocessing_fingerprint,
        preprocessing=asdict(config.preprocessing),
        subjects=all_prepared_subjects,
        package_versions=package_versions(),
    )
    return dataset_dir


def prepare_all_datasets(config: ExperimentConfig) -> list[Path]:
    config.processed_dir.mkdir(parents=True, exist_ok=True)
    return [prepare_dataset(config, section) for section in config.datasets]


def _selected_prepared_subjects(
    config: ExperimentConfig,
    section: DatasetSection,
) -> list[str]:
    prepared = list_prepared_subjects(config.processed_dir, section.name)
    prepared_set = set(prepared)
    if section.subjects == "all":
        selected = prepared
    else:
        selected = [str(value) for value in section.subjects]
        missing = sorted(set(selected).difference(prepared_set), key=_subject_sort_key)
        if missing:
            raise FileNotFoundError(f"{section.name}: configured subjects not prepared: {missing}")
    excluded = {str(value) for value in section.exclude_subjects}
    return [value for value in selected if value not in excluded]


def validate_dataset(
    config: ExperimentConfig,
    section: DatasetSection,
    verify_checksums: bool = True,
) -> pd.DataFrame:
    dataset_dir = config.processed_dir / section.name
    manifest_path = dataset_dir / DATASET_MANIFEST
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing dataset manifest: {manifest_path}")
    manifest = read_manifest(manifest_path)
    if int(manifest.get("processing_schema_version", -1)) != PROCESSING_SCHEMA_VERSION:
        raise ValueError(f"Unsupported processing schema for {section.name}")
    if manifest["preprocessing_fingerprint"] != config.preprocessing_fingerprint:
        raise ValueError(
            f"Preprocessing fingerprint mismatch for {section.name}: "
            f"{manifest['preprocessing_fingerprint']} != {config.preprocessing_fingerprint}"
        )
    # Compare against the JSON-native representation, not the raw dataclass
    # payload: fields such as `channels` (tuple[str, ...] | None) round-trip
    # through the on-disk JSON manifest as lists, and `[...] != (...)` in
    # Python even when they encode the same value.
    expected_preprocessing = json.loads(json.dumps(asdict(config.preprocessing)))
    if manifest.get("preprocessing") != expected_preprocessing:
        raise ValueError(f"Preprocessing payload mismatch for {section.name}")

    subjects = _selected_prepared_subjects(config, section)
    rows: list[dict[str, Any]] = []
    reference_channels: tuple[str, ...] | None = None
    reference_samples: int | None = None
    reference_sfreq: float | None = None
    manifest_hashes = manifest.get("subject_manifest_sha256", {})
    for subject in subjects:
        subject_dir = subject_directory(config.processed_dir, section.name, subject)
        subject_manifest_path = subject_dir / SUBJECT_MANIFEST
        expected_manifest_hash = manifest_hashes.get(str(subject))
        if expected_manifest_hash is None:
            raise ValueError(f"Dataset manifest omits configured subject {subject}")
        observed_manifest_hash = sha256_file(subject_manifest_path)
        if observed_manifest_hash != expected_manifest_hash:
            raise ValueError(f"Subject manifest changed after dataset manifest: {subject_dir}")
        shard = load_subject_shard(
            subject_dir,
            mmap_mode="r",
            verify_checksums=verify_checksums,
        )
        if reference_channels is None:
            reference_channels = shard.channels
            reference_samples = int(shard.X.shape[2])
            reference_sfreq = shard.sfreq
        else:
            if shard.channels != reference_channels:
                raise ValueError(f"{section.name}: channel order differs for subject {subject}")
            if shard.X.shape[2] != reference_samples:
                raise ValueError(f"{section.name}: sample length differs for subject {subject}")
            if not np.isclose(shard.sfreq, reference_sfreq):
                raise ValueError(f"{section.name}: sampling rate differs for subject {subject}")
        values, counts = np.unique(shard.y, return_counts=True)
        class_counts = dict(zip(values.astype(int), counts.astype(int), strict=True))
        groups = shard.metadata["session"].astype(str) + "::" + shard.metadata["run"].astype(str)
        split = make_target_split(
            shard.metadata,
            shard.y,
            config.split,
            seed=derive_seed(config.experiment.seed, section.name, subject, "validation_split"),
        )
        calibration_values, calibration_n = np.unique(
            shard.y[split.calibration_pool_idx], return_counts=True
        )
        calibration_counts = dict(
            zip(calibration_values.astype(int), calibration_n.astype(int), strict=True)
        )
        test_values, test_n = np.unique(shard.y[split.test_idx], return_counts=True)
        test_counts = dict(zip(test_values.astype(int), test_n.astype(int), strict=True))
        peak_to_peak_uv = np.ptp(np.asarray(shard.X), axis=2) * 1e6
        rows.append(
            {
                "dataset": section.name,
                "subject": str(subject),
                "trials": len(shard.y),
                "class_0": class_counts.get(0, 0),
                "class_1": class_counts.get(1, 0),
                "sessions": int(shard.metadata["session"].nunique()),
                "runs": int(groups.nunique()),
                "channels": len(shard.channels),
                "samples": shard.X.shape[2],
                "sfreq": shard.sfreq,
                "split_eligible": True,
                "split_strategy": split.strategy,
                "calibration_pool_trials": int(len(split.calibration_pool_idx)),
                "calibration_pool_class_0": int(calibration_counts.get(0, 0)),
                "calibration_pool_class_1": int(calibration_counts.get(1, 0)),
                "test_trials": int(len(split.test_idx)),
                "test_class_0": int(test_counts.get(0, 0)),
                "test_class_1": int(test_counts.get(1, 0)),
                "test_groups": ";".join(split.test_groups),
                "median_epoch_channel_peak_to_peak_uv": float(np.median(peak_to_peak_uv)),
                "maximum_epoch_channel_peak_to_peak_uv": float(np.max(peak_to_peak_uv)),
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError(f"No configured prepared subjects found for {section.name}")
    return frame


def validate_all_datasets(
    config: ExperimentConfig,
    verify_checksums: bool = True,
) -> pd.DataFrame:
    frames = [validate_dataset(config, section, verify_checksums) for section in config.datasets]
    return pd.concat(frames, ignore_index=True)


def dataset_manifest_digest(config: ExperimentConfig, dataset: str) -> str:
    path = config.processed_dir / dataset / DATASET_MANIFEST
    if not path.exists():
        raise FileNotFoundError(path)
    return sha256_file(path)


def describe_prepared_data(config: ExperimentConfig) -> str:
    frame = validate_all_datasets(config, verify_checksums=False)
    return json.dumps(frame.to_dict(orient="records"), indent=2)
