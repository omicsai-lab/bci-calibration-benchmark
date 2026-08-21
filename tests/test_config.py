from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from bci_calibration_benchmark.config import AlignmentSection, CalibrationSection, load_config


def test_checked_in_configs_load() -> None:
    for path in (
        Path("configs/pilot.yaml"),
        Path("configs/full.yaml"),
        Path("configs/sensitivity_three_channels.yaml"),
        Path("configs/sensitivity_all_sources.yaml"),
        Path("configs/sensitivity_ea_training_only.yaml"),
    ):
        config = load_config(path)
        assert len(config.preprocessing_fingerprint) == 16
        assert len(config.experiment_fingerprint) == 16
        assert config.analysis.pairwise_budgets == (5, 10)


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        """
experiment:
  name: bad
datasets:
  - name: BNCI2014_001
    subjects: [1, 2]
unexpected: true
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Unknown keys"):
        load_config(path)


def test_invalid_budget_order_is_rejected() -> None:
    config = load_config("configs/pilot.yaml")
    invalid = replace(
        config,
        calibration=CalibrationSection(budgets_per_class=(0, 10, 5)),
    )
    with pytest.raises(ValueError, match="increasing"):
        invalid.validate()


def test_fingerprint_changes_with_protocol() -> None:
    config = load_config("configs/pilot.yaml")
    changed = replace(config, calibration=replace(config.calibration, budgets_per_class=(0, 5, 10)))
    assert changed.experiment_fingerprint != config.experiment_fingerprint
    assert changed.preprocessing_fingerprint == config.preprocessing_fingerprint


def test_confirmatory_and_sensitivity_configs_use_ten_nested_calibration_repeats() -> None:
    # The frozen analysis plan specifies 10 nested calibration repeats for
    # the primary confirmatory analysis and both prespecified sensitivity
    # analyses (docs/DECISIONS.md, "sensitivity_all_sources.yaml repeats
    # misconfiguration"). This is a statistical/split setting, not a
    # source-cohort setting, so it must stay aligned across all three
    # configs regardless of unrelated intended differences (channel
    # montage, source-participant cap). The bounded pilot config is
    # intentionally exempt.
    for path in (
        "configs/full.yaml",
        "configs/sensitivity_three_channels.yaml",
        "configs/sensitivity_all_sources.yaml",
    ):
        config = load_config(path)
        assert config.split.repeats == 10, f"{path}: split.repeats == {config.split.repeats}, expected 10"


def test_ea_config_matches_primary_assignment_relevant_sections() -> None:
    # Exact assignment matching (docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md,
    # decision 2) depends on experiment.seed, datasets, split, and
    # calibration being byte-identical to the primary config -- only
    # experiment.name/output_root and the new alignment section may differ.
    # source is also required identical (it drives source-participant/trial
    # selection and is not one of the sections the EA sensitivity varies).
    full = load_config("configs/full.yaml")
    ea = load_config("configs/sensitivity_ea_training_only.yaml")
    assert ea.experiment.seed == full.experiment.seed
    assert ea.datasets == full.datasets
    assert ea.split == full.split
    assert ea.calibration == full.calibration
    assert ea.source == full.source
    assert ea.preprocessing == full.preprocessing
    assert ea.preprocessing_fingerprint == full.preprocessing_fingerprint
    assert ea.alignment.mode == "euclidean_training_only"
    assert full.alignment.mode == "none"
    assert ea.experiment_fingerprint != full.experiment_fingerprint


def test_alignment_default_leaves_existing_config_fingerprints_unchanged() -> None:
    # Adding AlignmentSection to ExperimentConfig must not change the
    # experiment_fingerprint (and therefore output_dir) of any config that
    # does not set alignment.mode away from its "none" default -- the
    # closed primary/prespecified-sensitivity result directories are keyed
    # by their pre-existing fingerprints on disk.
    checks = {
        "configs/full.yaml": "3fb8efe7e617b0c1",
        "configs/sensitivity_three_channels.yaml": "1fcb3f9ba9823bb1",
        "configs/sensitivity_all_sources.yaml": "e86ca10985667aec",
        "configs/pilot.yaml": "2b515a94ee6e8949",
    }
    for path, expected_fingerprint in checks.items():
        config = load_config(path)
        assert config.alignment == AlignmentSection()
        assert config.experiment_fingerprint == expected_fingerprint, path
    # Turning alignment on changes the fingerprint (it must not be silently
    # invisible to the run's own provenance/output-directory identity).
    full = load_config("configs/full.yaml")
    turned_on = replace(full, alignment=AlignmentSection(mode="euclidean_training_only"))
    assert turned_on.experiment_fingerprint != full.experiment_fingerprint


def test_zhou2016_structurally_ineligible_subjects_excluded_from_every_checked_in_config() -> None:
    # Zhou2016 subjects 2 and 4 are structurally ineligible for the
    # prespecified confirmatory design (docs/DECISIONS.md): each has one
    # released session/run with only 20 trials/class instead of the
    # protocol's 25/run (subject 2: session 1, run 1; subject 4: session 0,
    # run 0). Subject 4 was only discovered during the full-cohort run because
    # the pilot exercised only Zhou2016 subjects 1 and 3. Subject 2 had
    # already been excluded during pilot structural validation, and subject 4
    # was not part of the pilot cohort. Every other checked-in config uses
    # `subjects: all` and must exclude both.
    ineligible_subjects = {2, 4}
    for path in (
        "configs/pilot.yaml",
        "configs/full.yaml",
        "configs/sensitivity_three_channels.yaml",
        "configs/sensitivity_all_sources.yaml",
    ):
        config = load_config(path)
        zhou = next(section for section in config.datasets if section.name == "Zhou2016")
        if zhou.subjects == "all":
            missing = ineligible_subjects.difference(zhou.exclude_subjects)
            assert not missing, f"{path}: Zhou2016 subjects {missing} not excluded"
        else:
            requested = ineligible_subjects.intersection(zhou.subjects)
            assert not requested, f"{path}: Zhou2016 subjects {requested} explicitly included"
