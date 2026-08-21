# v1.0.0 release candidate report

This report records the state of the `release_v1.0.0` branch's release
preparation. Release-candidate validation (tests, lint, build, fingerprint
checks, manifest regeneration) was originally performed **before** commit,
against an uncommitted working tree, exactly as the release-prep task
required. Those validated release-prep changes were then **committed and
pushed** to `release_v1.0.0` for human review. As of this report: the
branch has **not** been merged to `main`, no `v1.0.0` git tag exists, no
GitHub Release exists, and no Zenodo DOI has been minted.

**No benchmark, model fitting, participant selection, scientific
aggregation, or statistical analysis was rerun or modified in this
release-prep work.**

## Branch and base commit

| Field | Value |
|---|---|
| Branch | `release_v1.0.0` |
| Base commit (the point from which release preparation began; last commit shared with `full_analysis`/`alignment_sensitivity` before any release-metadata edit) | `29389099d51a68561a362ac254420b8b2ff70cb4` (`2938909`) — "Merge pull request #3 from omicsai-lab/alignment_sensitivity" |
| Current release-candidate branch `HEAD` (`git rev-parse HEAD`) | `c11570a37e5bce1c9e6502db8e56b843c0ff3933` (`c11570a`) — "prepare v1.0.0 release candidate": the committed, pushed release-prep changes validated before commit, plus this subsequent release-metadata consistency pass |
| Branch tracking | `origin/release_v1.0.0`, up to date |

The base commit already contains the completed confirmatory analysis, both
pre-specified sensitivities, and the post-confirmatory Euclidean Alignment
robustness program (merged via PR #2 `sensitivity_analysis` and PR #3
`alignment_sensitivity`). Every commit from the base commit to the current
`HEAD` is release-metadata/documentation only — no scientific commit was
added on top of it.

## Intended version and release date

| Field | Value |
|---|---|
| Intended version | `1.0.0` |
| Intended release date | `2026-08-21`. Recorded in `CITATION.cff`'s `date-released` and in `CHANGELOG.md`'s `1.0.0` heading. A git tag and GitHub Release have not yet been created; the actual tag/Release timestamp may differ from this intended date and should be reconciled by whoever performs that step. |
| Development status | `Development Status :: 5 - Production/Stable` (manually set in `pyproject.toml`; preserved, not altered). |

## Test / lint / build / package status

| Check | Command | Result |
|---|---|---|
| Unit/integration/leakage-regression tests | `python -m pytest` | **60 passed**, 0 failed |
| Lint | `ruff check .` | **All checks passed** |
| Whitespace/diff hygiene | `git diff --check` | **clean** (exit 0, no output) |
| Byte-compilation | `python -m compileall -q src scripts tests` | **passed** (exit 0) |
| Package build | `python -m build --outdir <scratch dir outside the repo>` | **passed** — built `bci_calibration_benchmark-1.0.0.tar.gz` and `bci_calibration_benchmark-1.0.0-py3-none-any.whl`. Not built into the repository root (no untracked build artifacts left behind: `build/` and `src/*.egg-info` created transiently during the build were removed afterward). Not installed, not published to PyPI. |

Test count: **60**, matching the expected current count exactly (no
discrepancy to report). Up from 40 at `v0.1.1`. Tests, lint,
`git diff --check`, and byte-compilation were re-run fresh in this
consistency pass (all pass, as above). The package build itself was
validated when `c11570a` was prepared and was not rebuilt in this pass;
`pyproject.toml` and `__init__.py` (the files that determine package
version, classifiers, and code) were not touched in this pass, so the
package's importable contents and metadata fields are unaffected. `README.md`'s
content is embedded as the wheel/sdist long description (`readme =
"README.md"` in `pyproject.toml`), so a fresh build after this pass would
pick up the updated manuscript title in that long description; this does
not change package validity, version, or code contents.

Wheel-content verification: unzipped and inspected directly.
`Version: 1.0.0`, `Classifier: Development Status :: 5 - Production/Stable`,
`Project-URL: Repository, https://github.com/omicsai-lab/bci-calibration-benchmark`
all present in `METADATA`. The wheel's file listing includes every current
module, explicitly confirmed for the Euclidean Alignment components:
`alignment.py`, `assignment_reuse.py`, `ea_runner.py`, `ea_validation.py`,
`ea_aggregate.py`, `ea_plotting.py`.

## Manifest status

`MANIFEST.sha256` was originally stale (generated for the `v0.1.0`
archive; 78 entries), regenerated once when the release-prep changes
committed as `c11570a` were prepared, and regenerated again in this
consistency pass to pick up the content edits described above (title,
`date-released`, `CHANGELOG.md` heading, release-notes status wording):

- **Payload**: the intended tracked release payload, via
  `git ls-files --cached --others --exclude-standard` (already respects
  `.gitignore`). At the time of this regeneration every payload file is
  already `git`-tracked (the previously-new `docs/V1_RELEASE_NOTES.md`
  and this file were committed as part of `c11570a`); no untracked file
  needed to be added to the payload this time.
- **Exclusions**: `.git/`, `.venv/`, `.smoke-work/`, MOABB cache, raw/
  processed EEG, ignored `results/` runtime content, caches, temporary
  ZIP/TAR archives, `.DS_Store`, `.env`, credentials (all excluded via
  `.gitignore`, verified directly — see "Repository hygiene" below), and
  `MANIFEST.sha256` itself (matching the existing `v0.1.0` manifest's own
  convention of not self-hashing; confirmed the string `MANIFEST.sha256`
  does not appear anywhere in the regenerated file).
- **Order**: sorted by path (`./<path>`), deterministic.
- **Format**: `<sha256>  ./<relative-path>` (two spaces), unchanged from
  the existing convention.
- **Entry count: 152** (unchanged from the previous regeneration — this
  pass edited existing tracked files' content only; no file was added or
  removed from the payload).
- **Validation**: every one of the 152 listed hashes was independently
  recomputed from current file contents and compared — **152/152 match,
  0 mismatches.** Regenerated a second time from scratch and diffed
  against the first: **byte-identical** (determinism confirmed).
  `README.md`, `CITATION.cff`, and `CHANGELOG.md`'s entries specifically
  re-verified to reflect this pass's content changes.

## Config-fingerprint preservation

Verified by loading each config fresh through the (release-metadata-only
modified) codebase and comparing `experiment_fingerprint` against the
value already baked into its existing, closed `results/` directory name:

| Config | `experiment_fingerprint` | Expected | Match |
|---|---|---|---|
| `configs/full.yaml` | `3fb8efe7e617b0c1` | `3fb8efe7e617b0c1` | yes |
| `configs/sensitivity_three_channels.yaml` | `1fcb3f9ba9823bb1` | `1fcb3f9ba9823bb1` | yes |
| `configs/sensitivity_all_sources.yaml` | `e86ca10985667aec` | `e86ca10985667aec` | yes |
| `configs/sensitivity_ea_training_only.yaml` | `43e15c22709c6e6b` | `43e15c22709c6e6b` | yes |
| `configs/pilot.yaml` | `2b515a94ee6e8949` | `2b515a94ee6e8949` | yes |

All five match exactly; all five configs' resolved `output_dir` still
points at their existing, already-closed `results/` directory on disk.
No release-metadata edit in this round touched
`src/bci_calibration_benchmark/config.py`, any config YAML, or any other
file that participates in fingerprint computation.

## Files changed / new

**Committed as `c11570a` ("prepare v1.0.0 release candidate"), validated before commit, then pushed:**

- `README.md` — positioning, "Current study status" section, post-confirmatory-robustness run instructions, current test count (60), obsolete-wording replacement, confirmatory/prespecified/post-confirmatory distinctions maintained throughout.
- `pyproject.toml` — `version = "1.0.0"`; `Development Status :: 5 - Production/Stable` (manually set before that round; preserved); added `Repository` project URL.
- `src/bci_calibration_benchmark/__init__.py` — `__version__ = "1.0.0"` (the only source-code change in the release-prep work).
- `CITATION.cff` — `version: 1.0.0`; author email/ORCID; `repository-code`; no DOI field added.
- `CHANGELOG.md` — new `1.0.0` top entry.
- `MANIFEST.sha256` — fully regenerated.
- `docs/V1_RELEASE_NOTES.md`, `docs/V1_RELEASE_CANDIDATE_REPORT.md` — added new.

**This subsequent release-metadata consistency pass (uncommitted, left for review):**

- `README.md` — replaced the stale quoted manuscript working title with "From cold start to personalization: a leakage-resistant cross-session benchmark of motor-imagery BCI calibration efficiency"; no other wording changed.
- `CITATION.cff` — `date-released: 2026-08-21` set; the prior "intentionally left unset" comment removed; still no DOI field.
- `CHANGELOG.md` — `1.0.0` heading changed to `## 1.0.0 — 2026-08-21`; historical `0.1.0`/`0.1.1` entries untouched.
- `docs/V1_RELEASE_NOTES.md` — "Release process status" updated to state the release-prep changes are committed and pushed to `release_v1.0.0`, not yet merged to `main`.
- `docs/V1_RELEASE_CANDIDATE_REPORT.md` — this file: state/provenance wording, `HEAD` commit, intended release date.
- `MANIFEST.sha256` — regenerated again to reflect the above content changes (entry count unchanged; see below).

**Not modified — verified via `git diff`/`git status`, not assumed**: every
scientific config (`configs/*.yaml`), every file under
`src/bci_calibration_benchmark/` other than `__init__.py`'s version
string, every file under `tests/`, `results/`, and `manuscript/artifacts/`
(publication source-data values untouched), and every existing `docs/`
acceptance/decision/protocol record (`docs/ANALYSIS_PLAN.md`,
`docs/DECISIONS.md`, `docs/full_run_acceptance.md`,
`docs/sensitivity_run_acceptance.md`,
`docs/post_confirmatory_robustness_acceptance.md`,
`docs/POST_CONFIRMATORY_ROBUSTNESS_SPEC.md`,
`docs/RELEASE_CHECKLIST.md`, `docs/SOFTWARE_VALIDATION_REPORT.md`, etc.).
No calibration budget, participant-eligibility rule, method definition,
sensitivity definition, or statistical test was touched.

## Repository hygiene

- No `.venv/`, `.smoke-work/`, MOABB cache, raw EEG, or processed EEG
  tracked or newly added — checked directly against the full intended
  payload (`git ls-files --cached --others --exclude-standard`) with a
  case-insensitive pattern match for
  `\.venv/|\.smoke-work/|moabb-cache|^data/processed|^data/moabb|\.ds_store|\.env$|credential|secret|\.pem$|\.key$|\.zip$|\.tar$|\.tar\.gz$`:
  **zero matches**.
- `results/` contains only `.gitkeep` in the payload; the four closed run
  directories on local disk (`bci-calibration-full-v1-*`,
  `bci-calibration-three-channels-*`,
  `bci-calibration-all-sources-sensitivity-*`,
  `bci-calibration-ea-training-only-sensitivity-*`) are gitignored and
  were not added — no millions-row prediction file entered the payload.
- `data/` contains only `.gitkeep` and `README.md` in the payload.
- **Largest tracked file**: `manuscript/artifacts/full_analysis_publication/figures/Figure2_main_calibration_curves.png` (308 KB).
- **No tracked file exceeds 10 MB** (largest is 308 KB, three orders of magnitude below the threshold).
- **Total tracked payload size**: ~2.6 MB (`du -ck` over the full intended payload).
- No temporary manuscript or release ZIP/TAR file, `.DS_Store`, `.env`, or
  credential/secret-like filename is present in the payload.
- No suspicious filename found.
- `manuscript/artifacts/` (56 files: two publication-artifact packages'
  figures, tables, and source-data CSVs) is the intended repository asset
  set and was left untouched.

## Archival (Zenodo) status

- Zenodo's GitHub integration has been **enabled** for this repository.
- **No GitHub Release has been created and no Zenodo DOI exists yet.**
- This round did **not** create, guess, or insert a placeholder DOI
  anywhere (`CITATION.cff`, `README.md`, or elsewhere).
- DOI minting is deferred until after this branch is merged and an actual
  `v1.0.0` GitHub Release is created — Zenodo mints a DOI automatically
  from that Release once those steps occur. That merge/tag/Release
  sequence is itself outside this round's authorization.

## Remaining human decisions

1. Reconciling `CITATION.cff`'s recorded `date-released: 2026-08-21` against
   the actual git tag/GitHub Release timestamp once that step occurs (they
   may not be the same day).
2. Merge of `release_v1.0.0` to `main`.
3. Final git tag creation (`v1.0.0`).
4. GitHub Release creation.
5. Zenodo DOI, minted automatically after the GitHub Release above exists.
6. Final manuscript submission status (this repository supports, but does not itself constitute, the manuscript).

No other item is outstanding: software version, author identity, ORCID,
email, `Development Status` classifier, repository URL, and the intended
`date-released` value are already resolved and reflected in
`pyproject.toml`/`CITATION.cff` as of this report.

## Explicit statement

**No benchmark, model fitting, participant selection, scientific
aggregation, or statistical analysis was rerun or modified in this
release-prep round.** Every number quoted in `README.md`'s "Current study
status" section and in this report's fingerprint table was read from
already-existing, already-audited files (`run_manifest.json`,
`result_audit.json`) or computed fresh only from configuration (never
data) via `experiment_fingerprint`. No `results/` directory was written
to, deleted, or regenerated in this round.
