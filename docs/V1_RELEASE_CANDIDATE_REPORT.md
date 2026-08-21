# v1.0.0 release candidate report

This report records the state of the `release_v1.0.0` branch at the end of
the release-preparation round(s) that produced it. Nothing described below
has been committed, pushed, merged, or tagged; every change is uncommitted
and left for human review.

**No benchmark, model fitting, participant selection, scientific
aggregation, or statistical analysis was rerun or modified in this
release-prep round.**

## Branch and base commit

| Field | Value |
|---|---|
| Branch | `release_v1.0.0` |
| Base commit (`HEAD`, working tree clean at the start of release-prep work) | `29389099d51a68561a362ac254420b8b2ff70cb4` (`2938909`) — "Merge pull request #3 from omicsai-lab/alignment_sensitivity" |
| Branch tracking | `origin/release_v1.0.0`, up to date at the base commit |

The base commit already contains the completed confirmatory analysis, both
pre-specified sensitivities, and the post-confirmatory Euclidean Alignment
robustness program (merged via PR #2 `sensitivity_analysis` and PR #3
`alignment_sensitivity`). This release-prep work added no scientific
commit on top of it — only the uncommitted release-metadata/documentation
changes listed below.

## Intended version and release date

| Field | Value |
|---|---|
| Intended version | `1.0.0` |
| Intended release date | **Pending actual GitHub Release date.** No git tag and no GitHub Release exist yet. `CITATION.cff`'s `date-released` field is intentionally left unset (with an in-file comment explaining why) rather than populated with an invented or placeholder date. |
| Development status | `Development Status :: 5 - Production/Stable` (manually set in `pyproject.toml` prior to this round; preserved, not altered). |

## Test / lint / build / package status

| Check | Command | Result |
|---|---|---|
| Unit/integration/leakage-regression tests | `python -m pytest` | **60 passed**, 0 failed |
| Lint | `ruff check .` | **All checks passed** |
| Whitespace/diff hygiene | `git diff --check` | **clean** (exit 0, no output) |
| Byte-compilation | `python -m compileall -q src scripts tests` | **passed** (exit 0) |
| Package build | `python -m build --outdir <scratch dir outside the repo>` | **passed** — built `bci_calibration_benchmark-1.0.0.tar.gz` and `bci_calibration_benchmark-1.0.0-py3-none-any.whl`. Not built into the repository root (no untracked build artifacts left behind: `build/` and `src/*.egg-info` created transiently during the build were removed afterward). Not installed, not published to PyPI. |

Test count: **60**, matching the expected current count exactly (no
discrepancy to report). Up from 40 at `v0.1.1`.

Wheel-content verification: unzipped and inspected directly.
`Version: 1.0.0`, `Classifier: Development Status :: 5 - Production/Stable`,
`Project-URL: Repository, https://github.com/omicsai-lab/bci-calibration-benchmark`
all present in `METADATA`. The wheel's file listing includes every current
module, explicitly confirmed for the Euclidean Alignment components:
`alignment.py`, `assignment_reuse.py`, `ea_runner.py`, `ea_validation.py`,
`ea_aggregate.py`, `ea_plotting.py`.

## Manifest status

`MANIFEST.sha256` was stale (originally generated for the `v0.1.0`
archive; 78 entries). Regenerated deterministically after all other
release-prep edits, including the manually-set `Development Status ::
5 - Production/Stable` classifier change in `pyproject.toml`:

- **Payload**: the intended tracked release payload — every file `git`
  currently tracks, **plus** files newly added in this round that are not
  yet tracked but are part of the intended release
  (`docs/V1_RELEASE_NOTES.md`, this file) — via
  `git ls-files --cached --others --exclude-standard`, which already
  respects `.gitignore`.
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
- **Entry count: 152.**
- **Validation**: every one of the 152 listed hashes was independently
  recomputed from current file contents and compared — **152/152 match,
  0 mismatches.** Regenerated a second time from scratch and diffed
  against the first regeneration: **byte-identical** (determinism
  confirmed). `pyproject.toml`'s entry specifically re-verified to reflect
  its current content (including the `Development Status` line) after the
  manual edit.

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

## Files changed / new in this round

**Modified** (release metadata/documentation only):

- `README.md` — positioning, "Current study status" section, post-confirmatory-robustness run instructions, current test count (60), obsolete-wording replacement, confirmatory/prespecified/post-confirmatory distinctions maintained throughout.
- `pyproject.toml` — `version = "1.0.0"`; `Development Status :: 5 - Production/Stable` (manually set before this round; preserved); added `Repository` project URL.
- `src/bci_calibration_benchmark/__init__.py` — `__version__ = "1.0.0"` (the only source-code change in this round).
- `CITATION.cff` — `version: 1.0.0`; author email/ORCID; `repository-code`; `date-released` intentionally left unset with an explanatory comment; no DOI field added.
- `CHANGELOG.md` — new `1.0.0` top entry; `0.1.0`/`0.1.1` entries untouched.
- `MANIFEST.sha256` — fully regenerated (152 entries; see above).

**New**:

- `docs/V1_RELEASE_NOTES.md` — concise release-positioning note pointing to existing acceptance/provenance records, not duplicating them.
- `docs/V1_RELEASE_CANDIDATE_REPORT.md` — this file.

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

1. Actual `date-released` for `CITATION.cff` — set at real tag/Release time.
2. Final git tag creation (`v1.0.0`).
3. GitHub Release creation.
4. Zenodo DOI, minted automatically after the GitHub Release above exists.
5. Final manuscript submission status (this repository supports, but does not itself constitute, the manuscript).

No other item is outstanding: software version, author identity, ORCID,
email, `Development Status` classifier, and repository URL are already
resolved and reflected in `pyproject.toml`/`CITATION.cff` as of this
report.

## Explicit statement

**No benchmark, model fitting, participant selection, scientific
aggregation, or statistical analysis was rerun or modified in this
release-prep round.** Every number quoted in `README.md`'s "Current study
status" section and in this report's fingerprint table was read from
already-existing, already-audited files (`run_manifest.json`,
`result_audit.json`) or computed fresh only from configuration (never
data) via `experiment_fingerprint`. No `results/` directory was written
to, deleted, or regenerated in this round.
