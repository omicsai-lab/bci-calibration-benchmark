# Methods draft

## Study design

We designed a pre-specified secondary-analysis benchmark to quantify the relationship between target-user calibration burden and motor-imagery decoding performance on a later EEG recording session. The protocol and software were frozen before examining outcomes from the public datasets. All analyses used public data accessed through the Mother of All BCI Benchmarks (MOABB) version 1.5.0. The participant was the independent inferential unit.

## Datasets and task

We selected three datasets that exposed at least two recording sessions, contained left- and right-hand motor-imagery trials, supplied at least 40 labeled trials per class before the held-out session, and permitted a fixed later-session test without run- or trial-level fallback: Lee2019_MI (54 participants, two sessions, 62 EEG channels), BNCI2014_001/BCI Competition IV Dataset 2a (nine participants, two sessions, 22 EEG channels), and Zhou2016 (four participants, three sessions, 14 EEG channels). The nominal cohort therefore comprised 67 participants. Models and source cohorts were constructed within dataset; epochs were not pooled across datasets.

For Lee2019_MI, we instantiated the adapter with `train_run=True`, `test_run=False`, and `resting_state=False`, thereby retaining the labeled offline motor-imagery phase in both sessions and excluding the unlabeled online-feedback phase. For BNCI2014_001 and Zhou2016, the native multiclass labels were restricted to left- and right-hand imagery.

The task was cue-based motor imagery. Because class-specific visual cues remained present for part or all of the selected interval in the original protocols, the resulting discrimination cannot be interpreted as pure motor-intent decoding free of cue-related activity.

## Signal processing

EEG was band-pass filtered from 8 to 30 Hz, epoched from 0.5 to 3.5 s relative to the task event exposed by MOABB, resampled to 128 Hz, and stored as `float32`. No baseline correction was applied. The primary analysis used all EEG channels available in each dataset. A pre-specified sensitivity analysis used the common `C3`, `Cz`, and `C4` montage. Preprocessing parameters were fixed before model evaluation, and no outcome-driven artifact threshold or participant screening was used.

The software verified the expected number of sessions, runs, EEG channels, sensorimotor channels, and minimum per-session class counts for each pinned adapter. Processed participant shards included cryptographic checksums, software versions, channel names, sampling frequency, class counts, and trial metadata.

## Later-session evaluation and calibration sampling

For each target participant, the chronologically latest recording session was held out in its entirety. All earlier sessions formed the calibration pool. Test-session labels and metadata were used only to verify the pre-specified structural eligibility criteria (presence of both classes and minimum class counts) and for final scoring. Test-session signals or decoder outcomes were not used for source selection, preprocessing fitting, hyperparameter selection, model fitting, early stopping, exception handling, or performance-based participant exclusion. Confirmatory configurations prohibited run-level and trial-level fallback and did not substitute an earlier session when the latest session failed eligibility criteria.

We evaluated calibration budgets of 0, 5, 10, 20, and 40 labeled target trials per class. For each participant and repeat, trials in each class of the calibration pool were randomly permuted using a deterministic seed. Each budget used the corresponding prefix of the class-specific ordering, producing nested samples without replacement. Ten calibration draws were used in the full analysis. The held-out test session remained identical across repeats and methods.

## Source cohort and training regimes

For a given target, all source participants came from the same dataset and the target participant was excluded before selection. The primary source cohort contained at most 10 deterministically selected participants, with at most 20 trials per class per source participant. Sampling was class-balanced within participant. A separate sensitivity analysis used every eligible source participant.

We compared three training regimes: a population model trained only on source participants; a target-only model trained only on labeled target calibration trials; and a source-plus-target model trained by pooling source and target calibration trials. At zero target calibration, the source-plus-target condition was an exact duplicate of the population condition and was retained only to anchor a continuous calibration curve. We refer to the third regime as pooled retraining rather than fine-tuning or domain adaptation.

## Decoders

The fixed classical core comprised: (1) channel-wise log variance followed by linear discriminant analysis with automatic covariance shrinkage; (2) regularized common spatial patterns followed by log-power features and shrinkage LDA; and (3) OAS epoch covariance matrices projected to the tangent space at the training-set Riemannian mean, standardized using training data, and classified by L2-regularized logistic regression. Eight CSP components were used in the full-montage analysis, capped by channel count, and three components were used in the common-montage sensitivity. No hyperparameter was selected using target-test outcomes.

## Outcomes

The primary endpoint was ROC-AUC on the held-out latest session. Secondary endpoints were balanced accuracy, accuracy, macro-F1, Brier score, and log loss. Thresholded metrics used a fixed probability threshold of 0.5.

Data efficiency was summarized by normalized area under the calibration curve (AUCC) on the axis `log2(b+1)`, where `b` was the labeled budget per class. The horizon was fixed at 40 trials per class, and AUCC was calculated only for complete curves. Subject-only and source-plus-target AUCC values were not compared across regimes because their minimum budgets differed.

## Statistical analysis

Metric values were first averaged across calibration repeats within participant, method, regime, and budget. Dataset-specific means and 95% confidence intervals were estimated by bootstrapping participants with 2,000 resamples.

At 5 and 10 trials per class, source-plus-target and target-only ROC-AUC were compared within participant and method. We reported paired mean and median differences, participant-bootstrap confidence intervals, two-sided Wilcoxon signed-rank tests, rank-biserial effect sizes, and Holm-adjusted p-values across the six pooled method-by-budget tests. Riemannian and CSP normalized ROC-AUC AUCC were compared within each adaptive regime using the same paired procedure and a separate two-test Holm family. Pooled contrasts were participant-weighted across datasets; dataset-specific contrasts were treated as supportive.

Positive-budget participant summaries were additionally analyzed with a mixed-effects model containing `log2(calibration budget + 1)`, method, regime, their interactions, and dataset as fixed effects. Participant nested within dataset was the grouping factor. A random intercept and budget slope were attempted first, with a documented random-intercept-only fallback for numerical failure or non-convergence. Trial rows and calibration repeats were not treated as independent participants.

## Reproducibility and audit

Every target trial role, calibration sample, source participant/trial selection, condition seed, held-out prediction, and metric was stored in machine-readable audit files. Before aggregation, the software verified group disjointness, nested and balanced calibration membership, target exclusion from source data, exact zero-budget duplication, condition completeness, prediction counts, and metrics recomputed from stored predictions. Result directories were fingerprinted by the full configuration, and run manifests captured package versions, dataset-manifest hashes, source-tree digest, and platform information.
