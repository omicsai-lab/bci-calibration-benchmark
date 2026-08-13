# Debugging log: bringing the pilot workflow to a reproducible working state

Scope: the eight-command pilot workflow (`validate_environment` → `pytest` →
`run_smoke_test` → `prepare_data` → `validate_data` → `run_benchmark` →
`audit_results` → `aggregate_results` → `make_figures`) on real public EEG
data (`Lee2019_MI`, `BNCI2014_001`, `Zhou2016`), macOS, Python 3.11.15,
`moabb==1.5.0`, `mne==1.12.1`.

Two issues (MOABB `n_jobs` and `MotorImagery`/`LeftRightImagery`) had already
been resolved in the working tree before this session; they are recorded
here for completeness since they were part of the original brief.

---

## 1. `paradigm.get_data(..., n_jobs=...)` — TypeError

**Error encountered**

```text
TypeError: BaseProcessing.get_data() got an unexpected keyword argument 'n_jobs'
```

**Root cause**

Confirmed by introspection (`inspect.signature(BaseProcessing.get_data)`
against the installed `moabb==1.5.0`): `get_data` no longer accepts
`n_jobs`. This is an upstream MOABB API change, not a bug in our code.

**Change made**

`src/bci_calibration_benchmark/datasets.py::prepare_subject` — removed the
`n_jobs=config.runtime.n_jobs_data` argument from the `paradigm.get_data(...)`
call (the line had already been commented out; this session deleted the
dead comment rather than leaving it in the source).

**Scientific consequence**

None. `runtime.n_jobs_data` remains a validated config field (data
preparation is single-process for this MOABB version); no preprocessing,
split, or estimator behavior changed.

**Verification**

```bash
python -c "import inspect; from moabb.paradigms.base import BaseProcessing; print(inspect.signature(BaseProcessing.get_data))"
python -m pytest tests/test_datasets.py
```

---

## 2. `MotorImagery(events=["left_hand", "right_hand"])` — TypeError

**Error encountered** (interactive/exploratory code, not present in the
committed pipeline)

```text
TypeError: '<' not supported between instances of 'int' and 'NoneType'
```

**Root cause**

`MotorImagery.__init__` defaults `n_classes=None`; passing `events=` without
`n_classes` leaves an internal comparison undefined. Confirmed via
`inspect.signature(MotorImagery.__init__)` and `inspect.signature(LeftRightImagery.__init__)`.

**Decision**

The pipeline (`datasets.py::_import_moabb_objects` /
`prepare_subject`) already uses `moabb.paradigms.LeftRightImagery`, which
takes no `events`/`n_classes` arguments at all and is semantically identical
to `MotorImagery(n_classes=2, events=["left_hand", "right_hand"])` for every
configured dataset (`Lee2019_MI`, `BNCI2014_001`, `Zhou2016` all define
`left_hand`/`right_hand` events). No code change was needed; this is
recorded as confirmation that the existing choice is correct and should not
be changed to `MotorImagery(...)`.

**Scientific consequence**

None (confirmatory only).

---

## 3. `Lee2019_MI: expected 2 sessions, observed 1`

**Error encountered**

```text
ValueError: Lee2019_MI: expected 2 sessions, observed 1: ['1']
```

**Investigation**

Direct introspection against the installed `moabb==1.5.0`:

```python
>>> from moabb.datasets import Lee2019_MI
>>> ds = Lee2019_MI(train_run=True, test_run=False, resting_state=False)
>>> ds.n_sessions
2
>>> ds._get_single_subject_data(1).keys()
dict_keys(['0', '1'])          # both sessions present at this layer
>>> ds.get_data(subjects=[1])[1].keys()
dict_keys(['1'])               # only one session survives get_data()
```

Root cause, traced through `moabb/datasets/Lee2019.py` and
`moabb/datasets/base.py`:

- `Lee2019._get_single_subject_data` names each subject's per-session data
  with the **0-indexed** string `str(session - 1)`, i.e. `"0"` and `"1"`,
  for the two raw sessions.
- `Lee2019.__init__` forwards its **1-indexed** `sessions` constructor
  argument (`(1, 2)` by default) to `BaseDataset.__init__(selected_sessions=sessions)`,
  which stores it verbatim as `self._selected_sessions`.
- `BaseDataset.get_data` post-filters the returned session dict with:
  `str_sessions = {str(s) for s in effective_sessions}` → `{"1", "2"}`,
  then keeps only `k in str_sessions`. Against keys `{"0", "1"}` this keeps
  only `"1"` and silently drops the entire first session for every subject.

This reproduces unconditionally (it does not depend on our `train_run`/
`test_run`/`resting_state` kwargs, and cannot be avoided by passing a
different `sessions=` value to the constructor, since `Lee2019.__init__`
rejects any session value not in `[1, 2]`). It is a genuine MOABB 1.5.0 bug
specific to `Lee2019`'s 0-indexed internal session-key convention colliding
with `BaseDataset`'s generic 1-indexed `selected_sessions` filter.
`BNCI2014_001` and `Zhou2016` were checked and do not exhibit this
(`_selected_sessions` is `None` for both by default, so the buggy filter
never engages).

**Change made**

`src/bci_calibration_benchmark/datasets.py` — added
`_instantiate_public_dataset(dataset_name, dataset_class, constructor_kwargs)`,
used at both dataset-construction call sites (`prepare_subject`,
`prepare_dataset`). For `Lee2019_MI` only, after construction it asserts
`dataset._selected_sessions == [1, 2]` (the exact known-buggy state) and
then sets `dataset._selected_sessions = None`, which disables the
buggy post-hoc filter. `DATASET_EXPECTATIONS["Lee2019_MI"].sessions == 2`
already required the full two-session protocol, so this restores rather than
changes the intended protocol. If a future MOABB release changes this
representation, the guard raises `RuntimeError` instead of silently
re-dropping data.

**Scientific consequence**

Corrects a silent data-loss bug that would otherwise have discarded every
subject's first (chronologically earliest) session and made the
`latest_session_only` calibration/test split structurally impossible for
`Lee2019_MI`. Preserves the prespecified design; does not change the
estimand, eligible sample, preprocessing, or statistical analysis.

**Verification**

```bash
python -m pytest tests/test_datasets.py -v   # includes 3 new regression tests
python scripts/prepare_data.py --config configs/pilot.yaml
python scripts/validate_data.py --config configs/pilot.yaml   # Lee2019_MI subjects show sessions=2
```

New tests: `tests/test_datasets.py::test_lee2019_session_workaround_neutralizes_selected_sessions`,
`::test_lee2019_session_workaround_fails_loudly_if_moabb_changes`,
`::test_non_lee2019_datasets_are_untouched_by_the_session_workaround`.

---

## 4. `Zhou2016 session 1: expected at least 50 trials per class, observed {0: 45, 1: 45}`

**Error encountered** during `prepare_data.py`, on Zhou2016 subject 2.

**Investigation**

The Zhou2016 protocol (per the MOABB dataset docstring and metadata: 3
sessions/subject, 2 runs/session, 25 trials/class/run → 50 trials/class/
session) is what `DATASET_EXPECTATIONS["Zhou2016"].minimum_trials_per_class_per_session = 50`
pins. Direct inspection of the raw BIDS release (bypassing any MOABB/paradigm
processing) via `mne.events_from_annotations` on each subject/session/run:

```text
subject 1: session0 run0/run1 = 30/30, 30/29     (session0 30+30/session1 25+25/session2 25+25)
subject 2: session0 25/25, session1 25+20, session2 25/25   <-- session1/run1 short
subject 3: all sessions/runs = 25/25
```

Subject 2's session-1/run-1 recording contains only 20 trials/class instead
of 25, and its recorded duration is correspondingly shorter (702 s vs.
~850-910 s for every other run in the cohort) — a genuine acquisition-time
shortfall in the publicly released recording itself, not a MOABB version
issue, an event-coding issue, or a bug in our pipeline. (The published paper
this dataset comes from is itself about automated trial-selection/exclusion,
consistent with per-subject trial-count variability in the release.)

**Decision**

The strict per-session floor in `validate_subject_structure` was **not**
weakened — it correctly caught a genuine structural shortfall and this is
exactly the "fail closed" behavior it exists for. Instead, subject 2 was
removed from the Zhou2016 pilot cohort in `configs/pilot.yaml`
(`subjects: [1, 3]`, was `[1, 2, 3]`, with an inline comment recording the
reason and the verification method), leaving 2 subjects — the minimum
required by `runner.py::_configured_subjects` for source/target
disjointness. `configs/full.yaml` and the `sensitivity_*.yaml` configs
request `subjects: all` for Zhou2016 and were **not** modified; they will
hit the same structural failure and need the same documented per-subject
decision (exclude subject 2, or a separately pre-registered protocol
decision about the minimum-session floor) before a full-scale run. See
"Remaining concerns" in the final summary.

**Scientific consequence**

Changes the eligible sample for the pilot only (`configs/pilot.yaml`,
explicitly marked non-inferential/compute-validation-only in that file's
header comment). Does not change the estimand, preprocessing, or
statistical analysis, and does not touch the validation logic that
protects the confirmatory design.

**Verification**

```bash
python -c "from bci_calibration_benchmark.config import load_config; c = load_config('configs/pilot.yaml'); print(c.datasets)"
python scripts/prepare_data.py --config configs/pilot.yaml
python scripts/validate_data.py --config configs/pilot.yaml
```

---

## 5. `audit_results.py`: stored `log_loss` differs from recomputed value by ~1e-11

**Error encountered**

```text
ValueError: Stored log_loss differs from predictions for {...}: stored=6.25164510254628, recomputed=6.251645102536929
```

**Investigation**

`audit_result_integrity` (`validation.py::_audit_predictions`) recomputes
every metric directly from the stored `predictions.csv.gz` and compares it
against `metrics.csv` with `np.allclose(..., rtol=1e-12, atol=1e-12)` — an
intentionally strict, near-bit-exact check. Isolated the discrepancy to CSV
float parsing:

```python
>>> pd.read_csv(path)["y_score"]                                    # default parser
0.9999999999999708
>>> pd.read_csv(path, float_precision="round_trip")["y_score"]      # exact
0.9999999999999707
```

`pandas.read_csv`'s default C float parser (`float_precision=None`) is not
guaranteed to round-trip a decimal literal to its exact original float64 bit
pattern; for this condition 43 of 100 `y_score` values differed from the
source text by 1 ULP (~1.1e-16). `compute_binary_metrics` (`metrics.py`)
clips probabilities to `[1e-7, 1 - 1e-7]` before `log_loss`; near that
boundary, `log_loss`'s `1/p` derivative amplifies a 1-ULP input error by a
factor of up to ~1e7, turning imperceptible parsing noise into an ~1e-11
absolute difference in the aggregate `log_loss` — enough to fail the
audit's `1e-12` tolerance. Reproduced directly:

```python
pd.read_csv(path)                              # default -> log_loss = 6.251645102536929
pd.read_csv(path, float_precision="round_trip") # exact   -> log_loss = 6.25164510254628 (matches stored)
```

This was a genuine bug in our code (an under-specified `pd.read_csv` call),
not a scientific or protocol issue, and not evidence of any actual
non-determinism in model fitting/prediction.

**Change made**

- `src/bci_calibration_benchmark/validation.py::_read_csv` — defaults to
  `float_precision="round_trip"` (via `kwargs.setdefault`, so any explicit
  caller override is still respected). This is the single read helper used
  throughout `audit_result_integrity` for `metrics.csv`, `predictions.csv.gz`,
  and the assignment CSVs.
- `src/bci_calibration_benchmark/aggregate.py::aggregate_run` — the
  standalone `metrics = pd.read_csv(metrics_path, ...)` read (used when
  `audit_result_integrity` is invoked from `aggregate_results`, which
  supplies an already-loaded `metrics` frame rather than re-reading it) now
  also passes `float_precision="round_trip"`, so both call paths
  (`audit_results` standalone and `aggregate_results`) compare consistently
  parsed values.

`runner.py`'s resume-time CSV reads were intentionally left unchanged: they
only use string/int key columns (dataset, subject, repeat, method, regime,
budget, split_id) for resume bookkeeping, never the float metric columns, so
they carry no precision risk.

**Scientific consequence**

None on the underlying computation — model fitting, prediction, and the
originally stored `metrics.csv` values are untouched. This only fixes how
metrics are *re-read from disk* for audit/aggregation, making the "recompute
from predictions and compare" integrity check actually exact rather than
spuriously failing on immaterial parsing noise. Confirms, rather than
weakens, the audit's strict reproducibility guarantee.

**Verification**

```bash
python -m pytest tests/test_validation.py -v   # new: test_read_csv_round_trips_floats_exactly
python scripts/run_benchmark.py --config configs/pilot.yaml
python scripts/audit_results.py --config configs/pilot.yaml    # status: ok
python scripts/aggregate_results.py --config configs/pilot.yaml
```
