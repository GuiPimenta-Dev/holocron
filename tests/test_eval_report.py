"""Report phase pure parts: citation check, aggregation, delta math, rendering.

Fixtures are real persisted runs (tests/fixtures/eval_runs) produced by
`python -m eval answer` against the pinned corpus — never synthetic shapes.
"""

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from core.domain import Citation, Continuity
from eval.golden import Category, GoldenSet
from eval.report import AnswerRecord, CitationChecker, PersistedRun, QuestionGrade, ReportRenderer, ScoreBoard

FIXTURE_RUNS = Path(__file__).parent / "fixtures" / "eval_runs"
MULTI_HOP_RUN = FIXTURE_RUNS / "20260710T164433Z"
UNANSWERABLE_RUN = FIXTURE_RUNS / "20260710T165239Z"


@pytest.fixture(scope="module")
def golden() -> GoldenSet:
    return GoldenSet.load(Path("eval/golden_set.json"))


def _record(run: Path, strategy: str) -> AnswerRecord:
    return AnswerRecord.from_json(json.loads(next((run / strategy).glob("*.json")).read_text()))


def _flipped(grade: QuestionGrade) -> QuestionGrade:
    return replace(grade, passed=not grade.passed if grade.passed is not None else None)


# --- citation checker ---


def test_citation_check_happy(golden):
    checker = CitationChecker(golden)
    grade = checker.grade("agent", _record(MULTI_HOP_RUN, "agent"))
    assert grade.passed is True
    assert grade.category is Category.MULTI_HOP
    assert "Jango Fett" in grade.missing  # answered via Boba Fett's DONOR edge; Jango page not cited


def test_citation_check_miss(golden):
    # a real run missing its citations can't be produced deterministically — mutate the real record
    record = replace(
        _record(MULTI_HOP_RUN, "agent"),
        citations=(Citation(title="Naboo", name="Naboo", continuity=Continuity.CANON),),
    )
    grade = CitationChecker(golden).grade("agent", record)
    assert grade.passed is False
    assert set(grade.missing) == {"Boba Fett", "Jango Fett"}


def test_citation_check_wrong_continuity(golden):
    # a canon-titled page tagged legends is an inconsistent citation — not a match
    record = replace(
        _record(MULTI_HOP_RUN, "agent"),
        citations=(Citation(title="Boba Fett", name="Boba Fett", continuity=Continuity.LEGENDS),),
    )
    grade = CitationChecker(golden).grade("agent", record)
    assert grade.passed is False


def test_unanswerable_is_not_citation_graded(golden):
    grade = CitationChecker(golden).grade("agent", _record(UNANSWERABLE_RUN, "agent"))
    assert grade.passed is None


def test_unknown_question_id_rejected(golden):
    record = replace(_record(MULTI_HOP_RUN, "agent"), question_id="not-in-the-golden-set")
    with pytest.raises(ValueError, match="golden set"):
        CitationChecker(golden).grade("agent", record)


# --- persisted run loading ---


def test_load_real_run(golden):
    run = PersistedRun.load(MULTI_HOP_RUN, golden)
    assert run.run_id == "20260710T164433Z"
    assert set(run.strategies) == {"agent", "graph-only", "vector-only"}
    assert len(run.grades) == 3  # 1 question x 3 strategies


def test_incomplete_run_is_a_hard_error(golden, tmp_path):
    broken = tmp_path / "broken"
    shutil.copytree(MULTI_HOP_RUN, broken)
    (broken / "run.json").unlink()
    with pytest.raises(ValueError, match="manifest"):
        PersistedRun.load(broken, golden)


def test_missing_artifact_is_a_hard_error(golden, tmp_path):
    broken = tmp_path / "broken"
    shutil.copytree(MULTI_HOP_RUN, broken)
    next((broken / "graph-only").glob("*.json")).unlink()
    with pytest.raises(ValueError, match="missing artifact"):
        PersistedRun.load(broken, golden)


# --- aggregation + delta math ---


def test_scoreboard_rates(golden):
    run = PersistedRun.load(MULTI_HOP_RUN, golden)
    board = ScoreBoard(run.grades)
    assert board.cell(Category.MULTI_HOP, "agent") == (1, 1)  # passed, graded
    assert board.cell(Category.SINGLE_HOP, "agent") == (0, 0)  # nothing graded


def test_scoreboard_excludes_ungraded(golden):
    run = PersistedRun.load(UNANSWERABLE_RUN, golden)
    board = ScoreBoard(run.grades)
    assert board.cell(Category.UNANSWERABLE, "agent") == (0, 0)


def test_flips_between_boards(golden):
    current = PersistedRun.load(MULTI_HOP_RUN, golden)
    baseline_grades = [_flipped(g) for g in current.grades if g.strategy == "agent"]
    flips = ScoreBoard(current.grades).flips_against(ScoreBoard(baseline_grades))
    assert len(flips) == 1
    flip = flips[0]
    assert flip.strategy == "agent"
    assert flip.direction == "fixed"  # baseline failed, current passes
    assert "Boba Fett" in flip.question  # quoted verbatim


def test_regressions_are_detected_and_listed_first(golden):
    baseline = PersistedRun.load(MULTI_HOP_RUN, golden)  # everything passes
    current_grades = [_flipped(g) if g.strategy == "agent" else g for g in baseline.grades]
    # graph-only regresses in the baseline board instead, so both directions coexist
    baseline_grades = [_flipped(g) if g.strategy == "graph-only" else g for g in baseline.grades]
    flips = ScoreBoard(current_grades).flips_against(ScoreBoard(baseline_grades))
    assert [f.direction for f in flips] == ["regressed", "fixed"]
    assert flips[0].strategy == "agent"  # passed in baseline, fails now


# --- rendering ---


def test_render_without_baseline(golden):
    run = PersistedRun.load(MULTI_HOP_RUN, golden)
    text = ReportRenderer().render(run, baseline=None)
    assert "Baseline: none" in text and "absolute" in text
    assert "100%" in text
    assert "| multi-hop |" in text


def test_render_with_baseline_shows_deltas_and_flips(golden, tmp_path):
    baseline_dir = tmp_path / "baseline"
    shutil.copytree(MULTI_HOP_RUN, baseline_dir)
    artifact_path = next((baseline_dir / "agent").glob("*.json"))
    artifact = json.loads(artifact_path.read_text())
    artifact["citations"] = []  # baseline agent missed its citations
    artifact_path.write_text(json.dumps(artifact))

    run = PersistedRun.load(MULTI_HOP_RUN, golden)
    baseline = PersistedRun.load(baseline_dir, golden)
    text = ReportRenderer().render(run, baseline=baseline)
    assert "+100pp" in text
    assert "What species was the genetic donor Boba Fett was cloned from?" in text


def test_render_incomparable_baseline(golden, tmp_path):
    baseline_dir = tmp_path / "baseline"
    shutil.copytree(MULTI_HOP_RUN, baseline_dir)
    manifest = json.loads((baseline_dir / "run.json").read_text())
    manifest["corpus_lock_sha256"] = "different"
    (baseline_dir / "run.json").write_text(json.dumps(manifest))

    run = PersistedRun.load(MULTI_HOP_RUN, golden)
    baseline = PersistedRun.load(baseline_dir, golden)
    text = ReportRenderer().render(run, baseline=baseline)
    assert "incomparable" in text
    assert "+0pp" not in text  # no deltas against a different corpus
