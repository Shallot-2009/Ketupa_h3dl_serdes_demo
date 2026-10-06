"""User-facing commands for deterministic and LLM-assisted data adaptation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile

from .classifier import analyze
from .llm import draft_profile
from .models import AdapterError
from .normalizer import normalize
from .profile import load_profile, runtime_approved, validate_profile


ROOT = Path(__file__).resolve().parent
PROFILE_DIR = ROOT / "profiles"
ACTIVE_FILE = ROOT / "active_profile.json"
FAMILIES = ("lpddr", "pcie", "serdes", "pll_clk")
TOPOLOGIES = ("pcb", "pkg")


def _write_json(payload: dict, destination: str = "") -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if destination:
        path = Path(destination).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
        os.close(handle)
        try:
            Path(temporary).write_text(text, encoding="utf-8")
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        print(path)
    else:
        print(text, end="")


def _profile_file(reference: str) -> Path:
    requested = Path(reference).expanduser()
    if requested.is_file():
        return requested.resolve()
    if requested.suffix.casefold() != ".json":
        requested = requested.with_suffix(".json")
    candidate = (PROFILE_DIR / requested).resolve()
    if not candidate.is_file() or candidate.parent != PROFILE_DIR.resolve():
        raise AdapterError(f"Profile not found: {reference}")
    return candidate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "OpenKetupa v1.0.1 company-neutral data adapter. "
            "Deterministic runtime; optional LLMs create review-only profiles."
        )
    )
    parser.add_argument("--version", action="version", version="ketupa-data-adapter 1.0.1")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="classify a source and explain evidence")
    inspect_parser.add_argument("source")
    inspect_parser.add_argument("--profile", default="industry_default")
    inspect_parser.add_argument("--sheet", default="")
    inspect_parser.add_argument("--report", default="")

    normalize_parser = subparsers.add_parser("normalize", help="write a validated canonical .xlsx")
    normalize_parser.add_argument("source")
    normalize_parser.add_argument("--output", "-o", required=True)
    normalize_parser.add_argument("--profile", default="industry_default")
    normalize_parser.add_argument("--sheet", default="")
    normalize_parser.add_argument("--kind", choices=("auto", "netlist", "placement"), default="auto")
    normalize_parser.add_argument("--family", choices=("auto", *FAMILIES), default="auto")
    normalize_parser.add_argument("--topology", choices=("auto", *TOPOLOGIES), default="auto")
    normalize_parser.add_argument("--groups", default="auto")
    normalize_parser.add_argument("--force", action="store_true")

    template_parser = subparsers.add_parser(
        "profile-template", help="generate a deterministic reviewable customer-profile skeleton"
    )
    template_parser.add_argument("source")
    template_parser.add_argument("--base", default="industry_default")
    template_parser.add_argument("--id", required=True)
    template_parser.add_argument("--family", choices=FAMILIES)
    template_parser.add_argument("--topology", choices=TOPOLOGIES)
    template_parser.add_argument("--output", "-o", required=True)

    llm_parser = subparsers.add_parser(
        "llm-profile", help="ask a local/online LLM for a draft profile; never activates it"
    )
    llm_parser.add_argument("source")
    llm_parser.add_argument("--id", required=True)
    llm_parser.add_argument("--family", choices=FAMILIES, required=True)
    llm_parser.add_argument("--topology", choices=TOPOLOGIES, required=True)
    llm_parser.add_argument("--provider", choices=("ollama", "openai-compatible"), required=True)
    llm_parser.add_argument("--model", required=True)
    llm_parser.add_argument("--endpoint", default="")
    llm_parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    llm_parser.add_argument("--sample-limit", type=int, default=120)
    llm_parser.add_argument("--timeout", type=float, default=90)
    llm_parser.add_argument("--output", "-o", required=True)

    validate_parser = subparsers.add_parser("validate-profile", help="validate and fingerprint a profile")
    validate_parser.add_argument("profile")

    approve_parser = subparsers.add_parser(
        "approve-profile", help="record human approval after validation and sample review"
    )
    approve_parser.add_argument("profile")
    approve_parser.add_argument("--reviewer", required=True)

    activate_parser = subparsers.add_parser("activate-profile", help="select a runtime profile and mode")
    activate_parser.add_argument("profile")
    activate_parser.add_argument("--mode", choices=("legacy", "hybrid", "universal"), default="hybrid")

    subparsers.add_parser("status", help="show active adapter mode and profile")
    subparsers.add_parser("self-test", help="run offline adapter regression checks")
    return parser


def _template(arguments: argparse.Namespace) -> int:
    profile, digest = load_profile(arguments.base, PROFILE_DIR)
    result = analyze(arguments.source, profile, digest)
    contracts = {
        family: {
            topology: {"recognizer": None, "unmatched_policy": "skip", "rules": [], "mappings": []}
            for topology in TOPOLOGIES
        }
        for family in FAMILIES
    }
    output = {
        "schema_version": 1,
        "id": arguments.id,
        "version": "1.0.0-draft",
        "extends": arguments.base,
        "builtin": False,
        "approval": {"status": "draft", "approved_by": ""},
        "columns": {
            field: [result.table.headers[index]]
            for field, index in sorted(result.table.mapping.items())
        },
        "family_rules": {},
        "network_contracts": contracts,
        "endpoint_rules": [],
        "component_role_rules": [],
        "review": {
            "required": True,
            "selected_family": arguments.family,
            "selected_topology": arguments.topology,
            "note": "Fill mutually exclusive rules and endpoint roles, normalize samples, then approve.",
            "analysis": result.as_dict(),
        },
    }
    _write_json(output, arguments.output)
    return 0


def _approve(arguments: argparse.Namespace) -> int:
    path = _profile_file(arguments.profile)
    if path.name in {"base.json", "industry_default.json", "legacy_v3l.json"}:
        raise AdapterError("Built-in profiles are release-controlled and cannot be approved in place")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise AdapterError("Profile root must be an object")
    validate_profile(payload)
    configured_contracts = [
        contract
        for topologies in payload.get("network_contracts", {}).values()
        if isinstance(topologies, dict)
        for contract in topologies.values()
        if isinstance(contract, dict) and (contract.get("rules") or contract.get("mappings"))
    ]
    if not configured_contracts:
        raise AdapterError("Profile has no reviewed network rules or explicit mappings")
    reviewer = arguments.reviewer.strip()
    if not reviewer:
        raise AdapterError("Reviewer must not be empty")
    payload["builtin"] = False
    payload["approval"] = {
        "status": "approved",
        "approved_by": reviewer,
        "approved_utc": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(payload, str(path))
    profile, digest = load_profile(path, PROFILE_DIR)
    _write_json({"status": "APPROVED", "profile": profile["id"], "sha256": digest})
    return 0


def _activate(arguments: argparse.Namespace) -> int:
    profile, digest = load_profile(arguments.profile, PROFILE_DIR)
    if arguments.mode != "legacy" and not runtime_approved(profile):
        raise AdapterError("Customer profiles must be approved before hybrid/universal activation")
    reference = str(_profile_file(arguments.profile)) if Path(arguments.profile).is_file() else arguments.profile
    settings = {
        "schema_version": 1,
        "mode": arguments.mode,
        "profile": reference,
        "require_approved_customer_profile": True,
        "llm_runtime": False,
    }
    _write_json(settings, str(ACTIVE_FILE))
    _write_json({"status": "ACTIVE", "mode": arguments.mode, "profile": profile["id"], "sha256": digest})
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command == "profile-template":
            return _template(arguments)
        if arguments.command == "llm-profile":
            base, _ = load_profile("industry_default", PROFILE_DIR)
            profile = draft_profile(
                source=arguments.source,
                base_profile=base,
                family=arguments.family,
                topology=arguments.topology,
                profile_id=arguments.id,
                provider=arguments.provider,
                model=arguments.model,
                endpoint=arguments.endpoint,
                api_key_env=arguments.api_key_env,
                sample_limit=arguments.sample_limit,
                timeout=arguments.timeout,
            )
            _write_json(profile, arguments.output)
            return 0
        if arguments.command == "validate-profile":
            profile, digest = load_profile(arguments.profile, PROFILE_DIR)
            _write_json(
                {
                    "status": "VALID",
                    "id": profile["id"],
                    "version": profile["version"],
                    "sha256": digest,
                    "runtime_approved": runtime_approved(profile),
                }
            )
            return 0
        if arguments.command == "approve-profile":
            return _approve(arguments)
        if arguments.command == "activate-profile":
            return _activate(arguments)
        if arguments.command == "status":
            settings = json.loads(ACTIVE_FILE.read_text(encoding="utf-8-sig"))
            profile, digest = load_profile(settings["profile"], PROFILE_DIR)
            _write_json(
                {
                    **settings,
                    "profile_id": profile["id"],
                    "profile_version": profile["version"],
                    "profile_sha256": digest,
                    "runtime_approved": runtime_approved(profile),
                }
            )
            return 0
        if arguments.command == "self-test":
            from .selftest import run

            return run()
        profile, digest = load_profile(arguments.profile, PROFILE_DIR)
        if arguments.command == "inspect":
            result = analyze(arguments.source, profile, digest, sheet=arguments.sheet)
            _write_json(result.as_dict(), arguments.report)
            return 0 if result.status == "AUTO" else 2
        report = normalize(
            arguments.source,
            arguments.output,
            profile,
            digest,
            family=arguments.family,
            topology=arguments.topology,
            kind=arguments.kind,
            sheet=arguments.sheet,
            force=arguments.force,
            groups=arguments.groups,
        )
        _write_json(report)
        return 0
    except (AdapterError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


__all__ = ["build_parser", "main"]
