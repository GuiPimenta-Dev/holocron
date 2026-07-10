# ADR-0004: OO style — composition, protocols and domain types

**Status:** accepted (2026-07-10). Grilling session 4, DECISIONS.md.

## Context

Phase 2 shipped correct but stylistically mixed code: module-level singletons
hiding state (`tools.py:_driver`, `wiki.py:_client`), public loose functions,
`dict[str, Any]` traveling through every layer with magic keys, `continuity`
as a bare string revalidated with ifs in three places, and one provider
type-switch duplicated across ingest and serving. The owner's explicit
preference is object-oriented code: composition over inheritance,
polymorphism, explicit dependencies.

## Decision

The rule set lives in CLAUDE.md → "Code style". The load-bearing choices:

- **Public = classes/methods; private pure helpers may stay functions.**
  Resource owners become classes (`KnowledgeGraph`, `VectorIndex`,
  `WikiClient`, `PageParser`, `GraphLoader`); hidden module state becomes
  instance state.
- **Strict constructor injection with a composition root.** Only
  `api/__main__.py` (and future eval/CLI entrypoints) constructs resources and
  reads the environment. Guarantees the phase-4 eval can assemble
  vector-only/graph-only/agent strategies from the same objects.
- **No implementation inheritance; polymorphism via `typing.Protocol`.**
  Chosen over ABCs after weighing both: Protocol keeps implementations and
  test fakes decoupled from the interface (the api layer's `Agent` protocol
  already works this way) and is checked statically by pyright. Carve-out:
  custom exceptions.
- **Exactly one polymorphism point today: `EmbeddingProvider`** (OpenAI /
  Voyage) in `core/embeddings.py` — the only type-switch that repeated (ingest
  + query paths), and centralizing it removes a latent index/query dimension
  mismatch. Explicitly rejected: polymorphic Tool objects (LangChain already
  is that), polymorphic retrieval strategies (phase-4 design), and rewriting
  validation ifs.
- **Domain types over dicts:** `core/domain.py` holds frozen dataclasses named
  after CONTEXT.md vocabulary (`Continuity`, `EntityRecord`, `Relation`,
  `Chunk`, `Citation`...). Dicts/JSON exist only at the edges. `run_cypher`
  keeps raw rows — its result shape is arbitrary by design (escape hatch).
- **Folder repagination:** `core/` (neutral shared leaf) and `retrieval/`
  (replaces root `tools.py`; named after the glossary term Retrieval
  Strategy). `ingest/`, `agent/`, `api/`, `tests/` keep their homes.
- **LLM-facing docstrings are exempt from brevity rules** — the retrieval tool
  docstrings are prompt engineering the agent routes by (add-tool skill).

## Consequences

- Readability in the owner's dialect; pyright catches key/shape errors that
  dicts deferred to runtime.
- The refactor is behavior-preserving by definition: same SSE contract, same
  queries, same corpus.lock; the full test suite and a live /ask smoke gate it.
- Python-idiom purists may find strict OO unusual for a script-sized repo;
  this is a deliberate owner preference, recorded here so future sessions
  don't "helpfully" revert it.
- Rejected alternative: full clean architecture (application/infrastructure
  layers, repositories, use-cases) — overengineering at this scale.
