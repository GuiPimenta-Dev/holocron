# Holocron

Star Wars lore agent: decides at runtime between vector search and knowledge-graph
traversal, evaluated A/B/C (vector-only vs graph-only vs agent). Vocabulary lives
in CONTEXT.md, decisions in DECISIONS.md and docs/adr/ — read those before
renaming or re-architecting anything.

## Architecture

```
ingest/        scrape Wookieepedia (MediaWiki API) → cache wikitext → parse
               infoboxes → LanceDB index + Neo4j graph. Runs offline.
               Corpus pinned by corpus.lock (title, revid) — see ADR-0002.
tools.py       pure functions over Neo4j + LanceDB. No LLM, no framework imports.
agent/         LangGraph state graph (ADR-0001): routing node → tools → synthesis.
               Framework imports live here only. Traced via Langfuse callbacks.
api/           FastAPI serving the agent; POST /ask streams steps + answer via SSE.
frontend/      Next.js + React + Tailwind consuming the SSE stream (ADR-0003).
eval/          golden set (4 categories) + LLM-judge harness; datasets and runs
               registered in Langfuse, baselines saved in eval/baselines/.
```

Boundary rules (non-negotiable):
- `tools.py` functions take/return plain data, testable without any LLM. They must
  not know an agent exists.
- LangGraph/LangChain imports live in `agent/` only; FastAPI in `api/` only.
- `ingest/` and the serving side never import each other; they meet at the data
  stores on disk.
- Every chunk and every graph node carries `continuity: canon | legends`.
- Curated graph edges obey the target-type compatibility matrix in `ingest/graph.py`
  (e.g. TRAINED_BY → Character only). The uncurated edge tail is pruned only with
  eval evidence, never for aesthetics.

## Toolchain & infra

- `uv` for env + deps. `ruff` (lint+format), `pyright` (all tool signatures typed),
  `pytest`. Frontend: `npm` inside `frontend/`.
- `docker compose up`: Neo4j + Langfuse. Everything runs locally; no deploy.
- CI (GitHub Actions) runs lint + pyright + pytest only — never the eval.

## Testing doctrine

- Every function in `tools.py` and every infobox parser has a pytest with real
  fixtures (saved wikitext), no synthetic minimal inputs.
- Agent behavior is measured only by the eval harness. Never mock the LLM.
- Eval runs manually per phase via the `run-eval` skill; judge model + rubric are
  never changed in the same run as a system change.

## Process

- Nothing lands on main without a branch + PR, green CI, and a self-review
  (/code-review). Conventional commits.
- Big features (a new surface like the frontend) get a mini-PRD first; a new agent
  tool follows the `add-tool` skill instead.
- Every agent run is traced (Langfuse); eval regressions must link to the trace of
  the failing question.

## Conventions

- Everything in English: code, comments, README, golden set.
- Graph edges: SCREAMING_SNAKE from infobox keys (TRAINED_BY, MEMBER_OF). Node
  labels by type (Character, Celestialbody…) + :Entity always.
- Real-world pages ({{Top}} flags `real`/`rw*`) are never entities.
