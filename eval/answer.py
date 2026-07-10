"""Answer phase: run a Retrieval Strategy over the Golden Set, persist a run dir.

Answering and judging are decoupled (spec #11): every answer + citations +
Langfuse trace id is persisted per run, so a rubric change re-judges for free.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from core.domain import Citation, Continuity
from eval.golden import Category, GoldenQuestion, GoldenSet


class Strategy(Protocol):
    """A Retrieval Strategy: anything speaking the agent's event protocol."""

    def astream(self, question: str, continuity: str | None = None) -> AsyncIterator[dict[str, Any]]: ...


@dataclass(frozen=True)
class QuestionResult:
    """One strategy's answer to one Golden Set question."""

    question: GoldenQuestion
    answer: str
    citations: tuple[Citation, ...]
    trace_id: str | None

    @classmethod
    def from_events(cls, question: GoldenQuestion, events: list[dict[str, Any]]) -> QuestionResult:
        done = next((e for e in events if e["type"] == "done"), None)
        if done is None:
            raise ValueError(f"{question.id}: event stream ended without a done event")
        citations = tuple(
            Citation(
                title=c["title"],
                name=c["name"],
                continuity=Continuity(c["continuity"]),
                section=c.get("section"),
            )
            for c in done["citations"]
        )
        answer = "".join(e["text"] for e in events if e["type"] == "answer_delta")
        return cls(question=question, answer=answer, citations=citations, trace_id=done.get("trace_id"))

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.question.id,
            "category": str(self.question.category),
            "question": self.question.question,
            "answer": self.answer,
            "citations": [c.as_dict() for c in self.citations],
            "trace_id": self.trace_id,
        }


class RunWriter:
    """Owns one run directory: `<runs_root>/<run_id>/<strategy>/<question_id>.json`.

    The manifest (run.json) lands only on finish() — its presence marks a
    completed run, so an interrupted run can never be partially reported.
    """

    def __init__(self, runs_root: Path, run_id: str, strategy: str, corpus_lock_sha256: str):
        self._dir = runs_root / run_id
        self._run_id = run_id
        self._strategy = strategy
        self._corpus_lock_sha256 = corpus_lock_sha256
        self._written: list[str] = []

    def write(self, result: QuestionResult) -> Path:
        strategy_dir = self._dir / self._strategy
        strategy_dir.mkdir(parents=True, exist_ok=True)
        path = strategy_dir / f"{result.question.id}.json"
        path.write_text(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
        self._written.append(result.question.id)
        return path

    def finish(self, category: Category | None) -> Path:
        manifest = {
            "run_id": self._run_id,
            "strategies": [self._strategy],
            "category": str(category) if category else None,
            "corpus_lock_sha256": self._corpus_lock_sha256,
            "questions": self._written,
        }
        (self._dir / "run.json").write_text(json.dumps(manifest, indent=2))
        return self._dir


class AnswerRunner:
    """Drives the strategy question-by-question, streaming progress to stdout."""

    def __init__(self, strategy: Strategy, writer: RunWriter):
        self._strategy = strategy
        self._writer = writer

    async def run(self, golden: GoldenSet, category: Category | None) -> Path:
        questions = (golden.filter(category) if category else golden).questions
        for i, q in enumerate(questions, 1):
            print(f"[{i}/{len(questions)}] {q.id}", flush=True)
            events = [ev async for ev in self._strategy.astream(q.question)]
            result = QuestionResult.from_events(q, events)
            self._writer.write(result)
            print(f"    citations={len(result.citations)} trace={result.trace_id}")
        return self._writer.finish(category)
