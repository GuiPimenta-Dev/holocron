# Holocron

Star Wars lore agent that decides at runtime between vector search and
knowledge-graph traversal, with a comparative eval (vector-only vs graph-only vs
agent) as the project's centerpiece. Vocabulary in [CONTEXT.md](CONTEXT.md),
decisions in [DECISIONS.md](DECISIONS.md) and [docs/adr/](docs/adr/).

## Setup

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/).

```sh
docker compose up -d --wait   # Neo4j + Langfuse (one command, no UI clicking)
cp .env.example .env          # then add your ANTHROPIC_API_KEY (+ an embedding key)
uv sync
```

The Langfuse project and API keys are pre-provisioned by docker-compose — the
values in `.env.example` work as-is. UI: <http://localhost:3001>
(`dev@holocron.local` / `holocron123`). Neo4j browser: <http://localhost:7474>
(`neo4j` / `holocron123`).

## Build the knowledge base

The corpus is pinned by [`corpus.lock`](corpus.lock) (page title → revision id,
ADR-0002), so the raw cache is reproducible from the repository:

```sh
uv run python -m ingest rebuild   # fetch every page at its pinned revision (~15 min)
uv run python -m ingest parse     # cache -> entities.jsonl + chunks.jsonl (~2 min)
uv run python -m ingest graph     # entities -> Neo4j (~1 min)
uv run python -m ingest embed     # chunks -> LanceDB (~10 min, needs an embedding key)
```

Expected costs: the embed run is one-time ~US$0.20 on OpenAI
(`text-embedding-3-small`) or free within Voyage's quota (`voyage-3-lite`,
requires a payment method on file for usable rate limits). Questions cost a
few cents each (Claude Sonnet + one query embedding).

## Ask a question

```sh
uv run python -m agent.smoke      # one traced LLM call — check the Langfuse UI
uv run python -m api              # serve the agent on :8000
curl -N localhost:8000/ask -X POST -H 'content-type: application/json' \
     -d '{"question": "What species is Kit Fisto?"}'
```

`POST /ask` streams SSE events (`tool_call`, `tool_result`, `answer_delta`,
`done` with continuity-tagged citations, `error`); every run is traced in
Langfuse.

## Development

```sh
uv run ruff check . && uv run pyright && uv run pytest
```

Tool tests run against the real Neo4j (they skip if it's down, and seed an
empty graph from `tests/fixtures/`). Agent behavior is measured only by the
eval harness — never mocked.

## Attribution

Lore content is sourced from [Wookieepedia](https://starwars.fandom.com/) and
is available under
[CC-BY-SA](https://www.fandom.com/licensing).
