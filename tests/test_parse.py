"""Parser tests over real Wookieepedia wikitext fixtures."""

import json
from pathlib import Path

import pytest

from ingest.graph import _edge_name, _resolve
from ingest.parse import parse_page

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str):
    page = json.loads((FIXTURES / f"{name}.json").read_text())
    return parse_page(page["title"], page["wikitext"], page["categories"])


@pytest.fixture(scope="module")
def kit():
    return load("Kit_Fisto")


@pytest.fixture(scope="module")
def kit_legends():
    return load("Kit_Fisto_Legends")


@pytest.fixture(scope="module")
def tatooine():
    return load("Tatooine")


def test_character_type_and_continuity(kit, kit_legends):
    assert kit.type == "Character"
    assert kit.continuity == "canon"
    assert kit_legends.continuity == "legends"
    assert kit_legends.name == "Kit Fisto"
    assert kit_legends.title == "Kit Fisto/Legends"


def test_infobox_fields_have_links(kit):
    assert "Nautolan" in kit.fields["species"]["links"]
    assert "Jedi Order" in kit.fields["affiliation"]["links"]


def test_planet_type(tatooine):
    assert tatooine.type == "Celestialbody"  # Wookieepedia's infobox for planets/moons/stars
    assert tatooine.continuity == "canon"


def test_chunks_are_clean_text(kit):
    assert len(kit.chunks) > 5
    for c in kit.chunks:
        assert "{{" not in c["text"], f"template leaked into chunk: {c['text'][:80]}"
        assert "<ref" not in c["text"]
        assert len(c["text"]) <= 2200  # CHUNK_MAX + paragraph slack


def test_page_without_infobox_returns_none():
    assert parse_page("Redirect page", "#REDIRECT [[Anakin Skywalker]]", []) is None


def test_real_world_page_is_skipped():
    assert load("George_Lucas") is None  # {{Top|rwp}} — actor/crew page, not lore


def test_concept_page_without_infobox_becomes_topic():
    blaster = load("Blaster")
    assert blaster is not None
    assert blaster.type == "Topic"
    assert blaster.fields == {}
    assert len(blaster.chunks) > 3  # text still indexed for vector search


def test_edge_names():
    assert _edge_name("masters") == "TRAINED_BY"
    assert _edge_name("birth") is None  # property, not relation
    assert _edge_name("some weird-field") == "SOME_WEIRD_FIELD"
    assert _edge_name("commanders1") == "COMMANDERS"  # battle infoboxes number these


def test_resolve_prefers_same_continuity():
    corpus = {"Tatooine", "Tatooine/Legends", "Naboo"}
    redirects = {"Vader": "Naboo"}
    assert _resolve("Tatooine", "legends", corpus, redirects) == "Tatooine/Legends"
    assert _resolve("Tatooine", "canon", corpus, redirects) == "Tatooine"
    assert _resolve("Vader", "canon", corpus, redirects) == "Naboo"
    assert _resolve("Unknown", "canon", corpus, redirects) is None
