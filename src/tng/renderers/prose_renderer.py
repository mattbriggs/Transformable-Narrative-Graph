"""Prose renderer — atoms in surface order decorated with perspective context.

Produces a Markdown-formatted prose draft.  Each scene is rendered as a
section headed by its sequence number and summary.  Atoms are joined with
spaces in their surface order.  An optional header block shows the active
perspective and mood if they have been set on the scene.
"""

from __future__ import annotations

import logging
from typing import Any

from tng.domain.models import GraphState, Scene
from tng.renderers.protocol import RenderOutput

logger = logging.getLogger(__name__)


class ProseRenderer:
    """Renders a narrative's atoms as a prose draft.

    The renderer reads atom text, scene metadata, and the current
    Perspective/MoodState from the ``GraphState`` snapshot.

    :method render: Convert ``GraphState`` to a Markdown prose draft.
    """

    def render(self, graph_state: GraphState, params: dict[str, Any]) -> RenderOutput:
        """Render all scenes in surface order as prose.

        :param graph_state: Complete narrative snapshot.
        :param params: Unused by this renderer (reserved for future options).
        :returns: ``RenderOutput`` with ``content_type="text/markdown"``.
        """
        narrative = graph_state.narrative
        lines: list[str] = [f"# {narrative.title}", ""]

        for scene in sorted(narrative.scenes, key=lambda s: s.sequence):
            lines.extend(self._render_scene(scene))

        content = "\n".join(lines)
        logger.debug("ProseRenderer produced %d chars.", len(content))
        return RenderOutput(
            content=content,
            content_type="text/markdown",
            metadata={"scene_count": len(narrative.scenes)},
        )

    def _render_scene(self, scene: Scene) -> list[str]:
        """Render a single scene block.

        :param scene: The scene to render.
        :returns: List of Markdown lines for this scene.
        """
        lines: list[str] = []
        lines.append(f"## Scene {scene.sequence}")
        if scene.summary:
            lines.append(f"*{scene.summary}*")
        lines.append("")

        # Context block
        ctx_parts: list[str] = []
        if scene.current_perspective:
            pov = scene.current_perspective
            ctx_parts.append(
                f"POV: {pov.focalizer} ({pov.distance.value}, {pov.reliability.value})"
            )
        if scene.current_mood:
            ctx_parts.append(f"Mood: {scene.current_mood.label}")
        if ctx_parts:
            lines.append("> " + " | ".join(ctx_parts))
            lines.append("")

        atoms_sorted = sorted(scene.atoms, key=lambda a: a.surface_order)
        text = " ".join(a.text for a in atoms_sorted)
        lines.append(text)
        lines.append("")

        return lines
