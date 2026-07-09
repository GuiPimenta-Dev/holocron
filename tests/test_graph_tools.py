"""Graph tools against a real Neo4j seeded from saved wikitext fixtures."""

import pytest

from tools import get_relations, path_between, run_cypher

pytestmark = pytest.mark.usefixtures("graph")


def test_get_relations_lists_outgoing_edges():
    results = get_relations("Kit Fisto")
    canon = next(r for r in results if r["continuity"] == "canon")
    member_of = [o for o in canon["outgoing"] if o["relation"] == "MEMBER_OF"]
    assert any(o["target"] == "Jedi Order" for o in member_of)
    assert all(
        {"relation", "target", "target_type", "target_continuity"} <= set(o) for o in member_of
    )


def test_get_relations_not_found_returns_empty_list():
    assert get_relations("Jar Jar Abrams") == []


def test_path_between_finds_direct_edge():
    paths = path_between("Kit Fisto", "Jedi Order")
    assert paths
    assert len(paths[0]["steps"]) == 1
    step = paths[0]["steps"][0]
    assert step["relation"] == "MEMBER_OF"
    assert {step["from"], step["to"]} == {"Kit Fisto", "Jedi Order"}


def test_path_between_no_path_returns_empty_list():
    assert path_between("Kit Fisto", "Jar Jar Abrams") == []


def test_run_cypher_executes_read_queries():
    rows = run_cypher("MATCH (e:Entity {name: 'Kit Fisto'}) RETURN e.title AS title")
    assert isinstance(rows, list)
    assert {"title": "Kit Fisto"} in rows


def test_run_cypher_rejects_writes():
    for evil in (
        "CREATE (x:Hack {name: 'x'})",
        "MATCH (e:Entity) DELETE e",
        "MATCH (e:Entity) SET e.name = 'pwned'",
        "MATCH (e) CALL apoc.create.node(['X'], {}) YIELD node RETURN node",
        "  match (e) detach delete e",
    ):
        result = run_cypher(evil)
        assert isinstance(result, dict) and "error" in result, evil
    # and nothing was written
    assert run_cypher("MATCH (x:Hack) RETURN x") == []


def test_run_cypher_surfaces_syntax_errors_without_raising():
    result = run_cypher("MATCH (e:Entity RETURN e")
    assert isinstance(result, dict) and "error" in result
