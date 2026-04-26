"""API request and response schemas (DTOs).

All schemas are Pydantic ``BaseModel`` subclasses.  They are distinct from
the domain models in ``tng.domain.models`` — they carry only the data
exposed via the HTTP API and use snake_case field names matching the JSON
conventions described in SRS §10.1.

Validation occurs at the FastAPI boundary before any service call; no
raw request dict ever reaches a service or repository.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from tng.domain.enums import RenderType, TransformAxis


# ── Ingest ────────────────────────────────────────────────────────────────────


class CodeTagAnnotation(BaseModel):
    """Pre-annotation code tag hint embedded in an ingest payload.

    :ivar atom_index: Zero-based position of the target atom in the scene.
    :ivar code: Barthesian code category string.
    """

    atom_index: int
    code: str


class SceneInput(BaseModel):
    """One scene block within a structured JSON ingest payload.

    :ivar scene_id: Optional scene ID (generated if absent).
    :ivar sequence: Ordinal position within the narrative.
    :ivar summary: Optional human-readable scene summary.
    :ivar text: Raw prose to atomize.
    :ivar pattern_hints: Optional list of pattern name hints.
    :ivar character_refs: Optional list of pre-identified character names.
    :ivar code_tags: Optional pre-annotation code tag hints.
    """

    scene_id: str | None = None
    sequence: int = 1
    summary: str = ""
    text: str
    pattern_hints: list[str] = Field(default_factory=list)
    character_refs: list[str] = Field(default_factory=list)
    code_tags: list[CodeTagAnnotation] = Field(default_factory=list)


class IngestRequest(BaseModel):
    """Request body for ``POST /v1/notes/import``.

    :ivar title: Narrative title.
    :ivar text: Raw text for plain-text or Markdown ingest.
    :ivar narrative_id: Optional; generated if absent.
    :ivar source_ref: Optional provenance reference.
    :ivar format: Input format: ``"text"``, ``"markdown"``, ``"json"``, or ``"csv"``.
    :ivar scenes: Pre-structured scenes (used when ``format="json"``).
    """

    title: str
    text: str = ""
    narrative_id: str | None = None
    source_ref: str = ""
    format: str = "text"
    scenes: list[SceneInput] = Field(default_factory=list)


class IngestResponse(BaseModel):
    """Response body for ``POST /v1/notes/import``.

    :ivar narrative_id: ID of the created or updated Narrative.
    :ivar scene_count: Number of scenes persisted.
    :ivar atom_count: Total atoms written.
    :ivar event_count: Total events written.
    :ivar character_count: Total characters written.
    :ivar pattern_count: Number of pattern instances created.
    :ivar flagged_count: Nodes flagged for human review.
    """

    narrative_id: str
    scene_count: int
    atom_count: int
    event_count: int
    character_count: int
    pattern_count: int
    flagged_count: int


# ── Narrative ─────────────────────────────────────────────────────────────────


class NarrativeSummary(BaseModel):
    """Response body for ``GET /v1/narratives/{id}``.

    :ivar id: Narrative ID.
    :ivar title: Narrative title.
    :ivar status: Life-cycle status string.
    :ivar source_ref: Provenance reference.
    :ivar scene_count: Number of scenes.
    :ivar created_at: UTC creation timestamp.
    """

    id: str
    title: str
    status: str
    source_ref: str
    scene_count: int
    created_at: datetime


# ── Patterns ──────────────────────────────────────────────────────────────────


class PatternRequest(BaseModel):
    """Request body for ``POST /v1/patterns``.

    :ivar id: Optional explicit ID; generated if absent.
    :ivar name: Pattern name.
    :ivar family: Family tag (e.g. ``"ritual"``).
    :ivar description: Prose description.
    """

    id: str | None = None
    name: str
    family: str
    description: str = ""


class PatternRecord(BaseModel):
    """Response record for a pattern template.

    :ivar id: Pattern ID.
    :ivar name: Pattern name.
    :ivar family: Family tag.
    :ivar description: Description.
    """

    id: str
    name: str
    family: str
    description: str


class PatternInstanceRecord(BaseModel):
    """A single pattern instance record.

    :ivar instance_id: PatternInstance ID.
    :ivar slot: Structural slot label.
    :ivar confidence: Match confidence.
    :ivar pattern_id: Parent Pattern ID.
    :ivar pattern_name: Pattern name.
    :ivar pattern_family: Pattern family.
    :ivar scene_id: Scene this instance belongs to.
    """

    instance_id: str
    slot: str
    confidence: float
    pattern_id: str
    pattern_name: str
    pattern_family: str
    scene_id: str


# ── Transforms ────────────────────────────────────────────────────────────────


class TransformRequest(BaseModel):
    """Request body for ``POST /v1/transforms/apply``.

    :ivar scene_id: Target scene ID.
    :ivar axis: Transformation axis (pov/mood/genre/chronotope/reliability/code_overlay).
    :ivar parameters: Axis-specific parameters dict.
    :ivar operator: Identifier of the requesting user/system.
    """

    scene_id: str
    axis: TransformAxis
    parameters: dict[str, Any] = Field(default_factory=dict)
    operator: str = "api"


class TransformResponse(BaseModel):
    """Response body for a transform operation.

    :ivar transform_id: ID of the created Transform audit node.
    :ivar scene_id: Target scene ID.
    :ivar axis: The axis applied.
    :ivar produced_id: ID of the new state node.
    :ivar status: Always ``"accepted"`` on success.
    """

    transform_id: str
    scene_id: str
    axis: str
    produced_id: str
    status: str


class BulkTransformRequest(BaseModel):
    """Request body for ``POST /v1/transforms/apply-bulk``.

    :ivar narrative_id: Target narrative ID.
    :ivar axis: Transformation axis applied to every scene.
    :ivar parameters: Axis-specific parameters dict.
    :ivar operator: Identifier of the requesting user/system.
    """

    narrative_id: str
    axis: TransformAxis
    parameters: dict[str, Any] = Field(default_factory=dict)
    operator: str = "api"


class BulkTransformResponse(BaseModel):
    """Response body for ``POST /v1/transforms/apply-bulk``.

    :ivar narrative_id: The narrative that was transformed.
    :ivar applied_count: Number of scenes transformed.
    :ivar results: Per-scene transform results.
    """

    narrative_id: str
    applied_count: int
    results: list[TransformResponse]


class TransformRecord(BaseModel):
    """Response body for ``GET /v1/transforms/{id}``.

    :ivar id: Transform ID.
    :ivar scene_id: Target scene ID.
    :ivar produced_type: Labels of the produced node.
    :ivar produced_id: ID of the produced state node.
    """

    id: str
    scene_id: str | None
    produced_type: list[str] | None
    produced_id: str | None


# ── Render ────────────────────────────────────────────────────────────────────


class RenderRequest(BaseModel):
    """Request body for ``POST /v1/render/{id}``.

    :ivar type: Output format type.
    :ivar params: Renderer-specific parameters (optional).
    """

    type: RenderType = RenderType.PROSE
    params: dict[str, Any] = Field(default_factory=dict)


class RenderResponse(BaseModel):
    """Response body for a render operation.

    :ivar narrative_id: The rendered narrative's ID.
    :ivar render_type: The output format that was produced.
    :ivar content: The rendered string content.
    :ivar content_type: MIME type of the content.
    """

    narrative_id: str
    render_type: str
    content: str
    content_type: str


# ── Atom revisions ────────────────────────────────────────────────────────────


class AtomReviseRequest(BaseModel):
    """Request body for ``PATCH /v1/atoms/{atom_id}``.

    :ivar text: New prose text for the atom.
    :ivar operator: Identifier of the requesting user/system.
    :ivar reason: Optional human-readable reason for the revision.
    """

    text: str
    operator: str = "api"
    reason: str = ""


class AtomRevisionRecord(BaseModel):
    """A single atom revision record.

    :ivar id: Revision ID.
    :ivar atom_id: Parent atom ID.
    :ivar text: Revised text.
    :ivar revised_at: UTC timestamp.
    :ivar operator: Who issued the revision.
    :ivar reason: Reason for the revision.
    """

    id: str
    atom_id: str
    text: str
    revised_at: datetime
    operator: str
    reason: str


class AtomRevisionResponse(BaseModel):
    """Response body for ``PATCH /v1/atoms/{atom_id}``.

    :ivar atom_id: The revised atom's ID.
    :ivar revision_id: The new revision's ID.
    :ivar text: The revised text.
    """

    atom_id: str
    revision_id: str
    text: str


class AtomRevisionListResponse(BaseModel):
    """Response body for ``GET /v1/atoms/{atom_id}/revisions``.

    :ivar atom_id: The queried atom's ID.
    :ivar revisions: Full revision history, oldest first.
    """

    atom_id: str
    revisions: list[AtomRevisionRecord]


# ── Health ────────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Response body for health endpoints.

    :ivar status: ``"ok"`` or ``"degraded"``.
    :ivar neo4j: Neo4j connectivity status string.
    """

    status: str
    neo4j: str = "unknown"
