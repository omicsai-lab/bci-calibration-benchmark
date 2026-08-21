#!/usr/bin/env python3
"""Three non-benchmark post-confirmatory robustness analyses.

Uses only the closed primary run's existing, already-audited outputs
(``results/bci-calibration-full-v1-3fb8efe7e617b0c1/summary_subject.csv``
and ``aucc_subject.csv``). Never re-runs the benchmark, never modifies any
file inside that directory, and writes only into a new, additive
``post_confirmatory_robustness/`` subdirectory.

See docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md section 5 and the human
decisions recorded there for the exact scope of each analysis:

A. Without-Zhou pooled re-aggregation (N=63) -- post-confirmatory robustness.
B. Random-intercept-only mixed model, same 1,560 observations and formula
   as the primary model -- model-form robustness, reported side by side
   with (not replacing) the primary random-intercept+slope model.
C. Fraction of participants benefiting from population data (descriptive
   n_positive/n_zero/n_negative/fraction_positive, no p-values).
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from bci_calibration_benchmark.config import load_config
from bci_calibration_benchmark.statistics import build_pairwise_tests
from bci_calibration_benchmark.utils import atomic_write_text, json_default, sha256_file

PRIMARY_DIR = Path("results/bci-calibration-full-v1-3fb8efe7e617b0c1")
OUTPUT_DIR = PRIMARY_DIR / "post_confirmatory_robustness"

FAMILY_RELABEL_WITHOUT_ZHOU = {
    "H2_regime_low_budget_confirmatory": "H2_regime_low_budget_without_zhou_robustness",
    "H2_regime_low_budget_dataset_supportive": "H2_regime_low_budget_without_zhou_dataset_supportive",
    "H3_method_aucc_confirmatory": "H3_method_aucc_without_zhou_robustness",
    "H3_method_aucc_dataset_supportive": "H3_method_aucc_without_zhou_dataset_supportive",
}
INFERENCE_ROLE_RELABEL_WITHOUT_ZHOU = {
    "confirmatory": "robustness_check_pooled",
    "supportive": "robustness_check_dataset_supportive",
}


def load_primary() -> tuple[Any, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    config = load_config("configs/full.yaml")
    summary_subject = pd.read_csv(PRIMARY_DIR / "summary_subject.csv", dtype={"target_subject": str})
    aucc_subject = pd.read_csv(PRIMARY_DIR / "aucc_subject.csv", dtype={"target_subject": str})
    mixed_effects_coefficients = pd.read_csv(PRIMARY_DIR / "mixed_effects_coefficients.csv")
    return config, summary_subject, aucc_subject, mixed_effects_coefficients


# ---------------------------------------------------------------------------
# A. Without-Zhou pooled re-aggregation
# ---------------------------------------------------------------------------


def analysis_a_without_zhou(config: Any, summary_subject: pd.DataFrame, aucc_subject: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    filtered_summary = summary_subject.loc[summary_subject["dataset"] != "Zhou2016"].copy()
    filtered_aucc = aucc_subject.loc[aucc_subject["dataset"] != "Zhou2016"].copy()
    n_participants = int(filtered_summary[["dataset", "target_subject"]].drop_duplicates().shape[0])
    if n_participants != 63:
        raise AssertionError(f"Expected N=63 without Zhou2016, got {n_participants}")

    pairwise = build_pairwise_tests(filtered_summary, filtered_aucc, config)
    pairwise = pairwise.copy()
    pairwise["classification"] = "post_confirmatory_robustness_without_zhou"
    pairwise["family"] = pairwise["family"].map(lambda value: FAMILY_RELABEL_WITHOUT_ZHOU.get(str(value), str(value)))
    pairwise["inference_role"] = pairwise["inference_role"].map(
        lambda value: INFERENCE_ROLE_RELABEL_WITHOUT_ZHOU.get(str(value), str(value))
    )
    assert not pairwise["family"].astype(str).eq("H2_regime_low_budget_confirmatory").any()
    assert not pairwise["family"].astype(str).eq("H3_method_aucc_confirmatory").any()

    meta = {
        "n_participants": n_participants,
        "n_participants_primary": int(summary_subject[["dataset", "target_subject"]].drop_duplicates().shape[0]),
        "datasets_included": sorted(filtered_summary["dataset"].unique().tolist()),
        "primary_n_unchanged": True,
    }
    return pairwise, meta


# ---------------------------------------------------------------------------
# B. Random-intercept-only mixed model sensitivity
# ---------------------------------------------------------------------------


def _prepare_mixed_model_data(subject_summary: pd.DataFrame, primary_metric: str) -> pd.DataFrame:
    data = subject_summary.loc[
        subject_summary["regime"].isin(["subject", "source_plus_target"])
        & (subject_summary["budget_per_class"] > 0)
    ].copy()
    data = data.dropna(subset=[primary_metric])
    data["target_subject"] = data["target_subject"].astype(str)
    data["participant_key"] = data["dataset"].astype(str) + "::" + data["target_subject"]
    data["log2_budget"] = np.log2(data["budget_per_class"].astype(float) + 1.0)
    return data


def analysis_b_random_intercept_only(config: Any, summary_subject: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    primary_metric = config.metrics.primary
    data = _prepare_mixed_model_data(summary_subject, primary_metric)
    if len(data) != 1560:
        raise AssertionError(f"Expected 1,560 observations (primary model-form robustness check), got {len(data)}")

    import statsmodels.formula.api as smf

    formula = f"{primary_metric} ~ log2_budget * C(method) * C(regime)"
    if data["dataset"].nunique() > 1:
        formula += " + C(dataset)"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model = smf.mixedlm(formula, data=data, groups=data["participant_key"], re_formula="1")
        result = model.fit(reml=False, method="lbfgs", maxiter=2000, disp=False)
        messages = [str(item.message) for item in caught]

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
    coefficients["classification"] = "model_form_robustness_random_intercept_only"
    diagnostics = {
        "classification": "model_form_robustness_random_intercept_only",
        "formula": formula,
        "random_effects_structure": "random_intercept",
        "n_observations": int(len(data)),
        "n_participants": int(data["participant_key"].nunique()),
        "converged": bool(result.converged),
        "warnings": messages,
        "aic": float(result.aic) if np.isfinite(result.aic) else None,
        "bic": float(result.bic) if np.isfinite(result.bic) else None,
        "log_likelihood": float(result.llf),
        "note": (
            "This is a deliberate, always-computed side-by-side comparison, not the "
            "convergence-triggered fallback inside statistics.fit_mixed_effects. The "
            "primary random-intercept+random-slope model remains the analysis of record."
        ),
    }
    return coefficients, diagnostics


def _build_comparison_table(primary_coefficients: pd.DataFrame, robustness_coefficients: pd.DataFrame) -> pd.DataFrame:
    left = primary_coefficients.copy()
    left = left[["term", "estimate", "standard_error", "ci_lower", "ci_upper", "p_value"]]
    left.columns = [f"primary_{c}" if c != "term" else "term" for c in left.columns]
    right = robustness_coefficients.copy()
    right = right[["term", "estimate", "standard_error", "ci_lower", "ci_upper", "p_value"]]
    right.columns = [f"random_intercept_only_{c}" if c != "term" else "term" for c in right.columns]
    merged = left.merge(right, on="term", how="outer")
    merged["is_regime_by_budget_interaction_of_interest"] = merged["term"].str.contains(
        r"log2_budget:C\(regime\)", regex=True, na=False
    )
    return merged.sort_values(
        ["is_regime_by_budget_interaction_of_interest", "term"], ascending=[False, True]
    ).reset_index(drop=True)


# ---------------------------------------------------------------------------
# C. Fraction of participants benefiting from population data
# ---------------------------------------------------------------------------


def analysis_c_fraction_benefiting(summary_subject: pd.DataFrame, primary_metric: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    positive_budgets = [5, 10, 20, 40]
    regime_data = summary_subject.loc[summary_subject["regime"].isin(["subject", "source_plus_target"])]
    for method in sorted(regime_data["method"].unique()):
        for budget in positive_budgets:
            subset = regime_data.loc[
                (regime_data["method"] == method) & (regime_data["budget_per_class"] == budget)
            ]
            if subset.empty:
                continue
            pivot = subset.pivot_table(
                index=["dataset", "target_subject"], columns="regime", values=primary_metric, aggfunc="first"
            )
            if not {"subject", "source_plus_target"}.issubset(pivot.columns):
                continue
            difference = (pivot["source_plus_target"] - pivot["subject"]).dropna()

            def _row(scope: str, series: pd.Series, method: str = method, budget: int = budget) -> dict[str, Any]:
                n_positive = int((series > 0).sum())
                n_zero = int((series == 0).sum())
                n_negative = int((series < 0).sum())
                n_total = n_positive + n_zero + n_negative
                return {
                    "classification": "descriptive_exploratory_summary",
                    "method": str(method),
                    "budget_per_class": int(budget),
                    "scope_dataset": scope,
                    "metric": primary_metric,
                    "contrast": "ROC-AUC(source_plus_target) - ROC-AUC(subject)",
                    "n_total": n_total,
                    "n_positive": n_positive,
                    "n_zero": n_zero,
                    "n_negative": n_negative,
                    "fraction_positive": (n_positive / n_total) if n_total else float("nan"),
                }

            rows.append(_row("ALL", difference))
            if difference.index.get_level_values("dataset").nunique() > 1:
                for dataset, group in difference.groupby(level="dataset"):
                    rows.append(_row(str(dataset), group))
            else:
                dataset = str(difference.index.get_level_values("dataset")[0]) if len(difference) else None
                if dataset is not None:
                    rows.append(_row(dataset, difference))
    return pd.DataFrame(rows).sort_values(
        ["method", "budget_per_class", "scope_dataset"], kind="stable"
    ).reset_index(drop=True)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config, summary_subject, aucc_subject, primary_mixed_coefficients = load_primary()

    without_zhou_pairwise, without_zhou_meta = analysis_a_without_zhou(config, summary_subject, aucc_subject)
    without_zhou_pairwise.to_csv(OUTPUT_DIR / "without_zhou_pairwise_tests.csv", index=False)

    random_intercept_coefficients, random_intercept_diagnostics = analysis_b_random_intercept_only(
        config, summary_subject
    )
    random_intercept_coefficients.to_csv(OUTPUT_DIR / "random_intercept_only_coefficients.csv", index=False)
    atomic_write_text(
        OUTPUT_DIR / "random_intercept_only_diagnostics.json",
        json.dumps(random_intercept_diagnostics, indent=2, sort_keys=True, default=json_default) + "\n",
    )
    comparison = _build_comparison_table(primary_mixed_coefficients, random_intercept_coefficients)
    comparison.to_csv(OUTPUT_DIR / "mixed_model_structure_comparison.csv", index=False)

    fraction_benefiting = analysis_c_fraction_benefiting(summary_subject, config.metrics.primary)
    fraction_benefiting.to_csv(OUTPUT_DIR / "fraction_benefiting.csv", index=False)

    manifest = {
        "schema_version": 1,
        "source_primary_dir": str(PRIMARY_DIR),
        "source_summary_subject_sha256": sha256_file(PRIMARY_DIR / "summary_subject.csv"),
        "source_aucc_subject_sha256": sha256_file(PRIMARY_DIR / "aucc_subject.csv"),
        "source_mixed_effects_coefficients_sha256": sha256_file(PRIMARY_DIR / "mixed_effects_coefficients.csv"),
        "primary_n_65_analysis_unchanged": True,
        "analyses": {
            "A_without_zhou": {
                "classification": "post_confirmatory_robustness",
                "meta": without_zhou_meta,
                "output": "without_zhou_pairwise_tests.csv",
            },
            "B_random_intercept_only": {
                "classification": "model_form_robustness",
                "diagnostics": random_intercept_diagnostics,
                "outputs": [
                    "random_intercept_only_coefficients.csv",
                    "random_intercept_only_diagnostics.json",
                    "mixed_model_structure_comparison.csv",
                ],
            },
            "C_fraction_benefiting": {
                "classification": "descriptive_exploratory_summary",
                "output": "fraction_benefiting.csv",
                "no_p_values": True,
            },
        },
    }
    atomic_write_text(
        OUTPUT_DIR / "post_confirmatory_robustness_manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True, default=json_default) + "\n",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True, default=json_default))


if __name__ == "__main__":
    main()
