"""Embedding providers — the project's single polymorphism point (ADR-0004).

Both sides use this: ingest embeds the corpus, retrieval embeds queries. One
provider choice for both kills the latent index/query dimension mismatch.
"""

from __future__ import annotations

import time
from typing import Any, Protocol

import httpx


class EmbeddingProvider(Protocol):
    model: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbeddings:
    model = "text-embedding-3-small"

    def __init__(self, api_key: str, retries: int = 2):
        self._api_key = api_key
        self._retries = retries

    def embed(self, texts: list[str]) -> list[list[float]]:
        data = _post_with_retry(
            "https://api.openai.com/v1/embeddings",
            self._api_key,
            {"model": self.model, "input": texts},
            self._retries,
        )
        return [d["embedding"] for d in data["data"]]


class VoyageEmbeddings:
    model = "voyage-3-lite"

    def __init__(self, api_key: str, retries: int = 2):
        self._api_key = api_key
        self._retries = retries

    def embed(self, texts: list[str]) -> list[list[float]]:
        data = _post_with_retry(
            "https://api.voyageai.com/v1/embeddings",
            self._api_key,
            {"model": self.model, "input": texts},
            self._retries,
        )
        return [d["embedding"] for d in data["data"]]


def provider_from_env(env: dict[str, str], retries: int = 2) -> EmbeddingProvider:
    """Pick the provider from the composition root's environment. OpenAI wins ties.

    `retries` tunes the 429/5xx backoff per caller: batch ingestion wants many
    (a 30k-chunk run must survive free-tier rate limits), the interactive query
    path wants few (a hung question is worse than a failed one).
    """
    if key := env.get("OPENAI_API_KEY"):
        return OpenAIEmbeddings(key, retries)
    if key := env.get("VOYAGE_API_KEY"):
        return VoyageEmbeddings(key, retries)
    raise RuntimeError("no OPENAI_API_KEY or VOYAGE_API_KEY set — see .env.example")


def _post_with_retry(url: str, api_key: str, payload: dict[str, Any], retries: int) -> dict[str, Any]:
    for attempt in range(retries + 1):
        r = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=60,
        )
        if (r.status_code == 429 or r.status_code >= 500) and attempt < retries:
            wait = float(r.headers.get("retry-after") or min(5 * 2**attempt, 60))
            print(f"  {r.status_code} from {url.split('/')[2]}, retrying in {wait:.0f}s")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"unreachable: {url}")
