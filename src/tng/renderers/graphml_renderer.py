"""GraphML renderer — yEd-compatible export with tension-coloured edges.

Implements ``RendererProtocol``.  Traverses a ``GraphState`` snapshot and
produces a GraphML document that can be opened directly in yEd Graph Editor.

**Node colouring by label type:**

+-------------------+--------------------+
| Node label        | Fill colour        |
+===================+====================+
| Narrative         | #4A90D9 (blue)     |
| Scene             | #7ED321 (green)    |
| Atom              | #F5A623 (amber)    |
| Event             | #D0021B (red)      |
| PatternInstance   | #9B59B6 (purple)   |
| Pattern           | #C0392B (dark-red) |
| Perspective       | #1ABC9C (teal)     |
| MoodState         | #E74C3C (coral)    |
| GenreProfile      | #3498DB (sky-blue) |
| Chronotope        | #27AE60 (dark-grn) |
| CodeTag           | #F39C12 (orange)   |
| Transform         | #95A5A6 (grey)     |
| Character         | #8E44AD (violet)   |
+-------------------+--------------------+

**Edge colouring by narrative tension:**

Edges are coloured by a composite tension score computed by
``tension_scorer.score_edge()``.  The six-stop gradient runs from neutral
grey (0.0) through steel-blue → gold → orange → crimson to dark-red (1.0).

**yEd import:**  File → Open → select the ``.graphml`` file.  The yFiles
extension keys (``d3``/``d6`` for node/edge graphics) are automatically
interpreted when the file is opened in yEd 3.x or later.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

from tng.domain.models import (
    Atom,
    Character,
    Chronotope,
    CodeTag,
    Event,
    GenreProfile,
    GraphState,
    MoodState,
    Narrative,
    PatternInstance,
    Perspective,
    Scene,
    Transform,
)
from tng.renderers.protocol import RenderOutput
from tng.renderers.tension_scorer import score_edge, score_structural_edge

logger = logging.getLogger(__name__)

# ── yEd / yFiles XML namespace ────────────────────────────────────────────────

_GRAPHML_NS = "http://graphml.graphdrawing.org/graphml"
_YFILES_NS = "http://www.yworks.com/xml/graphml"
_XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
_SCHEMA_LOC = (
    "http://graphml.graphdrawing.org/graphml "
    "http://www.yworks.com/xml/schema/graphml/1.1/ygraphml.xsd"
)

# ── Node fill colours by label ────────────────────────────────────────────────

_NODE_COLORS: dict[str, str] = {
    "narrative": "#4A90D9",
    "scene": "#7ED321",
    "atom": "#F5A623",
    "event": "#D0021B",
    "patterninstance": "#9B59B6",
    "pattern": "#C0392B",
    "perspective": "#1ABC9C",
    "moodstate": "#E74C3C",
    "genreprofile": "#3498DB",
    "chronotope": "#27AE60",
    "codetag": "#F39C12",
    "transform": "#95A5A6",
    "character": "#8E44AD",
}
_DEFAULT_NODE_COLOR = "#CCCCCC"

_NODE_WIDTH = 120.0
_NODE_HEIGHT = 40.0


class GraphMLRenderer:
    """Renders a ``GraphState`` as a yEd-compatible GraphML document.

    Edges are coloured by narrative tension (see ``tension_scorer``).
    Structural containment edges (HAS_SCENE, CONTAINS, etc.) are rendered
    in neutral grey; causal/preventive event relations are coloured on the
    full tension gradient.

    :method render: Convert ``GraphState`` to a GraphML XML string.
    """

    def render(self, graph_state: GraphState, params: dict[str, Any]) -> RenderOutput:
        """Produce a yEd-compatible GraphML document from the graph state.

        :param graph_state: Complete narrative snapshot.
        :param params: Optional renderer parameters (currently unused).
        :returns: ``RenderOutput`` with ``content_type="application/xml"``.
        """
        builder = _GraphMLBuilder(graph_state)
        xml_string = builder.build()

        narrative = graph_state.narrative
        node_count = builder.node_count
        edge_count = builder.edge_count
        logger.info(
            "GraphMLRenderer: narrative=%s nodes=%d edges=%d",
            narrative.id,
            node_count,
            edge_count,
        )
        return RenderOutput(
            content=xml_string,
            content_type="application/xml",
            metadata={
                "narrative_id": narrative.id,
                "node_count": node_count,
                "edge_count": edge_count,
                "format": "graphml-yed",
            },
        )


# ── Internal builder ──────────────────────────────────────────────────────────


class _GraphMLBuilder:
    """Stateful builder that walks ``GraphState`` and emits GraphML XML.

    :param graph_state: The narrative snapshot to serialise.
    """

    def __init__(self, graph_state: GraphState) -> None:
        self._gs = graph_state
        self._nodes: list[ET.Element] = []
        self._edges: list[ET.Element] = []
        self._seen_nodes: set[str] = set()
        self._edge_counter = 0

    @property
    def node_count(self) -> int:
        """Number of nodes emitted."""
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        """Number of edges emitted."""
        return len(self._edges)

    def build(self) -> str:
        """Walk the graph state and return the completed GraphML string.

        :returns: UTF-8 encoded GraphML document as a string.
        """
        self._walk()
        return self._serialise()

    # ── Graph traversal ───────────────────────────────────────────────────────

    def _walk(self) -> None:
        narrative = self._gs.narrative
        self._add_node(narrative.id, narrative.title or narrative.id, "narrative")

        for scene in narrative.scenes:
            self._add_scene(narrative, scene)

        for transform in self._gs.transforms:
            self._add_transform(transform)

        for character in self._gs.characters:
            self._add_node(character.id, character.name, "character")

        for rel in self._gs.event_relations:
            ts = score_edge(rel.relation_type)
            self._add_edge(
                rel.source_id,
                rel.target_id,
                rel.relation_type,
                ts.hex_color,
                ts.score,
            )

    def _add_scene(self, narrative: Narrative, scene: Scene) -> None:
        label = f"Scene {scene.sequence}"
        if scene.summary:
            label += f": {scene.summary[:40]}"
        self._add_node(scene.id, label, "scene")
        self._add_structural_edge(narrative.id, scene.id, "HAS_SCENE")

        for atom in scene.atoms:
            self._add_atom(scene, atom)

        for event in scene.events:
            self._add_event(scene, event)

        for pi in scene.pattern_instances:
            self._add_pattern_instance(scene, pi)

        if scene.current_perspective:
            self._add_perspective(scene, scene.current_perspective)

        if scene.current_mood:
            self._add_mood(scene, scene.current_mood)

        if scene.current_genre:
            self._add_genre(scene, scene.current_genre)

        if scene.chronotope:
            self._add_chronotope(scene, scene.chronotope)

    def _add_atom(self, scene: Scene, atom: Atom) -> None:
        label = atom.text[:50] if atom.text else atom.id
        self._add_node(atom.id, label, "atom")
        self._add_structural_edge(scene.id, atom.id, "CONTAINS")

        for tag in atom.code_tags:
            self._add_code_tag(atom, tag)

    def _add_event(self, scene: Scene, event: Event) -> None:
        label = f"{event.verb} ({event.tense})"
        self._add_node(event.id, label, "event")
        self._add_structural_edge(scene.id, event.id, "CONTAINS")

        for character in event.participants:
            if character.id not in self._seen_nodes:
                self._add_node(character.id, character.name, "character")
            ts = score_edge("PARTICIPATES_IN")
            self._add_edge(
                character.id,
                event.id,
                "PARTICIPATES_IN",
                ts.hex_color,
                ts.score,
            )

    def _add_pattern_instance(self, scene: Scene, pi: PatternInstance) -> None:
        label = pi.slot
        self._add_node(pi.id, label, "patterninstance")
        self._add_structural_edge(scene.id, pi.id, "CONTAINS")
        if pi.template is not None:
            if pi.template.id not in self._seen_nodes:
                self._add_node(pi.template.id, pi.template.name, "pattern")
            self._add_structural_edge(pi.id, pi.template.id, "INSTANCE_OF")

    def _add_perspective(self, scene: Scene, pov: Perspective) -> None:
        label = f"POV: {pov.focalizer}"
        self._add_node(pov.id, label, "perspective")
        self._add_structural_edge(scene.id, pov.id, "CURRENT_PERSPECTIVE")

    def _add_mood(self, scene: Scene, mood: MoodState) -> None:
        label = f"Mood: {mood.label}"
        self._add_node(mood.id, label, "moodstate")
        self._add_structural_edge(scene.id, mood.id, "CURRENT_MOOD")

    def _add_genre(self, scene: Scene, genre: GenreProfile) -> None:
        self._add_node(genre.id, genre.name, "genreprofile")
        self._add_structural_edge(scene.id, genre.id, "CURRENT_GENRE")

    def _add_chronotope(self, scene: Scene, ch: Chronotope) -> None:
        label = f"{ch.time_mode}/{ch.space_mode}"
        self._add_node(ch.id, label, "chronotope")
        self._add_structural_edge(scene.id, ch.id, "IN_CHRONOTOPE")

    def _add_code_tag(self, atom: Atom, tag: CodeTag) -> None:
        label = f"{tag.code.value}: {tag.label[:30]}"
        self._add_node(tag.id, label, "codetag")
        self._add_structural_edge(atom.id, tag.id, "TAGGED_AS")

    def _add_transform(self, transform: Transform) -> None:
        label = f"Transform: {transform.axis.value}"
        self._add_node(transform.id, label, "transform")
        if transform.scene_id:
            ts = score_structural_edge("APPLIED_TO")
            self._add_edge(
                transform.id,
                transform.scene_id,
                "APPLIED_TO",
                ts.hex_color,
                ts.score,
            )

    # ── Node / edge factory helpers ───────────────────────────────────────────

    def _add_node(self, node_id: str, label: str, label_type: str) -> None:
        if node_id in self._seen_nodes:
            return
        self._seen_nodes.add(node_id)
        fill = _NODE_COLORS.get(label_type.lower(), _DEFAULT_NODE_COLOR)
        el = _make_node_element(node_id, label, fill)
        self._nodes.append(el)

    def _add_structural_edge(self, source: str, target: str, rel_type: str) -> None:
        ts = score_structural_edge(rel_type)
        self._add_edge(source, target, rel_type, ts.hex_color, ts.score)

    def _add_edge(
        self,
        source: str,
        target: str,
        label: str,
        color: str,
        tension: float,
    ) -> None:
        self._edge_counter += 1
        edge_id = f"e{self._edge_counter}"
        el = _make_edge_element(edge_id, source, target, label, color, tension)
        self._edges.append(el)

    # ── XML serialisation ─────────────────────────────────────────────────────

    def _serialise(self) -> str:
        ET.register_namespace("", _GRAPHML_NS)
        ET.register_namespace("y", _YFILES_NS)
        ET.register_namespace("xsi", _XSI_NS)

        root = ET.Element(
            "graphml",
            attrib={
                "xmlns": _GRAPHML_NS,
                "xmlns:y": _YFILES_NS,
                "xmlns:xsi": _XSI_NS,
                "xsi:schemaLocation": _SCHEMA_LOC,
            },
        )

        # yEd key declarations
        _key(root, "d3", "node", "nodegraphics", "yfiles.type", "nodegraphics")
        _key(root, "d6", "edge", "edgegraphics", "yfiles.type", "edgegraphics")
        _key(root, "d7", "node", "description", "string")
        _key(root, "d8", "edge", "tension_score", "double")

        graph_el = ET.SubElement(
            root,
            "graph",
            attrib={"id": "G", "edgedefault": "directed"},
        )
        for node in self._nodes:
            graph_el.append(node)
        for edge in self._edges:
            graph_el.append(edge)

        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="unicode", xml_declaration=True)


# ── XML element factories ─────────────────────────────────────────────────────


def _key(
    parent: ET.Element,
    key_id: str,
    for_: str,
    attr_name: str,
    attr_type: str,
    yfiles_type: str = "",
) -> ET.Element:
    attrib: dict[str, str] = {
        "id": key_id,
        "for": for_,
        "attr.name": attr_name,
        "attr.type": attr_type,
    }
    if yfiles_type:
        attrib["yfiles.type"] = yfiles_type
    return ET.SubElement(parent, "key", attrib=attrib)


def _make_node_element(node_id: str, label: str, fill: str) -> ET.Element:
    node = ET.Element("node", attrib={"id": _xml_id(node_id)})
    data = ET.SubElement(node, "data", attrib={"key": "d3"})
    shape_node = ET.SubElement(data, "y:ShapeNode")
    ET.SubElement(
        shape_node,
        "y:Geometry",
        attrib={
            "width": str(_NODE_WIDTH),
            "height": str(_NODE_HEIGHT),
        },
    )
    ET.SubElement(shape_node, "y:Fill", attrib={"color": fill, "transparent": "false"})
    ET.SubElement(
        shape_node,
        "y:BorderStyle",
        attrib={"color": "#000000", "type": "line", "width": "1.0"},
    )
    node_label = ET.SubElement(
        shape_node,
        "y:NodeLabel",
        attrib={
            "alignment": "center",
            "fontFamily": "Dialog",
            "fontSize": "11",
            "textColor": "#000000",
            "visible": "true",
        },
    )
    node_label.text = label
    ET.SubElement(shape_node, "y:Shape", attrib={"type": "roundrectangle"})
    return node


def _make_edge_element(
    edge_id: str,
    source: str,
    target: str,
    label: str,
    color: str,
    tension: float,
) -> ET.Element:
    edge = ET.Element(
        "edge",
        attrib={
            "id": edge_id,
            "source": _xml_id(source),
            "target": _xml_id(target),
        },
    )

    # Tension score as a queryable data attribute
    tension_data = ET.SubElement(edge, "data", attrib={"key": "d8"})
    tension_data.text = str(round(tension, 4))

    data = ET.SubElement(edge, "data", attrib={"key": "d6"})
    poly_line = ET.SubElement(data, "y:PolyLineEdge")
    ET.SubElement(
        poly_line,
        "y:LineStyle",
        attrib={"color": color, "type": "line", "width": "2.0"},
    )
    ET.SubElement(poly_line, "y:Arrows", attrib={"source": "none", "target": "standard"})
    edge_label = ET.SubElement(
        poly_line,
        "y:EdgeLabel",
        attrib={
            "alignment": "center",
            "fontFamily": "Dialog",
            "fontSize": "9",
            "textColor": "#000000",
            "visible": "true",
        },
    )
    edge_label.text = label
    return edge


def _xml_id(raw: str) -> str:
    """Escape a node ID for use as a GraphML XML attribute value.

    GraphML ``id`` attributes must be valid XML Name tokens.  Periods and
    hyphens are legal in XML Names; spaces are not.  Replace spaces and
    forward-slashes with underscores.

    :param raw: The original node ID string.
    :returns: A sanitised XML-safe identifier.
    """
    return raw.replace(" ", "_").replace("/", "_")
