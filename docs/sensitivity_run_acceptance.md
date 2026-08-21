# Sensitivity analysis run acceptance record

This record formally closes execution of the two prespecified sensitivity
analyses. It is a closure/provenance record, not a results document —
**scientific interpretation of the numbers is intentionally deferred** to a
separate task and does not appear here. The factual, non-interpretive
comparison against the primary confirmatory analysis is in
`manuscript/artifacts/sensitivity_analysis/sensitivity_comparison.md`.

## Common identification

| Field | Value |
|---|---|
| Branch | `sensitivity_analysis` |
| Run code commit | `18834b3c31236f49fe069d83557cadf67e3c7b24` (`18834b3`), working tree dirty at run start (contained the not-yet-committed `split.repeats` correction, the `validate_dataset()` JSON-normalization fix, and their regression tests — see "Deviations" below) |
| Environment | Python 3.11.15, MOABB 1.5.0, MNE-Python 1.12.1, NumPy 2.4.6, pandas 2.3.3, scikit-learn 1.9.0, SciPy 1.17.1, statsmodels 0.14.6, macOS (`macOS-26.5.2-arm64-arm-64bit`) — identical package versions to the primary run's `results/full_run_environment.txt`, confirmed via `validate_environment.py` for both sensitivity configs. No separate per-sensitivity `pip freeze` snapshot was captured (not part of the prescribed script sequence for this task). |
| Confirmatory cohort (both analyses) | Lee2019_MI 54, BNCI2014_001 9, Zhou2016 2 (subjects 2, 4 structurally excluded) — **identical to the primary confirmatory analysis**; `participant_flow.csv` is byte-identical across all three run directories |

## Three-channel sensitivity (`configs/sensitivity_three_channels.yaml`)

| Field | Value |
|---|---|
| Date | 2026-08-16 |
| Config | `configs/sensitivity_three_channels.yaml` |
| Preprocessing fingerprint | `ea325577448eac83` |
| Experiment fingerprint | `1fcb3f9ba9823bb1` |
| Output directory | `results/bci-calibration-three-channels-1fcb3f9ba9823bb1/` (gitignored, locally reproducible) |
| Conditions completed / failed | 19,500 / 0 |
| Prediction rows | 2,068,800 |
| Audit result | `status: ok`, 19,500/19,500 metric conditions recomputed from stored predictions and matched exactly |
| Aggregation result | PASS — `curve_summary.csv`, `aucc_subject.csv`, `pairwise_tests.csv`, `mixed_effects_coefficients.csv`, `summary_subject.csv`, `participant_flow.csv` all written |
| Figure-generation result | PASS — 55 figure/source-data files under `figures/` |
| Runtime | `prepare_data.py` reused already-processed data (fast); `run_benchmark.py` started 2026-08-17T00:58:06.18Z, finished 2026-08-17T01:07:17Z (~9m 11s) |

### Deviations / warnings

- **Gate A stop (resolved before this run):** initial static comparison
  found `configs/sensitivity_all_sources.yaml` had `split.repeats: 5`
  instead of the frozen protocol's `10`. Execution was halted before either
  sensitivity analysis ran. Corrected to `10` (see "All-source sensitivity"
  below) — see `docs/DECISIONS.md`, "`sensitivity_all_sources.yaml` repeats
  misconfiguration". This did not affect the three-channel config, which
  already used `split.repeats: 10`.
- **`validate_data.py` failure and fix (resolved before benchmark
  execution):** the first `validate_data.py` run against this config raised
  `ValueError: Preprocessing payload mismatch for Lee2019_MI`. Root cause:
  `validate_dataset()` compared the in-memory config's `preprocessing`
  dataclass payload (where `channels` is a `tuple`) directly against the
  on-disk JSON manifest's payload (where `channels` deserializes as a
  `list`) — `[...] != (...)` in Python even for the same values. Confirmed
  this was an engineering/type-representation bug, not a real preprocessing
  mismatch (the prepared data's channel montage was independently verified
  correct: `X.shape == (200, 3, 384)` for subject 1). Fixed in
  `src/bci_calibration_benchmark/datasets.py::validate_dataset` by
  normalizing the expected payload through JSON before comparison. No
  scientific setting, tolerance, or eligibility rule was changed. Full
  detail: `docs/debugging_log.md`, item 6. `run_benchmark.py` was not
  executed until after this fix and a clean `validate_data.py` pass.
  `prepare_data.py` was not re-run — the already-prepared data (from the
  first attempt) was reused and confirmed valid.
- No other deviations or warnings.

## All-source sensitivity (`configs/sensitivity_all_sources.yaml`)

| Field | Value |
|---|---|
| Date | 2026-08-16 to 2026-08-17 |
| Config | `configs/sensitivity_all_sources.yaml` |
| Preprocessing fingerprint | `861cc64b9adbc47c` (identical to the primary run — `channels: null` in both) |
| Experiment fingerprint | `e86ca10985667aec` |
| Output directory | `results/bci-calibration-all-sources-sensitivity-e86ca10985667aec/` (gitignored, locally reproducible) |
| Conditions completed / failed | 19,500 / 0 |
| Prediction rows | 2,068,800 |
| Audit result | `status: ok`, 19,500/19,500 metric conditions recomputed from stored predictions and matched exactly |
| Aggregation result | PASS — same six aggregate outputs as the three-channel run, all written |
| Figure-generation result | PASS — figures under `figures/` |
| Runtime | `prepare_data.py` reused the primary run's already-processed data (`data/processed/861cc64b9adbc47c/`, same fingerprint) almost instantly; `run_benchmark.py` started 2026-08-17T01:11:06.64Z, finished 2026-08-17T09:18:41Z (~8h 7m), substantially longer than the primary (~1h 56m) and three-channel (~9m) runs, as expected for an uncapped source cohort |

### Deviations / warnings

- **Pre-execution protocol correction:** `configs/sensitivity_all_sources.yaml`
  originally specified `split.repeats: 5`. This was found during Gate A
  static preflight, before any sensitivity benchmark, prediction, metric,
  or outcome existed for this config, and was corrected to `10` (the frozen
  protocol value, matching `configs/full.yaml` and
  `configs/sensitivity_three_channels.yaml`) prior to running
  `run_benchmark.py`. A regression test
  (`tests/test_config.py::test_confirmatory_and_sensitivity_configs_use_ten_nested_calibration_repeats`)
  now prevents this from silently recurring. Full detail:
  `docs/DECISIONS.md`, "2026-08-15 — `sensitivity_all_sources.yaml` repeats
  misconfiguration".
- `resume: true` was preserved; the source-cohort definition
  (`source.max_subjects: null`) was not altered to reduce runtime.
- `source_selection_rows` (2,936) and `source_trial_assignment_rows`
  (117,440) are substantially larger than the three-channel run's (614 and
  24,560 respectively) and the primary run's, confirming the uncapped
  source-cohort design took effect as intended.
- No other deviations or warnings.

## Gate results (both analyses)

| Gate | Three-channel | All-source |
|---|---:|---:|
| Environment validation | PASS | PASS |
| Data preparation | PASS | PASS |
| Structural validation | PASS (after the `validate_dataset()` fix above) | PASS |
| Benchmark | PASS — 19,500/19,500, 0 failed | PASS — 19,500/19,500, 0 failed |
| Result-integrity audit | PASS — `status: ok` | PASS — `status: ok` |
| Aggregation | PASS | PASS |
| Figure generation | PASS | PASS |

## Deferred

Scientific interpretation, manuscript Results/Discussion text, and any
performance-based judgment about whether the primary findings hold are
explicitly out of scope for this record. See
`manuscript/artifacts/sensitivity_analysis/sensitivity_comparison.md` for
the factual (non-interpretive) comparison, including the notable
direction-reversal and statistical-support findings that must not be
hidden (H3 subject-only regime reverses under three-channel; H3
source-plus-target regime reverses, significantly, under all-source).

## Decision

**READY FOR SCIENTIFIC REVIEW.** Both prespecified sensitivity analyses
completed with 0 failures, `status: ok` audits, and the identical 65-
participant cohort as the primary confirmatory analysis. This record closes
execution only; it does not constitute or authorize a scientific conclusion
about whether the primary findings are supported.
