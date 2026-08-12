"""Small deterministic utilities shared across the project."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Iterable


def canonical_json(value: Any) -> str:
    """Serialize a value deterministically for scientific fingerprints."""
    if is_dataclass(value):
        value = asdict(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(value: Any, length: int | None = 16) -> str:
    digest = sha256_text(canonical_json(value))
    return digest if length is None else digest[:length]


def derive_seed(global_seed: int, *parts: object) -> int:
    """Derive a stable NumPy-compatible seed without Python's randomized hash()."""
    payload = canonical_json([int(global_seed), *[str(part) for part in parts]])
    return int.from_bytes(hashlib.sha256(payload.encode("utf-8")).digest()[:4], "big")


def ensure_unique(values: Iterable[Any], name: str) -> None:
    values_list = list(values)
    if len(values_list) != len(set(values_list)):
        raise ValueError(f"{name} must contain unique values: {values_list}")


def json_default(value: Any) -> Any:
    """JSON serializer for NumPy/pandas scalar-like values."""
    try:
        import numpy as np

        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
    except ImportError:
        pass
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def atomic_write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(target)
