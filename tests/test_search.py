"""search_chunks against the real LanceDB index (built from the pinned corpus)."""

import pytest

from tools import search_chunks

pytestmark = pytest.mark.usefixtures("vector_index")


def test_search_returns_relevant_chunks_with_metadata():
    results = search_chunks("the Jedi purge executed by the clone troopers", k=5)
    assert 0 < len(results) <= 5
    for r in results:
        assert {"title", "name", "section", "continuity", "text"} <= set(r)
        assert r["continuity"] in ("canon", "legends")
    assert any("order 66" in (r["title"] + r["text"]).lower() for r in results)


def test_search_respects_continuity_filter():
    results = search_chunks("Jedi Order history", continuity="legends", k=5)
    assert results
    assert all(r["continuity"] == "legends" for r in results)


def test_search_ignores_invalid_continuity():
    # the LLM controls this argument — junk must not become a filter clause
    assert search_chunks("Tatooine desert", continuity="disney", k=2)


def test_search_caps_results_at_k():
    assert len(search_chunks("lightsaber", k=3)) <= 3
