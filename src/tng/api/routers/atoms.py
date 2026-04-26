"""Atoms router — atom text revision and revision history (iteration 2).

``PATCH /v1/atoms/{atom_id}``         — create a new text revision (non-destructive).
``GET  /v1/atoms/{atom_id}/revisions`` — list full revision history.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from tng.api.dependencies import get_repo
from tng.api.schemas import (
    AtomRevisionListResponse,
    AtomRevisionRecord,
    AtomRevisionResponse,
    AtomReviseRequest,
)
from tng.ingest.annotator import make_id
from tng.repository.graph_repository import GraphRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/atoms", tags=["atoms"])


@router.patch(
    "/{atom_id}",
    response_model=AtomRevisionResponse,
    summary="Revise atom text",
)
def revise_atom(
    atom_id: str,
    body: AtomReviseRequest,
    repo: GraphRepository = Depends(get_repo),
) -> AtomRevisionResponse:
    """Create a new text revision for an atom (non-destructive).

    The original atom text and all prior revisions are preserved in the
    graph.  The new revision becomes the active text used by all renderers.

    :param atom_id: Target atom ID.
    :param body: Revision request with new text and optional reason.
    :param repo: Injected graph repository.
    :returns: ``AtomRevisionResponse`` with the new revision's ID.
    :raises HTTPException: 404 when the atom does not exist.
    """
    revision_id = make_id()
    found = repo.revise_atom(
        atom_id=atom_id,
        revision_id=revision_id,
        text=body.text,
        revised_at=datetime.utcnow(),
        operator=body.operator,
        reason=body.reason,
    )
    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Atom {atom_id!r} not found.",
        )
    logger.info("Atom %r revised → revision %r", atom_id, revision_id)
    return AtomRevisionResponse(
        atom_id=atom_id,
        revision_id=revision_id,
        text=body.text,
    )


@router.get(
    "/{atom_id}/revisions",
    response_model=AtomRevisionListResponse,
    summary="List atom revision history",
)
def get_atom_revisions(
    atom_id: str,
    repo: GraphRepository = Depends(get_repo),
) -> AtomRevisionListResponse:
    """Return the full revision history for an atom, oldest first.

    :param atom_id: Target atom ID.
    :param repo: Injected graph repository.
    :returns: ``AtomRevisionListResponse`` with ordered revision list.
    """
    raw = repo.get_atom_revisions(atom_id)
    revisions = [
        AtomRevisionRecord(
            id=r["id"],
            atom_id=r["atom_id"],
            text=r["text"],
            revised_at=r["revised_at"] if isinstance(r["revised_at"], datetime)
            else datetime.fromisoformat(str(r["revised_at"])),
            operator=r.get("operator", "system"),
            reason=r.get("reason", ""),
        )
        for r in raw
    ]
    return AtomRevisionListResponse(atom_id=atom_id, revisions=revisions)
