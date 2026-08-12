# Release checklist

## Protocol

- [x] Analysis plan frozen before public outcomes.
- [x] Decision log current.
- [x] Configs load under strict schema.
- [x] Confirmatory and sensitivity analyses clearly separated.
- [x] No performance-based exclusions.

## Software

- [x] Unit/integration tests pass locally.
- [x] Deterministic synthetic smoke passes twice.
- [x] Shuffled-label negative control is plausible.
- [ ] Lint and package build pass in remote CI.
- [x] No cache, credential, raw data, or local result files in release archive.

## Public-data pilot

- [ ] Environment report saved.
- [ ] All pilot adapters pass structure checks.
- [ ] Processed checksums validate.
- [ ] Manual event/session/channel inspection completed.
- [ ] All methods/budgets complete.
- [ ] Result audit status is `ok`.
- [ ] Runtime/storage documented.
- [ ] Pilot acceptance record signed/date-stamped.

## Full analysis

- [ ] Full data validation report archived.
- [ ] Confirmatory run completes without undocumented exceptions.
- [ ] Prediction-derived metrics match metrics table.
- [ ] Participant-level aggregation complete.
- [ ] Mixed-model convergence/fallback reported.
- [ ] Three-channel sensitivity complete.
- [ ] All-source sensitivity complete.
- [ ] Dataset-specific and pooled estimates reported.

## Manuscript

- [ ] No clinical or causal overclaim.
- [ ] Cue-based interpretation explicit.
- [ ] Recent literature reviewed through submission date.
- [ ] Null results and failures reported.
- [ ] Every dataset/software citation present.
- [ ] Tables and figures trace to source CSVs.

## Archive

- [ ] Git tag created.
- [ ] `CITATION.cff` updated with final repository URL and DOI.
- [x] SHA-256 manifest generated for the v0.1.0 archive.
- [x] Release ZIP built from clean tree.
- [ ] Zenodo/archival DOI created.
- [ ] Environment freeze and run manifests deposited.
