"""Serving-side semantic search over the pgvector chunk index (ADR-0005).

Boundary rules (CLAUDE.md): domain types in/out, no LLM, no framework. The
`search` docstring is LLM-facing — the agent routes by reading it (never trim).
"""

from __future__ import annotations

from typing import Any

from core.domain import Chunk, Continuity
from core.embeddings import EmbeddingProvider, pgvector_literal


class VectorIndex:
    """Query-time face of the chunk index; embeds with the same provider as ingest."""

    def __init__(self, embeddings: EmbeddingProvider, conn: Any):
        self._embeddings = embeddings
        self._conn = conn  # psycopg connection, opened by the composition root

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
        vector = pgvector_literal(self._embeddings.embed([query])[0])
        limit = max(1, min(int(k), 20))
        parsed = Continuity.parse(continuity)  # LLM-controlled arg: junk never filters
        where = "WHERE continuity = %(continuity)s" if parsed else ""
        rows = self._conn.execute(
            f"SELECT title, name, section, continuity, text FROM chunks {where} "
            f"ORDER BY embedding <=> %(query)s::vector LIMIT {limit}",
            {"query": vector, "continuity": str(parsed) if parsed else None},
        ).fetchall()
        return [
            Chunk(title=title, name=name, section=section, continuity=Continuity(cont), text=text)
            for title, name, section, cont, text in rows
        ]
