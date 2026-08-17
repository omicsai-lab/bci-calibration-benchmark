"""Environment validation for reproducible public-data and synthetic runs."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import sys
from pathlib import Path
from typing import Any

from .config import ExperimentConfig
from .provenance import PACKAGES, package_versions, repository_source_digest

REQUIRED_PUBLIC_PACKAGES = {
    "numpy": None,
    "pandas": None,
    "scipy": None,
    "scikit-learn": None,
    "mne": None,
    "moabb": "1.5.0",
    "statsmodels": None,
}


def validate_environment(
    *,
    repository_root: str | Path = ".",
    config: ExperimentConfig | None = None,
    require_public_data_stack: bool = True,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    versions = package_versions()
    required = REQUIRED_PUBLIC_PACKAGES if require_public_data_stack else {
        name: expected for name, expected in REQUIRED_PUBLIC_PACKAGES.items() if name != "moabb"
    }
    for package, expected in required.items():
        observed = versions.get(package)
        if observed is None:
            errors.append(f"Missing required package: {package}")
        elif expected is not None and observed != expected:
            errors.append(f"{package} must be {expected}; observed {observed}")
    if config is not None:
        try:
            config.validate()
        except Exception as error:
            errors.append(f"Configuration validation failed: {error}")
        if "eegnet" in config.methods:
            for package in ("torch", "braindecode"):
                if versions.get(package) is None:
                    errors.append(f"Method eegnet requires missing optional package: {package}")
        for path_name, path_value in (
            ("output_root", config.experiment.output_root),
            ("processed_root", config.experiment.processed_root),
            ("cache_root", config.experiment.cache_root),
        ):
            parent = Path(path_value).expanduser().resolve().parent
            if not parent.exists():
                warnings.append(f"Parent directory for {path_name} does not yet exist: {parent}")
    installed_distributions: dict[str, str | None] = {}
    for package in PACKAGES:
        try:
            installed_distributions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            installed_distributions[package] = None
    return {
        "status": "ok" if not errors else "failed",
        "python": sys.version,
        "platform": platform.platform(),
        "package_versions": installed_distributions,
        "repository_source_sha256": repository_source_digest(repository_root),
        "errors": errors,
        "warnings": warnings,
        "public_data_stack_required": require_public_data_stack,
    }


def environment_report_json(**kwargs: Any) -> str:
    return json.dumps(validate_environment(**kwargs), indent=2, sort_keys=True) + "\n"
