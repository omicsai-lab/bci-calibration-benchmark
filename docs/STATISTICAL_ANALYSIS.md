# Statistical analysis specification

## Independent unit

The participant is the independent unit. Calibration repeats and held-out trials are repeated observations within a participant and are not counted as additional participants.

## Participant-level aggregation

For each dataset × participant × method × regime × budget, successful metric values are averaged across calibration repeats:

\[
\bar{Y}_{imrb}=\frac{1}{S}\sum_{s=1}^{S}Y_{imrbs}.
\]

The number of observed repeats and number of unique test splits are retained. In the confirmatory protocol, the latter must equal one.

## Curve estimates

Dataset-specific means and percentile bootstrap intervals resample participants, not trials. The bootstrap uses 2,000 deterministic resamples and a 95% interval.

Because the datasets differ substantially, every pooled claim is shown with dataset-specific distributions. No pooled curve is allowed to conceal an opposite direction in a source dataset.

## Normalized AUCC

Let \(x_b=\log_2(b+1)\). For a complete participant curve,

\[
\operatorname{AUCC}=
\frac{\sum_j (x_{j+1}-x_j)(Y_j+Y_{j+1})/2}
{x_{\max}-x_{\min}}.
\]

The horizon is fixed at 40 trials/class. The expected budgets are:

- subject-only: 5, 10, 20, 40;
- source-plus-target: 0, 5, 10, 20, 40.

Incomplete curves remain in `aucc_subject.csv` with a reason but derived AUCC and slope values are missing. AUCC is compared only within the same regime.

## Confirmatory paired contrasts

### Family H2: source-plus-target versus subject-only

For each method at 5 and 10 trials/class:

\[
D_i=Y_{i,\text{source+target}}-Y_{i,\text{subject}}.
\]

Outputs include pair count, mean and median difference, participant-bootstrap interval for the mean difference, Wilcoxon statistic, two-sided p-value, rank-biserial effect size, and Holm-adjusted p-value.

The six pooled tests form one confirmatory family. Dataset-specific tests form a separate supportive family.

### Family H3: Riemannian versus CSP AUCC

Within subject-only and source-plus-target regimes:

\[
D_i=\operatorname{AUCC}_{i,\text{Riemann}}-
\operatorname{AUCC}_{i,\text{CSP}}.
\]

The two pooled tests form one confirmatory Holm family. Dataset-specific estimates are supportive.

## Pooled weighting

Pooled paired contrasts are participant-weighted. Therefore, `Lee2019_MI` contributes more participants than the two smaller datasets. This is explicit in `scope_weighting` and must be stated in the manuscript.

As a sensitivity, an equal-dataset-weighted summary of dataset mean paired differences should be reported descriptively. With only three datasets, it is not treated as a high-powered random-effects meta-analysis.

## Mixed-effects model

Positive-budget participant summaries enter:

`ROC_AUC ~ log2_budget * method * regime + dataset`

with participant key `dataset::subject` as the grouping factor. A random intercept and random slope for `log2_budget` are attempted first. A random-intercept-only model is used only if the first model fails or does not converge, and the fallback is recorded.

The model is used to estimate calibration trends and heterogeneity. ROC-AUC is bounded, so residual and influence diagnostics are required. If Gaussian mixed-model assumptions are materially violated, the manuscript will emphasize paired nonparametric and bootstrap results; an alternative transformation/model may be exploratory, not silently substituted.

## Heterogeneity

Report:

- participant-specific calibration slopes;
- zero-calibration ROC-AUC;
- high-budget ROC-AUC;
- distributions and heatmaps by dataset;
- random-intercept and random-slope variance when estimable;
- correlation between zero-calibration performance and calibration response as exploratory unless separately pre-specified.

No “BCI illiterate” label is assigned from this analysis. Near-chance participants remain in the primary cohort.

## Proper scoring rules

Brier score and log loss assess probability quality, not only ranking. They are secondary because LDA and logistic probabilities may have different calibration properties and no held-out calibration set is used to recalibrate them. Lower values are better.

## Thresholded metrics

Balanced accuracy, accuracy, and macro-F1 use a fixed 0.5 threshold. They are secondary. The threshold is not tuned separately for participant, method, dataset, or budget.

## Missingness and failures

- Failed model fits are missing outcomes, not zero or 0.5 scores.
- Pairwise tests use complete participant pairs for the relevant contrast.
- Pair counts are reported for every test.
- A method with systematic failures cannot be declared superior from the remaining subset without an explicit failure analysis.
- Participant exclusions based on performance are prohibited.

## Multiplicity and interpretation

Holm correction is applied only within named, pre-specified families. Supportive and exploratory analyses are labeled. Confidence intervals, paired effect distributions, and dataset consistency take precedence over binary significance language.
