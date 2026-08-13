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


def test_zhou2016_subject_2_excluded_from_every_checked_in_config() -> None:
    # Zhou2016 subject 2 is structurally ineligible for the prespecified
    # confirmatory design (docs/DECISIONS.md): their released session-1/
    # run-1 recording has only 20 trials/class instead of the protocol's
    # 25/run. This must hold in the pilot, confirmatory, and every
    # sensitivity configuration, whether expressed as an explicit subject
    # list or as `subjects: all` plus `exclude_subjects`.
    for path in (
        "configs/pilot.yaml",
        "configs/full.yaml",
        "configs/sensitivity_three_channels.yaml",
        "configs/sensitivity_all_sources.yaml",
    ):
        config = load_config(path)
        zhou = next(section for section in config.datasets if section.name == "Zhou2016")
        if zhou.subjects == "all":
            assert 2 in zhou.exclude_subjects, f"{path}: Zhou2016 subject 2 not excluded"
        else:
            assert 2 not in zhou.subjects, f"{path}: Zhou2016 subject 2 explicitly included"
