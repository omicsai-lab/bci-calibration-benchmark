# Post-confirmatory robustness — factual summary

Reviewer-motivated robustness package, post-confirmatory throughout. See
`PROVENANCE.md` for exact inputs/method per analysis and
`docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md` /
`docs/post_confirmatory_robustness_acceptance.md` for the full specification
and execution record. **No item in this document is confirmatory or
prespecified**, regardless of its result.

## A. Without-Zhou pooled re-aggregation (N=63)

Excluding `Zhou2016`'s 2 participants (of 65) and recomputing the identical
pooled H2/H3 contrasts with the identical statistical machinery used for the
primary N=65 analysis:

**H2 (source+target pooled retraining − subject-only, ROC-AUC), pooled:**

| Method | Budget | Primary (N=65) mean Δ | Without-Zhou (N=63) mean Δ | Direction | Holm p (without-Zhou) |
|---|---:|---:|---:|---|---:|
| CSP + LDA | 5 | +0.057 | +0.054 | consistent | <0.001 |
| CSP + LDA | 10 | +0.021 | +0.019 | consistent | 0.221 |
| Log-variance + LDA | 5 | +0.059 | +0.058 | consistent | <0.001 |
| Log-variance + LDA | 10 | +0.031 | +0.030 | consistent | 0.026 |
| Riemannian TS + LR | 5 | +0.035 | +0.034 | consistent | 0.026 |
| Riemannian TS + LR | 10 | +0.008 | +0.007 | consistent | 0.570 |

All six pooled contrasts keep the same sign and the same significant/
non-significant pattern as the primary N=65 analysis; magnitudes shift by
at most 0.003. This is the expected result given Zhou2016 contributes only
2 of 65 (3.1%) participant weight to the pooled estimate.

**H3 (Riemannian − CSP, normalized log-AUCC), pooled:** subject-only
+0.036 (both N=65 and N=63, bit-identical — this regime uses no
source-cohort data, so it cannot be affected by dropping Zhou2016's 2
participants' *source* trials, but participant weight itself did change;
the values are identical to the precision shown here); source+target
+0.020 (N=65) vs. +0.022 (N=63), both non-significant (Holm p = 0.175 vs.
0.123).

Full table: `source_data/without_zhou_pairwise_tests.csv`.

## B. Random-intercept-only mixed model (model-form robustness)

Same 1,560 observations, same fixed-effects formula
(`roc_auc ~ log2_budget * C(method) * C(regime) + C(dataset)`) as the
primary random-intercept + random-slope model. The random-intercept-only
structure also converged (AIC −3643.7, BIC −3558.1, log-likelihood
1837.9).

The fixed effect of primary scientific interest — the
`log2_budget × regime[subject]` interaction, i.e. how the source+target
advantage's calibration slope differs from the subject-only slope — is
**identical to six decimal places** between the two random-effects
structures: estimate 0.027358, p < 0.001, under both the primary
random-intercept+slope model and this random-intercept-only comparison.
The calibration-trend fixed effects are not sensitive to this modeling
choice in this dataset.

Full side-by-side table: `source_data/mixed_model_structure_comparison.csv`;
full random-intercept-only coefficient table:
`source_data/random_intercept_only_coefficients.csv`.

## C. Fraction of participants benefiting from population data (descriptive)

Participant-level (repeat-averaged), pooled across all 65 participants,
`ROC-AUC(source_plus_target) > ROC-AUC(subject)`:

| Method | Budget 5 | Budget 10 | Budget 20 | Budget 40 |
|---|---:|---:|---:|---:|
| CSP + LDA | 46/65 (70.8%) | 41/65 (63.1%) | 33/65 (50.8%) | 24/65 (36.9%) |
| Log-variance + LDA | 47/65 (72.3%) | 44/65 (67.7%) | 41/65 (63.1%) | 38/65 (58.5%) |
| Riemannian TS + LR | 43/65 (66.2%) | 37/65 (56.9%) | 25/65 (38.5%), 1 tie | 19/65 (29.2%), 1 tie |

Fraction benefiting declines with budget for every method — consistent
with the calibration-curve interpretation that pooled retraining's low-
budget advantage narrows as subject-only calibration accumulates more
labeled trials. Ties (`n_zero`; two occur, both Riemannian TS + LR at
higher budgets) are reported separately, not folded into "not benefiting."
No p-value is computed for this table by design. Per-dataset fractions:
`source_data/fraction_benefiting.csv`.

## D. Euclidean Alignment (EA) sensitivity

Post-confirmatory exploratory robustness. Training-only Euclidean Alignment
(literal He-Wu formulation, `R = mean_i(X_i X_i^T)`, no `/n_samples`
normalization) applied upstream of the same three confirmatory decoders,
at budgets 5/10/20/40 only (budget 0 is structurally undefined for this
design). Full 65-participant run: 15,600/15,600 conditions succeeded, 0
failures, result-integrity audit `status: "ok"`, and the fail-closed
assignment-reuse equality gate passed before any model was fit (identical
140,110 split rows / 97,500 calibration rows / 614 source-selection rows /
24,560 source-trial rows to the primary run, confirmed by independent
regeneration). 1,655,040 held-out predictions — exactly matching the
assignment-derived arithmetic prediction in
`docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md` section 4.1
(`2,068,800 × 8/10`).

### H2-analog contrast (EA source+target − EA subject, ROC-AUC), pooled, budgets 5 and 10

| Method | Budget | Primary (unaligned) mean Δ [95% CI] | EA mean Δ [95% CI] | Direction | Magnitude |
|---|---:|---|---|---|---|
| CSP + LDA | 5 | +0.057 [+0.028, +0.083] | **+0.113** [+0.088, +0.136] | consistent | strengthened |
| CSP + LDA | 10 | +0.021 [-0.011, +0.050] | **+0.077** [+0.052, +0.101] | consistent | strengthened |
| Log-variance + LDA | 5 | +0.059 [+0.031, +0.085] | **+0.116** [+0.091, +0.140] | consistent | strengthened |
| Log-variance + LDA | 10 | +0.031 [+0.004, +0.058] | **+0.066** [+0.044, +0.088] | consistent | strengthened |
| Riemannian TS + LR | 5 | +0.035 [+0.010, +0.060] | **+0.054** [+0.032, +0.078] | consistent | strengthened |
| Riemannian TS + LR | 10 | +0.008 [-0.016, +0.031] | **+0.029** [+0.006, +0.051] | consistent | strengthened |

**Direction:** consistent with the unaligned primary result (pooled
retraining outperforms subject-only calibration) in all 6/6 method × budget
combinations. **Magnitude:** strengthened at every one of the 6
combinations, roughly doubling the primary effect at 5 trials/class for
CSP and log-variance. **Statistical support:** the two primary
combinations whose 95% CI crossed zero (CSP + LDA @10, Riemannian TS + LR
@10) both have a CI that excludes zero under EA. This is the same
qualitative pattern already on record for the three-channel prespecified
sensitivity in `manuscript/artifacts/sensitivity_analysis/sensitivity_comparison.md`
("the two primary-non-significant rows... both become significant"),
observed here for a different, post-confirmatory manipulation.

Full table: `source_data/ea_vs_primary_h2_comparison.csv`;
`source_data/ea_pairwise_tests.csv`.

### Descriptive trajectories at 20 and 40 trials/class — persistence and a reversal

Pooled EA `source_plus_target − subject` mean difference by budget:

| Method | 5 | 10 | 20 | 40 |
|---|---:|---:|---:|---:|
| CSP + LDA | +0.113 | +0.077 | +0.048 | **+0.030** |
| Log-variance + LDA | +0.116 | +0.066 | +0.042 | **+0.036** |
| Riemannian TS + LR | +0.054 | +0.029 | +0.002 | **-0.016** |

CSP + LDA and Log-variance + LDA persist in the positive direction through
40 trials/class, shrinking in magnitude as subject-only calibration
accumulates more data — the expected narrowing pattern. **Riemannian TS +
LR reverses direction under EA between 10 and 40 trials/class**: from a
significant positive effect at 5 (+0.054) and 10 (+0.029) trials/class,
through an indistinguishable-from-zero estimate at 20 (+0.002, CI
[-0.020, +0.024]), to a negative point estimate at 40 (-0.016, CI
[-0.037, +0.005], still crossing zero). This reversal is reported as
observed; it is not treated as a confirmatory finding and no p-value
family spans these four budgets.

Full table: `source_data/ea_regime_contrast_trajectory.csv`,
`source_data/ea_vs_primary_trajectory.csv`.

### Dataset dependence

The BNCI2014_001-specific, dataset-supportive Riemannian TS + LR contrast
stays **negative under EA**, consistent in direction with the unaligned
primary result's dataset-specific finding (see section 6.3 of
`docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md`): -0.039 [-0.101, +0.016] at 5
trials/class (primary: -0.053) and -0.067 [-0.117, -0.024] at 10
trials/class (primary: -0.068, itself the only dataset-specific EA
combination whose CI excludes zero). Both point estimates and CI widths
are close to the unaligned primary run's; EA does not resolve BNCI2014_001's
subject-only Riemannian advantage. Lee2019_MI (54/65 participants) drives
the pooled EA strengthening described above; Zhou2016 (2/65 participants)
is descriptive only and shows the same qualitative pattern (all six
positive) but is not independently informative given its size.

Full per-dataset table: `source_data/ea_pairwise_tests.csv`
(`family == "EA_H2analog_low_budget_dataset_descriptive"`).

### Interpretation boundary

This is a single post-confirmatory exploratory sensitivity, not a
confirmatory test and not a claim that EA "works" or "fails." The pooled
strengthening at low budgets and the Riemannian-specific higher-budget
reversal are both reported factually; neither should be read as resolving
whether Euclidean Alignment is beneficial in general — see
`docs/post_confirmatory_robustness_acceptance.md` for the full scientific
cautions.
