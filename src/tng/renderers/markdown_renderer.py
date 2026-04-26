"""Markdown renderer — structured summary with scene, patterns, and transform log.

Produces a human-readable Markdown document organised as:
1. Title and narrative metadata
2. Per-scene summaries with atom counts
3. Pattern instances table
4. Transformation history table
"""

from __future__ import annotations

import logging
from typing import Any

from tng.domain.models import GraphState
from tng.renderers.protocol import RenderOutput

logger = logging.getLogger(__name__)


class MarkdownRenderer:
    """Renders a narrative summary as a structured Markdown document.

    :method render: Convert ``GraphState`` to a Markdown summary.
    """

    def render(self, graph_state: GraphState, params: dict[str, Any]) -> RenderOutput:
        """Render a structured Markdown summary.

        :param graph_state: Complete narrative snapshot.
        :param params: Unused (reserved).
        :returns: ``RenderOutput`` with ``content_type="text/markdown"``.
        """
        n = graph_state.narrative
        lines: list[str] = [
            f"# {n.title}",
            "",
            f"**Status:** {n.status.value}  ",
            f"**Scenes:** {len(n.scenes)}  ",
            f"**Transformations:** {len(graph_state.transforms)}  ",
            "",
            "---",
            "",
            "## Scenes",
            "",
        ]

        for scene in sorted(n.scenes, key=lambda s: s.sequence):
            lines.append(f"### Scene {scene.sequence}")
            if scene.summary:
                lines.append(f"> {scene.summary}")
            lines.append(f"- Atoms: {len(scene.atoms)}")
            lines.append(f"- Events: {len(scene.events)}")
            flagged = sum(1 for a in scene.atoms if a.needs_review)
            if flagged:
                lines.append(f"- ⚠ Flagged for review: {flagged}")
            if scene.current_perspective:
                pov = scene.current_perspective
                lines.append(
                    f"- POV: {pov.focalizer} / {pov.distance.value} / {pov.reliability.value}"
                )
            if scene.current_mood:
                lines.append(f"- Mood: {scene.current_mood.label}")
            lines.append("")

        # Pattern instances table
        all_instances = [
            pi for scene in n.scenes for pi in scene.pattern_instances
        ]
        if all_instances:
            lines += [
                "## Pattern Instances",
                "",
                "| Pattern | Family | Scene | Confidence |",
                "|---------|--------|-------|------------|",
            ]
            for pi in all_instances:
                name = pi.template.name if pi.template else "—"
                family = pi.template.family if pi.template else "—"
                scene_seq = next(
                    (s.sequence for s in n.scenes if pi in s.pattern_instances), "?"
                )
                lines.append(
                    f"| {name} | {family} | {scene_seq} | {pi.confidence:.2f} |"
                )
            lines.append("")

        # Transformation history table
        if graph_state.transforms:
            lines += [
                "## Transformation History",
                "",
                "| # | Axis | Operator | Applied At | Produced |",
                "|---|------|----------|------------|---------|",
            ]
            for i, t in enumerate(graph_state.transforms, 1):
                lines.append(
                    f"| {i} | {t.axis.value} | {t.operator} "
                    f"| {t.applied_at.strftime('%Y-%m-%d %H:%M')} "
                    f"| {t.produced_id} |"
                )
            lines.append("")

        content = "\n".join(lines)
        logger.debug("MarkdownRenderer produced %d chars.", len(content))
        return RenderOutput(
            content=content,
            content_type="text/markdown",
            metadata={"scene_count": len(n.scenes)},
        )
