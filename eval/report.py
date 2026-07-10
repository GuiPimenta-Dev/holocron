"""Report phase: the deterministic (free) half of the grade.

Reads a persisted run, checks expected citation titles + continuity consistency,
aggregates per category x strategy, and renders the table. Scores are only ever
reported as deltas against a Baseline (run-eval doctrine); without one the table
is explicitly marked absolute. Unanswerable questions are not citation-graded —
refusal is the Judge's call (#15).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from core.domain import Continuity
from eval.golden import Category, GoldenSet


@dataclass(frozen=True)
class QuestionGrade:
    """One strategy's deterministic grade on one question. passed=None: not citation-graded."""

    question_id: str
    question: str
    category: Category
    strategy: str
    passed: bool | None
    missing: tuple[str, ...]  # expected titles the answer did not cite

    def flipped(self) -> QuestionGrade:
        """The same grade with the opposite outcome (test/fixture helper)."""
        return replace(self, passed=not self.passed if self.passed is not None else None)


@dataclass(frozen=True)
class Flip:
    """A question whose pass/fail changed against the Baseline."""

    strategy: str
    question_id: str
    question: str
    direction: str  # "regressed" | "fixed"


class CitationChecker:
    """Expected titles ∩ cited titles, with continuity-consistency (spec #11 stage 1).

    A citation matches only if its title is expected AND its continuity tag is
    consistent with the title (a `/Legends` page must carry `legends`).
    """

    def __init__(self, golden: GoldenSet):
        self._by_id = {q.id: q for q in golden.questions}

    def grade(self, strategy: str, artifact: dict[str, Any]) -> QuestionGrade:
        question = self._by_id.get(artifact["id"])
        if question is None:
            raise ValueError(f"artifact {artifact['id']!r} is not in the golden set")
        if question.category is Category.UNANSWERABLE:
            return QuestionGrade(question.id, question.question, question.category, strategy, None, ())
        cited = {c["title"] for c in artifact["citations"] if _consistent(c)}
        matched = set(question.expected_citations) & cited
        missing = tuple(t for t in question.expected_citations if t not in cited)
        return QuestionGrade(question.id, question.question, question.category, strategy, bool(matched), missing)


def _consistent(citation: dict[str, Any]) -> bool:
    expected = Continuity.LEGENDS if citation["title"].endswith("/Legends") else Continuity.CANON
    return Continuity.parse(citation["continuity"]) is expected


class PersistedRun:
    """A completed run dir, loaded and graded. Incomplete runs are a hard error."""

    def __init__(
        self, run_id: str, corpus_lock_sha256: str, strategies: tuple[str, ...], grades: tuple[QuestionGrade, ...]
    ):
        self.run_id = run_id
        self.corpus_lock_sha256 = corpus_lock_sha256
        self.strategies = strategies
        self.grades = grades

    @classmethod
    def load(cls, run_dir: Path, golden: GoldenSet) -> PersistedRun:
        manifest_path = run_dir / "run.json"
        if not manifest_path.exists():
            raise ValueError(f"{run_dir}: no manifest — the run is incomplete and cannot be reported")
        manifest = json.loads(manifest_path.read_text())
        checker = CitationChecker(golden)
        grades = []
        for strategy in manifest["strategies"]:
            for qid in manifest["questions"]:
                path = run_dir / strategy / f"{qid}.json"
                if not path.exists():
                    raise ValueError(f"{run_dir}: missing artifact {strategy}/{qid}.json — run is incomplete")
                grades.append(checker.grade(strategy, json.loads(path.read_text())))
        return cls(
            run_id=manifest["run_id"],
            corpus_lock_sha256=manifest["corpus_lock_sha256"],
            strategies=tuple(manifest["strategies"]),
            grades=tuple(grades),
        )


class ScoreBoard:
    """Per-category x per-strategy aggregation over graded questions."""

    def __init__(self, grades: list[QuestionGrade] | tuple[QuestionGrade, ...]):
        self._grades = {(g.strategy, g.question_id): g for g in grades}

    def cell(self, category: Category, strategy: str) -> tuple[int, int]:
        """(passed, graded) for one cell; ungraded questions (passed=None) are excluded."""
        graded = [
            g
            for g in self._grades.values()
            if g.category is category and g.strategy == strategy and g.passed is not None
        ]
        return sum(g.passed is True for g in graded), len(graded)

    def flips_against(self, baseline: ScoreBoard) -> list[Flip]:
        """Questions whose outcome changed vs the Baseline — regressions first."""
        flips = []
        for key, grade in self._grades.items():
            base = baseline._grades.get(key)
            if base is None or grade.passed is None or base.passed is None or grade.passed == base.passed:
                continue
            direction = "regressed" if base.passed and not grade.passed else "fixed"
            flips.append(Flip(grade.strategy, grade.question_id, grade.question, direction))
        return sorted(flips, key=lambda f: (f.direction != "regressed", f.strategy, f.question_id))


# Presentation order of the A/B/C table columns; unknown strategies are appended.
_STRATEGY_ORDER = ("vector-only", "graph-only", "agent")


class ReportRenderer:
    """Markdown table (readable in terminal and pasteable into the README)."""

    def render(self, run: PersistedRun, baseline: PersistedRun | None) -> str:
        board = ScoreBoard(list(run.grades))
        comparable = baseline is not None and baseline.corpus_lock_sha256 == run.corpus_lock_sha256
        base_board = ScoreBoard(list(baseline.grades)) if baseline and comparable else None

        lines = [f"# Eval report — run {run.run_id}", ""]
        if baseline is None:
            lines.append("Baseline: none — **absolute numbers**, comparable only to future runs.")
        elif not comparable:
            lines.append(
                f"Baseline {baseline.run_id} is **incomparable** (different corpus.lock, ADR-0002) — "
                "absolute numbers shown, no deltas."
            )
        else:
            lines.append(f"Baseline: {baseline.run_id} — cells show pass rate and delta.")
        lines.append("")

        strategies = [s for s in _STRATEGY_ORDER if s in run.strategies]
        strategies += [s for s in run.strategies if s not in strategies]
        lines.append("| Category | " + " | ".join(strategies) + " |")
        lines.append("|---" * (len(strategies) + 1) + "|")
        rows = 0
        for category in Category:
            cells = [self._cell(board, base_board, category, s) for s in strategies]
            if all(c == "–" for c in cells):
                continue
            lines.append(f"| {category} | " + " | ".join(cells) + " |")
            rows += 1
        if rows == 0:
            lines.append("")
            lines.append("No citation-gradable questions in this run — unanswerable questions are scored by the Judge.")

        if base_board is not None:
            flips = board.flips_against(base_board)
            if flips:
                lines += ["", "## Flipped vs Baseline", ""]
                lines += [f'- **{f.direction}** {f.strategy}/{f.question_id}: "{f.question}"' for f in flips]
        return "\n".join(lines) + "\n"

    def _cell(self, board: ScoreBoard, base: ScoreBoard | None, category: Category, strategy: str) -> str:
        passed, graded = board.cell(category, strategy)
        if graded == 0:
            return "–"
        text = f"{100 * passed // graded}% ({passed}/{graded})"
        if base is not None:
            base_passed, base_graded = base.cell(category, strategy)
            if base_graded:
                delta = 100 * passed // graded - 100 * base_passed // base_graded
                text += f" ({delta:+d}pp)"
        return text
