"""Embed chunks into LanceDB. Provider picked by available API key."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
import lancedb

DB_DIR = "data/lancedb"
TABLE = "chunks"


def _post_with_retry(url: str, key: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST, retrying 429/5xx with Retry-After or exponential backoff.

    Free embedding tiers rate-limit by requests-per-minute; a 30k-chunk run
    must survive that instead of dying mid-way.
    """
    for attempt in range(8):
        r = httpx.post(
            url,
            headers={"Authorization": f"Bearer {key}"},
            json=payload,
            timeout=60,
        )
        if r.status_code == 429 or r.status_code >= 500:
            wait = float(r.headers.get("retry-after") or min(5 * 2**attempt, 60))
            print(f"  {r.status_code} from {url.split('/')[2]}, retrying in {wait:.0f}s")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise SystemExit(f"still rate-limited after 8 retries: {url}")


def _embed_batch(texts: list[str]) -> list[list[float]]:
    if os.environ.get("OPENAI_API_KEY"):
        data = _post_with_retry(
            "https://api.openai.com/v1/embeddings",
            os.environ["OPENAI_API_KEY"],
            {"model": "text-embedding-3-small", "input": texts},
        )
        return [d["embedding"] for d in data["data"]]
    if os.environ.get("VOYAGE_API_KEY"):
        data = _post_with_retry(
            "https://api.voyageai.com/v1/embeddings",
            os.environ["VOYAGE_API_KEY"],
            {"model": "voyage-3-lite", "input": texts},
        )
        return [d["embedding"] for d in data["data"]]
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
