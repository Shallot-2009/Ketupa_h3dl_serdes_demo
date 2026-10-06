"""Small immutable contracts shared by the adapter stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class AdapterError(RuntimeError):
    """A user-actionable classification or normalization failure."""


class NoNormalizedRows(AdapterError):
    """The source table was valid, but no network matched the selected family."""


@dataclass(frozen=True)
class TableCandidate:
    source: Path
    sheet: str
    header_row: int
    headers: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    mapping: dict[str, int]
    ambiguous_columns: dict[str, tuple[int, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class Score:
    name: str
    value: float
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class Analysis:
    source: Path
    profile_id: str
    profile_version: str
    profile_sha256: str
    table: TableCandidate
    kind: Score
    family: Score
    topology: Score
    family_candidates: tuple[Score, ...]
    status: str
    issues: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        def score(value: Score) -> dict[str, Any]:
            return {
                "name": value.name,
                "score": round(value.value, 3),
                "evidence": list(value.evidence),
            }

        return {
            "source": str(self.source),
            "profile": {
                "id": self.profile_id,
                "version": self.profile_version,
                "sha256": self.profile_sha256,
            },
            "table": {
                "sheet": self.table.sheet,
                "header_row": self.table.header_row,
                "headers": list(self.table.headers),
                "mapped_columns": {
                    key: self.table.headers[index]
                    for key, index in sorted(self.table.mapping.items())
                },
                "ambiguous_columns": {
                    key: [self.table.headers[index] for index in indices]
                    for key, indices in self.table.ambiguous_columns.items()
                },
                "data_rows": len(self.table.rows),
            },
            "kind": score(self.kind),
            "family": score(self.family),
            "family_candidates": [score(item) for item in self.family_candidates],
            "topology": score(self.topology),
            "status": self.status,
            "issues": list(self.issues),
        }
