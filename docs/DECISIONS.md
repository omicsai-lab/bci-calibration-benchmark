# Protocol decision log

Every scientific decision is dated and recorded before public-data outcome analysis. Changes after outcome inspection must be labeled exploratory and released under a new protocol version.

## 2026-08-11 — Repository-first strategy

**Decision:** Build the auditable execution and validation layer before downloading the full public datasets.  
**Rationale:** Split leakage, adapter collapse, silent preprocessing changes, and pseudoreplication can invalidate a result even when the classifier code runs.

## 2026-08-11 — Operational question, not architecture race

**Decision:** Study calibration burden and later-session performance rather than propose another attention/CNN variant.  
**Rationale:** The literature is crowded with single-dataset architecture papers; a multi-dataset calibration estimand is more practically interpretable.

## 2026-08-11 — Binary left/right task

**Decision:** Harmonize to left-hand versus right-hand motor imagery.  
**Rationale:** This task exists in all selected datasets and supports a common ROC-AUC endpoint.

## 2026-08-11 — Strict latest-session holdout

**Decision:** Hold out the chronologically latest session in full; no back-selection and no run/trial fallback in confirmatory configurations.  
**Rationale:** This approximates deployment to a later recording and prevents favorable split search.

## 2026-08-11 — Reject Cho2017 and PhysionetMI for confirmatory v0.1

**Decision:** Do not use these large cohorts in the primary cross-session analysis.  
**Rationale:** Their current MOABB representation does not expose the multi-session structure required by this estimand. Trial-level splitting would answer a different question.

## 2026-08-11 — Reject BNCI2014_004

**Decision:** Do not use BCI Competition IV Dataset 2b in v0.1.  
**Rationale:** The later sessions include continuous feedback while the earlier sessions do not; the latest-session comparison would confound calibration with protocol shift.

## 2026-08-11 — Select Lee2019_MI, BNCI2014_001, and Zhou2016

**Decision:** Use these three MOABB adapters as the confirmatory set.  
**Rationale:** Each supports a strict later-session test, enough earlier-session calibration data, left/right imagery, and no required trial fallback.

## 2026-08-11 — Exclude Lee online-feedback phase

**Decision:** Instantiate `Lee2019_MI(train_run=True, test_run=False, resting_state=False)`.  
**Rationale:** The labeled offline phase is available in both sessions and matches the supervised estimand; the online test phase is unlabeled in the adapter.

## 2026-08-11 — Fix preprocessing

**Decision:** 8–30 Hz, 0.5–3.5 s, 128 Hz, no baseline, full montage.  
**Rationale:** The interval lies inside the imagery period exposed by the adapters and avoids the earliest cue transient. It does not eliminate cue activity, which is disclosed as a limitation.

## 2026-08-11 — Pre-specify common three-channel sensitivity

**Decision:** Repeat the analysis on `C3/Cz/C4`.  
**Rationale:** These channels are present in all selected datasets and provide a low-density sensorimotor check against montage-driven results.

## 2026-08-11 — Calibration budgets

**Decision:** Use 0, 5, 10, 20, and 40 labeled trials per class, with nested samples and 10 repeats.  
**Rationale:** The range spans no calibration through a feasible full earlier-session budget in every selected dataset.

## 2026-08-11 — Cap the primary source cohort

**Decision:** Select at most 10 source participants and 20 trials/class/source participant.  
**Rationale:** Equalize source influence, prevent extreme source-to-target imbalance, and keep repeated CSP/Riemannian fitting tractable. An all-source sensitivity analysis is retained.

## 2026-08-11 — Classical confirmatory core

**Decision:** Use log-variance/LDA, CSP/LDA, and Riemannian tangent-space/logistic regression; keep EEGNet optional.  
**Rationale:** Fixed classical methods are auditable and scientifically sufficient for the first calibration benchmark. Deep learning requires a separate compute and optimization protocol.

## 2026-08-11 — Participant-level inference

**Decision:** Average calibration repeats within participant before inferential comparisons.  
**Rationale:** Trials and repeated calibration draws are not independent human participants.

## 2026-08-11 — Fixed-horizon AUCC

**Decision:** Calculate normalized AUCC on `log2(b+1)` through 40 trials/class only for complete curves.  
**Rationale:** Variable horizons can reward methods simply because they have more observed budget points.

## 2026-08-11 — Pooled comparisons and supportive dataset estimates

**Decision:** Label pooled participant-weighted paired contrasts confirmatory and dataset-specific contrasts supportive; report both.  
**Rationale:** The large Lee cohort necessarily dominates participant-weighted pooled estimates. Dataset-specific reporting prevents that fact from being hidden.

## 2026-08-11 — Yang2025 reserved for a later release

**Decision:** Do not add Yang2025 to confirmatory v0.1.  
**Rationale:** It is highly relevant but distributed as a large single archive and has not passed local adapter/compute validation. It can serve as pre-declared external validation in a later version.

## 2026-08-12 — Lee2019 session-index workaround

**Observed behavior:** During the real-data pilot, `Lee2019_MI` preparation
failed with `expected 2 sessions, observed 1`, even though
`Lee2019_MI().n_sessions == 2` and both sessions' raw `.mat` files were
present and downloaded.

**Underlying MOABB 1.5.0 issue:** Introspection (`moabb/datasets/Lee2019.py`,
`moabb/datasets/base.py`) showed that `Lee2019` names each subject's
per-session data with 0-indexed string keys (`"0"`, `"1"`) internally, while
its constructor forwards the *1-indexed* `sessions` argument (`(1, 2)` by
default) to `BaseDataset.__init__(selected_sessions=sessions)`.
`BaseDataset.get_data()` then keeps only session keys matching
`{str(s) for s in selected_sessions}` == `{"1", "2"}`, which overlaps only
key `"1"` and silently discards the entire first session for every subject.
This was verified directly by introspection, not inferred, and reproduces
unconditionally (it does not depend on our constructor kwargs and cannot be
worked around by passing a different `sessions=` value, since `Lee2019`
rejects any session value outside `[1, 2]`).

**Decision:** Neutralize the bug at the point of dataset construction
(`datasets.py::_instantiate_public_dataset`) by resetting
`Lee2019_MI()._selected_sessions` to `None` after construction, which
disables the buggy post-hoc filter and restores both sessions. This is a
targeted, MOABB-version-specific workaround, not a change to our own
session-handling logic.

**Why the workaround is required, not optional:** Without it, the
prespecified `latest_session_only` split (earlier sessions as calibration
pool, latest session held out) is structurally impossible for `Lee2019_MI` —
only one session would ever be observed. The dataset would otherwise have to
be dropped from the confirmatory set entirely, which is a materially larger
protocol change than working around a verified upstream indexing bug.

**Estimand:** Unchanged. `DATASET_EXPECTATIONS["Lee2019_MI"].sessions == 2`
already required the full two-session protocol before this bug was found;
the workaround *restores* that pre-specified structure rather than altering
it. No preprocessing, split policy, calibration budget, source-cohort logic,
or statistical analysis changed.

**Fail-loud guard:** The workaround asserts
`dataset._selected_sessions == [1, 2]` (the exact known-buggy state)
immediately before overriding it. If a future MOABB release changes this
internal representation, the assertion raises `RuntimeError` instead of
silently applying a now-incorrect override. Regression tests
(`tests/test_datasets.py`) cover both the neutralization and the fail-loud
path, and confirm no other confirmatory dataset (`BNCI2014_001`, `Zhou2016`)
is affected.

## 2026-08-12 — Zhou2016 subject 2 structural exclusion

**Decision:** `Zhou2016` subject 2 is structurally ineligible for the
prespecified confirmatory calibration design and is excluded from
`configs/pilot.yaml`, `configs/full.yaml`,
`configs/sensitivity_three_channels.yaml`, and
`configs/sensitivity_all_sources.yaml`.

**Basis:** The publicly released recording for this subject's session
1, run 1 contains only 20 trials/class where the protocol (and every other
subject/session/run in this cohort) has 25 trials/class per run — verified
directly against raw event counts in the released BIDS data via
`mne.events_from_annotations`, independent of MOABB version or our
pipeline. This fails
`DATASET_EXPECTATIONS["Zhou2016"].minimum_trials_per_class_per_session`,
which is unchanged and was not relaxed to accommodate this subject.

**This is a pre-outcome structural exclusion, not performance-based subject
removal:**

- The failure occurred inside `validate_subject_structure` during
  `prepare_data`/structural validation, strictly before any split
  construction, model fit, prediction, or metric computation for this
  subject was possible.
- No model performance, calibration curve, or decoder output was consulted
  in making this decision.
- The exclusion is recorded in configuration (`exclude_subjects: [2]`),
  visible to any reader inspecting the scientific configuration, rather
  than hard-coded inside execution logic.

**Estimand:** Unchanged. Left-hand-versus-right-hand motor-imagery ROC-AUC
under later-session holdout remains the estimand; this decision only
determines which participants can be structurally scored under that
estimand. At pilot time, subjects 1 and 3 (the only other `Zhou2016`
subjects then exercised) satisfied the 25-trials/class/run floor; subject 4
had not yet been checked (see the following decision entry, which found it
does not).

**Scope:** This decision must stand before confirmatory outcome analysis
begins and must not be revisited based on how any decoder performs on the
remaining participants.

## 2026-08-13 — Zhou2016 subject 4 structural exclusion

**Decision:** `Zhou2016` subject 4 is structurally ineligible for the
prespecified confirmatory calibration design, for the same reason and under
the same criterion as subject 2 above, and is excluded from
`configs/full.yaml`, `configs/sensitivity_three_channels.yaml`, and
`configs/sensitivity_all_sources.yaml`. (`configs/pilot.yaml` never included
subject 4 and is unaffected.)

**Basis:** Discovered during `prepare_data.py --config configs/full.yaml`
(the confirmatory full-cohort run), which exercises every nominal `Zhou2016`
subject for the first time — the pilot only ever checked subjects 1 and 3.
Subject 4's session 0, run 0 contains only 20 trials/class instead of the
protocol's 25/run (run 1 of the same session has the full 25/class),
verified directly against raw event counts via `mne.events_from_annotations`
on the released BIDS data. The short run's recorded duration (726.0 s) is
proportionally shorter than every other run for this subject (840-869 s) —
the same signature as subject 2's shortfall (702 s vs. ~850-910 s) — meaning
the underlying recording session was genuinely shorter, not that events were
lost from an otherwise full-length file. This fails
`DATASET_EXPECTATIONS["Zhou2016"].minimum_trials_per_class_per_session`,
which is unchanged and was not relaxed to accommodate this subject, exactly
as for subject 2.

**This is a pre-outcome structural exclusion, not performance-based subject
removal:** the failure occurred inside `validate_subject_structure` during
data preparation, strictly before any split, model fit, or prediction for
this subject existed. No model performance was consulted. The finding was
reported before any config change was made, and the exclusion — once
confirmed — was applied using the identical mechanism and evidentiary
standard as the subject-2 decision.

**Estimand:** Unchanged, for the same reasons as the subject-2 decision.
With both subjects 2 and 4 excluded, `Zhou2016` contributes the same 2
participants (1 and 3) to the confirmatory full-cohort run as it did to the
pilot.

**Scope:** This decision must stand before confirmatory outcome analysis
begins and must not be revisited based on how any decoder performs on the
remaining participants. It does not retroactively imply that subjects 1 and
3 will remain the only eligible `Zhou2016` participants in any future
release of this dataset — only that these are the two currently verified
eligible under this protocol's structural criterion.
