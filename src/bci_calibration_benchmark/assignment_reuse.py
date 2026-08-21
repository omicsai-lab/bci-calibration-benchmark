"""Assignment reuse and the independent-regeneration equality gate.

Human-reviewed decision (``docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md``,
decision 2, approved): the EA sensitivity must literally reuse the primary
run's four assignment artifacts (``split_assignments.csv.gz``,
``calibration_assignments.csv.gz``, ``source_selection.csv``,
``source_trial_assignments.csv.gz``), and must also regenerate them
independently via the same frozen deterministic seed machinery used by the
confirmatory run, failing closed unless the two are exactly identical.

This module deliberately does not import or modify anything in
``runner.py`` beyond reusing already-existing, private row-building helpers
by reference -- it never re-implements or edits the confirmatory
``run_benchmark`` loop, so the closed primary and prespecified-sensitivity
result directories cannot be affected by anything in this module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import ExperimentConfig
from .data_types import CalibrationSample, SubjectShard, TargetSplit
from .io import list_prepared_subjects, load_subject_shard, subject_directory
from .runner import (
    CALIBRATION_ASSIGNMENT_COLUMNS,
    SOURCE_SELECTION_COLUMNS,
    SOURCE_TRIAL_ASSIGNMENT_COLUMNS,
    SPLIT_ASSIGNMENT_COLUMNS,
    _calibration_assignment_rows,
    _configured_subjects,
    _split_assignment_rows,
    _subject_sort_key,
)
from .sampling import choose_source_subjects, nested_calibration_samples, source_indices_for_subject
from .splits import make_target_split
from .utils import derive_seed, fingerprint, sha256_file

ASSIGNMENT_FILES: tuple[str, ...] = (
    "split_assignments.csv.gz",
    "calibration_assignments.csv.gz",
    "source_selection.csv",
    "source_trial_assignments.csv.gz",
)


@dataclass(frozen=True)
class ReusedAssignments:
    primary_output_dir: Path
    primary_experiment_fingerprint: str | None
    primary_git_commit: str | None
    file_sha256: dict[str, str]
    split_assignments: pd.DataFrame
    calibration_assignments: pd.DataFrame
    source_selection: pd.DataFrame
    source_trial_assignments: pd.DataFrame


def load_reused_assignments(primary_output_dir: str | Path) -> ReusedAssignments:
    primary_output_dir = Path(primary_output_dir)
    for name in ASSIGNMENT_FILES:
        if not (primary_output_dir / name).exists():
            raise FileNotFoundError(
                f"Assignment-reuse source is missing required file: {primary_output_dir / name}"
            )
    file_sha256 = {name: sha256_file(primary_output_dir / name) for name in ASSIGNMENT_FILES}
    manifest_path = primary_output_dir / "run_manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    split = pd.read_csv(
        primary_output_dir / "split_assignments.csv.gz",
        dtype={"target_subject": str, "split_id": str, "trial_uid": str, "session": str, "run": str},
        low_memory=False,
    )
    calibration = pd.read_csv(
        primary_output_dir / "calibration_assignments.csv.gz",
        dtype={"target_subject": str, "split_id": str, "trial_uid": str, "session": str, "run": str},
        low_memory=False,
    )
    source_selection = pd.read_csv(
        primary_output_dir / "source_selection.csv",
        dtype={"target_subject": str, "source_subject": str},
        low_memory=False,
    )
    source_trial = pd.read_csv(
        primary_output_dir / "source_trial_assignments.csv.gz",
        dtype={"target_subject": str, "source_subject": str, "trial_uid": str, "session": str, "run": str},
        low_memory=False,
    )
    missing = {
        "split_assignments.csv.gz": set(SPLIT_ASSIGNMENT_COLUMNS) - set(split.columns),
        "calibration_assignments.csv.gz": set(CALIBRATION_ASSIGNMENT_COLUMNS) - set(calibration.columns),
        "source_selection.csv": set(SOURCE_SELECTION_COLUMNS) - set(source_selection.columns),
        "source_trial_assignments.csv.gz": set(SOURCE_TRIAL_ASSIGNMENT_COLUMNS) - set(source_trial.columns),
    }
    for name, absent in missing.items():
        if absent:
            raise ValueError(f"{name}: missing expected columns {sorted(absent)}")
    return ReusedAssignments(
        primary_output_dir=primary_output_dir,
        primary_experiment_fingerprint=manifest.get("experiment_fingerprint"),
        primary_git_commit=(manifest.get("git") or {}).get("commit"),
        file_sha256=file_sha256,
        split_assignments=split,
        calibration_assignments=calibration,
        source_selection=source_selection,
        source_trial_assignments=source_trial,
    )


def _regenerate_assignments(
    config: ExperimentConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Recompute the four assignment artifacts from scratch.

    Uses exactly the same deterministic functions and seed-derivation call
    sites as ``runner.run_benchmark`` (``make_target_split``,
    ``nested_calibration_samples``, ``choose_source_subjects``,
    ``source_indices_for_subject``, and the same private row-building
    helpers), without loading full X arrays for fitting or writing any
    output file. This is the independent-regeneration half of the reuse
    equality gate; ``run_benchmark`` itself is never called or modified.
    """
    split_rows: list[dict[str, Any]] = []
    calibration_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    source_trial_rows: list[dict[str, Any]] = []
    for section in config.datasets:
        prepared = list_prepared_subjects(config.processed_dir, section.name)
        all_subjects = _configured_subjects(section, prepared)
        for target_subject in all_subjects:
            target = load_subject_shard(
                subject_directory(config.processed_dir, section.name, target_subject),
                mmap_mode="r",
                verify_checksums=False,
            )
            source_seed = derive_seed(
                config.experiment.seed, section.name, target.subject, "source_subjects"
            )
            source_subjects = choose_source_subjects(
                all_subjects,
                target_subject=target.subject,
                source_config=config.source,
                seed=source_seed,
            )
            for source_subject in source_subjects:
                shard = load_subject_shard(
                    subject_directory(config.processed_dir, section.name, source_subject),
                    mmap_mode="r",
                    verify_checksums=False,
                )
                selection_seed = derive_seed(
                    config.experiment.seed,
                    section.name,
                    target.subject,
                    source_subject,
                    "source_trials",
                )
                indices = source_indices_for_subject(shard.y, config.source, seed=selection_seed)
                selected_y = np.asarray(shard.y[indices], dtype=int)
                selected_metadata = shard.metadata.iloc[indices].reset_index(drop=True)
                selected_uids = selected_metadata["trial_uid"].astype(str).tolist()
                source_rows.append(
                    {
                        "dataset": section.name,
                        "target_subject": str(target_subject),
                        "source_subject": str(source_subject),
                        "selection_seed": selection_seed,
                        "selected_trials": int(len(indices)),
                        "class_0_trials": int(np.sum(selected_y == 0)),
                        "class_1_trials": int(np.sum(selected_y == 1)),
                        "selected_trial_uid_sha256": fingerprint(sorted(selected_uids), length=None),
                    }
                )
                for index, metadata in selected_metadata.iterrows():
                    source_trial_rows.append(
                        {
                            "dataset": section.name,
                            "target_subject": str(target_subject),
                            "source_subject": str(source_subject),
                            "selection_seed": selection_seed,
                            "trial_uid": str(metadata["trial_uid"]),
                            "session": str(metadata["session"]),
                            "run": str(metadata["run"]),
                            "label": int(selected_y[index]),
                        }
                    )
            for repeat in range(config.split.repeats):
                split_seed = derive_seed(
                    config.experiment.seed, section.name, target_subject, repeat, "split"
                )
                split = make_target_split(target.metadata, target.y, config.split, split_seed)
                calibration_seed = derive_seed(
                    config.experiment.seed, section.name, target_subject, repeat, "calibration"
                )
                samples = nested_calibration_samples(
                    target.y, split.calibration_pool_idx, config.calibration, calibration_seed
                )
                split_rows.extend(_split_assignment_rows(section.name, target, repeat, split))
                calibration_rows.extend(
                    _calibration_assignment_rows(section.name, target, repeat, split, samples)
                )
    return (
        pd.DataFrame(split_rows, columns=SPLIT_ASSIGNMENT_COLUMNS),
        pd.DataFrame(calibration_rows, columns=CALIBRATION_ASSIGNMENT_COLUMNS),
        pd.DataFrame(source_rows, columns=SOURCE_SELECTION_COLUMNS),
        pd.DataFrame(source_trial_rows, columns=SOURCE_TRIAL_ASSIGNMENT_COLUMNS),
    )


def _assert_frames_equal(reused: pd.DataFrame, regenerated: pd.DataFrame, columns: list[str], name: str) -> int:
    def _canonicalize(frame: pd.DataFrame) -> pd.DataFrame:
        canonical = frame[columns].astype(str).copy()
        return canonical.sort_values(columns, kind="stable").reset_index(drop=True)

    a = _canonicalize(reused)
    b = _canonicalize(regenerated)
    if len(a) != len(b) or not a.equals(b):
        raise AssertionError(
            f"{name}: reused primary assignments do not exactly match independently "
            f"regenerated assignments (reused rows={len(a)}, regenerated rows={len(b)}). "
            "This is a hard leakage/provenance failure; the EA run must stop."
        )
    return len(a)


def verify_assignment_reuse(config: ExperimentConfig, reused: ReusedAssignments) -> dict[str, Any]:
    """Fail-closed equality gate: reused primary assignments vs. a fresh, independent regeneration.

    Raises ``AssertionError`` on any mismatch. Returns a small report on success.
    """
    regen_split, regen_calibration, regen_source, regen_source_trial = _regenerate_assignments(config)
    report: dict[str, Any] = {"status": "ok"}
    report["split_assignments_rows"] = _assert_frames_equal(
        reused.split_assignments, regen_split, SPLIT_ASSIGNMENT_COLUMNS, "split_assignments.csv.gz"
    )
    report["calibration_assignments_rows"] = _assert_frames_equal(
        reused.calibration_assignments,
        regen_calibration,
        CALIBRATION_ASSIGNMENT_COLUMNS,
        "calibration_assignments.csv.gz",
    )
    report["source_selection_rows"] = _assert_frames_equal(
        reused.source_selection, regen_source, SOURCE_SELECTION_COLUMNS, "source_selection.csv"
    )
    report["source_trial_assignment_rows"] = _assert_frames_equal(
        reused.source_trial_assignments,
        regen_source_trial,
        SOURCE_TRIAL_ASSIGNMENT_COLUMNS,
        "source_trial_assignments.csv.gz",
    )
    return report


def target_split_from_reused(
    dataset: str, target: SubjectShard, repeat: int, split_rows: pd.DataFrame
) -> TargetSplit:
    """Reconstruct a ``TargetSplit`` from this target/repeat's reused split-assignment rows.

    Filters on ``dataset`` as well as ``target_subject``: subject-ID strings
    are reused across datasets (e.g. every dataset has a "subject 1"), so
    filtering on ``target_subject`` alone would silently mix rows from an
    unrelated dataset's participant of the same ID into this target's split.
    """
    rows = split_rows.loc[
        (split_rows["dataset"].astype(str) == str(dataset))
        & (split_rows["target_subject"].astype(str) == str(target.subject))
        & (split_rows["repeat"].astype(int) == int(repeat))
    ]
    if rows.empty:
        raise ValueError(
            f"No reused split-assignment rows for dataset={dataset}, subject={target.subject}, repeat={repeat}"
        )
    uid_to_pos = {uid: pos for pos, uid in enumerate(target.metadata["trial_uid"].astype(str))}
    missing_uids = set(rows["trial_uid"].astype(str)) - set(uid_to_pos)
    if missing_uids:
        raise ValueError(
            f"Reused split-assignment trial UIDs not found in the loaded target shard for "
            f"subject={target.subject}: {sorted(missing_uids)[:5]}"
        )
    calibration_idx = np.asarray(
        sorted(uid_to_pos[u] for u in rows.loc[rows["role"] == "calibration_pool", "trial_uid"].astype(str)),
        dtype=int,
    )
    test_idx = np.asarray(
        sorted(uid_to_pos[u] for u in rows.loc[rows["role"] == "test", "trial_uid"].astype(str)),
        dtype=int,
    )
    split_ids = rows["split_id"].astype(str).unique()
    strategies = rows["split_strategy"].astype(str).unique()
    if len(split_ids) != 1 or len(strategies) != 1:
        raise ValueError(f"Ambiguous reused split identity for subject={target.subject}, repeat={repeat}")
    group_id = target.metadata["session"].astype(str) + "::" + target.metadata["run"].astype(str)
    calibration_groups = tuple(sorted(group_id.iloc[calibration_idx].unique().tolist()))
    test_groups = tuple(sorted(group_id.iloc[test_idx].unique().tolist()))
    split = TargetSplit(
        calibration_pool_idx=calibration_idx,
        test_idx=test_idx,
        calibration_groups=calibration_groups,
        test_groups=test_groups,
        strategy=str(strategies[0]),
        split_id=str(split_ids[0]),
        details={"provenance": "reused_primary_assignment"},
    )
    split.validate(len(target.metadata), target.y)
    return split


def calibration_samples_from_reused(
    dataset: str,
    target: SubjectShard,
    repeat: int,
    split_id: str,
    calibration_rows: pd.DataFrame,
    budgets: tuple[int, ...],
) -> dict[int, CalibrationSample]:
    """Reconstruct nested ``CalibrationSample`` objects for the given positive budgets.

    Filters on ``dataset`` in addition to ``target_subject``/``repeat``/
    ``split_id`` for the same subject-ID-collision reason as
    ``target_split_from_reused`` -- ``split_id`` alone is a content-derived
    hash and is practically (not provably to this code) collision-free, so
    this is defense in depth, not redundant.
    """
    rows = calibration_rows.loc[
        (calibration_rows["dataset"].astype(str) == str(dataset))
        & (calibration_rows["target_subject"].astype(str) == str(target.subject))
        & (calibration_rows["repeat"].astype(int) == int(repeat))
        & (calibration_rows["split_id"].astype(str) == str(split_id))
    ]
    uid_to_pos = {uid: pos for pos, uid in enumerate(target.metadata["trial_uid"].astype(str))}
    result: dict[int, CalibrationSample] = {}
    prior: set[int] = set()
    for budget in sorted(budgets):
        if budget <= 0:
            raise ValueError("calibration_samples_from_reused only accepts positive budgets")
        budget_rows = rows.loc[rows["budget_per_class"].astype(int) == int(budget)]
        if budget_rows.empty:
            raise ValueError(
                f"No reused calibration rows for subject={target.subject}, repeat={repeat}, "
                f"budget={budget}"
            )
        missing_uids = set(budget_rows["trial_uid"].astype(str)) - set(uid_to_pos)
        if missing_uids:
            raise ValueError(
                f"Reused calibration trial UIDs not found in the loaded target shard for "
                f"subject={target.subject}: {sorted(missing_uids)[:5]}"
            )
        indices = np.asarray(
            sorted(uid_to_pos[u] for u in budget_rows["trial_uid"].astype(str)), dtype=int
        )
        current = set(indices.tolist())
        if prior and not prior.issubset(current):
            raise AssertionError(
                f"Reused calibration samples are not nested for subject={target.subject}, "
                f"repeat={repeat}, budget={budget}"
            )
        prior = current
        counts = {
            0: int((budget_rows["label"].astype(int) == 0).sum()),
            1: int((budget_rows["label"].astype(int) == 1).sum()),
        }
        sample = CalibrationSample(budget_per_class=budget, indices=indices, class_counts=counts)
        sample.validate(target.y)
        result[budget] = sample
    return result


def source_subjects_from_reused(
    dataset: str, target_subject: str, source_selection_rows: pd.DataFrame
) -> list[str]:
    rows = source_selection_rows.loc[
        (source_selection_rows["dataset"].astype(str) == str(dataset))
        & (source_selection_rows["target_subject"].astype(str) == str(target_subject))
    ]
    if rows.empty:
        raise ValueError(f"No reused source-selection rows for dataset={dataset}, target={target_subject}")
    return sorted(rows["source_subject"].astype(str).unique().tolist(), key=_subject_sort_key)


def source_indices_from_reused(
    shard: SubjectShard,
    dataset: str,
    target_subject: str,
    source_subject: str,
    source_trial_rows: pd.DataFrame,
) -> np.ndarray:
    rows = source_trial_rows.loc[
        (source_trial_rows["dataset"].astype(str) == str(dataset))
        & (source_trial_rows["target_subject"].astype(str) == str(target_subject))
        & (source_trial_rows["source_subject"].astype(str) == str(source_subject))
    ]
    if rows.empty:
        raise ValueError(
            f"No reused source-trial rows for dataset={dataset}, target={target_subject}, "
            f"source={source_subject}"
        )
    uid_to_pos = {uid: pos for pos, uid in enumerate(shard.metadata["trial_uid"].astype(str))}
    missing_uids = set(rows["trial_uid"].astype(str)) - set(uid_to_pos)
    if missing_uids:
        raise ValueError(
            f"Reused source-trial UIDs not found in the loaded source shard for "
            f"subject={source_subject}: {sorted(missing_uids)[:5]}"
        )
    return np.asarray(sorted(uid_to_pos[u] for u in rows["trial_uid"].astype(str)), dtype=int)
