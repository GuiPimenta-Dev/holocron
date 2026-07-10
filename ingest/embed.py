"""Embed chunks into LanceDB using an injected provider (core/embeddings.py)."""

from __future__ import annotations

import lancedb

from core.embeddings import EmbeddingProvider

BATCH = 100


class IndexBuilder:
    """Rebuilds the chunk table from scratch with one embedding provider."""

    def __init__(self, embeddings: EmbeddingProvider, db_dir: str):
        self._embeddings = embeddings
        self._db_dir = db_dir

    def build(self, chunks: list[dict], table: str = "chunks") -> int:
        """chunks: [{title, name, continuity, section, text}]. Rebuilds the table."""
        rows = []
        for i in range(0, len(chunks), BATCH):
            batch = chunks[i : i + BATCH]
            vectors = self._embeddings.embed([c["text"] for c in batch])
            rows += [{**c, "vector": v} for c, v in zip(batch, vectors, strict=True)]
            print(f"  embedded {min(i + BATCH, len(chunks))}/{len(chunks)}")
        db = lancedb.connect(self._db_dir)
        db.create_table(table, rows, mode="overwrite")
        return len(rows)
