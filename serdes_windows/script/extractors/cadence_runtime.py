"""Resolve the installed Cadence export utility without binding to one workstation."""

from __future__ import annotations

import os
import re
from pathlib import Path
import shutil


HERE = Path(__file__).resolve().parent
SETTINGS_FILE = HERE / "cds_env"
ENVIRONMENT_KEYS = (
    "CADENCE_TOOLS_BIN",
    "CADENCE",
    "CDSROOT",
    "CDS_HOME",
    "SPB_HOME",
)


def _settings():
    values = {}
    if not SETTINGS_FILE.is_file():
        return values
    for raw_line in SETTINGS_FILE.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", ";")) or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip().upper()] = value.strip().strip('"')
    return values


def _paths(value):
    text = os.path.expandvars(str(value).strip().strip('"'))
    if not text:
        return ()
    path = Path(text).expanduser()
    if path.name.casefold() == "report.exe":
        return (path,)
    return (
        path / "report.exe",
        path / "bin" / "report.exe",
        path / "tools" / "bin" / "report.exe",
    )


def _adjacent_spb_installs(value):
    """Find other installed SPB releases next to a configured Cadence root."""
    text = os.path.expandvars(str(value).strip().strip('"'))
    if not text:
        return ()
    anchor = Path(text).expanduser()
    parent = anchor.parent if anchor.name.casefold().startswith("spb") else anchor
    if not parent.is_dir():
        return ()
    return tuple(
        path for path in parent.iterdir()
        if path.is_dir() and path.name.casefold().startswith("spb")
    )


def cadence_export_candidates():
    configured = _settings()
    values = []
    for name in ENVIRONMENT_KEYS:
        value = os.environ.get(name, "").strip() or configured.get(name, "").strip()
        if value:
            values.append(value)
    located = shutil.which("report.exe")
    if located:
        values.append(located)
    for name in ("CDSROOT", "CADENCE", "CDS_HOME", "SPB_HOME"):
        value = os.environ.get(name, "").strip() or configured.get(name, "").strip()
        values.extend(str(path) for path in _adjacent_spb_installs(value))

    unique = []
    seen = set()
    for value in values:
        for candidate in (p for item in value.split(os.pathsep) for p in _paths(item)):
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            key = os.path.normcase(str(resolved))
            if key not in seen:
                seen.add(key)
                unique.append(resolved)
    return tuple(unique)


def resolve_cadence_export_command(design=None):
    candidates = cadence_export_candidates()
    required = cadence_design_version(design) if design is not None else None
    compatible = [
        (path, cadence_tool_version(path))
        for path in candidates
        if path.is_file()
    ]
    compatible = [
        (path, version)
        for path, version in compatible
        if required is None or version is None or version >= required
    ]
    configured = _settings().get("CADENCE_TOOLS_BIN", "").strip()
    environment = os.environ.get("CADENCE_TOOLS_BIN", "").strip()
    cdsroot = os.environ.get("CDSROOT", "").strip()
    inherited_default = bool(
        environment and cdsroot
        and Path(environment).resolve().is_relative_to(Path(cdsroot).resolve())
    )
    explicit = configured or ("" if inherited_default else environment)
    for item in explicit.split(os.pathsep):
        for candidate in _paths(item):
            selected = candidate.resolve()
            if any(path == selected for path, _version in compatible):
                return selected
    versioned = [(path, version) for path, version in compatible if version is not None]
    if versioned:
        return max(versioned, key=lambda item: item[1])[0]
    if compatible:
        return compatible[0][0]
    checked = "; ".join(str(path.parent) for path in candidates)
    raise FileNotFoundError(
        "Cadence tools were not found. Configure CADENCE_TOOLS_BIN, update "
        "script/extractors/cds_env, or add the Cadence tools/bin folder to PATH. "
        "Checked: {0}".format(checked or "no candidate folders")
    )


resolve_cadence_report = resolve_cadence_export_command


def cadence_design_version(path):
    selected = Path(path)
    if not selected.is_file(): return None
    with selected.open('rb') as stream: header = stream.read(4 * 1024 * 1024)
    match = re.search(rb'(?:allegro|cdnsip|cdsmcm)\s+([0-9]{2})\.([0-9]{1,2})\b', header, re.I)
    return tuple(map(int, match.groups())) if match else None

def cadence_tool_version(path):
    match = re.search(r'SPB[^0-9]*(\d{2})[._-](\d{1,2})', str(path), re.I)
    if match is None: match = re.search(r'SPB(\d{2})(\d{1,2})', str(path), re.I)
    return tuple(map(int, match.groups())) if match else None
