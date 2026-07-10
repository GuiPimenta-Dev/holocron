# Holocron

Star Wars lore agent: decides at runtime between vector search and knowledge-graph
traversal, evaluated A/B/C (vector-only vs graph-only vs agent). Vocabulary lives
in CONTEXT.md, decisions in DECISIONS.md and docs/adr/ — read those before
renaming or re-architecting anything.

## Architecture

```
core/          neutral leaf both sides may import: domain types (domain.py) and
               the embedding providers (embeddings.py). No framework, no agent.
ingest/        scrape Wookieepedia (MediaWiki API) → cache wikitext → parse
               infoboxes → LanceDB index + Neo4j graph. Runs offline.
               Corpus pinned by corpus.lock (title, revid) — see ADR-0002.
retrieval/     serving-side data access: KnowledgeGraph (Neo4j) and VectorIndex
               (LanceDB). Pure classes over plain data. No LLM, no framework.
agent/         LangGraph state graph (ADR-0001): routing node → tools → synthesis.
               Framework imports live here only. Traced via Langfuse callbacks.
api/           FastAPI serving the agent; POST /ask streams steps + answer via SSE.
               api/__main__.py is the composition root — the only place that
               constructs resources.
frontend/      Next.js + React + Tailwind consuming the SSE stream (ADR-0003).
eval/          golden set (4 categories) + LLM-judge harness; datasets and runs
               registered in Langfuse, baselines saved in eval/baselines/.
```

Boundary rules (non-negotiable):
- `core/` is the only shared dependency; it imports nothing from the project.
- `retrieval/` classes take/return domain types from `core/` (dataclasses +
  primitives), testable without any LLM. They must not know an agent exists.
- LangGraph/LangChain imports live in `agent/` only; FastAPI in `api/` only.
- `ingest/` and the serving side (`retrieval/`, `agent/`, `api/`) never import
  each other; they meet at `core/` and the data stores on disk.
- Every chunk and every graph node carries `continuity: canon | legends`.
- Curated graph edges obey the target-type compatibility matrix in `ingest/graph.py`
  (e.g. TRAINED_BY → Character only). The uncurated edge tail is pruned only with
  eval evidence, never for aesthetics.

## Code style (ADR-0004)

- Public surface is classes and methods only; loose functions may exist private
  (`_name`), pure, inside the module that uses them.
- Whoever owns a resource or configuration is a class. Resources are constructed
  once in the composition root (`api/__main__.py`, eval harness, CLI entrypoints)
  and injected via constructor — required params, no hidden defaults, no class
  constructs its own resource dependency. Config is read from the environment at
  the composition root only.
- Implementation inheritance is forbidden. Polymorphism goes through
  `typing.Protocol`; the only carve-out is custom exceptions extending
  `Exception`. Prefer composition (has-a) always.
- Polymorphism only where the same type-switch repeats in ≥2 places (today:
  `EmbeddingProvider`). Guards and validations stay as ifs.
- Domain vocabulary is typed: frozen dataclasses + `Continuity` enum in
  `core/domain.py`, matching CONTEXT.md terms. `dict`/JSON exists only at the
  edges (SSE, LangChain binding, disk) — convert once, at the edge.
- Docstrings come in two classes: LLM-facing (retrieval tool methods — mandatory,
  long, with an example call; they are prompt engineering, never trim) and
  internal (one line when the name isn't enough, none when it is).
- Max ~4 params per signature; params that travel together become a dataclass.

## Toolchain & infra

- `uv` for env + deps. `ruff` (lint+format), `pyright` (all tool signatures typed),
  `pytest`. Frontend: `npm` inside `frontend/`.
- `docker compose up`: Neo4j + Langfuse. Everything runs locally; no deploy.
- CI (GitHub Actions) runs lint + pyright + pytest only — never the eval.

## Testing doctrine

- Every retrieval method and every infobox parser has a pytest with real
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
