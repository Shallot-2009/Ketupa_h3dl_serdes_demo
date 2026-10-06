"""Resolve the installed Cadence export utility without binding to one workstation."""

from __future__ import annotations

import hashlib
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path
import shutil
import subprocess
import time


REPORT_CACHE_SCHEMA = 1
REPORT_CACHE_ENABLED = True
REPORT_TIMEOUT_SECONDS = 300.0
REPORT_ATTEMPTS = 3
REPORT_RETRY_SECONDS = 2.0
EXPORT_RECEIPT_SCHEMA = 1


def _report_looks_valid(path, report_code):
    """Reject a non-empty Cadence error page before it enters the cache."""
    selected = Path(path)
    if not selected.is_file() or selected.stat().st_size <= 0:
        return False
    with selected.open("rb") as stream:
        sample = stream.read(2 * 1024 * 1024).lower()
    required = {
        "net": (b"net name", b"net pins"),
        "cmp": (b"refdes", b"comp_package", b"sym_x", b"sym_y"),
    }.get(str(report_code).casefold())
    return required is None or all(token in sample for token in required)


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _cache_enabled():
    return REPORT_CACHE_ENABLED


def _cache_project_root():
    root = (
        os.environ.get("KETUPA_PROJECT_ROOT", "").strip()
        or os.environ.get("KETUPA_PCB_PROJECT_ROOT", "").strip()
    )
    if not root:
        root = str(Path(__file__).resolve().parents[2])
    return Path(root).expanduser().resolve()


def _cache_directory():
    from lib.core.cache_policy import persistent_cache_directory

    return persistent_cache_directory(
        _cache_project_root(),
        "cadence_reports",
        "KETUPA_CADENCE_REPORT_CACHE",
    )


def _cache_identity(report_code, design, executable):
    executable_stat = executable.stat()
    payload = {
        "schema": REPORT_CACHE_SCHEMA,
        "report_code": str(report_code),
        "source_sha256": _sha256(design),
        "executable": str(executable),
        "executable_size": executable_stat.st_size,
        "executable_mtime_ns": executable_stat.st_mtime_ns,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest(), payload


def _valid_cached_report(report_path, metadata_path, identity, report_code):
    if not report_path.is_file() or not metadata_path.is_file():
        return False
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        return (
            metadata.get("identity") == identity
            and metadata.get("report_size") == report_path.stat().st_size
            and metadata.get("report_size", 0) > 0
            and metadata.get("report_sha256") == _sha256(report_path)
            and _report_looks_valid(report_path, report_code)
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def _publish_cache(report_path, metadata_path, destination, identity, details):
    report_tmp = report_path.with_name(report_path.name + ".{0}.tmp".format(os.getpid()))
    metadata_tmp = metadata_path.with_name(metadata_path.name + ".{0}.tmp".format(os.getpid()))
    try:
        shutil.copyfile(destination, report_tmp)
        report_size = report_tmp.stat().st_size
        if report_size <= 0:
            raise RuntimeError("Cadence report cache rejected an empty report")
        metadata = {
            "schema_version": REPORT_CACHE_SCHEMA,
            "identity": identity,
            "source": details,
            "report_size": report_size,
            "report_sha256": _sha256(report_tmp),
        }
        metadata_tmp.write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        report_tmp.replace(report_path)
        metadata_tmp.replace(metadata_path)
    finally:
        report_tmp.unlink(missing_ok=True)
        metadata_tmp.unlink(missing_ok=True)


@contextmanager
def _exclusive_cache_lock(path):
    import fcntl

    stream = Path(path).open("a+b")
    try:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def _cadence_root(path):
    """Return an SPB installation root without resolving the ``report`` symlink."""
    selected = Path(os.path.abspath(str(path))).expanduser()
    if selected.name.casefold() == "report":
        selected = selected.parent
    if selected.name.casefold() == "bin" and selected.parent.name.casefold() in {
        "tools",
        "tools.lnx86",
    }:
        return selected.parent.parent
    if selected.name.casefold() in {"tools", "tools.lnx86"}:
        return selected.parent
    return selected


def _cadence_environment(executable):
    """Build a version-local child environment for one Cadence installation."""
    root = _cadence_root(executable)
    bin_path = Path(executable).parent
    native_bin = root / "tools.lnx86" / "bin"
    native_lib = root / "tools.lnx86" / "lib" / "64bit"
    entries = [str(native_bin), str(bin_path), str(root / "tools" / "bin")]
    environment = os.environ.copy()
    environment["PATH"] = os.pathsep.join(
        dict.fromkeys(
            [*entries, *filter(None, environment.get("PATH", "").split(os.pathsep))]
        )
    )
    if native_lib.is_dir():
        environment["LD_LIBRARY_PATH"] = os.pathsep.join(
            dict.fromkeys(
                [
                    str(native_lib),
                    *filter(
                        None,
                        environment.get("LD_LIBRARY_PATH", "").split(os.pathsep),
                    ),
                ]
            )
        )
    environment.update(
        CDSROOT=str(root),
        CDS_HOME=str(root),
        SPB_HOME=str(root),
        SPB_INST_DIR=str(root),
        CDS_USE_XVFB="1",
        CDS_AUTO_64BIT="ALL",
        CDS_PLAT="lnx86",
    )
    return environment


HERE = Path(__file__).resolve().parent
SETTINGS_FILE = HERE / "cds_env"
QUALIFIED_REPORT_DIRECTORY = HERE / "qualified_reports"
QUALIFIED_REPORT_MANIFEST = QUALIFIED_REPORT_DIRECTORY / "manifest.json"
ENVIRONMENT_KEYS = (
    "CADENCE_TOOLS_BIN",
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
    if path.name.casefold() == "report":
        return (path,)
    if path.name.casefold() == "bin":
        return (path / "report",)
    return tuple(
        directory / "report"
        for directory in (
            path,
            path / "bin",
            path / "tools" / "bin",
            path / "tools.lnx86" / "bin",
        )
    )


def _version_from_installation(path):
    text = _cadence_root(path).name
    match = re.search(r"SPB(?P<major>[0-9]{2})(?P<minor>[0-9]{1,2})", text, re.I)
    if match is None:
        match = re.search(
            r"SPB[^0-9]*(?P<major>[0-9]{2})[._-](?P<minor>[0-9]{1,2})",
            text,
            re.I,
        )
    if match is None:
        return None
    return int(match.group("major")), int(match.group("minor"))


def _format_version(value):
    return "unknown" if value is None else "{0}.{1}".format(*value)


_DESIGN_VERSION = re.compile(
    rb"(?:allegro|cdnsip|cdsmcm)\s+([0-9]{2})\.([0-9]{1,2})\b",
    re.I,
)


def cadence_design_version(path):
    """Read the Cadence writer version embedded in a BRD/MCM/SIP when present."""
    selected = Path(path).expanduser().resolve()
    if not selected.is_file():
        return None
    overlap = b""
    with selected.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            payload = overlap + block
            match = _DESIGN_VERSION.search(payload)
            if match is not None:
                return int(match.group(1)), int(match.group(2))
            overlap = payload[-128:]
    return None


def cadence_tool_version(path):
    """Return the SPB release encoded by an installation directory name."""
    return _version_from_installation(path)


def _qualified_report_entries():
    if not QUALIFIED_REPORT_MANIFEST.is_file():
        return ()
    try:
        payload = json.loads(
            QUALIFIED_REPORT_MANIFEST.read_text(encoding="utf-8-sig")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Qualified Cadence report manifest is unreadable: {0}".format(
                QUALIFIED_REPORT_MANIFEST
            )
        ) from exc
    if payload.get("schema_version") != 1 or not isinstance(
        payload.get("reports"), list
    ):
        raise RuntimeError(
            "Qualified Cadence report manifest has an unsupported schema: {0}".format(
                QUALIFIED_REPORT_MANIFEST
            )
        )
    return tuple(payload["reports"])


def qualified_report_snapshot(design_path, report_code):
    """Return an exact-hash qualified report snapshot, or ``None``.

    A snapshot is release evidence, not a synthetic Cadence export.  It is
    accepted only when both the source layout and the report payload match the
    immutable hashes in the manifest.
    """
    design = Path(design_path).expanduser().resolve()
    if not design.is_file():
        return None
    source_size = design.stat().st_size
    source_hash = _sha256(design)
    for entry in _qualified_report_entries():
        if not isinstance(entry, dict):
            raise RuntimeError("Qualified Cadence report entry must be an object")
        if (
            str(entry.get("report_code", "")).casefold()
            != str(report_code).casefold()
            or entry.get("source_bytes") != source_size
            or not hmac_compare(entry.get("source_sha256"), source_hash)
        ):
            continue
        relative = Path(str(entry.get("report", "")))
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError("Qualified Cadence report path is not confined")
        report = (QUALIFIED_REPORT_DIRECTORY / relative).resolve()
        if report.parent != QUALIFIED_REPORT_DIRECTORY.resolve():
            raise RuntimeError("Qualified Cadence report path is not confined")
        if not report.is_file():
            raise RuntimeError(
                "Qualified Cadence report is missing: {0}".format(report)
            )
        expected_size = entry.get("report_bytes")
        expected_hash = entry.get("report_sha256")
        if (
            report.stat().st_size != expected_size
            or not hmac_compare(expected_hash, _sha256(report))
        ):
            raise RuntimeError(
                "Qualified Cadence report failed integrity validation: {0}".format(
                    report
                )
            )
        return report
    return None


def hmac_compare(expected, actual):
    """Compare release hashes without accepting missing or partial values."""
    import hmac

    return isinstance(expected, str) and hmac.compare_digest(
        expected.casefold(), str(actual).casefold()
    )


def _export_receipt_path(design, report_code):
    identity = hashlib.sha256()
    identity.update(str(report_code).casefold().encode("ascii", errors="strict"))
    identity.update(b"\0")
    identity.update(_sha256(design).encode("ascii"))
    return _cache_directory() / "receipts" / (identity.hexdigest() + ".json")


def _record_export_source(design, report_code, kind, source):
    source = Path(source).expanduser().absolute()
    payload = {
        "schema_version": EXPORT_RECEIPT_SCHEMA,
        "report_code": str(report_code).casefold(),
        "design_sha256": _sha256(design),
        "source_kind": str(kind),
        "source_path": str(source),
        "source_bytes": source.stat().st_size,
        "source_sha256": _sha256(source),
    }
    receipt = _export_receipt_path(design, report_code)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt.with_name(receipt.name + ".{0}.tmp".format(os.getpid()))
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(receipt)
    finally:
        temporary.unlink(missing_ok=True)


def cadence_export_source(design_path, report_code):
    """Return the verified source used by the latest export, when recorded."""
    design = Path(design_path).expanduser().resolve()
    receipt = _export_receipt_path(design, report_code)
    if not receipt.is_file():
        return None
    try:
        payload = json.loads(receipt.read_text(encoding="utf-8-sig"))
        source = Path(payload["source_path"]).expanduser().absolute()
        valid = (
            payload.get("schema_version") == EXPORT_RECEIPT_SCHEMA
            and payload.get("report_code") == str(report_code).casefold()
            and hmac_compare(payload.get("design_sha256"), _sha256(design))
            and source.is_file()
            and payload.get("source_bytes") == source.stat().st_size
            and hmac_compare(payload.get("source_sha256"), _sha256(source))
        )
    except (KeyError, OSError, UnicodeError, ValueError, json.JSONDecodeError):
        valid = False
    if not valid:
        return None
    return {
        "kind": payload["source_kind"],
        "path": source,
    }


def _configured_values():
    configured = _settings()
    values = []
    for name in ENVIRONMENT_KEYS:
        # cds_env is the product-owned source of truth. An inherited process
        # value is retained only as a lower-priority fallback for portability.
        for value in (
            configured.get(name, "").strip(),
            os.environ.get(name, "").strip(),
        ):
            if value:
                values.extend(
                    token.strip()
                    for token in value.split(os.pathsep)
                    if token.strip()
                )
    return list(dict.fromkeys(values))


def _discovered_installations(configured_values):
    roots = []
    for value in configured_values:
        paths = _paths(value)
        if paths:
            roots.append(_cadence_root(paths[0]))
    for name in ("CDSROOT", "SPB_HOME", "SPB_INST_DIR"):
        value = os.environ.get(name, "").strip()
        if value:
            roots.append(_cadence_root(value))
    containers = {root.parent for root in roots if root.parent.is_dir()}
    installations = set(roots)
    for container in containers:
        for pattern in ("SPB*", "spb*"):
            installations.update(path for path in container.glob(pattern) if path.is_dir())
    return sorted(
        installations,
        key=lambda path: (_version_from_installation(path) or (-1, -1), str(path)),
        reverse=True,
    )


def cadence_export_candidates(design_path=None):
    configured_values = _configured_values()
    values = list(configured_values)
    values.extend(_discovered_installations(configured_values))
    located = shutil.which("report")
    if located:
        values.append(located)
    unique = []
    seen = set()
    for value in values:
        for candidate in _paths(value):
            try:
                # Cadence dispatches by argv[0]: report is a symlink to
                # allegro_batch.  Keep the public name instead of resolving
                # the symlink and accidentally selecting the wrong tool.
                resolved = Path(os.path.abspath(str(candidate)))
            except OSError:
                continue
            key = os.path.normcase(str(resolved))
            if key not in seen:
                seen.add(key)
                unique.append(resolved)
    if design_path is not None:
        writer = cadence_design_version(design_path)
        if writer is not None:
            indexed = list(enumerate(unique))

            def compatibility(item):
                index, candidate = item
                version = _version_from_installation(candidate)
                if version is None:
                    return 2, (999, 999), index
                if version >= writer:
                    return 0, (version[0] - writer[0], version[1] - writer[1]), index
                return 1, (-version[0], -version[1]), index

            unique = [candidate for _, candidate in sorted(indexed, key=compatibility)]
    return tuple(unique)


def resolve_cadence_export_command(design_path=None):
    candidates = cadence_export_candidates(design_path)
    executable = next(
        (
            path
            for path in candidates
            if path.is_file() and os.access(path, os.X_OK)
        ),
        None,
    )
    if executable is not None:
        return executable
    checked = "; ".join(str(path.parent) for path in candidates)
    raise FileNotFoundError(
        "Cadence tools were not found. Set CADENCE_TOOLS_BIN in "
        "script/extractors/cds_env or the process environment, or add the "
        "Cadence tools/bin folder to PATH. "
        "Checked: {0}".format(checked or "no candidate folders")
    )


def _positive_timeout():
    return REPORT_TIMEOUT_SECONDS


def _retry_policy():
    return REPORT_ATTEMPTS, REPORT_RETRY_SECONDS


def _retryable_export_failure(completed, destination, report_code):
    output = str(completed.stdout or "").casefold()
    deterministic_tokens = (
        "failed to open the drawing",
        "error reading extract file",
        "database is newer",
        "unsupported database",
    )
    if any(token in output for token in deterministic_tokens):
        return False
    license_tokens = (
        "lmf-10015",
        "cannot connect to license server",
        "license checking failed",
        "license server system does not support",
        "all licenses are in use",
        "connection reset",
        "resource temporarily unavailable",
        "database is locked",
    )
    return (
        any(token in output for token in license_tokens)
        or completed.returncode != 0
        or not _report_looks_valid(destination, report_code)
    )


@contextmanager
def _exclusive_cadence_process(executable):
    """Serialize report processes per SPB installation.

    Allegro ``report`` uses shared Cadence session state and is less reliable
    when several preprocess jobs start it at the same instant. The lock is
    advisory, process-safe, and released automatically after crashes.
    """
    identity = hashlib.sha256(
        str(_cadence_root(executable)).encode("utf-8")
    ).hexdigest()
    lock_root = _cache_directory() / "process-locks"
    lock_root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with _exclusive_cache_lock(lock_root / (identity + ".lock")):
        waited = time.monotonic() - started
        if waited >= 0.1:
            print(
                "Cadence report queue: waited {0:.2f}s for {1}".format(
                    waited, _cadence_root(executable)
                ),
                flush=True,
            )
        yield


def _execute_cadence_export(executable, report_code, design, destination):
    command = (
        str(executable),
        "-v",
        str(report_code),
        str(design),
        str(destination),
    )
    print(
        "Cadence report: executable={0}; input={1}; output={2}".format(
            executable, design, destination
        ),
        flush=True,
    )
    attempts, delay = _retry_policy()
    completed = None
    for attempt in range(1, attempts + 1):
        destination.unlink(missing_ok=True)
        try:
            with _exclusive_cadence_process(executable):
                completed = subprocess.run(
                    command,
                    cwd=str(destination.parent),
                    env=_cadence_environment(executable),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    errors="replace",
                    check=False,
                    timeout=_positive_timeout(),
                )
        except subprocess.TimeoutExpired as exc:
            output = exc.stdout or exc.stderr or "no diagnostic output"
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            destination.unlink(missing_ok=True)
            if attempt < attempts:
                print(
                    "Cadence report timed out; retry {0}/{1} in {2:.1f}s".format(
                        attempt + 1, attempts, delay
                    ),
                    flush=True,
                )
                time.sleep(delay)
                continue
            raise RuntimeError(
                "Cadence report timed out after {0:.1f}s. Command: {1}. Output: {2}".format(
                    _positive_timeout(), " ".join(command), str(output).strip()
                )
            ) from exc
        if (
            completed.returncode == 0
            and _report_looks_valid(destination, report_code)
        ):
            return destination
        if attempt < attempts and _retryable_export_failure(
            completed, destination, report_code
        ):
            print(
                "Cadence report transient failure; retry {0}/{1} in {2:.1f}s".format(
                    attempt + 1, attempts, delay
                ),
                flush=True,
            )
            time.sleep(delay)
            continue
        break
    if completed.returncode != 0 or not destination.is_file():
        destination.unlink(missing_ok=True)
        raise RuntimeError(
            "Cadence export failed ({0}). Command: {1}. Output: {2}".format(
                completed.returncode,
                " ".join(command),
                completed.stdout.strip() or "no diagnostic output",
            )
        )
    if destination.stat().st_size <= 0:
        destination.unlink(missing_ok=True)
        raise RuntimeError(
            "Cadence export created an empty report: {0}".format(destination)
        )
    destination.unlink(missing_ok=True)
    raise RuntimeError(
        "Cadence export returned success but the report contract is invalid. "
        "Expected headers for report code {0}. Command: {1}. Output: {2}".format(
            report_code,
            " ".join(command),
            completed.stdout.strip() or "no diagnostic output",
        )
    )


def _run_cached_candidate(executable, report_code, design, destination):
    """Try one SPB installation with its own environment and cache identity."""
    if not _cache_enabled():
        return _execute_cadence_export(executable, report_code, design, destination)

    cache_root = _cache_directory()
    cache_root.mkdir(parents=True, exist_ok=True)
    project_root = _cache_project_root()
    identity, details = _cache_identity(report_code, design, executable)
    cache = cache_root / (identity + ".htm")
    metadata = cache_root / (identity + ".json")
    started = time.monotonic()
    with _exclusive_cache_lock(cache_root / (identity + ".lock")):
        from lib.core.cache_policy import (
            legacy_cache_directory,
            preserve_invalid_cache_entry,
            record_cache_event,
        )

        if _valid_cached_report(cache, metadata, identity, report_code):
            record_cache_event(
                project_root,
                "cadence_reports",
                "hit",
                identity,
                cache,
                identity=details,
            )
            shutil.copyfile(cache, destination)
            print(
                "Cadence report cache hit: code={0}; waited={1:.2f}s; cache={2}".format(
                    report_code, time.monotonic() - started, cache
                ),
                flush=True,
            )
            return destination
        if cache.exists():
            preserve_invalid_cache_entry(
                project_root,
                "cadence_reports",
                cache,
                "report or metadata verification failed",
            )
        if metadata.exists():
            preserve_invalid_cache_entry(
                project_root,
                "cadence_reports",
                metadata,
                "report or metadata verification failed",
            )

        legacy_root = legacy_cache_directory(project_root, "cadence_reports")
        legacy_cache = legacy_root / cache.name
        legacy_metadata = legacy_root / metadata.name
        if _valid_cached_report(
            legacy_cache, legacy_metadata, identity, report_code
        ):
            _publish_cache(cache, metadata, legacy_cache, identity, details)
            record_cache_event(
                project_root,
                "cadence_reports",
                "migrate",
                identity,
                cache,
                identity=details,
            )
            shutil.copyfile(cache, destination)
            print(
                "Cadence report cache migrated: code={0}; cache={1}".format(
                    report_code, cache
                ),
                flush=True,
            )
            return destination

        _execute_cadence_export(executable, report_code, design, destination)
        _publish_cache(cache, metadata, destination, identity, details)
        record_cache_event(
            project_root,
            "cadence_reports",
            "publish",
            identity,
            cache,
            identity=details,
        )
        print("Cadence report cached: {0}".format(cache), flush=True)
        return destination


def _installed_export_commands(design):
    selected = []
    seen_roots = set()
    for path in cadence_export_candidates(design):
        if not path.is_file() or not os.access(path, os.X_OK):
            continue
        key = os.path.normcase(str(_cadence_root(path)))
        if key in seen_roots:
            continue
        seen_roots.add(key)
        selected.append(path)
    return tuple(selected)


def _export_failure_message(design, candidates, failures):
    writer = cadence_design_version(design)
    versions = []
    for executable in candidates:
        label = _format_version(cadence_tool_version(executable))
        if label not in versions:
            versions.append(label)
    installed = ", ".join(versions) or "none"
    lines = [
        "No installed Cadence SPB report tool could read the design.",
        "Design: {0}".format(design),
        "Detected design writer: {0}".format(_format_version(writer)),
        "Tried SPB versions: {0}".format(installed),
    ]
    if writer is not None and not any(
        (cadence_tool_version(path) or (-1, -1)) >= writer for path in candidates
    ):
        lines.append(
            "Install Cadence SPB {0} or a newer compatible release, or point "
            "CADENCE_TOOLS_BIN to its tools/bin directory.".format(
                _format_version(writer)
            )
        )
    else:
        lines.append(
            "Check that the selected SPB installation, platform libraries, and "
            "license are usable; CADENCE_TOOLS_BIN may point to another tools/bin."
        )
    for executable, error in failures:
        detail = " ".join(str(error).split())
        lines.append(
            "SPB {0} ({1}): {2}".format(
                _format_version(cadence_tool_version(executable)),
                executable,
                detail[-1600:],
            )
        )
    return "\n".join(lines)


def _restore_qualified_report(design, report_code, destination):
    snapshot = qualified_report_snapshot(design, report_code)
    if snapshot is None:
        return None
    shutil.copyfile(snapshot, destination)
    if not destination.is_file() or destination.stat().st_size <= 0:
        destination.unlink(missing_ok=True)
        raise RuntimeError(
            "Qualified Cadence report produced an empty destination: {0}".format(
                destination
            )
        )
    _record_export_source(
        design, report_code, "qualified_report_snapshot", snapshot
    )
    print(
        "Cadence qualified report snapshot: source layout SHA-256 matched; "
        "report={0}".format(snapshot),
        flush=True,
    )
    return destination


def run_cadence_export(report_code, design_path, report_path):
    """Export with the best installed SPB and fall back across local versions."""
    design = Path(design_path).expanduser().resolve()
    destination = Path(report_path).expanduser().resolve()
    if not design.is_file():
        raise FileNotFoundError("Cadence layout was not found: {0}".format(design))
    destination.parent.mkdir(parents=True, exist_ok=True)
    candidates = _installed_export_commands(design)
    if not candidates:
        restored = _restore_qualified_report(
            design, report_code, destination
        )
        if restored is not None:
            return restored
        resolve_cadence_export_command(design)
        raise AssertionError("unreachable")
    print(
        "Cadence compatibility: design={0}; installed={1}".format(
            _format_version(cadence_design_version(design)),
            ", ".join(
                "{0}:{1}".format(_format_version(cadence_tool_version(path)), path)
                for path in candidates
            ),
        ),
        flush=True,
    )
    failures = []
    for executable in candidates:
        try:
            result = _run_cached_candidate(
                executable, report_code, design, destination
            )
            _record_export_source(
                design, report_code, "cadence_spb", executable
            )
            return result
        except RuntimeError as error:
            destination.unlink(missing_ok=True)
            failures.append((executable, error))
            print(
                "Cadence SPB {0} could not export this design; trying the next "
                "installed release.".format(
                    _format_version(cadence_tool_version(executable))
                ),
                flush=True,
            )
    restored = _restore_qualified_report(design, report_code, destination)
    if restored is not None:
        return restored
    raise RuntimeError(_export_failure_message(design, candidates, failures))


resolve_cadence_report = resolve_cadence_export_command
