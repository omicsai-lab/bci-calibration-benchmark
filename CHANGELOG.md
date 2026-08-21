# Changelog

## 1.0.0 — 2026-08-21

First manuscript-associated archival software release. Closes execution of
the confirmatory full-cohort analysis, both pre-specified sensitivity
analyses, and a reviewer-motivated post-confirmatory robustness program.
No public-EEG scientific conclusion beyond the conservative summary in
`README.md` is claimed by this changelog entry.

- **Confirmatory full-cohort analysis complete.** `configs/full.yaml`:
  19,500/19,500 conditions, 0 failures, 2,068,800 held-out predictions,
  result-integrity audit `PASS`, on the final eligible cohort of **N = 65**
  (`Lee2019_MI` 54, `BNCI2014_001` 9, `Zhou2016` 2). Final N reflects two
  pre-outcome structural exclusions in `Zhou2016` (subjects 2 and 4, each
  failing the per-session trial-count check on the publicly released
  recordings — found by structural validation before any decoder was fit,
  never by performance). See `docs/full_run_acceptance.md` and
  `docs/DECISIONS.md`.
- **Both pre-specified sensitivity analyses complete.** Common `C3/Cz/C4`
  montage and all-eligible-source-cohort sensitivities, each
  19,500/19,500 conditions, audit `PASS`, on the identical 65-participant
  cohort. See `docs/sensitivity_run_acceptance.md`.
- **Publication artifacts generated.** Figures, tables, and traceable
  source-data CSVs for the confirmatory/sensitivity comparison under
  `manuscript/artifacts/full_analysis_publication/` and
  `manuscript/artifacts/sensitivity_analysis/`.
- **Post-confirmatory training-only Euclidean Alignment robustness**
  (reviewer-motivated, performed after the above results were on record;
  never pre-specified). `configs/sensitivity_ea_training_only.yaml`:
  15,600/15,600 conditions, 0 failures, 1,655,040 held-out predictions,
  result-integrity audit `PASS`. Reuses the confirmatory run's exact
  target-split, calibration, and source-selection assignments rather than
  drawing new random assignments, verified before any model was fit by an
  independent, fail-closed regeneration-equality check (`--assignment-source`).
  See `docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md` and
  `docs/post_confirmatory_robustness_acceptance.md`.
- **Without-`Zhou2016` pooled re-aggregation** (N=63), recomputing the same
  pooled contrasts with identical statistical machinery, as a
  post-confirmatory robustness check. Does not alter the primary N=65
  analysis.
- **Random-intercept-only mixed-model robustness**: the same 1,560
  observations and fixed-effects formula as the primary mixed model,
  fit with a random-intercept-only structure and reported side by side
  with (not replacing) the primary random-intercept-and-slope model.
- **Descriptive fraction-benefiting analysis**: participant-level
  `n_positive`/`n_zero`/`n_negative`/`fraction_positive` summary of
  population-data benefit by method and budget; no p-values.
- **Test suite**: 60 unit/integration/leakage-regression tests passing
  (up from 40 at `v0.1.1`), including new Euclidean Alignment leakage-
  boundary, determinism, and assignment-reuse-drift-detection tests.
- **Audit/provenance**: every analysis above closes with a machine-checked
  result-integrity audit reporting `status: "ok"`, and the Euclidean
  Alignment run additionally records source/target alignment-reference
  provenance and the primary-assignment-reuse equality-gate result.
- Software version bumped to `1.0.0` across `pyproject.toml`,
  `src/bci_calibration_benchmark/__init__.py`, and `CITATION.cff`. No
  scientific config fingerprint, calibration budget, participant
  eligibility rule, or model hyperparameter changed as part of this
  release-preparation work.
- This release is prepared for a manuscript **in preparation/submission
  preparation**; it does not claim manuscript acceptance or publication.

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
