# Software validation report

This report is append-only across releases: earlier validation runs are
preserved rather than overwritten, so the record of what was and was not
checked at each version stays visible.

- [Original software validation — v0.1.0](#original-software-validation--v010) (2026-08-11, synthetic-only; MOABB unavailable in that build environment)
- [Real-data pilot validation — v0.1.1](#real-data-pilot-validation--v011-2026-08-12) (2026-08-12, real public EEG data)

---

## Original software validation — v0.1.0

**Validation date:** 2026-08-11  
**Scope:** software and protocol execution only; no public EEG result

## Validation environment

- Operating system: Linux x86_64
- Python: 3.13.5
- NumPy: 2.3.5
- pandas: 2.2.3
- SciPy: 1.17.0
- scikit-learn: 1.8.0
- MNE-Python: 1.11.0
- statsmodels: 0.14.6
- MOABB: not installed in this build environment

Python 3.11 and 3.12 remain the reference CI versions. The local Python 3.13 run is an additional compatibility check, not a substitute for remote CI.

## Unit and integration tests

Command:

```bash
PYTHONPATH=src pytest --cov=bci_calibration_benchmark --cov-report=term-missing:skip-covered
```

Result:

- 35 tests passed;
- 0 tests failed;
- total statement/branch coverage reported by `coverage.py`: 60%;
- public-data adapter/download paths and the optional deep-learning path were intentionally not executed and account for much of the uncovered code.

The suite includes explicit tamper-detection tests for modified metric values and modified source-trial assignments.

## Deterministic synthetic end-to-end validation

Command:

```bash
PYTHONPATH=src python scripts/run_smoke_test.py \
  --workspace /mnt/data/bci-calibration-smoke-final
```

Two independently created runs were compared after removing only wall-clock timing columns.

| Check | Result |
|---|---:|
| Successful condition rows | 108 / 108 |
| Held-out prediction rows | 1,296 |
| Metric conditions recomputed from predictions | 108 / 108 |
| Split-assignment rows | 144 |
| Calibration-assignment rows | 96 |
| Source-selection rows | 6 |
| Source-trial assignment rows | 144 |
| Deterministic metrics equality | exact pass |
| Result-integrity audit | pass in both runs |
| Shuffled-label permutations | 16 |
| Mean shuffled-label ROC-AUC | 0.5381944444 |

The minimum and maximum shuffled-label ROC-AUC values were 0.0 and 1.0 because the synthetic held-out sample is deliberately tiny; the pre-specified acceptance criterion applies to the mean across permutations, not to each individual permutation.

## Packaging checks

- `python -m compileall -q src scripts tests`: passed.
- Strict loading/validation of all four YAML configurations: passed.
- `python -m pip wheel --no-deps --no-build-isolation .`: passed.
- Wheel produced during validation: `bci_calibration_benchmark-0.1.0-py3-none-any.whl`.

`ruff` and the `build` front end were not present locally and could not be downloaded because this build environment has no package-network access. The repository CI installs the declared development dependencies and runs both `ruff check .` and `python -m build`; remote CI completion remains an unchecked release gate.

## Scientific safeguards exercised

The synthetic validation exercised:

- fixed latest-session holdout;
- target/source participant disjointness;
- group-disjoint target roles;
- nested, class-balanced calibration samples;
- deterministic source-participant and source-trial sampling;
- exact zero-budget duplication;
- prediction-derived recomputation of ROC-AUC, balanced accuracy, accuracy, macro-F1, Brier score, and log loss;
- source-selection count and SHA-256 digest reconciliation;
- complete configured condition-grid accounting;
- participant-level repeat aggregation;
- fixed-horizon AUCC;
- paired inferential tables and multiplicity-family assignment;
- figure generation from traceable source CSVs.

## Explicitly unvalidated in this environment

The following remain mandatory public-data pilot gates:

- installation and local execution of MOABB 1.5.0;
- download and licensing checks for `Lee2019_MI`, `BNCI2014_001`, and `Zhou2016`;
- empirical verification of adapter session/run/channel/trial structures;
- manual inspection of event timing and channel naming;
- full-cohort runtime, memory, and storage requirements;
- all real-data metrics, statistical estimates, and scientific conclusions.

No synthetic number in this report may be quoted as evidence about human BCI performance.

---

## Real-data pilot validation — v0.1.1 (2026-08-12)

**Validation date:** 2026-08-12
**Scope:** software and data-path execution on real public EEG data, using
the bounded pilot cohort in `configs/pilot.yaml`. This closes the "explicitly
unvalidated" gates listed above for `v0.1.0`. **It is not a confirmatory
scientific result.** See [`docs/pilot_acceptance.md`](pilot_acceptance.md)
for the formal closure record and go/no-go decision, and
[`docs/DECISIONS.md`](DECISIONS.md) for the scientific/reproducibility
decisions this run required.

### Validation environment

- Operating system: macOS (`macOS-26.5.2-arm64-arm-64bit`)
- Python: 3.11.15
- NumPy: 2.4.6
- pandas: 2.3.3
- SciPy: 1.17.1
- scikit-learn: 1.9.0
- MNE-Python: 1.12.1
- statsmodels: 0.14.6
- MOABB: 1.5.0

### Command sequence and results

| Step | Command | Result |
|---|---|---:|
| Environment validation | `scripts/validate_environment.py --config configs/pilot.yaml` | pass |
| Unit/integration tests | `pytest` | 39 / 39 passed (a 40th regression test, covering cross-configuration `Zhou2016` subject-2 eligibility, was added while preparing the v0.1.1 milestone and also passes; it does not require real data) |
| Synthetic smoke test | `scripts/run_smoke_test.py --workspace .smoke-work` | pass |
| Real-data preparation | `scripts/prepare_data.py --config configs/pilot.yaml` | pass |
| Real-data structural validation | `scripts/validate_data.py --config configs/pilot.yaml` | pass |
| Benchmark execution | `scripts/run_benchmark.py --config configs/pilot.yaml` | pass |
| Result-integrity audit | `scripts/audit_results.py --config configs/pilot.yaml` | pass |
| Aggregation | `scripts/aggregate_results.py --config configs/pilot.yaml` | pass |
| Figure generation | `scripts/make_figures.py --config configs/pilot.yaml` | pass |

Datasets exercised, real public data: `Lee2019_MI`, `BNCI2014_001`,
`Zhou2016` — see `docs/pilot_acceptance.md` for the exact pilot cohort
(participant counts and the one documented structural exclusion).

### Issues found and resolved during this validation

Full root-cause traces, evidence, and verification commands are in
[`docs/debugging_log.md`](debugging_log.md); scientific-decision framing is
in [`docs/DECISIONS.md`](DECISIONS.md). Summary:

1. **MOABB 1.5.0 `Lee2019` session-indexing bug.** `Lee2019`'s internal
   per-subject session dictionary uses 0-indexed string keys (`"0"`, `"1"`)
   while `BaseDataset.get_data()` filters against the 1-indexed
   `_selected_sessions` the adapter was constructed with, so only session
   `"1"` survived and the first session was silently dropped for every
   subject. Fixed with a guarded, version-checked workaround in
   `datasets.py` that fails loudly if the underlying MOABB behavior
   changes. Restores the intended two-session design; does not change the
   estimand.
2. **`Zhou2016` subject 2 structural shortfall.** The publicly released
   session-1/run-1 recording contains 20 trials/class instead of the
   protocol's 25/run — a genuine acquisition-time gap in the released data,
   confirmed directly against raw BIDS event counts, not a software defect.
   Subject 2 is excluded from the pilot and from every confirmatory/
   sensitivity configuration, based on pre-outcome structural validation
   only.
3. **CSV float round-trip in the audit.** Pandas' default float CSV parser
   is not guaranteed bit-exact; a 1-ULP parsing gap, amplified by
   `log_loss`'s probability clipping, produced a spurious audit mismatch.
   Fixed by reading with `float_precision="round_trip"` wherever the audit
   recomputes and compares metrics. This is an audit/reproducibility fix
   with no effect on any computed result.

### Scientific safeguards exercised on real data

In addition to everything exercised synthetically in `v0.1.0` (listed
above), this run additionally exercised, on real recordings:

- real MOABB adapter execution, download, and caching for all three
  confirmatory datasets;
- empirical session/run/channel/trial structural validation against the
  pinned `DATASET_EXPECTATIONS` (including a genuine structural failure
  correctly caught and excluded, not silently passed);
- real-data checksum-verified processed-shard manifests and provenance;
- full pipeline execution (CSP, Riemannian tangent-space, and log-variance
  pipelines) on real EEG epochs through fit, predict, metric computation,
  audit recomputation, aggregation, and figure generation.

### Explicitly still unvalidated

- the confirmatory full-cohort run (`configs/full.yaml`) and both
  sensitivity configurations have not been executed;
- structural eligibility has only been empirically checked for the pilot's
  8 participants (3 `Lee2019_MI`, 3 `BNCI2014_001`, 2 `Zhou2016`), not for
  the remaining nominal participants in each dataset;
- full-cohort runtime, memory, and storage requirements;
- all real-data metrics, statistical estimates, and scientific conclusions.

No pilot number in this report, or elsewhere in this repository, may be
quoted as evidence about human BCI performance.
