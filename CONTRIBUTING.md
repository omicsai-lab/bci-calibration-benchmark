# Contributing

This is a scientific-analysis repository. A change to preprocessing, dataset selection, split policy, calibration sampling, source cohort, estimator, endpoint, exclusion rule, or statistical analysis is a protocol change—not a cosmetic refactor.

## Change classes

- **Protocol-preserving:** implementation or documentation change that leaves every scientific estimand and condition unchanged.
- **Sensitivity-only:** adds a clearly labeled non-primary analysis.
- **Confirmatory-changing:** changes the primary protocol and requires a new version before outcome inspection.
- **Exploratory:** motivated after viewing outcomes and must be labeled as such.

## Requirements

1. Describe the scientific rationale and change class.
2. Add or update tests, especially leakage, determinism, and audit tests.
3. Update `docs/DECISIONS.md` with date, rationale, and expected impact.
4. Never silently change seeds, budgets, exclusions, endpoints, source caps, or dataset adapters.
5. Never convert model failures to chance scores.
6. Never commit raw EEG, credentials, private participant information, or unreviewed generated results.
7. Preserve source licenses and citations.

## Development checks

```bash
ruff check .
pytest
python scripts/run_smoke_test.py --workspace .smoke-work
python -m build
```

A confirmatory-changing contribution requires a new semantic version and configuration fingerprint.
