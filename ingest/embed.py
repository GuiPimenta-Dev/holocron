"""Embed chunks into pgvector using an injected provider (core/embeddings.py, ADR-0005)."""

from __future__ import annotations

import psycopg
from psycopg import sql

from core.embeddings import EmbeddingProvider, pgvector_literal

BATCH = 100


class IndexBuilder:
    """Rebuilds the chunk table from scratch with one embedding provider.

    Owns the holocron database's schema: ensures the database and the vector
    extension exist, then DROP/CREATEs the table — the index is only ever built
    whole (mirrors the previous overwrite semantics). The vector dimension is
    fixed at build time by the provider's output.
    """

    def __init__(self, embeddings: EmbeddingProvider, dsn: str):
        self._embeddings = embeddings
        self._dsn = dsn

    def build(self, chunks: list[dict], table: str = "chunks") -> int:
        """chunks: [{title, name, continuity, section, text}]. Rebuilds the table."""
        self._ensure_database()
        rows: list[tuple] = []
        dim = 0
        for i in range(0, len(chunks), BATCH):
            batch = chunks[i : i + BATCH]
            vectors = self._embeddings.embed([c["text"] for c in batch])
            dim = len(vectors[0])
            rows += [
                (c["title"], c["name"], c["section"], c["continuity"], c["text"], pgvector_literal(v))
                for c, v in zip(batch, vectors, strict=True)
            ]
            print(f"  embedded {min(i + BATCH, len(chunks))}/{len(chunks)}")
        t = sql.Identifier(table)
        with psycopg.connect(self._dsn) as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(t))
            conn.execute(
                sql.SQL(
                    "CREATE TABLE {} (title text, name text, section text, "
                    "continuity text, text text, embedding vector({}))"
                ).format(t, sql.Literal(dim))
            )
            with conn.cursor() as cur:
                cur.executemany(
                    sql.SQL(
                        "INSERT INTO {} (title, name, section, continuity, text, embedding) "
                        "VALUES (%s, %s, %s, %s, %s, %s::vector)"
                    ).format(t),
                    rows,
                )
            conn.execute(sql.SQL("CREATE INDEX ON {} USING hnsw (embedding vector_cosine_ops)").format(t))
        return len(rows)

    def _ensure_database(self) -> None:
        """CREATE DATABASE can't run inside a transaction and needs the admin db."""
        admin_dsn, _, dbname = self._dsn.rpartition("/")
        with psycopg.connect(f"{admin_dsn}/postgres", autocommit=True) as conn:
            exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", [dbname]).fetchone()
            if not exists:
                conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
