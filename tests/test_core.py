"""core/: domain edge conversions and embedding provider selection."""

import pytest

from core.domain import Citation, Continuity
from core.embeddings import OpenAIEmbeddings, VoyageEmbeddings, provider_from_env


def test_continuity_parse_is_lenient_at_the_edge():
    assert Continuity.parse("canon") is Continuity.CANON
    assert Continuity.parse("legends") is Continuity.LEGENDS
    assert Continuity.parse("disney") is None  # LLM-supplied junk
    assert Continuity.parse(None) is None


def test_citation_serializes_without_null_section():
    entity = Citation(title="Kit Fisto", name="Kit Fisto", continuity=Continuity.CANON)
    chunk = Citation("Order 66", "Order 66", Continuity.CANON, section="History")
    assert "section" not in entity.as_dict()
    assert entity.as_dict()["continuity"] == "canon"  # StrEnum serializes as its value
    assert chunk.as_dict()["section"] == "History"


def test_provider_selection_prefers_openai_and_fails_loudly():
    assert isinstance(provider_from_env({"OPENAI_API_KEY": "x"}), OpenAIEmbeddings)
    assert isinstance(provider_from_env({"VOYAGE_API_KEY": "y"}), VoyageEmbeddings)
    assert isinstance(
        provider_from_env({"OPENAI_API_KEY": "x", "VOYAGE_API_KEY": "y"}), OpenAIEmbeddings
    )
    with pytest.raises(RuntimeError):
        provider_from_env({})
