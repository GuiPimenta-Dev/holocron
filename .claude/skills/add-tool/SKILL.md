---
name: add-tool
description: Procedure for adding a new tool to the agent — typed signature, LLM-facing docstring, pytest with real fixtures, registration in agent.py, and a golden-set question covering it. Use whenever a new agent tool/function is added or an existing tool signature changes.
---

# add-tool

A tool is the agent's API. It never lands without a test and eval coverage.

## Steps

1. **Justify**: can an existing tool answer this with different arguments? If
   yes, stop — extend or document the existing one instead.
2. **Write the function** in `tools.py`:
   - Fully typed signature, plain-data params and return (str/int/list/dict —
     no ORM objects, no framework types).
   - Docstring written FOR THE LLM: what it does, when to use it vs the other
     tools, one concrete example call. This docstring is prompt engineering —
     the agent chooses tools by reading it.
   - Must run without any LLM in the process.
3. **Test it**: pytest in `tests/` with real fixtures (actual graph data /
   saved wikitext), covering the happy path and the not-found case. Empty
   results return empty structures, never raise.
4. **Register** in `agent.py`. Check the system prompt: does it enumerate tools
   or describe strategy? Update if the new tool changes when the agent should
   pick graph vs vector.
5. **Cover in eval**: add at least one golden-set question that is best answered
   through this tool, in the appropriate category.
6. **Verify**: `uv run pytest` green, then one manual smoke question through the
   agent (`uv run python -m agent` or the app) confirming the tool actually gets
   called — check the tool-call log.

## Rules

- Read-only. Tools never mutate the graph or the index.
- `run_cypher` escape hatch stays read-only (reject non-MATCH queries).
- If the tool count exceeds ~6, stop and consolidate — too many similar tools
  degrades the agent's routing more than it helps.
