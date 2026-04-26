"""JSON renderer — full graph state as a structured JSON document.

Serialises the complete ``GraphState`` into a node/edge-list representation
suitable for downstream processing, archiving, or re-import.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from tng.domain.models import GraphState
from tng.renderers.protocol import RenderOutput

logger = logging.getLogger(__name__)


class JSONRenderer:
    """Serialises a ``GraphState`` to a JSON document.

    The output structure mirrors the SRS §4 data model:
    narrative → scenes → atoms/events/pattern_instances.

    :method render: Convert ``GraphState`` to JSON.
    """

    def render(self, graph_state: GraphState, params: dict[str, Any]) -> RenderOutput:
        """Render the full graph state as a JSON document.

        :param graph_state: Complete narrative snapshot.
        :param params: Unused (reserved).
        :returns: ``RenderOutput`` with ``content_type="application/json"``.
        """
        narrative = graph_state.narrative
        doc = {
            "narrative": {
                "id": narrative.id,
                "title": narrative.title,
                "status": narrative.status.value,
                "source_ref": narrative.source_ref,
                "created_at": narrative.created_at.isoformat(),
                "scenes": [self._scene_to_dict(s) for s in narrative.scenes],
            },
            "transforms": [
                {
                    "id": t.id,
                    "axis": t.axis.value,
                    "operator": t.operator,
                    "applied_at": t.applied_at.isoformat(),
                    "parameters": t.parameters,
                    "scene_id": t.scene_id,
                    "produced_id": t.produced_id,
                }
                for t in graph_state.transforms
            ],
            "characters": [
                {"id": c.id, "name": c.name, "role": c.role}
                for c in graph_state.characters
            ],
        }
        content = json.dumps(doc, indent=2, default=str)
        logger.debug("JSONRenderer produced %d chars.", len(content))
        return RenderOutput(
            content=content,
            content_type="application/json",
            metadata={"scene_count": len(narrative.scenes)},
        )

    def _scene_to_dict(self, scene: Any) -> dict:
        """Serialise a Scene to a plain dict.

        :param scene: A ``Scene`` domain object.
        :returns: Dict representation.
        """
        return {
            "id": scene.id,
            "sequence": scene.sequence,
            "summary": scene.summary,
            "atoms": [
                {
                    "id": a.id,
                    "text": a.text,
                    "kind": a.kind.value,
                    "surface_order": a.surface_order,
                    "confidence": a.confidence,
                    "needs_review": a.needs_review,
                    "code_tags": [
                        {"id": t.id, "code": t.code.value, "label": t.label}
                        for t in a.code_tags
                    ],
                }
                for a in scene.atoms
            ],
            "events": [
                {
                    "id": e.id,
                    "verb": e.verb,
                    "tense": e.tense,
                    "aspect": e.aspect,
                    "confidence": e.confidence,
                    "needs_review": e.needs_review,
                    "participants": [
                        {"id": c.id, "name": c.name} for c in e.participants
                    ],
                }
                for e in scene.events
            ],
            "pattern_instances": [
                {
                    "id": pi.id,
                    "slot": pi.slot,
                    "confidence": pi.confidence,
                    "pattern_id": pi.template.id if pi.template else None,
                    "pattern_name": pi.template.name if pi.template else None,
                }
                for pi in scene.pattern_instances
            ],
            "current_perspective": (
                {
                    "id": scene.current_perspective.id,
                    "focalizer": scene.current_perspective.focalizer,
                    "distance": scene.current_perspective.distance.value,
                    "reliability": scene.current_perspective.reliability.value,
                }
                if scene.current_perspective
                else None
            ),
            "current_mood": (
                {
                    "id": scene.current_mood.id,
                    "label": scene.current_mood.label,
                    "valence": scene.current_mood.valence,
                    "arousal": scene.current_mood.arousal,
                }
                if scene.current_mood
                else None
            ),
        }
