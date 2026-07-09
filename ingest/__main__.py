"""Ingestion CLI.

  uv run python -m ingest crawl [--cap 5000]   fetch corpus from Wookieepedia
  uv run python -m ingest lock                 pin cache -> corpus.lock (ADR-0002)
  uv run python -m ingest rebuild              corpus.lock -> refetch cache at pinned revids
  uv run python -m ingest parse                cache -> entities.jsonl + chunks.jsonl
  uv run python -m ingest graph                entities -> Neo4j
  uv run python -m ingest embed                chunks -> LanceDB
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from ingest import parse as parse_mod
from ingest import wiki

# Corpus = everything linked from the 11 saga/anthology films, depth 1,
# plus each page's /Legends counterpart.
SEEDS = [
    "Star Wars: Episode I The Phantom Menace",
    "Star Wars: Episode II Attack of the Clones",
    "Star Wars: Episode III Revenge of the Sith",
    "Star Wars: Episode IV A New Hope",
    "Star Wars: Episode V The Empire Strikes Back",
    "Star Wars: Episode VI Return of the Jedi",
    "Star Wars: Episode VII The Force Awakens",
    "Star Wars: Episode VIII The Last Jedi",
    "Star Wars: Episode IX The Rise of Skywalker",
    "Rogue One: A Star Wars Story",
    "Solo: A Star Wars Story",
]

ENTITIES_FILE = Path("data/entities.jsonl")
CHUNKS_FILE = Path("data/chunks.jsonl")
LOCK_FILE = Path("corpus.lock")


def cmd_crawl(cap: int) -> None:
    print(f"crawling from {len(SEEDS)} film seeds, cap {cap}")
    wiki.fetch_pages(SEEDS)
    counts: dict[str, int] = {}  # title -> number of seed films linking to it
    for seed in SEEDS:
        for t in wiki.get_links(seed):
            counts[t] = counts.get(t, 0) + 1
        print(f"  links after {seed}: {len(counts)}")
    # Rank by cross-film frequency so --cap keeps the most central pages,
    # not an alphabetical slice.
    ranked = sorted(counts, key=lambda t: -counts[t])
    titles = [t for t in ranked if not t.endswith("/Legends")][:cap]
    print(f"fetching {len(titles)} canon pages")
    wiki.fetch_pages(titles)
    legends = [f"{t}/Legends" for t in titles]
    print(f"probing {len(legends)} /Legends variants")
    wiki.fetch_pages(legends)
    print(f"cache now has {len(wiki.cached_titles())} pages")


def cmd_lock() -> None:
    """Pin every cached page to its revid and write corpus.lock (ADR-0002)."""
    missing = sorted(t for t, r in wiki.cached_revids().items() if r is None)
    if missing:
        print(f"refetching {len(missing)} pages cached before revid tracking")
        wiki.fetch_pages(missing, skip_cached=False)
    revids = wiki.cached_revids()
    dropped = sorted(t for t, r in revids.items() if r is None)
    for t in dropped:
        print(f"  WARNING: no revid for {t!r} (page moved or deleted) — left out of the lock")
    lock = {t: r for t, r in sorted(revids.items()) if r is not None}
    LOCK_FILE.write_text(json.dumps(lock, indent=1, sort_keys=True) + "\n")
    print(f"{LOCK_FILE}: {len(lock)} pages pinned")


def cmd_rebuild() -> None:
    """Refetch the raw cache at the exact revids pinned in corpus.lock."""
    lock: dict[str, int] = json.loads(LOCK_FILE.read_text())
    have = wiki.cached_revids()
    todo = sorted(r for t, r in lock.items() if have.get(t) != r)
    print(f"rebuilding {len(todo)}/{len(lock)} pages from {LOCK_FILE}")
    wiki.fetch_by_revids(todo)


def _load_entities() -> list[parse_mod.Entity]:
    entities = []
    for line in ENTITIES_FILE.read_text().splitlines():
        d = json.loads(line)
        entities.append(parse_mod.Entity(**d))
    return entities


def cmd_parse() -> None:
    n_pages, entities = 0, []
    for p in sorted(wiki.RAW_DIR.glob("*.json")):
        page = json.loads(p.read_text())
        n_pages += 1
        e = parse_mod.parse_page(page["title"], page["wikitext"], page["categories"])
        if e:
            entities.append(e)
    with ENTITIES_FILE.open("w") as f:
        for e in entities:
            f.write(json.dumps(e.__dict__) + "\n")
    with CHUNKS_FILE.open("w") as f:
        n_chunks = 0
        for e in entities:
            for c in e.chunks:
                f.write(
                    json.dumps(
                        {
                            "title": e.title,
                            "name": e.name,
                            "continuity": e.continuity,
                            **c,
                        }
                    )
                    + "\n"
                )
                n_chunks += 1
    print(f"{n_pages} pages -> {len(entities)} entities, {n_chunks} chunks")
    types: dict[str, int] = {}
    for e in entities:
        types[e.type] = types.get(e.type, 0) + 1
    for t, n in sorted(types.items(), key=lambda kv: -kv[1])[:15]:
        print(f"  {t}: {n}")


def cmd_graph() -> None:
    from ingest import graph

    stats = graph.load(_load_entities(), wiki.load_redirects())
    print(stats)


def cmd_embed() -> None:
    from ingest import embed

    chunks = [json.loads(line) for line in CHUNKS_FILE.read_text().splitlines()]
    print(f"{embed.load(chunks)} chunks embedded into {embed.DB_DIR}")


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser(prog="ingest")
    sub = ap.add_subparsers(dest="cmd", required=True)
    crawl = sub.add_parser("crawl")
    crawl.add_argument("--cap", type=int, default=5000)
    for name in ("lock", "rebuild", "parse", "graph", "embed"):
        sub.add_parser(name)
    args = ap.parse_args()
    if args.cmd == "crawl":
        cmd_crawl(args.cap)
    else:
        {
            "lock": cmd_lock,
            "rebuild": cmd_rebuild,
            "parse": cmd_parse,
            "graph": cmd_graph,
            "embed": cmd_embed,
        }[args.cmd]()


if __name__ == "__main__":
    main()
