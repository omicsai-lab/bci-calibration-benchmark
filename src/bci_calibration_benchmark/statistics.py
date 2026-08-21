"""Participant-level aggregation and pre-specified statistical analyses.

The participant, not the trial or repeated split, is the primary independent
unit.  Functions in this module therefore aggregate repeats before inferential
comparisons and bootstrap participants rather than rows of trial predictions.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import rankdata, wilcoxon

from .config import ExperimentConfig
from .metrics import METRIC_NAMES
from .utils import derive_seed

CONDITION_COLUMNS = [
    "dataset",
    "target_subject",
    "method",
    "regime",
    "budget_per_class",
]


@dataclass(frozen=True)
class BootstrapInterval:
    estimate: float
    lower: float
    upper: float
    n: int


def _as_subject_string(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    if "target_subject" in output:
        output["target_subject"] = output["target_subject"].astype(str)
    return output


def validate_metrics_frame(frame: pd.DataFrame) -> None:
    required = {
        "dataset",
        "target_subject",
        "repeat",
        "method",
        "regime",
        "budget_per_class",
        "split_id",
        "status",
        *METRIC_NAMES,
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"metrics.csv is missing required columns: {sorted(missing)}")
    successful = frame.loc[frame["status"] == "ok"].copy()
    if successful.empty:
        raise ValueError("No successful benchmark conditions are available")
    key = [
        "dataset",
        "target_subject",
        "repeat",
        "method",
        "regime",
        "budget_per_class",
        "split_id",
    ]
    duplicated = successful.duplicated(key, keep=False)
    if duplicated.any():
        examples = successful.loc[duplicated, key].head(10).to_dict(orient="records")
        raise ValueError(f"Duplicate successful condition rows detected: {examples}")
    for metric in METRIC_NAMES:
        values = pd.to_numeric(successful[metric], errors="coerce")
        if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
            raise ValueError(f"Successful rows contain invalid {metric} values")
    if not successful["roc_auc"].between(0, 1).all():
        raise ValueError("ROC-AUC values must lie in [0, 1]")


def aggregate_repeats(metrics: pd.DataFrame) -> pd.DataFrame:
    """Average repeated-split metrics within participant and condition."""
    metrics = _as_subject_string(metrics)
    validate_metrics_frame(metrics)
    successful = metrics.loc[metrics["status"] == "ok"].copy()
    for column in METRIC_NAMES:
        successful[column] = pd.to_numeric(successful[column], errors="raise")
    numeric_context = [
        column
        for column in (
            "calibration_trials_total",
            "source_subject_count",
            "source_trials",
            "train_trials",
            "test_trials",
            "fit_seconds",
            "predict_seconds",
        )
        if column in successful.columns
    ]
    grouped = successful.groupby(CONDITION_COLUMNS, sort=True, observed=True, dropna=False)
    summary = grouped[list(METRIC_NAMES) + numeric_context].mean().reset_index()
    counts = grouped.size().rename("n_repeats_observed").reset_index()
    split_counts = grouped["split_id"].nunique().rename("n_unique_test_splits").reset_index()
    summary = summary.merge(counts, on=CONDITION_COLUMNS, validate="one_to_one")
    summary = summary.merge(split_counts, on=CONDITION_COLUMNS, validate="one_to_one")
    summary["log2_budget"] = np.log2(summary["budget_per_class"].astype(float) + 1.0)
    return summary.sort_values(CONDITION_COLUMNS, kind="stable").reset_index(drop=True)


def participant_bootstrap_mean(
    values: np.ndarray,
    *,
    n_resamples: int,
    ci_level: float,
    seed: int,
) -> BootstrapInterval:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return BootstrapInterval(np.nan, np.nan, np.nan, 0)
    estimate = float(np.mean(values))
    if values.size == 1:
        return BootstrapInterval(estimate, estimate, estimate, 1)
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, values.size, size=(n_resamples, values.size))
    bootstrap_means = values[indices].mean(axis=1)
    alpha = (1.0 - ci_level) / 2.0
    lower, upper = np.quantile(bootstrap_means, [alpha, 1.0 - alpha])
    return BootstrapInterval(estimate, float(lower), float(upper), int(values.size))


def summarize_curves(subject_summary: pd.DataFrame, config: ExperimentConfig) -> pd.DataFrame:
    """Create dataset-level curve estimates with participant bootstrap intervals."""
    required = {*CONDITION_COLUMNS, *METRIC_NAMES}
    missing = required.difference(subject_summary.columns)
    if missing:
        raise ValueError(f"subject summary missing columns: {sorted(missing)}")
    group_columns = ["dataset", "method", "regime", "budget_per_class"]
    rows: list[dict[str, Any]] = []
    for keys, group in subject_summary.groupby(group_columns, sort=True, observed=True):
        base = dict(zip(group_columns, keys, strict=True))
        for metric in METRIC_NAMES:
            values = group[metric].to_numpy(dtype=float)
            interval = participant_bootstrap_mean(
                values,
                n_resamples=config.analysis.bootstrap_resamples,
                ci_level=config.analysis.ci_level,
                seed=derive_seed(config.experiment.seed, "curve", *keys, metric),
            )
            finite = values[np.isfinite(values)]
            rows.append(
                {
                    **base,
                    "metric": metric,
                    "mean": interval.estimate,
                    "ci_lower": interval.lower,
                    "ci_upper": interval.upper,
                    "n_subjects": interval.n,
                    "sd": float(np.std(finite, ddof=1)) if finite.size > 1 else np.nan,
                    "median": float(np.median(finite)) if finite.size else np.nan,
                    "ci_level": config.analysis.ci_level,
                    "bootstrap_resamples": config.analysis.bootstrap_resamples,
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["dataset", "metric", "regime", "method", "budget_per_class"], kind="stable"
    ).reset_index(drop=True)


def _normalized_aucc(budgets: np.ndarray, values: np.ndarray) -> float:
    budgets = np.asarray(budgets, dtype=float)
    values = np.asarray(values, dtype=float)
    valid = np.isfinite(budgets) & np.isfinite(values)
    budgets = budgets[valid]
    values = values[valid]
    if budgets.size < 2:
        return np.nan
    order = np.argsort(budgets)
    budgets = budgets[order]
    values = values[order]
    if np.unique(budgets).size != budgets.size:
        raise ValueError("AUCC input contains duplicate budgets")
    x = np.log2(budgets + 1.0)
    width = float(x[-1] - x[0])
    if width <= 0:
        return np.nan
    return float(np.trapezoid(values, x=x) / width)


def _calibration_slope(budgets: np.ndarray, values: np.ndarray) -> float:
    budgets = np.asarray(budgets, dtype=float)
    values = np.asarray(values, dtype=float)
    valid = np.isfinite(budgets) & np.isfinite(values)
    budgets = budgets[valid]
    values = values[valid]
    if budgets.size < 2 or np.unique(budgets).size < 2:
        return np.nan
    x = np.log2(budgets + 1.0)
    return float(np.polyfit(x, values, deg=1)[0])


def _first_budget_at_threshold(
    budgets: np.ndarray,
    values: np.ndarray,
    threshold: float,
) -> float:
    budgets = np.asarray(budgets, dtype=float)
    values = np.asarray(values, dtype=float)
    valid = np.isfinite(budgets) & np.isfinite(values) & (values >= threshold)
    if not valid.any():
        return np.nan
    return float(np.min(budgets[valid]))


def build_aucc_table(subject_summary: pd.DataFrame, config: ExperimentConfig) -> pd.DataFrame:
    """Compute participant-level calibration-curve summaries.

    Population-only rows are excluded because they are structurally defined only
    at zero calibration.  AUCC is computed only over a pre-specified, fixed
    horizon and only when every expected budget in that horizon is present.
    Incomplete curves remain in the output as auditable rows, but all derived
    curve summaries are set to missing so they cannot enter inferential tests.
    """
    curves = subject_summary.loc[
        subject_summary["regime"].isin(["subject", "source_plus_target"])
    ].copy()
    group_columns = ["dataset", "target_subject", "method", "regime"]
    horizon = int(config.analysis.aucc_max_budget_per_class)
    configured = tuple(
        int(value) for value in config.calibration.budgets_per_class if value <= horizon
    )
    rows: list[dict[str, Any]] = []
    for keys, group in curves.groupby(group_columns, sort=True, observed=True):
        regime = str(keys[-1])
        expected = tuple(value for value in configured if regime != "subject" or value > 0)
        ordered = group.loc[group["budget_per_class"] <= horizon].sort_values(
            "budget_per_class"
        )
        budgets = ordered["budget_per_class"].to_numpy(dtype=float)
        if np.unique(budgets).size != budgets.size:
            raise ValueError(f"Duplicate participant-level budgets for {keys}")
        observed = tuple(int(value) for value in budgets)
        missing = tuple(value for value in expected if value not in observed)
        unexpected = tuple(value for value in observed if value not in expected)
        complete = observed == expected
        reasons: list[str] = []
        if missing:
            reasons.append("missing=" + ";".join(str(value) for value in missing))
        if unexpected:
            reasons.append("unexpected=" + ";".join(str(value) for value in unexpected))
        if observed and observed != tuple(sorted(observed)):
            reasons.append("nonmonotone_observed_budgets")
        if not observed:
            reasons.append("no_points_within_horizon")
        row: dict[str, Any] = dict(zip(group_columns, keys, strict=True))
        row.update(
            {
                "n_curve_points": int(len(ordered)),
                "curve_complete": bool(complete),
                "incomplete_reason": " | ".join(reasons),
                "aucc_horizon_per_class": horizon,
                "expected_budgets": ";".join(str(value) for value in expected),
                "minimum_budget_expected": int(expected[0]) if expected else np.nan,
                "maximum_budget_expected": int(expected[-1]) if expected else np.nan,
                "minimum_budget_observed": int(np.min(budgets)) if budgets.size else np.nan,
                "maximum_budget_observed": int(np.max(budgets)) if budgets.size else np.nan,
                "observed_budgets": ";".join(str(value) for value in observed),
            }
        )
        for metric in METRIC_NAMES:
            values = ordered[metric].to_numpy(dtype=float)
            row[f"aucc_{metric}"] = (
                _normalized_aucc(budgets, values) if complete else np.nan
            )
            row[f"slope_{metric}"] = (
                _calibration_slope(budgets, values) if complete else np.nan
            )
        if complete:
            row["first_budget_roc_auc_threshold"] = _first_budget_at_threshold(
                budgets,
                ordered["roc_auc"].to_numpy(dtype=float),
                config.analysis.roc_auc_threshold,
            )
            row["first_budget_balanced_accuracy_threshold"] = _first_budget_at_threshold(
                budgets,
                ordered["balanced_accuracy"].to_numpy(dtype=float),
                config.analysis.balanced_accuracy_threshold,
            )
        else:
            row["first_budget_roc_auc_threshold"] = np.nan
            row["first_budget_balanced_accuracy_threshold"] = np.nan
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=group_columns)
    return pd.DataFrame(rows).sort_values(group_columns, kind="stable").reset_index(drop=True)


def holm_adjust(p_values: Iterable[float]) -> np.ndarray:
    values = np.asarray(list(p_values), dtype=float)
    adjusted = np.full(values.shape, np.nan, dtype=float)
    finite_indices = np.flatnonzero(np.isfinite(values))
    if finite_indices.size == 0:
        return adjusted
    finite_values = values[finite_indices]
    order = np.argsort(finite_values)
    sorted_values = finite_values[order]
    m = len(sorted_values)
    running = 0.0
    sorted_adjusted = np.empty(m, dtype=float)
    for rank, p_value in enumerate(sorted_values):
        candidate = (m - rank) * p_value
        running = max(running, candidate)
        sorted_adjusted[rank] = min(running, 1.0)
    inverse = np.empty(m, dtype=int)
    inverse[order] = np.arange(m)
    adjusted[finite_indices] = sorted_adjusted[inverse]
    return adjusted


def _rank_biserial(differences: np.ndarray) -> float:
    differences = np.asarray(differences, dtype=float)
    differences = differences[np.isfinite(differences) & (differences != 0)]
    if differences.size == 0:
        return 0.0
    ranks = rankdata(np.abs(differences), method="average")
    positive = float(ranks[differences > 0].sum())
    negative = float(ranks[differences < 0].sum())
    denominator = positive + negative
    return 0.0 if denominator == 0 else (positive - negative) / denominator


def _paired_result(
    paired: pd.DataFrame,
    *,
    left_column: str,
    right_column: str,
    n_resamples: int,
    ci_level: float,
    seed: int,
) -> dict[str, Any]:
    clean = paired[[left_column, right_column]].dropna()
    differences = clean[left_column].to_numpy(dtype=float) - clean[right_column].to_numpy(dtype=float)
    if differences.size == 0:
        return {
            "n_pairs": 0,
            "mean_difference": np.nan,
            "median_difference": np.nan,
            "ci_lower": np.nan,
            "ci_upper": np.nan,
            "wilcoxon_statistic": np.nan,
            "p_value": np.nan,
            "rank_biserial": np.nan,
        }
    interval = participant_bootstrap_mean(
        differences,
        n_resamples=n_resamples,
        ci_level=ci_level,
        seed=seed,
    )
    if np.allclose(differences, 0.0, rtol=0.0, atol=0.0):
        statistic, p_value = 0.0, 1.0
    else:
        test = wilcoxon(
            differences,
            alternative="two-sided",
            zero_method="wilcox",
            correction=False,
            method="auto",
        )
        statistic, p_value = float(test.statistic), float(test.pvalue)
    return {
        "n_pairs": int(differences.size),
        "mean_difference": float(np.mean(differences)),
        "median_difference": float(np.median(differences)),
        "ci_lower": interval.lower,
        "ci_upper": interval.upper,
        "wilcoxon_statistic": statistic,
        "p_value": p_value,
        "rank_biserial": _rank_biserial(differences),
    }


def _scope_iter(frame: pd.DataFrame) -> Iterable[tuple[str, pd.DataFrame]]:
    for dataset, group in frame.groupby("dataset", sort=True, observed=True):
        yield str(dataset), group
    if frame["dataset"].nunique() > 1:
        yield "ALL", frame


def build_pairwise_tests(
    subject_summary: pd.DataFrame,
    aucc_subject: pd.DataFrame,
    config: ExperimentConfig,
) -> pd.DataFrame:
    """Generate only the confirmatory paired-comparison families in the protocol."""
    rows: list[dict[str, Any]] = []
    primary = config.metrics.primary

    # H2 family: pooled retraining minus subject-only at low calibration budgets.
    regime_data = subject_summary.loc[
        subject_summary["regime"].isin(["subject", "source_plus_target"])
    ].copy()
    for budget in config.analysis.pairwise_budgets:
        budget_data = regime_data.loc[regime_data["budget_per_class"] == budget]
        for method, method_data in budget_data.groupby("method", sort=True, observed=True):
            for scope, scoped in _scope_iter(method_data):
                pivot = scoped.pivot_table(
                    index=["dataset", "target_subject"],
                    columns="regime",
                    values=primary,
                    aggfunc="first",
                )
                if not {"source_plus_target", "subject"}.issubset(pivot.columns):
                    continue
                result = _paired_result(
                    pivot,
                    left_column="source_plus_target",
                    right_column="subject",
                    n_resamples=config.analysis.bootstrap_resamples,
                    ci_level=config.analysis.ci_level,
                    seed=derive_seed(
                        config.experiment.seed,
                        "paired-regime",
                        scope,
                        method,
                        budget,
                        primary,
                    ),
                )
                pooled_scope = scope == "ALL"
                rows.append(
                    {
                        "family": (
                            "H2_regime_low_budget_confirmatory"
                            if pooled_scope
                            else "H2_regime_low_budget_dataset_supportive"
                        ),
                        "inference_role": "confirmatory" if pooled_scope else "supportive",
                        "scope_dataset": scope,
                        "scope_weighting": (
                            "participant_weighted_across_datasets"
                            if pooled_scope
                            else "within_dataset"
                        ),
                        "metric": primary,
                        "budget_per_class": int(budget),
                        "regime": "source_plus_target_vs_subject",
                        "method_left": str(method),
                        "method_right": str(method),
                        "contrast": "source_plus_target - subject",
                        **result,
                    }
                )

    # H3 family: Riemannian minus CSP normalized log-AUCC, within each regime.
    aucc_metric = f"aucc_{primary}"
    if not aucc_subject.empty and aucc_metric in aucc_subject.columns:
        complete_aucc = aucc_subject
        if "curve_complete" in complete_aucc.columns:
            complete_aucc = complete_aucc.loc[complete_aucc["curve_complete"]].copy()
        for regime, regime_data in complete_aucc.groupby("regime", sort=True, observed=True):
            for scope, scoped in _scope_iter(regime_data):
                pivot = scoped.pivot_table(
                    index=["dataset", "target_subject"],
                    columns="method",
                    values=aucc_metric,
                    aggfunc="first",
                )
                if not {"riemann_lr", "csp_lda"}.issubset(pivot.columns):
                    continue
                result = _paired_result(
                    pivot,
                    left_column="riemann_lr",
                    right_column="csp_lda",
                    n_resamples=config.analysis.bootstrap_resamples,
                    ci_level=config.analysis.ci_level,
                    seed=derive_seed(
                        config.experiment.seed,
                        "paired-aucc",
                        scope,
                        regime,
                        primary,
                    ),
                )
                pooled_scope = scope == "ALL"
                rows.append(
                    {
                        "family": (
                            "H3_method_aucc_confirmatory"
                            if pooled_scope
                            else "H3_method_aucc_dataset_supportive"
                        ),
                        "inference_role": "confirmatory" if pooled_scope else "supportive",
                        "scope_dataset": scope,
                        "scope_weighting": (
                            "participant_weighted_across_datasets"
                            if pooled_scope
                            else "within_dataset"
                        ),
                        "metric": aucc_metric,
                        "budget_per_class": np.nan,
                        "regime": str(regime),
                        "method_left": "riemann_lr",
                        "method_right": "csp_lda",
                        "contrast": "riemann_lr - csp_lda",
                        **result,
                    }
                )

    if not rows:
        return pd.DataFrame()
    output = pd.DataFrame(rows)
    output["p_holm"] = np.nan
    for _, indices in output.groupby("family", sort=False).groups.items():
        output.loc[indices, "p_holm"] = holm_adjust(output.loc[indices, "p_value"])
    return output.sort_values(
        ["family", "scope_dataset", "regime", "method_left", "budget_per_class"],
        kind="stable",
        na_position="last",
    ).reset_index(drop=True)


def fit_mixed_effects(
    subject_summary: pd.DataFrame,
    config: ExperimentConfig,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Fit the pre-specified participant-level mixed model.

    A random slope is attempted first and a random-intercept model is used only
    as an explicit numerical fallback.  Failures are returned as diagnostics,
    not converted into inferential results.
    """
    primary = config.metrics.primary
    data = subject_summary.loc[
        subject_summary["regime"].isin(["subject", "source_plus_target"])
        & (subject_summary["budget_per_class"] > 0)
    ].copy()
    data = data.dropna(subset=[primary])
    data["target_subject"] = data["target_subject"].astype(str)
    data["participant_key"] = data["dataset"].astype(str) + "::" + data["target_subject"]
    data["log2_budget"] = np.log2(data["budget_per_class"].astype(float) + 1.0)
    diagnostics: dict[str, Any] = {
        "status": "not_run",
        "metric": primary,
        "n_observations": int(len(data)),
        "n_participants": int(data["participant_key"].nunique()),
    }
    if not config.analysis.fit_mixed_effects:
        diagnostics["reason"] = "Disabled by analysis.fit_mixed_effects"
        return pd.DataFrame(), diagnostics
    if data["participant_key"].nunique() < 3 or len(data) < 20:
        diagnostics["reason"] = "Insufficient participants or observations"
        return pd.DataFrame(), diagnostics

    try:
        import statsmodels.formula.api as smf
    except ImportError as error:
        diagnostics.update({"status": "failed", "error": repr(error)})
        return pd.DataFrame(), diagnostics

    formula = f"{primary} ~ log2_budget * C(method) * C(regime)"
    if data["dataset"].nunique() > 1:
        formula += " + C(dataset)"
    attempts = [("random_intercept_and_slope", "~log2_budget"), ("random_intercept", "1")]
    errors: list[dict[str, str]] = []
    for structure, re_formula in attempts:
        captured: list[str] = []
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                model = smf.mixedlm(
                    formula,
                    data=data,
                    groups=data["participant_key"],
                    re_formula=re_formula,
                )
                result = model.fit(reml=False, method="lbfgs", maxiter=2000, disp=False)
                captured = [str(item.message) for item in caught]
            if not bool(result.converged):
                errors.append(
                    {
                        "structure": structure,
                        "error": "Model fit returned converged=False",
                        "warnings": " | ".join(captured),
                    }
                )
                continue
            conf = result.conf_int()
            coefficients = pd.DataFrame(
                {
                    "term": result.params.index.astype(str),
                    "estimate": result.params.to_numpy(dtype=float),
                    "standard_error": result.bse.reindex(result.params.index).to_numpy(dtype=float),
                    "z_value": result.tvalues.reindex(result.params.index).to_numpy(dtype=float),
                    "p_value": result.pvalues.reindex(result.params.index).to_numpy(dtype=float),
                    "ci_lower": conf.reindex(result.params.index)[0].to_numpy(dtype=float),
                    "ci_upper": conf.reindex(result.params.index)[1].to_numpy(dtype=float),
                }
            )
            diagnostics.update(
                {
                    "status": "ok",
                    "formula": formula,
                    "random_effects_structure": structure,
                    "converged": bool(result.converged),
                    "warnings": captured,
                    "aic": float(result.aic) if np.isfinite(result.aic) else None,
                    "bic": float(result.bic) if np.isfinite(result.bic) else None,
                    "log_likelihood": float(result.llf),
                    "fallback_attempts": errors,
                }
            )
            return coefficients, diagnostics
        except Exception as error:  # numerical failures are recorded and fallback is explicit
            errors.append({"structure": structure, "error": repr(error), "warnings": " | ".join(captured)})
    diagnostics.update(
        {
            "status": "failed",
            "formula": formula,
            "attempts": errors,
        }
    )
    return pd.DataFrame(), diagnostics
