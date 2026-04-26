"""FastAPI dependency providers.

All infrastructure objects (driver, repository, services) are created once
at application startup and injected via FastAPI's dependency injection system.
Tests override these dependencies using ``app.dependency_overrides`` so that
no live Neo4j instance is required for API-layer tests (SRS §14.3).

Module-level singletons
-----------------------
``_driver`` and ``_repo`` are initialised in ``lifespan()`` and closed at
shutdown.  They are never ``None`` during normal request handling — the
startup hook ensures Neo4j is reachable before the app accepts traffic.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Generator

from fastapi import Depends, FastAPI

from tng.config import get_settings
from tng.repository.graph_repository import GraphRepository, create_driver
from tng.services.ingest_service import IngestService
from tng.services.pattern_service import PatternService
from tng.services.render_service import RenderService
from tng.services.transform_service import TransformService

logger = logging.getLogger(__name__)

_repo: GraphRepository | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage driver and schema initialisation for the application lifetime.

    :param app: The FastAPI application instance.
    """
    global _repo
    settings = get_settings()
    driver = create_driver(settings)
    _repo = GraphRepository(driver, database=settings.neo4j_database)
    try:
        _repo.apply_schema()
        logger.info("TNGS application started.")
    except Exception as exc:
        logger.error("Schema application failed at startup: %s", exc)
    yield
    if _repo:
        _repo.close()
    logger.info("TNGS application shut down.")


def get_repo() -> Generator[GraphRepository, None, None]:
    """Yield the shared ``GraphRepository`` instance.

    :yields: The application-scoped ``GraphRepository``.
    :raises RuntimeError: If called before startup completes.
    """
    if _repo is None:
        raise RuntimeError("GraphRepository not initialised.")
    yield _repo


def get_ingest_service(
    repo: GraphRepository = Depends(get_repo),
) -> IngestService:
    """Provide an ``IngestService`` instance.

    :param repo: Injected repository (via FastAPI dependency).
    :returns: A configured ``IngestService``.
    """
    settings = get_settings()
    pattern_service = PatternService(repo)
    return IngestService(repo, pattern_service, settings)


def get_pattern_service(
    repo: GraphRepository = Depends(get_repo),
) -> PatternService:
    """Provide a ``PatternService`` instance.

    :param repo: Injected repository (via FastAPI dependency).
    :returns: A configured ``PatternService``.
    """
    return PatternService(repo)


def get_transform_service(
    repo: GraphRepository = Depends(get_repo),
) -> TransformService:
    """Provide a ``TransformService`` instance.

    :param repo: Injected repository (via FastAPI dependency).
    :returns: A configured ``TransformService``.
    """
    return TransformService(repo)


def get_render_service(
    repo: GraphRepository = Depends(get_repo),
) -> RenderService:
    """Provide a ``RenderService`` instance.

    :param repo: Injected repository (via FastAPI dependency).
    :returns: A configured ``RenderService``.
    """
    return RenderService(repo)
