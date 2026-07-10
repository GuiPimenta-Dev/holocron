"""Serving-side access to the knowledge graph.

Boundary rules (CLAUDE.md): domain types in/out, no LLM, no framework. The
public method docstrings are LLM-facing — the agent routes by reading them
(never trim). Empty results return empty structures, never raise.
"""

from __future__ import annotations

import re
from typing import Any, LiteralString, cast

from neo4j import READ_ACCESS, Driver
from neo4j.exceptions import Neo4jError

from core.domain import Continuity, EntityRecord, EntityRelations, Path, PathStep, Relation

INCOMING_CAP = 50  # popular nodes (Tatooine...) have hundreds of incoming edges
ROW_CAP = 50

_CORE_KEYS = ("title", "name", "type", "continuity")
_WRITE_KEYWORDS = re.compile(
    r"\b(create|merge|delete|detach|set|remove|drop|call|load|foreach)\b", re.IGNORECASE
)


def _name_match(var: str, param: str) -> str:
    """Cypher fragment: case-insensitive match on an entity's name or exact title."""
    return f"(toLower({var}.name) = toLower(${param}) OR toLower({var}.title) = toLower(${param}))"


class KnowledgeGraph:
    """Typed queries over the Neo4j entity graph, plus a read-only escape hatch."""

    def __init__(self, driver: Driver):
        self._driver = driver

    def get_entity(self, name: str) -> list[EntityRecord]:
        """Look up a Star Wars entity (character, planet, organization...) by name.

        Use this first for any question about a specific named subject. Returns
        one entry per continuity the entity exists in — a `canon` and/or a
        `legends` version — each with its wiki `title`, entity `type`
        (Character, Celestialbody, ...), and infobox `properties` (birth, eyes,
        height...). Returns an empty list if the corpus has no such entity.

        Example: get_entity("Kit Fisto") -> [{"title": "Kit Fisto", "type":
        "Character", "continuity": "canon", "properties": {...}}, {"title":
        "Kit Fisto/Legends", "continuity": "legends", ...}]
        """
        with self._driver.session() as session:
            records = session.run(
                cast(
                    LiteralString,
                    f"MATCH (e:Entity) WHERE {_name_match('e', 'q')} "
                    f"RETURN e ORDER BY e.continuity",
                ),
                q=name,
            )
            return [self._entity_record(r["e"]) for r in records]

    def get_relations(self, name: str) -> list[EntityRelations]:
        """List the knowledge-graph relations of an entity, per continuity.

        Use this to answer relational questions ("who trained X?", "what is X a
        member of?") after locating the entity. Returns one entry per continuity
        with `outgoing` edges (this entity -> other, e.g. TRAINED_BY, MEMBER_OF,
        HOMEWORLD) and `incoming` edges (other -> this entity, capped at 50 with
        the true count in `incoming_total`). Each edge names the far end in
        `other_title`/`other_type`/`other_continuity`. Empty list if the entity
        is unknown.

        Example: get_relations("Kit Fisto") -> [{"title": "Kit Fisto",
        "continuity": "canon", "outgoing": [{"relation": "MEMBER_OF",
        "other_title": "Jedi Order", ...}], "incoming": [...],
        "incoming_total": 3}, ...]
        """
        out = []
        with self._driver.session() as session:
            for match in self.get_entity(name):
                outgoing = session.run(
                    "MATCH (e:Entity {title: $t})-[r]->(x:Entity) "
                    "RETURN type(r) AS relation, x.title AS title, x.type AS type, "
                    "x.continuity AS continuity ORDER BY relation, title",
                    t=match.title,
                ).data()
                incoming = session.run(
                    "MATCH (x:Entity)-[r]->(e:Entity {title: $t}) "
                    "RETURN type(r) AS relation, x.title AS title, x.type AS type, "
                    "x.continuity AS continuity ORDER BY relation, title",
                    t=match.title,
                ).data()
                out.append(
                    EntityRelations(
                        title=match.title,
                        name=match.name,
                        continuity=match.continuity,
                        outgoing=tuple(self._relation(r) for r in outgoing),
                        incoming=tuple(self._relation(r) for r in incoming[:INCOMING_CAP]),
                        incoming_total=len(incoming),
                    )
                )
        return out

    def path_between(self, a: str, b: str, max_hops: int = 4) -> list[Path]:
        """Find how two entities are connected through the knowledge graph.

        Use this for multi-hop questions ("how is X related to Y?"). Returns up
        to 5 shortest undirected paths, each as ordered `steps` of
        {"source", "relation", "target"} plus the `entities` visited. Empty
        list when either entity is unknown or no path exists within `max_hops`
        (default 4).

        Example: path_between("Kit Fisto", "Jedi Order") -> [{"entities":
        ["Kit Fisto", "Jedi Order"], "steps": [{"source": "Kit Fisto",
        "relation": "MEMBER_OF", "target": "Jedi Order"}]}]
        """
        hops = max(1, min(int(max_hops), 6))
        with self._driver.session() as session:
            records = session.run(
                cast(
                    LiteralString,  # safe: hops is a clamped int; fragments are static
                    f"MATCH (a:Entity), (b:Entity) "
                    f"WHERE {_name_match('a', 'a')} AND {_name_match('b', 'b')} "
                    f"MATCH p = allShortestPaths((a)-[*..{hops}]-(b)) "
                    f"RETURN p LIMIT 5",
                ),
                a=a,
                b=b,
            )
            return [self._path(r["p"]) for r in records]

    def run_cypher(self, query: str) -> list[dict[str, Any]] | dict[str, str]:
        """Run a read-only Cypher query against the knowledge graph (escape hatch).

        Use this only when the typed tools cannot express the question
        (aggregates, unusual patterns). Nodes are `(:Entity {title, name, type,
        continuity, ...})`; relations are SCREAMING_SNAKE (TRAINED_BY,
        MEMBER_OF, HOMEWORLD...). The query must start with MATCH and contain
        no write clauses — anything else is rejected. Returns at most 50 rows,
        or {"error": ...} explaining what to fix.

        Example: run_cypher("MATCH (c:Character)-[:HOMEWORLD]->(p {name:
        'Tatooine'}) RETURN c.name, c.continuity")
        """
        stripped = query.strip()
        if not stripped.lower().startswith("match"):
            return {"error": "read-only: the query must start with MATCH"}
        if m := _WRITE_KEYWORDS.search(stripped):
            return {"error": f"read-only: {m.group(0).upper()} is not allowed"}
        try:
            # READ_ACCESS is the backstop in case a write form slips past the regex.
            with self._driver.session(default_access_mode=READ_ACCESS) as session:
                return session.run(stripped).data()[:ROW_CAP]  # pyright: ignore[reportArgumentType]
        except Neo4jError as exc:
            return {"error": str(exc)}

    @staticmethod
    def _entity_record(node: Any) -> EntityRecord:
        props = dict(node)
        core = {k: props.pop(k, None) for k in _CORE_KEYS}
        return EntityRecord(
            title=core["title"],
            name=core["name"],
            type=core["type"],
            continuity=Continuity(core["continuity"]),
            properties=props,
        )

    @staticmethod
    def _relation(row: dict[str, Any]) -> Relation:
        return Relation(
            relation=row["relation"],
            other_title=row["title"],
            other_type=row["type"],
            other_continuity=Continuity(row["continuity"]),
        )

    @staticmethod
    def _path(p: Any) -> Path:
        return Path(
            entities=tuple(n["title"] for n in p.nodes),
            steps=tuple(
                PathStep(
                    source=r.start_node["title"],  # pyright: ignore[reportOptionalSubscript]
                    relation=r.type,
                    target=r.end_node["title"],  # pyright: ignore[reportOptionalSubscript]
                )
                for r in p.relationships
            ),
        )
