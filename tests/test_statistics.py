from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from bci_calibration_benchmark.config import load_config
from bci_calibration_benchmark.metrics import METRIC_NAMES
from bci_calibration_benchmark.statistics import (
    aggregate_repeats,
    build_aucc_table,
    holm_adjust,
)


def _metrics_frame(budgets: tuple[int, ...] = (5, 10, 20)) -> pd.DataFrame:
    rows = []
    for repeat, value in ((0, 0.60), (1, 0.70)):
        for budget in budgets:
            row = {
                "dataset": "D",
                "target_subject": "1",
                "repeat": repeat,
                "method": "csp_lda",
                "regime": "subject",
                "budget_per_class": budget,
                "split_id": "fixed-test-split",
                "status": "ok",
                "calibration_trials_total": budget * 2,
                "source_subject_count": 2,
                "source_trials": 20,
                "train_trials": budget * 2,
                "test_trials": 10,
                "fit_seconds": 1.0,
                "predict_seconds": 0.1,
            }
            for metric in METRIC_NAMES:
                if metric in {"brier", "log_loss"}:
                    row[metric] = 0.2
                else:
                    row[metric] = value + 0.01 * (budget / 10)
            rows.append(row)
    return pd.DataFrame(rows)


def test_repeat_aggregation_and_fixed_horizon_aucc() -> None:
    config = load_config("configs/pilot.yaml")
    summary = aggregate_repeats(_metrics_frame())
    assert len(summary) == 3
    assert np.allclose(summary["roc_auc"], [0.655, 0.66, 0.67])
    aucc = build_aucc_table(summary, config)
    assert len(aucc) == 1
    assert bool(aucc.loc[0, "curve_complete"])
    assert aucc.loc[0, "expected_budgets"] == "5;10;20"
    assert aucc.loc[0, "maximum_budget_observed"] == 20
    assert aucc.loc[0, "aucc_horizon_per_class"] == 20
    assert np.isfinite(aucc.loc[0, "aucc_roc_auc"])


def test_incomplete_curve_is_retained_but_excluded_from_aucc() -> None:
    config = load_config("configs/pilot.yaml")
    summary = aggregate_repeats(_metrics_frame(budgets=(5, 10)))
    aucc = build_aucc_table(summary, config)
    assert len(aucc) == 1
    assert not bool(aucc.loc[0, "curve_complete"])
    assert aucc.loc[0, "incomplete_reason"] == "missing=20"
    assert np.isnan(aucc.loc[0, "aucc_roc_auc"])
    assert np.isnan(aucc.loc[0, "slope_roc_auc"])
    assert np.isnan(aucc.loc[0, "first_budget_roc_auc_threshold"])


def test_source_plus_target_curve_includes_zero_budget() -> None:
    config = load_config("configs/pilot.yaml")
    frame = _metrics_frame(budgets=(5, 10, 20))
    zero = frame.loc[frame["budget_per_class"] == 5].copy()
    zero["budget_per_class"] = 0
    zero["calibration_trials_total"] = 0
    frame = pd.concat([zero, frame], ignore_index=True)
    frame["regime"] = "source_plus_target"
    summary = aggregate_repeats(frame)
    aucc = build_aucc_table(summary, config)
    assert bool(aucc.loc[0, "curve_complete"])
    assert aucc.loc[0, "expected_budgets"] == "0;5;10;20"


def test_config_validation_prevents_aucc_horizon_outside_budgets() -> None:
    config = load_config("configs/pilot.yaml")
    invalid = replace(config, analysis=replace(config.analysis, aucc_max_budget_per_class=40))
    try:
        invalid.validate()
    except ValueError as error:
        assert "configured calibration budget" in str(error)
    else:
        raise AssertionError("Invalid AUCC horizon was accepted")


def test_holm_adjustment_is_monotone_in_sorted_order() -> None:
    raw = np.asarray([0.01, 0.04, 0.03])
    adjusted = holm_adjust(raw)
    assert np.all(adjusted >= raw)
    order = np.argsort(raw)
    assert np.all(np.diff(adjusted[order]) >= 0)


def test_pairwise_tests_separate_confirmatory_and_dataset_supportive_families() -> None:
    from bci_calibration_benchmark.statistics import build_pairwise_tests

    config = load_config("configs/pilot.yaml")
    rows: list[dict[str, object]] = []
    for dataset in ("D1", "D2"):
        for subject in ("1", "2", "3"):
            for method, offset in (("csp_lda", 0.00), ("riemann_lr", 0.02)):
                for regime, regime_offset in (("subject", 0.00), ("source_plus_target", 0.01)):
                    for budget in ((5, 10, 20) if regime == "subject" else (0, 5, 10, 20)):
                        base = 0.60 + offset + regime_offset + 0.002 * budget
                        row: dict[str, object] = {
                            "dataset": dataset,
                            "target_subject": subject,
                            "method": method,
                            "regime": regime,
                            "budget_per_class": budget,
                        }
                        for metric in METRIC_NAMES:
                            row[metric] = 0.2 if metric in {"brier", "log_loss"} else base
                        rows.append(row)
    summary = pd.DataFrame(rows)
    aucc = build_aucc_table(summary, config)
    tests = build_pairwise_tests(summary, aucc, config)
    assert set(tests["inference_role"]) == {"confirmatory", "supportive"}
    confirmatory = tests.loc[tests["inference_role"] == "confirmatory"]
    assert set(confirmatory["scope_dataset"]) == {"ALL"}
    assert confirmatory["family"].str.endswith("_confirmatory").all()
