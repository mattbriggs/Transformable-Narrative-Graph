"""Render router — generate output from graph state (SRS FR-15, FR-19).

``POST /v1/render/{id}`` renders the narrative to the requested format.
Supports five output types: prose, diff, json, cypher, and markdown.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from tng.api.dependencies import get_render_service
from tng.api.schemas import RenderRequest, RenderResponse
from tng.services.render_service import RenderService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/render", tags=["render"])


@router.post(
    "/{narrative_id}",
    response_model=RenderResponse,
    summary="Render current graph state",
)
def render_narrative(
    narrative_id: str,
    body: RenderRequest,
    svc: RenderService = Depends(get_render_service),
) -> RenderResponse:
    """Render a narrative to the requested output format.

    :param narrative_id: The narrative to render.
    :param body: Render type and optional parameters.
    :param svc: Injected ``RenderService``.
    :returns: ``RenderResponse`` with rendered content.
    :raises HTTPException: 404 when the narrative does not exist;
        500 on unexpected renderer failures.
    """
    try:
        output = svc.render(narrative_id, body.type, body.params)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown render type: {exc}",
        )
    except Exception as exc:
        logger.error("Render failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    return RenderResponse(
        narrative_id=narrative_id,
        render_type=body.type.value,
        content=output.content,
        content_type=output.content_type,
    )
