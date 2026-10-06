"""Evidence-based input classification with explicit ambiguity handling."""

from __future__ import annotations

import re
from pathlib import Path

from .models import Analysis, Score, TableCandidate
from .tabular import cell, read_tables


NETLIST_FIELDS = {"net_name"}
NETLIST_ENDPOINT_SETS = ({"endpoint_a", "endpoint_b"}, {"all_pins"})
PLACEMENT_FIELDS = {"refdes", "x", "y"}


def _kind_score(table: TableCandidate) -> tuple[Score, tuple[str, ...]]:
    fields = set(table.mapping)
    evidence: list[str] = []
    issues: list[str] = []
    netlist = 0.0
    placement = 0.0
    if NETLIST_FIELDS <= fields:
        netlist += 35
        evidence.append("net_name column mapped")
    if any(required <= fields for required in NETLIST_ENDPOINT_SETS):
        netlist += 55
        evidence.append("endpoint columns mapped")
    if PLACEMENT_FIELDS <= fields:
        placement += 75
    placement += min(25, 5 * len(fields & {"role", "side", "mirror", "rotation", "package"}))
    if placement:
        placement_evidence = ["refdes/x/y columns mapped"]
        if fields & {"role", "side", "mirror", "rotation", "package"}:
            placement_evidence.append("placement attributes mapped")
    else:
        placement_evidence = []
    if table.ambiguous_columns:
        issues.append("One or more semantic fields match multiple source columns")
    if netlist == placement and netlist > 0:
        issues.append("Table matches both Netlist and Placement")
        return Score("ambiguous", netlist, tuple(evidence + placement_evidence)), tuple(issues)
    if netlist > placement:
        return Score("netlist", min(netlist, 100), tuple(evidence)), tuple(issues)
    if placement > netlist:
        return Score("placement", min(placement, 100), tuple(placement_evidence)), tuple(issues)
    return Score("unknown", 0, ()), tuple((*issues, "Required semantic columns were not found"))


def _values(table: TableCandidate, field: str, limit: int = 500) -> list[str]:
    index = table.mapping.get(field)
    if index is None:
        return []
    return [value for row in table.rows[:limit] if (value := cell(row, index))]


def _family_scores(table: TableCandidate, profile: dict) -> tuple[Score, ...]:
    values = {
        field: _values(table, field)
        for field in ("net_name", "signal_type", "group")
    }
    values["filename"] = [table.source.name]
    values["sheet"] = [table.sheet]
    scores: list[Score] = []
    for family, rules in profile["family_rules"].items():
        total = 0.0
        evidence: list[str] = []
        for rule in rules:
            field = rule.get("field", "net_name")
            population = values.get(field, [])
            if not population:
                continue
            regex = re.compile(rule["pattern"], re.IGNORECASE)
            matched = sum(regex.search(value) is not None for value in population)
            if not matched:
                continue
            coverage = matched / len(population)
            weight = float(rule.get("weight", 10))
            points = weight * coverage
            total += points
            evidence.append(
                f"{field}:{rule['pattern']} matched {matched}/{len(population)} (+{points:.1f})"
            )
        scores.append(Score(family, total, tuple(evidence)))
    return tuple(sorted(scores, key=lambda item: (-item.value, item.name)))


def _topology(table: TableCandidate, profile: dict) -> Score:
    source_text = "/".join(part.casefold() for part in table.source.parts)
    candidates = []
    for topology, patterns in profile.get("topology_rules", {}).items():
        matched = [pattern for pattern in patterns if re.search(pattern, source_text, re.IGNORECASE)]
        candidates.append(Score(topology, 20.0 * len(matched), tuple(f"path:{item}" for item in matched)))
    candidates.sort(key=lambda item: (-item.value, item.name))
    if not candidates or candidates[0].value == 0:
        return Score("unknown", 0, ())
    if len(candidates) > 1 and candidates[0].value == candidates[1].value:
        return Score("ambiguous", candidates[0].value, candidates[0].evidence + candidates[1].evidence)
    return candidates[0]


def _table_rank(table: TableCandidate, profile: dict) -> tuple[int, int, int, str]:
    kind, _ = _kind_score(table)
    preferred = [str(value).casefold() for value in profile.get("table", {}).get("preferred_sheets", [])]
    try:
        sheet_rank = len(preferred) - preferred.index(table.sheet.casefold())
    except ValueError:
        sheet_rank = 0
    return int(kind.value), sheet_rank, len(table.rows), table.sheet.casefold()


def analyze(source: str | Path, profile: dict, profile_sha256: str, sheet: str = "") -> Analysis:
    tables = read_tables(source, profile)
    if sheet:
        selected = [item for item in tables if item.sheet.casefold() == sheet.casefold()]
        if not selected:
            raise ValueError(f"Worksheet not found: {sheet}")
        table = selected[0]
    else:
        table = max(tables, key=lambda item: _table_rank(item, profile))
    kind, kind_issues = _kind_score(table)
    family_candidates = _family_scores(table, profile)
    family = family_candidates[0] if family_candidates else Score("unknown", 0, ())
    threshold = float(profile.get("classification", {}).get("minimum_family_score", 5))
    margin = float(profile.get("classification", {}).get("minimum_family_margin", 1.5))
    issues = list(kind_issues)
    status = "AUTO"
    if kind.name in {"unknown", "ambiguous"} or table.ambiguous_columns:
        status = "REJECT"
    if kind.name == "netlist":
        second = family_candidates[1].value if len(family_candidates) > 1 else 0
        if family.value < threshold:
            issues.append("No signal family reached the minimum evidence score")
            status = "REVIEW" if status != "REJECT" else status
        elif family.value - second < margin:
            issues.append("The leading signal families are tied or too close")
            status = "REVIEW" if status != "REJECT" else status
    else:
        family = Score("not_applicable", 100, ("placement is family-neutral",))
    topology = _topology(table, profile)
    if topology.name in {"unknown", "ambiguous"}:
        issues.append("Topology requires an explicit PCB/PKG selection")
        status = "REVIEW" if status == "AUTO" else status
    return Analysis(
        source=Path(source).expanduser().resolve(),
        profile_id=str(profile["id"]),
        profile_version=str(profile["version"]),
        profile_sha256=profile_sha256,
        table=table,
        kind=kind,
        family=family,
        topology=topology,
        family_candidates=family_candidates,
        status=status,
        issues=tuple(issues),
    )
