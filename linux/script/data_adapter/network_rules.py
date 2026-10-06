"""Map company-specific physical network names to stable logical identities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .models import AdapterError


@dataclass(frozen=True)
class NetworkIdentity:
    logical_id: str
    group: str
    signal_type: str
    partition: str
    polarity: str
    segment: str
    rule_id: str


class _StrictValues(dict[str, str]):
    def __missing__(self, key: str) -> str:
        raise KeyError(key)


def _pin_parts(pin: str) -> tuple[str, str]:
    refdes, separator, pin_name = str(pin).partition(".")
    return (refdes, pin_name) if separator else (str(pin), "")


def _render(template: Any, values: dict[str, str], rule_id: str, field: str) -> str:
    if template is None:
        return ""
    try:
        return str(template).format_map(_StrictValues(values)).strip()
    except KeyError as exc:
        raise AdapterError(
            f"Network rule {rule_id!r} field {field!r} references missing value {exc.args[0]!r}"
        ) from exc


def _contract(profile: dict, family: str, topology: str) -> dict:
    contract = (
        profile.get("network_contracts", {})
        .get(family, {})
        .get(topology)
    )
    if not isinstance(contract, dict):
        raise AdapterError(
            f"Profile {profile['id']!r} has no network contract for {family}-{topology}"
        )
    return contract


def map_network(
    *,
    name: str,
    endpoint_a: list[str],
    endpoint_b: list[str],
    source_signal_type: str,
    source_group: str,
    source_partition: str,
    family: str,
    topology: str,
    profile: dict,
) -> NetworkIdentity | None:
    """Return exactly one deterministic logical identity or reject ambiguity."""
    contract = _contract(profile, family, topology)
    if contract.get("recognizer") == "industry":
        from .industry_patterns import identify

        result = identify(
            name=name,
            family=family,
            topology=topology,
            endpoint_a=endpoint_a,
            source_signal_type=source_signal_type,
            source_group=source_group,
            source_partition=source_partition,
        )
        if result is None:
            if str(contract.get("unmatched_policy", "reject")).casefold() == "skip":
                return None
            raise AdapterError(
                f"Physical network {name!r} is not recognized by the conservative "
                f"industry {family}-{topology} rules; create or select a project profile"
            )
        return NetworkIdentity(**result)
    a_refdes, a_pin = _pin_parts(endpoint_a[0] if endpoint_a else "")
    b_refdes, b_pin = _pin_parts(endpoint_b[0] if endpoint_b else "")
    base_values = {
        "net_name": name,
        "source_group": source_group,
        "source_signal_type": source_signal_type,
        "source_partition": source_partition,
        "a_refdes": a_refdes,
        "a_pin": a_pin,
        "b_refdes": b_refdes,
        "b_pin": b_pin,
        "family": family,
        "topology": topology,
    }

    exact_matches = []
    for index, mapping in enumerate(contract.get("mappings", []), start=1):
        if str(mapping.get("net", "")).casefold() == name.casefold():
            exact_matches.append((mapping.get("id", f"mapping-{index}"), mapping, {}))

    rule_matches = []
    for index, rule in enumerate(contract.get("rules", []), start=1):
        rule_id = str(rule.get("id", f"rule-{index}"))
        method = re.fullmatch if rule.get("match", "full") == "full" else re.search
        match = method(rule["pattern"], name, re.IGNORECASE)
        if match:
            rule_matches.append((rule_id, rule, match.groupdict()))

    matches = exact_matches or rule_matches
    if len(matches) > 1:
        raise AdapterError(
            f"Physical network {name!r} matches multiple {family}-{topology} rules: "
            + ", ".join(str(item[0]) for item in matches)
        )
    if not matches:
        policy = str(contract.get("unmatched_policy", "reject")).casefold()
        if policy == "skip":
            return None
        raise AdapterError(
            f"Physical network {name!r} matches no {family}-{topology} rule in profile {profile['id']!r}"
        )

    rule_id, rule, captures = matches[0]
    action = str(rule.get("action", "include")).casefold()
    if action == "ignore":
        return None
    if action != "include":
        raise AdapterError(f"Network rule {rule_id!r} has unsupported action {action!r}")
    values = dict(base_values)
    values.update({key: str(value) for key, value in captures.items() if value is not None})
    values.update({str(key): str(value) for key, value in rule.get("values", {}).items()})
    emit = rule.get("emit", rule)

    polarity = _render(emit.get("polarity", ""), values, rule_id, "polarity").upper()
    polarity = polarity.removeprefix("D")
    signal_type = _render(
        emit.get("signal_type", source_signal_type), values, rule_id, "signal_type"
    )
    if not signal_type and polarity in {"P", "N"}:
        signal_type = "DIFF_" + polarity
    group = _render(emit.get("group", source_group), values, rule_id, "group")
    partition = _render(
        emit.get("partition", source_partition), values, rule_id, "partition"
    )
    logical_id = _render(emit.get("logical_id", ""), values, rule_id, "logical_id")
    segment = _render(emit.get("segment", ""), values, rule_id, "segment")
    missing = [
        field
        for field, value in (
            ("logical_id", logical_id),
            ("group", group),
            ("signal_type", signal_type),
            ("partition", partition),
        )
        if not value
    ]
    if missing:
        raise AdapterError(
            f"Network rule {rule_id!r} cannot derive: {', '.join(missing)} for {name!r}"
        )
    if signal_type.upper() in {"DIFF_P", "DIFF_N"}:
        inferred = signal_type.upper()[-1]
        if polarity and polarity != inferred:
            raise AdapterError(
                f"Network rule {rule_id!r} emits conflicting polarity and signal_type for {name!r}"
            )
        polarity = inferred
    return NetworkIdentity(
        logical_id=logical_id,
        group=group,
        signal_type=signal_type,
        partition=partition,
        polarity=polarity,
        segment=segment,
        rule_id=rule_id,
    )
