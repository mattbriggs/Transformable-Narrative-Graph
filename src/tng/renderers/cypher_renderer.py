"""Cypher renderer — replayable MERGE script for the full graph state.

Produces a Cypher script that, when executed against an empty Neo4j
database, recreates all persisted state from the ``GraphState`` snapshot.
All statements use ``MERGE`` to remain idempotent (SRS §8.1).

The generated script is ordered:
1. Narrative node
2. Scene nodes + HAS_SCENE edges
3. Atom nodes + CONTAINS edges
4. Event nodes + CONTAINS edges
5. Transform audit nodes + APPLIED_TO / PRODUCED edges
"""

from __future__ import annotations

import json
import logging
from typing import Any

from tng.domain.models import GraphState
from tng.renderers.protocol import RenderOutput

logger = logging.getLogger(__name__)


def _esc(value: Any) -> str:
    """Escape a value for inline embedding in a Cypher string literal.

    :param value: Any scalar value.
    :returns: JSON-encoded string safe for embedding in Cypher.
    """
    return json.dumps(str(value))


class CypherRenderer:
    """Renders a ``GraphState`` as a replayable Cypher MERGE script.

    :method render: Convert ``GraphState`` to a Cypher text script.
    """

    def render(self, graph_state: GraphState, params: dict[str, Any]) -> RenderOutput:
        """Render the full graph state as a Cypher script.

        :param graph_state: Complete narrative snapshot.
        :param params: Unused (reserved).
        :returns: ``RenderOutput`` with ``content_type="text/x-cypher"``.
        """
        narrative = graph_state.narrative
        lines: list[str] = [
            "// TNGS replayable Cypher export",
            f"// Narrative: {narrative.title}",
            f"// Generated: {__import__('datetime').datetime.utcnow().isoformat()}",
            "",
        ]

        lines.extend(self._narrative_lines(narrative))
        for scene in narrative.scenes:
            lines.extend(self._scene_lines(scene, narrative.id))
            for atom in scene.atoms:
                lines.extend(self._atom_lines(atom, scene.id))
            for event in scene.events:
                lines.extend(self._event_lines(event, scene.id))

        for t in graph_state.transforms:
            lines.extend(self._transform_lines(t))

        content = "\n".join(lines)
        logger.debug("CypherRenderer produced %d lines.", len(lines))
        return RenderOutput(
            content=content,
            content_type="text/x-cypher",
            metadata={"line_count": len(lines)},
        )

    def _narrative_lines(self, narrative: Any) -> list[str]:
        return [
            f"MERGE (n:Narrative {{id: {_esc(narrative.id)}}})",
            f"  SET n.title = {_esc(narrative.title)},",
            f"      n.status = {_esc(narrative.status.value)},",
            f"      n.source_ref = {_esc(narrative.source_ref)};",
            "",
        ]

    def _scene_lines(self, scene: Any, narrative_id: str) -> list[str]:
        return [
            f"MERGE (s:Scene {{id: {_esc(scene.id)}}}) SET s.sequence = {scene.sequence}, s.summary = {_esc(scene.summary)};",
            f"MATCH (n:Narrative {{id: {_esc(narrative_id)}}}), (s:Scene {{id: {_esc(scene.id)}}}) MERGE (n)-[:HAS_SCENE]->(s);",
            "",
        ]

    def _atom_lines(self, atom: Any, scene_id: str) -> list[str]:
        return [
            f"MERGE (a:Atom {{id: {_esc(atom.id)}}}) SET a.text = {_esc(atom.text)}, a.kind = {_esc(atom.kind.value)}, a.surface_order = {atom.surface_order}, a.confidence = {atom.confidence};",
            f"MATCH (s:Scene {{id: {_esc(scene_id)}}}), (a:Atom {{id: {_esc(atom.id)}}}) MERGE (s)-[:CONTAINS]->(a);",
            "",
        ]

    def _event_lines(self, event: Any, scene_id: str) -> list[str]:
        return [
            f"MERGE (e:Event {{id: {_esc(event.id)}}}) SET e.verb = {_esc(event.verb)}, e.tense = {_esc(event.tense)}, e.confidence = {event.confidence};",
            f"MATCH (s:Scene {{id: {_esc(scene_id)}}}), (e:Event {{id: {_esc(event.id)}}}) MERGE (s)-[:CONTAINS]->(e);",
            "",
        ]

    def _transform_lines(self, t: Any) -> list[str]:
        return [
            f"MERGE (t:Transform {{id: {_esc(t.id)}}}) SET t.axis = {_esc(t.axis.value)}, t.operator = {_esc(t.operator)}, t.applied_at = datetime({_esc(t.applied_at.isoformat())});",
            f"MATCH (t:Transform {{id: {_esc(t.id)}}}), (s:Scene {{id: {_esc(t.scene_id)}}}) MERGE (t)-[:APPLIED_TO]->(s);",
            "",
        ]
