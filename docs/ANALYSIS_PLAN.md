# Pre-specified analysis plan

**Protocol version:** 0.1.0  
**Protocol date:** 2026-08-11  
**Status:** frozen before examining outcomes from the public EEG datasets

## 1. Scientific objective

The study quantifies the amount of labeled target-user EEG required to improve motor-imagery decoding on a later recording session. The central object is a **calibration–performance curve**, not a single best accuracy and not a newly proposed neural architecture.

The target estimand for method \(m\), regime \(r\), dataset \(d\), and calibration budget \(b\) is

\[
\mu_{mrd}(b)=E_i\left[E_s\{\operatorname{AUC}_{imrd}(b,s)\}\right],
\]

where \(i\) indexes eligible participants and \(s\) indexes a deterministic family of repeated, nested calibration samples. The test session is fixed for a participant; only calibration membership varies across repeats.

## 2. Research questions

1. How rapidly does later-session ROC-AUC change as labeled calibration trials from the target participant are added?
2. At low budgets, does pooled source-plus-target retraining outperform a target-only decoder?
3. Do CSP and Riemannian decoders differ in data efficiency over the fixed calibration horizon?
4. How heterogeneous are zero-calibration performance, calibration response, and high-budget performance across participants and datasets?
5. Are the conclusions robust to a common `C3/Cz/C4` montage and to the size of the source cohort?

## 3. Confirmatory task and datasets

The task is binary **left-hand versus right-hand motor imagery**. The confirmatory set is:

| MOABB adapter | Nominal N | Sessions | Runs/session | EEG channels | Left/right trials per session after selection |
|---|---:|---:|---:|---:|---:|
| `Lee2019_MI` | 54 | 2 | 1 labeled offline run | 62 | 50/class |
| `BNCI2014_001` | 9 | 2 | 6 | 22 | 72/class |
| `Zhou2016` | 4 | 3 | 2 | 14 | 50/class |

Source participants are drawn only from the same dataset as the target. Epochs are never pooled across datasets because acquisition systems, montages, references, task timing, and participant populations differ.

The final included cohort is fixed by pre-outcome adapter and split validation. A public-data exclusion requires a versioned configuration change and an entry in `docs/DECISIONS.md`; it cannot be made because of decoder performance.

## 4. Interpretation boundary: cue-based motor imagery

All three source protocols use directional or class-specific visual cues. In at least part of the selected epoch, cue-related visual activity can coexist with motor-imagery activity. Therefore, the estimand is **cue-based motor-imagery decoding**. The study will not claim that all discriminative signal is pure motor intention.

The `C3/Cz/C4` sensitivity analysis reduces, but does not eliminate, this concern. It is not an artifact-free or cue-free design.

## 5. Preprocessing

The confirmatory preprocessing is fixed:

- band-pass: 8–30 Hz;
- epoch: 0.5–3.5 s relative to the MOABB task event;
- resampling: 128 Hz;
- baseline correction: none;
- primary montage: all EEG channels exposed by the pinned adapter;
- sensitivity montage: `C3`, `Cz`, `C4`;
- stored dtype: `float32`.

The 0.5 s offset avoids the earliest cue transient but does not remove all cue-related activity. No outcome-driven artifact threshold, frequency band, epoch window, or channel subset is selected. Signal-quality summaries are reported before modeling; no participant is removed because of poor decoding.

## 6. Adapter-level structural validation

MOABB is pinned to version 1.5.0. Before a processed shard is accepted, the repository verifies the expected number of sessions, runs, EEG channels, required sensorimotor channels, and minimum class counts. A changed or collapsed adapter fails closed.

`Lee2019_MI` is instantiated with `train_run=True`, `test_run=False`, and `resting_state=False`, retaining labeled offline trials and excluding the unlabeled online-feedback phase.

## 7. Target split

For every target participant:

1. Sessions are naturally ordered by their adapter identifiers.
2. The chronologically latest session is held out in full.
3. Every earlier session forms the calibration pool.
4. Calibration and test groups must each contain both classes and meet the pre-specified minimum counts.
5. No earlier session is substituted when the latest session is inconvenient.
6. No run-level or trial-level fallback is permitted in confirmatory configurations.
7. Test-session labels and metadata are used only for the pre-specified structural eligibility check (both classes and minimum counts) and final scoring. Test-session signals or decoder outcomes are never used for preprocessing fitting, source selection, hyperparameter selection, model fitting, early stopping, exception recovery, or performance-based participant exclusion.

The exact trial roles and a cryptographic split digest are stored for audit.

## 8. Calibration budgets and repeated sampling

Budgets are labeled target trials **per class**:

`0, 5, 10, 20, 40`.

For each participant and repeat, a class-specific permutation of the earlier-session calibration pool is generated once. The budget-\(b\) sample is the first \(b\) trials of each class, so smaller samples are strict subsets of larger samples. Sampling is without replacement.

The full analysis uses 10 repeats. Repeats do not create new test sets and are not treated as independent participants; they estimate sensitivity to which calibration examples happen to be labeled.

## 9. Source cohort

The target participant is removed before source selection.

The confirmatory source cohort is capped at 10 participants per target. Within each selected source participant, at most 20 trials per class are sampled, class-balanced and deterministically. This design:

- limits the computation required for repeated CSP/Riemannian fitting;
- prevents participants with more available trials from dominating;
- prevents a small target calibration sample from being overwhelmed by thousands of source trials;
- keeps source selection independent of target test labels.

An all-source sensitivity configuration tests whether the cap materially changes conclusions.

## 10. Decoding methods

Hyperparameters are fixed before public outcomes are inspected.

### 10.1 Log-variance plus shrinkage LDA

Per-epoch channel-wise log variance is followed by LDA with automatic covariance shrinkage. This is a transparent sanity baseline.

### 10.2 CSP plus shrinkage LDA

Regularized common spatial patterns are fit only on training data, followed by log-power features and shrinkage LDA. Eight CSP components are used in the full-montage analysis, capped by channel count; three are used in the three-channel sensitivity.

### 10.3 Riemannian tangent space plus logistic regression

Each epoch is represented by an OAS covariance matrix. The Riemannian mean is estimated only from training covariances; matrices are projected to its tangent space, standardized on training data, and classified with L2-regularized logistic regression.

### 10.4 Deep-learning extension

A fixed EEGNet adapter is present but not part of the v0.1 confirmatory run. It may enter a later protocol only after separate tests for convergence, deterministic behavior, training-only early stopping, compute feasibility, and seed sensitivity.

## 11. Training regimes

- `population`: selected source participants only; defined at budget 0.
- `subject`: target calibration trials only; defined only for positive budgets.
- `source_plus_target`: pooled source trials and target calibration trials; defined at every budget.

At budget 0, `source_plus_target` is an exact duplicate of `population`. The duplicated condition is retained for a continuous calibration curve, explicitly flagged, and audited at the prediction level.

The phrase **pooled retraining** is used. This repository does not mislabel the procedure as fine-tuning, meta-learning, domain adaptation, or online adaptation.

## 12. Outcomes

### Primary endpoint

- ROC-AUC on the untouched later session.

### Secondary endpoints

- balanced accuracy;
- accuracy;
- macro-F1;
- Brier score;
- log loss.

Thresholded metrics use a fixed probability threshold of 0.5. No threshold is tuned on the test session.

### Calibration-curve summaries

For each participant, method, and adaptive regime, the normalized area under the calibration curve is

\[
\operatorname{AUCC}=\frac{1}{x_{\max}-x_{\min}}
\int_{x_{\min}}^{x_{\max}} A(x)\,dx,
\qquad x=\log_2(b+1).
\]

The horizon is fixed at 40 trials per class. AUCC is calculated only when every required budget is present. Subject-only curves begin at 5; source-plus-target curves include 0. Curves with different starting points are never compared across regimes by AUCC.

Secondary summaries include the participant-specific linear slope over `log2(b+1)` and the first observed budget reaching ROC-AUC 0.75 or balanced accuracy 0.70.

## 13. Inferential unit and repeated measures

The participant is the independent inferential unit. Trial rows and calibration repeats are retained for audit and prediction-level diagnostics but are not used as independent observations in confirmatory tests.

Metrics are first averaged over repeats within participant, method, regime, and budget. Paired contrasts then compare the same participant under two conditions.

## 14. Pre-specified inferential families

### H2: low-budget benefit of source data

At 5 and 10 trials per class, compare `source_plus_target - subject` within each method using participant-paired differences. The pooled, participant-weighted comparisons across datasets are confirmatory. The six tests (3 methods × 2 budgets) form one Holm family. Dataset-specific contrasts are supportive and corrected separately.

### H3: method-level data efficiency

Within each adaptive regime, compare `riemann_lr - csp_lda` for normalized ROC-AUC AUCC. The two pooled regime comparisons form one Holm family. Dataset-specific contrasts are supportive.

### Calibration trend and heterogeneity

Calibration slope, method, regime, and dataset are modeled using participant-level repeated-condition summaries. A random participant intercept and budget slope are attempted; a random-intercept-only model is an explicitly recorded numerical fallback. Fixed-effect estimates, uncertainty, convergence diagnostics, and random-effect variance are reported. This model supports estimation and heterogeneity characterization; it is not used to manufacture a single universal “minimum calibration” claim.

## 15. Uncertainty and effect sizes

- participant bootstrap with 2,000 resamples for means and paired mean differences;
- two-sided Wilcoxon signed-rank tests for paired confirmatory contrasts;
- Holm adjustment within each pre-specified family;
- mean and median paired differences;
- rank-biserial effect size;
- dataset-specific distributions regardless of pooled significance.

No conclusion rests on a p-value alone.

## 16. Missingness, failures, and exclusions

- A pipeline failure is recorded; it is never converted to a chance score.
- The full configuration stops on an unexpected error.
- A missing budget is retained in audit tables but excludes that curve from AUCC inference.
- A structurally invalid adapter or split must be resolved before outcome analysis, with a protocol version change if necessary.
- Participants are not excluded for low accuracy, near-chance performance, or an unfavorable calibration slope.
- Generated results are written to a configuration-fingerprinted directory and are not silently overwritten.

## 17. Sensitivity analyses

Pre-specified:

1. common `C3/Cz/C4` montage;
2. all eligible source participants rather than the 10-participant cap;
3. dataset-specific estimates alongside pooled participant-weighted estimates;
4. balanced accuracy and proper scoring rules as secondary endpoints;
5. descriptive comparison of zero-calibration performance and calibration response.

Additional analyses discovered after viewing outcomes must be labeled exploratory.

## 18. Reporting standard

The manuscript will report participant flow, exact class and split counts, software versions, protocol fingerprints, calibration curves, subject-level distributions, failed conditions, null results, cue-related limitations, and computational resources. Public data and original dataset citations are not redistributed or replaced by this repository.
