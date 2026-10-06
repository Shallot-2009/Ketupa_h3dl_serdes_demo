#!/usr/bin/env python3
"""OpenKetupa H3DL 112G/224G SerDes three-workflow distribution.

Author: hongbo.li
Contact: asenjoaupa@gmail.com, 3405802009@qq.com
"""

from pathlib import Path
from modules.product_controller import run_saved_configuration

PROJECT_ROOT = Path(__file__).resolve().parent

# Cases: select PCB, PKG, Merge, or any combination.
SELECTIONS = (
    ("serdes", "Merge"),
)

# Packaged inputs: every value resolves to the matching item under input/.
PCB_DIR = PROJECT_ROOT / "input/PCB"
PKG_DIR = PROJECT_ROOT / "input/PKG"
CONNECTOR_DIR = PROJECT_ROOT / "input/Connector"

INPUTS = {
    "default": {
        "pcb_layout":      PCB_DIR / "pcb/112G_224G_Serdes_PCB.brd",
        "pcb_stackup":     PCB_DIR / "stackup/112G_224G_Serdes_PCB_stackup.xml",
        "pcb_netlist":     PCB_DIR / "netlist/NetListReport_112G_224G_Serdes_PCB_SerDes.xlsx",
        "pcb_placement":   PCB_DIR / "placement/Placement_112G_224G_Serdes_PCB_SerDes.xlsx",
        "pkg_layout":      PKG_DIR / "pkg/112G_224G_Serdes_PKG.aedb",
        "pkg_stackup":     PKG_DIR / "stackup/112G_224G_Serdes_PKG_stackup.xml",
        "pkg_netlist":     PKG_DIR / "netlist/NetListReport_112G_224G_Serdes_PKG_SerDes.xlsx",
        "connector_3dcomp": CONNECTOR_DIR / "connector/Stripline_connector_1p0mm_110GHz.a3dcomp",
    },
}

# Run options
RUN_OPTIONS = {
    "prefix": "ALL",
    "corps": "\\",
    "mode": 0,                 # 0: build; 1: build and solve.
    "dry_run": False,          # Check only; do not start AEDT.
    "signoff": False,          # Create a Mode 1 signoff summary.
    "preprocess": False,        # Set True only after replacing a packaged input.
    "preprocess_entry": "sh",  # Linux preprocessing entry point.
    "parallel_groups": "",     # Empty: process all matching groups.
    "max_workers": None,       # None: use the safe automatic limit.
}

def main(argv=None):
    return run_saved_configuration(
        PROJECT_ROOT, SELECTIONS, INPUTS, RUN_OPTIONS, argv
    )

if __name__ == "__main__":
    raise SystemExit(main())
