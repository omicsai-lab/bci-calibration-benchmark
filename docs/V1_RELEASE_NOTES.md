# v1.0.0 release notes

## What this release represents

`v1.0.0` is the first manuscript-associated archival software release of
this repository. It closes execution of:

- the confirmatory full-cohort analysis (`configs/full.yaml`);
- both pre-specified sensitivity analyses (common `C3/Cz/C4` montage;
  all-eligible-source-cohort);
- a reviewer-motivated post-confirmatory robustness program (training-only
  Euclidean Alignment; a without-`Zhou2016` pooled re-aggregation; a
  random-intercept-only mixed-model comparison; a descriptive
  fraction-benefiting summary).

It is a software/data-pipeline and audit closure milestone, prepared to
accompany a manuscript in preparation. **It is not itself a manuscript, a
peer-reviewed publication, or a claim of clinical utility.**

## Where to find the actual record

This file intentionally does not restate numbers already on record
elsewhere. See:

- [`README.md`](../README.md), "Current study status" — the current,
  top-level summary of what is complete.
- [`docs/full_run_acceptance.md`](full_run_acceptance.md) — confirmatory
  full-cohort closure record.
- [`docs/sensitivity_run_acceptance.md`](sensitivity_run_acceptance.md) —
  both pre-specified sensitivities' closure record.
- [`docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md`](POST_CONFIRMATORY_ROBUSTNESS_SPEC.md)
  and
  [`docs/post_confirmatory_robustness_acceptance.md`](post_confirmatory_robustness_acceptance.md)
  — the post-confirmatory Euclidean Alignment and related robustness
  program's specification and closure record.
- [`docs/DECISIONS.md`](DECISIONS.md) — every dated scientific/protocol
  decision, including the two pre-outcome `Zhou2016` structural
  exclusions.
- [`docs/SOFTWARE_VALIDATION_REPORT.md`](SOFTWARE_VALIDATION_REPORT.md) —
  append-only software validation history across releases.
- [`manuscript/artifacts/`](../manuscript/artifacts/) — publication
  figures, tables, and traceable source-data CSVs.
- [`docs/V1_RELEASE_CANDIDATE_REPORT.md`](V1_RELEASE_CANDIDATE_REPORT.md) —
  this specific release-preparation round's validation status, file
  changes, and remaining human decisions.

## What changed in this release relative to `v0.1.1`

Scientifically: everything described above — the confirmatory run, both
pre-specified sensitivities, and the post-confirmatory robustness program
did not exist at `v0.1.1`, which validated only the software/data path on
a bounded real-data pilot cohort with no scientific claim.

In software terms, this release-preparation round changed only release
metadata (version strings, `CHANGELOG.md`, `README.md`, `CITATION.cff`,
`MANIFEST.sha256`) and added this notes file and the release candidate
report. No scientific config, calibration budget, participant-eligibility
rule, statistical analysis, or model hyperparameter was changed as part of
preparing this release. No completed result was rerun, modified, or
recomputed.

## Release process status

`v1.0.0` has been **published**. The `v1.0.0` GitHub Release was created
from the `release_v1.0.0` branch and has been **archived successfully by
Zenodo**. Two DOIs were minted:

- **Specific `v1.0.0` DOI: [10.5281/zenodo.22038602](https://doi.org/10.5281/zenodo.22038602)** — resolves to the exact archived snapshot of this software version; this is the DOI to cite for the manuscript.
- **Concept DOI: [10.5281/zenodo.22038603](https://doi.org/10.5281/zenodo.22038603)** — a stable identifier for the software project as a whole, which will resolve to whichever version is most recently archived; do not use this in place of the version DOI when citing the exact software used for the manuscript's results.

See `docs/V1_RELEASE_CANDIDATE_REPORT.md` for the release-candidate
validation record and `CITATION.cff` for the machine-readable citation
metadata, which now records the specific `v1.0.0` DOI.
