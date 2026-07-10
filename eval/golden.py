"""The Golden Set: the versioned question suite in four categories (CONTEXT.md).

Two eval runs are comparable question-by-question only under the same golden
set file and the same corpus.lock (ADR-0002).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class Category(StrEnum):
    SINGLE_HOP = "single-hop"
    MULTI_HOP = "multi-hop"
    CONTINUITY_CONFLICT = "continuity-conflict"
    UNANSWERABLE = "unanswerable"


@dataclass(frozen=True)
class GoldenQuestion:
    id: str
    category: Category
    question: str
    expected_facts: tuple[str, ...]  # facts the answer must state
    expected_citations: tuple[str, ...]  # page titles the answer must cite
    expected_continuity: str  # how the answer must handle continuity


class GoldenSet:
    """Loads, validates, and filters the versioned golden set file."""

    def __init__(self, questions: tuple[GoldenQuestion, ...]):
        self._questions = questions

    @property
    def questions(self) -> tuple[GoldenQuestion, ...]:
        return self._questions

    @classmethod
    def load(cls, path: Path) -> GoldenSet:
        questions = tuple(_parse_entry(e) for e in json.loads(path.read_text()))
        ids = [q.id for q in questions]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"{path}: duplicate question ids {sorted(dupes)}")
        return cls(questions)

    def filter(self, category: Category) -> GoldenSet:
        return GoldenSet(tuple(q for q in self._questions if q.category is category))


_FIELDS = ("id", "category", "question", "expected_facts", "expected_citations", "expected_continuity")


def _parse_entry(entry: dict[str, Any]) -> GoldenQuestion:
    missing = [f for f in _FIELDS if f not in entry]
    if missing:
        raise ValueError(f"golden entry {entry.get('id', '?')!r}: missing fields {missing}")
    try:
        category = Category(entry["category"])
    except ValueError:
        raise ValueError(f"golden entry {entry['id']!r}: unknown category {entry['category']!r}") from None
    question = GoldenQuestion(
        id=entry["id"],
        category=category,
        question=entry["question"],
        expected_facts=tuple(entry["expected_facts"]),
        expected_citations=tuple(entry["expected_citations"]),
        expected_continuity=entry["expected_continuity"],
    )
    if not question.question.strip():
        raise ValueError(f"golden entry {question.id!r}: empty question")
    if question.category is Category.UNANSWERABLE:
        if question.expected_facts or question.expected_citations:
            raise ValueError(f"golden entry {question.id!r}: unanswerable questions expect refusal, not facts")
    elif not (question.expected_facts and question.expected_citations):
        raise ValueError(f"golden entry {question.id!r}: expected_facts and expected_citations are required")
    return question
