"""Composition root for the eval harness — constructs resources, reads env (ADR-0004).

Answer phase (persists a run dir under eval/runs/):

    uv run python -m eval answer [--category single-hop] [--strategy vector-only]

Report phase (deterministic citation check, free, re-runnable):

    uv run python -m eval report [--run 20260710T164433Z]

Judge phase (LLM verdicts via a logged-in claude CLI; never re-runs strategies):

    uv run python -m eval judge [--run 20260710T164433Z]

Reports the latest run by default, against the latest Baseline in
eval/baselines/ when one exists (promotion lands with #16).
"""

import argparse
import asyncio
import hashlib
import os
import sys
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
    report = sub.add_parser("report", help="citation-check a persisted run and render the table vs the Baseline")
    report.add_argument("--run", help="run id under eval/runs (default: latest completed)")
    judge = sub.add_parser(
        "judge",
        help="judge a persisted run via claude -p (Opus, pinned rubric); free; "
        "existing verdicts are kept — delete *.verdict.json to re-judge",
    )
    judge.add_argument("--run", help="run id under eval/runs (default: latest completed)")
    args = parser.parse_args()

    root = Path(__file__).parent
    golden = GoldenSet.load(root / "golden_set.json")

    if args.command == "report":
        _report(root, golden, args.run)
        return
    if args.command == "judge":
        _judge(root, golden, args.run)
        return

    import lancedb
    from neo4j import GraphDatabase

    from agent.holocron import TOOL_NAMES, HolocronAgent, Toolset
    from core.embeddings import provider_from_env
    from eval.answer import AnswerRunner, RunWriter
    from retrieval import KnowledgeGraph, VectorIndex

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
    if {t.name for t in toolsets} != set(STRATEGY_NAMES):
        raise RuntimeError("STRATEGY_NAMES drifted from the toolsets built here — --strategy would run nothing")
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


def _report(root: Path, golden: GoldenSet, run_id: str | None) -> None:
    from eval.report import PersistedRun, ReportRenderer

    run_dir = (root / "runs" / run_id) if run_id else _latest_completed(root / "runs")
    if run_dir is None:
        raise SystemExit("no completed run under eval/runs — run `python -m eval answer` first")
    baseline_dir = _latest_completed(root / "baselines")
    run = PersistedRun.load(run_dir, golden)
    baseline = PersistedRun.load(baseline_dir, golden) if baseline_dir else None
    text = ReportRenderer().render(run, baseline)
    (run_dir / "report.md").write_text(text)
    print(text)


def _judge(root: Path, golden: GoldenSet, run_id: str | None) -> None:
    from eval.judge import ClaudeJudge, JudgeRunner, JudgeUnavailableError

    run_dir = (root / "runs" / run_id) if run_id else _latest_completed(root / "runs")
    if run_dir is None:
        raise SystemExit("no completed run under eval/runs — run `python -m eval answer` first")
    # No ANTHROPIC_API_KEY: the judge must bill the subscription, not the API (spec #11).
    judge_env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    try:
        judged = JudgeRunner(ClaudeJudge(judge_env)).run(run_dir, golden)
    except JudgeUnavailableError as exc:
        raise SystemExit(f"judge unavailable: {exc}") from None
    print(f"{judged} new verdict(s) in {run_dir}")


def _latest_completed(root: Path) -> Path | None:
    """Newest run dir holding a manifest; incomplete (interrupted) dirs are skipped loudly."""
    dirs = sorted(root.glob("*")) if root.exists() else []
    completed = [d for d in dirs if (d / "run.json").exists()]
    if completed and dirs and dirs[-1] not in completed:
        print(
            f"WARNING: skipping incomplete run {dirs[-1].name} (no manifest); reporting {completed[-1].name}",
            file=sys.stderr,
        )
    return completed[-1] if completed else None


if __name__ == "__main__":
    main()
