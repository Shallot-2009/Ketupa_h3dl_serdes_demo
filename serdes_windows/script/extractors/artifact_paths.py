"""Canonical preprocessing folders and Excel names shared by every extractor."""

from __future__ import annotations

from pathlib import Path


NO_SIGNALS = 20


class NoMatchingSignals(ValueError):
    pass


def extractor_exit(main):
    try:
        return main()
    except NoMatchingSignals as error:
        print("[SKIPPED] {0}".format(error), flush=True)
        return NO_SIGNALS


def absent_marker(path):
    return Path(path).with_name(Path(path).name + ".no-signals.json")


def require_current_artifact(path):
    if absent_marker(path).is_file():
        raise ValueError("Latest preprocessing found no matching signals; do not reuse the old workbook: {0}".format(path))
    return path


SIGNAL_LABELS = {
    "lpddr": "LPDDR",
    "pcie": "PCIe",
    "pll_clk": "PLL_CLK",
    "serdes": "SerDes",
}


def signal_label(signal):
    """Return the stable filename label for one signal family."""
    key = str(signal).strip().casefold().replace("-", "_")
    try:
        return SIGNAL_LABELS[key]
    except KeyError as exc:
        raise ValueError("Unsupported preprocessing signal: {0}".format(signal)) from exc


def artifact_name(design_path, report_kind, signal):
    """Return ``NetListReport_<design>_<signal>.xlsx`` or Placement equivalent."""
    kind = str(report_kind).strip().casefold()
    if kind == "netlist":
        prefix = "NetListReport"
    elif kind in {"component", "placement"}:
        prefix = "Placement"
    else:
        raise ValueError("Unsupported report kind: {0}".format(report_kind))
    return "{0}_{1}_{2}.xlsx".format(
        prefix,
        Path(design_path).stem,
        signal_label(signal),
    )


def artifact_path(side_root, design_path, report_kind, signal):
    """Return an Excel path below ``PCB|PKG/netlist|placement``."""
    kind = str(report_kind).strip().casefold()
    directory_name = "netlist" if kind == "netlist" else "placement"
    directory = Path(side_root).resolve() / directory_name
    directory.mkdir(parents=True, exist_ok=True)
    return (directory / artifact_name(design_path, report_kind, signal)).resolve()


__all__ = ["SIGNAL_LABELS", "artifact_name", "artifact_path", "signal_label"]
