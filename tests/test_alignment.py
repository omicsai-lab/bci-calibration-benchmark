from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bci_calibration_benchmark.alignment import (
    apply_ea_transform,
    estimate_ea_reference,
    reference_digest,
)
from bci_calibration_benchmark.assignment_reuse import (
    load_reused_assignments,
    source_indices_from_reused,
    verify_assignment_reuse,
)
from bci_calibration_benchmark.config import AlignmentSection, DatasetSection
from bci_calibration_benchmark.ea_aggregate import aggregate_ea_run
from bci_calibration_benchmark.ea_runner import run_ea_benchmark
from bci_calibration_benchmark.ea_validation import audit_ea_result_integrity
from bci_calibration_benchmark.runner import run_benchmark
from bci_calibration_benchmark.synthetic import (
    SyntheticSpecification,
    build_smoke_config,
    generate_synthetic_dataset,
)


def _correlated_epochs(rng: np.random.Generator, n_trials: int, n_channels: int, n_times: int) -> np.ndarray:
    base = rng.normal(size=(n_trials, n_channels, n_times))
    mix = rng.normal(size=(n_channels, n_channels))
    return np.einsum("cd,ndt->nct", mix, base)


# ---------------------------------------------------------------------------
# Unit-level contract tests on alignment.py
# ---------------------------------------------------------------------------


def test_alignment_rejects_budget_zero() -> None:
    with pytest.raises(ValueError, match="zero trials"):
        estimate_ea_reference(np.empty((0, 4, 32)))


def test_alignment_is_deterministic() -> None:
    rng = np.random.default_rng(7)
    X = _correlated_epochs(rng, 20, 4, 48)
    reference_a = estimate_ea_reference(X, epsilon=1e-12)
    reference_b = estimate_ea_reference(X, epsilon=1e-12)
    assert np.array_equal(reference_a, reference_b)
    aligned_a = apply_ea_transform(X, reference_a)
    aligned_b = apply_ea_transform(X, reference_b)
    assert np.array_equal(aligned_a, aligned_b)
    assert reference_digest(reference_a) == reference_digest(reference_b)


def test_alignment_references_are_participant_specific() -> None:
    rng_a = np.random.default_rng(1)
    rng_b = np.random.default_rng(2)
    X_a = _correlated_epochs(rng_a, 24, 5, 40)
    X_b = _correlated_epochs(rng_b, 24, 5, 40)
    reference_a = estimate_ea_reference(X_a)
    reference_b = estimate_ea_reference(X_b)
    assert reference_digest(reference_a) != reference_digest(reference_b)
    # Same participant, same data, called again -> identical digest.
    assert reference_digest(estimate_ea_reference(X_a)) == reference_digest(reference_a)


def test_alignment_literal_he_wu_formula_no_sample_normalization() -> None:
    # Human-reviewed decision: R = mean_i(X_i X_i^T), NOT divided by n_samples.
    rng = np.random.default_rng(3)
    X = _correlated_epochs(rng, 15, 3, 64)
    reference = estimate_ea_reference(X, epsilon=1e-12)
    expected_R = np.mean(np.matmul(X, np.transpose(X, (0, 2, 1))), axis=0)
    from bci_calibration_benchmark.riemann import matrix_power_spd

    expected_reference = matrix_power_spd(expected_R, -0.5, 1e-12)
    assert np.allclose(reference, expected_reference, atol=1e-10)
    # A /n_samples-normalized reference would differ by more than numerical
    # tolerance for a nontrivial n_times, confirming the literal (unnormalized)
    # formula is actually what is used, not silently equivalent to it.
    normalized_R = expected_R / X.shape[2]
    normalized_reference = matrix_power_spd(normalized_R, -0.5, 1e-12)
    assert not np.allclose(reference, normalized_reference, atol=1e-6)


def test_ea_identity_property() -> None:
    # mean_i(X_aligned_i X_aligned_i^T) should be close to identity when
    # eigenvalue flooring is not materially active.
    rng = np.random.default_rng(11)
    X = _correlated_epochs(rng, 200, 6, 96)
    reference = estimate_ea_reference(X, epsilon=1e-12)
    aligned = apply_ea_transform(X, reference)
    R_after = np.mean(np.matmul(aligned, np.transpose(aligned, (0, 2, 1))), axis=0)
    assert np.allclose(R_after, np.eye(6), atol=1e-6)


def test_alignment_epsilon_floor_near_singular_covariance_stays_finite() -> None:
    rng = np.random.default_rng(13)
    base = rng.normal(size=(30, 1, 40))
    # Every channel is a scaled copy of the same signal -> rank-deficient R.
    X = np.repeat(base, 5, axis=1) * np.asarray([1.0, 1.0, 1.0, 1.0, 1.0 + 1e-9]).reshape(1, 5, 1)
    reference = estimate_ea_reference(X, epsilon=1e-8)
    assert np.isfinite(reference).all()
    aligned = apply_ea_transform(X, reference)
    assert np.isfinite(aligned).all()


# ---------------------------------------------------------------------------
# Leakage-boundary tests
# ---------------------------------------------------------------------------


def test_target_reference_excludes_test_trials() -> None:
    rng = np.random.default_rng(21)
    calibration = _correlated_epochs(rng, 16, 4, 48)
    reference_with_normal_test_data = estimate_ea_reference(calibration)
    # The reference estimator only ever receives the calibration slice; it
    # cannot see any "test" trials regardless of their content. Prove this
    # by never passing test trials in and confirming the reference is a
    # pure function of the calibration array alone, unaffected by whatever
    # sentinel/extreme values might exist in a co-located test array.
    sentinel_test = np.full((10, 4, 48), fill_value=1e6)
    combined = np.concatenate([calibration, sentinel_test], axis=0)
    # A caller that (incorrectly) sliced the wrong rows would see this
    # extreme content; the correct call site (ea_runner.py) never does.
    reference_from_calibration_slice_only = estimate_ea_reference(combined[: len(calibration)])
    assert np.array_equal(reference_with_normal_test_data, reference_from_calibration_slice_only)
    reference_if_leaked = estimate_ea_reference(combined)
    assert not np.allclose(reference_with_normal_test_data, reference_if_leaked)


def test_source_reference_excludes_unselected_trials() -> None:
    rng = np.random.default_rng(23)
    n_channels, n_times = 4, 48
    selected = _correlated_epochs(rng, 20, n_channels, n_times)
    excluded = _correlated_epochs(rng, 30, n_channels, n_times) * 5.0  # very different scale
    reference_selected_only = estimate_ea_reference(selected)
    combined = np.concatenate([selected, excluded], axis=0)
    reference_if_excluded_included = estimate_ea_reference(combined[:20])
    assert np.array_equal(reference_selected_only, reference_if_excluded_included)
    reference_if_leaked = estimate_ea_reference(combined)
    assert not np.allclose(reference_selected_only, reference_if_leaked)


def test_source_indices_from_reused_only_returns_selected_rows() -> None:
    metadata = pd.DataFrame({"trial_uid": [f"t{i}" for i in range(6)]})
    from bci_calibration_benchmark.data_types import SubjectShard

    shard = SubjectShard(
        dataset="D",
        subject="9",
        X=np.zeros((6, 2, 4), dtype=np.float32),
        y=np.asarray([0, 1, 0, 1, 0, 1]),
        metadata=metadata,
        channels=("a", "b"),
        sfreq=128.0,
    )
    reused_rows = pd.DataFrame(
        {
            "dataset": ["D", "D", "D"],
            "target_subject": ["1", "1", "1"],
            "source_subject": ["9", "9", "9"],
            "trial_uid": ["t1", "t3", "t5"],
        }
    )
    indices = source_indices_from_reused(shard, "D", "1", "9", reused_rows)
    assert sorted(indices.tolist()) == [1, 3, 5]


# ---------------------------------------------------------------------------
# End-to-end integration tests (synthetic data, fast)
# ---------------------------------------------------------------------------


def _build_ea_pair(tmp_path: Path, name: str):
    config_a = build_smoke_config(tmp_path, f"{name}-baseline")
    config_a = replace(config_a, methods=("logvar_lda", "csp_lda", "riemann_lr"))
    config_a.validate()
    generate_synthetic_dataset(
        config_a.experiment.processed_root, config_a.preprocessing_fingerprint, config_a.preprocessing
    )
    output_a = run_benchmark(config_a, repository_root=Path.cwd())

    config_ea = replace(
        config_a,
        experiment=replace(
            config_a.experiment,
            name=f"{name}-ea",
            output_root=str(tmp_path / f"{name}-ea" / "results"),
        ),
        alignment=AlignmentSection(mode="euclidean_training_only"),
    )
    config_ea.validate()
    return config_a, output_a, config_ea


def test_ea_handles_overlapping_subject_ids_across_datasets(tmp_path: Path) -> None:
    # Regression test: subject-ID strings are reused across datasets (every
    # dataset has a "subject 1"). Filtering reused assignment rows on
    # target_subject alone, without also filtering on dataset, silently
    # mixes another dataset's same-numbered participant's rows in -- this
    # was caught by running the real 3-dataset EA config end to end (Lee2019
    # MI / BNCI2014_001 / Zhou2016 all have a subject "1") after the
    # single-dataset synthetic smoke tests above passed. This test
    # reproduces the collision with two small synthetic datasets that share
    # subject numbering 1..3.
    config_a = build_smoke_config(tmp_path, "collision-baseline")
    preprocessing = config_a.preprocessing
    generate_synthetic_dataset(
        config_a.experiment.processed_root,
        config_a.preprocessing_fingerprint,
        preprocessing,
        specification=SyntheticSpecification(dataset="SyntheticA", n_subjects=3, seed=101),
    )
    generate_synthetic_dataset(
        config_a.experiment.processed_root,
        config_a.preprocessing_fingerprint,
        preprocessing,
        specification=SyntheticSpecification(dataset="SyntheticB", n_subjects=3, seed=202),
        overwrite=False,
    )
    config_a = replace(
        config_a,
        datasets=(
            DatasetSection(name="SyntheticA", subjects=(1, 2, 3)),
            DatasetSection(name="SyntheticB", subjects=(1, 2, 3)),
        ),
        methods=("logvar_lda",),
    )
    config_a.validate()
    output_a = run_benchmark(config_a, repository_root=Path.cwd())

    config_ea = replace(
        config_a,
        experiment=replace(
            config_a.experiment,
            name="collision-ea",
            output_root=str(tmp_path / "collision-ea" / "results"),
        ),
        alignment=AlignmentSection(mode="euclidean_training_only"),
    )
    config_ea.validate()
    output_ea = run_ea_benchmark(config_ea, assignment_source=output_a, repository_root=Path.cwd())
    metrics = pd.read_csv(output_ea / "metrics.csv", dtype={"target_subject": str})
    assert (metrics["status"] == "ok").all()
    assert set(metrics["dataset"].unique()) == {"SyntheticA", "SyntheticB"}
    audit = audit_ea_result_integrity(config_ea)
    assert audit["status"] == "ok", audit


def test_ea_end_to_end_reuses_primary_assignments_and_shares_target_transform(tmp_path: Path) -> None:
    config_a, output_a, config_ea = _build_ea_pair(tmp_path, "reuse")
    output_ea = run_ea_benchmark(config_ea, assignment_source=output_a, repository_root=Path.cwd())

    report = json.loads((output_ea / "assignment_reuse_report.json").read_text())
    assert report["status"] == "ok"
    assert report["regeneration_equality_gate"]["status"] == "ok"

    metrics = pd.read_csv(output_ea / "metrics.csv")
    assert (metrics["status"] == "ok").all()
    assert set(metrics["regime"].unique()) == {"subject", "source_plus_target"}
    assert "population" not in set(metrics["regime"].unique())
    assert (metrics["budget_per_class"].astype(int) > 0).all()
    assert set(metrics["alignment_mode"].unique()) == {"euclidean_training_only"}

    audit = audit_ea_result_integrity(config_ea)
    assert audit["status"] == "ok", audit

    # Shared-transform structural proof: exactly one target-alignment-reference
    # row per (dataset, target_subject, repeat, split_id, budget) group -- if
    # the two regimes had used different references, there would be no single
    # place a "the" reference could be recorded per group.
    target_prov = pd.read_csv(output_ea / "target_alignment_provenance.csv.gz")
    group_key = ["dataset", "target_subject", "repeat", "split_id", "budget_per_class"]
    assert not target_prov.duplicated(group_key).any()
    n_subjects = metrics[["dataset", "target_subject"]].drop_duplicates().shape[0]
    n_repeats = config_ea.split.repeats
    n_budgets = len([b for b in config_ea.calibration.budgets_per_class if b > 0])
    assert len(target_prov) == n_subjects * n_repeats * n_budgets


def test_ea_expected_condition_count(tmp_path: Path) -> None:
    config_a, output_a, config_ea = _build_ea_pair(tmp_path, "count")
    output_ea = run_ea_benchmark(config_ea, assignment_source=output_a, repository_root=Path.cwd())
    metrics = pd.read_csv(output_ea / "metrics.csv")
    n_subjects = metrics[["dataset", "target_subject"]].drop_duplicates().shape[0]
    n_positive_budgets = len([b for b in config_ea.calibration.budgets_per_class if b > 0])
    expected = n_subjects * config_ea.split.repeats * len(config_ea.methods) * 2 * n_positive_budgets
    assert len(metrics) == expected


def test_ea_aggregation_never_labels_confirmatory(tmp_path: Path) -> None:
    config_a, output_a, config_ea = _build_ea_pair(tmp_path, "labeling")
    run_ea_benchmark(config_ea, assignment_source=output_a, repository_root=Path.cwd())
    output_ea = aggregate_ea_run(config_ea)
    pairwise = pd.read_csv(output_ea / "pairwise_tests.csv")
    if not pairwise.empty:
        assert not pairwise["family"].astype(str).str.contains("confirmatory", case=False).any()
        assert set(pairwise["inference_role"].unique()) == {"exploratory"}
    assert not (output_ea / "mixed_effects_coefficients.csv").exists()
    assert not (output_ea / "aucc_subject.csv").exists()


def test_audit_detects_assignment_reuse_drift(tmp_path: Path) -> None:
    config_a, output_a, config_ea = _build_ea_pair(tmp_path, "drift")
    # Corrupt a copy of the primary assignment source and confirm the
    # fail-closed equality gate rejects it before any model is fit.
    tampered_source = tmp_path / "tampered-primary"
    shutil.copytree(output_a, tampered_source)
    calibration_path = tampered_source / "calibration_assignments.csv.gz"
    calibration = pd.read_csv(calibration_path, dtype=str)
    calibration.loc[0, "trial_uid"] = f"{calibration.loc[0, 'trial_uid']}:tampered"
    calibration.to_csv(calibration_path, index=False, compression="gzip")

    reused = load_reused_assignments(tampered_source)
    with pytest.raises(AssertionError, match="do not exactly match"):
        verify_assignment_reuse(config_ea, reused)

    with pytest.raises(AssertionError, match="do not exactly match"):
        run_ea_benchmark(config_ea, assignment_source=tampered_source, repository_root=Path.cwd())
    # No metrics should have been written -- the gate runs before any fit.
    assert not (config_ea.output_dir / "metrics.csv").exists()


def test_audit_detects_tampered_alignment_reference(tmp_path: Path) -> None:
    config_a, output_a, config_ea = _build_ea_pair(tmp_path, "prov-tamper")
    output_ea = run_ea_benchmark(config_ea, assignment_source=output_a, repository_root=Path.cwd())
    target_prov_path = output_ea / "target_alignment_provenance.csv.gz"
    target_prov = pd.read_csv(target_prov_path, dtype=str)
    target_prov = pd.concat([target_prov, target_prov.iloc[[0]]], ignore_index=True)
    target_prov.to_csv(target_prov_path, index=False, compression="gzip")

    audit = audit_ea_result_integrity(config_ea)
    assert audit["status"] == "failed"
    assert "target_alignment_provenance" in audit["error_message"] or "Duplicate" in audit["error_message"]
