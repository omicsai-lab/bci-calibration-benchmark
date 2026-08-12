# Dataset selection rationale

## Selection rule

A confirmatory dataset had to satisfy all of the following before outcomes were examined:

1. public, programmatically retrievable EEG;
2. a MOABB 1.5.0 adapter;
3. left- and right-hand motor-imagery labels;
4. at least two distinct sessions per participant;
5. enough labeled earlier-session trials for 40 trials/class calibration;
6. enough trials in the fixed latest session for stable held-out scoring;
7. no required trial-level fallback;
8. no known feedback or task discontinuity that is perfectly confounded with the held-out latest session;
9. compatible access and citation terms;
10. tractable first-release download and compute.

## Selected datasets

`Lee2019_MI`, `BNCI2014_001`, and `Zhou2016` jointly provide:

- a large two-session cohort;
- a canonical competition benchmark;
- an independent three-session replication;
- three different montages and acquisition systems;
- a nominal 67 participants under one binary task.

This is not the largest possible collection. It is the largest set identified for v0.1 that met the strict split and protocol-continuity rules without writing unvalidated custom adapters.

## Why not maximize participant count immediately?

A larger but structurally incompatible cohort would answer a different question. Random trial splitting in Cho2017 or PhysionetMI would estimate within-recording discrimination, not later-session calibration performance. Including BNCI2014_004 with its feedback transition would create a confounded temporal comparison. Including an unpiloted 65.6 GB archive would increase operational risk before the core protocol is validated.

The release therefore favors **estimand integrity over nominal N**.

## Relationship to recent work

A July 2026 preprint benchmarked extensive within-session pipeline heterogeneity on Cho2017, PhysionetMI, and Zhou2016. The present protocol is deliberately different: it fixes a later session as the untouched target, varies the amount of labeled earlier-session target data, and treats calibration draws as repeated measurements rather than new test folds.

Recent cross-subject pooling and adaptation work establishes that calibration reduction is active and competitive. The contribution here is not a claim to invent transfer learning. It is a controlled estimate of the calibration–performance curve under a common, leakage-resistant, cross-session protocol.

## Expansion policy

A new dataset may be added only in a new version after:

- adapter structure is checked against the original protocol;
- task event timing is reconciled with the common epoch;
- session/run counts and channel names are tested;
- source license and citation are documented;
- a bounded pilot completes;
- the change is declared confirmatory extension or external validation before outcomes are examined.
