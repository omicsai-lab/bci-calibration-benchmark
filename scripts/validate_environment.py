#!/usr/bin/env python3
"""Thin wrapper for ``bci-calibration environment``."""

from __future__ import annotations

import sys

from bci_calibration_benchmark.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["environment", *sys.argv[1:]]))
