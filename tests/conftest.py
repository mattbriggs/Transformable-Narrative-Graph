"""Shared pytest fixtures for the TNGS test suite.

Fixtures in this file are available to all test modules.  The key fixture
is ``mock_repo`` — a ``MagicMock`` of ``GraphRepository`` used in unit and
API tests to avoid any live Neo4j dependency (SRS §14.3).
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tng.api.main import app
from tng.api.dependencies import (
    get_ingest_service,
    get_pattern_service,
    get_render_service,
    get_repo,
    get_transform_service,
)
from tng.config import Settings
from tng.domain.enums import NarrativeStatus
from tng.domain.models import (
    Atom,
    Character,
    Event,
    GraphState,
    Narrative,
    Pattern,
    PatternInstance,
    Scene,
    Transform,
)
from tng.domain.enums import AtomKind, TransformAxis
from tng.repository.graph_repository import GraphRepository
from tng.services.ingest_service import IngestService
from tng.services.pattern_service import PatternService
from tng.services.render_service import RenderService
from tng.services.transform_service import TransformService


# ── Settings ─────────────────────────────────────────────────────────────────


@pytest.fixture
def test_settings() -> Settings:
    """Return a Settings instance with safe test defaults."""
    return Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="test",
        confidence_threshold=0.6,
        log_level="DEBUG",
    )


# ── Domain fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def sample_atom() -> Atom:
    """Return a minimal Atom for testing."""
    return Atom(
        id="atom-001",
        text="Alice walked slowly through the rain.",
        kind=AtomKind.DESCRIPTIVE,
        surface_order=0,
        confidence=0.9,
    )


@pytest.fixture
def sample_event() -> Event:
    """Return a minimal Event for testing."""
    return Event(
        id="event-001",
        verb="walk",
        tense="past",
        aspect="simple",
        confidence=0.75,
    )


@pytest.fixture
def sample_character() -> Character:
    """Return a minimal Character for testing."""
    return Character(id="char-001", name="Alice", role="protagonist")


@pytest.fixture
def sample_pattern() -> Pattern:
    """Return a Pattern template for testing."""
    return Pattern(
        id="pattern.gift_exchange",
        name="Gift Exchange",
        family="ritual",
        description="A subject gives an object to another party.",
    )


@pytest.fixture
def sample_scene(sample_atom, sample_event) -> Scene:
    """Return a Scene containing one atom and one event."""
    return Scene(
        id="scene-001",
        sequence=1,
        summary="Test scene.",
        atoms=[sample_atom],
        events=[sample_event],
    )


@pytest.fixture
def sample_narrative(sample_scene) -> Narrative:
    """Return a Narrative containing one scene."""
    return Narrative(
        id="narr-001",
        title="Test Narrative",
        status=NarrativeStatus.ATOMIZED,
        scenes=[sample_scene],
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )


@pytest.fixture
def sample_graph_state(sample_narrative) -> GraphState:
    """Return a GraphState wrapping the sample narrative."""
    return GraphState(narrative=sample_narrative, transforms=[])


# ── Mock repository ───────────────────────────────────────────────────────────


@pytest.fixture
def mock_repo(sample_narrative, sample_pattern) -> MagicMock:
    """Return a MagicMock GraphRepository with sensible defaults."""
    repo = MagicMock(spec=GraphRepository)
    repo.ping.return_value = True
    repo.get_narrative.return_value = sample_narrative
    repo.get_pattern.return_value = sample_pattern
    repo.list_patterns.return_value = [sample_pattern]
    repo.list_pattern_instances.return_value = []
    repo.archive_narrative.return_value = True
    repo.get_transform.return_value = {
        "id": "t-001",
        "scene_id": "scene-001",
        "produced_type": ["Perspective"],
        "produced_id": "pov-t-001",
    }
    repo.get_transform_history.return_value = []
    repo.get_scene_ids.return_value = ["scene-001"]
    repo.revise_atom.return_value = True
    repo.get_atom_revisions.return_value = []
    repo.get_graph_state.return_value = GraphState(
        narrative=sample_narrative, transforms=[]
    )
    return repo


# ── Service fixtures (use mock_repo) ─────────────────────────────────────────


@pytest.fixture
def ingest_service(mock_repo, test_settings) -> IngestService:
    """Return an IngestService backed by the mock repository."""
    pattern_service = PatternService(mock_repo)
    return IngestService(mock_repo, pattern_service, test_settings)


@pytest.fixture
def pattern_service(mock_repo) -> PatternService:
    """Return a PatternService backed by the mock repository."""
    return PatternService(mock_repo)


@pytest.fixture
def transform_service(mock_repo) -> TransformService:
    """Return a TransformService backed by the mock repository."""
    return TransformService(mock_repo)


@pytest.fixture
def render_service(mock_repo) -> RenderService:
    """Return a RenderService backed by the mock repository."""
    return RenderService(mock_repo)


# ── FastAPI TestClient (injects mock dependencies) ────────────────────────────


@pytest.fixture
def api_client(mock_repo) -> TestClient:
    """Return a TestClient with all repo dependencies overridden.

    No live Neo4j instance is required.
    """
    settings = Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="test",
        confidence_threshold=0.6,
    )
    pattern_svc = PatternService(mock_repo)
    ingest_svc = IngestService(mock_repo, pattern_svc, settings)
    transform_svc = TransformService(mock_repo)
    render_svc = RenderService(mock_repo)

    def _mock_repo():
        yield mock_repo

    app.dependency_overrides[get_repo] = _mock_repo
    app.dependency_overrides[get_ingest_service] = lambda: ingest_svc
    app.dependency_overrides[get_pattern_service] = lambda: pattern_svc
    app.dependency_overrides[get_transform_service] = lambda: transform_svc
    app.dependency_overrides[get_render_service] = lambda: render_svc

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
