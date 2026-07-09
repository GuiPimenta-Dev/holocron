"""corpus.lock plumbing: revid scan of the cache is complete and deterministic."""

import json

from ingest.wiki import cached_revids


def write_page(dir, title, revid):
    d = {"title": title, "wikitext": "x", "categories": []}
    if revid is not None:
        d["revid"] = revid
    (dir / f"{title}.json").write_text(json.dumps(d))


def test_cached_revids_reports_pinned_and_unpinned(tmp_path):
    write_page(tmp_path, "Tatooine", 123)
    write_page(tmp_path, "Naboo", None)  # cached before revid tracking
    assert cached_revids(tmp_path) == {"Tatooine": 123, "Naboo": None}


def test_lock_generation_is_deterministic(tmp_path):
    write_page(tmp_path, "B_page", 2)
    write_page(tmp_path, "A_page", 1)
    lock = lambda: json.dumps(  # noqa: E731 — same expression as cmd_lock
        {t: r for t, r in sorted(cached_revids(tmp_path).items()) if r is not None},
        indent=1,
        sort_keys=True,
    )
    first = lock()
    assert first == lock()
    assert json.loads(first) == {"A_page": 1, "B_page": 2}
