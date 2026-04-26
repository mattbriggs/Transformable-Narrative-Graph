"""Patterns router — register and query pattern templates (SRS FR-9 to FR-11).

``POST /v1/patterns`` registers a new pattern template.
``GET /v1/patterns`` lists all patterns, optionally filtered by family.
``GET /v1/patterns/{id}/instances`` lists concrete pattern realisations.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from tng.api.dependencies import get_pattern_service, get_repo
from tng.api.schemas import PatternInstanceRecord, PatternRecord, PatternRequest
from tng.domain.models import Pattern
from tng.ingest.annotator import make_id
from tng.repository.graph_repository import GraphRepository
from tng.services.pattern_service import PatternService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/patterns", tags=["patterns"])


@router.post(
    "",
    response_model=PatternRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Register a pattern template",
)
def create_pattern(
    body: PatternRequest,
    repo: GraphRepository = Depends(get_repo),
) -> PatternRecord:
    """Register a new pattern template in the graph library.

    :param body: Pattern registration request.
    :param repo: Injected graph repository.
    :returns: The created ``PatternRecord``.
    """
    pattern = Pattern(
        id=body.id or f"pattern.{make_id()}",
        name=body.name,
        family=body.family,
        description=body.description,
    )
    repo.save_pattern(pattern)
    return PatternRecord(
        id=pattern.id,
        name=pattern.name,
        family=pattern.family,
        description=pattern.description,
    )


@router.get(
    "",
    response_model=list[PatternRecord],
    summary="List pattern templates",
)
def list_patterns(
    family: str | None = Query(default=None, description="Filter by pattern family"),
    repo: GraphRepository = Depends(get_repo),
) -> list[PatternRecord]:
    """List all registered pattern templates.

    :param family: Optional family filter.
    :param repo: Injected graph repository.
    :returns: List of ``PatternRecord`` items.
    """
    patterns = repo.list_patterns(family=family)
    return [
        PatternRecord(
            id=p.id,
            name=p.name,
            family=p.family,
            description=p.description,
        )
        for p in patterns
    ]


@router.get(
    "/{pattern_id}/instances",
    response_model=list[PatternInstanceRecord],
    summary="List pattern instances for a pattern",
)
def list_instances(
    pattern_id: str,
    narrative_id: str = Query(..., description="Narrative to query"),
    repo: GraphRepository = Depends(get_repo),
) -> list[PatternInstanceRecord]:
    """List all concrete realisations of a pattern in a narrative.

    :param pattern_id: The pattern template ID.
    :param narrative_id: The narrative to search.
    :param repo: Injected graph repository.
    :returns: List of ``PatternInstanceRecord`` items.
    :raises HTTPException: 404 when the pattern template does not exist.
    """
    pattern = repo.get_pattern(pattern_id)
    if pattern is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pattern {pattern_id!r} not found.",
        )
    all_instances = repo.list_pattern_instances(narrative_id)
    return [
        PatternInstanceRecord(**inst)
        for inst in all_instances
        if inst["pattern_id"] == pattern_id
    ]
