"""KnowledgeGraph against a real Neo4j seeded from saved wikitext fixtures."""

from core.domain import Continuity


def test_get_entity_returns_both_continuities(knowledge_graph):
    results = knowledge_graph.get_entity("Kit Fisto")
    assert {r.continuity for r in results} == {Continuity.CANON, Continuity.LEGENDS}
    canon = next(r for r in results if r.continuity is Continuity.CANON)
    assert canon.title == "Kit Fisto"
    assert canon.type == "Character"
    assert canon.properties.get("eyes")  # infobox props survive the round trip


def test_get_entity_is_case_insensitive(knowledge_graph):
    assert knowledge_graph.get_entity("kit fisto")
    assert knowledge_graph.get_entity("TATOOINE")


def test_get_entity_accepts_exact_title(knowledge_graph):
    results = knowledge_graph.get_entity("Kit Fisto/Legends")
    assert len(results) == 1
    assert results[0].continuity is Continuity.LEGENDS


def test_get_entity_not_found_returns_empty_list(knowledge_graph):
    assert knowledge_graph.get_entity("Jar Jar Abrams") == []


def test_get_relations_lists_outgoing_edges(knowledge_graph):
    results = knowledge_graph.get_relations("Kit Fisto")
    canon = next(r for r in results if r.continuity is Continuity.CANON)
    member_of = [o for o in canon.outgoing if o.relation == "MEMBER_OF"]
    assert any(o.other_title == "Jedi Order" for o in member_of)


def test_get_relations_not_found_returns_empty_list(knowledge_graph):
    assert knowledge_graph.get_relations("Jar Jar Abrams") == []


def test_path_between_finds_direct_edge(knowledge_graph):
    paths = knowledge_graph.path_between("Kit Fisto", "Jedi Order")
    assert paths
    step = paths[0].steps[0]
    assert len(paths[0].steps) == 1
    assert step.relation == "MEMBER_OF"
    assert {step.source, step.target} == {"Kit Fisto", "Jedi Order"}


def test_path_between_no_path_returns_empty_list(knowledge_graph):
    assert knowledge_graph.path_between("Kit Fisto", "Jar Jar Abrams") == []


def test_run_cypher_executes_read_queries(knowledge_graph):
    rows = knowledge_graph.run_cypher("MATCH (e:Entity {name: 'Kit Fisto'}) RETURN e.title AS t")
    assert isinstance(rows, list)
    assert {"t": "Kit Fisto"} in rows


def test_run_cypher_rejects_writes(knowledge_graph):
    for evil in (
        "CREATE (x:Hack {name: 'x'})",
        "MATCH (e:Entity) DELETE e",
        "MATCH (e:Entity) SET e.name = 'pwned'",
        "MATCH (e) CALL apoc.create.node(['X'], {}) YIELD node RETURN node",
        "  match (e) detach delete e",
    ):
        result = knowledge_graph.run_cypher(evil)
        assert isinstance(result, dict) and "error" in result, evil
    assert knowledge_graph.run_cypher("MATCH (x:Hack) RETURN x") == []  # nothing was written


def test_run_cypher_surfaces_syntax_errors_without_raising(knowledge_graph):
    result = knowledge_graph.run_cypher("MATCH (e:Entity RETURN e")
    assert isinstance(result, dict) and "error" in result
