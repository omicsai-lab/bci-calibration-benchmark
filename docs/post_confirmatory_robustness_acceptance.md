# Post-confirmatory robustness — implementation and execution acceptance record

This record closes implementation and execution of the post-confirmatory
robustness package authorized in
`docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md` (originally written
specification-only, then approved for implementation subject to five
overriding human decisions — see that file's status header). It is a
closure/provenance record, matching the style of
`docs/sensitivity_run_acceptance.md`: **scientific interpretation is
intentionally limited to the factual comparisons already present in
`manuscript/artifacts/post_confirmatory_robustness/summary.md`**; broader
manuscript integration is out of scope for this round.

## Classification of every analysis (per spec section 7)

| Analysis | Classification |
|---|---|
| Primary full analysis (`configs/full.yaml`) | Confirmatory (unchanged, unmodified by this round) |
| Three-channel / all-source sensitivities | Prespecified sensitivities (unchanged, unmodified by this round) |
| Euclidean Alignment (EA) sensitivity | **Post-confirmatory exploratory robustness** |
| Without-Zhou pooled re-aggregation | **Post-confirmatory robustness** |
| Random-intercept-only mixed model | **Model-form robustness** |
| Fraction-benefiting analysis | **Descriptive exploratory summary** (no p-values) |

**This entire package is reviewer-motivated and post-confirmatory.** It was
initiated by a reviewer-style critique identifying a missing comparator
(distribution alignment before source-plus-target pooling), not by
anything in the frozen `docs/ANALYSIS_PLAN.md`. No item above is, or may
ever be described as, prespecified or confirmatory, regardless of its
result.

## Human decisions that overrode the original specification draft

Recorded here for traceability (full text in
`POST_CONFIRMATORY_ROBUSTNESS_SPEC.md`'s status header):

1. Literal, unnormalized He-Wu covariance `R = mean_i(X_i X_i^T)` — **not**
   the `/n_samples`-normalized variant the original spec draft proposed.
2. Assignment reuse via a runtime/CLI argument
   (`bci-calibration run --assignment-source <primary_output_dir>`), not a
   fingerprinted config field.
3. Two separate alignment-provenance files
   (`source_alignment_provenance.csv.gz`, `target_alignment_provenance.csv.gz`),
   not one combined scope-based table.
4. No mixed-effects model fit for the EA run; EA inference limited to the
   H2-analog paired contrast (budgets 5/10) plus descriptive trajectories
   (budgets 20/40).
5. Fraction-benefiting schema: `n_positive`/`n_zero`/`n_negative`/
   `fraction_positive` per method × budget × scope, ties never folded into
   "negative," no p-values.

All five were implemented exactly as specified; see "Deviations" below for
the two implementation-time corrections found in addition to these five
decisions.

## Environment and code state

| Field | Value |
|---|---|
| Branch | `alignment_sensitivity` |
| Base commit | `4369714e0dfef571bc0144c6e8e38aecea8128bb` (`4369714`) |
| Working tree | **dirty** at both implementation and run time — this entire round's changes (below) were not committed, per instruction not to commit/push |
| Python | 3.11.15 |
| Package versions | MOABB 1.5.0, MNE-Python 1.12.1, NumPy 2.4.6, pandas 2.3.3, scikit-learn 1.9.0, SciPy 1.17.1, statsmodels 0.14.6 — **identical** to the primary run's recorded environment (`results/full_run_environment.txt`, confirmed via `bci-calibration environment`) |
| Platform | `macOS-26.5.2-arm64-arm-64bit` |
| Lint | `ruff check .` — all checks passed |
| Tests | `pytest` — 60/60 passed (15 new in `tests/test_alignment.py`, 2 new in `tests/test_config.py`) |

### Files changed (uncommitted, working tree)

**Modified** (all additive; verified byte-identical `experiment_fingerprint`
for every pre-existing config — see "Deviation 1" below):
`src/bci_calibration_benchmark/cli.py`,
`src/bci_calibration_benchmark/config.py`, `tests/test_config.py`.

**New**:
`src/bci_calibration_benchmark/alignment.py`,
`src/bci_calibration_benchmark/assignment_reuse.py`,
`src/bci_calibration_benchmark/ea_runner.py`,
`src/bci_calibration_benchmark/ea_validation.py`,
`src/bci_calibration_benchmark/ea_aggregate.py`,
`src/bci_calibration_benchmark/ea_plotting.py`,
`configs/sensitivity_ea_training_only.yaml`,
`scripts/post_confirmatory_robustness.py`,
`scripts/build_ea_vs_primary_comparison.py`,
`tests/test_alignment.py`,
`docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md` (from the prior specification
round), `manuscript/artifacts/post_confirmatory_robustness/` (this
package), this file.

**Not modified, not touched by any file operation**:
`src/bci_calibration_benchmark/runner.py`,
`src/bci_calibration_benchmark/validation.py`,
`src/bci_calibration_benchmark/statistics.py`,
`src/bci_calibration_benchmark/riemann.py`, and every file inside
`results/bci-calibration-full-v1-3fb8efe7e617b0c1/`,
`results/bci-calibration-three-channels-1fcb3f9ba9823bb1/`, and
`results/bci-calibration-all-sources-sensitivity-e86ca10985667aec/`. This
was a design goal (spec section 3, "smallest generic implementation") and
is directly checkable: `git status`/`git diff` touch no file under
`results/` (gitignored and unaffected) and no primary/sensitivity-path
module.

## Assignment-source fingerprint and digests

| Field | Value |
|---|---|
| Primary output directory reused | `results/bci-calibration-full-v1-3fb8efe7e617b0c1/` |
| Primary experiment fingerprint | `3fb8efe7e617b0c1` |
| Primary run code commit | `750d87b8d877357b2907e0b61a66fca46cbe76b9` |
| `split_assignments.csv.gz` SHA-256 | `f0c2f018d8dc77ca8cc29750a9ccd97db9f5fe0126aac96cb4457530f055e78e` |
| `calibration_assignments.csv.gz` SHA-256 | `8a57f9776e0b5d34cc028a494a75ff16db7f959d35ce5bb29ca505354df2a717` |
| `source_selection.csv` SHA-256 | `7a4727401c680027ae47cea87a1d760389432e92732b83a3adc17385f53de238` |
| `source_trial_assignments.csv.gz` SHA-256 | `a0da8c7fb5751cfc9dfc4418758cfe2db9d826101f3a1b824c6f2b0d8b23acb6` |
| Regeneration equality gate | `status: "ok"` — 140,110 split rows / 97,500 calibration rows / 614 source-selection rows / 24,560 source-trial rows, **all exactly identical** between the reused primary files and an independent from-scratch regeneration under `configs/sensitivity_ea_training_only.yaml`'s seed/dataset/split/calibration/source sections |

All values above are read directly from
`results/bci-calibration-ea-training-only-sensitivity-43e15c22709c6e6b/assignment_reuse_report.json`
and `run_manifest.json`, not retyped from memory.

## Cohort

Identical to the primary confirmatory analysis (same reused assignments):
Lee2019_MI 54, BNCI2014_001 9, Zhou2016 2 (subjects 2 and 4 structurally
excluded, per `docs/DECISIONS.md`) — **65 participants**, confirmed via
`participant_flow.csv` and the audit's `participants: 65`.

## EA benchmark execution

| Field | Value |
|---|---|
| Config | `configs/sensitivity_ea_training_only.yaml` |
| Preprocessing fingerprint | `861cc64b9adbc47c` (identical to primary — full montage, `channels: null`) |
| Experiment fingerprint | `43e15c22709c6e6b` |
| Output directory | `results/bci-calibration-ea-training-only-sensitivity-43e15c22709c6e6b/` (gitignored, locally reproducible) |
| Expected condition count | 15,600 (`65 participants × 10 repeats × 3 methods × 2 regimes × 4 positive budgets`) |
| Conditions completed / failed | **15,600 / 0** |
| Prediction rows | **1,655,040** — exactly matches the assignment-derived arithmetic prediction in the spec (`2,068,800 × 8/10`); validated against the actual run, not forced |
| Result-integrity audit | `status: "ok"` — 15,600/15,600 metric conditions recomputed from stored predictions and matched exactly; `source_alignment_provenance_rows: 614` (matches primary's `source_selection_rows` exactly); `target_alignment_provenance_rows: 2,600` (`65 × 10 repeats × 4 budgets`, one row per group — the structural proof that `subject` and `source_plus_target` share one target transform per condition group) |
| Aggregation result | PASS — `summary_subject.csv`, `curve_summary.csv`, `pairwise_tests.csv`, `ea_regime_contrast_trajectory.csv`, `participant_flow.csv`, `result_audit.json` all written; **no** `mixed_effects_coefficients.csv` / `mixed_effects_diagnostics.json` / `aucc_subject.csv` (per human decision 4 / the EA design not using AUCC) |
| Figure-generation result | PASS — calibration and heterogeneity figures for all 3 datasets under `figures/`; no AUCC figures (none computed) |
| Runtime | `run_ea_benchmark` started `2026-08-20T23:47:43.259653Z`, completed `2026-08-21T01:25:59Z` (**1h 38m**) |
| Regime/budget/method grid observed | regimes `{subject, source_plus_target}` only (no `population`); budgets `{5, 10, 20, 40}` only (no `0`); methods `{logvar_lda, csp_lda, riemann_lr}`; `alignment_mode == "euclidean_training_only"` for every row |

## Leakage-boundary and provenance checks (all passed)

- Fail-closed assignment-reuse equality gate: **passed** before any model
  was fit (see fingerprints above).
- Target-reference estimation reads only the calibration-subset array for
  its condition group; never `split.test_idx`. Verified by construction
  (`ea_runner.py`) and by unit/integration tests
  (`test_target_reference_excludes_test_trials`,
  `test_ea_end_to_end_reuses_primary_assignments_and_shares_target_transform`).
- Source-reference estimation reads only each source participant's
  already-capped, reused selected-trial indices; never an unselected trial
  or the target's own trials. Verified by
  `test_source_reference_excludes_unselected_trials`,
  `test_source_indices_from_reused_only_returns_selected_rows`.
- `subject` and `source_plus_target` regimes share one target transform
  per `(dataset, target_subject, repeat, split_id, budget_per_class)`
  group: `target_alignment_provenance.csv.gz` has exactly one row per
  group (2,600 rows = 65 × 10 × 4, no duplicates) — this is a structural
  guarantee (the code computes the reference once per group and reuses the
  same in-memory array for both regimes), and the audit asserts the
  uniqueness that makes it checkable from disk.
- EA is deterministic: no RNG is used anywhere in `alignment.py`; verified
  directly (`test_alignment_is_deterministic`) and via the identity
  property `mean_i(X_aligned_i X_aligned_i^T) ≈ I`
  (`test_ea_identity_property`).
- Budget 0 is structurally absent from every EA output file (metrics,
  predictions, both provenance files) and `estimate_ea_reference` raises
  `ValueError` on an empty trial axis rather than silently no-op'ing
  (`test_alignment_rejects_budget_zero`).
- Tampering detection: a corrupted reused-assignment copy is rejected by
  the equality gate before any fit (`test_audit_detects_assignment_reuse_drift`);
  a duplicated `target_alignment_provenance` row is rejected by the audit
  (`test_audit_detects_tampered_alignment_reference`).
- No EA-derived output file contains the word "confirmatory" in any
  `family` or `inference_role` value — asserted in code
  (`ea_aggregate._relabel_pairwise`) and in tests
  (`test_ea_aggregation_never_labels_confirmatory`), and confirmed on the
  real run's `pairwise_tests.csv`.

## Deviations from the original specification draft (beyond the five human decisions)

1. **Config-fingerprint backward-compatibility fix (found and fixed before
   any benchmark ran).** Adding `AlignmentSection` as a new
   `ExperimentConfig` field naively changes `experiment_fingerprint` (and
   therefore `output_dir`) for **every** existing config, including
   `configs/full.yaml`, because `experiment_fingerprint` hashes
   `asdict(self)` in full. This was caught immediately by recomputing
   `configs/full.yaml`'s fingerprint after the field was added
   (`e964f1750935ec8d` instead of the on-disk `3fb8efe7e617b0c1`) — it
   would have silently redirected the primary config's `output_dir` away
   from its own closed results directory on any future load. Fixed by
   omitting the `alignment` key from the fingerprint payload exactly when
   `alignment.mode == "none"` (its no-op default), which restores
   byte-identical fingerprints for `configs/full.yaml`,
   `configs/sensitivity_three_channels.yaml`,
   `configs/sensitivity_all_sources.yaml`, and `configs/pilot.yaml`
   (verified directly, and covered by
   `test_alignment_default_leaves_existing_config_fingerprints_unchanged`),
   while a config that actually turns EA on still gets a distinct
   fingerprint as intended. No benchmark, aggregation, or audit had been
   run against the unfixed code at the time this was found.
2. **Dataset-collision bug in assignment reuse (found on the first real
   3-dataset run attempt, fixed before any valid EA metrics existed).**
   `target_split_from_reused` and `calibration_samples_from_reused`
   initially filtered reused assignment rows by `target_subject` (and,
   for calibration, `split_id`) but not by `dataset`. Every dataset in
   this study has a "subject 1", so the filter silently mixed another
   dataset's same-numbered participant's rows into a target's split. This
   was caught immediately: the first full-cohort EA run attempt
   (2026-08-20, ~19:44 local) failed loudly with
   `ValueError: Reused split-assignment trial UIDs not found in the
   loaded target shard` rather than silently producing a wrong result —
   exactly the fail-closed behavior the leakage boundary was designed to
   produce. The partial output directory from that failed attempt
   (3 small provenance/manifest files, no `metrics.csv`, no scientific
   content) was deleted before re-running. Root cause: the single-dataset
   synthetic smoke tests used during development could not exercise this
   class of bug (there was no second dataset to collide with). Fixed by
   adding `dataset` to both functions' filters, and a regression test
   (`test_ea_handles_overlapping_subject_ids_across_datasets`) was added
   that reproduces the collision with two small synthetic datasets sharing
   subject numbering 1..3, and passes against the fix. The full pytest
   suite and the real 65-participant run were only executed after this
   fix, never before it.
3. **No `aucc_subject.csv` / AUCC figures for EA**, per human decision 4
   (no mixed-effects model; EA inference limited to the H2-analog contrast
   and descriptive trajectories — there is no Riemannian-vs-CSP AUCC
   contrast requested for EA at all). `make_all_figures`/`aggregate_run`
   were not reused unmodified for this reason; `ea_plotting.make_ea_figures`
   calls only `plotting.make_calibration_figures` and
   `plotting.make_heterogeneity_figures`.
4. **`cli.py` was extended rather than left untouched**, contrary to this
   round's initial risk-minimization instinct: a `--assignment-source`
   argument and an `alignment.mode`-based dispatch were added to the
   existing `run`/`aggregate`/`figures`/`audit` subcommands. This was a
   deliberate, low-risk choice (the `alignment.mode == "none"` branch of
   every dispatch calls the exact pre-existing function with no changed
   arguments) made after confirming it did not require touching
   `runner.py`, `validation.py`, `statistics.py`, or `aggregate.py`.
5. **No large diagnostic report was generated ad hoc outside this
   package** — all read-only exploration during implementation (schema
   checks, fingerprint verification, the assignment-reuse dry run against
   real primary data) was done via short inline Python invocations, not
   persisted as separate files, consistent with keeping this round's
   footprint to the files listed above.

No other deviations or warnings.

## Artifacts

- `src/bci_calibration_benchmark/{alignment,assignment_reuse,ea_runner,ea_validation,ea_aggregate,ea_plotting}.py`
- `configs/sensitivity_ea_training_only.yaml`
- `scripts/{post_confirmatory_robustness,build_ea_vs_primary_comparison}.py`
- `tests/test_alignment.py` (15 tests), extensions to `tests/test_config.py` (2 tests)
- `results/bci-calibration-ea-training-only-sensitivity-43e15c22709c6e6b/` — full EA run (metrics, predictions, both alignment-provenance files, assignment_reuse_report.json, run_manifest.json, aggregated tables, result_audit.json, figures)
- `results/bci-calibration-full-v1-3fb8efe7e617b0c1/post_confirmatory_robustness/` — analyses A/B/C outputs (additive; primary directory's pre-existing files untouched)
- `manuscript/artifacts/post_confirmatory_robustness/` — `PROVENANCE.md`, `summary.md`, `source_data/` (reproducible CSVs for all four analyses)
- `docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md` — status header updated to reflect approval and implementation (this round)
- This file

## Scientific cautions (factual, not interpretive conclusions)

- The EA sensitivity's pooled low-budget strengthening and the
  Riemannian-specific higher-budget reversal are both reported in
  `manuscript/artifacts/post_confirmatory_robustness/summary.md` without
  editorial softening. Per the explicit stop-condition instruction, this
  round did not stop or alter anything because a result was reversed or
  unfavorable to any particular narrative.
- This package does not resolve *why* EA strengthens the pooled effect at
  low budgets or *why* it reverses for Riemannian TS + LR at higher
  budgets; both are reported as observed patterns, not explained
  mechanistically.
- Every pooled EA and without-Zhou estimate is participant-weighted, so
  Lee2019_MI (54/65) still dominates; Zhou2016 (2/65) remains descriptive
  only in every analysis in this package, exactly as in the primary
  confirmatory analysis.
- None of this package's findings have been reviewed for manuscript
  inclusion or wording; `docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md`
  section 6 contains proposed (not applied) manuscript wording unrelated
  to the EA results themselves (H2/H3 numbering, abstract wording, the
  BNCI2014_001 Riemannian finding, the deep-model limitation).

## Decision

**READY FOR HUMAN SCIENTIFIC REVIEW.** Implementation, the full regression/
leakage test suite, the real 65-participant EA benchmark, its
result-integrity audit, aggregation, and figures, and the three
non-benchmark robustness analyses all completed successfully with 0
failures and `status: "ok"` audits throughout. This record closes
implementation and execution only; it does not constitute or authorize a
scientific conclusion, a manuscript change, or a commit/push of any file
listed above.
