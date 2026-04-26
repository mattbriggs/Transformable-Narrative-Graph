"""Diff renderer — side-by-side before/after for each transformed axis.

Produces a JSON object showing the transformation history for each scene,
grouping transforms by axis and presenting the sequence of state changes
so authors can compare what changed at each step.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from tng.domain.models import GraphState
from tng.renderers.protocol import RenderOutput

logger = logging.getLogger(__name__)


class DiffRenderer:
    """Renders the transformation history as a structured diff document.

    Each entry in the output describes one transform: the axis, operator,
    timestamp, and the ID of the state node produced.

    :method render: Convert ``GraphState`` to a JSON diff document.
    """

    def render(self, graph_state: GraphState, params: dict[str, Any]) -> RenderOutput:
        """Render the transformation history as a JSON diff.

        :param graph_state: Complete narrative snapshot including transform
            history.
        :param params: Unused (reserved for future filter options).
        :returns: ``RenderOutput`` with ``content_type="application/json"``.
        """
        transforms_by_axis: dict[str, list[dict]] = {}

        for t in graph_state.transforms:
            key = t.axis.value
            transforms_by_axis.setdefault(key, []).append(
                {
                    "transform_id": t.id,
                    "scene_id": t.scene_id,
                    "operator": t.operator,
                    "applied_at": t.applied_at.isoformat(),
                    "parameters": t.parameters,
                    "produced_id": t.produced_id,
                }
            )

        payload = {
            "narrative_id": graph_state.narrative.id,
            "title": graph_state.narrative.title,
            "diff_by_axis": transforms_by_axis,
            "total_transforms": len(graph_state.transforms),
        }
        content = json.dumps(payload, indent=2, default=str)
        logger.debug("DiffRenderer produced %d transforms.", len(graph_state.transforms))
        return RenderOutput(
            content=content,
            content_type="application/json",
            metadata={"total_transforms": len(graph_state.transforms)},
        )
