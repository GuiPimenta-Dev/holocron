# ADR-0005: pgvector over LanceDB

Supersedes the LanceDB half of decision #8. LanceDB was chosen for "embedded
vector store, zero infra" — but a Postgres 17 already runs in docker-compose as
Langfuse's backing store, so the zero-infra argument bought nothing, and
Postgres+pgvector is the production vector standard the job market recognizes
(the same signal rationale that superseded Streamlit in decision #27).

The chunk index lives in a separate `holocron` database on the shared instance
(image: `pgvector/pgvector:pg17`, host port 5434): `chunks` table, HNSW index
with cosine ops, continuity filter as plain SQL. Raw `psycopg`, no ORM — the
repo's raw-driver style. Vectors serialize via their text literal + `::vector`
cast (`core.embeddings.pgvector_literal`), avoiding an adapter dependency.

Validated by a full eval run against Baseline 20260710T215754Z (same corpus
lock, same golden set, judge untouched). Rejected: keeping both stores behind a
Protocol (no repeated type-switch — ADR-0004; double maintenance for a toggle
nobody flips), a dedicated second Postgres container (isolation nobody needs).
