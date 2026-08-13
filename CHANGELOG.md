# Changelog

## 0.1.1 — 2026-08-12

Real-data pilot validated; ready for confirmatory full-cohort analysis.

- Executed the full software/data pipeline end to end on real public EEG data for `Lee2019_MI`, `BNCI2014_001`, and `Zhou2016`: environment validation, unit/integration tests, the synthetic smoke test, real-data preparation, real-data structural validation, benchmark execution, result audit, aggregation, and figure generation all passed. See `docs/pilot_acceptance.md`.
- Fixed a MOABB 1.5.0 session-indexing bug that silently dropped `Lee2019_MI`'s first session for every subject, with a guarded workaround that fails loudly if MOABB's internal representation changes. Restores the pre-specified two-session protocol; does not change the estimand.
- Documented and configured a structural eligibility exclusion for `Zhou2016` subject 2 (a genuine trial-count shortfall in the publicly released recording, found by pre-outcome structural validation) across the pilot, confirmatory, and both sensitivity configurations.
- Fixed a CSV float round-trip issue (`float_precision="round_trip"`) that could otherwise produce a false-positive audit failure; no effect on any computed result.
- Added regression tests for the Lee2019 workaround, the float round-trip fix, and cross-configuration Zhou2016 eligibility. 40 tests passing (35 at v0.1.0; the real-data pilot fixes brought this to 39, and the cross-configuration eligibility test added while preparing this milestone brought it to 40).
- No public EEG scientific result is claimed in this release; the pilot is a non-inferential software/data-path validation. See `docs/pilot_acceptance.md`.

## 0.1.0 — 2026-08-11

Initial protocol-frozen research release.

- Defines a strict later-session motor-imagery calibration benchmark on `Lee2019_MI`, `BNCI2014_001`, and `Zhou2016`.
- Implements deterministic, nested per-class calibration budgets and target-disjoint source sampling.
- Provides log-variance/LDA, CSP/LDA, and Riemannian tangent-space/logistic-regression pipelines.
- Stores trial-level split, calibration, source-selection, source-trial, prediction, and provenance records.
- Audits the full configured condition grid and recomputes all six metrics from held-out predictions.
- Aggregates at participant level, computes fixed-horizon AUCC, paired bootstrap/Wilcoxon contrasts, Holm adjustment, and mixed-effects diagnostics.
- Includes deterministic synthetic end-to-end validation and tamper-detection tests.

No public EEG outcome is claimed in this release.
