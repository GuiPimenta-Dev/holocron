"""Retrieval tools against a real Neo4j seeded from saved wikitext fixtures."""

import pytest

from tools import get_entity

pytestmark = pytest.mark.usefixtures("graph")


def test_get_entity_returns_both_continuities():
    results = get_entity("Kit Fisto")
    assert {r["continuity"] for r in results} == {"canon", "legends"}
    canon = next(r for r in results if r["continuity"] == "canon")
    assert canon["title"] == "Kit Fisto"
    assert canon["type"] == "Character"
    assert canon["properties"].get("eyes")  # infobox props survive the round trip


def test_get_entity_is_case_insensitive():
    assert get_entity("kit fisto")
    assert get_entity("TATOOINE")


def test_get_entity_accepts_exact_title():
    results = get_entity("Kit Fisto/Legends")
    assert len(results) == 1
    assert results[0]["continuity"] == "legends"


def test_get_entity_not_found_returns_empty_list():
    assert get_entity("Jar Jar Abrams") == []
