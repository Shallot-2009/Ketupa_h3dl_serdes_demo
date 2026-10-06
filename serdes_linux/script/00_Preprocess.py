#!/usr/bin/env python3
"""Generate every required Netlist and Placement file for one workflow."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


sys.dont_write_bytecode = True
PRODUCT_ROOT = Path(__file__).resolve().parents[1]
if str(PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(PRODUCT_ROOT))

from lib.preprocess_cli import effective_arguments
from lib.preprocess_dispatch import execute_stage


def main(argv=None) -> int:
    argv = effective_arguments(argv, "00")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("signal", help="lpddr/ddr, pcie, pll_clk/pllclk/pll/clk, serdes, or all; missing signals are skipped")
    parser.add_argument(
        "method", nargs="?", choices=("pcb", "pkg", "all"), help="pcb, pkg, or all"
    )
    options, remaining = parser.parse_known_args(argv)
    return execute_stage(options.signal, options.method, "00", remaining)


if __name__ == "__main__":
    raise SystemExit(main())
