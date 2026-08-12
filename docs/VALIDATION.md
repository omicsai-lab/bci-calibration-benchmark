# Validation status

## What has been validated in this release

The repository has been validated locally with deterministic synthetic EEG and unit/integration tests. Synthetic data contain a known contralateral variance pattern and are used only to test software behavior.

Validated behaviors include:

- strict YAML parsing and scientific constraint checks;
- target/source participant disjointness;
- fixed latest-session holdout with no favorable back-selection;
- group-disjoint calibration and test roles;
- nested, class-balanced calibration samples;
- deterministic source sampling;
- CSP, log-variance, and Riemannian pipeline execution;
- SPD covariance and tangent-space operations;
- exact zero-budget population duplication;
- source-trial selection records and digest reconciliation;
- six metrics recomputed independently from stored held-out predictions;
- configured condition-grid completeness;
- output schemas, resume checks, and provenance manifests;
- participant-level aggregation and fixed-horizon AUCC;
- separated confirmatory/supportive multiplicity families;
- end-to-end deterministic result equality across two synthetic runs;
- shuffled-label negative control near chance;
- generation of figures and figure-source CSV files.

The current local test suite result is recorded in `docs/SOFTWARE_VALIDATION_REPORT.md` when the release archive is built.

## What has not been validated here

This execution environment did not contain MOABB or the public EEG archives. Therefore, the following are **not claimed as completed** in v0.1.0:

- download of the three confirmatory datasets;
- local execution of the current MOABB 1.5.0 adapters;
- confirmation of observed public-data session/run/channel counts;
- full-cohort compute duration or memory use;
- any public EEG performance result;
- remote GitHub Actions completion;
- manuscript-ready biological conclusions.

Official MOABB documentation and source were used to pin adapter expectations, but the public-data pilot remains mandatory.

## Public-data pilot acceptance gates

The full run cannot begin until the pilot demonstrates:

1. all configured pilot participants download and preprocess;
2. adapter-level structural checks pass exactly;
3. the common three-channel configuration finds `C3/Cz/C4` in every dataset;
4. latest-session test and earlier-session calibration counts match expectations;
5. data checksums and manifests validate;
6. all three classical methods fit at every pilot budget;
7. audit status is `ok`;
8. no prediction/metric recomputation mismatch exists;
9. runtime and memory are recorded;
10. any deviation is resolved by a documented protocol decision before full outcomes are examined.

## Interpretation of synthetic results

A high synthetic ROC-AUC means that the software can recover the deliberately injected synthetic pattern. It says nothing about real BCI performance. The shuffled-label check is a software negative control, not a formal permutation test for the public study.
