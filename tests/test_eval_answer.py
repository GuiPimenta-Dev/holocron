"""Answer-phase pure parts: event-stream -> result assembly, and the persisted-run shape.

The strategy itself (LLM) is never run or mocked here — its quality is measured
only by eval runs (testing doctrine).
"""

import json

import pytest

from core.domain import Citation, Continuity
from eval.answer import QuestionResult, RunWriter
from eval.golden import Category, GoldenQuestion

QUESTION = GoldenQuestion(
    id="single-hop-kit-fisto-species",
    category=Category.SINGLE_HOP,
    question="What species is Kit Fisto?",
    expected_facts=("Nautolan",),
    expected_citations=("Kit Fisto",),
    expected_continuity="Same answer in both continuities.",
)

# The agent's event protocol, verbatim shapes (agent/holocron.py `astream`).
EVENTS = [
    {"type": "tool_call", "name": "get_entity", "args": {"name": "Kit Fisto"}},
    {"type": "tool_result", "name": "get_entity", "result": [{"title": "Kit Fisto"}]},
    {"type": "answer_delta", "text": "Kit Fisto is "},
    {"type": "answer_delta", "text": "a Nautolan."},
    {
        "type": "done",
        "citations": [{"title": "Kit Fisto", "name": "Kit Fisto", "continuity": "canon"}],
        "trace_id": "abc123",
    },
]


def test_result_from_events():
    result = QuestionResult.from_events(QUESTION, EVENTS)
    assert result.answer == "Kit Fisto is a Nautolan."
    assert result.citations == (Citation(title="Kit Fisto", name="Kit Fisto", continuity=Continuity.CANON),)
    assert result.trace_id == "abc123"


def test_result_requires_done_event():
    with pytest.raises(ValueError, match="done"):
        QuestionResult.from_events(QUESTION, EVENTS[:-1])


def test_run_dir_shape(tmp_path):
    writer = RunWriter(runs_root=tmp_path, run_id="20260710T120000Z", strategy="agent", corpus_lock_sha256="deadbeef")
    writer.write(QuestionResult.from_events(QUESTION, EVENTS))
    run_dir = writer.finish(category=None)

    assert run_dir == tmp_path / "20260710T120000Z"
    artifact = json.loads((run_dir / "agent" / "single-hop-kit-fisto-species.json").read_text())
    assert artifact == {
        "id": "single-hop-kit-fisto-species",
        "category": "single-hop",
        "question": "What species is Kit Fisto?",
        "answer": "Kit Fisto is a Nautolan.",
        "citations": [{"title": "Kit Fisto", "name": "Kit Fisto", "continuity": "canon"}],
        "trace_id": "abc123",
    }
    manifest = json.loads((run_dir / "run.json").read_text())
    assert manifest == {
        "run_id": "20260710T120000Z",
        "strategies": ["agent"],
        "category": None,
        "corpus_lock_sha256": "deadbeef",
        "questions": ["single-hop-kit-fisto-species"],
    }


def test_manifest_lands_only_on_finish(tmp_path):
    """An interrupted run has no manifest — it can never be reported (spec #11)."""
    writer = RunWriter(runs_root=tmp_path, run_id="r1", strategy="agent", corpus_lock_sha256="deadbeef")
    writer.write(QuestionResult.from_events(QUESTION, EVENTS))
    assert not (tmp_path / "r1" / "run.json").exists()
    writer.finish(category=Category.SINGLE_HOP)
    manifest = json.loads((tmp_path / "r1" / "run.json").read_text())
    assert manifest["category"] == "single-hop"
