#!/usr/bin/env python3
"""Inspect, normalize, profile, and validate company-specific SI input data."""

from __future__ import annotations

from pathlib import Path
import sys


sys.dont_write_bytecode = True
SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from data_adapter.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
