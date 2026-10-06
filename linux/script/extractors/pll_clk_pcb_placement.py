#!/usr/bin/env python3
"""Generate Merge PCB PLL/CLK endpoint placement from BRD or HTM/HTML."""

from __future__ import annotations

import os

from pathlib import Path

from pll_clk_common import placement_cli


def main() -> int:
    """Run this project's local PLL/CLK preprocessing entry."""
    return placement_cli(Path(os.environ["KETUPA_WORKFLOW_INPUT"]).resolve(), "pcb")


if __name__ == "__main__":
    raise SystemExit(main())
