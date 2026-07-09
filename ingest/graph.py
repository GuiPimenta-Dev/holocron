"""Load parsed entities into Neo4j.

Nodes: one per entity, label = infobox type (whitelisted) + :Entity always.
Edges: infobox fields whose wikilinks resolve to another corpus entity.
Edge names: curated map for the common fields, SCREAMING_SNAKE fallback.
"""

from __future__ import annotations

import os
import re
from typing import LiteralString, cast

from neo4j import GraphDatabase

from ingest.parse import Entity

# Curated edge names; anything else falls back to SCREAMING_SNAKE(field).
FIELD_TO_EDGE = {
    "homeworld": "HOMEWORLD",
    "species": "SPECIES",
    "masters": "TRAINED_BY",
    "apprentices": "TRAINED",
    "affiliation": "MEMBER_OF",
    "region": "IN_REGION",
    "sector": "IN_SECTOR",
    "system": "IN_SYSTEM",
    "capital": "HAS_CAPITAL",
    "headquarters": "HEADQUARTERED_IN",
    "leader": "LED_BY",
    "leaders": "LED_BY",
    "founder": "FOUNDED_BY",
}

# Fields that are properties of the entity, not relations — even if they
# happen to contain wikilinks (dates link to year pages, etc.).
PROP_FIELDS = {
    "birth", "death", "gender", "pronouns", "height", "mass", "hair", "eyes",
    "skin", "cyber", "era", "type", "class", "length", "width", "population",
    "language", "currency", "atmosphere", "climate", "terrain", "gravity",
    "diameter", "rotation", "orbit", "moons", "suns", "grid",
}

SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


# Edges that only make sense pointing at a person (infoboxes also list
# titles like "Jedi Master" in the masters field).
CHARACTER_ONLY_EDGES = {"TRAINED_BY", "TRAINED"}


def _edge_name(fieldname: str) -> str | None:
    fieldname = re.sub(r"\d+$", "", fieldname)  # commanders1/commanders2 -> commanders
    if fieldname in PROP_FIELDS:
        return None
    name = FIELD_TO_EDGE.get(fieldname, re.sub(r"[^a-z0-9]+", "_", fieldname).upper().strip("_"))
    return name if SAFE_NAME.match(name) else None


def driver():
    return GraphDatabase.driver(
        os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        auth=(
            os.environ.get("NEO4J_USER", "neo4j"),
            os.environ.get("NEO4J_PASSWORD", "holocron123"),
        ),
    )


def _resolve(
    target: str, continuity: str, corpus: set[str], redirects: dict[str, str]
) -> str | None:
    """Resolve a wikilink to a corpus entity title, preferring same continuity."""
    target = redirects.get(target, target)
    if continuity == "legends" and f"{target}/Legends" in corpus:
        return f"{target}/Legends"
    return target if target in corpus else None


def load(entities: list[Entity], redirects: dict[str, str]) -> dict[str, int]:
    corpus = {e.title for e in entities}
    nodes = [
        {
            "title": e.title,
            "name": e.name,
            "type": e.type,
            "continuity": e.continuity,
            "props": {
                k: v["text"] for k, v in e.fields.items() if k in PROP_FIELDS and v["text"]
            },
        }
        for e in entities
    ]
    types = {e.title: e.type for e in entities}
    edges: dict[str, list[dict]] = {}
    for e in entities:
        for fieldname, value in e.fields.items():
            rel = _edge_name(fieldname)
            if rel is None:
                continue
            for link in value["links"]:
                target = _resolve(link, e.continuity, corpus, redirects)
                if target is None or target == e.title:
                    continue
                if rel in CHARACTER_ONLY_EDGES and types[target] != "Character":
                    continue
                edges.setdefault(rel, []).append({"src": e.title, "dst": target})

    with driver() as drv, drv.session() as session:
        session.run("MATCH (n) DETACH DELETE n")  # load() rebuilds from scratch
        session.run("CREATE CONSTRAINT entity_title IF NOT EXISTS "
                    "FOR (e:Entity) REQUIRE e.title IS UNIQUE")
        session.run(
            "UNWIND $nodes AS n "
            "MERGE (e:Entity {title: n.title}) "
            "SET e.name = n.name, e.type = n.type, e.continuity = n.continuity, e += n.props",
            nodes=nodes,
        )
        # Second pass: type-specific labels (dynamic labels need per-type queries).
        for etype in {n["type"] for n in nodes}:
            if SAFE_NAME.match(etype):
                # cast is safe: etype/rel are SAFE_NAME-validated identifiers
                session.run(
                    cast(LiteralString, f"MATCH (e:Entity) WHERE e.type = $t SET e:`{etype}`"),
                    t=etype,
                )
        edge_count = 0
        for rel, rows in edges.items():
            session.run(
                cast(
                    LiteralString,
                    f"UNWIND $rows AS r "
                    f"MATCH (a:Entity {{title: r.src}}), (b:Entity {{title: r.dst}}) "
                    f"MERGE (a)-[:`{rel}`]->(b)",
                ),
                rows=rows,
            )
            edge_count += len(rows)
    return {"nodes": len(nodes), "edges": edge_count, "edge_types": len(edges)}
