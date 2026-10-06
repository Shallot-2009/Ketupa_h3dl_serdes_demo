"""Load, inherit, validate, and fingerprint deterministic adapter profiles."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .models import AdapterError


def _merge(parent: Any, child: Any) -> Any:
    if isinstance(parent, dict) and isinstance(child, dict):
        result = dict(parent)
        for key, value in child.items():
            result[key] = _merge(result[key], value) if key in result else value
        return result
    if isinstance(parent, list) and isinstance(child, list):
        result = list(parent)
        for value in child:
            if value not in result:
                result.append(value)
        return result
    return child


def _profile_path(reference: str | Path, profile_dir: Path) -> Path:
    requested = Path(reference)
    if requested.is_file():
        return requested.resolve()
    if requested.suffix.lower() != ".json":
        requested = requested.with_suffix(".json")
    candidate = profile_dir / requested
    if candidate.is_file():
        return candidate.resolve()
    raise AdapterError(f"Profile not found: {reference}")


def _load(path: Path, profile_dir: Path, chain: tuple[Path, ...]) -> dict[str, Any]:
    if path in chain:
        joined = " -> ".join(str(item) for item in (*chain, path))
        raise AdapterError(f"Profile inheritance cycle: {joined}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AdapterError(f"Cannot read profile {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AdapterError(f"Profile root must be an object: {path}")
    parent_ref = payload.pop("extends", None)
    if not parent_ref:
        return payload
    parent_path = _profile_path(parent_ref, profile_dir)
    merged = _merge(_load(parent_path, profile_dir, (*chain, path)), payload)
    if "builtin" not in payload:
        merged["builtin"] = False
    return merged


def validate_profile(profile: dict[str, Any]) -> None:
    required = ("schema_version", "id", "version", "columns", "family_rules")
    missing = [key for key in required if key not in profile]
    if missing:
        raise AdapterError("Profile is missing: " + ", ".join(missing))
    if profile["schema_version"] != 1:
        raise AdapterError("Only profile schema_version=1 is supported")
    if not str(profile.get("id", "")).strip() or not str(profile.get("version", "")).strip():
        raise AdapterError("Profile id and version must be non-empty")
    if not isinstance(profile["columns"], dict):
        raise AdapterError("Profile columns must be an object")
    for field, aliases in profile["columns"].items():
        if not isinstance(aliases, list) or not all(isinstance(x, str) and x for x in aliases):
            raise AdapterError(f"Column aliases for {field!r} must be non-empty strings")
    allowed_families = {"lpddr", "pcie", "serdes", "pll_clk"}
    extra = set(profile["family_rules"]) - allowed_families
    if extra:
        raise AdapterError("Unknown signal families: " + ", ".join(sorted(extra)))
    contracts = profile.get("network_contracts", {})
    if not isinstance(contracts, dict):
        raise AdapterError("network_contracts must be an object")
    for family, topologies in contracts.items():
        if family not in allowed_families:
            raise AdapterError(f"Unknown network-contract family: {family}")
        if not isinstance(topologies, dict):
            raise AdapterError(f"Network contracts for {family} must be an object")
        for topology, contract in topologies.items():
            if topology not in {"pcb", "pkg"}:
                raise AdapterError(f"Unknown network-contract topology: {family}-{topology}")
            if not isinstance(contract, dict):
                raise AdapterError(f"Network contract {family}-{topology} must be an object")
            if contract.get("unmatched_policy", "reject") not in {"reject", "skip"}:
                raise AdapterError(f"Invalid unmatched_policy in {family}-{topology}")
            recognizer = contract.get("recognizer")
            if recognizer not in {None, "industry"}:
                raise AdapterError(
                    f"Invalid recognizer in {family}-{topology}: {recognizer!r}"
                )
            for index, rule in enumerate(contract.get("rules", []), start=1):
                if not isinstance(rule, dict) or not rule.get("pattern"):
                    raise AdapterError(f"Rule {index} in {family}-{topology} needs a pattern")
                if len(str(rule["pattern"])) > 512:
                    raise AdapterError(f"Rule {index} in {family}-{topology} is too long")
                try:
                    re.compile(rule["pattern"])
                except re.error as exc:
                    raise AdapterError(
                        f"Invalid regex in {family}-{topology} rule {index}: {exc}"
                    ) from exc
                emit = rule.get("emit", rule)
                if rule.get("action", "include") not in {"include", "ignore"}:
                    raise AdapterError(
                        f"Rule {index} in {family}-{topology} has an invalid action"
                    )
                if rule.get("action", "include") == "include" and not emit.get("logical_id"):
                    raise AdapterError(
                        f"Rule {index} in {family}-{topology} needs emit.logical_id"
                    )
            for index, mapping in enumerate(contract.get("mappings", []), start=1):
                emit = mapping.get("emit", mapping) if isinstance(mapping, dict) else {}
                if not isinstance(mapping, dict) or not mapping.get("net") or not emit.get("logical_id"):
                    raise AdapterError(
                        f"Mapping {index} in {family}-{topology} needs net and logical_id"
                    )
    for index, rule in enumerate(profile.get("endpoint_rules", []), start=1):
        if not isinstance(rule, dict) or rule.get("target") not in {"a", "b"}:
            raise AdapterError(f"Endpoint rule {index} must target a or b")
        try:
            re.compile(str(rule["refdes_pattern"]))
        except (KeyError, re.error) as exc:
            raise AdapterError(f"Invalid endpoint rule {index}: {exc}") from exc
    for index, rule in enumerate(profile.get("endpoint_order_rules", []), start=1):
        if not isinstance(rule, dict) or not isinstance(rule.get("rank"), int):
            raise AdapterError(f"Endpoint order rule {index} needs an integer rank")
        try:
            re.compile(str(rule["refdes_pattern"]))
        except (KeyError, re.error) as exc:
            raise AdapterError(f"Invalid endpoint order rule {index}: {exc}") from exc


def load_profile(reference: str | Path, profile_dir: Path) -> tuple[dict[str, Any], str]:
    path = _profile_path(reference, profile_dir)
    profile = _load(path, profile_dir, ())
    validate_profile(profile)
    canonical = json.dumps(profile, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return profile, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def runtime_approved(profile: dict[str, Any]) -> bool:
    """Built-ins are trusted; customer/LLM profiles require explicit approval."""
    if profile.get("builtin") is True:
        return True
    approval = profile.get("approval", {})
    return (
        isinstance(approval, dict)
        and approval.get("status") == "approved"
        and bool(str(approval.get("approved_by", "")).strip())
    )


__all__ = ["load_profile", "runtime_approved", "validate_profile"]
