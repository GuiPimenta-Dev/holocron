"""Composition root for the eval harness — constructs resources, reads env (ADR-0004).

Answer phase (persists a run dir under eval/runs/):

    uv run python -m eval answer [--category single-hop] [--strategy vector-only]
"""

import argparse
import asyncio
import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from eval.golden import Category, GoldenSet

# The three Retrieval Strategies (CONTEXT.md); toolsets are built in main()
# after the (heavy) agent import — same agent, same LLM, only the tools differ.
STRATEGY_NAMES = ("vector-only", "graph-only", "agent")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="python -m eval")
    sub = parser.add_subparsers(dest="command", required=True)
    answer = sub.add_parser("answer", help="run the Retrieval Strategies over the Golden Set and persist a run dir")
    answer.add_argument("--category", choices=[str(c) for c in Category], help="run one category only")
    answer.add_argument("--strategy", choices=STRATEGY_NAMES, help="run one strategy only (default: all three)")
    args = parser.parse_args()

    import lancedb
    from neo4j import GraphDatabase

    from agent.holocron import TOOL_NAMES, HolocronAgent, Toolset
    from core.embeddings import provider_from_env
    from eval.answer import AnswerRunner, RunWriter
    from retrieval import KnowledgeGraph, VectorIndex

    root = Path(__file__).parent
    golden = GoldenSet.load(root / "golden_set.json")
    category = Category(args.category) if args.category else None

    driver = GraphDatabase.driver(
        os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        auth=(
            os.environ.get("NEO4J_USER", "neo4j"),
            os.environ.get("NEO4J_PASSWORD", "holocron123"),
        ),
    )
    chunks = lancedb.connect("data/lancedb").open_table("chunks")
    graph = KnowledgeGraph(driver)
    index = VectorIndex(provider_from_env(dict(os.environ)), chunks)
    traced = bool(os.environ.get("LANGFUSE_PUBLIC_KEY"))
    toolsets = (
        Toolset("vector-only", frozenset({"search_chunks"})),
        Toolset("graph-only", TOOL_NAMES - {"search_chunks"}),
        Toolset("agent", None),
    )
    strategies = {
        t.name: HolocronAgent(graph=graph, index=index, traced=traced, toolset=t)
        for t in toolsets
        if args.strategy is None or t.name == args.strategy
    }
    writer = RunWriter(
        runs_root=root / "runs",
        run_id=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        corpus_lock_sha256=hashlib.sha256(Path("corpus.lock").read_bytes()).hexdigest(),
    )
    try:
        run_dir = asyncio.run(AnswerRunner(strategies, writer).run(golden, category))
        print(f"run persisted: {run_dir}")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
