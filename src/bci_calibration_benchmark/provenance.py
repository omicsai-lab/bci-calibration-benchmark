"""Environment, git, source-tree, and run provenance capture."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import subprocess
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import ExperimentConfig
from .utils import atomic_write_text, fingerprint, json_default, sha256_file

PACKAGES = (
    "numpy",
    "pandas",
    "scipy",
    "scikit-learn",
    "mne",
    "moabb",
    "statsmodels",
    "torch",
    "braindecode",
)


def package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def git_state(root: str | Path = ".") -> dict[str, Any]:
    cwd = Path(root)
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=cwd, text=True, stderr=subprocess.DEVNULL
        ).strip()
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=cwd, text=True, stderr=subprocess.DEVNULL
        )
        return {"commit": commit, "dirty": bool(status.strip())}
    except (FileNotFoundError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def repository_source_digest(root: str | Path = ".") -> str | None:
    """Hash executable/configuration sources even when no git repository is present."""
    root_path = Path(root).resolve()
    if not root_path.exists():
        return None
    candidates: list[Path] = []
    for relative in ("pyproject.toml", "environment.yml", "Dockerfile", "Makefile"):
        path = root_path / relative
        if path.is_file():
            candidates.append(path)
    for directory, patterns in (
        ("src", ("*.py",)),
        ("scripts", ("*.py",)),
        ("configs", ("*.yaml", "*.yml")),
    ):
        base = root_path / directory
        if not base.exists():
            continue
        for pattern in patterns:
            candidates.extend(path for path in base.rglob(pattern) if path.is_file())
    if not candidates:
        return None
    payload = [
        {
            "path": str(path.relative_to(root_path).as_posix()),
            "sha256": sha256_file(path),
        }
        for path in sorted(set(candidates))
    ]
    return fingerprint(payload, length=None)


def build_run_manifest(config: ExperimentConfig, repository_root: str | Path = ".") -> dict[str, Any]:
    payload = asdict(config)
    payload.pop("config_path", None)
    return {
        "schema_version": 1,
        "experiment_name": config.experiment.name,
        "experiment_fingerprint": config.experiment_fingerprint,
        "preprocessing_fingerprint": config.preprocessing_fingerprint,
        "started_utc": datetime.now(UTC).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "package_versions": package_versions(),
        "git": git_state(repository_root),
        "repository_source_sha256": repository_source_digest(repository_root),
        "configuration": payload,
    }


def write_run_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    atomic_write_text(
        path,
        json.dumps(manifest, indent=2, sort_keys=True, default=json_default) + "\n",
    )
