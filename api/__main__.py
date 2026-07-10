"""Composition root — the only place that constructs resources (ADR-0004).

Serve the agent locally:  uv run python -m api

Then:  curl -N localhost:8000/ask -X POST -H 'content-type: application/json' \
           -d '{"question": "What species is Kit Fisto?"}'
"""

import os

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()

    import lancedb
    import uvicorn
    from neo4j import GraphDatabase

    from agent.holocron import HolocronAgent
    from api.app import create_app
    from core.embeddings import provider_from_env
    from retrieval import KnowledgeGraph, VectorIndex

    driver = GraphDatabase.driver(
        os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        auth=(
            os.environ.get("NEO4J_USER", "neo4j"),
            os.environ.get("NEO4J_PASSWORD", "holocron123"),
        ),
    )
    chunks = lancedb.connect("data/lancedb").open_table("chunks")
    agent = HolocronAgent(
        graph=KnowledgeGraph(driver),
        index=VectorIndex(provider_from_env(dict(os.environ)), chunks),
        traced=bool(os.environ.get("LANGFUSE_PUBLIC_KEY")),
    )
    try:
        uvicorn.run(create_app(agent), host="127.0.0.1", port=8000)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
