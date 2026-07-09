"""Wookieepedia MediaWiki API client with on-disk cache.

All fetched wikitext lands in data/raw/ as one JSON per page; redirect
mappings accumulate in data/redirects.json. Everything downstream (parse,
graph, embed) works offline from this cache.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import httpx

API = "https://starwars.fandom.com/api.php"
RAW_DIR = Path("data/raw")
REDIRECTS_FILE = Path("data/redirects.json")
BATCH = 50

_client = httpx.Client(
    headers={"User-Agent": "Holocron/0.1 (portfolio project; polite crawler)"},
    timeout=30,
)


def _get(params: dict[str, Any]) -> dict[str, Any]:
    params = {"format": "json", "formatversion": 2, **params}
    for attempt in range(3):
        try:
            r = _client.get(API, params=params)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError:
            if attempt == 2:
                raise
            time.sleep(2**attempt)
        finally:
            time.sleep(0.2)  # ponytail: fixed polite delay, tune if Fandom throttles
    raise AssertionError("unreachable")


def slug(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", title)


def cached_titles() -> set[str]:
    return set(cached_revids())


def cached_revids(raw_dir: Path = RAW_DIR) -> dict[str, int | None]:
    """title -> pinned revid for every cached page (None = fetched pre-lock)."""
    out: dict[str, int | None] = {}
    for p in raw_dir.glob("*.json"):
        page = json.loads(p.read_text())
        out[page["title"]] = page.get("revid")
    return out


def load_redirects() -> dict[str, str]:
    if REDIRECTS_FILE.exists():
        return json.loads(REDIRECTS_FILE.read_text())
    return {}


def _save_redirects(new: dict[str, str]) -> None:
    if not new:
        return
    merged = load_redirects() | new
    REDIRECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    REDIRECTS_FILE.write_text(json.dumps(merged, indent=1, sort_keys=True))


def _query_pages(params: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Run one prop=revisions|categories query to completion (continuations)."""
    pages: dict[str, dict[str, Any]] = {}
    redirects: dict[str, str] = {}
    cont: dict[str, Any] = {}
    while True:
        resp = _get(params | cont)
        q = resp.get("query", {})
        for r in q.get("redirects", []):
            redirects[r["from"]] = r["to"]
        for p in q.get("pages", []):
            if p.get("missing") or p.get("invalid"):
                continue
            page = pages.setdefault(
                p["title"],
                {"title": p["title"], "revid": None, "wikitext": None, "categories": []},
            )
            if "revisions" in p and page["wikitext"] is None:
                rev = p["revisions"][0]
                page["revid"] = rev["revid"]
                page["wikitext"] = rev["slots"]["main"]["content"]
            page["categories"] += [c["title"] for c in p.get("categories", [])]
        if "continue" not in resp:
            break
        cont = resp["continue"]
    return pages, redirects


def _write_cache(pages: dict[str, dict[str, Any]]) -> int:
    written = 0
    for page in pages.values():
        if page["wikitext"] is None:
            continue
        page["categories"] = sorted(set(page["categories"]))
        (RAW_DIR / f"{slug(page['title'])}.json").write_text(json.dumps(page))
        written += 1
    return written


_PROP_PARAMS: dict[str, Any] = {
    "action": "query",
    "prop": "revisions|categories",
    "rvprop": "ids|content",
    "rvslots": "main",
    "clshow": "!hidden",
    "cllimit": "max",
}


def fetch_pages(titles: list[str], skip_cached: bool = True) -> int:
    """Fetch wikitext + revid + visible categories for titles, write to cache.

    Silently skips pages that don't exist (used to probe /Legends variants).
    Returns number of pages newly written.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if skip_cached:
        have = cached_titles()
        titles = [t for t in titles if t not in have]
    written = 0
    for i in range(0, len(titles), BATCH):
        batch = titles[i : i + BATCH]
        pages, redirects = _query_pages(_PROP_PARAMS | {"titles": "|".join(batch), "redirects": 1})
        _save_redirects(redirects)
        written += _write_cache(pages)
        print(f"  fetched {min(i + BATCH, len(titles))}/{len(titles)} (+{written} new)")
    return written


def fetch_by_revids(revids: list[int]) -> int:
    """Fetch pages at exact pinned revisions (corpus.lock rebuild, ADR-0002).

    Categories are fetched as of today, not as of the revision — the API only
    versions text. They only feed continuity detection, which is stable.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for i in range(0, len(revids), BATCH):
        batch = revids[i : i + BATCH]
        pages, _ = _query_pages(_PROP_PARAMS | {"revids": "|".join(map(str, batch))})
        written += _write_cache(pages)
        print(f"  fetched {min(i + BATCH, len(revids))}/{len(revids)} (+{written} new)")
    return written


def get_links(title: str) -> list[str]:
    """All main-namespace links on a page (follows continuation)."""
    links: list[str] = []
    cont: dict[str, Any] = {}
    while True:
        resp = _get(
            {
                "action": "query",
                "titles": title,
                "prop": "links",
                "plnamespace": 0,
                "pllimit": "max",
                "redirects": 1,
                **cont,
            }
        )
        for p in resp.get("query", {}).get("pages", []):
            links += [link["title"] for link in p.get("links", [])]
        if "continue" not in resp:
            break
        cont = resp["continue"]
    return links
