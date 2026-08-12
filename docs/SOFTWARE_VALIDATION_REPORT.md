# Software validation report — v0.1.0

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
