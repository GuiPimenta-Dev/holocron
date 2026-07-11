"""Shared fixtures — the tests' composition root (ADR-0004).

Retrieval tests run against a real Neo4j + pgvector (testing doctrine: no
mocks). Locally the full corpus is already loaded — tests assert on entities
that are both in the corpus and in tests/fixtures. In CI the Neo4j service
starts empty, so we seed it from the saved wikitext fixtures; the vector tests
skip (no index, no embedding key). Never wipes a non-empty graph.
"""

import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()  # local runs pick up Neo4j creds + embedding keys; CI has neither

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def neo4j_driver():
    """A live Neo4j driver over a graph containing the fixture entities, or skip."""
    from neo4j import GraphDatabase
    from neo4j.exceptions import ServiceUnavailable

    driver = GraphDatabase.driver(
        os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        auth=(
            os.environ.get("NEO4J_USER", "neo4j"),
            os.environ.get("NEO4J_PASSWORD", "holocron123"),
        ),
    )
    try:
        with driver.session() as session:
            count = session.run("MATCH (e:Entity) RETURN count(e)").single(strict=True)[0]
            if count == 0:
                _seed_from_fixtures(driver)
            else:
                have = session.run("MATCH (e:Entity {name: 'Kit Fisto'}) RETURN count(e)").single(strict=True)[0]
                if have == 0:
                    pytest.skip("Neo4j graph is populated but lacks the fixture entities")
    except (ServiceUnavailable, OSError):
        pytest.skip("Neo4j not reachable — start it with `docker compose up -d neo4j`")
    yield driver
    driver.close()


def _seed_from_fixtures(driver) -> None:
    from ingest.graph import GraphLoader
    from ingest.parse import PageParser

    parser = PageParser()
    entities = []
    for p in sorted(FIXTURES.glob("*.json")):
        page = json.loads(p.read_text())
        e = parser.parse(page["title"], page["wikitext"], page["categories"])
        if e:
            entities.append(e)
    GraphLoader(driver).load(entities, {})


@pytest.fixture(scope="session")
def knowledge_graph(neo4j_driver):
    from retrieval import KnowledgeGraph

    return KnowledgeGraph(neo4j_driver)


@pytest.fixture(scope="session")
def vector_index():
    """A VectorIndex over the real pgvector chunk index, or skip when it can't exist."""
    from core.embeddings import provider_from_env

    if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("VOYAGE_API_KEY")):
        pytest.skip("no embedding API key — VectorIndex embeds the query")
    import psycopg

    from retrieval import VectorIndex

    dsn = os.environ.get("HOLOCRON_PG_DSN", "postgresql://postgres:postgres@localhost:5434/holocron")
    try:
        conn = psycopg.connect(dsn, autocommit=True)
        if conn.execute("SELECT to_regclass('chunks')").fetchone()[0] is None:  # pyright: ignore[reportOptionalSubscript]
            pytest.skip("pgvector index not built — run `uv run python -m ingest embed`")
    except psycopg.OperationalError:
        pytest.skip("Postgres not reachable — start it with `docker compose up -d postgres`")
    yield VectorIndex(provider_from_env(dict(os.environ)), conn)
    conn.close()
