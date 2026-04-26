"""Health check router — liveness and readiness probes (SRS FR-17).

``/v1/health/live`` — always returns 200; confirms the process is running.
``/v1/health/ready`` — returns 200 when Neo4j responds, 503 otherwise.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from tng.api.schemas import HealthResponse
from tng.repository.graph_repository import GraphRepository
from tng.api.dependencies import get_repo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/health", tags=["health"])


@router.get("/live", response_model=HealthResponse, summary="Liveness probe")
def liveness() -> HealthResponse:
    """Return 200 to confirm the process is alive.

    :returns: ``{"status": "ok"}``.
    """
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=HealthResponse,
    summary="Readiness probe",
    responses={503: {"description": "Neo4j unavailable"}},
)
def readiness(repo: GraphRepository = Depends(get_repo)) -> HealthResponse:
    """Return 200 when Neo4j is reachable; 503 otherwise.

    :param repo: Injected graph repository.
    :returns: Health status with Neo4j connectivity detail.
    :raises HTTPException: 503 when Neo4j is unreachable.
    """
    try:
        repo.ping()
        return HealthResponse(status="ok", neo4j="reachable")
    except Exception as exc:
        logger.warning("Readiness check failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "degraded", "neo4j": str(exc)},
        )
