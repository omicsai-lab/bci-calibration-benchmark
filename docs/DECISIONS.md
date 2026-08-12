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
