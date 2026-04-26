"""Transforms router — apply transformations and retrieve audit records (SRS FR-12 to FR-13).

``POST /v1/transforms/apply`` applies one of the six transformation axes.
``GET /v1/transforms/{id}`` retrieves a single Transform audit record.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from tng.api.dependencies import get_transform_service
from tng.api.schemas import (
    BulkTransformRequest,
    BulkTransformResponse,
    TransformRecord,
    TransformRequest,
    TransformResponse,
)
from tng.repository.graph_repository import GraphRepository
from tng.api.dependencies import get_repo
from tng.services.transform_service import (
    TransformRequest as SvcTransformRequest,
    TransformService,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/transforms", tags=["transforms"])


@router.post(
    "/apply",
    response_model=TransformResponse,
    summary="Apply an axis transformation",
)
def apply_transform(
    body: TransformRequest,
    svc: TransformService = Depends(get_transform_service),
) -> TransformResponse:
    """Apply a transformation axis to a scene.

    Parameters are validated against the axis-specific schema before any
    graph write occurs.  On success a ``Transform`` audit node is created
    and the old state node is detached (but not deleted).

    :param body: Transformation request.
    :param svc: Injected ``TransformService``.
    :returns: ``TransformResponse`` with the new transform's ID.
    :raises HTTPException: 400 on validation errors; 500 on unexpected failures.
    """
    try:
        result = svc.apply(
            SvcTransformRequest(
                scene_id=body.scene_id,
                axis=body.axis,
                parameters=body.parameters,
                operator=body.operator,
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Transform failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    return TransformResponse(
        transform_id=result.transform_id,
        scene_id=result.scene_id,
        axis=result.axis,
        produced_id=result.produced_id,
        status=result.status,
    )


@router.post(
    "/apply-bulk",
    response_model=BulkTransformResponse,
    summary="Apply an axis transformation to every scene in a narrative",
)
def apply_bulk_transform(
    body: BulkTransformRequest,
    svc: TransformService = Depends(get_transform_service),
) -> BulkTransformResponse:
    """Apply a transformation axis to every scene in a narrative in one call.

    Parameters are validated once before any write occurs.  On success a
    ``Transform`` audit node is created per scene.

    :param body: Bulk transformation request.
    :param svc: Injected ``TransformService``.
    :returns: ``BulkTransformResponse`` with per-scene results.
    :raises HTTPException: 400 on validation errors or no scenes found;
        500 on unexpected failures.
    """
    try:
        results = svc.apply_bulk(
            narrative_id=body.narrative_id,
            axis=body.axis,
            parameters=body.parameters,
            operator=body.operator,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Bulk transform failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    return BulkTransformResponse(
        narrative_id=body.narrative_id,
        applied_count=len(results),
        results=[
            TransformResponse(
                transform_id=r.transform_id,
                scene_id=r.scene_id,
                axis=r.axis,
                produced_id=r.produced_id,
                status=r.status,
            )
            for r in results
        ],
    )


@router.get(
    "/{transform_id}",
    response_model=TransformRecord,
    summary="Retrieve a transform audit record",
)
def get_transform(
    transform_id: str,
    repo: GraphRepository = Depends(get_repo),
) -> TransformRecord:
    """Retrieve the audit record for a single Transform node.

    :param transform_id: The transform's unique ID.
    :param repo: Injected graph repository.
    :returns: ``TransformRecord``.
    :raises HTTPException: 404 when the transform does not exist.
    """
    record = repo.get_transform(transform_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transform {transform_id!r} not found.",
        )
    return TransformRecord(
        id=transform_id,
        scene_id=record.get("scene_id"),
        produced_type=record.get("produced_type"),
        produced_id=record.get("produced_id"),
    )
