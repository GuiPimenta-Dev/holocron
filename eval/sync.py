"""Langfuse sync: the Golden Set as a dataset, run scores attached to traces (spec #11).

History lives where the traces live: dataset items are upserted by question id,
and each graded question pushes its scores onto the Langfuse trace of the answer
that produced it. Not unit-tested (external service, no mocks — doctrine);
verified by real pushes against the local Langfuse.
"""

from __future__ import annotations

from typing import Any

from eval.golden import GoldenSet
from eval.report import PersistedRun

DATASET_NAME = "holocron-golden-set"


class LangfuseSync:
    """Client injected by the composition root; this class only maps domain -> Langfuse calls."""

    def __init__(self, client: Any):
        self._client = client

    def register_golden_set(self, golden: GoldenSet) -> int:
        """Upsert every golden question as a dataset item (id = question id)."""
        self._client.create_dataset(
            name=DATASET_NAME,
            description="Holocron Golden Set — versioned in git (eval/golden_set.json)",
        )
        for q in golden.questions:
            self._client.create_dataset_item(
                dataset_name=DATASET_NAME,
                id=q.id,
                input={"question": q.question},
                expected_output={
                    "expected_facts": list(q.expected_facts),
                    "expected_citations": list(q.expected_citations),
                    "expected_continuity": q.expected_continuity,
                },
                metadata={"category": str(q.category)},
            )
        return len(golden.questions)

    def push_scores(self, run: PersistedRun) -> int:
        """Attach citation/judge scores to each graded question's trace. Returns scores pushed."""
        pushed = 0
        for g in run.grades:
            if g.trace_id is None:
                continue
            scores: list[tuple[str, bool]] = []
            if g.passed is not None:
                scores.append(("citation-pass", g.passed))
            if g.judge_passed is not None:
                scores.append(("judge-pass", g.judge_passed))
            if g.hallucinated is not None:
                scores.append(("hallucinated", g.hallucinated))
            for name, value in scores:
                self._client.create_score(
                    name=name,
                    value=1.0 if value else 0.0,
                    trace_id=g.trace_id,
                    data_type="BOOLEAN",
                    comment=f"run {run.run_id} · {g.strategy} · {g.question_id}",
                )
                pushed += 1
        self._client.flush()
        return pushed
