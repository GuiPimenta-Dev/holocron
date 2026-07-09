"""Embed chunks into LanceDB. Provider picked by available API key."""

from __future__ import annotations

import os

import httpx
import lancedb

DB_DIR = "data/lancedb"
TABLE = "chunks"


def _embed_batch(texts: list[str]) -> list[list[float]]:
    if os.environ.get("OPENAI_API_KEY"):
        r = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
            json={"model": "text-embedding-3-small", "input": texts},
            timeout=60,
        )
        r.raise_for_status()
        return [d["embedding"] for d in r.json()["data"]]
    if os.environ.get("VOYAGE_API_KEY"):
        r = httpx.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {os.environ['VOYAGE_API_KEY']}"},
            json={"model": "voyage-3-lite", "input": texts},
            timeout=60,
        )
        r.raise_for_status()
        return [d["embedding"] for d in r.json()["data"]]
    raise SystemExit("No OPENAI_API_KEY or VOYAGE_API_KEY set — put one in .env")


def load(chunks: list[dict]) -> int:
    """chunks: [{title, name, continuity, section, text}]. Rebuilds the table."""
    rows = []
    for i in range(0, len(chunks), 100):
        batch = chunks[i : i + 100]
        vectors = _embed_batch([c["text"] for c in batch])
        rows += [{**c, "vector": v} for c, v in zip(batch, vectors, strict=True)]
        print(f"  embedded {min(i + 100, len(chunks))}/{len(chunks)}")
    db = lancedb.connect(DB_DIR)
    db.create_table(TABLE, rows, mode="overwrite")
    return len(rows)
