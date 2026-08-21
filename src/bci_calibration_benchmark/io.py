"""Transparent storage for participant-level processed EEG shards and results."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import PROCESSING_SCHEMA_VERSION
from .data_types import SubjectShard
from .utils import atomic_write_text, json_default, sha256_file

SUBJECT_MANIFEST = "manifest.json"
DATASET_MANIFEST = "dataset_manifest.json"


def normalized_subject_id(subject: str | int) -> str:
    return str(subject)


def _subject_sort_key(value: str) -> tuple[int, int | str]:
    return (0, int(value)) if value.isdigit() else (1, value)


def subject_directory(processed_dir: str | Path, dataset: str, subject: str | int) -> Path:
    return Path(processed_dir) / dataset / f"subject-{normalized_subject_id(subject)}"


def _validate_existing_subject_manifest(
    manifest: dict[str, Any],
    shard: SubjectShard,
    preprocessing: dict[str, Any],
    package_versions: dict[str, str | None],
    directory: Path,
) -> None:
    if int(manifest.get("processing_schema_version", -1)) != PROCESSING_SCHEMA_VERSION:
        raise ValueError(
            f"Existing processed shard uses a different processing schema: {directory}"
        )
    if str(manifest.get("dataset")) != shard.dataset or str(manifest.get("subject")) != str(shard.subject):
        raise ValueError(f"Existing shard identity does not match requested data: {directory}")
    if manifest.get("preprocessing") != preprocessing:
        raise ValueError(
            f"Existing shard preprocessing differs; use overwrite or a new fingerprint: {directory}"
        )
    for package in ("numpy", "mne", "moabb"):
        existing = manifest.get("package_versions", {}).get(package)
        current = package_versions.get(package)
        if existing != current:
            raise ValueError(
                f"Existing shard {directory} was prepared with {package}={existing}, current={current}; "
                "explicitly overwrite after documenting the change"
            )
    for filename in ("X.npy", "y.npy", "metadata.csv.gz"):
        if not (directory / filename).exists():
            raise FileNotFoundError(f"Existing manifest references a missing file: {directory / filename}")


def save_subject_shard(
    shard: SubjectShard,
    directory: str | Path,
    preprocessing: dict[str, Any],
    package_versions: dict[str, str | None],
    overwrite: bool = False,
) -> Path:
    shard.validate()
    directory = Path(directory)
    manifest_path = directory / SUBJECT_MANIFEST
    if directory.exists() and manifest_path.exists() and not overwrite:
        manifest = read_manifest(manifest_path)
        _validate_existing_subject_manifest(
            manifest,
            shard,
            preprocessing,
            package_versions,
            directory,
        )
        return directory
    directory.mkdir(parents=True, exist_ok=True)

    x_path = directory / "X.npy"
    y_path = directory / "y.npy"
    metadata_path = directory / "metadata.csv.gz"

    np.save(x_path, np.asarray(shard.X), allow_pickle=False)
    np.save(y_path, np.asarray(shard.y, dtype=np.int8), allow_pickle=False)
    metadata = shard.metadata.copy()
    for column in ("subject", "session", "run", "trial_uid"):
        metadata[column] = metadata[column].astype(str)
    metadata.to_csv(
        metadata_path,
        index=False,
        compression={"method": "gzip", "compresslevel": 6, "mtime": 0},
    )

    values, counts = np.unique(shard.y, return_counts=True)
    class_counts = {
        str(int(label)): int(count)
        for label, count in zip(values, counts, strict=True)
    }
    group_counts = (
        metadata.assign(group_id=metadata["session"] + "::" + metadata["run"])
        .groupby(["session", "run"], dropna=False)
        .size()
        .astype(int)
        .to_dict()
    )
    group_counts_json = {
        f"{session}::{run}": count for (session, run), count in group_counts.items()
    }

    manifest = {
        "schema_version": 1,
        "processing_schema_version": PROCESSING_SCHEMA_VERSION,
        "dataset": shard.dataset,
        "subject": str(shard.subject),
        "shape": list(shard.X.shape),
        "dtype": str(shard.X.dtype),
        "sfreq": float(shard.sfreq),
        "channels": list(shard.channels),
        "class_mapping": {"left_hand": 0, "right_hand": 1},
        "class_counts": class_counts,
        "group_counts": group_counts_json,
        "preprocessing": preprocessing,
        "package_versions": package_versions,
        "files": {
            "X.npy": sha256_file(x_path),
            "y.npy": sha256_file(y_path),
            "metadata.csv.gz": sha256_file(metadata_path),
        },
    }
    atomic_write_text(
        manifest_path,
        json.dumps(manifest, indent=2, sort_keys=True, default=json_default) + "\n",
    )
    return directory


def read_manifest(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_subject_shard(
    directory: str | Path,
    mmap_mode: str | None = "r",
    verify_checksums: bool = False,
) -> SubjectShard:
    directory = Path(directory)
    manifest = read_manifest(directory / SUBJECT_MANIFEST)
    if int(manifest.get("processing_schema_version", -1)) != PROCESSING_SCHEMA_VERSION:
        raise ValueError(f"Unsupported processed-data schema in {directory}")
    if verify_checksums:
        for filename, expected in manifest["files"].items():
            observed = sha256_file(directory / filename)
            if observed != expected:
                raise ValueError(
                    f"Checksum mismatch for {directory / filename}: expected {expected}, got {observed}"
                )
    X = np.load(directory / "X.npy", mmap_mode=mmap_mode, allow_pickle=False)
    y = np.load(directory / "y.npy", mmap_mode=mmap_mode, allow_pickle=False).astype(int, copy=False)
    metadata = pd.read_csv(directory / "metadata.csv.gz", dtype=str)
    shard = SubjectShard(
        dataset=str(manifest["dataset"]),
        subject=str(manifest["subject"]),
        X=X,
        y=y,
        metadata=metadata,
        channels=tuple(str(value) for value in manifest["channels"]),
        sfreq=float(manifest["sfreq"]),
        source_dir=directory,
    )
    shard.validate()
    expected_shape = tuple(int(value) for value in manifest["shape"])
    if shard.X.shape != expected_shape:
        raise ValueError(f"Stored X shape differs from manifest in {directory}")
    if str(shard.X.dtype) != str(manifest["dtype"]):
        raise ValueError(f"Stored X dtype differs from manifest in {directory}")
    return shard


def write_dataset_manifest(
    dataset_dir: str | Path,
    dataset: str,
    preprocessing_fingerprint: str,
    preprocessing: dict[str, Any],
    subjects: Iterable[str | int],
    package_versions: dict[str, str | None],
) -> Path:
    dataset_dir = Path(dataset_dir)
    dataset_dir.mkdir(parents=True, exist_ok=True)
    subject_ids = sorted({str(subject) for subject in subjects}, key=_subject_sort_key)
    subject_manifests: dict[str, str] = {}
    for subject in subject_ids:
        manifest_path = subject_directory(dataset_dir.parent, dataset, subject) / SUBJECT_MANIFEST
        if not manifest_path.exists():
            raise FileNotFoundError(f"Missing subject manifest: {manifest_path}")
        subject_manifests[subject] = sha256_file(manifest_path)
    payload = {
        "schema_version": 1,
        "processing_schema_version": PROCESSING_SCHEMA_VERSION,
        "dataset": dataset,
        "preprocessing_fingerprint": preprocessing_fingerprint,
        "preprocessing": preprocessing,
        "subjects": subject_ids,
        "n_subjects": len(subject_ids),
        "subject_manifest_sha256": subject_manifests,
        "package_versions": package_versions,
    }
    path = dataset_dir / DATASET_MANIFEST
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True, default=json_default) + "\n")
    return path


def list_prepared_subjects(processed_dir: str | Path, dataset: str) -> list[str]:
    dataset_dir = Path(processed_dir) / dataset
    manifest_path = dataset_dir / DATASET_MANIFEST
    if manifest_path.exists():
        manifest = read_manifest(manifest_path)
        return [str(value) for value in manifest["subjects"]]
    return sorted(
        (
            path.name.removeprefix("subject-")
            for path in dataset_dir.glob("subject-*")
            if (path / SUBJECT_MANIFEST).exists()
        ),
        key=_subject_sort_key,
    )


def append_csv(path: str | Path, rows: list[dict[str, Any]], columns: list[str] | None = None) -> None:
    if not rows:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    if columns is not None:
        for column in columns:
            if column not in frame:
                frame[column] = None
        frame = frame[columns]
    frame.to_csv(path, mode="a", header=not path.exists(), index=False)


def write_dataframe_atomic(
    frame: pd.DataFrame,
    path: str | Path,
    compression: str | None = None,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False, compression=compression)
    temporary.replace(path)
