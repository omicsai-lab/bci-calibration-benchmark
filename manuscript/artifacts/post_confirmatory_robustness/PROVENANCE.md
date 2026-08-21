# Provenance — post-confirmatory robustness package

This directory packages four post-confirmatory robustness analyses,
authorized under human-reviewed decisions recorded in
`docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md` (originally written
pre-implementation, subsequently approved with overriding decisions; see
that file's status header and `docs/post_confirmatory_robustness_acceptance.md`
for the implementation/execution record). No item here is prespecified and
none may be described as confirmatory, regardless of its result.

## Classification of every analysis in this package

| Analysis | Classification | Source |
|---|---|---|
| A. Without-Zhou pooled re-aggregation | post-confirmatory robustness | `results/bci-calibration-full-v1-3fb8efe7e617b0c1/post_confirmatory_robustness/without_zhou_pairwise_tests.csv` |
| B. Random-intercept-only mixed model | model-form robustness | `results/bci-calibration-full-v1-3fb8efe7e617b0c1/post_confirmatory_robustness/random_intercept_only_coefficients.csv`, `mixed_model_structure_comparison.csv` |
| C. Fraction benefiting from population data | descriptive exploratory summary (no p-values) | `results/bci-calibration-full-v1-3fb8efe7e617b0c1/post_confirmatory_robustness/fraction_benefiting.csv` |
| D. Euclidean Alignment (EA) sensitivity | post-confirmatory exploratory robustness | `results/bci-calibration-ea-training-only-sensitivity-43e15c22709c6e6b/` |

## A/B/C: inputs and method

A, B, and C use **only** the closed primary confirmatory run's existing,
already-audited outputs
(`results/bci-calibration-full-v1-3fb8efe7e617b0c1/summary_subject.csv`,
`aucc_subject.csv`, `mixed_effects_coefficients.csv`). No benchmark was
re-run and the primary N=65 analysis's own files were never modified —
`scripts/post_confirmatory_robustness.py` is read-only with respect to that
directory except for writing new, additive files into its
`post_confirmatory_robustness/` subdirectory.

- **A** filters `summary_subject.csv`/`aucc_subject.csv` to
  `dataset != "Zhou2016"` (N: 65 → 63) and recomputes the identical pooled
  H2/H3 contrasts via `statistics.build_pairwise_tests` — the same function,
  same bootstrap/Wilcoxon/Holm machinery, same `configs/full.yaml`
  statistical settings used for the primary confirmatory analysis. Family
  labels are rewritten (e.g. `H2_regime_low_budget_confirmatory` →
  `H2_regime_low_budget_without_zhou_robustness`) so no row can be
  misread as confirmatory.
- **B** re-derives the identical 1,560-observation, positive-budget
  participant-level dataset and the identical fixed-effects formula
  (`roc_auc ~ log2_budget * C(method) * C(regime) + C(dataset)`) used by
  the primary mixed model, and fits `statsmodels.formula.api.mixedlm` with
  `re_formula="1"` (random intercept only) as a deliberate, always-computed
  comparison — not the convergence-triggered fallback inside
  `statistics.fit_mixed_effects`. The primary random-intercept+random-slope
  model (`mixed_effects_coefficients.csv`) remains the analysis of record;
  `mixed_model_structure_comparison.csv` joins both structures' fixed
  effects side by side, term by term.
- **C** is a pure pivot/count over `summary_subject.csv` (already
  repeat-averaged per participant): for each method and budget in
  `{5, 10, 20, 40}`, `n_positive`/`n_zero`/`n_negative`/`fraction_positive`
  of participants with `ROC-AUC(source_plus_target) > ROC-AUC(subject)`,
  reported pooled (`scope_dataset == "ALL"`) and per dataset. Ties are
  counted in `n_zero`, never folded into `n_negative`. No p-value is
  computed.

## D: inputs and method

D reuses the primary run's `split_assignments.csv.gz`,
`calibration_assignments.csv.gz`, `source_selection.csv`, and
`source_trial_assignments.csv.gz` (fail-closed equality-gated against an
independent regeneration before any model was fit — see
`results/bci-calibration-ea-training-only-sensitivity-43e15c22709c6e6b/assignment_reuse_report.json`)
and applies training-only Euclidean Alignment upstream of the same three
confirmatory decoders, at budgets `{5, 10, 20, 40}` only (budget 0 is
structurally undefined for this design). Full detail:
`docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md` section 1 and
`docs/post_confirmatory_robustness_acceptance.md`.

## What this package does not do

- It does not alter, delete, or re-run anything in
  `results/bci-calibration-full-v1-3fb8efe7e617b0c1/` (the primary N=65
  analysis of record) or in either prespecified sensitivity's result
  directory.
- It does not introduce a new confirmatory inferential family, a new Holm
  correction spanning multiple runs, or a statistical test comparing EA to
  the unaligned primary result — the EA-vs-primary comparison is factual
  only (direction, magnitude, CI, persistence/reversal with budget,
  dataset/method dependence), mirroring
  `manuscript/artifacts/sensitivity_analysis/sensitivity_comparison.md`'s
  existing pattern for the two prespecified sensitivities.
- It does not select a mixed-model structure based on significance (B
  reports both structures; neither replaces the other).
