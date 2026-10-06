"""Optional LLM profile drafting through local or OpenAI-compatible HTTP APIs.

LLMs are advisory only: the returned profile remains a draft and cannot be
activated by the runtime until a human approves it with the CLI.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import AdapterError
from .profile import validate_profile
from .tabular import cell, read_tables


SYSTEM_PROMPT = """You draft deterministic OpenKetupa network-name profiles.
Return one JSON object only. Never infer missing electrical intent. The workflow
family and topology are authoritative. Create mutually exclusive full-match
regular expressions or explicit mappings. Preserve physical net names. Every
included rule must emit logical_id, group, signal_type, partition, polarity,
and segment. Mark the profile as a draft; never mark it approved."""


def _samples(source: str | Path, profile: dict, limit: int) -> dict[str, Any]:
    tables = read_tables(source, profile)
    table = max(tables, key=lambda item: (len(item.mapping), len(item.rows)))
    net_index = table.mapping.get("net_name")
    pin_index = table.mapping.get("all_pins")
    names = []
    pin_shapes = []
    for row in table.rows:
        name = cell(row, net_index)
        if name and name not in names:
            names.append(name)
        pins = cell(row, pin_index)
        if pins:
            shape = re.sub(r"[A-Za-z]+", "X", pins)
            shape = re.sub(r"[0-9]+", "N", shape)[:160]
            if shape not in pin_shapes:
                pin_shapes.append(shape)
        if len(names) >= limit:
            break
    return {
        "source_name": Path(source).name,
        "sheet": table.sheet,
        "headers": list(table.headers),
        "network_names": names,
        "redacted_pin_shapes": pin_shapes[:20],
    }


def _request_json(url: str, payload: dict, headers: dict[str, str], timeout: float) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=body, headers={"Content-Type": "application/json", **headers})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise AdapterError(f"LLM request failed: {exc}") from exc


def _json_object(text: str) -> dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.I | re.S)
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise AdapterError(f"LLM response is not one valid JSON object: {exc}") from exc
    if not isinstance(payload, dict):
        raise AdapterError("LLM response root must be a JSON object")
    return payload


def draft_profile(
    *,
    source: str | Path,
    base_profile: dict,
    family: str,
    topology: str,
    profile_id: str,
    provider: str,
    model: str,
    endpoint: str = "",
    api_key_env: str = "OPENAI_API_KEY",
    sample_limit: int = 120,
    timeout: float = 90,
) -> dict[str, Any]:
    evidence = _samples(source, base_profile, sample_limit)
    user_prompt = json.dumps(
        {
            "task": "Draft one OpenKetupa schema_version=1 customer profile",
            "profile_id": profile_id,
            "extends": "industry_default",
            "authoritative_family": family,
            "authoritative_topology": topology,
            "requirements": {
                "approval": {"status": "draft", "approved_by": ""},
                "contract_path": f"network_contracts.{family}.{topology}",
                "contract_recognizer": None,
                "unmatched_policy": "skip",
                "avoid_overlapping_rules": True,
                "include_endpoint_rules_when_refdes_semantics_are_clear": True,
            },
            "evidence": evidence,
        },
        ensure_ascii=False,
        indent=2,
    )
    provider_name = provider.strip().casefold()
    if provider_name == "ollama":
        url = (endpoint or "http://127.0.0.1:11434").rstrip("/") + "/api/chat"
        response = _request_json(
            url,
            {
                "model": model,
                "stream": False,
                "format": "json",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            },
            {},
            timeout,
        )
        content = str(response.get("message", {}).get("content", ""))
    elif provider_name == "openai-compatible":
        if not endpoint:
            raise AdapterError("--endpoint is required for openai-compatible provider")
        key = os.environ.get(api_key_env, "").strip()
        if not key:
            raise AdapterError(f"API key environment variable is empty: {api_key_env}")
        url = endpoint.rstrip("/")
        if not url.endswith("/chat/completions"):
            url += "/v1/chat/completions"
        response = _request_json(
            url,
            {
                "model": model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            },
            {"Authorization": "Bearer " + key},
            timeout,
        )
        choices = response.get("choices", [])
        content = str(choices[0].get("message", {}).get("content", "")) if choices else ""
    else:
        raise AdapterError("Provider must be ollama or openai-compatible")
    profile = _json_object(content)
    profile["schema_version"] = 1
    profile["id"] = profile_id
    profile.setdefault("version", "1.0.0-draft")
    profile["extends"] = "industry_default"
    profile["builtin"] = False
    profile["approval"] = {"status": "draft", "approved_by": ""}
    profile.setdefault("columns", {})
    profile.setdefault("family_rules", {})
    contract = profile.get("network_contracts", {}).get(family, {}).get(topology)
    if not isinstance(contract, dict) or not (
        contract.get("rules") or contract.get("mappings")
    ):
        raise AdapterError(
            f"LLM draft has no rules or mappings for {family}-{topology}"
        )
    contract["recognizer"] = None
    validate_profile(profile)
    return profile


__all__ = ["draft_profile"]
