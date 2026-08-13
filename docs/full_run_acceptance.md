# Confirmatory full-cohort run acceptance record

This record formally closes execution of the confirmatory full-cohort
analysis. It is a closure/provenance record, not a results document —
**scientific interpretation of the numbers below is intentionally deferred**
to a separate task and does not appear here.

## Identification

| Field | Value |
|---|---|
| Date | 2026-08-13 |
| Branch | `full_analysis` |
| Run code commit | `750d87b8d877357b2907e0b61a66fca46cbe76b9` (`750d87b`) |
| Config | `configs/full.yaml` |
| Preprocessing fingerprint | `861cc64b9adbc47c` |
| Experiment fingerprint | `3fb8efe7e617b0c1` |
| Output directory | `results/bci-calibration-full-v1-3fb8efe7e617b0c1/` (gitignored, locally reproducible) |
| Environment snapshot | `results/full_run_environment.txt` (`pip freeze`, frozen at run time) |

## Environment

Python 3.11.15, MOABB 1.5.0, MNE-Python 1.12.1, NumPy 2.4.6, pandas 2.3.3,
scikit-learn 1.9.0, SciPy 1.17.1, statsmodels 0.14.6, macOS
(`macOS-26.5.2-arm64-arm-64bit`). Full pinned dependency list:
`results/full_run_environment.txt`.

## Confirmatory cohort

| Dataset | Nominal | Excluded | Structurally validated |
|---|---:|---|---:|
| Lee2019_MI | 54 | none | 54 |
| BNCI2014_001 | 9 | none | 9 |
| Zhou2016 | 4 | subjects 2, 4 | 2 |
| **Total** | **67** | | **65** |

### Exclusions and reasons

Both exclusions are structural (pre-outcome), verified directly against raw
BIDS event counts, and unrelated to model performance. Full evidence and
reasoning: [`docs/DECISIONS.md`](DECISIONS.md) ("Zhou2016 subject 2
structural exclusion", "Zhou2016 subject 4 structural exclusion").

- **Zhou2016 subject 2:** session 1, run 1 contains 20 trials/class instead
  of the protocol's 25/run. Known since the v0.1.1 pilot; applied to
  `configs/pilot.yaml` (explicit subject list) and, as of this run, to
  `configs/full.yaml`, `configs/sensitivity_three_channels.yaml`, and
  `configs/sensitivity_all_sources.yaml` (`exclude_subjects: [2, 4]`).
- **Zhou2016 subject 4:** session 0, run 0 contains 20 trials/class instead
  of the protocol's 25/run (recorded duration 726.0 s vs. 840-869 s for
  this subject's other runs). Discovered for the first time during this
  confirmatory run (`prepare_data.py --config configs/full.yaml`), inside
  `validate_subject_structure`, strictly before any split, model fit, or
  prediction existed for this subject — i.e. before any outcome or model
  result existed for this subject. No model performance was consulted in
  making this exclusion. Reported and confirmed before the config change
  was applied, then used identically to the subject-2 exclusion.

## Gate results

| Gate | Command | Status |
|---|---|---:|
| Environment validation | `scripts/validate_environment.py --config configs/full.yaml` | PASS |
| Data preparation | `scripts/prepare_data.py --config configs/full.yaml` | PASS (after one network-transient retry and the subject-4 exclusion above) |
| Structural validation | `scripts/validate_data.py --config configs/full.yaml` | PASS — 65/65 structurally validated participants |
| Benchmark | `scripts/run_benchmark.py --config configs/full.yaml` | PASS — **19,500 / 19,500 conditions completed, 0 failed** |
| Result-integrity audit | `scripts/audit_results.py --config configs/full.yaml` | PASS — `status: ok`, 19,500/19,500 metric conditions recomputed from stored predictions and matched exactly, **2,068,800 prediction rows** |
| Aggregation | `scripts/aggregate_results.py --config configs/full.yaml` | PASS |
| Figure generation | `scripts/make_figures.py --config configs/full.yaml` | PASS |

## Run integrity summary

- Configured conditions: 19,500 (65 participants × 10 repeats × 3 methods × 10 conditions/repeat)
- Completed: 19,500 — Failed: 0
- Prediction rows: 2,068,800
- Curve completeness: 390/390 AUCC rows `curve_complete: True`
- Participant flow: 65/65 attempted participants had at least one success and zero failures, across all three datasets (`participant_flow.csv`)

## Deferred

Scientific interpretation, claims, manuscript Results/Discussion text, and
any performance-based judgment are explicitly out of scope for this record
and have not been made. See the separate results/artifact-inventory report
for the factual (non-interpretive) numerical outputs of this run.

## Decision

**READY FOR SCIENTIFIC INTERPRETATION**, subject to the structural
eligibility rule recorded above. This record closes execution only; it does
not constitute or authorize a scientific conclusion.
