# Sensitivity analysis comparison

Factual, audit-only comparison of the two prespecified sensitivity analyses
against the audited primary confirmatory analysis. No new hypothesis tests
were performed; every number below is read directly from each run's audited
`pairwise_tests.csv`. Full precision, machine-readable values are in
`sensitivity_comparison.csv`. Filtering logic and exact input files are in
`PROVENANCE.md`.

This document uses only factual comparison labels (direction consistent /
inconsistent with primary, effect estimate attenuated / strengthened,
confidence interval widened, statistical support retained / not retained).
It does not characterize the manuscript's findings as "robust" or "not
robust" — that is a scientific-interpretation judgment reserved for human
review after this report.

## Cohort and execution

All three analyses (primary, three-channel, all-source) use the **same 65
structurally validated participants**: Lee2019_MI 54, BNCI2014_001 9,
Zhou2016 2 (Zhou2016 subjects 2 and 4 structurally excluded in every run,
per `docs/DECISIONS.md`). `participant_flow.csv` is byte-identical across
all three result directories:

| Dataset | Attempted | Succeeded | Failed |
|---|---|---|---|
| BNCI2014_001 | 9 | 9 | 0 |
| Lee2019_MI | 54 | 54 | 0 |
| Zhou2016 | 2 | 2 | 0 |

19,500/19,500 conditions completed and 2,068,800 held-out predictions were
produced in every one of the three runs, and `result_audit.json` reports
`status: "ok"` for all three. No participant was added, removed, or
re-included beyond the frozen exclusion set in either sensitivity analysis.

## H2 comparison — source + target pooled retraining − subject-only calibration (ROC-AUC)

Participant-weighted pooled estimate across all three datasets, n = 65 in
every row.

| Method | Budget | Source | Mean Δ ROC-AUC [95% CI] | Holm p | r_rb | Sign | Δ from primary |
|---|---|---|---|---|---|---|---|
| CSP + LDA | 5 | primary | +0.057 [+0.028, +0.083] | <0.001 | +0.568 | + | — |
| CSP + LDA | 5 | three-channel | +0.063 [+0.038, +0.082] | <0.001 | +0.720 | + | +0.006 |
| CSP + LDA | 5 | all-source | +0.132 [+0.103, +0.160] | <0.001 | +0.901 | + | +0.075 |
| CSP + LDA | 10 | primary | +0.021 [-0.011, +0.050] | 0.136 | +0.261 | + | — |
| CSP + LDA | 10 | three-channel | +0.045 [+0.026, +0.062] | <0.001 | +0.685 | + | +0.024 |
| CSP + LDA | 10 | all-source | +0.090 [+0.060, +0.118] | <0.001 | +0.745 | + | +0.069 |
| Log-variance + LDA | 5 | primary | +0.059 [+0.031, +0.085] | <0.001 | +0.575 | + | — |
| Log-variance + LDA | 5 | three-channel | +0.065 [+0.044, +0.086] | <0.001 | +0.755 | + | +0.007 |
| Log-variance + LDA | 5 | all-source | +0.093 [+0.066, +0.120] | <0.001 | +0.775 | + | +0.035 |
| Log-variance + LDA | 10 | primary | +0.031 [+0.004, +0.058] | 0.016 | +0.397 | + | — |
| Log-variance + LDA | 10 | three-channel | +0.050 [+0.027, +0.070] | <0.001 | +0.681 | + | +0.018 |
| Log-variance + LDA | 10 | all-source | +0.062 [+0.037, +0.086] | <0.001 | +0.648 | + | +0.031 |
| Riemannian TS + LR | 5 | primary | +0.035 [+0.010, +0.060] | 0.015 | +0.413 | + | — |
| Riemannian TS + LR | 5 | three-channel | +0.089 [+0.066, +0.111] | <0.001 | +0.808 | + | +0.054 |
| Riemannian TS + LR | 5 | all-source | +0.045 [+0.017, +0.075] | 0.002 | +0.461 | + | +0.010 |
| Riemannian TS + LR | 10 | primary | +0.008 [-0.016, +0.031] | 0.478 | +0.101 | + | — |
| Riemannian TS + LR | 10 | three-channel | +0.056 [+0.038, +0.074] | <0.001 | +0.758 | + | +0.048 |
| Riemannian TS + LR | 10 | all-source | +0.014 [-0.013, +0.041] | 0.297 | +0.149 | + | +0.006 |

**Direction:** consistent with primary (positive: pooled retraining
outperforms subject-only calibration) in all 18/18 method × budget × source
combinations.

**Magnitude:**
- **Three-channel:** effect estimate strengthened at every method/budget
  pair, most substantially for Riemannian TS + LR (5 trials/class: +0.035 →
  +0.089; 10 trials/class: +0.008 → +0.056, a 7-fold increase). Statistical
  support strengthened correspondingly — the two primary-non-significant
  rows (CSP + LDA @10, `Holm p = 0.136`; Riemannian TS + LR @10, `Holm p =
  0.478`) both become significant under the three-channel montage
  (`Holm p < 0.001` and confidence intervals that no longer cross zero).
- **All-source:** effect estimate strengthened at every method/budget pair,
  most substantially for CSP + LDA (5 trials/class: +0.057 → +0.132; 10
  trials/class: +0.021 → +0.090) and Log-variance + LDA. Riemannian TS + LR
  strengthens only modestly (+0.035 → +0.045 at 5 trials/class) and its
  10-trials/class estimate remains non-significant (`Holm p = 0.297`,
  primary `Holm p = 0.478`).

## H3 comparison — Riemannian TS + LR − CSP + LDA (normalized log-AUCC)

Participant-weighted pooled estimate, n = 65 in every row.

| Regime | Source | Mean Δ log-AUCC [95% CI] | Holm p | r_rb | Sign | Δ from primary |
|---|---|---|---|---|---|---|
| Subject-only | primary | +0.036 [+0.022, +0.049] | <0.001 | +0.704 | + | — |
| Subject-only | three-channel | -0.005 [-0.009, -0.000] | 0.051 | -0.318 | - | -0.041 |
| Subject-only | all-source | +0.036 [+0.022, +0.049] | <0.001 | +0.704 | + | +0.000 |
| Source + target | primary | +0.020 [-0.002, +0.043] | 0.175 | +0.193 | + | — |
| Source + target | three-channel | +0.007 [-0.002, +0.015] | 0.204 | +0.183 | + | -0.014 |
| Source + target | all-source | -0.043 [-0.063, -0.024] | <0.001 | -0.566 | - | -0.064 |

**Subject-only regime:** all-source is bit-identical to primary (expected:
this regime uses no source-cohort data at all, so it cannot be affected by
the source-cohort-size sensitivity). Three-channel **reverses direction**
(+0.036 → -0.005) and statistical support is **not retained**
(`Holm p < 0.001` → `Holm p = 0.051`, just above 0.05); the confidence
interval for the three-channel estimate is narrow and sits almost entirely
on the negative side of zero.

**Source + target regime:** primary is already non-significant
(`Holm p = 0.175`, CI crosses zero). Three-channel is direction-consistent
but further attenuated toward zero (`Holm p = 0.204`). All-source **reverses
direction** to a statistically significant negative effect
(+0.020 → -0.043, `Holm p < 0.001`) — under the all-source design, CSP + LDA
significantly outperforms Riemannian TS + LR in the pooled source-plus-target
regime, the opposite pattern from (the already non-significant) primary
estimate.

## Calibration trajectory comparison

The pooled low-budget advantage of source+target retraining over
subject-only calibration (H2, above) is **preserved in direction and
strengthened in magnitude** under both sensitivity analyses, at every
method and budget tested. No sensitivity reverses H2's direction.

**Dataset dependence**, from the per-dataset supportive contrasts
underlying the pooled H2 estimate:

- **Lee2019_MI** (54 participants) is the only dataset whose H2 estimates
  change under the all-source sensitivity (e.g. CSP + LDA @5:
  +0.057 → +0.147; Riemannian TS + LR @5: +0.049 → +0.061). BNCI2014_001 and
  Zhou2016's all-source H2 estimates are bit-identical to primary. This
  traces to the source-selection design: source participants are drawn only
  from the *same* dataset as the target
  (`runner.py`: "Source and target shards must belong to the same
  dataset"). Lee2019_MI is the only confirmatory dataset with more than 10
  same-dataset non-target participants available (53), so it is the only
  dataset where raising `source.max_subjects` from 10 to unlimited can
  change anything; BNCI2014_001 (8 available) and Zhou2016 (1 available)
  are already below the cap in the primary analysis. The all-source H3
  reversal (source-plus-target regime) is consistent with being driven
  predominantly by this same Lee2019_MI-concentrated change, given
  Lee2019_MI's 54/65 participant weight in the pooled estimate.
- **Three-channel** changes every dataset's H2 estimates (all three
  datasets' inputs are re-preprocessed under the restricted montage), with
  the largest per-dataset swings concentrated in Riemannian TS + LR
  (e.g. BNCI2014_001 Riemannian TS + LR @5: -0.053 → +0.052, a **sign
  reversal at the dataset-specific, non-confirmatory level** — BNCI2014_001
  alone is descriptive/supportive, not independently confirmatory, per
  `docs/DECISIONS.md`, and this reversal does not propagate to the pooled
  H2 estimate, which stays positive for Riemannian TS + LR under
  three-channel).

## Cohort and execution — reconfirmed

Same 65 participants, same exclusions, in all three analyses (see "Cohort
and execution" above). No new hypothesis tests were performed beyond the
prespecified H2/H3 aggregated contrasts already computed by each run's own
`aggregate_results.py`.
