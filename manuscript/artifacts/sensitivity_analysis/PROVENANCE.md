# Provenance — sensitivity analysis comparison

This directory compares the two prespecified sensitivity analyses
(`configs/sensitivity_three_channels.yaml`,
`configs/sensitivity_all_sources.yaml`) against the audited primary
confirmatory analysis. Every number in `sensitivity_comparison.csv` and
`sensitivity_comparison.md` is read directly from the three runs' own
audited outputs. No benchmark, model fit, prediction, or statistical test
was re-run, altered, or newly computed to build this comparison — it is a
read-only aggregation of already-audited results.

## Input result directories

| Run | Output directory | Experiment fingerprint | Preprocessing fingerprint | Audit status |
|---|---|---|---|---|
| Primary confirmatory | `results/bci-calibration-full-v1-3fb8efe7e617b0c1/` | `3fb8efe7e617b0c1` | `861cc64b9adbc47c` | `ok` |
| Three-channel sensitivity | `results/bci-calibration-three-channels-1fcb3f9ba9823bb1/` | `1fcb3f9ba9823bb1` | `ea325577448eac83` | `ok` |
| All-source sensitivity | `results/bci-calibration-all-sources-sensitivity-e86ca10985667aec/` | `e86ca10985667aec` | `861cc64b9adbc47c` (same as primary; `channels: null`, so preprocessing is identical to the primary analysis) | `ok` |

## Input files read

For each of the three run directories above:

- `pairwise_tests.csv` — source of every row in `sensitivity_comparison.csv`
  and every H2/H3 table in `sensitivity_comparison.md`.
- `participant_flow.csv` — source of the "Cohort and execution" comparison
  (confirmed byte-identical across all three runs).
- `result_audit.json` — source of the audit-status column above.
- `run_manifest.json` — source of the fingerprints above and the runtime
  figures in `docs/sensitivity_run_acceptance.md`.

No other file (no `metrics.csv`, `predictions.csv.gz`, `curve_summary.csv`,
`summary_subject.csv`, `mixed_effects_coefficients.csv`, or figure) was used
to build this comparison; the pooled and per-dataset contrasts already
present in `pairwise_tests.csv` are sufficient for every reported number,
and using them (rather than recomputing anything from raw metrics or
predictions) guarantees this comparison performs no new hypothesis testing.

## Filtering logic

**H2 rows** (`sensitivity_comparison.csv`, `comparison == "H2"`): from each
run's `pairwise_tests.csv`, rows with
`family == "H2_regime_low_budget_confirmatory"` — the pooled
(`scope_dataset == "ALL"`, `scope_weighting ==
"participant_weighted_across_datasets"`), participant-weighted,
`source_plus_target_vs_subject` regime contrast, for all three methods at
`budget_per_class` 5 and 10. 6 rows per run × 3 runs = 18 rows.

**H3 rows** (`comparison == "H3"`): rows with
`family == "H3_method_aucc_confirmatory"` — the pooled
`riemann_lr - csp_lda` contrast on normalized log-AUCC, one row per regime
(`subject`, `source_plus_target`). 2 rows per run × 3 runs = 6 rows.

**Dataset-dependence discussion** (`sensitivity_comparison.md`, "Calibration
trajectory comparison" section only — not written to the CSV): rows with
`family == "H2_regime_low_budget_dataset_supportive"`, i.e. the same H2
contrast computed separately within each dataset
(`scope_dataset in {"Lee2019_MI", "BNCI2014_001", "Zhou2016"}`). These are
supportive/descriptive per-dataset estimates, not independent confirmatory
tests (per `docs/DECISIONS.md`), and are used here only to explain *why*
the pooled all-source H2/H3 changes are concentrated in Lee2019_MI's
contribution — not as an additional confirmatory claim.

**`diff_from_primary_mean`** (`sensitivity_comparison.csv`): for each
sensitivity row, `mean_difference` minus the primary run's
`mean_difference` for the same `(comparison, method, budget_per_class)` (H2)
or `(comparison, method, regime)` (H3) key. `0.0` for every primary row by
construction (self-comparison).

## What this comparison does not do

- It does not recompute any bootstrap CI, Wilcoxon test, or Holm adjustment
  — all `ci_lower`/`ci_upper`/`p_value`/`p_holm`/`rank_biserial` values are
  copied verbatim from each run's own `pairwise_tests.csv`.
- It does not select or omit any H2 or H3 confirmatory row: all 6 H2 rows
  and both H3 rows from every run are included.
- It does not characterize any result as "robust" or "not robust" — see the
  interpretation boundary noted at the top of `sensitivity_comparison.md`.
