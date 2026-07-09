---
name: run-eval
description: Run the A/B/C eval harness (vector-only vs graph-only vs agent), compare against the saved baseline, report regressions per category, and update the README results table. Use when the user asks to run the eval, check quality after a change, or update eval results.
---

# run-eval

Never report eval numbers without comparing to the previous baseline. A score
means nothing alone; the delta is the result.

## Steps

1. **Preflight**: confirm indices exist (LanceDB dir + Neo4j reachable) and the
   golden set loads. If either fails, stop and report — don't burn API calls on
   a broken setup.
2. **Run**: `uv run python -m eval.harness` (all three configs: vector-only,
   graph-only, agent). If the user asked for one config only, pass it through.
3. **Compare**: load the latest baseline from `eval/baselines/`. Produce a table:
   rows = 4 categories (single-hop, multi-hop, canon-vs-legends, unanswerable),
   columns = the three configs, cells = score with delta vs baseline.
4. **Interpret** — in this order:
   - Any category regressed >2 points? Name it first, with 2–3 example questions
     that flipped from pass to fail (read them from the run output).
   - Unanswerable category dropped = hallucination increase. Flag loudly.
   - Only then mention improvements.
5. **Persist**: on user confirmation that this run is the new reference, save it
   to `eval/baselines/` (timestamped) and update the results table in README.md.

## Rules

- Judge model and rubric are fixed in `eval/` config — never change them in the
  same run as a system change (you'd be moving the ruler with the object).
- Flipped questions get quoted verbatim in the report; aggregate scores hide
  what actually broke.
- A run that errors mid-way is discarded, not partially reported.
