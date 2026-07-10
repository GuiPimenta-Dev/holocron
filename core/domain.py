"""Domain vocabulary as types (CONTEXT.md), shared by ingest and serving.

Frozen dataclasses + primitives are this project's "plain data" (ADR-0004);
dict/JSON exists only at the edges — convert once, with `.as_dict()`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Continuity(StrEnum):
    CANON = "canon"
    LEGENDS = "legends"

    @classmethod
    def parse(cls, value: str | None) -> Continuity | None:
        """Lenient edge conversion: junk (LLM-supplied values) becomes None."""
        try:
            return cls(value) if value else None
        except ValueError:
            return None


@dataclass(frozen=True)
class EntityRecord:
    """A graph node as the serving side sees it: one entity in one continuity."""

    title: str
    name: str
    type: str
    continuity: Continuity
    properties: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Relation:
    """One typed edge touching an entity; `other_*` describe the far end."""

    relation: str
    other_title: str
    other_type: str
    other_continuity: Continuity

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EntityRelations:
    """All edges of one entity in one continuity."""

    title: str
    name: str
    continuity: Continuity
    outgoing: tuple[Relation, ...]
    incoming: tuple[Relation, ...]
    incoming_total: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PathStep:
    source: str
    relation: str
    target: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Path:
    """One connection between two entities: the entities visited and the steps."""

    entities: tuple[str, ...]
    steps: tuple[PathStep, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Chunk:
    """A section-bounded slice of an entity's text; the unit of vector retrieval."""

    title: str
    name: str
    section: str
    continuity: Continuity
    text: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Citation:
    """Pointer from an answer back to its source (CONTEXT.md: Citation)."""

    title: str
    name: str
    continuity: Continuity
    section: str | None = None

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.section is None:
            del d["section"]
        return d
