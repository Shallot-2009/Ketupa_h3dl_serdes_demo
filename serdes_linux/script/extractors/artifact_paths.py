"""Canonical preprocessing folders and Excel names shared by every extractor."""

from __future__ import annotations

import hashlib
import hmac
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


def provenance_path(path):
    return Path(path).with_name(Path(path).name + ".provenance.json")


def _file_identity(path):
    path = Path(path).expanduser().resolve()
    if path.is_dir():
        if path.suffix.casefold() != ".aedb" or not (path / "edb.def").is_file():
            raise ValueError("Only complete .aedb directories are valid: {0}".format(path))
        digest = hashlib.sha256(b"KETUPA-AEDB-DIRECTORY-V1\0")
        total_bytes = 0
        for item in sorted(
            value
            for value in path.rglob("*")
            if value.is_file() and not value.name.casefold().endswith(".tmp")
        ):
            relative = item.relative_to(path).as_posix().encode("utf-8")
            digest.update(len(relative).to_bytes(4, "big"))
            digest.update(relative)
            with item.open("rb") as stream:
                for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                    digest.update(block)
            total_bytes += item.stat().st_size
        return {"bytes": total_bytes, "sha256": digest.hexdigest()}
    protected = path.with_name(path.name + ".kbx")
    if not path.is_file() and protected.is_file():
        try:
            from _ketupa_secure_runtime import read_source

            root = next(
                parent for parent in path.parents
                if (parent / "lib").is_dir()
                and (parent / "resource").is_dir()
            )
            payload = read_source(path.relative_to(root).as_posix()).encode(
                "utf-8"
            )
        except (ImportError, FileNotFoundError, StopIteration, UnicodeError) as exc:
            raise FileNotFoundError(path) from exc
        return {
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    path = path.resolve(strict=True)
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (
        after.st_size,
        after.st_mtime_ns,
    ):
        raise RuntimeError("Preprocessing input changed while hashing: {0}".format(path))
    return {
        "bytes": after.st_size,
        "sha256": digest.hexdigest(),
    }


def preprocess_provenance(layout, extractor):
    """Bind generated evidence to layout, extractor and Cadence executable."""
    layout = Path(layout).expanduser().resolve()
    result = {
        "schema_version": 1,
        "layout": _file_identity(layout),
        "extractor": _file_identity(extractor),
    }
    if layout.suffix.casefold() == ".aedb":
        result["layout_reader"] = "ANSYS_EDB"
    else:
        from script.extractors.cadence_runtime import (
            cadence_export_source,
            resolve_cadence_export_command,
        )

        report_code = "cmp" if "placement" in Path(extractor).stem else "net"
        source = cadence_export_source(layout, report_code)
        if source is None:
            result["cadence_source_kind"] = "cadence_spb"
            result["cadence_report"] = _file_identity(
                resolve_cadence_export_command(layout)
            )
        else:
            result["cadence_source_kind"] = source["kind"]
            result["cadence_report"] = _file_identity(source["path"])
    return result


def provenance_matches(record, layout, extractor):
    try:
        expected = preprocess_provenance(layout, extractor)
        actual = record.get("provenance")
        if not isinstance(actual, dict):
            return False
        # Older evidence omitted this label before the first report-cache hit.
        # The executable/report, layout and extractor hashes remain mandatory.
        actual = dict(actual)
        for value in (actual, expected):
            if "cadence_report" in value:
                value.setdefault("cadence_source_kind", "cadence_spb")
        # Compare the canonical serialization to avoid accepting partial data.
        import json

        return hmac.compare_digest(
            json.dumps(actual, sort_keys=True, separators=(",", ":")),
            json.dumps(expected, sort_keys=True, separators=(",", ":")),
        )
    except (OSError, RuntimeError, ValueError, TypeError):
        return False


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


__all__ = [
    "SIGNAL_LABELS",
    "absent_marker",
    "artifact_name",
    "artifact_path",
    "preprocess_provenance",
    "provenance_matches",
    "provenance_path",
    "signal_label",
]
