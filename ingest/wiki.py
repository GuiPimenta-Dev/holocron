"""Wookieepedia MediaWiki API client with an on-disk cache.

All fetched wikitext lands in the raw dir as one JSON per page; redirect
mappings accumulate in the redirects file. Everything downstream (parse,
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
BATCH = 50

_PROP_PARAMS: dict[str, Any] = {
    "action": "query",
    "prop": "revisions|categories",
    "rvprop": "ids|content",
    "rvslots": "main",
    "clshow": "!hidden",
    "cllimit": "max",
}


def _slug(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", title)


class WikiClient:
    """Owns the HTTP session and the raw-cache directory."""

    def __init__(self, raw_dir: Path, redirects_file: Path):
        self._raw_dir = raw_dir
        self._redirects_file = redirects_file
        self._http = httpx.Client(
            headers={"User-Agent": "Holocron/0.1 (portfolio project; polite crawler)"},
            timeout=30,
        )

    def fetch_pages(self, titles: list[str], skip_cached: bool = True) -> int:
        """Fetch wikitext + revid + visible categories for titles, write to cache.

        Silently skips pages that don't exist (used to probe /Legends variants).
        Returns number of pages newly written.
        """
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        if skip_cached:
            have = self.cached_titles()
            titles = [t for t in titles if t not in have]
        written = 0
        for i in range(0, len(titles), BATCH):
            batch = titles[i : i + BATCH]
            pages, redirects = self._query_pages(
                _PROP_PARAMS | {"titles": "|".join(batch), "redirects": 1}
            )
            self._save_redirects(redirects)
            written += self._write_cache(pages)
            print(f"  fetched {min(i + BATCH, len(titles))}/{len(titles)} (+{written} new)")
        return written

    def fetch_by_revids(self, revids: list[int]) -> int:
        """Fetch pages at exact pinned revisions (corpus.lock rebuild, ADR-0002).

        Categories are fetched as of today, not as of the revision — the API
        only versions text. They only feed continuity detection, which is stable.
        """
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        written = 0
        for i in range(0, len(revids), BATCH):
            batch = revids[i : i + BATCH]
            pages, _ = self._query_pages(_PROP_PARAMS | {"revids": "|".join(map(str, batch))})
            written += self._write_cache(pages)
            print(f"  fetched {min(i + BATCH, len(revids))}/{len(revids)} (+{written} new)")
        return written

    def get_links(self, title: str) -> list[str]:
        """All main-namespace links on a page (follows continuation)."""
        links: list[str] = []
        cont: dict[str, Any] = {}
        while True:
            resp = self._get(
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

    def cached_titles(self) -> set[str]:
        return set(self.cached_revids())

    def cached_revids(self) -> dict[str, int | None]:
        """title -> pinned revid for every cached page (None = fetched pre-lock)."""
        out: dict[str, int | None] = {}
        for p in self._raw_dir.glob("*.json"):
            page = json.loads(p.read_text())
            out[page["title"]] = page.get("revid")
        return out

    def cached_pages(self) -> list[dict[str, Any]]:
        """Every cached page, sorted by filename (deterministic parse order)."""
        return [json.loads(p.read_text()) for p in sorted(self._raw_dir.glob("*.json"))]

    def build_lock(self) -> str:
        """Serialize the cache's (title, revid) pairs into the canonical corpus.lock text."""
        lock = {t: r for t, r in sorted(self.cached_revids().items()) if r is not None}
        return json.dumps(lock, indent=1, sort_keys=True) + "\n"

    def load_redirects(self) -> dict[str, str]:
        if self._redirects_file.exists():
            return json.loads(self._redirects_file.read_text())
        return {}

    def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        params = {"format": "json", "formatversion": 2, **params}
        for attempt in range(3):
            try:
                r = self._http.get(API, params=params)
                r.raise_for_status()
                return r.json()
            except httpx.HTTPError:
                if attempt == 2:
                    raise
                time.sleep(2**attempt)
            finally:
                time.sleep(0.2)  # ponytail: fixed polite delay, tune if Fandom throttles
        raise AssertionError("unreachable")

    def _query_pages(
        self, params: dict[str, Any]
    ) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
        """Run one prop=revisions|categories query to completion (continuations)."""
        pages: dict[str, dict[str, Any]] = {}
        redirects: dict[str, str] = {}
        cont: dict[str, Any] = {}
        while True:
            resp = self._get(params | cont)
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

    def _write_cache(self, pages: dict[str, dict[str, Any]]) -> int:
        written = 0
        for page in pages.values():
            if page["wikitext"] is None:
                continue
            page["categories"] = sorted(set(page["categories"]))
            (self._raw_dir / f"{_slug(page['title'])}.json").write_text(json.dumps(page))
            written += 1
        return written

    def _save_redirects(self, new: dict[str, str]) -> None:
        if not new:
            return
        merged = self.load_redirects() | new
        self._redirects_file.parent.mkdir(parents=True, exist_ok=True)
        self._redirects_file.write_text(json.dumps(merged, indent=1, sort_keys=True))
