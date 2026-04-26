"""Transform service — validates and applies transformation axes (SRS §7).

The six transformation axes are each dispatched through a dedicated
validator and then routed to the ``GraphRepository``.  The service is the
only place where axis-specific parameter validation occurs; the repository
is responsible only for the Cypher mechanics.

Non-destructive contract (SRS §7.2)
------------------------------------
Every transformation:

1. Creates a new state node.
2. Detaches the old ``CURRENT_*`` relationship.
3. Attaches the new ``CURRENT_*`` relationship.
4. Creates a ``Transform`` audit node linked to both.

The old state node is **never deleted** — full lineage is always traversable.

Design notes
------------
* Axis validators use Pydantic for parameter schemas; an invalid parameter
  dict raises ``ValueError`` before any graph write occurs (SRS Diagram 9).
* The ``TransformRequest`` dataclass is the public input contract; it is
  populated from the API schema and handed to ``apply()``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from tng.domain.enums import (
    BarthesCode,
    FocalizationDistance,
    NarrativeStatus,
    ReliabilityLevel,
    TransformAxis,
)
from tng.domain.models import Transform
from tng.ingest.annotator import make_id
from tng.repository.graph_repository import GraphRepository

logger = logging.getLogger(__name__)


# ── Axis parameter schemas ────────────────────────────────────────────────────


class PovParams(BaseModel):
    """Parameters for a POV transformation.

    :ivar focalizer: ID of the Character who becomes the focalizer.
    :ivar distance: Genettean focalization distance.
    :ivar reliability: Narrator/focalizer credibility.
    """

    focalizer: str
    distance: FocalizationDistance = FocalizationDistance.ZERO
    reliability: ReliabilityLevel = ReliabilityLevel.RELIABLE


class MoodParams(BaseModel):
    """Parameters for a mood transformation.

    :ivar label: Free-text mood label.
    :ivar valence: Sentiment polarity in [-1.0, 1.0].
    :ivar arousal: Activation in [0.0, 1.0].
    """

    label: str
    valence: float = Field(default=0.0, ge=-1.0, le=1.0)
    arousal: float = Field(default=0.5, ge=0.0, le=1.0)


class GenreParams(BaseModel):
    """Parameters for a genre transformation.

    :ivar name: Genre name.
    :ivar conventions: List of genre constraint strings.
    """

    name: str
    conventions: list[str] = Field(default_factory=list)


class ChronotopeParams(BaseModel):
    """Parameters for a chronotope transformation.

    :ivar time_mode: Time mode (cyclical/linear/suspended/compressed).
    :ivar space_mode: Space mode (bounded/open/liminal/utopian).
    """

    time_mode: str
    space_mode: str

    @field_validator("time_mode")
    @classmethod
    def _validate_time_mode(cls, v: str) -> str:
        valid = {"cyclical", "linear", "suspended", "compressed"}
        if v not in valid:
            raise ValueError(f"time_mode must be one of {valid}")
        return v

    @field_validator("space_mode")
    @classmethod
    def _validate_space_mode(cls, v: str) -> str:
        valid = {"bounded", "open", "liminal", "utopian"}
        if v not in valid:
            raise ValueError(f"space_mode must be one of {valid}")
        return v


class ReliabilityParams(BaseModel):
    """Parameters for a reliability transformation.

    :ivar reliability: New reliability level for the existing Perspective.
    """

    reliability: ReliabilityLevel


class CodeOverlayParams(BaseModel):
    """Parameters for a code overlay transformation.

    :ivar atom_id: ID of the target Atom.
    :ivar code: Barthesian code category.
    :ivar label: Human-readable annotation label.
    """

    atom_id: str
    code: BarthesCode
    label: str = ""


_PARAM_SCHEMAS: dict[TransformAxis, type[BaseModel]] = {
    TransformAxis.POV: PovParams,
    TransformAxis.MOOD: MoodParams,
    TransformAxis.GENRE: GenreParams,
    TransformAxis.CHRONOTOPE: ChronotopeParams,
    TransformAxis.RELIABILITY: ReliabilityParams,
    TransformAxis.CODE_OVERLAY: CodeOverlayParams,
}


# ── Service input/output ──────────────────────────────────────────────────────


@dataclass
class TransformRequest:
    """Input contract for a transform request.

    :param scene_id: Target scene ID.
    :param axis: The transformation axis.
    :param parameters: Axis-specific parameter dict.
    :param operator: Identifier of the requesting user/system.
    """

    scene_id: str
    axis: TransformAxis
    parameters: dict[str, Any]
    operator: str = "system"


@dataclass
class TransformResponse:
    """Result returned to the API after a transform operation.

    :param transform_id: ID of the created Transform audit node.
    :param scene_id: Target scene ID.
    :param axis: The axis that was applied.
    :param produced_id: ID of the new state node created.
    :param status: Always ``"accepted"`` on success.
    """

    transform_id: str
    scene_id: str
    axis: str
    produced_id: str
    status: str = "accepted"


# ── Service ───────────────────────────────────────────────────────────────────


class TransformService:
    """Validates and applies transformation axes.

    :param repo: Open ``GraphRepository`` instance.
    """

    def __init__(self, repo: GraphRepository) -> None:
        self._repo = repo

    def apply(self, request: TransformRequest) -> TransformResponse:
        """Validate parameters and apply a transformation to a scene.

        :param request: The transform request.
        :returns: A ``TransformResponse`` with the new transform's ID.
        :raises ValueError: When axis parameters fail validation.
        """
        validated_params = self._validate_params(request.axis, request.parameters)
        transform = Transform(
            id=make_id(),
            axis=request.axis,
            operator=request.operator,
            applied_at=datetime.utcnow(),
            parameters=validated_params,
            scene_id=request.scene_id,
        )
        result = self._repo.apply_transform(transform)
        self._repo.update_narrative_status_for_scene(
            request.scene_id, NarrativeStatus.TRANSFORMED
        )
        logger.info(
            "Applied %s transform to scene %s → produced %s",
            request.axis.value,
            request.scene_id,
            result.produced_id,
        )
        return TransformResponse(
            transform_id=result.id,
            scene_id=request.scene_id,
            axis=request.axis.value,
            produced_id=result.produced_id,
        )

    def apply_bulk(
        self,
        narrative_id: str,
        axis: TransformAxis,
        parameters: dict[str, Any],
        operator: str = "system",
    ) -> list[TransformResponse]:
        """Apply a transformation axis to every scene in a narrative.

        Validates parameters against the axis schema before issuing any write.
        Scenes are processed in sequence order.

        :param narrative_id: Target narrative ID.
        :param axis: The transformation axis.
        :param parameters: Axis-specific parameter dict (validated once).
        :param operator: Identifier of the requesting user/system.
        :returns: List of ``TransformResponse`` — one per scene.
        :raises ValueError: When parameters fail axis validation or the
            narrative has no scenes.
        """
        self._validate_params(axis, parameters)
        scene_ids = self._repo.get_scene_ids(narrative_id)
        if not scene_ids:
            raise ValueError(f"No scenes found for narrative {narrative_id!r}.")
        results = []
        for scene_id in scene_ids:
            result = self.apply(
                TransformRequest(
                    scene_id=scene_id,
                    axis=axis,
                    parameters=parameters,
                    operator=operator,
                )
            )
            results.append(result)
        return results

    def get_history(self, scene_id: str) -> list[dict]:
        """Return the transformation history for a scene.

        :param scene_id: The target scene ID.
        :returns: Ordered list of transform audit dicts.
        """
        return self._repo.get_transform_history(scene_id)

    def _validate_params(
        self, axis: TransformAxis, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate axis parameters using the axis-specific Pydantic schema.

        :param axis: The transformation axis.
        :param params: Raw parameter dict from the request.
        :returns: Validated parameter dict.
        :raises ValueError: On validation failure.
        """
        schema = _PARAM_SCHEMAS.get(axis)
        if schema is None:
            raise ValueError(f"No parameter schema defined for axis: {axis}")
        model = schema.model_validate(params)
        return model.model_dump()
