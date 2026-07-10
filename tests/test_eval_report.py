"""Report phase pure parts: citation check, aggregation, delta math, rendering.

Fixtures are real persisted runs (tests/fixtures/eval_runs) produced by
`python -m eval answer` against the pinned corpus — never synthetic shapes.
"""

import json
import shutil
from pathlib import Path

import pytest

from eval.golden import Category, GoldenSet
from eval.report import CitationChecker, PersistedRun, ReportRenderer, ScoreBoard

FIXTURE_RUNS = Path(__file__).parent / "fixtures" / "eval_runs"
MULTI_HOP_RUN = FIXTURE_RUNS / "20260710T164433Z"
UNANSWERABLE_RUN = FIXTURE_RUNS / "20260710T165239Z"


@pytest.fixture(scope="module")
def golden() -> GoldenSet:
    return GoldenSet.load(Path("eval/golden_set.json"))


def _artifact(run: Path, strategy: str) -> dict:
    return json.loads(next((run / strategy).glob("*.json")).read_text())


# --- citation checker ---


def test_citation_check_happy(golden):
    checker = CitationChecker(golden)
    grade = checker.grade("agent", _artifact(MULTI_HOP_RUN, "agent"))
    assert grade.passed is True
    assert grade.category is Category.MULTI_HOP
    assert "Jango Fett" in grade.missing  # answered via Boba Fett's DONOR edge; Jango page not cited


def test_citation_check_miss(golden):
    artifact = _artifact(MULTI_HOP_RUN, "agent")
    artifact["citations"] = [{"title": "Naboo", "name": "Naboo", "continuity": "canon"}]
    grade = CitationChecker(golden).grade("agent", artifact)
    assert grade.passed is False
    assert set(grade.missing) == {"Boba Fett", "Jango Fett"}


def test_citation_check_wrong_continuity(golden):
    artifact = _artifact(MULTI_HOP_RUN, "agent")
    # a canon-titled page tagged legends is an inconsistent citation — not a match
    artifact["citations"] = [{"title": "Boba Fett", "name": "Boba Fett", "continuity": "legends"}]
    grade = CitationChecker(golden).grade("agent", artifact)
    assert grade.passed is False


def test_unanswerable_is_not_citation_graded(golden):
    grade = CitationChecker(golden).grade("agent", _artifact(UNANSWERABLE_RUN, "agent"))
    assert grade.passed is None


def test_unknown_question_id_rejected(golden):
    artifact = _artifact(MULTI_HOP_RUN, "agent")
    artifact["id"] = "not-in-the-golden-set"
    with pytest.raises(ValueError, match="golden set"):
        CitationChecker(golden).grade("agent", artifact)


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
    baseline_grades = [g.flipped() for g in current.grades if g.strategy == "agent"]
    flips = ScoreBoard(current.grades).flips_against(ScoreBoard(baseline_grades))
    assert len(flips) == 1
    flip = flips[0]
    assert flip.strategy == "agent"
    assert flip.direction == "fixed"  # baseline failed, current passes
    assert "Boba Fett" in flip.question  # quoted verbatim


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
