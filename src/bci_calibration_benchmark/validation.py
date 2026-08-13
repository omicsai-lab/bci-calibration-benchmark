"""Audits for benchmark outputs and protocol-assignment files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import ExperimentConfig
from .metrics import METRIC_NAMES, compute_binary_metrics
from .statistics import validate_metrics_frame
from .utils import fingerprint


CONDITION_KEY = [
    "dataset",
    "target_subject",
    "repeat",
    "method",
    "regime",
    "budget_per_class",
    "split_id",
]
SPLIT_KEY = ["dataset", "target_subject", "repeat", "split_id"]


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    # pandas' default C float parser is not guaranteed to round-trip floats
    # to their exact original bit pattern (~1 ULP errors are possible). This
    # module recomputes metrics from stored predictions and compares them
    # bit-for-bit against the originally stored values, and log_loss's
    # near-0/near-1 probability clipping amplifies a 1-ULP input error by a
    # factor of up to ~1e7 through its 1/p derivative, which was observed to
    # turn a ~1e-16 parsing wobble into a spurious ~1e-11 audit failure.
    kwargs.setdefault("float_precision", "round_trip")
    return pd.read_csv(path, **kwargs)


def _audit_metric_protocol(metrics: pd.DataFrame) -> dict[str, Any]:
    validate_metrics_frame(metrics)
    successful = metrics.loc[metrics["status"] == "ok"].copy()
    successful["target_subject"] = successful["target_subject"].astype(str)

    split_counts = successful.groupby(
        ["dataset", "target_subject", "repeat"], observed=True
    )["split_id"].nunique()
    if (split_counts != 1).any():
        bad = split_counts.loc[split_counts != 1].head(10).to_dict()
        raise ValueError(f"Methods/regimes do not share one target split: {bad}")

    population = successful.loc[successful["regime"] == "population"]
    if not (population["budget_per_class"] == 0).all():
        raise ValueError("Population rows must have budget zero")
    subject = successful.loc[successful["regime"] == "subject"]
    if not (subject["budget_per_class"] > 0).all():
        raise ValueError("Subject-only rows are undefined at zero budget")
    unknown_regimes = set(successful["regime"]) - {
        "population",
        "subject",
        "source_plus_target",
    }
    if unknown_regimes:
        raise ValueError(f"Unknown training regimes in metrics: {sorted(unknown_regimes)}")

    if "duplicate_of_population" in successful.columns:
        duplicate = successful["duplicate_of_population"].astype(str).str.lower().isin(["true", "1"])
        expected = (successful["regime"] == "source_plus_target") & (
            successful["budget_per_class"] == 0
        )
        if not np.array_equal(duplicate.to_numpy(), expected.to_numpy()):
            raise ValueError("duplicate_of_population flags do not match pooled zero-budget rows")

    return {
        "successful_conditions": int(len(successful)),
        "failed_conditions": int((metrics["status"] != "ok").sum()),
        "participants": int(
            successful[["dataset", "target_subject"]].drop_duplicates().shape[0]
        ),
        "split_instances": int(successful[SPLIT_KEY].drop_duplicates().shape[0]),
    }


def _audit_predictions(output_dir: Path, successful: pd.DataFrame) -> dict[str, Any]:
    path = output_dir / "predictions.csv.gz"
    predictions = _read_csv(
        path,
        dtype={"target_subject": str, "split_id": str, "trial_uid": str},
    )
    required = {
        *CONDITION_KEY,
        "trial_uid",
        "y_true",
        "y_score",
        "y_pred",
    }
    missing = required.difference(predictions.columns)
    if missing:
        raise ValueError(f"predictions.csv.gz missing columns: {sorted(missing)}")
    if predictions.empty:
        raise ValueError("Predictions file is empty despite successful conditions")
    if predictions.duplicated(CONDITION_KEY + ["trial_uid"]).any():
        raise ValueError("Duplicate held-out trial predictions within a condition")
    scores = pd.to_numeric(predictions["y_score"], errors="raise").to_numpy(dtype=float)
    if not np.isfinite(scores).all() or np.any((scores < 0) | (scores > 1)):
        raise ValueError("Prediction probabilities are invalid")
    observed_pred = pd.to_numeric(predictions["y_pred"], errors="raise").to_numpy(dtype=int)
    expected_pred = (scores >= 0.5).astype(int)
    if not np.array_equal(observed_pred, expected_pred):
        raise ValueError("Stored y_pred is inconsistent with the 0.5 probability threshold")
    observed_labels = set(
        pd.to_numeric(predictions["y_true"], errors="raise").astype(int).unique().tolist()
    )
    if not observed_labels.issubset({0, 1}):
        raise ValueError(f"Stored y_true contains non-binary labels: {sorted(observed_labels)}")

    labels_per_condition = predictions.groupby(CONDITION_KEY, observed=True)["y_true"].nunique()
    if (labels_per_condition != 2).any():
        raise ValueError("At least one held-out condition lacks both test classes")

    metric_conditions = successful[CONDITION_KEY + ["test_trials"]].copy()
    prediction_counts = (
        predictions.groupby(CONDITION_KEY, observed=True)
        .size()
        .rename("prediction_count")
        .reset_index()
    )
    merged = metric_conditions.merge(
        prediction_counts,
        on=CONDITION_KEY,
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    if not (merged["_merge"] == "both").all():
        raise ValueError("Prediction and successful-metric condition sets differ")
    if not np.array_equal(
        merged["test_trials"].astype(int).to_numpy(),
        merged["prediction_count"].astype(int).to_numpy(),
    ):
        raise ValueError("Prediction counts do not match metrics.test_trials")

    recomputed_rows: list[dict[str, Any]] = []
    for keys, group in predictions.groupby(CONDITION_KEY, observed=True, sort=False):
        values = dict(zip(CONDITION_KEY, keys, strict=True))
        values.update(
            compute_binary_metrics(
                group["y_true"].to_numpy(dtype=int),
                group["y_score"].to_numpy(dtype=float),
            )
        )
        recomputed_rows.append(values)
    recomputed = pd.DataFrame(recomputed_rows)
    stored = successful[CONDITION_KEY + list(METRIC_NAMES)].copy()
    metric_check = stored.merge(
        recomputed,
        on=CONDITION_KEY,
        how="outer",
        suffixes=("_stored", "_recomputed"),
        indicator=True,
        validate="one_to_one",
    )
    if not (metric_check["_merge"] == "both").all():
        raise ValueError("Stored and recomputed metric condition sets differ")
    for metric in METRIC_NAMES:
        stored_values = pd.to_numeric(metric_check[f"{metric}_stored"], errors="raise").to_numpy(
            dtype=float
        )
        recomputed_values = pd.to_numeric(
            metric_check[f"{metric}_recomputed"], errors="raise"
        ).to_numpy(dtype=float)
        if not np.allclose(stored_values, recomputed_values, rtol=1e-12, atol=1e-12):
            difference = np.abs(stored_values - recomputed_values)
            bad_index = int(np.argmax(difference))
            condition = metric_check.loc[bad_index, CONDITION_KEY].to_dict()
            raise ValueError(
                f"Stored {metric} differs from predictions for {condition}: "
                f"stored={stored_values[bad_index]!r}, "
                f"recomputed={recomputed_values[bad_index]!r}"
            )

    zero = predictions.loc[
        predictions["budget_per_class"].eq(0)
        & predictions["regime"].isin(["population", "source_plus_target"])
    ].copy()
    if not zero.empty:
        pivot_key = [
            "dataset",
            "target_subject",
            "repeat",
            "method",
            "split_id",
            "trial_uid",
        ]
        population = zero.loc[zero["regime"] == "population", pivot_key + ["y_score", "y_true"]]
        pooled = zero.loc[
            zero["regime"] == "source_plus_target",
            pivot_key + ["y_score", "y_true"],
        ]
        matched = population.merge(
            pooled,
            on=pivot_key,
            how="outer",
            suffixes=("_population", "_pooled"),
            indicator=True,
            validate="one_to_one",
        )
        if not (matched["_merge"] == "both").all():
            raise ValueError("Population and pooled zero-budget prediction trial sets differ")
        if not np.array_equal(
            matched["y_true_population"].to_numpy(dtype=int),
            matched["y_true_pooled"].to_numpy(dtype=int),
        ) or not np.allclose(
            matched["y_score_population"].to_numpy(dtype=float),
            matched["y_score_pooled"].to_numpy(dtype=float),
            rtol=0,
            atol=0,
        ):
            raise ValueError("Pooled zero-budget predictions are not exact population duplicates")
    return {
        "prediction_rows": int(len(predictions)),
        "prediction_conditions": int(predictions[CONDITION_KEY].drop_duplicates().shape[0]),
        "metric_conditions_recomputed": int(len(recomputed)),
    }


def _expected_condition_frame(
    config: ExperimentConfig,
    split: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    split_instances = split[SPLIT_KEY].drop_duplicates()
    positive_budgets = [value for value in config.calibration.budgets_per_class if value > 0]
    for instance in split_instances.itertuples(index=False):
        base = {
            "dataset": str(instance.dataset),
            "target_subject": str(instance.target_subject),
            "repeat": int(instance.repeat),
            "split_id": str(instance.split_id),
        }
        for method in config.methods:
            for regime in ("population", "source_plus_target"):
                rows.append(
                    {
                        **base,
                        "method": method,
                        "regime": regime,
                        "budget_per_class": 0,
                    }
                )
            for budget in positive_budgets:
                for regime in ("subject", "source_plus_target"):
                    rows.append(
                        {
                            **base,
                            "method": method,
                            "regime": regime,
                            "budget_per_class": int(budget),
                        }
                    )
    return pd.DataFrame(rows, columns=CONDITION_KEY)


def _audit_condition_completeness(
    config: ExperimentConfig,
    metrics: pd.DataFrame,
    split: pd.DataFrame,
) -> dict[str, Any]:
    expected = _expected_condition_frame(config, split)
    observed = metrics[CONDITION_KEY].copy()
    observed["target_subject"] = observed["target_subject"].astype(str)
    observed["split_id"] = observed["split_id"].astype(str)
    for column in ("repeat", "budget_per_class"):
        observed[column] = pd.to_numeric(observed[column], errors="raise").astype(int)
    if observed.duplicated(CONDITION_KEY).any():
        raise ValueError("Duplicate metric condition rows")
    compared = expected.merge(
        observed,
        on=CONDITION_KEY,
        how="outer",
        indicator=True,
        validate="one_to_one",
    )
    if not (compared["_merge"] == "both").all():
        missing = compared.loc[compared["_merge"] == "left_only", CONDITION_KEY].head(10)
        unexpected = compared.loc[compared["_merge"] == "right_only", CONDITION_KEY].head(10)
        raise ValueError(
            "Configured condition grid is incomplete or contains unexpected rows; "
            f"missing={missing.to_dict('records')}, "
            f"unexpected={unexpected.to_dict('records')}"
        )
    return {"expected_conditions": int(len(expected))}


def _audit_assignments(
    output_dir: Path,
    config: ExperimentConfig,
    metrics: pd.DataFrame,
    predictions_expected: bool,
) -> dict[str, Any]:
    split_path = output_dir / "split_assignments.csv.gz"
    calibration_path = output_dir / "calibration_assignments.csv.gz"
    source_path = output_dir / "source_selection.csv"
    source_trial_path = output_dir / "source_trial_assignments.csv.gz"
    split = _read_csv(
        split_path,
        dtype={"target_subject": str, "split_id": str, "trial_uid": str},
    )
    calibration = _read_csv(
        calibration_path,
        dtype={"target_subject": str, "split_id": str, "trial_uid": str},
    )
    source = _read_csv(
        source_path,
        dtype={"target_subject": str, "source_subject": str},
    )
    source_trials = _read_csv(
        source_trial_path,
        dtype={
            "target_subject": str,
            "source_subject": str,
            "trial_uid": str,
        },
    )

    if split.duplicated(SPLIT_KEY + ["trial_uid"]).any():
        raise ValueError("Duplicate split-assignment trial rows")
    if not set(split["role"]).issubset({"calibration_pool", "test"}):
        raise ValueError("Unknown split-assignment roles")
    role_counts = split.groupby(SPLIT_KEY, observed=True)["role"].nunique()
    if (role_counts != 2).any():
        raise ValueError("Each split must contain calibration_pool and test roles")
    group_role_counts = split.groupby(SPLIT_KEY + ["group_id"], observed=True)["role"].nunique()
    if (group_role_counts != 1).any():
        raise ValueError("A session/run group appears in both target roles")

    if calibration.duplicated(
        ["dataset", "target_subject", "repeat", "split_id", "budget_per_class", "trial_uid"]
    ).any():
        raise ValueError("Duplicate calibration-assignment rows")
    if not calibration.empty:
        counts = calibration.groupby(
            ["dataset", "target_subject", "repeat", "split_id", "budget_per_class", "label"],
            observed=True,
        ).size()
        for index, count in counts.items():
            budget = int(index[-2])
            if int(count) != budget:
                raise ValueError(
                    f"Calibration class count {count} does not equal budget {budget} for {index}"
                )
        membership = split[SPLIT_KEY + ["trial_uid", "role"]]
        merged = calibration.merge(
            membership,
            on=SPLIT_KEY + ["trial_uid"],
            how="left",
            validate="many_to_one",
        )
        if merged["role"].isna().any() or not (merged["role"] == "calibration_pool").all():
            raise ValueError("Calibration samples contain non-pool or unknown trials")
        for keys, group in calibration.groupby(
            ["dataset", "target_subject", "repeat", "split_id"], observed=True
        ):
            prior: set[str] = set()
            for budget, budget_group in group.groupby("budget_per_class", sort=True, observed=True):
                current = set(budget_group["trial_uid"].astype(str))
                if prior and not prior.issubset(current):
                    raise ValueError(f"Calibration samples are not nested for {keys} at {budget}")
                prior = current

    if (source["target_subject"].astype(str) == source["source_subject"].astype(str)).any():
        raise ValueError("Target participant appears in source-selection records")
    if source.duplicated(["dataset", "target_subject", "source_subject"]).any():
        raise ValueError("Duplicate source-selection records")

    required_source_trial_columns = {
        "dataset",
        "target_subject",
        "source_subject",
        "selection_seed",
        "trial_uid",
        "session",
        "run",
        "label",
    }
    missing_source_trial_columns = required_source_trial_columns.difference(source_trials.columns)
    if missing_source_trial_columns:
        raise ValueError(
            "source_trial_assignments.csv.gz missing columns: "
            f"{sorted(missing_source_trial_columns)}"
        )
    source_trial_key = ["dataset", "target_subject", "source_subject", "trial_uid"]
    if source_trials.duplicated(source_trial_key).any():
        raise ValueError("Duplicate source-trial assignment rows")
    if (
        source_trials["target_subject"].astype(str)
        == source_trials["source_subject"].astype(str)
    ).any():
        raise ValueError("Target participant appears in source-trial assignments")
    source_labels = pd.to_numeric(source_trials["label"], errors="raise").astype(int)
    if not set(source_labels.unique().tolist()).issubset({0, 1}):
        raise ValueError("Source-trial assignments contain non-binary labels")
    source_trials = source_trials.assign(label=source_labels)

    detailed_rows: list[dict[str, Any]] = []
    source_group_key = ["dataset", "target_subject", "source_subject"]
    for keys, group in source_trials.groupby(source_group_key, observed=True, sort=False):
        seeds = pd.to_numeric(group["selection_seed"], errors="raise").astype(int).unique()
        if len(seeds) != 1:
            raise ValueError(f"Multiple selection seeds within source assignment {keys}")
        uids = group["trial_uid"].astype(str).tolist()
        detailed_rows.append(
            {
                "dataset": str(keys[0]),
                "target_subject": str(keys[1]),
                "source_subject": str(keys[2]),
                "selection_seed_detail": int(seeds[0]),
                "selected_trials_detail": int(len(group)),
                "class_0_trials_detail": int((group["label"] == 0).sum()),
                "class_1_trials_detail": int((group["label"] == 1).sum()),
                "selected_trial_uid_sha256_detail": fingerprint(sorted(uids), length=None),
            }
        )
    detailed = pd.DataFrame(detailed_rows)
    source_check = source.merge(
        detailed,
        on=source_group_key,
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    if not (source_check["_merge"] == "both").all():
        raise ValueError("Source summary and source-trial assignment sets differ")
    integer_pairs = (
        ("selection_seed", "selection_seed_detail"),
        ("selected_trials", "selected_trials_detail"),
        ("class_0_trials", "class_0_trials_detail"),
        ("class_1_trials", "class_1_trials_detail"),
    )
    for summary_column, detail_column in integer_pairs:
        summary_values = pd.to_numeric(source_check[summary_column], errors="raise").astype(int)
        detail_values = pd.to_numeric(source_check[detail_column], errors="raise").astype(int)
        if not np.array_equal(summary_values.to_numpy(), detail_values.to_numpy()):
            raise ValueError(
                f"Source summary {summary_column} does not match detailed assignments"
            )
    if not np.array_equal(
        source_check["selected_trial_uid_sha256"].astype(str).to_numpy(),
        source_check["selected_trial_uid_sha256_detail"].astype(str).to_numpy(),
    ):
        raise ValueError("Source-trial selection digests do not match detailed assignments")

    target_source_counts = source.groupby(
        ["dataset", "target_subject"], observed=True
    )["source_subject"].nunique()
    if config.source.max_subjects is not None and (
        target_source_counts > config.source.max_subjects
    ).any():
        raise ValueError("Source participant cap was exceeded")
    if config.source.max_trials_per_class_per_subject is not None:
        cap = config.source.max_trials_per_class_per_subject
        if (source_check[["class_0_trials", "class_1_trials"]].astype(int) > cap).any().any():
            raise ValueError("Per-class source-trial cap was exceeded")
    if config.source.balance_classes_within_subject and not np.array_equal(
        source_check["class_0_trials"].astype(int).to_numpy(),
        source_check["class_1_trials"].astype(int).to_numpy(),
    ):
        raise ValueError("Source-trial assignments are not class-balanced within participant")

    completeness = _audit_condition_completeness(config, metrics, split)

    details: dict[str, Any] = {
        "split_assignment_rows": int(len(split)),
        "calibration_assignment_rows": int(len(calibration)),
        "source_selection_rows": int(len(source)),
        "source_trial_assignment_rows": int(len(source_trials)),
        **completeness,
    }
    if predictions_expected:
        predictions = _read_csv(
            output_dir / "predictions.csv.gz",
            dtype={"target_subject": str, "split_id": str, "trial_uid": str},
        )
        predicted_test = predictions[SPLIT_KEY + ["trial_uid"]].drop_duplicates()
        assigned_test = split.loc[split["role"] == "test", SPLIT_KEY + ["trial_uid"]]
        matched = predicted_test.merge(
            assigned_test,
            on=SPLIT_KEY + ["trial_uid"],
            how="outer",
            indicator=True,
        )
        if not (matched["_merge"] == "both").all():
            raise ValueError("Predicted trials do not exactly match split-assigned test trials")
    return details


def audit_result_integrity(
    config: ExperimentConfig,
    *,
    metrics: pd.DataFrame | None = None,
) -> dict[str, Any]:
    output_dir = config.output_dir
    try:
        if metrics is None:
            metrics = _read_csv(
                output_dir / "metrics.csv",
                dtype={"target_subject": str, "split_id": str},
            )
        else:
            metrics = metrics.copy()
            metrics["target_subject"] = metrics["target_subject"].astype(str)
            metrics["split_id"] = metrics["split_id"].astype(str)
        protocol = _audit_metric_protocol(metrics)
        successful = metrics.loc[metrics["status"] == "ok"].copy()
        prediction_details: dict[str, Any] = {}
        if config.runtime.save_predictions:
            prediction_details = _audit_predictions(output_dir, successful)
        assignment_details = _audit_assignments(
            output_dir,
            config,
            metrics,
            predictions_expected=config.runtime.save_predictions,
        )
        return {
            "status": "ok",
            **protocol,
            **prediction_details,
            **assignment_details,
            "metrics_checked": list(METRIC_NAMES),
        }
    except Exception as error:
        return {
            "status": "failed",
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
