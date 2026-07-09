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
    return {
        json.loads(p.read_text())["title"]
        for p in RAW_DIR.glob("*.json")
    }


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


def fetch_pages(titles: list[str], skip_cached: bool = True) -> int:
    """Fetch wikitext + visible categories for titles, write to cache.

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
        pages: dict[str, dict[str, Any]] = {}
        redirects: dict[str, str] = {}
        params: dict[str, Any] = {
            "action": "query",
            "titles": "|".join(batch),
            "prop": "revisions|categories",
            "rvprop": "content",
            "rvslots": "main",
            "clshow": "!hidden",
            "cllimit": "max",
            "redirects": 1,
        }
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
                    p["title"], {"title": p["title"], "wikitext": None, "categories": []}
                )
                if "revisions" in p and page["wikitext"] is None:
                    page["wikitext"] = p["revisions"][0]["slots"]["main"]["content"]
                page["categories"] += [c["title"] for c in p.get("categories", [])]
            if "continue" not in resp:
                break
            cont = resp["continue"]
        _save_redirects(redirects)
        for page in pages.values():
            if page["wikitext"] is None:
                continue
            page["categories"] = sorted(set(page["categories"]))
            (RAW_DIR / f"{slug(page['title'])}.json").write_text(json.dumps(page))
            written += 1
        print(f"  fetched {min(i + BATCH, len(titles))}/{len(titles)} (+{written} new)")
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
