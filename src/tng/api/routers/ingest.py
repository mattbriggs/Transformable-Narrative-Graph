"""Ingest router — ``POST /v1/notes/import`` (SRS FR-1 to FR-8).

Accepts raw text, Markdown, or pre-structured JSON payloads, runs the full
ingest pipeline, and returns a summary of the persisted graph state.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from tng.api.dependencies import get_ingest_service
from tng.api.schemas import IngestRequest, IngestResponse
from tng.ingest.annotator import make_id
from tng.services.ingest_service import IngestPayload, IngestService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/notes", tags=["ingest"])


@router.post(
    "/import",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest and atomize notes",
)
def import_notes(
    body: IngestRequest,
    svc: IngestService = Depends(get_ingest_service),
) -> IngestResponse:
    """Ingest raw notes and build the narrative graph.

    Accepts plain text, Markdown, or pre-structured JSON.  Returns a
    summary of all nodes written and any items flagged for human review.

    :param body: The ingest request payload.
    :param svc: Injected ``IngestService``.
    :returns: ``IngestResponse`` with node counts.
    :raises HTTPException: 400 on validation errors, 500 on unexpected failures.
    """
    payload = IngestPayload(
        title=body.title,
        text=body.text,
        narrative_id=body.narrative_id or make_id(),
        source_ref=body.source_ref,
        format=body.format,
    )
    try:
        result = svc.ingest(payload)
    except Exception as exc:
        logger.error("Ingest failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    return IngestResponse(
        narrative_id=result.narrative_id,
        scene_count=result.scene_count,
        atom_count=result.atom_count,
        event_count=result.event_count,
        character_count=result.character_count,
        pattern_count=result.pattern_count,
        flagged_count=result.flagged_count,
    )
