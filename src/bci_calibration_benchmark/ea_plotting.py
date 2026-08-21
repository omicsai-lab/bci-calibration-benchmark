"""Figure generation for the EA sensitivity.

Reuses ``plotting.make_calibration_figures`` and
``plotting.make_heterogeneity_figures`` unmodified. Does not call
``plotting.make_aucc_figures`` / ``plotting.make_all_figures``: the EA
sensitivity does not compute a method-level (Riemannian-vs-CSP) AUCC
contrast at all (Human Decision 4 -- EA inference is limited to the
regime-contrast H2-analog and descriptive trajectories), so there is no
``aucc_subject.csv`` for it to plot.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .config import ExperimentConfig
from .ea_runner import ALIGNMENT_MODE
from .plotting import make_calibration_figures, make_heterogeneity_figures
from .utils import atomic_write_text, json_default, sha256_file


def make_ea_figures(config: ExperimentConfig) -> Path:
    if config.alignment.mode != ALIGNMENT_MODE:
        raise ValueError(f"make_ea_figures requires alignment.mode == {ALIGNMENT_MODE!r}")
    output_dir = config.output_dir
    curve_path = output_dir / "curve_summary.csv"
    subject_path = output_dir / "summary_subject.csv"
    for path in (curve_path, subject_path):
        if not path.exists():
            raise FileNotFoundError(f"Run EA aggregation before plotting: missing {path}")
    curve = pd.read_csv(curve_path, dtype={"target_subject": str})
    subject = pd.read_csv(subject_path, dtype={"target_subject": str})
    figure_dir = output_dir / "figures"
    outputs: list[Path] = []
    outputs.extend(make_calibration_figures(curve, config, figure_dir))
    outputs.extend(make_heterogeneity_figures(subject, config, figure_dir))
    manifest = {
        "schema_version": 1,
        "classification": "post_confirmatory_exploratory_robustness",
        "experiment_fingerprint": config.experiment_fingerprint,
        "files": {str(path.relative_to(output_dir)): sha256_file(path) for path in outputs if path.exists()},
    }
    atomic_write_text(
        figure_dir / "figure_manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True, default=json_default) + "\n",
    )
    return figure_dir
