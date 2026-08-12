# Manuscript outline

## Working title

**The Calibration–Performance Trade-off in Motor-Imagery Brain–Computer Interfaces: A Reproducible Cross-Session Benchmark**

Alternative:

**How Much Calibration Does a Motor-Imagery BCI Need? A Multi-Dataset Later-Session Evaluation**

## One-sentence contribution

We estimate how later-session decoding changes as 0–40 labeled trials per class from a target user are added, under a fixed leakage-resistant protocol across three public EEG datasets.

## Abstract structure

1. **Problem:** subject/session variability forces calibration, but studies usually report one budget, one dataset, or within-session accuracy.
2. **Objective:** estimate calibration curves, low-budget source-data benefit, method-level data efficiency, and participant heterogeneity.
3. **Methods:** three public datasets; 67 nominal participants; complete latest-session holdout; nested budgets; three fixed classical decoders; participant-level inference.
4. **Results:** insert main curve effects, low-budget paired differences, AUCC comparison, and heterogeneity after full analysis.
5. **Conclusion:** state what labeled calibration buys, for whom, and with what uncertainty; do not claim a universal calibration threshold.

## Introduction

### Paragraph 1: practical problem

Non-invasive MI BCIs are attractive but affected by inter-participant and inter-session non-stationarity. Calibration time is part of system burden, not merely a modeling detail.

### Paragraph 2: literature limitation

Many studies optimize architecture or report a single accuracy under within-session splits. Transfer-learning work aims to reduce calibration, but evaluation protocols, budgets, and test reuse vary.

### Paragraph 3: current benchmarks

MOABB improves standardized comparison. Recent large-scale work demonstrates substantial subject-level pipeline heterogeneity, but within-session ranking does not directly quantify how labeled target data improve performance on a later session.

### Paragraph 4: study gap

A useful benchmark should fix the deployment-like test session, vary only labeled target calibration, use identical trial assignments across methods, and treat participants—not trials—as the inferential unit.

### Paragraph 5: contributions

State the seven contributions from `docs/JOURNAL_STRATEGY.md` and the research questions.

## Methods

1. Protocol registration and repository design.
2. Dataset selection and exclusions.
3. Cue-based left/right motor-imagery task.
4. Preprocessing and montage sensitivity.
5. Fixed latest-session target split.
6. Source-cohort selection.
7. Nested calibration budgets.
8. Training regimes.
9. Decoders.
10. Outcomes and AUCC.
11. Participant-level statistical analysis.
12. Reproducibility, audit, and ethics.

## Results

1. Adapter validation and participant flow.
2. Trial/session counts and data-quality summaries.
3. Population zero-calibration performance.
4. Main calibration curves by dataset/method/regime.
5. H2 low-budget paired source-data benefit.
6. H3 Riemannian versus CSP AUCC.
7. Participant heterogeneity and calibration responsiveness.
8. Mixed-effects estimates and diagnostics.
9. Three-channel sensitivity.
10. All-source sensitivity.
11. Failures and compute.

## Discussion

1. Principal empirical finding.
2. Practical interpretation of calibration burden.
3. Why grand means conceal responsive and resistant users.
4. Source-data benefit versus target-data dilution/negative transfer.
5. Relation to within-session benchmarks and adaptation literature.
6. Methodological implications for BCI evaluation.
7. Limitations: cue activity, healthy volunteers, offline analysis, heterogeneous protocols, small Zhou cohort, no online closed loop, no clinical claim, no deep-model conclusion.
8. Next studies: adaptive stopping, explicit domain alignment, method selection, online longitudinal validation, external validation on Yang2025.

## Planned figures

1. Study design: source cohort, earlier-session calibration pool, untouched latest session.
2. Main ROC-AUC calibration curves with participant bootstrap intervals.
3. Paired low-budget differences for source-plus-target versus subject-only.
4. Participant heatmaps ordered by high-budget performance or pre-declared slope.
5. AUCC paired distributions.
6. Zero-calibration versus calibration response (exploratory).
7. Sensitivity forest/contrast plot.

## Planned tables

1. Dataset/protocol characteristics.
2. Participant flow and exact trial counts.
3. Main curve estimates.
4. Confirmatory paired contrasts and Holm correction.
5. Mixed-model coefficients and diagnostics.
6. Compute and failure summary.
