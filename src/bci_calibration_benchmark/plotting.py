"""Publication-oriented figures generated only from aggregated result tables."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import ExperimentConfig
from .utils import atomic_write_text, json_default, sha256_file


METHOD_LABELS = {
    "logvar_lda": "Log-variance + LDA",
    "csp_lda": "CSP + LDA",
    "riemann_lr": "Riemannian tangent space + LR",
    "eegnet": "EEGNet",
}
REGIME_LABELS = {
    "population": "Population only",
    "subject": "Target subject only",
    "source_plus_target": "Population + target (pooled retraining)",
}
METRIC_LABELS = {
    "roc_auc": "ROC-AUC",
    "balanced_accuracy": "Balanced accuracy",
    "accuracy": "Accuracy",
    "macro_f1": "Macro-F1",
    "brier": "Brier score",
    "log_loss": "Log loss",
}


def _safe_name(value: object) -> str:
    return str(value).replace("/", "-").replace(" ", "_")


def _save_figure(fig: Any, stem: Path) -> list[Path]:
    stem.parent.mkdir(parents=True, exist_ok=True)
    paths = [stem.with_suffix(".png"), stem.with_suffix(".pdf")]
    fig.savefig(paths[0], dpi=300, bbox_inches="tight")
    fig.savefig(paths[1], bbox_inches="tight")
    plt.close(fig)
    return paths


def _metric_limits(metric: str) -> tuple[float, float] | None:
    if metric in {"roc_auc", "balanced_accuracy", "accuracy", "macro_f1"}:
        return (0.0, 1.0)
    if metric == "brier":
        return (0.0, 0.5)
    return None


def make_calibration_figures(
    curve_summary: pd.DataFrame,
    config: ExperimentConfig,
    figure_dir: Path,
) -> list[Path]:
    metric = config.metrics.primary
    data = curve_summary.loc[curve_summary["metric"] == metric].copy()
    outputs: list[Path] = []
    for (dataset, regime), group in data.groupby(["dataset", "regime"], sort=True, observed=True):
        fig, ax = plt.subplots(figsize=(7.0, 4.8))
        source_rows: list[pd.DataFrame] = []
        for method, method_group in group.groupby("method", sort=True, observed=True):
            ordered = method_group.sort_values("budget_per_class")
            x = np.log2(ordered["budget_per_class"].to_numpy(dtype=float) + 1.0)
            y = ordered["mean"].to_numpy(dtype=float)
            line = ax.plot(
                x,
                y,
                marker="o",
                linewidth=1.8,
                label=METHOD_LABELS.get(str(method), str(method)),
            )[0]
            ax.fill_between(
                x,
                ordered["ci_lower"].to_numpy(dtype=float),
                ordered["ci_upper"].to_numpy(dtype=float),
                alpha=0.18,
                color=line.get_color(),
                linewidth=0,
            )
            source_rows.append(ordered)
        budgets = sorted(group["budget_per_class"].astype(int).unique())
        ax.set_xticks(np.log2(np.asarray(budgets, dtype=float) + 1.0), [str(value) for value in budgets])
        ax.set_xlabel("Labeled calibration trials per class")
        ax.set_ylabel(METRIC_LABELS.get(metric, metric))
        ax.set_title(f"{dataset}: {REGIME_LABELS.get(str(regime), str(regime))}")
        limits = _metric_limits(metric)
        if limits is not None:
            ax.set_ylim(*limits)
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend(frameon=False)
        stem = figure_dir / f"calibration_{_safe_name(dataset)}_{_safe_name(regime)}_{metric}"
        outputs.extend(_save_figure(fig, stem))
        pd.concat(source_rows, ignore_index=True).to_csv(
            stem.with_name(stem.name + "_source.csv"), index=False
        )
        outputs.append(stem.with_name(stem.name + "_source.csv"))
    return outputs


def make_aucc_figures(
    aucc_subject: pd.DataFrame,
    config: ExperimentConfig,
    figure_dir: Path,
) -> list[Path]:
    metric = f"aucc_{config.metrics.primary}"
    if aucc_subject.empty or metric not in aucc_subject.columns:
        return []
    outputs: list[Path] = []
    for (dataset, regime), group in aucc_subject.groupby(
        ["dataset", "regime"], sort=True, observed=True
    ):
        ordered_methods = [method for method in config.methods if method in set(group["method"])]
        values = [
            group.loc[group["method"] == method, metric].dropna().to_numpy(dtype=float)
            for method in ordered_methods
        ]
        if not values or all(len(value) == 0 for value in values):
            continue
        fig, ax = plt.subplots(figsize=(7.0, 4.8))
        ax.boxplot(values, tick_labels=[METHOD_LABELS.get(method, method) for method in ordered_methods])
        ax.set_ylabel(f"Normalized log-AUCC ({METRIC_LABELS[config.metrics.primary]})")
        ax.set_title(f"{dataset}: {REGIME_LABELS.get(str(regime), str(regime))}")
        ax.tick_params(axis="x", rotation=18)
        ax.grid(True, axis="y", alpha=0.25)
        stem = figure_dir / f"aucc_{_safe_name(dataset)}_{_safe_name(regime)}_{config.metrics.primary}"
        outputs.extend(_save_figure(fig, stem))
        group.to_csv(stem.with_name(stem.name + "_source.csv"), index=False)
        outputs.append(stem.with_name(stem.name + "_source.csv"))
    return outputs


def make_heterogeneity_figures(
    subject_summary: pd.DataFrame,
    config: ExperimentConfig,
    figure_dir: Path,
) -> list[Path]:
    metric = config.metrics.primary
    preferred_method = "riemann_lr" if "riemann_lr" in config.methods else config.methods[0]
    data = subject_summary.loc[
        (subject_summary["method"] == preferred_method)
        & (subject_summary["regime"] == "source_plus_target")
    ].copy()
    outputs: list[Path] = []
    for dataset, group in data.groupby("dataset", sort=True, observed=True):
        matrix = group.pivot_table(
            index="target_subject",
            columns="budget_per_class",
            values=metric,
            aggfunc="first",
        ).sort_index(key=lambda idx: idx.map(lambda x: int(x) if str(x).isdigit() else str(x)))
        if matrix.empty:
            continue
        fig, ax = plt.subplots(figsize=(7.2, max(4.8, min(12.0, 0.16 * len(matrix) + 2.0))))
        image = ax.imshow(matrix.to_numpy(dtype=float), aspect="auto", interpolation="nearest")
        ax.set_xticks(range(len(matrix.columns)), [str(int(value)) for value in matrix.columns])
        if len(matrix) <= 40:
            ax.set_yticks(range(len(matrix.index)), [str(value) for value in matrix.index])
        else:
            ax.set_yticks([])
        ax.set_xlabel("Labeled calibration trials per class")
        ax.set_ylabel("Target participant")
        ax.set_title(
            f"{dataset}: participant heterogeneity, {METHOD_LABELS.get(preferred_method, preferred_method)}"
        )
        colorbar = fig.colorbar(image, ax=ax)
        colorbar.set_label(METRIC_LABELS.get(metric, metric))
        limits = _metric_limits(metric)
        if limits is not None:
            image.set_clim(*limits)
        stem = figure_dir / f"heterogeneity_{_safe_name(dataset)}_{preferred_method}_{metric}"
        outputs.extend(_save_figure(fig, stem))
        matrix.to_csv(stem.with_name(stem.name + "_source.csv"))
        outputs.append(stem.with_name(stem.name + "_source.csv"))
    return outputs


def make_all_figures(config: ExperimentConfig) -> Path:
    output_dir = config.output_dir
    curve_path = output_dir / "curve_summary.csv"
    subject_path = output_dir / "summary_subject.csv"
    aucc_path = output_dir / "aucc_subject.csv"
    for path in (curve_path, subject_path, aucc_path):
        if not path.exists():
            raise FileNotFoundError(f"Run aggregation before plotting: missing {path}")
    curve = pd.read_csv(curve_path, dtype={"target_subject": str})
    subject = pd.read_csv(subject_path, dtype={"target_subject": str})
    aucc = pd.read_csv(aucc_path, dtype={"target_subject": str})
    figure_dir = output_dir / "figures"
    outputs: list[Path] = []
    outputs.extend(make_calibration_figures(curve, config, figure_dir))
    outputs.extend(make_aucc_figures(aucc, config, figure_dir))
    outputs.extend(make_heterogeneity_figures(subject, config, figure_dir))
    manifest = {
        "schema_version": 1,
        "experiment_fingerprint": config.experiment_fingerprint,
        "files": {
            str(path.relative_to(output_dir)): sha256_file(path)
            for path in outputs
            if path.exists()
        },
    }
    atomic_write_text(
        figure_dir / "figure_manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True, default=json_default) + "\n",
    )
    return figure_dir
