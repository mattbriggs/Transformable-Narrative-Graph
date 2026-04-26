"""Integration tests against a live Neo4j instance.

These tests require a running Neo4j container and are marked ``integration``
so that they are excluded from the default CI unit-test run.

Run with::

    pytest -m integration tests/integration/

The ``NEO4J_URI``, ``NEO4J_USER``, and ``NEO4J_PASSWORD`` environment
variables must be set, or a ``testcontainers`` Neo4j fixture must be used.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def live_repo():
    """Yield a ``GraphRepository`` connected to a real Neo4j instance.

    Skips automatically if ``NEO4J_URI`` is not set in the environment.
    """
    neo4j_uri = os.environ.get("NEO4J_URI")
    if not neo4j_uri:
        pytest.skip("NEO4J_URI not set — skipping integration tests.")

    from tng.config import Settings
    from tng.repository.graph_repository import GraphRepository, create_driver

    settings = Settings(
        neo4j_uri=neo4j_uri,
        neo4j_user=os.environ.get("NEO4J_USER", "neo4j"),
        neo4j_password=os.environ.get("NEO4J_PASSWORD", "neo4j"),
    )
    driver = create_driver(settings)
    repo = GraphRepository(driver, database=settings.neo4j_database)
    repo.apply_schema()
    yield repo
    repo.close()


class TestGraphRepositoryIntegration:
    """Live-database repository integration tests."""

    def test_ping_returns_true(self, live_repo):
        assert live_repo.ping() is True

    def test_save_and_get_narrative(self, live_repo):
        from tng.domain.models import Narrative
        narrative = Narrative(id="int-narr-001", title="Integration Test Narrative")
        live_repo.save_narrative(narrative)
        retrieved = live_repo.get_narrative("int-narr-001")
        assert retrieved is not None
        assert retrieved.title == "Integration Test Narrative"

    def test_save_and_get_pattern(self, live_repo):
        from tng.domain.models import Pattern
        pattern = Pattern(
            id="pattern.int-test",
            name="Integration Test Pattern",
            family="ritual",
            description="Test.",
        )
        live_repo.save_pattern(pattern)
        retrieved = live_repo.get_pattern("pattern.int-test")
        assert retrieved is not None
        assert retrieved.name == "Integration Test Pattern"

    def test_list_patterns_returns_saved(self, live_repo):
        patterns = live_repo.list_patterns()
        assert any(p.id == "pattern.int-test" for p in patterns)

    def test_archive_narrative(self, live_repo):
        from tng.domain.models import Narrative
        narrative = Narrative(id="int-narr-002", title="To Archive")
        live_repo.save_narrative(narrative)
        result = live_repo.archive_narrative("int-narr-002")
        assert result is True

    def test_archive_missing_narrative_returns_false(self, live_repo):
        result = live_repo.archive_narrative("does-not-exist")
        assert result is False
