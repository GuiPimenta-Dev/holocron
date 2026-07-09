"""Pure retrieval functions over Neo4j + LanceDB.

Boundary rules (CLAUDE.md): plain-data in, plain-data out; no LLM in the
process; no framework imports. Docstrings are LLM-facing — the agent routes
by reading them. Empty results return empty structures, never raise.
"""

from __future__ import annotations

import os
import re
from typing import Any, LiteralString, cast

from neo4j import READ_ACCESS, Driver, GraphDatabase
from neo4j.exceptions import Neo4jError

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


INCOMING_CAP = 50  # popular nodes (Tatooine...) have hundreds of incoming edges


def get_relations(name: str) -> list[dict[str, Any]]:
    """List the knowledge-graph relations of an entity, per continuity.

    Use this to answer relational questions ("who trained X?", "what is X a
    member of?") after locating the entity. Returns one entry per continuity
    with `outgoing` edges (this entity -> target, e.g. TRAINED_BY, MEMBER_OF,
    HOMEWORLD) and `incoming` edges (source -> this entity, capped at 50 with
    the true count in `incoming_total`). Empty list if the entity is unknown.

    Example: get_relations("Kit Fisto") -> [{"title": "Kit Fisto",
    "continuity": "canon", "outgoing": [{"relation": "MEMBER_OF", "target":
    "Jedi Order", ...}], "incoming": [...], "incoming_total": 3}, ...]
    """
    out = []
    with _get_driver().session() as session:
        for match in get_entity(name):
            title = match["title"]
            outgoing = session.run(
                "MATCH (e:Entity {title: $t})-[r]->(x:Entity) "
                "RETURN type(r) AS relation, x.title AS target, x.type AS target_type, "
                "x.continuity AS target_continuity ORDER BY relation, target",
                t=title,
            ).data()
            incoming = session.run(
                "MATCH (x:Entity)-[r]->(e:Entity {title: $t}) "
                "RETURN type(r) AS relation, x.title AS source, x.type AS source_type, "
                "x.continuity AS source_continuity ORDER BY relation, source",
                t=title,
            ).data()
            out.append(
                {
                    "title": title,
                    "name": match["name"],
                    "continuity": match["continuity"],
                    "outgoing": outgoing,
                    "incoming": incoming[:INCOMING_CAP],
                    "incoming_total": len(incoming),
                }
            )
    return out


def path_between(a: str, b: str, max_hops: int = 4) -> list[dict[str, Any]]:
    """Find how two entities are connected through the knowledge graph.

    Use this for multi-hop questions ("how is X related to Y?"). Returns up to
    5 shortest undirected paths, each as ordered `steps` of
    {"from", "relation", "to"} plus the `entities` visited. Empty list when
    either entity is unknown or no path exists within `max_hops` (default 4).

    Example: path_between("Kit Fisto", "Jedi Order") -> [{"entities":
    ["Kit Fisto", "Jedi Order"], "steps": [{"from": "Kit Fisto", "relation":
    "MEMBER_OF", "to": "Jedi Order"}]}]
    """
    hops = max(1, min(int(max_hops), 6))
    paths = []
    with _get_driver().session() as session:
        records = session.run(
            cast(
                LiteralString,  # safe: hops is a clamped int, the only interpolation
                f"MATCH (a:Entity), (b:Entity) "
                f"WHERE (toLower(a.name) = toLower($a) OR toLower(a.title) = toLower($a)) "
                f"AND (toLower(b.name) = toLower($b) OR toLower(b.title) = toLower($b)) "
                f"MATCH p = allShortestPaths((a)-[*..{hops}]-(b)) "
                f"RETURN p LIMIT 5",
            ),
            a=a,
            b=b,
        )
        for record in records:
            p = record["p"]
            paths.append(
                {
                    "entities": [n["title"] for n in p.nodes],
                    "steps": [
                        {
                            "from": r.start_node["title"],  # pyright: ignore[reportOptionalSubscript]
                            "relation": r.type,
                            "to": r.end_node["title"],  # pyright: ignore[reportOptionalSubscript]
                        }
                        for r in p.relationships
                    ],
                }
            )
    return paths


_WRITE_KEYWORDS = re.compile(
    r"\b(create|merge|delete|detach|set|remove|drop|call|load|foreach)\b", re.IGNORECASE
)
ROW_CAP = 50


def run_cypher(query: str) -> list[dict[str, Any]] | dict[str, str]:
    """Run a read-only Cypher query against the knowledge graph (escape hatch).

    Use this only when the typed tools cannot express the question (aggregates,
    unusual patterns). Nodes are `(:Entity {title, name, type, continuity, ...})`;
    relations are SCREAMING_SNAKE (TRAINED_BY, MEMBER_OF, HOMEWORLD...). The
    query must start with MATCH and contain no write clauses — anything else is
    rejected. Returns at most 50 rows, or {"error": ...} explaining what to fix.

    Example: run_cypher("MATCH (c:Character)-[:HOMEWORLD]->(p {name: 'Tatooine'})
    RETURN c.name, c.continuity")
    """
    stripped = query.strip()
    if not stripped.lower().startswith("match"):
        return {"error": "read-only: the query must start with MATCH"}
    if m := _WRITE_KEYWORDS.search(stripped):
        return {"error": f"read-only: {m.group(0).upper()} is not allowed"}
    try:
        # READ_ACCESS is the backstop in case a write form slips past the regex.
        with _get_driver().session(default_access_mode=READ_ACCESS) as session:
            return session.run(stripped).data()[:ROW_CAP]  # pyright: ignore[reportArgumentType]
    except Neo4jError as exc:
        return {"error": str(exc)}
