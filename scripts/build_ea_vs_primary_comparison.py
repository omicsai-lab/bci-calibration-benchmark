#!/usr/bin/env python3
"""Factual (non-inferential) comparison: EA sensitivity vs. the unaligned primary result.

Mirrors the existing pattern in
`manuscript/artifacts/sensitivity_analysis/sensitivity_comparison.md` for the
two prespecified sensitivities: reads each run's own already-computed,
already-audited `pairwise_tests.csv` directly and performs **no new
hypothesis test** comparing the two runs (no test-of-tests, no
cross-run Holm family). Read-only with respect to both result directories.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PRIMARY_DIR = Path("results/bci-calibration-full-v1-3fb8efe7e617b0c1")
EA_DIR = Path("results/bci-calibration-ea-training-only-sensitivity-43e15c22709c6e6b")
OUTPUT_DIR = Path("manuscript/artifacts/post_confirmatory_robustness/source_data")


def main() -> None:
    primary = pd.read_csv(PRIMARY_DIR / "pairwise_tests.csv")
    ea = pd.read_csv(EA_DIR / "pairwise_tests.csv")
    ea_trajectory = pd.read_csv(EA_DIR / "ea_regime_contrast_trajectory.csv")

    primary_h2 = primary.loc[primary["family"] == "H2_regime_low_budget_confirmatory"].copy()
    ea_h2 = ea.loc[ea["family"] == "EA_H2analog_low_budget_exploratory"].copy()

    key = ["method_left", "budget_per_class"]
    merged = primary_h2[key + ["mean_difference", "ci_lower", "ci_upper", "p_holm"]].merge(
        ea_h2[key + ["mean_difference", "ci_lower", "ci_upper", "p_holm"]],
        on=key,
        suffixes=("_primary", "_ea"),
        how="outer",
        validate="one_to_one",
    )
    merged["direction_primary"] = merged["mean_difference_primary"].apply(lambda v: "+" if v > 0 else "-")
    merged["direction_ea"] = merged["mean_difference_ea"].apply(lambda v: "+" if v > 0 else "-")
    merged["direction_consistent"] = merged["direction_primary"] == merged["direction_ea"]
    merged["diff_ea_minus_primary"] = merged["mean_difference_ea"] - merged["mean_difference_primary"]
    merged["magnitude_change"] = merged["diff_ea_minus_primary"].apply(
        lambda v: "strengthened" if v > 0 else ("attenuated" if v < 0 else "unchanged")
    )
    merged["ci_excludes_zero_primary"] = (merged["ci_lower_primary"] > 0) | (merged["ci_upper_primary"] < 0)
    merged["ci_excludes_zero_ea"] = (merged["ci_lower_ea"] > 0) | (merged["ci_upper_ea"] < 0)
    merged = merged.sort_values(["method_left", "budget_per_class"]).reset_index(drop=True)
    merged.to_csv(OUTPUT_DIR / "ea_vs_primary_h2_comparison.csv", index=False)

    # Persistence/reversal trajectory: EA-only mean differences at all four
    # budgets (5, 10, 20, 40), pooled ("ALL") scope, alongside the primary
    # run's two available budgets for direct visual comparison.
    ea_traj_pooled = ea_trajectory.loc[ea_trajectory["scope_dataset"] == "ALL"].copy()
    ea_traj_pooled = ea_traj_pooled[["method", "budget_per_class", "mean_difference", "ci_lower", "ci_upper"]]
    ea_traj_pooled.insert(0, "source", "ea_sensitivity")
    primary_traj = primary_h2.rename(columns={"method_left": "method"})[
        ["method", "budget_per_class", "mean_difference", "ci_lower", "ci_upper"]
    ].copy()
    primary_traj.insert(0, "source", "primary_unaligned")
    trajectory = pd.concat([primary_traj, ea_traj_pooled], ignore_index=True).sort_values(
        ["method", "budget_per_class", "source"]
    )
    trajectory.to_csv(OUTPUT_DIR / "ea_vs_primary_trajectory.csv", index=False)

    print(merged.to_string(index=False))
    print()
    print(trajectory.to_string(index=False))


if __name__ == "__main__":
    main()
