#!/usr/bin/env python3
"""Generate Merge PKG PLL/CLK netlist Excel from MCM/SIP or HTM/HTML."""

from __future__ import annotations

import os

from pathlib import Path

from pll_clk_common import netlist_cli


def main() -> int:
    """Run this project's local PLL/CLK preprocessing entry."""
    return netlist_cli(Path(os.environ["KETUPA_WORKFLOW_INPUT"]).resolve(), "pkg")


if __name__ == "__main__":
    raise SystemExit(main())
