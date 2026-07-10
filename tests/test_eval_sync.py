"""Score-mapping logic of LangfuseSync with a fake client (permitted: the doctrine
forbids mocking the LLM, not a metrics client). The real Langfuse API surface is
exercised by real `eval push` runs, not here."""

from pathlib import Path

import pytest

from eval.golden import GoldenSet
from eval.report import PersistedRun
from eval.sync import LangfuseSync

FIXTURE_RUNS = Path(__file__).parent / "fixtures" / "eval_runs"


class FakeLangfuse:
    def __init__(self):
        self.datasets: list[dict] = []
        self.items: list[dict] = []
        self.scores: list[dict] = []
        self.flushed = False

    def create_dataset(self, **kwargs):
        self.datasets.append(kwargs)

    def create_dataset_item(self, **kwargs):
        self.items.append(kwargs)

    def create_score(self, **kwargs):
        self.scores.append(kwargs)

    def flush(self):
        self.flushed = True


@pytest.fixture(scope="module")
def golden() -> GoldenSet:
    return GoldenSet.load(Path("eval/golden_set.json"))


def test_register_golden_set_upserts_by_question_id(golden):
    fake = FakeLangfuse()
    count = LangfuseSync(fake).register_golden_set(golden)  # pyright: ignore[reportArgumentType]
    assert count == len(fake.items) == 30
    assert {i["id"] for i in fake.items} == {q.id for q in golden.questions}
    unanswerable = next(i for i in fake.items if i["metadata"]["category"] == "unanswerable")
    assert unanswerable["expected_output"]["expected_citations"] == []


def test_push_scores_maps_all_three_booleans(golden):
    run = PersistedRun.load(FIXTURE_RUNS / "20260710T164433Z", golden)  # judged multi-hop run
    fake = FakeLangfuse()
    pushed = LangfuseSync(fake).push_scores(run)  # pyright: ignore[reportArgumentType]
    # 3 strategies x (citation-pass + judge-pass + hallucinated)
    assert pushed == len(fake.scores) == 9
    assert {s["name"] for s in fake.scores} == {"citation-pass", "judge-pass", "hallucinated"}
    assert all(s["trace_id"] for s in fake.scores)
    assert all(s["data_type"] == "BOOLEAN" for s in fake.scores)
    assert fake.flushed


def test_push_scores_skips_citation_score_for_unanswerable(golden):
    run = PersistedRun.load(FIXTURE_RUNS / "20260710T165239Z", golden)  # judged unanswerable run
    fake = FakeLangfuse()
    LangfuseSync(fake).push_scores(run)  # pyright: ignore[reportArgumentType]
    assert {s["name"] for s in fake.scores} == {"judge-pass", "hallucinated"}  # no citation-pass
