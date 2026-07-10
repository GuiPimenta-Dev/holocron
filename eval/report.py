"""Report phase: the deterministic (free) half of the grade.

Reads a persisted run, checks expected citation titles + continuity consistency,
aggregates per category x strategy, and renders the table. Scores are only ever
reported as deltas against a Baseline (run-eval doctrine); without one the table
is explicitly marked absolute. Unanswerable questions are not citation-graded —
refusal is the Judge's call (#15).
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from core.domain import Citation, Continuity
from eval.golden import Category, GoldenSet


@dataclass(frozen=True)
class AnswerRecord:
    """One persisted answer, typed at the disk edge (ADR-0004: dicts only at edges)."""

    question_id: str
    answer: str
    citations: tuple[Citation, ...]
    trace_id: str | None = None

    @classmethod
    def from_json(cls, artifact: dict[str, Any]) -> AnswerRecord:
        citations = tuple(
            Citation(
                title=c["title"],
                name=c["name"],
                continuity=Continuity(c["continuity"]),
                section=c.get("section"),
            )
            for c in artifact["citations"]
        )
        return cls(
            question_id=artifact["id"],
            answer=artifact["answer"],
            citations=citations,
            trace_id=artifact.get("trace_id"),
        )


@dataclass(frozen=True)
class QuestionGrade:
    """One strategy's grades on one question: deterministic + judge halves.

    passed=None: not citation-graded (unanswerable). judge_passed=None: not judged yet.
    """

    question_id: str
    question: str
    category: Category
    strategy: str
    passed: bool | None
    missing: tuple[str, ...]  # expected titles the answer did not cite
    judge_passed: bool | None = None
    hallucinated: bool | None = None  # None = not judged yet
    judge_reasoning: str = ""
    trace_id: str | None = None  # Langfuse trace of the answering run


@dataclass(frozen=True)
class Flip:
    """A question whose pass/fail changed against the Baseline."""

    strategy: str
    question_id: str
    question: str
    direction: Literal["regressed", "fixed"]


class CitationChecker:
    """Expected titles ∩ cited titles, with continuity-consistency (spec #11 stage 1).

    A citation matches only if its title is expected AND its continuity tag is
    consistent with the title (a `/Legends` page must carry `legends`).
    """

    def __init__(self, golden: GoldenSet):
        self._by_id = {q.id: q for q in golden.questions}

    def grade(self, strategy: str, record: AnswerRecord) -> QuestionGrade:
        question = self._by_id.get(record.question_id)
        if question is None:
            raise ValueError(f"artifact {record.question_id!r} is not in the golden set")
        if question.category is Category.UNANSWERABLE:
            return QuestionGrade(
                question.id, question.question, question.category, strategy, None, (), trace_id=record.trace_id
            )
        cited = {c.title for c in record.citations if _consistent(c)}
        matched = set(question.expected_citations) & cited
        missing = tuple(t for t in question.expected_citations if t not in cited)
        return QuestionGrade(
            question.id,
            question.question,
            question.category,
            strategy,
            bool(matched),
            missing,
            trace_id=record.trace_id,
        )


def _consistent(citation: Citation) -> bool:
    expected = Continuity.LEGENDS if citation.title.endswith("/Legends") else Continuity.CANON
    return citation.continuity is expected


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
                grade = checker.grade(strategy, AnswerRecord.from_json(json.loads(path.read_text())))
                verdict_path = run_dir / strategy / f"{qid}.verdict.json"
                if verdict_path.exists():
                    v = json.loads(verdict_path.read_text())
                    grade = replace(
                        grade,
                        judge_passed=v["passed"],
                        hallucinated=v["hallucinated"],
                        judge_reasoning=v.get("reasoning", ""),
                    )
                grades.append(grade)
        return cls(
            run_id=manifest["run_id"],
            corpus_lock_sha256=manifest["corpus_lock_sha256"],
            strategies=tuple(manifest["strategies"]),
            grades=tuple(grades),
        )


class ScoreBoard:
    """Per-category x per-strategy aggregation over graded questions."""

    def __init__(self, grades: Iterable[QuestionGrade]):
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
            direction: Literal["regressed", "fixed"] = "regressed" if base.passed and not grade.passed else "fixed"
            flips.append(Flip(grade.strategy, grade.question_id, grade.question, direction))
        return sorted(flips, key=lambda f: (f.direction != "regressed", f.strategy, f.question_id))


class BaselineStore:
    """Owns eval/baselines/: the Baseline moves only by explicit promotion (spec #11)."""

    def __init__(self, root: Path):
        self._root = root

    def promote(self, run_dir: Path) -> Path:
        if not (run_dir / "run.json").exists():
            raise ValueError(f"{run_dir}: no manifest — an incomplete run cannot become the Baseline")
        dest = self._root / run_dir.name
        if dest.exists():
            raise ValueError(f"{dest}: this run is already a Baseline")
        self._root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(run_dir, dest)
        return dest

    def latest(self) -> Path | None:
        completed = sorted(d for d in self._root.glob("*") if (d / "run.json").exists()) if self._root.exists() else []
        return completed[-1] if completed else None


# Presentation order of the A/B/C table columns; unknown strategies are appended.
_STRATEGY_ORDER = ("vector-only", "graph-only", "agent")


def _as_judge_grades(grades: Iterable[QuestionGrade]) -> list[QuestionGrade]:
    """Judge verdicts as a ScoreBoard input: `passed` becomes the judge's call."""
    return [replace(g, passed=g.judge_passed) for g in grades]


def _trace(grade: QuestionGrade | None) -> str:
    """Langfuse trace pointer for a failing question (run-eval: regressions are debuggable)."""
    return f" (trace `{grade.trace_id}`)" if grade and grade.trace_id else ""


class ReportRenderer:
    """Markdown table (readable in terminal and pasteable into the README)."""

    def render(self, run: PersistedRun, baseline: PersistedRun | None) -> str:
        comparable = baseline is not None and baseline.corpus_lock_sha256 == run.corpus_lock_sha256

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

        strategies = [s for s in _STRATEGY_ORDER if s in run.strategies]
        strategies += [s for s in run.strategies if s not in strategies]

        board = ScoreBoard(run.grades)
        base_board = ScoreBoard(baseline.grades) if baseline and comparable else None
        lines += ["", "## Citation check", ""]
        lines += self._table(board, base_board, strategies)
        if not any(g.passed is not None for g in run.grades):
            lines += [
                "",
                "No citation-gradable questions in this run — unanswerable questions are scored by the Judge.",
            ]

        judged = any(g.judge_passed is not None for g in run.grades)
        judge_board = judge_base = None
        if judged:
            judge_board = ScoreBoard(_as_judge_grades(run.grades))
            judge_base = ScoreBoard(_as_judge_grades(baseline.grades)) if baseline and comparable else None
            lines += ["", "## Judge", ""]
            lines += self._table(judge_board, judge_base, strategies)

        hallucinations = [g for g in run.grades if g.hallucinated]
        if hallucinations:
            lines += ["", "## ⚠ HALLUCINATIONS", ""]
            lines += [
                f'- **{g.strategy}/{g.question_id}**{_trace(g)}: "{g.question}" — {g.judge_reasoning}'
                for g in hallucinations
            ]

        by_key = {(g.strategy, g.question_id): g for g in run.grades}
        for title, cur, base in (("citation check", board, base_board), ("judge", judge_board, judge_base)):
            if cur is None or base is None:
                continue
            flips = cur.flips_against(base)
            if flips:
                lines += ["", f"## Flipped vs Baseline ({title})", ""]
                lines += [
                    f"- **{f.direction}** {f.strategy}/{f.question_id}"
                    f'{_trace(by_key.get((f.strategy, f.question_id)))}: "{f.question}"'
                    for f in flips
                ]
        return "\n".join(lines) + "\n"

    def _table(self, board: ScoreBoard, base: ScoreBoard | None, strategies: list[str]) -> list[str]:
        lines = ["| Category | " + " | ".join(strategies) + " |", "|---" * (len(strategies) + 1) + "|"]
        for category in Category:
            cells = [self._cell(board, base, category, s) for s in strategies]
            if all(c == "–" for c in cells):
                continue
            lines.append(f"| {category} | " + " | ".join(cells) + " |")
        return lines

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
