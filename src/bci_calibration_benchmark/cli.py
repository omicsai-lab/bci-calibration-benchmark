"""Command-line interface for the complete benchmark workflow."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from .aggregate import aggregate_run
from .config import load_config
from .datasets import prepare_all_datasets, validate_all_datasets
from .environment import validate_environment
from .plotting import make_all_figures
from .runner import run_benchmark
from .synthetic import run_synthetic_smoke_test
from .validation import audit_result_integrity


def _config_parser(subparsers: argparse._SubParsersAction, name: str, help_text: str) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(name, help=help_text)
    parser.add_argument("--config", required=True, type=Path, help="YAML configuration path")
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bci-calibration",
        description="Leakage-resistant calibration benchmark for motor-imagery EEG BCIs",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    _config_parser(subparsers, "prepare", "Download and prepare configured public datasets")
    validate_data = _config_parser(
        subparsers,
        "validate-data",
        "Validate processed shards, manifests, and checksums",
    )
    validate_data.add_argument(
        "--skip-checksums",
        action="store_true",
        help="Skip large-file checksum verification (not recommended for final analysis)",
    )
    run = _config_parser(subparsers, "run", "Run all configured benchmark conditions")
    run.add_argument(
        "--repository-root",
        type=Path,
        default=Path("."),
        help="Repository root used for git/source provenance",
    )
    run.add_argument(
        "--assignment-source",
        type=Path,
        default=None,
        help=(
            "Primary run's output directory to reuse split/calibration/source assignments from. "
            "Required when the config's alignment.mode is not 'none'; ignored otherwise."
        ),
    )
    _config_parser(subparsers, "aggregate", "Aggregate repeats at participant level")
    _config_parser(subparsers, "figures", "Generate figures from aggregated tables")
    _config_parser(subparsers, "audit", "Audit result and protocol-assignment integrity")

    environment = subparsers.add_parser("environment", help="Validate Python and package versions")
    environment.add_argument("--config", type=Path)
    environment.add_argument("--repository-root", type=Path, default=Path("."))
    environment.add_argument(
        "--synthetic-only",
        action="store_true",
        help="Do not require MOABB; suitable only for software smoke tests",
    )

    smoke = subparsers.add_parser("smoke", help="Run deterministic synthetic end-to-end validation")
    smoke.add_argument("--workspace", type=Path, default=Path(".smoke-work"))
    smoke.add_argument("--no-clean", action="store_true")
    smoke.add_argument("--no-figures", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "environment":
        config = load_config(args.config) if args.config else None
        report = validate_environment(
            repository_root=args.repository_root,
            config=config,
            require_public_data_stack=not args.synthetic_only,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] == "ok" else 2

    if args.command == "smoke":
        report = run_synthetic_smoke_test(
            args.workspace,
            clean=not args.no_clean,
            make_figures=not args.no_figures,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    config = load_config(args.config)
    if args.command == "prepare":
        paths = prepare_all_datasets(config)
        for path in paths:
            print(path)
        return 0
    if args.command == "validate-data":
        frame = validate_all_datasets(config, verify_checksums=not args.skip_checksums)
        report_path = config.processed_dir / f"validation-{config.experiment_fingerprint}.csv"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(report_path, index=False)
        print(frame.to_string(index=False))
        print(f"\nSaved: {report_path}")
        return 0
    if args.command == "run":
        if config.alignment.mode != "none":
            if not args.assignment_source:
                raise SystemExit(
                    "--assignment-source is required when alignment.mode is not 'none'"
                )
            from .ea_runner import run_ea_benchmark

            print(
                run_ea_benchmark(
                    config,
                    assignment_source=args.assignment_source,
                    repository_root=args.repository_root,
                )
            )
        else:
            print(run_benchmark(config, repository_root=args.repository_root))
        return 0
    if args.command == "aggregate":
        if config.alignment.mode != "none":
            from .ea_aggregate import aggregate_ea_run

            print(aggregate_ea_run(config))
        else:
            print(aggregate_run(config))
        return 0
    if args.command == "figures":
        if config.alignment.mode != "none":
            from .ea_plotting import make_ea_figures

            print(make_ea_figures(config))
        else:
            print(make_all_figures(config))
        return 0
    if args.command == "audit":
        if config.alignment.mode != "none":
            from .ea_validation import audit_ea_result_integrity

            report = audit_ea_result_integrity(config)
        else:
            report = audit_result_integrity(config)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] == "ok" else 2
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
