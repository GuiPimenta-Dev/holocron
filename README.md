# Holocron

GraphRAG over Star Wars lore. A LangGraph agent routes each question to
vector search (pgvector), knowledge-graph traversal (Neo4j), or both — and
an eval compares the three strategies on the same question set.

![The chat streams the answer while the knowledge-graph traversal renders as a live constellation](docs/assets/holocron-demo.gif)

*Three runs, four questions, different strategies each time. "How is Boba
Fett connected to the Jedi Order?" routes to graph traversal and renders
the path it walked; "Describe the Nautolan species" routes to vector
search and shows retrieved chunks as satellites. "How is Leia Organa
related to Darth Vader?" has the agent retrying name variants until the
graph confirms the PARENT edge. "Who did Count Dooku train?" comes back as
two separate constellations — canon in blue, Legends in amber — one answer
per continuity.*

## Why two retrieval systems

Vector search handles descriptive questions well: embed the question,
retrieve similar text, synthesize. Two kinds of questions expose its
limits, and Star Wars lore has plenty of both:

- **Relational questions.** "How is X connected to Y?" is answered by a
  path through entities, not by any single passage of text.
- **Conflicting continuities.** Canon and Legends often disagree.
  Similarity search retrieves both and tends to blend them into one
  answer.

Holocron builds both systems over the same ~5,900 Wookieepedia pages:

| | Vector search (RAG) | Graph traversal (GraphRAG) |
|---|---|---|
| Store | pgvector — embedded chunks | Neo4j — entities and typed edges |
| Strength | descriptions, narrative | relations, multi-hop paths |
| Agent tool | `search_chunks` | `get_entity`, `get_relations`, `path_between` |

The agent is a LangGraph state graph: a routing step reads the question
and picks tools, the tools query the stores, and a synthesis step answers
only from what they returned. Every chunk, node and edge carries a
`canon | legends` tag, so conflicting continuities are reported side by
side rather than merged.

## Eval: RAG vs GraphRAG vs agent

A 30-question golden set, split into four categories, is answered three
ways — vector-only, graph-only, and the agent — and graded by an LLM judge
against expected facts:

| Category | vector-only | graph-only | agent |
|---|---|---|---|
| single-hop | 100% | 100% | 100% |
| multi-hop | 87% | **100%** | 87% |
| continuity-conflict | 85% | **100%** | **100%** |
| unanswerable (refusal) | 100% | 100% | 100% |

Continuity-conflict is where plain RAG breaks: before prompt tuning,
vector-only passed 28% of those questions, merging canon and Legends into
single answers. With continuity encoded as structure, graph traversal
passes all of them. The vector-only misses that remain are questions whose
answers exist only as graph edges — retrieval failures, not prompting
failures.

## The knowledge graph

Wookieepedia infoboxes are structured data embedded in wikitext. Ingestion
parses them into typed entities and edges:

```
(Boba Fett:Character)-[:TRAINED_BY]->(Aurra Sing:Character)
(Aurra Sing:Character)-[:MEMBER_OF]->(Jedi Order:Organization)
```

This is what makes relational questions tractable: "How is Boba Fett
connected to the Jedi Order?" becomes a short path query instead of a
similarity search over text that never states the connection.

## Tracing

![Langfuse: dashboard, trace list, span tree with the LangGraph state graph, tool spans, and the golden-set dataset](docs/assets/langfuse-tour.gif)

*Every run — from the UI, the API or the eval — is traced in a local
Langfuse: the span tree next to the rendered LangGraph state graph, the
exact query each tool issued, token counts and latency per step, and the
golden set as a versioned dataset with judge scores attached to traces.*

## Running the project

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/), an
`ANTHROPIC_API_KEY` and an embedding key (OpenAI or Voyage).

```sh
docker compose up -d --wait
cp .env.example .env          # add your API keys; everything else works as-is
uv sync
```

The compose file brings up the full stack, pre-provisioned:

| Service | Role |
|---|---|
| Neo4j 5 | knowledge graph |
| Postgres 17 + pgvector | vector index (also Langfuse's DB) |
| Langfuse v3 (web + worker) | tracing and eval scores |
| ClickHouse, MinIO, Redis | Langfuse's internal storage |

Build the knowledge base — the corpus is pinned to fixed page revisions,
so the result is reproducible:

```sh
uv run python -m ingest rebuild   # fetch the pinned Wookieepedia pages (~15 min)
uv run python -m ingest parse     # wikitext -> entities + chunks
uv run python -m ingest graph     # entities -> Neo4j
uv run python -m ingest embed     # chunks -> pgvector
```

Serve the agent and the UI:

```sh
uv run python -m api                        # FastAPI + SSE on :8000
cd frontend && npm install && npm run dev   # Next.js UI on :3000
```

Or ask from the terminal:

```sh
curl -N localhost:8000/ask -X POST -H 'content-type: application/json' \
     -d '{"question": "What species is Kit Fisto?"}'
```

Local consoles: Langfuse at <http://localhost:3001>
(`dev@holocron.local` / `holocron123`), Neo4j browser at
<http://localhost:7474> (`neo4j` / `holocron123`).

## Running the eval

```sh
uv run python -m eval answer   # three strategies over the golden set
uv run python -m eval judge    # LLM judge (Opus via the local claude CLI)
uv run python -m eval report   # scores vs the current baseline
```

The judge model is stronger than the system under test and is never
changed in the same run as a system change; every score links back to its
trace.

## Development

```sh
uv run ruff check . && uv run pyright && uv run pytest
```

## Attribution

Lore content is sourced from [Wookieepedia](https://starwars.fandom.com/)
and is available under [CC-BY-SA](https://www.fandom.com/licensing).
