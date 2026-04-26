"""Renderer protocol and shared output types (SRS §10.4).

The ``RendererProtocol`` is a Python structural-typing ``Protocol``.  Any
object that implements ``render(graph_state, params) -> RenderOutput`` is a
valid renderer — no inheritance required.  This keeps renderer
implementations decoupled from this module.

Contract invariants
-------------------
* A renderer must **not** issue Cypher directly.
* All graph data must arrive via the ``GraphState`` parameter.
* The ``RenderOutput.content`` field must always be a non-empty string.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class RenderOutput:
    """The result of a render operation.

    :param content: The rendered string (prose, JSON, Cypher, Markdown, etc.).
    :param content_type: MIME type hint for HTTP responses.
    :param metadata: Arbitrary key/value pairs populated by the renderer.
    """

    content: str
    content_type: str = "text/plain"
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class RendererProtocol(Protocol):
    """Structural protocol for all TNGS renderer implementations.

    :method render: Convert a ``GraphState`` snapshot to a ``RenderOutput``.
    """

    def render(
        self,
        graph_state: Any,
        params: dict[str, Any],
    ) -> RenderOutput:
        """Render the graph state to a string output.

        :param graph_state: The ``GraphState`` domain snapshot.
        :param params: Renderer-specific parameters.
        :returns: A ``RenderOutput`` with content and metadata.
        """
        ...
