"""VectorIndex against the real pgvector index (built from the pinned corpus)."""

from core.domain import Continuity


def test_search_returns_relevant_chunks_with_metadata(vector_index):
    results = vector_index.search("the Jedi purge executed by the clone troopers", k=5)
    assert 0 < len(results) <= 5
    assert any("order 66" in (r.title + r.text).lower() for r in results)


def test_search_respects_continuity_filter(vector_index):
    results = vector_index.search("Jedi Order history", continuity="legends", k=5)
    assert results
    assert all(r.continuity is Continuity.LEGENDS for r in results)


def test_search_ignores_invalid_continuity(vector_index):
    # the LLM controls this argument — junk must not become a filter clause
    assert vector_index.search("Tatooine desert", continuity="disney", k=2)


def test_search_caps_results_at_k(vector_index):
    assert len(vector_index.search("lightsaber", k=3)) <= 3
