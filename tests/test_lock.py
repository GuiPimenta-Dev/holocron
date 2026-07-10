"""corpus.lock plumbing: revid scan of the cache is complete and deterministic."""

import json

import pytest

from ingest.wiki import WikiClient


@pytest.fixture
def wiki(tmp_path):
    return WikiClient(raw_dir=tmp_path, redirects_file=tmp_path / "redirects.json")


def write_page(dir, title, revid):
    d = {"title": title, "wikitext": "x", "categories": []}
    if revid is not None:
        d["revid"] = revid
    (dir / f"{title}.json").write_text(json.dumps(d))


def test_cached_revids_reports_pinned_and_unpinned(wiki, tmp_path):
    write_page(tmp_path, "Tatooine", 123)
    write_page(tmp_path, "Naboo", None)  # cached before revid tracking
    assert wiki.cached_revids() == {"Tatooine": 123, "Naboo": None}


def test_lock_generation_is_deterministic_and_drops_unpinned(wiki, tmp_path):
    write_page(tmp_path, "B_page", 2)
    write_page(tmp_path, "A_page", 1)
    write_page(tmp_path, "No_revid", None)
    first = wiki.build_lock()
    assert first == wiki.build_lock()
    assert json.loads(first) == {"A_page": 1, "B_page": 2}
