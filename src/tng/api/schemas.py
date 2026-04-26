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

    :param atom_index: Zero-based position of the target atom in the scene.
    :param code: Barthesian code category string.
    """

    atom_index: int
    code: str


class SceneInput(BaseModel):
    """One scene block within a structured JSON ingest payload.

    :param scene_id: Optional scene ID (generated if absent).
    :param sequence: Ordinal position within the narrative.
    :param summary: Optional human-readable scene summary.
    :param text: Raw prose to atomize.
    :param pattern_hints: Optional list of pattern name hints.
    :param character_refs: Optional list of pre-identified character names.
    :param code_tags: Optional pre-annotation code tag hints.
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

    :param title: Narrative title.
    :param text: Raw text for plain-text or Markdown ingest.
    :param narrative_id: Optional; generated if absent.
    :param source_ref: Optional provenance reference.
    :param format: Input format: ``"text"``, ``"markdown"``, ``"json"``, or ``"csv"``.
    :param scenes: Pre-structured scenes (used when ``format="json"``).
    """

    title: str
    text: str = ""
    narrative_id: str | None = None
    source_ref: str = ""
    format: str = "text"
    scenes: list[SceneInput] = Field(default_factory=list)


class IngestResponse(BaseModel):
    """Response body for ``POST /v1/notes/import``.

    :param narrative_id: ID of the created or updated Narrative.
    :param scene_count: Number of scenes persisted.
    :param atom_count: Total atoms written.
    :param event_count: Total events written.
    :param character_count: Total characters written.
    :param pattern_count: Number of pattern instances created.
    :param flagged_count: Nodes flagged for human review.
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

    :param id: Narrative ID.
    :param title: Narrative title.
    :param status: Life-cycle status string.
    :param source_ref: Provenance reference.
    :param scene_count: Number of scenes.
    :param created_at: UTC creation timestamp.
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

    :param id: Optional explicit ID; generated if absent.
    :param name: Pattern name.
    :param family: Family tag (e.g. ``"ritual"``).
    :param description: Prose description.
    """

    id: str | None = None
    name: str
    family: str
    description: str = ""


class PatternRecord(BaseModel):
    """Response record for a pattern template.

    :param id: Pattern ID.
    :param name: Pattern name.
    :param family: Family tag.
    :param description: Description.
    """

    id: str
    name: str
    family: str
    description: str


class PatternInstanceRecord(BaseModel):
    """A single pattern instance record.

    :param instance_id: PatternInstance ID.
    :param slot: Structural slot label.
    :param confidence: Match confidence.
    :param pattern_id: Parent Pattern ID.
    :param pattern_name: Pattern name.
    :param pattern_family: Pattern family.
    :param scene_id: Scene this instance belongs to.
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

    :param scene_id: Target scene ID.
    :param axis: Transformation axis (pov/mood/genre/chronotope/reliability/code_overlay).
    :param parameters: Axis-specific parameters dict.
    :param operator: Identifier of the requesting user/system.
    """

    scene_id: str
    axis: TransformAxis
    parameters: dict[str, Any] = Field(default_factory=dict)
    operator: str = "api"


class TransformResponse(BaseModel):
    """Response body for a transform operation.

    :param transform_id: ID of the created Transform audit node.
    :param scene_id: Target scene ID.
    :param axis: The axis applied.
    :param produced_id: ID of the new state node.
    :param status: Always ``"accepted"`` on success.
    """

    transform_id: str
    scene_id: str
    axis: str
    produced_id: str
    status: str


class TransformRecord(BaseModel):
    """Response body for ``GET /v1/transforms/{id}``.

    :param id: Transform ID.
    :param scene_id: Target scene ID.
    :param produced_type: Labels of the produced node.
    :param produced_id: ID of the produced state node.
    """

    id: str
    scene_id: str | None
    produced_type: list[str] | None
    produced_id: str | None


# ── Render ────────────────────────────────────────────────────────────────────


class RenderRequest(BaseModel):
    """Request body for ``POST /v1/render/{id}``.

    :param type: Output format type.
    :param params: Renderer-specific parameters (optional).
    """

    type: RenderType = RenderType.PROSE
    params: dict[str, Any] = Field(default_factory=dict)


class RenderResponse(BaseModel):
    """Response body for a render operation.

    :param narrative_id: The rendered narrative's ID.
    :param render_type: The output format that was produced.
    :param content: The rendered string content.
    :param content_type: MIME type of the content.
    """

    narrative_id: str
    render_type: str
    content: str
    content_type: str


# ── Health ────────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Response body for health endpoints.

    :param status: ``"ok"`` or ``"degraded"``.
    :param neo4j: Neo4j connectivity status string.
    """

    status: str
    neo4j: str = "unknown"
