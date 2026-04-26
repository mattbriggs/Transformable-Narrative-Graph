"""Narratives router — GET and DELETE for Narrative resources (SRS §10.1).

``GET /v1/narratives/{id}`` retrieves a narrative summary including optional
include parameters for patterns and transforms.
``DELETE /v1/narratives/{id}`` archives a narrative.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from tng.api.dependencies import get_repo
from tng.api.schemas import NarrativeSummary, PatternInstanceRecord
from tng.repository.graph_repository import GraphRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/narratives", tags=["narratives"])


@router.get(
    "/{narrative_id}",
    response_model=NarrativeSummary,
    summary="Retrieve narrative state",
)
def get_narrative(
    narrative_id: str,
    include: Annotated[list[str], Query()] = [],
    repo: GraphRepository = Depends(get_repo),
) -> NarrativeSummary:
    """Retrieve a narrative's current state and optional related data.

    :param narrative_id: The narrative's unique ID.
    :param include: Optional list of related data to include (``patterns``,
        ``transforms``).
    :param repo: Injected graph repository.
    :returns: ``NarrativeSummary`` for the requested narrative.
    :raises HTTPException: 404 when the narrative does not exist.
    """
    narrative = repo.get_narrative(narrative_id)
    if narrative is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Narrative {narrative_id!r} not found.",
        )
    return NarrativeSummary(
        id=narrative.id,
        title=narrative.title,
        status=narrative.status.value,
        source_ref=narrative.source_ref,
        scene_count=len(narrative.scenes),
        created_at=narrative.created_at,
    )


@router.delete(
    "/{narrative_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive a narrative",
)
def archive_narrative(
    narrative_id: str,
    repo: GraphRepository = Depends(get_repo),
) -> None:
    """Archive a narrative (sets status to ``archived``).

    :param narrative_id: The narrative to archive.
    :param repo: Injected graph repository.
    :raises HTTPException: 404 when the narrative does not exist.
    """
    found = repo.archive_narrative(narrative_id)
    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Narrative {narrative_id!r} not found.",
        )
