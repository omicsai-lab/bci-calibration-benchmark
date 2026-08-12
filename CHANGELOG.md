# Changelog

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
