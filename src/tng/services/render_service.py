"""Render service — dispatches render requests to registered renderers.

The service maintains a registry of ``RendererProtocol`` implementations
keyed by ``RenderType``.  Renderers are registered at startup; new output
types can be added without modifying this module (open/closed principle).

No renderer is allowed to issue Cypher directly.  All graph data arrives
as a ``GraphState`` snapshot fetched by this service via the repository.
"""

from __future__ import annotations

import logging
from typing import Any

from tng.domain.enums import NarrativeStatus, RenderType
from tng.domain.models import GraphState
from tng.renderers.cypher_renderer import CypherRenderer
from tng.renderers.diff_renderer import DiffRenderer
from tng.renderers.graphml_renderer import GraphMLRenderer
from tng.renderers.json_renderer import JSONRenderer
from tng.renderers.markdown_renderer import MarkdownRenderer
from tng.renderers.prose_renderer import ProseRenderer
from tng.renderers.protocol import RenderOutput, RendererProtocol
from tng.repository.graph_repository import GraphRepository

logger = logging.getLogger(__name__)

_DEFAULT_RENDERERS: dict[RenderType, RendererProtocol] = {
    RenderType.PROSE: ProseRenderer(),
    RenderType.DIFF: DiffRenderer(),
    RenderType.JSON: JSONRenderer(),
    RenderType.CYPHER: CypherRenderer(),
    RenderType.MARKDOWN: MarkdownRenderer(),
    RenderType.GRAPHML: GraphMLRenderer(),
}


class RenderService:
    """Dispatches render requests to the appropriate renderer implementation.

    :param repo: Open ``GraphRepository`` for fetching graph state.
    :param renderers: Renderer registry.  Defaults to the five built-in
        renderers; inject custom implementations for extensibility.
    """

    def __init__(
        self,
        repo: GraphRepository,
        renderers: dict[RenderType, RendererProtocol] | None = None,
    ) -> None:
        self._repo = repo
        self._renderers = renderers or _DEFAULT_RENDERERS.copy()

    def render(
        self,
        narrative_id: str,
        render_type: RenderType,
        params: dict[str, Any] | None = None,
    ) -> RenderOutput:
        """Fetch graph state and render it to the requested format.

        :param narrative_id: The narrative to render.
        :param render_type: The desired output format.
        :param params: Renderer-specific parameters (optional).
        :returns: A ``RenderOutput`` containing the rendered content.
        :raises KeyError: When ``render_type`` has no registered renderer.
        :raises ValueError: When the narrative does not exist.
        """
        renderer = self._renderers.get(render_type)
        if renderer is None:
            raise KeyError(f"No renderer registered for type: {render_type}")

        graph_state = self._repo.get_graph_state(narrative_id)
        if graph_state is None:
            raise ValueError(f"Narrative not found: {narrative_id}")

        self._repo.update_narrative_status(narrative_id, NarrativeStatus.RENDERED)
        logger.info(
            "Rendering narrative %s as %s.", narrative_id, render_type.value
        )
        return renderer.render(graph_state, params or {})

    def register_renderer(
        self, render_type: RenderType, renderer: RendererProtocol
    ) -> None:
        """Register or replace a renderer at runtime.

        :param render_type: The output format key.
        :param renderer: The renderer implementation to register.
        """
        self._renderers[render_type] = renderer
        logger.info("Registered renderer for %s.", render_type.value)
