---
name: run-eval
description: Run the A/B/C eval harness (vector-only vs graph-only vs agent), compare against the saved baseline, report regressions per category, and update the README results table. Use when the user asks to run the eval, check quality after a change, or update eval results.
---

# run-eval

Never report eval numbers without comparing to the previous baseline. A score
means nothing alone; the delta is the result.

## Steps

1. **Preflight**: confirm indices exist (LanceDB dir + Neo4j reachable), the
   golden set loads, and the `claude` CLI is logged in (the Judge runs through
   it). If any fails, stop and report — don't burn API calls on a broken setup.
2. **Run**: `uv run python -m eval answer` (all three Retrieval Strategies:
   vector-only, graph-only, agent). One strategy: `--strategy X`; one category:
   `--category Y`. Then `uv run python -m eval judge` (free; existing verdicts
   kept — delete `*.verdict.json` to re-judge). Then `uv run python -m eval push`
   to register the Golden Set dataset and attach the run's scores in Langfuse.
3. **Compare**: `uv run python -m eval report` — reads the latest run and the
   latest Baseline from `eval/baselines/`, renders citation-check + Judge tables
   (rows = 4 categories: single-hop, multi-hop, continuity-conflict,
   unanswerable; columns = the three strategies; cells = pass rate with delta
   vs Baseline) and persists `report.md` into the run dir.
4. **Interpret** — in this order:
   - Any category regressed >2 points? Name it first, with 2–3 example questions
     that flipped from pass to fail (read them from the run output).
   - Unanswerable category dropped = hallucination increase. Flag loudly.
   - Only then mention improvements.
5. **Persist**: on user confirmation that this run is the new reference, promote
   it — `uv run python -m eval promote <run-id>` (copies it into `eval/baselines/`,
   which is versioned; commit it) — and update the results table in README.md.

## Rules

- Judge model and rubric are pinned in `eval/judge.py` — never change them in
  the same run as a system change (you'd be moving the ruler with the object).
- Flipped questions get quoted verbatim in the report; aggregate scores hide
  what actually broke.
- A run that errors mid-way is never partially reported (no manifest = no
  report). Don't re-pay for its finished answers: complete it with
  `uv run python -m eval answer --resume <run-id>`.
