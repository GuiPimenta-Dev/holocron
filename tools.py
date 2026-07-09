"""Pure retrieval functions over Neo4j + LanceDB.

Boundary rules (CLAUDE.md): plain-data in, plain-data out; no LLM in the
process; no framework imports. Docstrings are LLM-facing — the agent routes
by reading them. Empty results return empty structures, never raise.
"""

from __future__ import annotations

import os
from typing import Any

from neo4j import Driver, GraphDatabase

_driver: Driver | None = None

CORE_KEYS = ("title", "name", "type", "continuity")


def _get_driver() -> Driver:
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            auth=(
                os.environ.get("NEO4J_USER", "neo4j"),
                os.environ.get("NEO4J_PASSWORD", "holocron123"),
            ),
        )
    return _driver


def _entity_dict(node: Any) -> dict[str, Any]:
    props = dict(node)
    return {k: props.pop(k, None) for k in CORE_KEYS} | {"properties": props}


def get_entity(name: str) -> list[dict[str, Any]]:
    """Look up a Star Wars entity (character, planet, organization...) by name.

    Use this first for any question about a specific named subject. Returns one
    entry per continuity the entity exists in — a `canon` and/or a `legends`
    version — each with its wiki `title`, entity `type` (Character,
    Celestialbody, ...), and infobox `properties` (species, homeworld, birth...).
    Returns an empty list if the corpus has no such entity.

    Example: get_entity("Kit Fisto") -> [{"title": "Kit Fisto", "type":
    "Character", "continuity": "canon", "properties": {...}}, {"title":
    "Kit Fisto/Legends", "continuity": "legends", ...}]
    """
    with _get_driver().session() as session:
        records = session.run(
            "MATCH (e:Entity) "
            "WHERE toLower(e.name) = toLower($q) OR toLower(e.title) = toLower($q) "
            "RETURN e ORDER BY e.continuity",
            q=name,
        )
        return [_entity_dict(r["e"]) for r in records]
