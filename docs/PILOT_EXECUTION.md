# Public-data pilot execution

The pilot validates adapters, storage, compute, and audit logic. It is not a miniature inferential study and its performance estimates must not appear as manuscript results.

## 1. Environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
python scripts/validate_environment.py --config configs/pilot.yaml
python -m pip freeze --all > requirements/pilot-environment-freeze.txt
```

Record operating system, CPU, RAM, free disk, and the MOABB cache location.

## 2. Software validation

```bash
pytest
python scripts/run_smoke_test.py --workspace .smoke-work
```

Both must complete before public downloads.

## 3. Download and process

```bash
python scripts/prepare_data.py --config configs/pilot.yaml
python scripts/validate_data.py --config configs/pilot.yaml
```

The pilot selects three participants per dataset. Inspect the generated validation table for session, run, class, montage, sample, and peak-to-peak summaries.

## 4. Run and audit

```bash
python scripts/run_benchmark.py --config configs/pilot.yaml
python scripts/audit_results.py --config configs/pilot.yaml
python scripts/aggregate_results.py --config configs/pilot.yaml
python scripts/make_figures.py --config configs/pilot.yaml
```

The audit must return `status: ok` before aggregation is considered valid.

## 5. Manual checks

For at least one participant per dataset, independently inspect:

- trial metadata and event labels;
- session order;
- test-session identity;
- class counts by session;
- selected channel names;
- one nested calibration sequence;
- one source-trial selection;
- one recomputed ROC-AUC from prediction rows.

Plot representative C3/C4 spectra or time-frequency summaries only as quality control. Do not tune the confirmatory band/window from pilot classifier outcomes.

## 6. Acceptance record

Create `pilot_acceptance.md` containing:

- date and commit;
- config fingerprint;
- environment freeze path;
- dataset-manifest hashes;
- audit report;
- runtime and peak memory by method/dataset;
- download size;
- deviations and their resolution;
- explicit go/no-go decision.

A no-go decision is scientifically acceptable. It is preferable to an undocumented workaround.

## 7. Full-run sequence

After acceptance:

```bash
python scripts/prepare_data.py --config configs/full.yaml
python scripts/validate_data.py --config configs/full.yaml
python scripts/run_benchmark.py --config configs/full.yaml
python scripts/audit_results.py --config configs/full.yaml
python scripts/aggregate_results.py --config configs/full.yaml
python scripts/make_figures.py --config configs/full.yaml
```

Then run the pre-specified `C3/Cz/C4` and all-source sensitivities. Never modify the full config in place after viewing outcomes; create a new versioned config.
