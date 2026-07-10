"""Serving-side semantic search over the LanceDB chunk index.

Boundary rules (CLAUDE.md): domain types in/out, no LLM, no framework. The
`search` docstring is LLM-facing — the agent routes by reading it (never trim).
"""

from __future__ import annotations

from typing import Any

from core.domain import Chunk, Continuity
from core.embeddings import EmbeddingProvider


class VectorIndex:
    """Query-time face of the chunk index; embeds with the same provider as ingest."""

    def __init__(self, embeddings: EmbeddingProvider, table: Any):
        self._embeddings = embeddings
        self._table = table  # lancedb table, opened by the composition root

    def search(self, query: str, continuity: str | None = None, k: int = 8) -> list[Chunk]:
        """Semantic search over the wiki's prose, returning the best-matching text chunks.

        Use this for descriptive or narrative questions ("describe Order 66",
        "what happened at the Battle of Endor?") and whenever the graph tools
        can't answer — the graph only holds infobox facts, the chunks hold the
        full article text. Each result carries the source entity `title`, the
        article `section`, its `continuity` (canon | legends) and the `text`.
        Optionally restrict to one continuity. Returns at most `k` chunks.

        Example: search_chunks("execution of Order 66", continuity="canon") ->
        [{"title": "Order 66", "section": "Introduction", "continuity":
        "canon", "text": "Order 66, also known as..."}, ...]
        """
        vector = self._embeddings.embed([query])[0]
        request = self._table.search(vector).limit(max(1, min(int(k), 20)))
        if parsed := Continuity.parse(continuity):  # LLM-controlled arg: junk never filters
            request = request.where(f"continuity = '{parsed}'", prefilter=True)
        return [
            Chunk(
                title=row["title"],
                name=row["name"],
                section=row["section"],
                continuity=Continuity(row["continuity"]),
                text=row["text"],
            )
            for row in request.to_list()
        ]
