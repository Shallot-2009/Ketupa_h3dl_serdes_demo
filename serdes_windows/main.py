"""Windows SerDes demo. Author: hongbo.li / Asenjo.HB.L.
Contact: asenjoaupa@gmail.com / 3405802009@qq.com.
See README.md and LICENSE before use. Configure inputs below; generated outputs
belong to this demo directory. Only licensed EDA installations may be used.
"""
from pathlib import Path
import sys

sys.dont_write_bytecode = True
PROJECT_ROOT = Path(__file__).resolve().parent
INPUT_ROOT = PROJECT_ROOT / "input"

from modules.product_controller import run_saved_configuration

SELECTIONS = (("serdes", "Merge"),)
INPUTS = {
    "default": {
        "pcb_layout": str(INPUT_ROOT / "PCB/pcb/112G_224G_Serdes_PCB.brd"),
        "pcb_stackup": str(INPUT_ROOT / "PCB/stackup/112G_224G_Serdes_PCB_stackup.xml"),
        "pcb_netlist": str(INPUT_ROOT / "PCB/netlist"),
        "pcb_placement": str(INPUT_ROOT / "PCB/placement"),
        "pkg_layout": str(INPUT_ROOT / "PKG/pkg/112G_224G_Serdes_PKG.sip"),
        "pkg_stackup": str(INPUT_ROOT / "PKG/stackup/112G_224G_Serdes_PKG_stackup.xml"),
        "pkg_netlist": str(INPUT_ROOT / "PKG/netlist"),
        "connector_3dcomp": str(
            INPUT_ROOT / "Connector/connector/Stripline_connector_1p0mm_110GHz.a3dcomp"
        ),
    }
}
RUN_OPTIONS = {
    "prefix": "ALL",
    "corps": "\\",
    "mode": 0,
    "dry_run": False,
    "signoff": False,
    "preprocess": False,
    "preprocess_entry": "py",
    "parallel_groups": "",
    "max_workers": None,
}


def main(argv=None):
    return run_saved_configuration(
        PROJECT_ROOT, SELECTIONS, INPUTS, RUN_OPTIONS, argv
    )


if __name__ == "__main__":
    raise SystemExit(main())
