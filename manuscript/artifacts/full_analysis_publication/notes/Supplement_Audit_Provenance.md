# Supplement — Audit and provenance summary

Factual, non-interpretive summary of the confirmatory full-cohort run
underlying every figure and table in this artifact set. Full closure record:
`docs/full_run_acceptance.md`. Full decision record: `docs/DECISIONS.md`.

## Run identification

- Output directory: `results/bci-calibration-full-v1-3fb8efe7e617b0c1/`
- Experiment fingerprint: `3fb8efe7e617b0c1`
- Preprocessing fingerprint: `861cc64b9adbc47c`

## Cohort

- Nominal participants: 67 (Lee2019_MI 54, BNCI2014_001 9, Zhou2016 4)
- Structurally excluded: Zhou2016 subjects 2 and 4 (pre-outcome structural
  shortfalls in the publicly released recordings; see `docs/DECISIONS.md`)
- Final structurally validated N: 65 (Lee2019_MI 54, BNCI2014_001 9, Zhou2016 2)

## Run integrity

- Configured conditions: 19500
- Successful conditions: 19500
- Failed conditions: 0
- Prediction rows: 2068800
- Result-integrity audit status: `ok`
- Metrics independently recomputed from stored predictions and matched exactly: 19500
- AUCC curve completeness: 390/390 rows complete

## Aggregation

- Aggregation manifest schema version: 1
- Aggregation input metrics checksum (SHA-256): `b1dc2d727542a9eaed4286a826abdcd2b535a9b793d8128b7c219e9bfbc8c959`

## LaTeX compiler availability at build time

No `pdflatex` (or other LaTeX compiler: `tectonic`, `latexmk`) was found on
`PATH` when this artifact set was generated (`which pdflatex` returned
nothing). The `.tex` tables were structurally reviewed by hand (balanced
environments, matching column counts between header and data rows, correct
`tabularx`/`threeparttable` nesting) but were **not** compiled by this
build. See `notes/PROVENANCE.md`, "LaTeX layout" section, for exactly what
changed and why.

This note is provenance/audit-only. It contains no performance interpretation.
