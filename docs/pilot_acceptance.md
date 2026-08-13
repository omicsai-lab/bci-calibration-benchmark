# Pilot acceptance record

This record formally closes the real-data pilot and states whether the
repository is accepted for the confirmatory full-cohort analysis. It is a
go/no-go record, not a scientific results document — it contains no
performance numbers, model rankings, or effect estimates.

## Identification

| Field | Value |
|---|---|
| Date | 2026-08-12 |
| Branch | `james_dev` |
| Base commit | `08280c716b0df7698106f0781e7740c21c215de4` (`08280c7`) |
| Milestone | v0.1.1 — Real-data pilot validated; ready for confirmatory full-cohort analysis |
| Pilot config | `configs/pilot.yaml` |
| Preprocessing fingerprint | `861cc64b9adbc47c` |
| Experiment fingerprint | `2b515a94ee6e8949` |
| Pilot output directory | `results/bci-calibration-pilot-2b515a94ee6e8949` (gitignored, locally reproducible) |

The base commit is the last commit on `james_dev` at the time this record
was written; the v0.1.1 documentation, configuration, and version-metadata
changes described below were prepared on top of it in the same working tree
and are reflected in `git status`/`git diff` at the time of the merge
review, not in a separate commit yet (see the accompanying final report for
this working tree's git status).

## Environment

| Field | Value |
|---|---|
| OS | macOS (`macOS-26.5.2-arm64-arm-64bit`) |
| Python | 3.11.15 |
| MOABB | 1.5.0 |
| MNE-Python | 1.12.1 |
| NumPy | 2.4.6 |
| pandas | 2.3.3 |
| SciPy | 1.17.1 |
| scikit-learn | 1.9.0 |
| statsmodels | 0.14.6 |

Full package list: `python scripts/validate_environment.py --config configs/pilot.yaml`.

## Datasets exercised (real public data)

- `Lee2019_MI` — subjects 1, 2, 3
- `BNCI2014_001` — subjects 1, 2, 3
- `Zhou2016` — subjects 1, 3 (subject 2 excluded; see below)

8 participants total in the pilot cohort.

## Gate results

| Gate | Command | Status |
|---|---|---:|
| Environment validation | `scripts/validate_environment.py --config configs/pilot.yaml` | PASS |
| Unit/integration tests | `pytest` | PASS (39/39 at pilot execution time; 40/40 after this milestone-prep pass added a cross-configuration Zhou2016 eligibility test — see below) |
| Synthetic smoke test | `scripts/run_smoke_test.py --workspace .smoke-work` | PASS |
| Real-data preparation | `scripts/prepare_data.py --config configs/pilot.yaml` | PASS |
| Real-data structural validation | `scripts/validate_data.py --config configs/pilot.yaml` | PASS |
| Benchmark execution | `scripts/run_benchmark.py --config configs/pilot.yaml` | PASS |
| Result-integrity audit | `scripts/audit_results.py --config configs/pilot.yaml` | PASS (`status: ok`, 384/384 conditions, 0 failed) |
| Aggregation | `scripts/aggregate_results.py --config configs/pilot.yaml` | PASS |
| Figure generation | `scripts/make_figures.py --config configs/pilot.yaml` | PASS |

The real-data gates above (preparation through figure generation) were executed once, against the 39-test-passing codebase that fixed the Lee2019 and CSV round-trip issues; they do not need real-data re-execution as a result of the milestone-preparation changes in this record, because `configs/pilot.yaml` itself was not modified during milestone preparation (only `configs/full.yaml` and the sensitivity configs changed, and only to add the `Zhou2016` subject-2 exclusion — see below). `pytest`, environment validation, and the smoke test were re-run after milestone preparation and confirmed 40/40 passing.

## Documented deviations and issues

All three are traced in detail in [`docs/debugging_log.md`](debugging_log.md)
and framed as scientific/reproducibility decisions in
[`docs/DECISIONS.md`](DECISIONS.md).

1. **Lee2019_MI / MOABB 1.5.0 session-indexing workaround.** MOABB 1.5.0's
   `Lee2019` dataset silently dropped the first of two sessions for every
   subject due to an internal 0-indexed/1-indexed key mismatch between its
   session dictionary and `BaseDataset`'s session filter. A guarded
   workaround in `datasets.py` neutralizes the filter for this dataset only,
   asserting the exact known-buggy state before acting so it fails loudly
   (`RuntimeError`) if MOABB's internal representation ever changes. This
   restores the pre-specified two-session protocol; it does not change the
   estimand, and regression tests cover it.
2. **Zhou2016 subject 2 structural exclusion.** This subject's publicly
   released session-1/run-1 recording contains only 20 trials/class instead
   of the protocol's 25/run — a genuine acquisition-time shortfall in the
   released data, verified directly against raw event counts. The
   exclusion happened during structural validation, strictly before any
   model was fit or any performance number existed for this subject. It is
   not performance-based subject removal. Subject 2 is now excluded, by
   explicit configuration (`exclude_subjects: [2]`), from
   `configs/pilot.yaml`, `configs/full.yaml`,
   `configs/sensitivity_three_channels.yaml`, and
   `configs/sensitivity_all_sources.yaml`.
3. **CSV float round-trip in the audit.** `pandas.read_csv`'s default float
   parser is not guaranteed bit-exact; a 1-ULP parsing gap was amplified by
   `log_loss`'s probability clipping into a spurious audit mismatch. Fixed
   by reading with `float_precision="round_trip"` wherever the audit
   recomputes and compares stored metrics. This is an audit-reproducibility
   fix with no effect on any computed metric.

## Non-inferential statement

The pilot cohort (8 participants: 3 `Lee2019_MI`, 3 `BNCI2014_001`, 2
`Zhou2016`) and every number the pilot produced are a **software and
data-path validation only**. No pilot performance figure, model comparison,
or statistical estimate from this pilot run has been or may be reported as
a scientific finding, cited in the manuscript Results, or used to select
models, tune hyperparameters, or decide participant eligibility. Subject
eligibility decisions in this record were made solely on structural
grounds, before any outcome was computed for the affected participant.

## Confirmatory readiness

The confirmatory full-cohort run (`configs/full.yaml`) and both sensitivity
configurations (`configs/sensitivity_three_channels.yaml`,
`configs/sensitivity_all_sources.yaml`) have **not** been executed. Their
nominal Zhou2016 cohort now excludes subject 2 by the same configuration
mechanism validated in the pilot; no other participant across any of the
three datasets has yet been structurally validated beyond the pilot's 8.
The maximum structurally eligible cohort therefore cannot exceed
66 participants (the 67 nominal participants across `Lee2019_MI` (54),
`BNCI2014_001` (9), and `Zhou2016` (4), minus the one documented Zhou2016
exclusion) and may be smaller once every remaining participant's session,
run, channel, and per-class trial-count structure is checked during the
full run. This is a structural ceiling, not a prediction of the analyzed
sample size.

## Decision

**GO for confirmatory full-cohort analysis, subject to the documented
Zhou2016 eligibility rule and the frozen confirmatory configuration.**

This decision covers running `configs/full.yaml` and the sensitivity
configurations as currently checked in. It does not cover merging, tagging,
or releasing this milestone, which remain separate, explicitly authorized
actions.
