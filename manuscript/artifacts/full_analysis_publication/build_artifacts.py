"""Reproducible builder for publication-ready artifacts.

Every number in every figure and table produced by this script is read
directly from the already-audited, aggregated outputs of the confirmatory
full-cohort run at:

    results/bci-calibration-full-v1-3fb8efe7e617b0c1/

This script performs NO new inferential analysis. The only derived
operations are: filtering/subsetting of existing rows, a unit-preserving
log2(budget + 1) axis transform for display, participant row-ordering for
heatmap legibility, and LaTeX/CSV formatting. See notes/PROVENANCE.md for a
complete account of every such operation.

Run from the repository root:

    python manuscript/artifacts/full_analysis_publication/build_artifacts.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "results" / "bci-calibration-full-v1-3fb8efe7e617b0c1"
ARTIFACT_DIR = Path(__file__).resolve().parent
FIG_DIR = ARTIFACT_DIR / "figures"
TABLE_DIR = ARTIFACT_DIR / "tables"
SRC_DIR = ARTIFACT_DIR / "source_data"
NOTES_DIR = ARTIFACT_DIR / "notes"
for _d in (FIG_DIR, TABLE_DIR, SRC_DIR, NOTES_DIR):
    _d.mkdir(parents=True, exist_ok=True)

if not RESULTS_DIR.exists():
    raise FileNotFoundError(
        f"Audited full-run output directory not found: {RESULTS_DIR}. "
        "This script does not run the benchmark; it only visualizes existing audited outputs."
    )

# --------------------------------------------------------------------------
# Style
# --------------------------------------------------------------------------
plt.rcParams.update(
    {
        "font.family": "serif",
        "font.size": 10,
        "axes.titlesize": 10.5,
        "axes.titleweight": "bold",
        "axes.labelsize": 10,
        "legend.fontsize": 8.5,
        "xtick.labelsize": 8.7,
        "ytick.labelsize": 8.7,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "figure.dpi": 150,
    }
)

METHOD_ORDER = ["logvar_lda", "csp_lda", "riemann_lr"]
METHOD_STYLE = {
    "logvar_lda": {"color": "#1b9e77", "marker": "o", "linestyle": "-", "label": "Log-variance + LDA"},
    "csp_lda": {"color": "#d95f02", "marker": "s", "linestyle": "--", "label": "CSP + LDA"},
    "riemann_lr": {"color": "#7570b3", "marker": "^", "linestyle": ":", "label": "Riemannian TS + LR"},
}
REGIME_LABEL = {
    "population": "Population only",
    "subject": "Subject only",
    "source_plus_target": "Source + target (pooled)",
}
PANEL_LABELS = "ABCDEFGH"


def savefig(fig: plt.Figure, stem: Path) -> None:
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(stem.with_suffix(".png"), bbox_inches="tight", dpi=300)
    plt.close(fig)


def panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.08,
        1.1,
        label,
        transform=ax.transAxes,
        fontsize=12.5,
        fontweight="bold",
        va="top",
        ha="left",
    )


def fmt_holm_label(p: float) -> str:
    """Plain-text Holm-adjusted p-value label for matplotlib figure
    annotations, e.g. 'Holm p < 0.001' or 'Holm p = 0.016'. No significance
    star is appended: the adjusted p-value itself is the displayed signal,
    so a redundant star would only clutter the annotation."""
    if pd.isna(p):
        return "Holm p = --"
    if p < 0.001:
        return "Holm p < 0.001"
    return f"Holm p = {p:.3f}"


def fmt_p_tex(p: float) -> str:
    """LaTeX p-value formatting (math-mode comparison operator), for .tex tables."""
    if pd.isna(p):
        return "--"
    if p < 0.001:
        return "$<$0.001"
    return f"{p:.3f}"


def fmt_num(x: float, nd: int = 3) -> str:
    if pd.isna(x):
        return "--"
    return f"{x:.{nd}f}"


def tex_escape(s: object) -> str:
    """Escape plain text for LaTeX. Input must be plain text, not pre-written
    LaTeX (a "×" unicode character is treated as literal multiplication and
    converted to math-mode \\times; a literal backslash is treated as raw
    data and escaped, never as an already-valid LaTeX command)."""
    text = str(s)
    for char, escaped in (
        ("\\", r"\textbackslash{}"),
        ("_", r"\_"),
        ("%", r"\%"),
        ("&", r"\&"),
        ("#", r"\#"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
        ("×", r"$\times$"),
    ):
        text = text.replace(char, escaped)
    return text


def sig_marker(p: float) -> str:
    if pd.isna(p):
        return ""
    return "*" if p < 0.05 else ""


# --------------------------------------------------------------------------
# Load audited data (read-only; no recomputation of any statistic)
# --------------------------------------------------------------------------
curve = pd.read_csv(RESULTS_DIR / "curve_summary.csv")
aucc_subject = pd.read_csv(RESULTS_DIR / "aucc_subject.csv", dtype={"target_subject": str})
pairwise = pd.read_csv(RESULTS_DIR / "pairwise_tests.csv")
mixed_coef = pd.read_csv(RESULTS_DIR / "mixed_effects_coefficients.csv")
mixed_diag = json.loads((RESULTS_DIR / "mixed_effects_diagnostics.json").read_text())
summary_subject = pd.read_csv(RESULTS_DIR / "summary_subject.csv", dtype={"target_subject": str})
participant_flow = pd.read_csv(RESULTS_DIR / "participant_flow.csv")
result_audit = json.loads((RESULTS_DIR / "result_audit.json").read_text())
aggregation_manifest = json.loads((RESULTS_DIR / "aggregation_manifest.json").read_text())
run_manifest = json.loads((RESULTS_DIR / "run_manifest.json").read_text())

FLOW = participant_flow.set_index("dataset")["participants_attempted"].to_dict()
assert FLOW == {"Lee2019_MI": 54, "BNCI2014_001": 9, "Zhou2016": 2}, (
    "participant_flow.csv no longer matches the expected structurally validated "
    f"cohort; refusing to build artifacts against unexpected counts: {FLOW}"
)
assert result_audit["status"] == "ok", "result_audit.json does not report status=ok"


# ==========================================================================
# Figure 1 — study design schematic (conceptual; no data)
#
# Strict orthogonal (Manhattan) routing: every connector is a sequence of
# purely horizontal and purely vertical segments, each drawn through empty
# canvas space that is reserved for it and verified (by construction, see
# inline notes) not to cross any box or any other connector. No diagonal
# segments and no line-over-line crossings anywhere in this figure.
# ==========================================================================
def make_figure1() -> None:
    LEFT, MID, RIGHT = 2.4, 8.6, 13.4
    fig, ax = plt.subplots(figsize=(12.4, 13.6))
    ax.set_xlim(-0.4, 18.4)
    ax.set_ylim(0, 17.2)
    ax.axis("off")

    def box(cx, cy, w, h, text, fc="#f4f4f4", ec="#333333", fontsize=9.0, ls="solid"):
        patch = FancyBboxPatch(
            (cx - w / 2, cy - h / 2),
            w,
            h,
            boxstyle="round,pad=0.02,rounding_size=0.12",
            linewidth=1.1,
            edgecolor=ec,
            facecolor=fc,
            linestyle=ls,
        )
        ax.add_patch(patch)
        ax.text(cx, cy, text, ha="center", va="center", fontsize=fontsize, linespacing=1.35)
        return {"cx": cx, "cy": cy, "w": w, "h": h, "top": cy + h / 2, "bottom": cy - h / 2}

    def varrow(x, y0, y1, color="#333333", lw=1.15):
        """Pure vertical arrow from (x, y0) down to (x, y1). y0 > y1."""
        ax.add_patch(
            FancyArrowPatch(
                (x, y0), (x, y1), arrowstyle="-|>", mutation_scale=12,
                linewidth=lw, color=color, shrinkA=0, shrinkB=0,
            )
        )

    def hline(x0, x1, y, color="#333333", lw=1.15):
        ax.plot([x0, x1], [y, y], color=color, linewidth=lw, solid_capstyle="butt", zorder=1)

    def vline(x, y0, y1, color="#333333", lw=1.15):
        ax.plot([x, x], [y0, y1], color=color, linewidth=lw, solid_capstyle="butt", zorder=1)

    # -- Row 1: the two independent starting points -----------------------
    src = box(LEFT, 16.0, 5.2, 1.2, "Source participants\n(other subjects, same dataset;\n≤ 10 subjects, ≤ 20 trials/class each)", fontsize=8.5)
    tgt = box(11.0, 16.0, 6.0, 1.2, "Target participant")

    # -- Row 2: target session split (local T-branch, both legs are pure
    #    verticals dropped from two distinct x-offsets on TGT's bottom edge)
    cal = box(MID, 13.9, 4.6, 1.2, "Earlier session(s) →\nCalibration pool")
    test = box(RIGHT, 13.9, 4.6, 1.2, "Latest session →\nHeld-out test\n(untouched until scoring)")
    varrow(MID, tgt["bottom"], cal["top"])
    varrow(RIGHT, tgt["bottom"], test["top"])

    # -- Row 3: calibration budgets, directly below the calibration pool --
    budg = box(MID, 11.9, 4.6, 0.95, "Calibration budgets (trials/class):\n0, 5, 10, 20, 40", fc="#ffffff", ec="#888888", fontsize=8.4)
    varrow(MID, cal["bottom"], budg["top"])

    # -- Row 3.5: small restated input tags, local to the pooled-regime
    #    column only, so no long-distance wire ever has to cross the busy
    #    MID column's vertical traffic (source: same info as the Row-1 box).
    tag_src = box(12.3, 11.9, 3.0, 0.72, "Source participants\n(same cohort as above)", fc="#ffffff", ec="#999999", fontsize=7.6, ls="dashed")
    tag_cal = box(15.1, 11.9, 3.0, 0.72, "Calibration pool\n(same as above)", fc="#ffffff", ec="#999999", fontsize=7.6, ls="dashed")

    # -- Row 4: three training regimes -------------------------------------
    pop = box(LEFT, 9.6, 4.0, 1.2, "Population only\n(source participants)")
    subj = box(MID, 9.6, 4.0, 1.2, "Subject only\n(calibration pool)")
    pool = box(RIGHT, 9.6, 4.4, 1.35, "Source + target\n(pooled retraining;\nsource participants +\ncalibration pool)")
    varrow(LEFT, src["bottom"], pop["top"])  # single clean vertical, same column
    varrow(MID, budg["bottom"], subj["top"])  # single clean vertical, same column
    varrow(12.3, tag_src["bottom"], pool["top"])
    varrow(15.1, tag_cal["bottom"], pool["top"])

    # -- Row 5: decoders, one wide box spanning under all three regimes,
    #    fed by three pure verticals aligned to each regime's own column.
    dec = box(
        7.9, 7.3, 13.4, 1.2,
        "Decoders (fit independently per regime × budget × repeat):\n"
        "log-variance + LDA   ·   CSP + LDA   ·   Riemannian tangent-space + LR",
    )
    varrow(LEFT, pop["bottom"], dec["top"])
    varrow(MID, subj["bottom"], dec["top"])
    varrow(RIGHT, pool["bottom"], dec["top"])

    # -- Row 6: evaluation, fed by decoders (same-column vertical) and by
    #    the held-out test set via a dedicated right-margin bypass lane
    #    that never overlaps any box (verified against every box's right
    #    edge below; margin lane sits strictly to the right of all of them).
    ev = box(7.9, 5.1, 9.2, 1.2, "Participant-level evaluation on the\nuntouched held-out test session\n(ROC-AUC + 5 secondary metrics)", fontsize=8.8)
    varrow(7.9, dec["bottom"], ev["top"])

    MARGIN_X = 17.4
    bypass_y = 13.0  # just below the "test" box, above every other row
    hline(RIGHT, MARGIN_X, bypass_y)
    vline(RIGHT, test["bottom"], bypass_y)
    vline(MARGIN_X, bypass_y, 5.1)
    entry_x = ev["cx"] + ev["w"] / 2  # enter evaluation box at its right edge
    hline(entry_x, MARGIN_X, 5.1)
    ax.add_patch(
        FancyArrowPatch(
            (entry_x + 0.35, 5.1), (entry_x, 5.1), arrowstyle="-|>", mutation_scale=12,
            linewidth=1.15, color="#333333", shrinkA=0, shrinkB=0,
        )
    )

    # -- Row 7: audited outputs --------------------------------------------
    out = box(
        7.9, 3.0, 10.4, 1.2,
        "Audited outputs: metrics.csv · predictions.csv.gz ·\n"
        "result_audit.json · aggregation · figures",
        fc="#eef3fb",
    )
    varrow(7.9, ev["bottom"], out["top"])

    ax.set_title("Study design: leakage-resistant later-session calibration benchmark", fontsize=13, pad=18)
    savefig(fig, FIG_DIR / "Figure1_study_design")


# ==========================================================================
# Figure 2 — main calibration curves (2x3: dataset rows x method columns;
# each panel overlays the two regimes that are directly comparable at a
# shared budget axis: subject-only and source+target pooled retraining).
# ==========================================================================
REGIME_OVERLAY_STYLE = {
    "subject": {"color": "#2b6cb0", "marker": "o", "linestyle": "-", "label": "Subject-only"},
    "source_plus_target": {"color": "#c2410c", "marker": "s", "linestyle": "--", "label": "Source + target (pooled)"},
}


def make_figure2() -> pd.DataFrame:
    datasets = ["Lee2019_MI", "BNCI2014_001"]
    regimes = ["subject", "source_plus_target"]
    base = curve[(curve.metric == "roc_auc") & curve.regime.isin(regimes)]
    all_budgets = sorted(base.budget_per_class.unique())

    fig, axes = plt.subplots(2, 3, figsize=(13.2, 7.8), sharey=True)
    source_rows: list[pd.DataFrame] = []
    idx = 0
    for i, dataset in enumerate(datasets):
        for j, method in enumerate(METHOD_ORDER):
            ax = axes[i, j]
            label = PANEL_LABELS[idx]
            idx += 1
            for regime in regimes:
                m = base[
                    (base.dataset == dataset) & (base.method == method) & (base.regime == regime)
                ].sort_values("budget_per_class")
                if m.empty:
                    continue
                style = REGIME_OVERLAY_STYLE[regime]
                x = np.log2(m.budget_per_class.to_numpy(dtype=float) + 1.0)
                y = m["mean"].to_numpy(dtype=float)
                ax.plot(
                    x, y, color=style["color"], marker=style["marker"], linestyle=style["linestyle"],
                    linewidth=1.8, markersize=5.5, label=style["label"],
                )
                ax.fill_between(
                    x, m.ci_lower.to_numpy(dtype=float), m.ci_upper.to_numpy(dtype=float),
                    color=style["color"], alpha=0.16, linewidth=0,
                )
                tagged = m.copy()
                tagged["figure_panel"] = label
                source_rows.append(tagged)
            ax.set_xticks(np.log2(np.asarray(all_budgets, dtype=float) + 1.0))
            ax.set_xticklabels([str(int(b)) for b in all_budgets])
            ax.set_ylim(0.45, 1.0)
            ax.axhline(0.5, color="0.65", linewidth=0.8, linestyle=":")
            ax.set_title(f"{dataset}\n{METHOD_STYLE[method]['label']}", fontsize=10)
            if i == 1:
                ax.set_xlabel("Calibration trials per class")
            if j == 0:
                ax.set_ylabel("ROC-AUC")
            panel_label(ax, label)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle(
        "Calibration trajectories: subject-only vs. pooled source + target retraining",
        y=1.03, fontsize=12.5,
    )
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    savefig(fig, FIG_DIR / "Figure2_main_calibration_curves")
    out = pd.concat(source_rows, ignore_index=True)
    out.to_csv(SRC_DIR / "Figure2_main_calibration_curves.csv", index=False)
    return out


# ==========================================================================
# Figure 3 — confirmatory paired contrasts (H2, budgets 5 & 10)
# ==========================================================================
def make_figure3() -> pd.DataFrame:
    budgets = [5, 10]
    scopes = ["ALL", "Lee2019_MI", "BNCI2014_001"]
    scope_label = {
        "ALL": f"Pooled across datasets (confirmatory, N={FLOW['Lee2019_MI'] + FLOW['BNCI2014_001'] + FLOW['Zhou2016']})",
        "Lee2019_MI": f"Lee2019_MI (supportive, n={FLOW['Lee2019_MI']})",
        "BNCI2014_001": f"BNCI2014_001 (supportive, n={FLOW['BNCI2014_001']})",
    }
    scope_color = {"ALL": "#111111", "Lee2019_MI": "#1b9e77", "BNCI2014_001": "#d95f02"}
    h2 = pairwise[
        pairwise.family.isin(["H2_regime_low_budget_confirmatory", "H2_regime_low_budget_dataset_supportive"])
        & pairwise.budget_per_class.isin(budgets)
        & pairwise.scope_dataset.isin(scopes)
    ].copy()

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 5.4), sharex=True)
    all_rows: list[pd.Series] = []
    for k, budget in enumerate(budgets):
        ax = axes[k]
        sub = h2[h2.budget_per_class == budget]
        yticks_major, yticklabels_major = [], []
        for mi, method in enumerate(METHOD_ORDER):
            base_y = -(mi * 4)
            for si, scope in enumerate(scopes):
                row = sub[(sub.method_left == method) & (sub.scope_dataset == scope)]
                if row.empty:
                    continue
                row = row.iloc[0]
                all_rows.append(row)
                y = base_y - si
                mean, lo, hi, p = row.mean_difference, row.ci_lower, row.ci_upper, row.p_holm
                marker = "D" if scope == "ALL" else "o"
                ax.errorbar(
                    mean,
                    y,
                    xerr=[[mean - lo], [hi - mean]],
                    fmt=marker,
                    color=scope_color[scope],
                    markersize=7 if scope == "ALL" else 5.5,
                    capsize=3,
                    linewidth=1.3,
                    elinewidth=1.1,
                )
                # Holm-adjusted p-values are annotated only for the pooled
                # confirmatory diamond, per the confirmatory/supportive
                # inferential-role distinction; dataset-specific supportive
                # points retain their CIs (drawn above) but are not
                # individually p-annotated, to avoid implying dataset-level
                # significance testing that the protocol does not perform.
                if scope == "ALL":
                    ax.annotate(
                        fmt_holm_label(p),
                        (hi, y),
                        xytext=(5, 0),
                        textcoords="offset points",
                        fontsize=7.5,
                        fontweight="bold",
                        va="center",
                        color="0.15",
                    )
            yticks_major.append(base_y - 1)
            yticklabels_major.append(METHOD_STYLE[method]["label"])
        ax.axvline(0, color="0.3", linewidth=1.0)
        ax.set_yticks(yticks_major)
        ax.set_yticklabels(yticklabels_major)
        ax.set_ylim(-(len(METHOD_ORDER) * 4) + 1, 2)
        ax.margins(x=0.35)
        ax.set_xlabel("Mean ROC-AUC difference\n(source + target − subject)")
        ax.set_title(f"Budget = {budget} trials/class")
        panel_label(ax, PANEL_LABELS[k])
    legend_handles = [
        Line2D([0], [0], marker="D", color=scope_color["ALL"], linestyle="", markersize=7, label=scope_label["ALL"]),
        Line2D([0], [0], marker="o", color=scope_color["Lee2019_MI"], linestyle="", markersize=5.5, label=scope_label["Lee2019_MI"]),
        Line2D([0], [0], marker="o", color=scope_color["BNCI2014_001"], linestyle="", markersize=5.5, label=scope_label["BNCI2014_001"]),
    ]
    fig.legend(handles=legend_handles, loc="lower center", ncol=1, frameon=False, bbox_to_anchor=(0.5, -0.02), fontsize=8.5)
    fig.suptitle("H2: pooled retraining vs. subject-only calibration (source + target − subject)", y=1.05, fontsize=12)
    fig.tight_layout(rect=(0, 0.14, 1, 1))
    savefig(fig, FIG_DIR / "Figure3_paired_contrasts_budget5_10")
    out = pd.DataFrame(all_rows)
    out.to_csv(SRC_DIR / "Figure3_paired_contrasts_budget5_10.csv", index=False)
    return out


# ==========================================================================
# Figure 4 — participant heterogeneity (riemann_lr, ROC-AUC)
# ==========================================================================
def make_figure4() -> pd.DataFrame:
    method = "riemann_lr"
    datasets = ["Lee2019_MI", "BNCI2014_001"]
    regimes = ["subject", "source_plus_target"]
    fig, axes = plt.subplots(2, 2, figsize=(10.4, 9.6))
    fig.subplots_adjust(hspace=0.55, wspace=0.3)
    source_rows: list[pd.DataFrame] = []
    idx = 0

    order_by_dataset: dict[str, list[str]] = {}
    for dataset in datasets:
        ref = summary_subject[
            (summary_subject.dataset == dataset)
            & (summary_subject.method == method)
            & (summary_subject.regime == "source_plus_target")
        ]
        order_by_dataset[dataset] = ref.groupby("target_subject")["roc_auc"].mean().sort_values().index.tolist()

    last_image = None
    for i, dataset in enumerate(datasets):
        for j, regime in enumerate(regimes):
            ax = axes[i, j]
            label = PANEL_LABELS[idx]
            idx += 1
            sub = summary_subject[
                (summary_subject.dataset == dataset)
                & (summary_subject.method == method)
                & (summary_subject.regime == regime)
            ]
            pivot = sub.pivot_table(index="target_subject", columns="budget_per_class", values="roc_auc", aggfunc="first")
            pivot = pivot.reindex(order_by_dataset[dataset])
            pivot = pivot[sorted(pivot.columns)]
            last_image = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", vmin=0.4, vmax=1.0, cmap="viridis", interpolation="nearest")
            ax.set_xticks(range(len(pivot.columns)))
            ax.set_xticklabels([str(int(c)) for c in pivot.columns])
            if dataset == "BNCI2014_001":
                ax.set_yticks(range(len(pivot.index)))
                ax.set_yticklabels(pivot.index)
            else:
                ax.set_yticks([])
            ax.set_xlabel("Calibration trials per class")
            if j == 0:
                ax.set_ylabel(f"{dataset} participants\n(sorted by mean pooled ROC-AUC)")
            ax.set_title(f"{dataset} — {REGIME_LABEL[regime]}")
            panel_label(ax, label)
            melted = pivot.reset_index().melt(id_vars="target_subject", var_name="budget_per_class", value_name="roc_auc")
            melted["dataset"] = dataset
            melted["regime"] = regime
            melted["method"] = method
            melted["figure_panel"] = label
            melted["participant_order_rank"] = melted["target_subject"].map(
                {subj: rank for rank, subj in enumerate(order_by_dataset[dataset])}
            )
            source_rows.append(melted)

    fig.subplots_adjust(right=0.9)
    cbar_ax = fig.add_axes((0.93, 0.15, 0.015, 0.7))
    fig.colorbar(last_image, cax=cbar_ax, label="ROC-AUC")
    fig.suptitle(f"Participant heterogeneity in calibration response ({METHOD_STYLE[method]['label']})", y=1.0, fontsize=12)
    savefig(fig, FIG_DIR / "Figure4_participant_heterogeneity")
    out = pd.concat(source_rows, ignore_index=True)
    out.to_csv(SRC_DIR / "Figure4_participant_heterogeneity.csv", index=False)
    return out


# ==========================================================================
# Supplement figure — Zhou2016, descriptive only
# ==========================================================================
def make_supplement_figure_zhou2016() -> pd.DataFrame:
    dataset = "Zhou2016"
    regimes = ["subject", "source_plus_target"]
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.3))
    source_rows: list[pd.DataFrame] = []
    for j, regime in enumerate(regimes):
        ax = axes[j]
        sub = curve[(curve.dataset == dataset) & (curve.regime == regime) & (curve.metric == "roc_auc")]
        for method in METHOD_ORDER:
            m = sub[sub.method == method].sort_values("budget_per_class")
            if m.empty:
                continue
            style = METHOD_STYLE[method]
            x = np.log2(m.budget_per_class.to_numpy(dtype=float) + 1.0)
            y = m["mean"].to_numpy(dtype=float)
            ax.plot(x, y, color=style["color"], marker=style["marker"], linestyle=style["linestyle"], linewidth=1.6, markersize=5, label=style["label"])
            ax.fill_between(x, m.ci_lower.to_numpy(dtype=float), m.ci_upper.to_numpy(dtype=float), color=style["color"], alpha=0.15, linewidth=0)
            tagged = m.copy()
            tagged["figure_panel"] = PANEL_LABELS[j]
            source_rows.append(tagged)
        budgets = sorted(sub.budget_per_class.unique())
        ax.set_xticks(np.log2(np.asarray(budgets, dtype=float) + 1.0))
        ax.set_xticklabels([str(int(b)) for b in budgets])
        ax.set_ylim(0.4, 1.0)
        ax.axhline(0.5, color="0.65", linewidth=0.8, linestyle=":")
        ax.set_title(f"{REGIME_LABEL[regime]}")
        ax.set_xlabel("Calibration trials per class")
        if j == 0:
            ax.set_ylabel("ROC-AUC")
        panel_label(ax, PANEL_LABELS[j])
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, -0.05))
    fig.suptitle("Zhou2016 (n = 2): descriptive / supportive only — not an independent inferential dataset", y=1.06, fontsize=11.5)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    savefig(fig, FIG_DIR / "Supplement_Figure_Zhou2016_descriptive")
    out = pd.concat(source_rows, ignore_index=True)
    out.to_csv(SRC_DIR / "Supplement_Figure_Zhou2016_descriptive.csv", index=False)
    return out


# ==========================================================================
# Table 1 — datasets and confirmatory cohort
# ==========================================================================
def make_table1() -> pd.DataFrame:
    rows = [
        dict(
            dataset="Lee2019_MI",
            nominal=54,
            excluded=0,
            excluded_detail="None",
            validated=FLOW["Lee2019_MI"],
            sessions=2,
            channels=62,
            task="Left/right motor imagery",
            role="Contributes to pooled confirmatory analysis; dataset-specific supportive",
        ),
        dict(
            dataset="BNCI2014_001",
            nominal=9,
            excluded=0,
            excluded_detail="None",
            validated=FLOW["BNCI2014_001"],
            sessions=2,
            channels=22,
            task="Left/right motor imagery",
            role="Contributes to pooled confirmatory analysis; dataset-specific supportive",
        ),
        dict(
            dataset="Zhou2016",
            nominal=4,
            excluded=2,
            excluded_detail="Subjects 2, 4 (structural)",
            validated=FLOW["Zhou2016"],
            sessions=3,
            channels=14,
            task="Left/right motor imagery",
            role="Contributes to pooled confirmatory analysis (n=2); dataset-specific descriptive only",
        ),
    ]
    df = pd.DataFrame(rows)
    df.to_csv(TABLE_DIR / "Table1_datasets_and_cohort.csv", index=False)
    # The CSV keeps every field, including "task", as the full record. The
    # LaTeX rendering below drops the Task column (identical "Left/right
    # motor imagery" on all three rows; stated once in the caption instead)
    # and gives Excluded a controlled wrapping width, since a redundant
    # per-row Task column was pushing the table past normal manuscript
    # width even with tabularx (up to ~47.8pt overfull, independently
    # pdflatex-compiled).
    assert df["task"].nunique() == 1, "Table 1 rows no longer share one task; caption assumes a single common task"
    common_task = df["task"].iloc[0]

    lines = [
        "% Requires \\usepackage{booktabs}, \\usepackage{tabularx}",
        "\\begin{table}[t]",
        "\\centering",
        "\\small",
        "\\caption{Confirmatory datasets and cohort eligibility. All three datasets share the "
        f"same task: {tex_escape(common_task)} (binary left-hand vs.\\ right-hand "
        "classification). Nominal counts are the number of subject IDs each dataset "
        "publishes; final counts are participants that passed every pre-specified "
        "structural check (session count, run count, per-class trial minimums, channel "
        "montage) before any model was fit. See docs/DECISIONS.md for exclusion evidence.}",
        "\\label{tab:datasets_cohort}",
        "\\begin{tabularx}{\\textwidth}{@{} l r p{2.3cm} r r r X @{}}",
        "\\toprule",
        "Dataset & Nominal $N$ & Excluded & Final $N$ & Sessions & Channels & Confirmatory role \\\\",
        "\\midrule",
    ]
    for _, r in df.iterrows():
        lines.append(
            f"{tex_escape(r.dataset)} & {r.nominal} & {tex_escape(r.excluded_detail)} & "
            f"{r.validated} & {r.sessions} & {r.channels} & {tex_escape(r.role)} \\\\"
        )
    lines += ["\\bottomrule", "\\end{tabularx}", "\\end{table}", ""]
    (TABLE_DIR / "Table1_datasets_and_cohort.tex").write_text("\n".join(lines))
    return df


# ==========================================================================
# Table 2 — main confirmatory contrasts (H2 pooled @5,10; H3 pooled, subject)
# ==========================================================================
# Table 2's rendered LaTeX table uses manuscript-facing labels; the CSV
# (written before these are applied) keeps the original machine-readable
# `contrast`/`method_display` values for provenance. Values themselves are
# never altered, only how the single known H3 contrast string is displayed.
CONTRAST_LABELS = {
    "riemann_lr - csp_lda": "Riemannian TS + LR $-$ CSP + LDA",
}


def _method_label(name: str) -> str:
    return METHOD_STYLE.get(name, {}).get("label", name)


def _humanize_contrast(value: str) -> str:
    label = CONTRAST_LABELS.get(value)
    assert label is not None, f"Unmapped contrast for Table 2 humanized rendering: {value!r}"
    return label


def make_table2() -> pd.DataFrame:
    h2 = pairwise[pairwise.family == "H2_regime_low_budget_confirmatory"].copy()
    h3 = pairwise[(pairwise.family == "H3_method_aucc_confirmatory") & (pairwise.regime == "subject")].copy()
    combined = pd.concat([h2, h3], ignore_index=True)
    combined["method_display"] = np.where(
        combined.method_left == combined.method_right,
        combined.method_left,
        combined.method_left + " vs " + combined.method_right,
    )
    combined["budget_or_regime"] = np.where(
        combined.budget_per_class.notna(),
        combined.budget_per_class.astype("Int64").astype(str) + " trials/class",
        combined.regime + " regime (AUCC)",
    )
    cols = [
        "family",
        "contrast",
        "budget_or_regime",
        "budget_per_class",
        "regime",
        "method_display",
        "n_pairs",
        "mean_difference",
        "ci_lower",
        "ci_upper",
        "p_value",
        "p_holm",
        "rank_biserial",
    ]
    out = combined[cols].copy()
    out.to_csv(TABLE_DIR / "Table2_confirmatory_contrasts.csv", index=False)
    # The CSV keeps every column, including the raw budget_per_class/regime
    # fields (used to build the panel-specific LaTeX columns below) and the
    # unadjusted raw p_value, as the full audit trail. The rendered LaTeX
    # table presents H2 and H3 as two labeled panels within one table,
    # stating each contrast once in its panel heading instead of repeating
    # it as a per-row column (the prior repeated-Contrast-column design
    # overflowed ordinary manuscript width under independent pdflatex
    # verification).

    h2_rows = out[out.family == "H2_regime_low_budget_confirmatory"]
    h3_rows = out[out.family == "H3_method_aucc_confirmatory"]

    lines = [
        "% Requires \\usepackage{booktabs}, \\usepackage{tabularx}, \\usepackage{threeparttable}",
        "\\begin{table}[t]",
        "\\centering",
        "\\small",
        "\\begin{threeparttable}",
        "\\caption{Main confirmatory pairwise contrasts, pooled participant-weighted across "
        "all three datasets (Lee2019\\_MI, BNCI2014\\_001, Zhou2016; $n=65$ participants total; "
        "Lee2019\\_MI contributes 54 of 65, BNCI2014\\_001 contributes 9 of 65, and Zhou2016 "
        "contributes 2 of 65 participants to the participant-weighted pooled estimate). "
        "Panel A (H2): source+target pooled retraining vs.\\ subject-only calibration, "
        "ROC-AUC, at budgets 5 and 10 trials/class. Panel B (H3): decoder calibration "
        "efficiency, normalized log-AUCC, subject-only regime.}",
        "\\label{tab:confirmatory_contrasts}",
        "\\begin{tabularx}{\\textwidth}{@{} X l r l l r @{}}",
        "\\toprule",
        "\\multicolumn{6}{@{}l}{\\textbf{Panel A --- H2: Source + target pooled retraining "
        "$-$ subject-only calibration (ROC-AUC)}} \\\\",
        "\\midrule",
        "Method & Budget (trials/class) & $n$ & Mean $\\Delta$ [95\\% CI] & Holm $p$ & "
        "$r_\\mathrm{rb}$ \\\\",
        "\\midrule",
    ]
    for _, r in h2_rows.iterrows():
        ci = f"{fmt_num(r.mean_difference)} [{fmt_num(r.ci_lower)}, {fmt_num(r.ci_upper)}]"
        lines.append(
            f"{tex_escape(_method_label(r.method_display))} & {int(r.budget_per_class)} & "
            f"{int(r.n_pairs)} & {ci} & {fmt_p_tex(r.p_holm)} & {fmt_num(r.rank_biserial)} \\\\"
        )
    lines += [
        "\\midrule",
        "\\multicolumn{6}{@{}l}{\\textbf{Panel B --- H3: Decoder calibration efficiency "
        "(normalized log-AUCC)}} \\\\",
        "\\midrule",
        "Method contrast & Regime & $n$ & Mean $\\Delta$ [95\\% CI] & Holm $p$ & "
        "$r_\\mathrm{rb}$ \\\\",
        "\\midrule",
    ]
    for _, r in h3_rows.iterrows():
        ci = f"{fmt_num(r.mean_difference)} [{fmt_num(r.ci_lower)}, {fmt_num(r.ci_upper)}]"
        lines.append(
            f"{tex_escape(_humanize_contrast(r.contrast))} & "
            f"{tex_escape(REGIME_LABEL.get(r.regime, r.regime))} & {int(r.n_pairs)} & {ci} & "
            f"{fmt_p_tex(r.p_holm)} & {fmt_num(r.rank_biserial)} \\\\"
        )
    lines += [
        "\\bottomrule",
        "\\end{tabularx}",
        "\\begin{tablenotes}",
        "\\footnotesize",
        "\\item Holm-adjusted $p$ shown; no significance stars are used and the adjusted "
        "value itself is the displayed signal. Unadjusted raw $p$-values are omitted here "
        "for width and are preserved in \\texttt{Table2\\_confirmatory\\_contrasts.csv}.",
        "\\end{tablenotes}",
        "\\end{threeparttable}",
        "\\end{table}",
        "",
    ]
    (TABLE_DIR / "Table2_confirmatory_contrasts.tex").write_text("\n".join(lines))
    return out


# ==========================================================================
# Table 3 — mixed-effects model summary (fixed effects only)
# ==========================================================================
VARIANCE_TERMS = {"Group Var", "Group x log2_budget Cov", "log2_budget Var"}

TERM_LABELS = {
    "Intercept": "Intercept",
    "C(method)[T.logvar_lda]": "Method: log-variance + LDA (vs. CSP + LDA)",
    "C(method)[T.riemann_lr]": "Method: Riemannian TS + LR (vs. CSP + LDA)",
    "C(regime)[T.subject]": "Regime: subject-only (vs. source + target)",
    "C(dataset)[T.Lee2019_MI]": "Dataset: Lee2019_MI (vs. BNCI2014_001)",
    "C(dataset)[T.Zhou2016]": "Dataset: Zhou2016 (vs. BNCI2014_001)",
    "C(method)[T.logvar_lda]:C(regime)[T.subject]": "Log-variance + LDA × subject-only",
    "C(method)[T.riemann_lr]:C(regime)[T.subject]": "Riemannian TS + LR × subject-only",
    "log2_budget": "log2(budget + 1)",
    "log2_budget:C(method)[T.logvar_lda]": "log2(budget+1) × log-variance + LDA",
    "log2_budget:C(method)[T.riemann_lr]": "log2(budget+1) × Riemannian TS + LR",
    "log2_budget:C(regime)[T.subject]": "log2(budget+1) × subject-only",
    "log2_budget:C(method)[T.logvar_lda]:C(regime)[T.subject]": "log2(budget+1) × log-variance + LDA × subject-only",
    "log2_budget:C(method)[T.riemann_lr]:C(regime)[T.subject]": "log2(budget+1) × Riemannian TS + LR × subject-only",
}

# Compact, manuscript-ready subset (~8 rows): regime effect, budget effect,
# their interaction, method main effects, and dataset fixed effects.
MAIN_TABLE_TERMS = [
    "Intercept",
    "C(regime)[T.subject]",
    "log2_budget",
    "log2_budget:C(regime)[T.subject]",
    "C(method)[T.logvar_lda]",
    "C(method)[T.riemann_lr]",
    "C(dataset)[T.Lee2019_MI]",
    "C(dataset)[T.Zhou2016]",
]


def _mixed_effects_diagnostic_note_item() -> str:
    warnings_text = tex_escape(
        "; ".join(w.rstrip(".") for w in mixed_diag.get("warnings", [])) or "none"
    )
    return (
        "\\item[*] $p < 0.05$, uncorrected (single model, not a multiple-comparison "
        f"family). Diagnostic warning recorded at fit time: {warnings_text}."
    )


def _render_mixed_effects_table(
    rows: pd.DataFrame, caption: str, label: str, tex_path: Path
) -> None:
    # threeparttable ensures the footnote renders as a full-width line below
    # the table rather than beside the last rows (the previous \vspace{2pt}
    # + inline \footnotesize{...} pattern did not reliably do this).
    lines = [
        "% Requires \\usepackage{booktabs}, \\usepackage{threeparttable}",
        "\\begin{table}[t]",
        "\\centering",
        "\\small",
        "\\begin{threeparttable}",
        "\\caption{" + caption + "}",
        "\\label{" + label + "}",
        "\\begin{tabular}{lrrrr}",
        "\\toprule",
        "Term & Estimate & SE & $z$ & $p$ \\\\",
        "\\midrule",
    ]
    for _, r in rows.iterrows():
        lines.append(
            f"{tex_escape(r.term_label)} & {fmt_num(r.estimate, 4)} & {fmt_num(r.standard_error, 4)} & "
            f"{fmt_num(r.z_value, 2)} & {fmt_p_tex(r.p_value)}{sig_marker(r.p_value)} \\\\"
        )
    lines += [
        "\\bottomrule",
        "\\end{tabular}",
        "\\begin{tablenotes}",
        "\\footnotesize",
        _mixed_effects_diagnostic_note_item(),
        "\\end{tablenotes}",
        "\\end{threeparttable}",
        "\\end{table}",
        "",
    ]
    tex_path.write_text("\n".join(lines))


def make_table3() -> pd.DataFrame:
    fixed_effects = mixed_coef[~mixed_coef.term.isin(VARIANCE_TERMS)].copy()
    fixed_effects["term_label"] = fixed_effects["term"].map(TERM_LABELS).fillna(fixed_effects["term"])

    missing_main_terms = set(MAIN_TABLE_TERMS).difference(fixed_effects["term"])
    assert not missing_main_terms, f"MAIN_TABLE_TERMS references unknown terms: {missing_main_terms}"

    # Preserve the model's own term ordering rather than MAIN_TABLE_TERMS's
    # declaration order, so the compact table reads in the same order as
    # the full supplement table.
    main = fixed_effects[fixed_effects.term.isin(MAIN_TABLE_TERMS)].copy()
    main.to_csv(TABLE_DIR / "Table3_mixed_effects_summary.csv", index=False)

    variance_rows = mixed_coef[mixed_coef.term.isin(VARIANCE_TERMS)].copy()
    variance_rows.to_csv(TABLE_DIR / "Table3_mixed_effects_variance_components_supplement.csv", index=False)

    model_summary = (
        "(formula: \\texttt{" + tex_escape(mixed_diag["formula"]) + "}; "
        f"random-effects structure: {tex_escape(mixed_diag['random_effects_structure'])}; "
        f"$n$ = {mixed_diag['n_observations']} observations, "
        f"{mixed_diag['n_participants']} participants; converged: {mixed_diag['converged']})"
    )

    _render_mixed_effects_table(
        main,
        caption=(
            "Participant-level mixed-effects model of ROC-AUC, compact main-text subset "
            f"{model_summary}. Shows the regime, budget, budget $\\times$ regime, method, and "
            "dataset terms most directly relevant to interpretation. The complete 14-term "
            "fixed-effects table is in the supplement "
            "(\\texttt{Table3\\_mixed\\_effects\\_full\\_supplement.tex}); random-effect "
            "variance components are reported separately."
        ),
        label="tab:mixed_effects",
        tex_path=TABLE_DIR / "Table3_mixed_effects_summary.tex",
    )

    _render_mixed_effects_table(
        fixed_effects,
        caption=(
            f"Complete participant-level mixed-effects model of ROC-AUC {model_summary}: all "
            "14 fixed-effect and interaction terms. The compact main-text subset is Table~3 "
            "in the main text; random-effect variance components are reported separately "
            "(\\texttt{Table3\\_mixed\\_effects\\_variance\\_components\\_supplement.csv})."
        ),
        label="tab:mixed_effects_full",
        tex_path=TABLE_DIR / "Table3_mixed_effects_full_supplement.tex",
    )
    fixed_effects.to_csv(TABLE_DIR / "Table3_mixed_effects_full_supplement.csv", index=False)

    return main


# ==========================================================================
# Supplement table — all dataset-specific (supportive) contrasts
# ==========================================================================
def make_supplement_table_dataset_specific() -> pd.DataFrame:
    supportive = pairwise[pairwise.inference_role == "supportive"].copy()
    supportive["method_display"] = np.where(
        supportive.method_left == supportive.method_right,
        supportive.method_left,
        supportive.method_left + " vs " + supportive.method_right,
    )
    supportive["budget_or_regime"] = np.where(
        supportive.budget_per_class.notna(),
        supportive.budget_per_class.astype("Int64").astype(str) + " trials/class",
        supportive.regime + " regime (AUCC)",
    )
    cols = [
        "family",
        "scope_dataset",
        "contrast",
        "budget_or_regime",
        "method_display",
        "n_pairs",
        "mean_difference",
        "ci_lower",
        "ci_upper",
        "p_value",
        "p_holm",
        "rank_biserial",
    ]
    out = supportive[cols].sort_values(["family", "scope_dataset", "budget_or_regime", "method_display"]).reset_index(drop=True)
    out.to_csv(TABLE_DIR / "Supplement_Table_dataset_specific_contrasts.csv", index=False)

    lines = [
        "% Requires \\usepackage{booktabs}, \\usepackage{tabularx}, \\usepackage{threeparttable}",
        "\\begin{table}[t]",
        "\\centering",
        "\\tiny",
        "\\begin{threeparttable}",
        "\\caption{All dataset-specific (supportive, within-dataset) pairwise contrasts underlying "
        "the pooled confirmatory contrasts in Table~2, including Zhou2016 ($n=2$, descriptive/"
        "supportive only). $p_\\mathrm{holm}$ is Holm-adjusted within each contrast family across "
        "all rows shown for that family (confirmatory + supportive combined), matching "
        "pairwise\\_tests.csv.}",
        "\\label{tab:dataset_specific_contrasts}",
        "\\begin{tabularx}{\\textwidth}{@{} l l X r r r r r @{}}",
        "\\toprule",
        "Family & Dataset & Condition & $n$ & Mean $\\Delta$ [95\\% CI] & $p$ & $p_\\mathrm{holm}$ & $r_\\mathrm{rb}$ \\\\",
        "\\midrule",
    ]
    family_display = {
        "H2_regime_low_budget_dataset_supportive": "H2 (source+target vs. subject)",
        "H3_method_aucc_dataset_supportive": "H3 (riemann\\_lr vs. csp\\_lda)",
    }
    for _, r in out.iterrows():
        ci = f"{fmt_num(r.mean_difference)} [{fmt_num(r.ci_lower)}, {fmt_num(r.ci_upper)}]"
        lines.append(
            f"{family_display.get(r.family, tex_escape(r.family))} & {tex_escape(r.scope_dataset)} & "
            f"{tex_escape(r.method_display)}, {tex_escape(r.budget_or_regime)} & {int(r.n_pairs)} & {ci} & "
            f"{fmt_p_tex(r.p_value)} & {fmt_p_tex(r.p_holm)}{sig_marker(r.p_holm)} & {fmt_num(r.rank_biserial)} \\\\"
        )
    lines += [
        "\\bottomrule",
        "\\end{tabularx}",
        "\\begin{tablenotes}",
        "\\footnotesize",
        "\\item[*] Holm-adjusted $p < 0.05$. Zhou2016 rows use $n=2$ participants and are descriptive only.",
        "\\end{tablenotes}",
        "\\end{threeparttable}",
        "\\end{table}",
        "",
    ]
    (TABLE_DIR / "Supplement_Table_dataset_specific_contrasts.tex").write_text("\n".join(lines))
    return out


# ==========================================================================
# Supplement note — audit / provenance summary
# ==========================================================================
def make_supplement_audit_provenance_note() -> None:
    text = f"""# Supplement — Audit and provenance summary

Factual, non-interpretive summary of the confirmatory full-cohort run
underlying every figure and table in this artifact set. Full closure record:
`docs/full_run_acceptance.md`. Full decision record: `docs/DECISIONS.md`.

## Run identification

- Output directory: `results/bci-calibration-full-v1-3fb8efe7e617b0c1/`
- Experiment fingerprint: `{run_manifest.get("experiment_fingerprint", "n/a")}`
- Preprocessing fingerprint: `{run_manifest.get("preprocessing_fingerprint", "n/a")}`

## Cohort

- Nominal participants: 67 (Lee2019_MI 54, BNCI2014_001 9, Zhou2016 4)
- Structurally excluded: Zhou2016 subjects 2 and 4 (pre-outcome structural
  shortfalls in the publicly released recordings; see `docs/DECISIONS.md`)
- Final structurally validated N: 65 (Lee2019_MI {FLOW["Lee2019_MI"]}, BNCI2014_001 {FLOW["BNCI2014_001"]}, Zhou2016 {FLOW["Zhou2016"]})

## Run integrity

- Configured conditions: {result_audit["expected_conditions"]}
- Successful conditions: {result_audit["successful_conditions"]}
- Failed conditions: {result_audit["failed_conditions"]}
- Prediction rows: {result_audit["prediction_rows"]}
- Result-integrity audit status: `{result_audit["status"]}`
- Metrics independently recomputed from stored predictions and matched exactly: {result_audit["metric_conditions_recomputed"]}
- AUCC curve completeness: {int((aucc_subject["curve_complete"] == True).sum())}/{len(aucc_subject)} rows complete

## Aggregation

- Aggregation manifest schema version: {aggregation_manifest.get("schema_version", "n/a")}
- Aggregation input metrics checksum (SHA-256): `{aggregation_manifest.get("input_metrics_sha256", "n/a")}`

## LaTeX compiler availability at build time

No `pdflatex` (or other LaTeX compiler: `tectonic`, `latexmk`) was found on
`PATH` when this artifact set was generated (`which pdflatex` returned
nothing). The `.tex` tables were structurally reviewed by hand (balanced
environments, matching column counts between header and data rows, correct
`tabularx`/`threeparttable` nesting) but were **not** compiled by this
build. See `notes/PROVENANCE.md`, "LaTeX layout" section, for exactly what
changed and why.

This note is provenance/audit-only. It contains no performance interpretation.
"""
    (NOTES_DIR / "Supplement_Audit_Provenance.md").write_text(text)


# ==========================================================================
# Caption drafts (factual, not promotional)
# ==========================================================================
def make_caption_drafts() -> None:
    captions = {
        "Figure1_caption_draft.md": (
            "**Figure 1. Study design.** Conceptual schematic (no data). For each target "
            "participant, other participants in the same dataset form the source cohort "
            "(≤ 10 participants, ≤ 20 trials/class each). Earlier target sessions form "
            "the calibration pool; the chronologically latest target session is held out in "
            "full and untouched until final scoring. Calibration budgets of 0, 5, 10, 20, and "
            "40 labeled trials per class are drawn as nested subsets of the calibration pool. "
            "Three training regimes (population-only, subject-only, source+target pooled "
            "retraining) and three fixed decoders (log-variance + LDA, CSP + LDA, Riemannian "
            "tangent-space + logistic regression) are evaluated independently at every "
            "budget/regime/repeat combination on the untouched held-out session, producing "
            "audited, checksum-verified outputs."
        ),
        "Figure2_caption_draft.md": (
            "**Figure 2. Calibration trajectories: subject-only vs. pooled retraining.** "
            "ROC-AUC as a function of calibration budget (trials per class, log2(budget+1) "
            "axis) for Lee2019_MI (A-C) and BNCI2014_001 (D-F), one panel per decoder "
            "(log-variance + LDA: A, D; CSP + LDA: B, E; Riemannian TS + LR: C, F). Each panel "
            "overlays the two directly comparable regimes on a shared budget axis: "
            "subject-only (blue, budgets 5-40; undefined at budget 0) and pooled source+target "
            "retraining (orange, budgets 0-40). Lines show the participant-bootstrap mean; "
            "shaded ribbons show 95% bootstrap confidence intervals (2000 resamples). The "
            "pattern is dataset- and method-dependent, not universal. In Lee2019_MI, pooled "
            "retraining starts ahead of subject-only at the lowest calibrated budget (5 "
            "trials/class) for all three decoders, and subject-only converges with or crosses "
            "above it by budget 40 (A-C). In BNCI2014_001 the pattern differs by decoder: for "
            "log-variance + LDA and CSP + LDA (D, E), pooled retraining again starts ahead and "
            "subject-only catches up by higher budgets, as in Lee2019_MI; for Riemannian TS + "
            "LR (F), subject-only is already above pooled retraining at the lowest calibrated "
            "budget shown (5 trials/class: 0.731 vs. 0.678) and remains above it throughout. "
            "Zhou2016 is excluded from this figure (n=2 after structural exclusions; see "
            "Supplement Figure, Zhou2016 descriptive). Source data: "
            "`source_data/Figure2_main_calibration_curves.csv`, derived by filtering "
            "`curve_summary.csv` to dataset ∈ {Lee2019_MI, BNCI2014_001}, regime ∈ "
            "{subject, source_plus_target}, metric = roc_auc."
        ),
        "Figure3_caption_draft.md": (
            "**Figure 3. Confirmatory paired contrasts (H2).** Mean difference in ROC-AUC "
            "between pooled source+target retraining and subject-only calibration, at "
            "budgets 5 (A) and 10 (B) trials/class, for all three decoders. Diamonds show the "
            "pooled, participant-weighted confirmatory contrast across all three datasets "
            "(N=65 total; Lee2019_MI contributes 54 of 65, BNCI2014_001 contributes 9 of 65, "
            "and Zhou2016 contributes 2 of 65 participants to this pooled estimate); circles "
            "show the Lee2019_MI- and BNCI2014_001-specific supportive contrasts. All points "
            "show 95% bootstrap confidence intervals. Holm-adjusted p-values (within the H2 "
            "contrast family), labeled directly as e.g. 'Holm p < 0.001' or 'Holm p = 0.016' "
            "with no significance star (the adjusted p-value itself is the displayed signal), "
            "are annotated only for the pooled confirmatory diamonds, consistent with the "
            "confirmatory/supportive inferential-role distinction; dataset-specific supportive "
            "points are not individually p-annotated. Zhou2016's own dataset-specific contrast "
            "is not shown here (n=2, "
            "uninformative; see supplement table), though its 2 participants do contribute "
            "to the pooled diamond. "
            "Source data: `source_data/Figure3_paired_contrasts_budget5_10.csv`, the exact "
            "rows of `pairwise_tests.csv` plotted."
        ),
        "Figure4_caption_draft.md": (
            "**Figure 4. Participant heterogeneity.** ROC-AUC per participant and calibration "
            "budget for the Riemannian tangent-space + LR decoder, Lee2019_MI (A, B) and "
            "BNCI2014_001 (C, D), subject-only (A, C) and pooled source+target (B, D) "
            "regimes. Rows (participants) are ordered by each participant's mean pooled "
            "(source+target) ROC-AUC across budgets, with the same order held fixed across "
            "both regime panels of a dataset to ease visual comparison; this ordering is a "
            "display choice only and is not an inferential statistic. Source data: "
            "`source_data/Figure4_participant_heterogeneity.csv`."
        ),
        "Table1_caption_draft.md": (
            "**Table 1. Datasets and confirmatory cohort.** Nominal counts are the number of "
            "subject IDs each dataset publishes; final counts are participants that passed "
            "every pre-specified structural check before any model was fit (see "
            "`docs/DECISIONS.md`). All three datasets' structurally eligible participants "
            "contribute to the pooled confirmatory analyses (Table 2, Figure 3); Zhou2016 "
            "contributes only 2 participants (of 65 pooled total), so dataset-specific "
            "inference for Zhou2016 alone is descriptive only, not an independent "
            "confirmatory or supportive estimate."
        ),
        "Table2_caption_draft.md": (
            "**Table 2. Main confirmatory contrasts.** Panel A: H2, source+target pooled "
            "retraining minus subject-only calibration, ROC-AUC, budgets 5 and 10 "
            "trials/class, all three decoders. Panel B: H3, Riemannian TS + LR minus CSP + "
            "LDA, normalized log-AUCC, subject-only regime. Both panels pooled "
            "participant-weighted across all three datasets (N=65 total; Lee2019_MI "
            "contributes 54 of 65, BNCI2014_001 contributes 9 of 65, and Zhou2016 contributes "
            "2 of 65 participants). Holm-adjusted p-values are shown directly (no "
            "significance stars); the unadjusted raw p-value column is omitted from this "
            "table for width and is preserved in `Table2_confirmatory_contrasts.csv`. "
            "Dataset-specific contrasts underlying these pooled estimates, including "
            "Zhou2016's, are in the Supplement Table."
        ),
        "Table3_caption_draft.md": (
            "**Table 3. Mixed-effects model summary (main text).** Compact subset (8 of 14 "
            "fixed-effect terms) from the pre-specified participant-level mixed model of "
            "ROC-AUC (random intercept and slope by participant): the regime, "
            "log2(budget+1), their interaction, method main effects, and dataset fixed "
            "effects. The complete 14-term fixed-effects table is "
            "`Table3_mixed_effects_full_supplement`; random-effect variance components are "
            "reported separately (`Table3_mixed_effects_variance_components_supplement.csv`)."
        ),
        "Table3_full_supplement_caption_draft.md": (
            "**Supplement Table. Complete mixed-effects model.** All 14 fixed-effect and "
            "interaction terms from the same participant-level mixed model of ROC-AUC "
            "summarized in Table 3 (main text), including the method × regime and "
            "log2(budget+1) × method × regime interaction terms omitted from the compact "
            "main-text table for space. Random-effect variance components are reported "
            "separately (`Table3_mixed_effects_variance_components_supplement.csv`)."
        ),
        "Supplement_Figure_Zhou2016_caption_draft.md": (
            "**Supplement Figure. Zhou2016 calibration curves (descriptive only).** Same "
            "format as Figure 2, shown for Zhou2016 (n=2 after structural exclusion of "
            "subjects 2 and 4). With only two structurally eligible participants, this "
            "dataset cannot support an independent inferential claim; it is included for "
            "completeness and transparency only."
        ),
        "Supplement_Table_caption_draft.md": (
            "**Supplement Table. All dataset-specific contrasts.** Every within-dataset "
            "(supportive) H2 and H3 contrast, including Zhou2016 (n=2, descriptive only), "
            "underlying the pooled confirmatory contrasts in Table 2."
        ),
    }
    for filename, text in captions.items():
        (NOTES_DIR / filename).write_text(text + "\n")


# ==========================================================================
# Provenance note
# ==========================================================================
def make_provenance_note() -> None:
    text = f"""# PROVENANCE

All figures and tables in this artifact set are derived exclusively from the
already-audited outputs of the confirmatory full-cohort run at:

    {RESULTS_DIR.relative_to(REPO_ROOT)}

Generator script: `manuscript/artifacts/full_analysis_publication/build_artifacts.py`
(deterministic; reads the CSVs/JSONs below and writes figures/tables/source
data; performs no new inferential analysis, no re-fitting, and no
re-scoring).

## Input files used

- `curve_summary.csv` — participant-bootstrap calibration curves (Figures 2, Supplement Zhou2016 figure)
- `aucc_subject.csv` — participant-level fixed-horizon AUCC (curve-completeness check only in this build)
- `pairwise_tests.csv` — confirmatory + supportive paired contrasts (Figure 3, Tables 2 and Supplement)
- `mixed_effects_coefficients.csv` — mixed-effects model terms (Table 3)
- `mixed_effects_diagnostics.json` — model formula, convergence, warnings (Table 3 caption/footnote)
- `summary_subject.csv` — repeat-averaged participant-level outcomes (Figure 4)
- `participant_flow.csv` — attempted/succeeded/failed counts per dataset (Table 1, cross-checked by assertion)
- `result_audit.json` — integrity audit status and counts (Supplement audit note)
- `aggregation_manifest.json` — aggregation checksums (Supplement audit note)
- `run_manifest.json` — experiment/preprocessing fingerprints (Supplement audit note)

`metrics.csv` and `predictions.csv.gz` were **not** re-read or recomputed by
this script; they are the inputs the audit already verified metrics.csv/
aggregated tables against, and this build trusts the audited aggregates.

## Filtering / subsetting logic (no new statistics)

- **Figure 2**: `curve_summary.csv` filtered to `dataset in {{Lee2019_MI,
  BNCI2014_001}}`, `regime in {{subject, source_plus_target}}`,
  `metric == "roc_auc"`, laid out as a 2 (dataset) × 3 (method) grid, with
  the two regimes overlaid within each panel on the shared budget axis.
  Zhou2016 excluded per the pre-registered treatment of that dataset as
  descriptive/supportive only.
- **Figure 3**: `pairwise_tests.csv` filtered to
  `family in {{H2_regime_low_budget_confirmatory,
  H2_regime_low_budget_dataset_supportive}}`, `budget_per_class in {{5, 10}}`,
  `scope_dataset in {{ALL, Lee2019_MI, BNCI2014_001}}` (Zhou2016 excluded).
  p-value annotations are drawn only for `scope_dataset == "ALL"` rows
  (already-computed `p_holm` values; no new test or threshold).
- **Figure 4**: `summary_subject.csv` filtered to `method == "riemann_lr"`,
  `dataset in {{Lee2019_MI, BNCI2014_001}}`, `regime in {{subject,
  source_plus_target}}`, pivoted participant × budget.
- **Table 1**: static protocol facts (nominal N, sessions, channels, task)
  from the dataset registry / README; final validated N cross-checked by
  assertion against `participant_flow.csv`; exclusion detail from
  `docs/DECISIONS.md`.
- **Table 2**: `pairwise_tests.csv` filtered to
  `family == "H2_regime_low_budget_confirmatory"` (all rows) plus
  `family == "H3_method_aucc_confirmatory" and regime == "subject"`.
- **Table 3**: `mixed_effects_coefficients.csv` with the three random-effect
  variance-component rows (`Group Var`, `Group x log2_budget Cov`,
  `log2_budget Var`) moved to a separate supplement CSV
  (`Table3_mixed_effects_variance_components_supplement.csv`); the remaining
  14 fixed-effect and interaction terms are split into a compact main-text
  table (`Table3_mixed_effects_summary`, the 8 terms in `MAIN_TABLE_TERMS`:
  intercept, regime, log2(budget+1), their interaction, the two method main
  effects, and the two dataset fixed effects) and a complete supplement
  table with all 14 terms (`Table3_mixed_effects_full_supplement`). Row
  selection only; no coefficient, standard error, or p-value is altered
  between the two tables.
- **Supplement figure**: same construction as Figure 2, `dataset ==
  "Zhou2016"` only.
- **Supplement table**: `pairwise_tests.csv` filtered to
  `inference_role == "supportive"` (all dataset-specific H2 and H3 rows,
  including Zhou2016).

## Derived-for-display-only calculations

- `x = log2(budget_per_class + 1)` — a monotonic axis transform for legible
  spacing of 0/5/10/20/40; the underlying values plotted are the audited
  `mean`/`ci_lower`/`ci_upper` from `curve_summary.csv`, unchanged.
- Figure 4 participant row order: each dataset's participants are sorted by
  their own mean `source_plus_target` ROC-AUC across budgets (from
  `summary_subject.csv`), and that order is reused for the `subject`-regime
  panel of the same dataset. This is a display ordering only; it does not
  alter, select, or re-weight any value.
- Significance markers (`*`) in tables mark `p_holm < 0.05` (Table 3:
  uncorrected model `p < 0.05`, a single fitted model, not a
  multiple-comparison family) using the already-computed p-values; no new
  threshold, test, or correction is introduced. In Figure 3, p-value text
  annotations are drawn only next to the pooled confirmatory diamonds
  (`scope_dataset == "ALL"`); dataset-specific supportive points still show
  their confidence intervals but are not individually p-annotated, to keep
  the confirmatory/supportive distinction visually unambiguous. Figure 3's
  annotations read as plain text (e.g. "Holm p < 0.001", "Holm p = 0.016")
  with no significance star, since the adjusted p-value itself is already
  the displayed signal; this is a label-formatting change only, using the
  same `p_holm` values as before.
- Figure 2's title and caption were revised to state the pattern precisely
  rather than as a general "convergence" claim: Lee2019_MI shows a
  low-budget pooled advantage that converges/crosses over by budget 40 for
  all three decoders; BNCI2014_001 is method-dependent, with log-variance +
  LDA and CSP + LDA following the same pattern as Lee2019_MI but Riemannian
  TS + LR already favoring subject-only at the lowest calibrated budget
  shown (5 trials/class: 0.731 vs. 0.678, from `curve_summary.csv`). No
  plotted curve, CI, or panel changed; only the title text and caption
  wording changed.

## LaTeX layout (tables only; no data change)

Fixed real width/rendering problems found by compiling the previous version
of these tables with `pdflatex`: Table 1 (confirmatory-role column clipped,
~420pt overfull), Table 2 (~100pt overfull, rightmost effect-size column
clipped), the dataset-specific supplement table (~82pt overfull), and
Table 3's footnote rendering beside rather than below the table rows.

- **Table 1**: rebuilt with `tabularx`, `Confirmatory role` set as the `X`
  (wrapping) column; the `Task` column text shortened to "Left/right motor
  imagery" (was "Left- vs. right-hand motor imagery"). No row, count, or
  scientific content removed.
- **Table 2**: rebuilt with `tabularx`; the previously-combined "Condition"
  text column is now two explicit columns (`Method`, `Budget / regime`);
  the unadjusted raw `p` column is omitted from this rendering only (it
  remains a column in `Table2_confirmatory_contrasts.csv`, unchanged);
  `p_holm` and `rank_biserial` are both retained. Wrapped in
  `threeparttable` so the footnote renders below the table.
- **Supplement dataset-specific contrasts table**: rebuilt with
  `tabularx`, `Condition` set as the `X` column; wrapped in
  `threeparttable`. No row or value removed.
- **Table 3 (main and full supplement)**: both wrapped in `threeparttable`
  via the shared `_render_mixed_effects_table()` helper, replacing the
  previous vspace-plus-inline-footnotesize pattern that rendered beside the
  table. No coefficient, standard error, or p-value changed.

No `pdflatex` (or other LaTeX compiler) was available in the environment
that produced this build; see `notes/Supplement_Audit_Provenance.md` (or
the task's final report) for the explicit compiler-availability statement.
The fixes above follow the specific overfull/clipping measurements reported
from an independent `pdflatex` compilation and standard `tabularx`/
`threeparttable` usage, but were not compiled by this script itself.

## Consistency checks run by the generator

- Asserts `participant_flow.csv` attempted counts equal the expected
  structurally validated cohort (Lee2019_MI 54, BNCI2014_001 9, Zhou2016 2)
  before building Table 1.
- Asserts `result_audit.json["status"] == "ok"` before building anything.
- Asserts every declared `MAIN_TABLE_TERMS` entry actually exists in
  `mixed_effects_coefficients.csv` before building Table 3.
- Scans every generated `.tex` file for the literal string
  `textbackslash{{}}times` and fails the build if found. This string is what
  `tex_escape()` previously produced when a pre-written `$\\times$` LaTeX
  command was passed back through it (the backslash was escaped a second
  time, breaking compilation). The fix: interaction-term labels now store a
  plain Unicode "×" character, and `tex_escape()` is the single place that
  converts "×" to `$\\times$`, so no string is ever escaped twice.
"""
    (NOTES_DIR / "PROVENANCE.md").write_text(text)


# ==========================================================================
# Artifact index
# ==========================================================================
def make_artifact_index(built_files: list[Path]) -> None:
    def rel(p: Path) -> str:
        return str(p.relative_to(ARTIFACT_DIR))

    lines = [
        "# Artifact index — full-analysis publication set",
        "",
        "Every artifact below is derived exclusively from the audited outputs of",
        f"`{RESULTS_DIR.relative_to(REPO_ROOT)}`. See `notes/PROVENANCE.md` for exact",
        "filtering logic and `notes/Supplement_Audit_Provenance.md` for run integrity",
        "facts. Generated by `build_artifacts.py`; rerun it to regenerate this set",
        "deterministically from the same audited inputs.",
        "",
        "| Artifact | Contents | Intended use |",
        "|---|---|---|",
        "| `figures/Figure1_study_design.pdf` / `.png` | Conceptual study-design schematic (no data) | Main paper |",
        "| `figures/Figure2_main_calibration_curves.pdf` / `.png` | ROC-AUC calibration curves, 2 (dataset) x 3 (method) grid, subject-only vs. pooled overlaid per panel | Main paper |",
        "| `source_data/Figure2_main_calibration_curves.csv` | Exact rows of `curve_summary.csv` plotted in Figure 2 | Provenance only |",
        "| `figures/Figure3_paired_contrasts_budget5_10.pdf` / `.png` | H2 forest plot, budgets 5 & 10, pooled + dataset-specific, p-values on pooled diamonds only | Main paper |",
        "| `source_data/Figure3_paired_contrasts_budget5_10.csv` | Exact rows of `pairwise_tests.csv` plotted in Figure 3 | Provenance only |",
        "| `figures/Figure4_participant_heterogeneity.pdf` / `.png` | Participant × budget ROC-AUC heatmaps, riemann_lr | Main paper |",
        "| `source_data/Figure4_participant_heterogeneity.csv` | Pivoted `summary_subject.csv` rows plotted in Figure 4 | Provenance only |",
        "| `figures/Supplement_Figure_Zhou2016_descriptive.pdf` / `.png` | Zhou2016 calibration curves, labeled descriptive-only | Supplement |",
        "| `source_data/Supplement_Figure_Zhou2016_descriptive.csv` | Exact rows plotted in the Zhou2016 supplement figure | Provenance only |",
        "| `tables/Table1_datasets_and_cohort.tex` / `.csv` | Dataset/cohort/eligibility table | Main paper |",
        "| `tables/Table2_confirmatory_contrasts.tex` / `.csv` | Pooled H2 (budgets 5, 10) + H3 (subject) contrasts | Main paper |",
        "| `tables/Table3_mixed_effects_summary.tex` / `.csv` | Mixed-effects model, compact main-text subset (8 of 14 fixed-effect terms) | Main paper |",
        "| `tables/Table3_mixed_effects_full_supplement.tex` / `.csv` | Mixed-effects model, complete 14-term fixed-effects table | Supplement |",
        "| `tables/Table3_mixed_effects_variance_components_supplement.csv` | Random-effect variance components | Supplement |",
        "| `tables/Supplement_Table_dataset_specific_contrasts.tex` / `.csv` | All dataset-specific H2/H3 contrasts, incl. Zhou2016 | Supplement |",
        "| `notes/Figure1_caption_draft.md` ... `Supplement_Table_caption_draft.md` | Factual caption drafts, one per figure/table | Main paper / Supplement (as captioned) |",
        "| `notes/Supplement_Audit_Provenance.md` | Run integrity summary (19,500/19,500 conditions, audit PASS, etc.) | Supplement |",
        "| `notes/PROVENANCE.md` | Full input-file list and filtering logic for every artifact | Provenance only |",
        "| `build_artifacts.py` | Deterministic generator script for this entire artifact set | Provenance only |",
        "",
        "## Slide-deck candidates",
        "",
        "Figures 2, 3, and 4 (PNG) are also suitable for slide decks as-is (300 dpi,",
        "readable panel labels). Figure 1 (schematic) is the recommended opening slide",
        "for describing the protocol without any data.",
        "",
        "## Files on disk at build time",
        "",
    ]
    for f in sorted(built_files):
        lines.append(f"- `{rel(f)}`")
    lines.append("")
    (ARTIFACT_DIR / "ARTIFACT_INDEX.md").write_text("\n".join(lines))


def main() -> None:
    built: list[Path] = []
    make_figure1()
    built += [FIG_DIR / "Figure1_study_design.pdf", FIG_DIR / "Figure1_study_design.png"]

    make_figure2()
    built += [
        FIG_DIR / "Figure2_main_calibration_curves.pdf",
        FIG_DIR / "Figure2_main_calibration_curves.png",
        SRC_DIR / "Figure2_main_calibration_curves.csv",
    ]

    make_figure3()
    built += [
        FIG_DIR / "Figure3_paired_contrasts_budget5_10.pdf",
        FIG_DIR / "Figure3_paired_contrasts_budget5_10.png",
        SRC_DIR / "Figure3_paired_contrasts_budget5_10.csv",
    ]

    make_figure4()
    built += [
        FIG_DIR / "Figure4_participant_heterogeneity.pdf",
        FIG_DIR / "Figure4_participant_heterogeneity.png",
        SRC_DIR / "Figure4_participant_heterogeneity.csv",
    ]

    make_supplement_figure_zhou2016()
    built += [
        FIG_DIR / "Supplement_Figure_Zhou2016_descriptive.pdf",
        FIG_DIR / "Supplement_Figure_Zhou2016_descriptive.png",
        SRC_DIR / "Supplement_Figure_Zhou2016_descriptive.csv",
    ]

    make_table1()
    built += [TABLE_DIR / "Table1_datasets_and_cohort.tex", TABLE_DIR / "Table1_datasets_and_cohort.csv"]

    make_table2()
    built += [TABLE_DIR / "Table2_confirmatory_contrasts.tex", TABLE_DIR / "Table2_confirmatory_contrasts.csv"]

    make_table3()
    built += [
        TABLE_DIR / "Table3_mixed_effects_summary.tex",
        TABLE_DIR / "Table3_mixed_effects_summary.csv",
        TABLE_DIR / "Table3_mixed_effects_full_supplement.tex",
        TABLE_DIR / "Table3_mixed_effects_full_supplement.csv",
        TABLE_DIR / "Table3_mixed_effects_variance_components_supplement.csv",
    ]

    make_supplement_table_dataset_specific()
    built += [
        TABLE_DIR / "Supplement_Table_dataset_specific_contrasts.tex",
        TABLE_DIR / "Supplement_Table_dataset_specific_contrasts.csv",
    ]

    make_supplement_audit_provenance_note()
    built += [NOTES_DIR / "Supplement_Audit_Provenance.md"]

    make_caption_drafts()
    built += list(NOTES_DIR.glob("*_caption_draft.md"))

    make_provenance_note()
    built += [NOTES_DIR / "PROVENANCE.md"]

    make_artifact_index(built)
    built += [ARTIFACT_DIR / "ARTIFACT_INDEX.md"]

    verify_tex_escaping()

    print(f"Built {len(built)} artifact files under {ARTIFACT_DIR}")


def verify_tex_escaping() -> None:
    """No LaTeX compiler is assumed available in this environment. As an
    explicit substitute for a compile check, scan every generated .tex file
    for the specific double-escaping failure mode this build previously
    exhibited (a pre-written "$\\times$" run back through tex_escape(),
    which escapes the backslash and yields the literal, non-compiling
    "$\\textbackslash{}times$"), and fail loudly if it recurs."""
    bad_pattern = "textbackslash{}times"
    offenders: list[str] = []
    for tex_path in sorted(TABLE_DIR.glob("*.tex")):
        text = tex_path.read_text()
        if bad_pattern in text:
            offenders.append(str(tex_path.relative_to(ARTIFACT_DIR)))
    assert not offenders, (
        f"Found '{bad_pattern}' in generated .tex files (a LaTeX-breaking "
        f"double-escape of an interaction ×): {offenders}"
    )
    print(f"Verified: '{bad_pattern}' does not occur in any generated .tex file.")


if __name__ == "__main__":
    main()
