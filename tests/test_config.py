from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from bci_calibration_benchmark.config import CalibrationSection, load_config


def test_checked_in_configs_load() -> None:
    for path in (
        Path("configs/pilot.yaml"),
        Path("configs/full.yaml"),
        Path("configs/sensitivity_three_channels.yaml"),
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
