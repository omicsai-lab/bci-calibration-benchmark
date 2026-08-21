"""Aggregation and non-confirmatory statistical labeling for the EA sensitivity.

Post-confirmatory exploratory robustness component
(``docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md``). Reuses
``statistics.aggregate_repeats`` / ``summarize_curves`` / ``build_pairwise_tests``
unmodified (they are generic over whatever regime/budget values are present)
rather than editing ``statistics.py``. The one thing this module must not do
is let ``build_pairwise_tests``'s hardcoded "confirmatory" family labels leak
into an EA output file, so every family/inference_role value produced here is
rewritten to an unambiguous EA-exploratory label before being written to
disk (Human Decision 4 / spec section 7: no EA-derived result may be labeled
confirmatory or prespecified). No mixed-effects model is fit for the EA run
(Human Decision 4).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .aggregate import _participant_flow
from .config import ExperimentConfig
from .ea_runner import ALIGNMENT_MODE
from .ea_validation import audit_ea_result_integrity
from .io import write_dataframe_atomic
from .statistics import (
    _paired_result,
    _scope_iter,
    aggregate_repeats,
    build_pairwise_tests,
    summarize_curves,
)
from .utils import atomic_write_text, derive_seed, json_default, sha256_file

FAMILY_RELABEL = {
    "H2_regime_low_budget_confirmatory": "EA_H2analog_low_budget_exploratory",
    "H2_regime_low_budget_dataset_supportive": "EA_H2analog_low_budget_dataset_descriptive",
}


def _relabel_pairwise(pairwise: pd.DataFrame) -> pd.DataFrame:
    if pairwise.empty:
        return pairwise
    output = pairwise.copy()
    output["family"] = output["family"].map(lambda value: FAMILY_RELABEL.get(str(value), str(value)))
    # Every EA-derived inferential row is exploratory by construction; this
    # is not a per-row judgment call, it is the classification fixed by
    # docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md section 7.
    output["inference_role"] = "exploratory"
    assert not output["family"].astype(str).str.contains("confirmatory", case=False).any(), (
        "An EA-derived pairwise-contrast family still contains the word 'confirmatory' after "
        "relabeling; this is a hard scientific-labeling failure and must not be written to disk"
    )
    return output


def build_ea_regime_contrast_trajectory(subject_summary: pd.DataFrame, config: ExperimentConfig) -> pd.DataFrame:
    """Descriptive (no p-value) EA source_plus_target-minus-subject trajectory at every positive budget.

    Budgets 5 and 10 duplicate (in mean/median/CI) what pairwise_tests.csv
    reports with full Wilcoxon/Holm machinery; budgets 20 and 40 are
    included here only, as pre-specified descriptive persistence/reversal
    trajectories (spec section 1.9 / Human Decision 4) -- never as a new
    p-value family.
    """
    primary = config.metrics.primary
    positive_budgets = tuple(sorted(b for b in config.calibration.budgets_per_class if b > 0))
    regime_data = subject_summary.loc[subject_summary["regime"].isin(["subject", "source_plus_target"])].copy()
    rows: list[dict[str, Any]] = []
    for budget in positive_budgets:
        budget_data = regime_data.loc[regime_data["budget_per_class"] == budget]
        for method, method_data in budget_data.groupby("method", sort=True, observed=True):
            for scope, scoped in _scope_iter(method_data):
                pivot = scoped.pivot_table(
                    index=["dataset", "target_subject"], columns="regime", values=primary, aggfunc="first"
                )
                if not {"source_plus_target", "subject"}.issubset(pivot.columns):
                    continue
                result = _paired_result(
                    pivot,
                    left_column="source_plus_target",
                    right_column="subject",
                    n_resamples=config.analysis.bootstrap_resamples,
                    ci_level=config.analysis.ci_level,
                    seed=derive_seed(config.experiment.seed, "ea-trajectory", scope, method, budget, primary),
                )
                rows.append(
                    {
                        "classification": "post_confirmatory_exploratory_robustness",
                        "scope_dataset": scope,
                        "metric": primary,
                        "budget_per_class": int(budget),
                        "method": str(method),
                        "contrast": "EA source_plus_target - EA subject",
                        "n_pairs": result["n_pairs"],
                        "mean_difference": result["mean_difference"],
                        "median_difference": result["median_difference"],
                        "ci_lower": result["ci_lower"],
                        "ci_upper": result["ci_upper"],
                    }
                )
    return pd.DataFrame(rows).sort_values(
        ["scope_dataset", "method", "budget_per_class"], kind="stable"
    ).reset_index(drop=True) if rows else pd.DataFrame(rows)


def aggregate_ea_run(config: ExperimentConfig) -> Path:
    if config.alignment.mode != ALIGNMENT_MODE:
        raise ValueError(f"aggregate_ea_run requires alignment.mode == {ALIGNMENT_MODE!r}")
    output_dir = config.output_dir
    metrics_path = output_dir / "metrics.csv"
    if not metrics_path.exists():
        raise FileNotFoundError(f"EA benchmark metrics not found: {metrics_path}")
    metrics = pd.read_csv(
        metrics_path,
        dtype={"target_subject": str, "split_id": str},
        float_precision="round_trip",
    )

    audit = audit_ea_result_integrity(config, metrics=metrics)
    if audit["status"] != "ok":
        raise ValueError(f"EA result-integrity audit failed: {audit}")

    subject_summary = aggregate_repeats(metrics)
    curve_summary = summarize_curves(subject_summary, config)

    pairwise_raw = build_pairwise_tests(subject_summary, pd.DataFrame(), config)
    pairwise = _relabel_pairwise(pairwise_raw)
    trajectory = build_ea_regime_contrast_trajectory(subject_summary, config)
    flow = _participant_flow(metrics, subject_summary)

    write_dataframe_atomic(subject_summary, output_dir / "summary_subject.csv")
    write_dataframe_atomic(curve_summary, output_dir / "curve_summary.csv")
    write_dataframe_atomic(pairwise, output_dir / "pairwise_tests.csv")
    write_dataframe_atomic(trajectory, output_dir / "ea_regime_contrast_trajectory.csv")
    write_dataframe_atomic(flow, output_dir / "participant_flow.csv")
    atomic_write_text(
        output_dir / "result_audit.json",
        json.dumps(audit, indent=2, sort_keys=True, default=json_default) + "\n",
    )
    manifest = {
        "schema_version": 1,
        "classification": "post_confirmatory_exploratory_robustness",
        "created_utc": datetime.now(UTC).isoformat(),
        "experiment_fingerprint": config.experiment_fingerprint,
        "input_metrics_sha256": sha256_file(metrics_path),
        "outputs": {
            filename: sha256_file(output_dir / filename)
            for filename in (
                "summary_subject.csv",
                "curve_summary.csv",
                "pairwise_tests.csv",
                "ea_regime_contrast_trajectory.csv",
                "participant_flow.csv",
                "result_audit.json",
            )
        },
    }
    atomic_write_text(
        output_dir / "aggregation_manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True, default=json_default) + "\n",
    )
    return output_dir
