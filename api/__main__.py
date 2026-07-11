"""Composition root — the only place that constructs resources (ADR-0004).

Serve the agent locally:  uv run python -m api

Then:  curl -N localhost:8000/ask -X POST -H 'content-type: application/json' \
           -d '{"question": "What species is Kit Fisto?"}'
"""

import os

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()

    import psycopg
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
    pg = psycopg.connect(
        os.environ.get("HOLOCRON_PG_DSN", "postgresql://postgres:postgres@localhost:5434/holocron"),
        autocommit=True,  # read-only serving: no eternal snapshot, errors never poison the connection
    )
    agent = HolocronAgent(
        graph=KnowledgeGraph(driver),
        index=VectorIndex(provider_from_env(dict(os.environ)), pg),
        traced=bool(os.environ.get("LANGFUSE_PUBLIC_KEY")),
    )
    try:
        ui_origin = os.environ.get("HOLOCRON_UI_ORIGIN", "http://localhost:3000")
        uvicorn.run(create_app(agent, ui_origin), host="127.0.0.1", port=8000)
    finally:
        driver.close()
        pg.close()


if __name__ == "__main__":
    main()
