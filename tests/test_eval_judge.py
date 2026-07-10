"""Judge pure parts: verdict parsing and merge into the report.

The claude CLI itself is never mocked or unit-tested (doctrine) — judge quality
is measured only by eval runs. Verdict fixtures are real judge outputs persisted
under tests/fixtures/eval_runs.
"""

import json
import shutil
from pathlib import Path

import pytest

from eval.golden import GoldenSet
from eval.judge import RUBRICS, Verdict
from eval.report import PersistedRun, ReportRenderer

FIXTURE_RUNS = Path(__file__).parent / "fixtures" / "eval_runs"
MULTI_HOP_RUN = FIXTURE_RUNS / "20260710T164433Z"
UNANSWERABLE_RUN = FIXTURE_RUNS / "20260710T165239Z"


@pytest.fixture(scope="module")
def golden() -> GoldenSet:
    return GoldenSet.load(Path("eval/golden_set.json"))


# --- verdict parsing ---


def test_parse_plain_json():
    v = Verdict.parse('{"passed": true, "hallucinated": false, "reasoning": "grounded"}')
    assert v == Verdict(passed=True, hallucinated=False, reasoning="grounded")


def test_parse_fenced_json():
    v = Verdict.parse('```json\n{"passed": false, "hallucinated": true, "reasoning": "invented"}\n```')
    assert v.passed is False
    assert v.hallucinated is True


def test_parse_rejects_non_bool():
    with pytest.raises(ValueError, match="verdict"):
        Verdict.parse('{"passed": "yes", "hallucinated": false, "reasoning": "x"}')


def test_parse_rejects_garbage():
    with pytest.raises(ValueError, match="verdict"):
        Verdict.parse("the answer looks fine to me")


def test_every_category_has_a_rubric():
    from eval.golden import Category

    assert set(RUBRICS) == set(Category)


# --- merge into the report ---


def test_run_loads_real_verdicts(golden):
    run = PersistedRun.load(MULTI_HOP_RUN, golden)
    graded = [g for g in run.grades if g.judge_passed is not None]
    assert len(graded) == 3  # one real verdict per strategy


def test_unanswerable_judge_grades_refusal(golden):
    run = PersistedRun.load(UNANSWERABLE_RUN, golden)
    # all three strategies refused the fabricated question in the real run
    assert all(g.judge_passed is True for g in run.grades)
    assert all(g.hallucinated is False for g in run.grades)


def test_report_renders_judge_table(golden):
    text = ReportRenderer().render(PersistedRun.load(MULTI_HOP_RUN, golden), baseline=None)
    assert "## Citation check" in text
    assert "## Judge" in text


def test_hallucination_flagged_loudly(golden, tmp_path):
    run_dir = tmp_path / "run"
    shutil.copytree(UNANSWERABLE_RUN, run_dir)
    verdict_path = run_dir / "vector-only" / "unanswerable-vela-korr-species.verdict.json"
    verdict = json.loads(verdict_path.read_text())
    verdict.update(passed=False, hallucinated=True, reasoning="states a species for a fabricated character")
    verdict_path.write_text(json.dumps(verdict))

    text = ReportRenderer().render(PersistedRun.load(run_dir, golden), baseline=None)
    assert "HALLUCINATION" in text
    assert "vector-only/unanswerable-vela-korr-species" in text


def test_report_without_verdicts_has_no_judge_table(golden, tmp_path):
    run_dir = tmp_path / "run"
    shutil.copytree(MULTI_HOP_RUN, run_dir)
    for p in run_dir.rglob("*.verdict.json"):
        p.unlink()
    text = ReportRenderer().render(PersistedRun.load(run_dir, golden), baseline=None)
    assert "## Judge" not in text
