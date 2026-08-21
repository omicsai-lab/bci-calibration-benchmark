# Post-confirmatory robustness specification: Euclidean Alignment sensitivity and related analyses

**Status:** APPROVED AND IMPLEMENTED. This document was originally written
SPECIFICATION ONLY (pre-implementation) in an earlier round on the
`alignment_sensitivity` branch. It was then reviewed by a human and
**approved for implementation, subject to five overriding decisions**
(literal unnormalized He-Wu covariance in place of this document's
`/n_samples` proposal in section 1.4; assignment reuse as a runtime/CLI
argument rather than a config field, per section 3.1's own flagged open
question; two separate alignment-provenance files rather than the combined
layout in section 3.6; no mixed-effects model for the EA run; and the
exact `n_positive`/`n_zero`/`n_negative`/`fraction_positive` schema for the
fraction-benefiting analysis in section 5.C). Implementation, the full
regression/leakage test suite, the real 65-participant EA benchmark
execution, and the three non-benchmark robustness analyses were then
completed. This document's body is left as originally written (including
the superseded `/n_samples` proposal in 1.4, correctzed by the overriding
decision) for an accurate historical record of what was proposed versus
what was authorized, corrected by the overriding decision; **the overriding
decisions above take precedence over any conflicting text below.** The execution/results record is
`docs/post_confirmatory_robustness_acceptance.md`, not this file.
**Author round:** reviewer-response robustness planning, `alignment_sensitivity` branch.
**Relationship to the frozen protocol:** everything in this document is
**post-confirmatory**. `docs/ANALYSIS_PLAN.md` (frozen 2026-08-11) does not
mention distribution alignment. Nothing here amends that document, and
nothing here is retroactively labeled prespecified. This document only
proposes what a later, separately approved implementation round would build.

This document does not modify code, configs, or the manuscript. Where exact
wording is proposed for the manuscript, it is quoted for human copy/paste,
not applied.

---

## 0. What was inspected to write this spec

Before writing anything below, the current `alignment_sensitivity` branch
(clean, no local changes, `HEAD=4369714`) was read in full for the
components this spec depends on:

- `src/bci_calibration_benchmark/config.py` — schema, `_check_keys`,
  `ExperimentConfig.validate()`, fingerprint properties.
- `src/bci_calibration_benchmark/splits.py`, `sampling.py` — how
  `split_id`, calibration orderings, and source selection are derived.
- `src/bci_calibration_benchmark/runner.py` — the condition loop, seed
  derivation call sites, `ConditionKey`, resume/dedup logic, and exactly
  where source/target training arrays are assembled.
- `src/bci_calibration_benchmark/riemann.py` — the only existing
  SPD/eigendecomposition code in the repository (`matrix_power_spd`,
  `_eigh_spd`), which the alignment transform should reuse rather than
  duplicate.
- `src/bci_calibration_benchmark/statistics.py`, `validation.py` — how the
  H2/H3 paired contrasts, mixed model, and result-integrity audit are
  implemented, since the EA sensitivity and the three non-benchmark
  analyses reuse this machinery rather than inventing new statistics.
- `docs/ANALYSIS_PLAN.md`, `docs/STATISTICAL_ANALYSIS.md`,
  `docs/DECISIONS.md`, `docs/full_run_acceptance.md`,
  `docs/sensitivity_run_acceptance.md`,
  `manuscript/artifacts/sensitivity_analysis/sensitivity_comparison.md`,
  `manuscript/methods_draft.md`, `manuscript/outline.md` — frozen protocol
  text, the two prespecified sensitivities' precedent for how a
  non-primary analysis is scoped and reported, and the exact places the
  reviewer-flagged jargon and findings currently live.
- The actual audited primary artifacts in
  `results/bci-calibration-full-v1-3fb8efe7e617b0c1/` (`metrics.csv`,
  `pairwise_tests.csv`, `split_assignments.csv.gz`,
  `calibration_assignments.csv.gz`, `source_selection.csv`,
  `source_trial_assignments.csv.gz`) — read directly (not assumed) to
  confirm row counts, column names, and the BNCI2014_001 Riemannian
  dataset-specific numbers quoted in §6.

No benchmark was run and no file other than this one was written.

---

## 1. Euclidean Alignment sensitivity: estimand and transform

### 1.1 Estimand

Post-confirmatory exploratory question: **does training-only Euclidean
Alignment (EA) materially change the observed low-budget
population–personalization trade-off (H2-analog: `source_plus_target −
subject`, ROC-AUC, at 5 and 10 trials/class)?**

This is explicitly *not* a new confirmatory hypothesis. It reuses the
H2 contrast structure descriptively, under a new preprocessing step,
without Holm-family status.

### 1.2 Cohort, system settings (unchanged from primary)

- 65 structurally eligible participants, identical to the primary run and
  both prespecified sensitivities: `Lee2019_MI` 54, `BNCI2014_001` 9,
  `Zhou2016` 2 (subjects 2 and 4 excluded per `docs/DECISIONS.md`).
- Full montage (`preprocessing.channels: null`), i.e. the same processed
  data as the primary run — **not** the three-channel sensitivity's data.
- `source.max_subjects: 10`, `source.max_trials_per_class_per_subject: 20`,
  `source.balance_classes_within_subject: true`.
- `split.repeats: 10`.
- `methods: [logvar_lda, csp_lda, riemann_lr]`.
- Target calibration budgets used for EA-transformed conditions: **5, 10,
  20, 40** trials/class only.

### 1.3 Budget 0 is out of scope, unconditionally

Budget 0 is excluded for **every** EA regime, not only the target-only
regime. Reasoning, confirmed by re-reading `runner.py`:

- The `population` regime (source-only, budget 0) still requires scoring
  on `X_test`. Under EA, scoring requires transforming `X_test` with a
  **target-specific** alignment reference (§1.6). That reference is
  estimated only from target calibration data. At budget 0 there is no
  target calibration data, so no target-specific reference can be
  constructed without either (a) using held-out test-session EEG to
  estimate it — forbidden — or (b) substituting a different,
  non-target-specific reference (e.g. a population/source reference) —
  which would silently change the estimand from "training-only,
  target-specific EA" to a different, unspecified alignment design.
- Therefore `population`, and any EA-transformed `subject` or
  `source_plus_target` row, are all undefined at budget 0. The
  implementation must **fail closed** on this case (§3.6, test #8), not
  silently substitute or skip.

Because `ExperimentConfig.validate()` currently hard-requires
`budgets_per_class[0] == 0` (`config.py`, `validate()`:
`"Calibration budgets must begin with zero"`), the EA config keeps
`calibration.budgets_per_class: [0, 5, 10, 20, 40]` at the schema level —
this preserves seed-derivation identity with the primary config (§2) and
schema validity — but the alignment execution path must never emit or
score an EA-transformed condition at budget 0. This is a runtime
restriction on the EA code path, not a change to the shared budget-list
invariant.

### 1.4 Transformation definition

Standard He–Wu Euclidean Alignment (He & Wu, *IEEE TBME* 2020), applied
**per participant** (each source participant separately; each target
participant separately, per repeat and per budget):

```
R = mean_i( X_i X_i^T )          # trial-averaged spatial covariance
X_aligned_i = R^(-1/2) X_i        # per-trial whitening
```

where `X_i` is one trial's `(channels, samples)` array from this
repository's already-preprocessed shard (8–30 Hz, 0.5–3.5 s, 128 Hz,
`float32`, no baseline correction — the existing confirmatory
preprocessing is unchanged; EA is inserted downstream of it).

Concrete specification, one clause per required decision:

- **Trial centering:** none beyond what the confirmatory preprocessing
  already does. The frozen protocol applies no baseline correction
  (`docs/ANALYSIS_PLAN.md` §5), and this spec does not add any new
  per-trial mean subtraction. `R` is computed directly from the
  preprocessed `X_i`, consistent with the standard EA formulation, which
  does not baseline-correct either.
- **Covariance normalization:** `R_i = X_i X_i^T / n_samples` (divide by
  the number of time samples per trial, a fixed constant — 384 samples at
  128 Hz over 3.0 s — across the whole study). This is a documented,
  disclosed deviation from the literal unnormalized He–Wu formula
  (`R_i = X_i X_i^T`); it only rescales `R` by a positive constant shared
  by every trial in the study, so it does not change `R^{-1/2}`'s
  direction/conditioning relative to the unnormalized form up to that
  constant, and it keeps `R`'s numerical scale comparable to the
  covariance objects already computed elsewhere in this codebase
  (`OASCovariances`, which is fit on `epoch.T`, i.e. `(samples,
  channels)`, an sklearn convention that likewise produces
  sample-normalized covariances). Because every condition in this
  sensitivity uses the identical epoch length, this normalization choice
  cannot differentially affect the alignment reference across
  participants, methods, or regimes.
- **Eigendecomposition / inverse-square-root procedure:** reuse
  `riemann.matrix_power_spd(matrix, power=-0.5, epsilon)` verbatim (do not
  reimplement). That function symmetrizes `R`, computes `np.linalg.eigh`,
  clips eigenvalues to a floor, and reconstructs
  `V diag(λ^power) V^T`. Reusing it means the alignment transform inherits
  the same audited numerical behavior already exercised by
  `tests/test_riemann.py` and the confirmatory Riemannian pipeline, rather
  than introducing a second, independently-fallible SPD inverse-square-root
  implementation.
- **Eigenvalue floor / regularization:** `epsilon = 1e-12` by default,
  identical to `riemann.py`'s existing default, configurable via
  `alignment.epsilon` (§3.1). This guards only against near-singular `R`
  (e.g. a degenerate calibration subset); it is not a tunable hyperparameter
  and must not be selected on outcome.
- **Deterministic behavior:** `np.linalg.eigh` and every operation in the
  transform are deterministic given the same input array (no RNG is
  consumed by EA — see §3.6, test #5). The transform therefore needs no
  seed of its own; it inherits determinism entirely from the determinism
  of *which trials* feed it, which is governed by the existing assignment
  machinery (§2).

### 1.5 Source-side estimation (source data only)

For each selected source participant `s` (selected exactly as in the
primary run — see §2), estimate `R_s` from exactly that participant's
already-capped, class-balanced selected source trials — the same trial
set produced today by `sampling.source_indices_for_subject` and recorded
in `source_trial_assignments.csv.gz`. No target data, no source
participant's *un*selected trials (trials excluded by the
`max_trials_per_class_per_subject` cap), and no other source
participant's trials may contribute to `R_s`. Apply
`X_aligned = R_s^{-1/2} X` to that participant's selected trials only,
before those trials are concatenated into the pooled source training
array.

### 1.6 Target-side estimation (target calibration data only)

For every `(dataset, target_subject, repeat, budget)` in `{5, 10, 20,
40}`, estimate `R_target` from exactly that condition's target
calibration subset (the nested calibration sample already recorded in
`calibration_assignments.csv.gz` for that budget) — never from the target
test trials, never from a different repeat's or a different budget's
calibration subset. Freeze `R_target^{-1/2}` and apply it to:

  (a) the target calibration trials themselves, and
  (b) the untouched later-session target test trials.

Test trials are transformed by this frozen reference but never used to
*estimate* it. This is the load-bearing leakage boundary of the whole
sensitivity (§3.6, test #1).

### 1.7 Same target transform across both compared regimes

For a given `(dataset, target_subject, repeat, budget)`, both `EA
subject-only` and `EA source-plus-target` must use the identical
`R_target^{-1/2}` computed in §1.6 — the target-side transform must not
be re-estimated per regime. This is required so the source-data contrast
is not confounded by different target preprocessing between the two arms
being compared. Concretely: `R_target` depends only on the target
calibration subset, never on which regime is being scored, so a correct
implementation gets this for free as long as the reference is computed
once per `(dataset, target_subject, repeat, budget)` and threaded into
both regimes' training/scoring calls (§3.2).

### 1.8 Primary and descriptive contrasts

- **Primary alignment contrast (post-confirmatory exploratory, not a new
  confirmatory family):** `EA source_plus_target − EA subject` for
  ROC-AUC, at 5 and 10 trials/class, computed with the same paired
  participant-level machinery already implemented in
  `statistics.build_pairwise_tests` (reused, not reimplemented — see
  §3.2), but **relabeled** so no output can be read as confirmatory
  (§3.2, §7).
- **Descriptive use of budgets 20 and 40:** calibration trajectories,
  convergence, persistence, or reversal of the source-data effect as
  budget grows, reported descriptively (curves, per-participant paired
  differences by budget) — no additional Holm family, no new p-value
  family.

### 1.9 Scope discipline

This sensitivity tests **Euclidean Alignment only**. No deep learning, no
Riemannian re-centering (a different, distinct
recentering-in-tangent-space technique from EA and out of scope), no
other domain-adaptation method, and no partial pooling are introduced.
`config.py`'s existing `valid_methods = {"logvar_lda", "csp_lda",
"riemann_lr", "eegnet"}` is unchanged; EA only inserts a preprocessing
step upstream of the existing three confirmatory decoders. `eegnet`
remains untouched by this sensitivity and out of scope (see §6.4 on the
deep-model limitation wording).

---

## 2. Exact assignment matching

**Decision: Option B (explicit reuse of the primary run's assignment
files) is the operative mechanism, with Option A's deterministic-seed
argument required as an automated equality cross-check, not trusted
blindly.**

### 2.1 Why Option A's argument is credible (evidence, not assumption)

Tracing the code:

- `splits.make_target_split` → `_latest_session_holdout` computes the
  target split **only from `metadata` (`session`, `run`, `trial_uid`) and
  `y`**. It consumes no seed at all (the only seeded split path,
  `_trial_level_fallback`, is disabled in every confirmatory/sensitivity
  config via `allow_trial_level_fallback: false`). So `split_id` depends
  only on which trials exist and their session/run labels — not on
  `experiment.seed`, not on `preprocessing.channels`, not on
  `source.max_subjects`.
- `sampling.nested_calibration_samples` seeds a single
  `rng.shuffle` per class from `calibration_seed =
  derive_seed(experiment.seed, dataset, target_subject, repeat,
  "calibration")`. This does not depend on `budgets_per_class`'s content
  (the budget-0 branch consumes no RNG state at all), so adding/removing
  budget 0 from the *processing loop* — as opposed to the *config field*,
  which must stay `[0, 5, 10, 20, 40]` per §1.3 — cannot perturb the
  orderings used for budgets 5/10/20/40.
- `sampling.choose_source_subjects` and `source_indices_for_subject` seed
  from `derive_seed(experiment.seed, dataset, target_subject,
  "source_subjects")` and `derive_seed(experiment.seed, dataset,
  target_subject, source_subject, "source_trials")` respectively — again
  functions only of `experiment.seed` plus explicit string parts, not of
  the full config.
- `utils.derive_seed` is a pure function of `(int(global_seed),
  *str(parts))` via SHA-256 — it does not hash the whole config, so an
  unrelated new config section (e.g. `alignment:`) cannot perturb it.

**This is not merely theoretical.** The two existing prespecified
sensitivities already constitute an empirical test of exactly this
claim: `configs/sensitivity_three_channels.yaml` changes
`preprocessing.channels` (a different `processed_dir`, i.e. genuinely
different `X` content) and `configs/sensitivity_all_sources.yaml` changes
`source.max_subjects` — and both runs report, in
`docs/sensitivity_run_acceptance.md`, **byte-identical
`participant_flow.csv`** and an **identical total prediction-row count
(2,068,800)** to the primary run, across all three result directories.
Since prediction-row count equals the sum of `test_trials` over all
conditions, and `test_trials` is fixed per `(dataset, target_subject,
repeat)` by the split alone, this is direct evidence that the target
split was reproduced exactly under two configuration changes that (like
the proposed EA config) preserve `experiment.seed` and the
`datasets`/`split`/`calibration` sections.

### 2.2 Why Option A alone is still not adopted as the sole mechanism

The evidence above is strong but was generated by configs that changed
different things than an alignment config would. A future alignment
implementation is new code with its own defect surface (e.g. an
accidental extra `derive_seed(...)` call inserted before the existing
ones in the source loop would not change *this* run's determinism but
could not be ruled out purely by re-reading old runs). Given the stated
priority order —
`scientific validity > untouched-test integrity > exact assignment
matching > auditability > runtime convenience` — the safer design is to
make exact matching **structural**, not **inferred**:

### 2.3 Specification

1. The EA sensitivity run **must load and reuse**, not regenerate, the
   primary run's four assignment artifacts:
   - `split_assignments.csv.gz`
   - `calibration_assignments.csv.gz`
   - `source_selection.csv`
   - `source_trial_assignments.csv.gz`

   from `results/bci-calibration-full-v1-3fb8efe7e617b0c1/`. The EA run
   selects trials for calibration/test/source-selection purposes by
   joining against these reused files (keyed on
   `dataset, target_subject, repeat, split_id` /
   `dataset, target_subject, source_subject`), not by re-invoking
   `make_target_split` / `nested_calibration_samples` /
   `choose_source_subjects` / `source_indices_for_subject` against fresh
   RNG state.
2. As a mandatory validation gate (fail closed, run before any model is
   fit), the implementation must **also** regenerate the same four
   artifacts from scratch under the EA config (i.e. actually exercise
   Option A's code path) and assert **exact equality** — same trial UID
   sets, same roles, same nesting, same source subject lists, same
   per-source trial UID sets — between the reused files and the freshly
   regenerated ones. Any mismatch is a hard error that stops the run
   before scoring. This is §3.6 test #6 and #7.
3. This gate serves two purposes simultaneously: it gives the strong
   provenance guarantee of literal reuse (differences in downstream
   metrics can be attributed to alignment, full stop), and it exercises
   the deterministic-seed claim as a live regression check rather than a
   one-time trust decision, so a future refactor that broke seed
   derivation would be caught immediately rather than silently
   invalidating the "same assignments" claim.

---

## 3. Proposed implementation architecture

Nothing below is implemented in this round. It is scoped for a
separately approved implementation round.

### 3.1 Config field(s)

New top-level, backward-compatible section (default `mode: "none"`
reproduces today's behavior exactly, so `configs/full.yaml`,
`configs/sensitivity_three_channels.yaml`, and
`configs/sensitivity_all_sources.yaml` remain valid, unfingerprint-changed,
and unaffected):

```yaml
alignment:
  mode: euclidean_training_only   # "none" (default) | "euclidean_training_only"
  epsilon: 1.0e-12                # SPD eigenvalue floor, reused riemann.py convention
```

`ExperimentConfig` gains
`alignment: AlignmentSection = field(default_factory=AlignmentSection)`.
Because `experiment_fingerprint` already hashes `asdict(self)` in full,
adding this field automatically changes the fingerprint (hence the
output directory) for any config that sets `mode` away from `"none"`,
and leaves every existing config's fingerprint untouched at `mode:
"none"` (dataclass default) — no special-casing needed in
`config.experiment_fingerprint` / `provenance.build_run_manifest`.

No config field is proposed for the assignment-reuse source path (§2.3).
That is treated as a run-time/provenance concern, not a scientific
parameter, and is proposed as a required CLI argument instead (§3.5),
recorded into `run_manifest.json` alongside the rest of the
configuration. This is flagged as an open design choice in §H — a
reviewer may reasonably prefer it as a fingerprinted config field
instead.

### 3.2 Config-schema changes

- `config.py`: new frozen `AlignmentSection` dataclass
  (`mode: Literal["none", "euclidean_training_only"] = "none"`,
  `epsilon: float = 1e-12`).
- `load_config`: add `"alignment"` to the top-level `_check_keys(...)`
  allow-list; add a nested `_expect_mapping`/`_check_keys` block mirroring
  the existing `source`/`classical` handling.
- `ExperimentConfig.validate()`: add `if self.alignment.mode not in
  {"none", "euclidean_training_only"}: raise ValueError(...)`; add
  `if self.alignment.epsilon <= 0: raise ValueError(...)`. No change to
  the existing `budgets_per_class[0] == 0` rule (§1.3 explains why the EA
  config keeps it).

### 3.3 Preprocessing/model pipeline insertion point

EA is inserted in `runner.py`, **upstream of `build_estimator`**, as a
transform on raw epoch arrays (`(trials, channels, samples)`), not inside
`pipelines.py`'s per-method `Pipeline` objects. Rationale: EA is
method-agnostic (applies identically ahead of `logvar_lda`, `csp_lda`,
`riemann_lr`) and dataset-agnostic (operates on whatever channel set the
shard already has — full montage here, but nothing in the transform
hard-codes a channel name or count). Concretely, when
`config.alignment.mode == "euclidean_training_only"`:

- In `_load_source_training`: after `source_indices_for_subject` selects
  a source participant's trial indices (reused from
  `source_trial_assignments.csv.gz` per §2.3) and before those trials are
  appended to `source_X_parts`, estimate that participant's `R_s` from
  exactly those selected trials and replace them with
  `R_s^{-1/2} @ trial` for each selected trial (§1.5).
- In the budget loop (`run_benchmark`'s inner loop over `budget, sample in
  samples.items()`): before building `X_train`/`X_test` for `regime in
  ("subject", "source_plus_target")`, compute `R_target^{-1/2}` once per
  `(dataset, target_subject, repeat, budget)` from `X_calibration` only
  (§1.6), and apply it to both `X_calibration` and `X_test` before they
  enter either regime's training/scoring call (§1.7). Skip `budget == 0`
  entirely (§1.3) — the existing `population`/budget-0 block in
  `run_benchmark` must not execute when `alignment.mode !=
  "none"`.
- New module `src/bci_calibration_benchmark/alignment.py`:
  `estimate_ea_reference(X, epsilon) -> np.ndarray` (returns
  `R^{-1/2}`, reusing `riemann.matrix_power_spd`) and
  `apply_ea_transform(X, reference_invsqrt) -> np.ndarray` (batched
  `reference_invsqrt @ X_i` per trial). Both functions raise `ValueError`
  on empty input (`X.shape[0] == 0`) — this is the concrete mechanism
  behind the budget-0 rejection test (§3.6, test #8): calling
  `estimate_ea_reference` with an empty target-calibration array must
  raise rather than silently return an identity/no-op transform.

### 3.4 Fingerprint and manifest changes

None beyond §3.1's automatic fingerprint change. `provenance.py`'s
`build_run_manifest` already serializes the full `ExperimentConfig`
(`asdict(config)`), so `alignment.mode`/`alignment.epsilon` are captured
for free. `PACKAGES` in `provenance.py` needs no addition (no new
dependency — `alignment.py` only uses `numpy` and the existing
`riemann.matrix_power_spd`).

### 3.5 Condition identifiers and result-output directory naming

- Regime vocabulary is **unchanged**: `subject`, `source_plus_target`
  (`population` is structurally absent from this sensitivity, since it
  only exists at budget 0 — §1.3). "EA subject-only" / "EA
  source-plus-target" in this document's language map directly onto
  these two existing regime strings; no new regime string is introduced.
- A new, additive `alignment_mode` column (constant
  `"euclidean_training_only"` for every row in this run) is added to
  `METRICS_COLUMNS`/`PREDICTION_COLUMNS` **only when
  `config.alignment.mode != "none"`** — i.e. the effective column list is
  computed at run time as `METRICS_COLUMNS + (ALIGNMENT_COLUMNS if
  config.alignment.mode != "none" else [])`, not by editing the shared
  global constants in place. This avoids ever changing the on-disk schema
  of the three closed primary/sensitivity result directories, which
  remain resumable/auditable exactly as they are today; only a *new*
  experiment name (a new output directory) can acquire the new columns.
- Proposed `experiment.name: bci-calibration-ea-training-only-sensitivity`
  (mirrors the existing `bci-calibration-all-sources-sensitivity` /
  `bci-calibration-three-channels` naming convention), giving
  `results/bci-calibration-ea-training-only-sensitivity-<fingerprint>/`
  via the existing `ExperimentConfig.output_dir` property — no naming
  logic changes needed.
- `ConditionKey` (`data_types.py`) is left structurally unchanged
  (`dataset, target_subject, repeat, method, regime, budget_per_class,
  split_id`); directory separation, not an enlarged key, disambiguates EA
  rows from primary rows. `alignment_mode` is carried as a plain metrics
  column for self-description/audit convenience, not as part of the
  dedup/resume key.

### 3.6 Required audit/provenance additions

**New alignment-provenance artifact**, `alignment_provenance.csv.gz`,
written under the EA run's output directory. Two row types (kept as one
file with a `scope` column, or two files — implementation's choice, but
scoped here as one artifact conceptually):

- One row per `(dataset, target_subject)` — source side, repeat-invariant
  (source selection does not depend on `repeat` — see §2.1):
  `dataset, target_subject, source_subject, source_alignment_reference_sha256,
  alignment_config_digest`.
- One row per `(dataset, target_subject, repeat, budget_per_class)` —
  target side: `dataset, target_subject, repeat, split_id,
  budget_per_class, target_calibration_trial_uid_sha256,
  target_alignment_reference_sha256, alignment_config_digest`.

`*_sha256` fields are digests of the canonicalized `R^{-1/2}` matrix
bytes (`utils.fingerprint`-style), not the matrices themselves — per the
task's instruction not to store large redundant covariance matrices, and
matching this codebase's existing convention (`source_selection.csv`
already stores `selected_trial_uid_sha256`, not raw trial data, for the
same reason). `target_calibration_trial_uid_sha256` is a redundant
cross-check against `calibration_assignments.csv.gz`'s own trial set for
that budget (§3.6 test #1's audit hook). `alignment_config_digest =
fingerprint({mode, epsilon})`, one constant value per run, included
per-row for row-level self-containment without needing to cross-reference
`run_manifest.json`.

**Extend `validation.py`'s audit** with a new
`_audit_alignment_provenance` check (mirrors the existing
`_audit_assignments` pattern), asserting:

- every EA metric row has a matching `alignment_provenance` row;
- for a fixed `(dataset, target_subject, repeat, budget_per_class)`, the
  `target_alignment_reference_sha256` referenced by the `subject` regime
  row equals the one referenced by the `source_plus_target` regime row
  (§1.7, test #4);
- `target_calibration_trial_uid_sha256` for a given row equals the
  SHA-256 of the sorted trial-UID set found for that
  `(dataset, target_subject, repeat, split_id, budget_per_class)` in the
  **reused** `calibration_assignments.csv.gz` (§3.6 test #1);
- no `budget_per_class == 0` row exists anywhere in the EA metrics/
  provenance files (§3.6 test #8);
- the reused-vs-regenerated assignment equality gate from §2.3 passed
  (surfaced in `result_audit.json`, not silently swallowed).

**Reused H2-analog statistics must not claim confirmatory status.**
`statistics.build_pairwise_tests` currently hardcodes the family labels
`"H2_regime_low_budget_confirmatory"` /
`"H2_regime_low_budget_dataset_supportive"` (and the analogous H3
labels). If this function is reused unmodified against EA data, its
output would misleadingly claim confirmatory status for a post-hoc
sensitivity — a direct violation of §7's classification requirement.
The implementation must either (a) add a `family_prefix`/`inference_role`
override parameter to `build_pairwise_tests`, or (b) wrap its output and
rename `family` values to something unambiguous, e.g.
`"EA_H2analog_low_budget_exploratory"` /
`"EA_H2analog_low_budget_dataset_descriptive"`, and set
`inference_role` to `"exploratory"` (never `"confirmatory"`) for every
EA-derived row. A regression test must assert no output file produced by
the EA pathway contains the literal substring `"confirmatory"` in any
`family` or `inference_role` value.

**Regression and leakage tests, minimum required set** (new
`tests/test_alignment.py` unless noted; item numbers match the task's
required list):

1. `test_target_alignment_excludes_test_trials` — construct synthetic
   target data where test-role trials are set to extreme/NaN-adjacent
   sentinel values; assert `estimate_ea_reference` over the calibration
   subset is bit-identical whether or not the sentinel test trials are
   present in the full shard (i.e. reference computation provably never
   reads `split.test_idx`-indexed rows).
2. `test_source_alignment_excludes_unselected_trials` — same pattern
   using `source_indices_for_subject`'s excluded (over-cap) trials as the
   sentinel-perturbed set.
3. `test_alignment_references_are_participant_specific` — on synthetic
   multi-participant data with distinct covariance structure per
   participant, assert distinct `*_sha256` digests across participants
   and identical digests across repeated calls for the same participant.
4. `test_target_transform_shared_across_regimes` — for a fixed
   `(dataset, target_subject, repeat, budget)`, assert the
   `target_alignment_reference_sha256` recorded for the `subject` row
   equals the one recorded for the `source_plus_target` row.
5. `test_alignment_is_deterministic` — call
   `estimate_ea_reference`/`apply_ea_transform` twice on identical input
   and assert bit-identical (`np.array_equal`, not `allclose`) output;
   run an end-to-end single condition twice and assert identical stored
   hashes and metrics.
6. `test_ea_run_reuses_primary_assignment_files` — assert the four reused
   assignment files' trial-UID/role/nesting content, loaded from the EA
   run's provenance, matches the primary run's files exactly for every
   `(dataset, target_subject, repeat)` / `(dataset, target_subject,
   source_subject)` key. Add a config-level companion test in
   `tests/test_config.py`, mirroring the existing
   `test_confirmatory_and_sensitivity_configs_use_ten_nested_calibration_repeats`
   pattern: assert the (not-yet-created)
   `configs/sensitivity_ea_training_only.yaml`'s `experiment.seed`,
   `datasets`, `split`, and `calibration` sections are **identical** to
   `configs/full.yaml`'s (only `experiment.name`, `alignment`, and
   `experiment.output_root`/naming may differ).
7. `test_audit_detects_assignment_drift` — mutate one trial UID (or one
   `target_alignment_reference_sha256`) in a copied assignment/provenance
   file and assert the §2.3/§3.6 equality gate and
   `audit_result_integrity`-style check raise / report `status: "failed"`
   rather than passing silently.
8. `test_alignment_rejects_budget_zero` — assert
   `estimate_ea_reference(np.empty((0, C, T)), epsilon)` raises
   `ValueError`; assert an end-to-end config/condition-grid check for
   `alignment.mode == "euclidean_training_only"` never contains
   `budget_per_class == 0` (extend the `_expected_condition_frame`-style
   completeness check in `validation.py` for the EA path to assert this
   directly, not merely by omission).

A ninth test worth including for numerical parity with the rest of the
codebase, not required by the task but low-cost: `test_alignment_epsilon_floor`
— near-singular synthetic `R` (rank-deficient calibration subset) does
not raise or produce non-finite output, mirroring
`tests/test_riemann.py`'s existing near-singular coverage.

### 3.7 Genericity / fail-closed constraints (explicit, per task instruction)

- No channel name (`C3`/`Cz`/`C4`), dataset name, or subject ID appears
  in `alignment.py`, `AlignmentSection`, or any new runner branch. The
  transform operates on `(trials, channels, samples)` arrays and integer
  indices only.
- No condition-specific value (a specific budget, method, or regime
  string) is hard-coded inside `estimate_ea_reference` /
  `apply_ea_transform`; budget-0 rejection is enforced by the *emptiness*
  of the input array, not by comparing a budget number.
- Every new validation described above fails the run (raises), rather
  than warning and continuing, consistent with the confirmatory
  protocol's existing `continue_on_error: false` convention and
  `validation.py`'s existing "raise, don't downgrade to a warning" style.

### 3.8 Files likely to require modification (implementation round only)

- `src/bci_calibration_benchmark/config.py` — `AlignmentSection`, schema
  checks, `validate()`.
- `src/bci_calibration_benchmark/alignment.py` — **new**.
- `src/bci_calibration_benchmark/runner.py` — insertion points in
  `_load_source_training` and the budget loop; conditional column list;
  budget-0 skip; alignment-provenance writer.
- `src/bci_calibration_benchmark/validation.py` — new
  `_audit_alignment_provenance`; EA-aware condition-completeness check.
- `src/bci_calibration_benchmark/statistics.py` — `family_prefix`/
  `inference_role` override for `build_pairwise_tests` (or an equivalent
  wrapper kept out of `statistics.py` entirely — implementer's choice, but
  the "no output says confirmatory" invariant is mandatory either way).
- `src/bci_calibration_benchmark/aggregate.py` — orchestration for the EA
  output set (curve summary, EA-labeled pairwise tests; mixed-effects
  fitting is **not** requested for EA by this spec and should stay off
  unless a future round asks for it).
- `src/bci_calibration_benchmark/cli.py` — assignment-reuse source
  argument (§3.1).
- `configs/sensitivity_ea_training_only.yaml` — **new**, not created in
  this round.
- `tests/test_alignment.py` — **new**. Extensions to `tests/test_config.py`,
  `tests/test_runner_end_to_end.py`, `tests/test_validation.py`,
  `tests/test_statistics.py`.
- `docs/DECISIONS.md` — a dated entry recording this as a post-hoc,
  reviewer-motivated addition (not created in this round).

---

## 4. Planned EA outputs

### 4.1 Expected condition count

```
65 participants × 10 repeats × 3 methods × 2 regimes × 4 positive budgets
  = 65 × 10 × 3 × 2 × 4
  = 15,600 metric rows
```

Contrast with the primary run's 19,500 (`65 × 10 × 3 × 10
conditions/repeat`, where the 10 = 2 budget-0 regimes +
4 positive budgets × 2 regimes). The EA run has 8 conditions/repeat/method
instead of 10 (no `population`, no budget 0 for either regime), i.e.
`65 × 10 × 3 × 8 = 15,600` — consistent.

Expected prediction-row count, derivable from reused assignments (§2):
since every condition at a given `(dataset, target_subject, repeat)`
shares the same `test_trials` count regardless of budget/regime/method,
and the primary run's 19,500 conditions produced 2,068,800 prediction
rows (`docs/sensitivity_run_acceptance.md`), the EA run's expected count
is `2,068,800 × (8/10) = 1,655,040`. This is a checkable arithmetic
prediction to validate against the reused assignment files at
implementation time, not a measured result.

### 4.2 Expected outputs

- `metrics.csv`, `predictions.csv.gz` (schema: existing columns +
  `alignment_mode`, §3.5).
- `alignment_provenance.csv.gz` (§3.6, new).
- Reused-not-regenerated copies/joins of `split_assignments.csv.gz`,
  `calibration_assignments.csv.gz`, `source_selection.csv`,
  `source_trial_assignments.csv.gz` (§2.3), plus the regenerated
  cross-check artifacts consumed only by the equality gate (need not be
  persisted long-term if the gate passes; if persisted, prefixed
  `_regenerated_check_*` to avoid ambiguity with the reused files).
- `run_manifest.json`, `result_audit.json` (existing machinery, extended
  per §3.6).
- Calibration curves at budgets 5/10/20/40 for both EA regimes (existing
  `plotting.py`/figure machinery, reused).
- Participant-level summaries (`summary_subject.csv`-equivalent, via
  existing `aggregate_repeats`).
- Paired `EA source_plus_target − EA subject` contrasts at 5 and 10
  trials/class (relabeled per §3.6), plus descriptive trajectory/
  persistence summaries at 20/40.
- A comparison against the unaligned primary result (§4.3).
- A concise manuscript/supplement artifact package, mirroring
  `manuscript/artifacts/sensitivity_analysis/`'s existing
  factual-comparison style (`sensitivity_comparison.md`-equivalent, e.g.
  `manuscript/artifacts/ea_sensitivity/ea_comparison.md`) — not created in
  this round.

### 4.3 Comparing EA to the unaligned primary result without creating a new outcome-driven testing family

Reuse the same **factual-comparison** pattern already established by
`manuscript/artifacts/sensitivity_analysis/sensitivity_comparison.md` for
the two prespecified sensitivities: read both runs' already-computed,
already-audited `pairwise_tests.csv` files directly; perform **no new
hypothesis test** comparing EA to primary (no test-of-tests, no
meta-analysis, no Holm family spanning both runs). Report, for each
method × budget in `{5, 10}` (primary contrast) and descriptively for
`{20, 40}`:

- **Direction:** does EA's `source_plus_target − subject` sign match the
  primary (unaligned) run's sign?
- **Magnitude:** EA's mean paired difference vs. primary's, and the
  signed delta between them.
- **Confidence interval:** EA's participant-bootstrap CI vs. primary's;
  whether either crosses zero.
- **Persistence to higher budgets:** whether a direction/significance
  pattern seen at 5/10 persists, attenuates, or reverses by 20/40.
- **Dataset/method dependence:** per-dataset supportive contrasts,
  exactly as `sensitivity_comparison.md` already reports for
  three-channel/all-source, so a pooled EA claim cannot conceal an
  opposite per-dataset direction (this mirrors
  `docs/STATISTICAL_ANALYSIS.md`'s existing "no pooled curve is allowed
  to conceal an opposite direction" principle).

This labeling discipline is exactly the one already used for the two
prespecified sensitivities — extending it to EA does not require
inventing a new comparison methodology, only applying the existing one
to a third run.

---

## 5. Three non-benchmark robustness analyses

All three reuse **only** the primary run's existing audited outputs
(`summary_subject.csv`, `aucc_subject.csv`, `metrics.csv` under
`results/bci-calibration-full-v1-3fb8efe7e617b0c1/`). None re-runs
`run_benchmark.py`, none touches the primary directory's existing files,
and none is executed in this round — this section specifies what a later
round would compute. Proposed output location: a new, additive
subdirectory `results/bci-calibration-full-v1-3fb8efe7e617b0c1/post_confirmatory_robustness/`
(read from, never written into, the primary directory's existing files).

### 5.A Without-Zhou pooled re-aggregation

Filter `summary_subject.csv`/`aucc_subject.csv` to `dataset !=
"Zhou2016"` (N: 65 → 63, i.e. `54 + 9`), then recompute the identical
pooled H2/H3 summaries by calling the **same** `statistics.
build_pairwise_tests` machinery already used for the primary analysis
against this filtered frame and the same `configs/full.yaml`-derived
`ExperimentConfig` (statistical settings — bootstrap resamples, CI level,
pairwise budgets — are unchanged; only the participant set entering
`_scope_iter`'s `"ALL"` pool changes). The primary N=65 analysis and its
files are not modified. Output labeled explicitly `without_zhou_robustness`
throughout (directory name, `family` values, any figure/table caption) —
never `confirmatory`.

### 5.B Random-intercept-only mixed-model sensitivity

Use the identical 1,560 positive-budget participant observations
(`subject_summary` filtered exactly as `statistics.fit_mixed_effects`
already filters it: `regime in {subject, source_plus_target}`,
`budget_per_class > 0`) and the identical fixed-effects formula
(`roc_auc ~ log2_budget * C(method) * C(regime) + C(dataset)`). Extract
`fit_mixed_effects`'s per-attempt model-fitting body into a small
reusable helper (e.g. `_fit_single_mixed_model(formula, data, groups,
re_formula)`) so this sensitivity can call it directly with
`re_formula="1"` (random intercept only) **as a deliberate, always-run
comparison**, not as the existing convergence-triggered fallback path
(`statistics.fit_mixed_effects` already falls back to intercept-only
*only on non-convergence* of the intercept+slope model — this sensitivity
is a different, always-computed comparison of both structures side by
side, run regardless of whether the intercept+slope model converged).
Report both models' fixed-effect coefficient tables side by side, with
particular attention to the `log2_budget:C(regime)[T.subject]`
interaction term (the task's "`log2(budget+1) × subject-only regime`"
term — the slope difference between the subject-only and
source-plus-target regimes). No model is selected based on which is
"more significant" — both are reported; the original random-intercept
+ random-slope model in the primary run's own
`mixed_effects_coefficients.csv` remains the analysis of record.

### 5.C Fraction of participants benefiting from population data

Purely descriptive, computed directly from `summary_subject.csv`
(already repeat-averaged per participant by `aggregate_repeats`). For
each method and budget in `{5, 10, 20, 40}`: pivot
`source_plus_target`/`subject` ROC-AUC per participant, compute the
proportion with `ROC-AUC(source_plus_target) > ROC-AUC(subject)`. Report
pooled (N=65) and per-dataset fractions where a dataset's participant
count makes the fraction meaningful (flagging `Zhou2016`, N=2, as
descriptive-only, consistent with existing precedent for that dataset —
`docs/DECISIONS.md`, `sensitivity_comparison.md`). No p-values are
computed for this analysis; it is explicit descriptive engineering
communication.

---

## 6. Manuscript integration notes (wording only — not applied)

### 6.1 H2/H3 numbering

Currently, `docs/ANALYSIS_PLAN.md` §14 introduces "H2" and "H3" directly
(no "H1" ever appears anywhere in the repository — confirmed by
inspection). Recommended footnote/parenthetical for first manuscript use
of either label:

> "H2 and H3 label the two pre-specified confirmatory inferential
> families in the frozen analysis plan (`docs/ANALYSIS_PLAN.md`) and
> follow the numbering of Research Questions 2 and 3 there; no separate
> H1 confirmatory family was pre-specified."

### 6.2 Abstract wording

The reviewer-flagged phrase appears verbatim in
`manuscript/artifacts/sensitivity_analysis/sensitivity_comparison.md:20`
("the same 65 **structurally validated participants**") and the related
unexplained "67 nominal participants" appears in
`manuscript/outline.md`'s abstract-structure bullet 3. Recommended
replacement, usable in the abstract and anywhere else this phrase
recurs:

> "...three public datasets; 65 of 67 nominal participants satisfying the
> pre-specified session, run, channel, and trial-count requirements
> (Lee2019_MI 54, BNCI2014_001 9, Zhou2016 2; two Zhou2016 participants
> were excluded before any model was fit, for a documented per-session
> trial-count shortfall — see `docs/DECISIONS.md`)..."

and, for the shorter recurring phrase used in `sensitivity_comparison.md`-
style factual tables:

> "...the same 65 participants who satisfied the prespecified session,
> run, channel, and trial-count eligibility requirements..."

replacing "structurally validated participants" everywhere it recurs
without an inline gloss.

### 6.3 BNCI2014_001 Riemannian negative transfer

Verified directly against the primary run's audited
`pairwise_tests.csv` (`results/bci-calibration-full-v1-3fb8efe7e617b0c1/`),
`H2_regime_low_budget_dataset_supportive` rows, `riemann_lr`,
`BNCI2014_001`:

| Budget | Mean Δ ROC-AUC (source+target − subject) | 95% CI | p |
|---|---|---|---|
| 5 | −0.053 | [−0.132, +0.021] | 0.359 |
| 10 | −0.068 | [−0.132, −0.009] | 0.074 |

Recommended wording:

> "In BNCI2014_001, subject-only Riemannian tangent-space decoding
> exceeded pooled source-plus-target retraining at both calibrated
> low budgets tested (dataset-specific, supportive contrast: mean
> ΔROC-AUC = −0.053 at 5 trials/class, 95% CI [−0.132, +0.021]; −0.068 at
> 10 trials/class, 95% CI [−0.132, −0.009]), illustrating that population
> information can be conditionally unhelpful rather than uniformly
> beneficial. This dataset-specific estimate is supportive, not
> independently confirmatory, per the pre-specified participant-weighted
> pooling scheme (`docs/STATISTICAL_ANALYSIS.md`)."

### 6.4 Deep-model limitation

Recommended wording, consistent with `docs/ANALYSIS_PLAN.md` §10.4 and
`docs/DECISIONS.md`'s existing "Classical confirmatory core" entry:

> "Classical, deterministic decoders (log-variance + LDA, CSP + LDA,
> Riemannian tangent-space + logistic regression) were used throughout to
> isolate calibration-regime effects under a fully auditable,
> hyperparameter-frozen training procedure. An EEGNet adapter is present
> in the codebase but was not exercised in this protocol; deep and
> foundation-model transfer approaches require a separate tuning,
> convergence, and validation protocol (training-only early stopping,
> seed sensitivity, compute-budget controls) before they can be compared
> under this estimand. Their omission here should not be read as evidence
> that they would not benefit differently from population pretraining or
> from Euclidean Alignment."

---

## 7. Classification and provenance

| Analysis | Classification | Basis |
|---|---|---|
| Primary full analysis (`configs/full.yaml`) | **Confirmatory** | Frozen `docs/ANALYSIS_PLAN.md`, executed and closed per `docs/full_run_acceptance.md`. |
| Three-channel montage sensitivity | **Prespecified sensitivity** | `docs/ANALYSIS_PLAN.md` §17 item 1; closed per `docs/sensitivity_run_acceptance.md`. |
| All-source sensitivity | **Prespecified sensitivity** | `docs/ANALYSIS_PLAN.md` §17 item 2; closed per `docs/sensitivity_run_acceptance.md`. |
| Euclidean Alignment sensitivity (this spec, §1–4) | **Post-confirmatory exploratory robustness** | Motivated by a post-outcome reviewer critique, not present anywhere in `docs/ANALYSIS_PLAN.md`. Never to be retroactively described as prespecified, regardless of its results. |
| Without-Zhou pooled re-aggregation (§5.A) | **Post-confirmatory robustness** | Re-aggregation of already-audited primary outputs under a different participant filter; not a new data collection or model fit. |
| Random-intercept-only mixed model (§5.B) | **Model-form robustness** | A deliberate alternative random-effects structure on the identical primary observations/formula, reported alongside (not replacing) the primary model. |
| Fraction-benefiting analysis (§5.C) | **Descriptive exploratory summary** | No inferential test; a proportion computed from already-audited participant-level outcomes. |

No item in this table may be relabeled based on how any of these
analyses' results turn out. This mirrors the existing discipline in
`docs/DECISIONS.md` ("must not be revisited based on how any decoder
performs") applied to the classification labels themselves.

---

## 8. Final response

### A. READY FOR HUMAN SPECIFICATION REVIEW

This document specifies but does not implement, execute, configure, or
commit anything. Human approval is requested before any implementation
round begins.

### B. Exact proposed EA estimand and transformation

Post-confirmatory exploratory contrast: `EA source_plus_target − EA
subject`, ROC-AUC, at 5 and 10 trials/class (primary), descriptive at 20
and 40. Transform: `R = mean_i(X_i X_i^T / n_samples)`,
`X_aligned = R^{-1/2} X`, no additional trial centering, eigenvalue floor
`1e-12`, computed via reused `riemann.matrix_power_spd`. Source-side `R`
per selected source participant from that participant's selected trials
only; target-side `R` per `(dataset, target_subject, repeat, budget ∈
{5,10,20,40})` from that condition's calibration subset only, applied
frozen to both calibration and test trials, shared identically across
both compared regimes. Budget 0 is undefined and rejected for every EA
regime (§1.3).

### C. Test-data leakage boundary

Target test trials may be **transformed** by the frozen target reference
but must **never contribute to estimating** any reference (target or
source). This is enforced by construction (the reference estimator only
ever receives the calibration-subset array) and is directly tested
(§3.6, test #1) rather than asserted only by design.

### D. Assignment-reuse/matching strategy

Option B: explicit reuse of the primary run's four assignment artifacts
(`split_assignments.csv.gz`, `calibration_assignments.csv.gz`,
`source_selection.csv`, `source_trial_assignments.csv.gz`), with a
mandatory fail-closed equality gate against a from-scratch regeneration
(Option A's deterministic-seed mechanism, cross-checked rather than
trusted). Rationale and code-level evidence in §2.

### E. Expected condition count

15,600 metric rows (`65 × 10 × 3 × 2 × 4`); ~1,655,040 expected
prediction rows, derived arithmetically from the primary run's reused
assignments (§4.1) — to be validated, not assumed, at implementation
time.

### F. Files that would be modified in the later implementation round

`src/bci_calibration_benchmark/config.py`,
`src/bci_calibration_benchmark/alignment.py` (new),
`src/bci_calibration_benchmark/runner.py`,
`src/bci_calibration_benchmark/validation.py`,
`src/bci_calibration_benchmark/statistics.py`,
`src/bci_calibration_benchmark/aggregate.py`,
`src/bci_calibration_benchmark/cli.py`,
`configs/sensitivity_ea_training_only.yaml` (new),
`tests/test_alignment.py` (new),
`tests/test_config.py`, `tests/test_runner_end_to_end.py`,
`tests/test_validation.py`, `tests/test_statistics.py`,
`docs/DECISIONS.md`. Full detail in §3.8.

### G. Proposed tests

Eight required tests plus one optional numerical-parity test, listed in
full in §3.6, covering: test-trial exclusion from target-reference
estimation; excluded-source-trial exclusion from source-reference
estimation; participant-specificity of references; shared target
transform across regimes; determinism; exact assignment-reuse identity;
detection of a genuinely altered assignment/reference hash; and hard
rejection of budget 0.

### H. Unresolved design decisions requiring human approval

1. **Assignment-reuse plumbing:** CLI argument (this spec's default
   recommendation, §3.1/§3.5) vs. a fingerprinted config field pointing
   at the primary output directory. The CLI choice keeps the config
   "scientific-parameters-only" but is less self-contained in a single
   fingerprinted artifact; a config field is more self-contained but
   couples the EA config's fingerprint to a specific primary run's
   directory path. Either is defensible; this spec picked the CLI option
   but flags it explicitly for reviewer override.
2. **Covariance normalization constant** (`/n_samples`, §1.4): a
   disclosed, justified deviation from the literal unnormalized He–Wu
   formula, chosen for numerical-scale consistency with this codebase's
   existing `OASCovariances` convention. A reviewer preferring the
   literal unnormalized form should say so before implementation; the
   deviation is scale-only and provably cannot differentially affect
   participants/methods/regimes within this study (fixed epoch length
   throughout), but "provably cannot differentially affect" is a
   mathematical claim this document makes, not yet a claim any test
   verifies — that verification should be added as part of
   implementation, not asserted from the spec alone.
3. **Alignment-provenance file layout:** one combined
   `alignment_provenance.csv.gz` with a `scope` column vs. two separate
   files (source-side, repeat-invariant; target-side, per-repeat/budget)
   — §3.6 leaves this as an implementer's choice; a reviewer with a
   preference should state it.
4. **Mixed-effects model for EA data:** this spec does not request a
   mixed-effects model fit on the EA metrics (only paired contrasts and
   descriptive trajectories, §1.8/§4.2). Confirm this scope is correct
   before implementation — extending `fit_mixed_effects` to the EA run
   would be a small addition if wanted, but was not asked for in the
   task and is deliberately left out to avoid inventing a new inferential
   family beyond what was requested.

### I. Git status and diff stat

```
$ git status
On branch alignment_sensitivity
Your branch is up to date with 'origin/alignment_sensitivity'.

Untracked files:
  (use "git add <file>..." to include in what will be committed)
        docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md

nothing added to commit but untracked files present (use "git add" to track)

$ git diff --stat
(no output — no tracked file was modified)
```

No file was committed or pushed. This is the only file created in this
round.
