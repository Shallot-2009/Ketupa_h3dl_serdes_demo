"""Safe integration between proven legacy extractors and the universal adapter."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable, TypeVar

from .models import AdapterError, NoNormalizedRows
from .normalizer import normalize
from .profile import load_profile, runtime_approved


ROOT = Path(__file__).resolve().parent
PROFILE_DIR = ROOT / "profiles"
ACTIVE_FILE = ROOT / "active_profile.json"
_T = TypeVar("_T")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def active_settings() -> dict:
    try:
        value = json.loads(ACTIVE_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AdapterError(f"Cannot read adapter settings {ACTIVE_FILE}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise AdapterError("active_profile.json must use schema_version=1")
    if value.get("mode") not in {"legacy", "hybrid", "universal"}:
        raise AdapterError("Adapter mode must be legacy, hybrid, or universal")
    if value.get("llm_runtime") is not False:
        raise AdapterError("LLM runtime decisions are forbidden; llm_runtime must be false")
    return value


def _current_output(source: Path, output: Path, profile_digest: str) -> bool:
    sidecar = output.with_suffix(output.suffix + ".adapter.json")
    if not output.is_file() or not sidecar.is_file():
        return False
    try:
        report = json.loads(sidecar.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        report.get("source", {}).get("sha256") == _sha256(source)
        and report.get("profile", {}).get("sha256") == profile_digest
        and report.get("output", {}).get("sha256") == _sha256(output)
    )


def normalize_report(
    source: str | Path,
    output: str | Path,
    *,
    family: str,
    topology: str,
    groups: str = "auto",
    force: bool = False,
) -> Path:
    settings = active_settings()
    profile, digest = load_profile(str(settings.get("profile", "industry_default")), PROFILE_DIR)
    if settings.get("require_approved_customer_profile", True) and not runtime_approved(profile):
        raise AdapterError(
            f"Profile {profile.get('id')!r} is not approved for runtime use. "
            "Validate it, then run 05_DataAdapter.py approve-profile."
        )
    source_path = Path(source).expanduser().resolve()
    output_path = Path(output).expanduser().resolve()
    if not force and _current_output(source_path, output_path, digest):
        print(f"Unchanged universal adapter output: {output_path}")
        return output_path
    report = normalize(
        source_path,
        output_path,
        profile,
        digest,
        family=family,
        topology=topology,
        kind="netlist",
        force=force,
        groups=groups,
    )
    print(
        "Universal adapter: profile={0} family={1} topology={2} rows={3}".format(
            profile["id"], family, topology, report["statistics"]["rows"]
        )
    )
    return output_path


def convert_with_fallback(
    legacy: Callable[[], _T],
    source: str | Path,
    output: str | Path,
    *,
    family: str,
    topology: str,
    groups: str = "auto",
    force: bool = False,
) -> _T | Path:
    settings = active_settings()
    mode = settings["mode"]
    if mode == "universal":
        return normalize_report(
            source, output, family=family, topology=topology, groups=groups, force=force
        )
    try:
        return legacy()
    except (OSError, ValueError, RuntimeError) as legacy_error:
        if mode == "legacy":
            raise
        try:
            print(f"Legacy extractor did not accept this naming: {legacy_error}")
            print("Trying the approved universal profile...", flush=True)
            return normalize_report(
                source,
                output,
                family=family,
                topology=topology,
                groups=groups,
                force=force,
            )
        except (OSError, ValueError, RuntimeError) as adapter_error:
            # The legacy extractor owns the public no-signal protocol. When
            # both engines parsed the report and independently found no
            # matching family rows, preserve that typed outcome so stage 00
            # writes authenticated no-signal evidence (exit code 20). Any
            # other adapter failure remains release-blocking.
            if (
                isinstance(legacy_error, ValueError)
                and legacy_error.__class__.__name__ == "NoMatchingSignals"
                and isinstance(adapter_error, NoNormalizedRows)
            ):
                raise legacy_error from None
            raise AdapterError(
                "Both extraction paths rejected the input. "
                f"Legacy: {legacy_error}. Universal: {adapter_error}"
            ) from adapter_error


__all__ = ["active_settings", "convert_with_fallback", "normalize_report"]
