# BCI Calibration Benchmark

**A leakage-resistant, cross-session benchmark of calibration burden in motor-imagery EEG brain–computer interfaces.**

This repository is the computational foundation for the planned study:

> **The Calibration–Performance Trade-off in Motor-Imagery Brain–Computer Interfaces: A Reproducible Cross-Session Benchmark**

The scientific question is operational rather than architectural:

> How much labeled EEG from a new user is required to improve performance on a later recording session, and how does that relationship vary across decoding methods, datasets, and users?

Version `0.1.0` froze the classical-core protocol before any public-data outcome was examined. Version `0.1.1` validates that the full software/data pipeline runs end to end on real public EEG data (adapter execution, structural validation, benchmark, audit, aggregation, and figure generation). **Neither release contains a claimed public EEG result.** The `0.1.1` real-data pilot is a non-inferential software/data-path validation, not the confirmatory analysis; see [Public-data pilot](#public-data-pilot) below.

## Confirmatory design

The task is binary **left-hand versus right-hand motor imagery**. The confirmatory dataset set contains only MOABB adapters that expose multiple sessions and enough labeled trials for a strict later-session test.

| MOABB dataset | Nominal participants | Sessions | EEG channels | Native sampling | Left/right trials per session after task selection | Confirmatory role |
|---|---:|---:|---:|---:|---:|---|
| `Lee2019_MI` | 54 | 2 | 62 | 1000 Hz | 50 per class | large-cohort anchor |
| `BNCI2014_001` | 9 | 2 | 22 | 250 Hz | 72 per class | canonical BCI Competition IV-2a replication |
| `Zhou2016` | 4 | 3 | 14 | 250 Hz | 50 per class | independent three-session protocol replication |

The nominal total is 67 participants (sum of the "Nominal participants" column above) — the number of subject IDs each dataset publishes, before any structural check runs. This is **not** an eligible or analyzed sample size. The confirmatory full-cohort run applies pre-specified structural and class-count checks (session count, run count, per-class trial minimums, channel montage) to every participant before any decoder is fit; a participant who fails those checks is excluded and recorded, never dropped after outcome inspection. One such exclusion is already known and documented: `Zhou2016` subject 2 fails the per-session trial-count check on the publicly released recording itself (see [`docs/DECISIONS.md`](docs/DECISIONS.md)) and is excluded in `configs/full.yaml` and every sensitivity configuration. The confirmatory full-cohort analysis has not yet been run, so the true structurally eligible count across all three datasets is not yet known; see [Confirmatory readiness](docs/pilot_acceptance.md) for the current pilot-derived expectation.

For `Lee2019_MI`, the adapter is explicitly instantiated with `train_run=True`, `test_run=False`, and `resting_state=False`. This retains the labeled offline phase in both sessions and excludes the unlabeled online-feedback phase.

### Why other large public datasets are not confirmatory in v0.1

- `Cho2017` and `PhysionetMI` were rejected for this protocol because their current MOABB representation does not provide the multi-session structure required for the pre-specified prospective holdout.
- `BNCI2014_004` was rejected because its latest sessions include continuous smiley feedback, whereas the first sessions do not. Holding out the latest session would therefore mix calibration effects with a task/feedback protocol shift.

These exclusions were made before public-data outcomes were run and are recorded in [`docs/DECISIONS.md`](docs/DECISIONS.md) and [`docs/DATASET_SELECTION_RATIONALE.md`](docs/DATASET_SELECTION_RATIONALE.md).

## Primary evaluation protocol

For each target participant:

1. All other eligible participants from the same dataset form the candidate source cohort.
2. All earlier target sessions form the calibration pool.
3. The chronologically latest target session is held out in its entirety and is never used for fitting, selection, normalization, early stopping, or exception handling.
4. Calibration budgets are `0, 5, 10, 20, 40` labeled trials **per class**.
5. Within a repeat, smaller calibration sets are strict subsets of larger sets.
6. Ten calibration draws are used in the full analysis. The underlying test session remains fixed; only calibration membership varies.
7. No run-level or trial-level fallback is allowed in the confirmatory configuration. A participant who cannot satisfy the fixed protocol is excluded with an explicit validation failure rather than assigned a more favorable split.

The primary preprocessing is fixed at 8–30 Hz, 0.5–3.5 s after the MOABB task event, 128 Hz, no baseline correction, and the full available EEG montage within each dataset. A pre-specified `C3/Cz/C4` sensitivity analysis assesses whether conclusions persist on a common sensorimotor montage.

The directional visual cue remains visible for part or all of the analyzed interval in some source protocols. Therefore, this benchmark estimates **cue-based motor-imagery decoding performance**, not a pure neural-intent signal isolated from all cue-related activity. The common sensorimotor-montage sensitivity and explicit limitation language are mandatory.

## Training regimes

- `population`: source participants only, evaluated at zero target calibration.
- `subject`: target calibration trials only, evaluated at positive budgets.
- `source_plus_target`: source data plus target calibration data using pooled retraining. At budget zero, this condition is an exact audited duplicate of `population`.

`source_plus_target` is deliberately described as **pooled retraining**, not as neural-network fine-tuning, meta-learning, or a clinically validated personalization method.

The primary source cohort is capped at 10 non-target participants, with at most 20 trials per class per source participant. This limits computation, equalizes source-participant influence, and prevents the small target calibration set from being numerically overwhelmed by thousands of source trials. Source selection is deterministic, target-disjoint, and independent of target test labels. An all-source sensitivity configuration is provided separately.

## Implemented methods

The primary release uses fixed, auditable pipelines without outcome-driven hyperparameter tuning:

- `logvar_lda`: channel-wise log variance plus shrinkage LDA; transparent sanity baseline.
- `csp_lda`: regularized common spatial patterns plus shrinkage LDA.
- `riemann_lr`: OAS epoch covariance, training-set Riemannian mean, tangent-space projection, standardization, and logistic regression.

An optional Braindecode EEGNet adapter is included behind the `deep` extra but is not enabled in a confirmatory configuration. It must pass a separate convergence, determinism, early-stopping, and compute audit before inclusion in a manuscript.

## Outcomes and statistical unit

The primary endpoint is ROC-AUC. Pre-specified secondary endpoints are balanced accuracy, accuracy, macro-F1, Brier score, and log loss.

The participant—not the trial and not the repeated calibration draw—is the independent inferential unit. Repeats are averaged within participant before bootstrap intervals, paired tests, or mixed-effects modeling.

Data efficiency is summarized by a normalized area under the calibration curve on the fixed axis

\[
x = \log_2(b+1),
\]

where \(b\) is the number of labeled trials per class. AUCC is calculated only when every pre-specified budget through the fixed horizon is present. Incomplete curves remain in audit files but cannot enter AUCC inference.

See [`docs/ANALYSIS_PLAN.md`](docs/ANALYSIS_PLAN.md) and [`docs/STATISTICAL_ANALYSIS.md`](docs/STATISTICAL_ANALYSIS.md).

## Repository layout

```text
.
├── configs/                 # pilot, confirmatory, and sensitivity configurations
├── data/                    # ignored MOABB cache and processed shards
├── docs/                    # protocol, decisions, validation, governance, journal plan
├── figures/                 # repository-level placeholder; run figures live under results/
├── manuscript/              # outline, methods draft, BibTeX
├── requirements/            # environment constraints
├── results/                 # ignored fingerprinted run outputs
├── scripts/                 # thin command-line wrappers
├── src/bci_calibration_benchmark/
└── tests/                   # unit, leakage, integrity, and end-to-end tests
```

## Installation

Python 3.11 and 3.12 are the CI reference versions. MOABB is pinned to `1.5.0` because adapter structure is part of the protocol.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

For the optional EEGNet adapter:

```bash
python -m pip install -e '.[dev,deep]'
```

A Conda environment and a Dockerfile are included. Dataset downloads can be large; review source licenses and local storage before running the public-data workflow.

## Validation before public data

```bash
python scripts/validate_environment.py --config configs/pilot.yaml
pytest
python scripts/run_smoke_test.py --workspace .smoke-work
```

The synthetic smoke test checks deterministic end-to-end execution, split assignments, nested calibration samples, result schemas, prediction counts, exact zero-budget duplication, aggregation, statistical outputs, and figure-source files. It is not evidence about BCI performance.

## Public-data pilot

The pilot is an adapter and compute validation run, not an inferential subset analysis. **Pilot performance numbers must never be reported as scientific study findings**, cited in the manuscript Results, or used to select models, tune hyperparameters, or change participant eligibility.

```bash
python scripts/prepare_data.py --config configs/pilot.yaml
python scripts/validate_data.py --config configs/pilot.yaml
python scripts/run_benchmark.py --config configs/pilot.yaml
python scripts/audit_results.py --config configs/pilot.yaml
python scripts/aggregate_results.py --config configs/pilot.yaml
python scripts/make_figures.py --config configs/pilot.yaml
```

As of `v0.1.1`, this workflow has been executed end to end against real public EEG data for all three confirmatory adapters (`Lee2019_MI`, `BNCI2014_001`, `Zhou2016`) on macOS with Python 3.11 and `moabb==1.5.0`: environment validation, the full test suite (40 tests), the synthetic smoke test, real-data preparation, real-data structural validation, benchmark execution, result audit, aggregation, and figure generation all completed successfully. This demonstrates that the software and data path work end to end on real recordings; it does **not** constitute confirmatory scientific evidence, and no pilot performance figure appears in this repository's user-facing documentation. See [`docs/pilot_acceptance.md`](docs/pilot_acceptance.md) for the full closure record and [`docs/SOFTWARE_VALIDATION_REPORT.md`](docs/SOFTWARE_VALIDATION_REPORT.md) for validation evidence.

Two genuine issues were found and resolved during the real-data pilot, both documented in [`docs/DECISIONS.md`](docs/DECISIONS.md) and traced in [`docs/debugging_log.md`](docs/debugging_log.md):

- A MOABB 1.5.0 session-indexing bug that silently dropped `Lee2019_MI`'s first session for every subject. A guarded, fail-loud workaround restores the intended two-session protocol; it does not change the estimand.
- `Zhou2016` subject 2's publicly released recording is structurally short one required trial block (see [Confirmatory design](#confirmatory-design) above). This was found by pre-outcome structural validation, not by inspecting performance, and the participant is excluded from the pilot, the confirmatory run, and every sensitivity configuration.

The full confirmatory run is permitted only after the pilot acceptance gates in [`docs/PILOT_EXECUTION.md`](docs/PILOT_EXECUTION.md) and the GO decision in [`docs/pilot_acceptance.md`](docs/pilot_acceptance.md) are satisfied.

## Confirmatory and sensitivity runs

```bash
# Confirmatory full-montage analysis
python scripts/prepare_data.py --config configs/full.yaml
python scripts/validate_data.py --config configs/full.yaml
python scripts/run_benchmark.py --config configs/full.yaml
python scripts/audit_results.py --config configs/full.yaml
python scripts/aggregate_results.py --config configs/full.yaml
python scripts/make_figures.py --config configs/full.yaml

# Common C3/Cz/C4 montage sensitivity
python scripts/prepare_data.py --config configs/sensitivity_three_channels.yaml
python scripts/run_benchmark.py --config configs/sensitivity_three_channels.yaml
python scripts/audit_results.py --config configs/sensitivity_three_channels.yaml
python scripts/aggregate_results.py --config configs/sensitivity_three_channels.yaml
python scripts/make_figures.py --config configs/sensitivity_three_channels.yaml

# Source-cohort-size sensitivity
python scripts/run_benchmark.py --config configs/sensitivity_all_sources.yaml
python scripts/audit_results.py --config configs/sensitivity_all_sources.yaml
python scripts/aggregate_results.py --config configs/sensitivity_all_sources.yaml
```

Processed data are keyed by a preprocessing fingerprint, so configurations with identical preprocessing reuse compatible shards without silently overwriting them.

## Auditable outputs

Each run creates a fingerprinted directory under `results/` containing:

- `run_manifest.json`: configuration, software versions, source digest, platform, and processed-data manifest digests.
- `metrics.csv`: one row per dataset × target participant × repeat × method × regime × budget.
- `predictions.csv.gz`: held-out trial predictions with immutable trial identifiers.
- `failures.csv`: explicit condition failures and tracebacks.
- `split_assignments.csv.gz`: every target trial labeled `calibration_pool` or `test`.
- `calibration_assignments.csv.gz`: every selected calibration trial at every positive budget.
- `source_selection.csv`: source participant IDs, sample counts, seeds, and selected-trial digests.
- `source_trial_assignments.csv.gz`: every selected source trial, its label and recording group, and the target for which it was used.
- `result_audit.json`: machine-checked protocol and file-integrity report.
- `summary_subject.csv`: repeat-averaged participant-level outcomes.
- `curve_summary.csv`: participant-bootstrap curve estimates.
- `aucc_subject.csv`: fixed-horizon participant-level AUCC and responsiveness summaries.
- `pairwise_tests.csv`: pre-specified paired contrasts with role-specific Holm adjustment.
- `mixed_effects_coefficients.csv` and `mixed_effects_diagnostics.json`.
- `participant_flow.csv` and `aggregation_manifest.json`.
- `figures/`: PNG, PDF, exact source CSVs, and a checksum manifest.

## Fail-closed safeguards

The code rejects or records failures when:

- the target participant appears in source data;
- calibration and test trials overlap;
- a session/run group appears in both target roles;
- the latest session is invalid and the configuration forbids fallback;
- calibration sets are not nested or do not contain exactly the requested class counts;
- methods do not share the same held-out test trials;
- a processed shard has changed checksum, schema, preprocessing, channel order, sample count, or pinned package version;
- the MOABB adapter no longer exposes the expected number of sessions, runs, channels, or labeled trials;
- a resumed run has partial predictions, duplicate conditions, changed code, changed package versions, or changed dataset manifests;
- an AUCC curve is incomplete at the fixed horizon.

## Current validation status

`v0.1.0` passed the local unit/integration suite and a deterministic synthetic end-to-end run; MOABB and the public EEG archives were not available in that build environment, so real-data adapter execution remained an explicit pilot gate rather than a claimed validation.

`v0.1.1` closes that gate: the full software/data pipeline (environment validation, 40 unit/integration tests, the synthetic smoke test, real-data preparation, real-data structural validation, benchmark execution, result audit, aggregation, and figure generation) has now run successfully end to end on real public EEG data for `Lee2019_MI`, `BNCI2014_001`, and `Zhou2016`. This validates the software and data path. **It does not constitute confirmatory scientific evidence** — the pilot is a bounded adapter/compute check (see [Public-data pilot](#public-data-pilot) above), and the confirmatory full-cohort analysis has not yet been run. See [`docs/VALIDATION.md`](docs/VALIDATION.md), [`docs/SOFTWARE_VALIDATION_REPORT.md`](docs/SOFTWARE_VALIDATION_REPORT.md), and [`docs/pilot_acceptance.md`](docs/pilot_acceptance.md).

## Ethics and data governance

This is secondary analysis of public, de-identified research datasets. The repository does not redistribute raw EEG. Users must comply with each dataset's original license, citation, and governance requirements and must not attempt re-identification. See [`docs/ETHICS_AND_DATA_GOVERNANCE.md`](docs/ETHICS_AND_DATA_GOVERNANCE.md).

## Citation and license

Until a DOI is assigned, cite the software using `CITATION.cff`. Any publication must also cite the original dataset papers, MOABB, MNE-Python, scikit-learn, and the relevant decoding-method references in `manuscript/references.bib`.

Code is released under the BSD 3-Clause License. Dataset files retain their original terms and are not redistributed.
