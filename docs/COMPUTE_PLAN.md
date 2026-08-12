# Compute plan

## Why compute is controlled

The study repeats training over participants, budgets, calibration draws, regimes, and methods. Unbounded source cohorts would multiply both covariance estimation and repeated fitting while making target calibration numerically negligible.

## Primary workload

Nominal confirmatory cohort: 67 target participants.

Per target and method:

- 2 zero-budget rows (`population` and its audited `source_plus_target` duplicate) for each repeat;
- 4 positive budgets × 2 adaptive regimes × 10 repeats;
- one fixed later-session test set.

The zero-budget population estimator is fit once per target/method and reused across repeats because source data and the test session do not change.

## Source cap

The confirmatory cap is:

- at most 10 source participants;
- at most 20 trials/class/source participant;
- at most 400 source epochs per target.

The all-source sensitivity is intentionally separate and uses five repeats.

## Deliberately conservative implementation

Version 0.1.0 fits each configured condition from its explicitly assembled training epochs. It does **not** yet cache method-specific representations across budgets. This is slower than an optimized implementation but keeps the scientific execution path simple and auditable for the first public-data pilot.

Log-variance and covariance caching is a legitimate future optimization only after numerical-equivalence tests are added. CSP must remain training-set dependent and cannot be cached as a fixed epoch representation.

## Execution order

1. synthetic smoke;
2. one participant from each dataset, one repeat;
3. bounded pilot (three participants/dataset, two repeats);
4. full-montage confirmatory run;
5. three-channel sensitivity;
6. all-source sensitivity;
7. optional deep extension only after classical completion.

## Resource recording

For each run record:

- CPU model and logical/physical cores;
- RAM;
- storage used by raw cache, processed shards, and outputs;
- wall time and fit/predict time by condition;
- failures and retries;
- thread environment variables;
- GPU model and deterministic settings if deep learning is added.

## Parallelism

Data download/preparation defaults to one job because some public hosts and MNE loaders are not robust to aggressive parallel download. Model-level parallelization should be introduced only after deterministic file-writing is preserved. Separate fingerprinted configurations may be scheduled independently.
