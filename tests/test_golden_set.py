"""Golden Set loader: the real versioned file must load; malformed entries are rejected."""

import json
from pathlib import Path

import pytest

from eval.golden import Category, GoldenSet

GOLDEN_PATH = Path("eval/golden_set.json")


def _entries() -> list[dict]:
    return json.loads(GOLDEN_PATH.read_text())


def _write(tmp_path: Path, entries: list[dict]) -> Path:
    path = tmp_path / "golden.json"
    path.write_text(json.dumps(entries))
    return path


def test_real_golden_set_loads():
    golden = GoldenSet.load(GOLDEN_PATH)
    assert len(golden.questions) >= 5
    assert {q.category for q in golden.questions} == set(Category)


def test_filter_by_category():
    golden = GoldenSet.load(GOLDEN_PATH)
    subset = golden.filter(Category.UNANSWERABLE)
    assert subset.questions
    assert all(q.category is Category.UNANSWERABLE for q in subset.questions)


def test_rejects_unknown_category(tmp_path):
    entries = _entries()
    entries[0]["category"] = "trivia"
    with pytest.raises(ValueError, match="category"):
        GoldenSet.load(_write(tmp_path, entries))


def test_rejects_missing_field(tmp_path):
    entries = _entries()
    del entries[0]["question"]
    with pytest.raises(ValueError, match="missing"):
        GoldenSet.load(_write(tmp_path, entries))


def test_rejects_duplicate_ids(tmp_path):
    entries = _entries()
    entries[1]["id"] = entries[0]["id"]
    with pytest.raises(ValueError, match="duplicate"):
        GoldenSet.load(_write(tmp_path, entries))


def test_rejects_unanswerable_with_expectations(tmp_path):
    entries = _entries()
    bad = next(e for e in entries if e["category"] == "unanswerable")
    bad["expected_citations"] = ["Yoda"]
    with pytest.raises(ValueError, match="unanswerable"):
        GoldenSet.load(_write(tmp_path, entries))


def test_rejects_answerable_without_expectations(tmp_path):
    entries = _entries()
    good = next(e for e in entries if e["category"] != "unanswerable")
    good["expected_citations"] = []
    with pytest.raises(ValueError, match="expected_citations"):
        GoldenSet.load(_write(tmp_path, entries))


def test_rejects_non_list_top_level(tmp_path):
    path = tmp_path / "golden.json"
    path.write_text(json.dumps({"questions": _entries()}))
    with pytest.raises(ValueError, match="list"):
        GoldenSet.load(path)


def test_rejects_string_where_list_expected(tmp_path):
    entries = _entries()
    entries[0]["expected_facts"] = "Nautolan"
    with pytest.raises(ValueError, match="must be a list"):
        GoldenSet.load(_write(tmp_path, entries))
