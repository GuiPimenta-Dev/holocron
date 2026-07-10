"""Shared fixtures. Tools tests run against a real Neo4j (testing doctrine: no mocks).

Locally the full corpus graph is already loaded — tests assert on entities that are
both in the corpus and in tests/fixtures. In CI the service container starts empty,
so we seed it from the saved wikitext fixtures. Never wipes a non-empty graph.
"""

import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()  # local runs pick up Neo4j creds + embedding keys; CI has neither

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def graph():
    """Yields nothing; guarantees a Neo4j with the fixture entities, or skips."""
    from neo4j.exceptions import ServiceUnavailable

    import ingest.graph as graph_mod
    from ingest.parse import parse_page

    try:
        with graph_mod.driver() as drv, drv.session() as session:
            count = session.run("MATCH (e:Entity) RETURN count(e)").single(strict=True)[0]
            if count == 0:
                entities = []
                for p in sorted(FIXTURES.glob("*.json")):
                    page = json.loads(p.read_text())
                    e = parse_page(page["title"], page["wikitext"], page["categories"])
                    if e:
                        entities.append(e)
                graph_mod.load(entities, {})
            else:
                have = session.run("MATCH (e:Entity {name: 'Kit Fisto'}) RETURN count(e)").single(
                    strict=True
                )[0]
                if have == 0:
                    pytest.skip("Neo4j graph is populated but lacks the fixture entities")
    except (ServiceUnavailable, OSError):
        pytest.skip("Neo4j not reachable — start it with `docker compose up -d neo4j`")
    yield


@pytest.fixture(scope="session")
def vector_index():
    """Skips unless the real LanceDB index and an embedding key are available."""
    if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("VOYAGE_API_KEY")):
        pytest.skip("no embedding API key — search_chunks embeds the query")
    if not Path("data/lancedb/chunks.lance").exists():
        pytest.skip("LanceDB index not built — run `uv run python -m ingest embed`")
