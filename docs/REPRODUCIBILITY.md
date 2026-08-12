# Reproducibility and provenance

## Reproducibility target

A second researcher should be able to determine exactly:

- which source dataset adapter and software version were used;
- which participant/session/run/trial occupied each role;
- which calibration trials were selected at each nested budget;
- which source participants and source trials were selected;
- which estimator settings and random seeds were used;
- which code/configuration generated each result table and figure.

Reproducibility does not mean that floating-point results are guaranteed bitwise identical across every CPU, BLAS, operating system, or deep-learning device. It means the computational state is captured and differences become diagnosable rather than silent.

## Version and environment controls

- Python reference versions: 3.11 and 3.12 in CI.
- MOABB: exactly 1.5.0.
- Top-level dependency ranges: `pyproject.toml` and `requirements/constraints.txt`.
- Conda reference: `environment.yml`.
- Container recipe: `Dockerfile`.
- Exact execution environment: save `python -m pip freeze --all` beside the final run.

`validate_environment.py` reports Python, platform, installed package versions, source-tree digest, and configuration validation.

## Configuration fingerprints

Every YAML configuration is parsed into a strict dataclass schema. Unknown keys fail validation. Two hashes are generated:

- preprocessing fingerprint: controls processed shard location;
- experiment fingerprint: controls result directory location.

Changing a calibration budget, seed, source cap, method, endpoint, or split policy changes the experiment fingerprint.

## Processed-data manifests

Each subject shard contains:

- `X.npy`;
- `y.npy`;
- compressed trial metadata;
- channel names and sampling frequency;
- class and group counts;
- preprocessing payload;
- package versions;
- SHA-256 checksum for every stored file.

Each dataset manifest hashes all subject manifests. A run manifest then hashes the dataset manifests. Modifying a processed shard after a run starts invalidates safe resume.

## Trial-level protocol records

The runner writes:

- `split_assignments.csv.gz`: every target trial and its calibration-pool/test role;
- `calibration_assignments.csv.gz`: every selected target calibration trial at every budget and the first budget at which it entered;
- `source_selection.csv`: source participant counts, seeds, and selection digests;
- `source_trial_assignments.csv.gz`: every selected source trial, label, session, run, and target for which it was used;
- `predictions.csv.gz`: every held-out prediction when enabled.

These files are not inferential tables; they are audit evidence.

## Deterministic seeds

Python's randomized `hash()` is not used. Every seed is derived by SHA-256 from the global seed and semantic identifiers such as dataset, target participant, repeat, source participant, method, regime, and budget.

The same calibration membership is shared across methods and regimes for a participant/repeat. The same held-out session is shared across every condition.

## Resume safety

Resume is permitted only when:

- the experiment fingerprint matches;
- preprocessing and dataset-manifest hashes match;
- package versions match;
- executable/configuration source digest matches when available;
- no duplicate or partial condition/prediction rows are present.

A run with `resume: false` refuses to write into an existing managed result directory.

## Result audit

Before aggregation, the audit verifies:

- one shared target split per participant/repeat;
- allowed regimes and budgets;
- exact population/source-plus-target equality at budget zero;
- prediction count and held-out trial identity;
- metrics recomputed from stored predictions;
- group disjointness;
- nested calibration membership and class balance;
- target exclusion from source participants;
- source-trial count and digest consistency;
- successful condition completeness under the configured design.

Aggregation is blocked when the audit fails.

## Figure provenance

Each figure is generated from an aggregated CSV table. The exact source table used for each figure is copied beside the image, and `figure_manifest.json` records file hashes. Manual editing of quantitative figure content is prohibited.

## Archival release

Before submission:

1. tag the exact Git commit;
2. create a release archive;
3. archive it with Zenodo or another DOI service;
4. record the DOI in `CITATION.cff` and the manuscript;
5. archive environment freeze, config files, result manifests, aggregate tables, and figure-source CSVs;
6. do not archive source EEG unless the original license explicitly permits redistribution.
