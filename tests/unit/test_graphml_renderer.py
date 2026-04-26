"""Unit tests for the GraphML renderer and tension scorer.

Tests cover:
- Tension score computation (base, code bonus, mood bonus, clamping)
- Colour interpolation across the six-stop gradient
- GraphML document structure (XML well-formedness, key declarations)
- Node and edge presence for a minimal synthetic GraphState
- yEd key declarations (d3, d6, d7, d8)
- Edge tension_score data values
- XML ID sanitisation
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime

import pytest

from tng.domain.enums import (
    AtomKind,
    BarthesCode,
    FocalizationDistance,
    NarrativeStatus,
    ReliabilityLevel,
    TransformAxis,
)
from tng.domain.models import (
    Atom,
    Character,
    CodeTag,
    Event,
    EventRelation,
    GenreProfile,
    GraphState,
    MoodState,
    Narrative,
    PatternInstance,
    Pattern,
    Perspective,
    Scene,
    Transform,
)
from tng.renderers.graphml_renderer import GraphMLRenderer, _xml_id
from tng.renderers.tension_scorer import (
    RELATION_BASE,
    TensionScore,
    _code_bonus,
    _interpolate_color,
    _mood_bonus,
    score_edge,
    score_structural_edge,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def minimal_graph_state() -> GraphState:
    """A minimal GraphState with one narrative, one scene, one atom."""
    atom = Atom(id="atom-1", text="She walked slowly.", kind=AtomKind.DESCRIPTIVE)
    scene = Scene(id="scene-1", sequence=1, summary="Opening", atoms=[atom])
    narrative = Narrative(
        id="nar-1",
        title="Test Narrative",
        status=NarrativeStatus.ATOMIZED,
        scenes=[scene],
        created_at=datetime(2026, 1, 1),
    )
    return GraphState(narrative=narrative)


@pytest.fixture()
def rich_graph_state() -> GraphState:
    """A richer GraphState exercising most node/edge types."""
    code_tag = CodeTag(id="ct-1", code=BarthesCode.HERMENEUTIC, label="mystery")
    atom = Atom(
        id="atom-2",
        text="The door was locked.",
        kind=AtomKind.DESCRIPTIVE,
        code_tags=[code_tag],
    )
    character = Character(id="char-1", name="Alice", role="protagonist")
    event = Event(
        id="event-1",
        verb="lock",
        tense="past",
        participants=[character],
    )
    mood = MoodState(id="mood-1", label="tense", valence=-0.6, arousal=0.8)
    perspective = Perspective(
        id="pov-1",
        focalizer="char-1",
        distance=FocalizationDistance.INTERNAL,
        reliability=ReliabilityLevel.RELIABLE,
    )
    genre = GenreProfile(id="genre-1", name="gothic", conventions=["isolation"])
    pattern = Pattern(id="pat-1", name="revelation", family="revelation", description="")
    pi = PatternInstance(id="pi-1", slot="scene-core", template=pattern)
    scene = Scene(
        id="scene-2",
        sequence=1,
        atoms=[atom],
        events=[event],
        pattern_instances=[pi],
        current_perspective=perspective,
        current_mood=mood,
        current_genre=genre,
    )
    narrative = Narrative(
        id="nar-2",
        title="Rich Narrative",
        scenes=[scene],
        created_at=datetime(2026, 1, 1),
    )
    transform = Transform(
        id="xform-1",
        axis=TransformAxis.POV,
        operator="user",
        applied_at=datetime(2026, 1, 2),
        scene_id="scene-2",
        produced_id="pov-1",
    )
    rel = EventRelation(
        source_id="event-1",
        target_id="event-2",
        relation_type="CAUSES",
    )
    return GraphState(
        narrative=narrative,
        transforms=[transform],
        characters=[character],
        event_relations=[rel],
    )


# ── Tension scorer: base scores ───────────────────────────────────────────────


class TestRelationBase:
    def test_prevents_is_highest(self) -> None:
        ts = score_edge("PREVENTS")
        assert ts.base == pytest.approx(0.9)

    def test_causes_score(self) -> None:
        ts = score_edge("CAUSES")
        assert ts.base == pytest.approx(0.7)

    def test_enables_score(self) -> None:
        ts = score_edge("ENABLES")
        assert ts.base == pytest.approx(0.4)

    def test_precedes_is_lowest(self) -> None:
        ts = score_edge("PRECEDES")
        assert ts.base == pytest.approx(0.2)

    def test_unknown_relation_is_zero(self) -> None:
        ts = score_edge("HAS_SCENE")
        assert ts.base == pytest.approx(0.0)

    def test_structural_edge_helper_returns_zero_tension(self) -> None:
        ts = score_structural_edge()
        assert ts.score == pytest.approx(0.0)


# ── Tension scorer: code bonus ────────────────────────────────────────────────


class TestCodeBonus:
    def test_hermeneutic_gives_highest_bonus(self) -> None:
        atom = Atom(
            id="a1",
            text="x",
            code_tags=[CodeTag(id="ct1", code=BarthesCode.HERMENEUTIC, label="enigma")],
        )
        assert _code_bonus([atom]) == pytest.approx(0.4)

    def test_cultural_gives_zero_bonus(self) -> None:
        atom = Atom(
            id="a2",
            text="x",
            code_tags=[CodeTag(id="ct2", code=BarthesCode.CULTURAL, label="ref")],
        )
        assert _code_bonus([atom]) == pytest.approx(0.0)

    def test_best_modifier_selected_across_multiple_atoms(self) -> None:
        a1 = Atom(
            id="a3",
            text="x",
            code_tags=[CodeTag(id="ct3", code=BarthesCode.SEMIC, label="s")],
        )
        a2 = Atom(
            id="a4",
            text="y",
            code_tags=[CodeTag(id="ct4", code=BarthesCode.PROAIRETIC, label="p")],
        )
        assert _code_bonus([a1, a2]) == pytest.approx(0.3)

    def test_no_atoms_gives_zero(self) -> None:
        assert _code_bonus([]) == pytest.approx(0.0)


# ── Tension scorer: mood bonus ────────────────────────────────────────────────


class TestMoodBonus:
    def test_high_arousal_negative_valence_gives_positive_bonus(self) -> None:
        mood = MoodState(id="m1", label="tense", valence=-1.0, arousal=1.0)
        bonus = _mood_bonus(mood)
        assert bonus == pytest.approx(0.6)

    def test_positive_valence_gives_zero_bonus(self) -> None:
        mood = MoodState(id="m2", label="happy", valence=1.0, arousal=0.9)
        assert _mood_bonus(mood) == pytest.approx(0.0)

    def test_none_mood_gives_zero(self) -> None:
        assert _mood_bonus(None) == pytest.approx(0.0)

    def test_partial_negative_valence(self) -> None:
        mood = MoodState(id="m3", label="uneasy", valence=-0.5, arousal=0.5)
        expected = 0.5 * 0.5 * 0.6
        assert _mood_bonus(mood) == pytest.approx(expected)


# ── Tension scorer: score_edge composite ─────────────────────────────────────


class TestScoreEdge:
    def test_score_is_clamped_to_one(self) -> None:
        atom = Atom(
            id="ax",
            text="x",
            code_tags=[CodeTag(id="ctx", code=BarthesCode.HERMENEUTIC, label="e")],
        )
        mood = MoodState(id="mx", label="horror", valence=-1.0, arousal=1.0)
        ts = score_edge("PREVENTS", atoms=[atom], mood=mood)
        assert ts.score <= 1.0

    def test_score_is_clamped_to_zero(self) -> None:
        ts = score_edge("_unknown")
        assert ts.score >= 0.0

    def test_returns_tension_score_instance(self) -> None:
        ts = score_edge("CAUSES")
        assert isinstance(ts, TensionScore)

    def test_hex_color_is_valid_hex(self) -> None:
        ts = score_edge("CAUSES")
        assert ts.hex_color.startswith("#")
        assert len(ts.hex_color) == 7


# ── Colour interpolation ──────────────────────────────────────────────────────


class TestColorInterpolation:
    def test_zero_maps_to_grey(self) -> None:
        color = _interpolate_color(0.0)
        assert color == "#A0A0A0"

    def test_one_maps_to_dark_red(self) -> None:
        color = _interpolate_color(1.0)
        assert color == "#8B0000"

    def test_midpoint_is_not_grey_and_not_dark_red(self) -> None:
        color = _interpolate_color(0.5)
        assert color != "#A0A0A0"
        assert color != "#8B0000"

    def test_all_outputs_are_six_char_hex(self) -> None:
        for t in [0.0, 0.1, 0.25, 0.4, 0.6, 0.8, 1.0]:
            c = _interpolate_color(t)
            assert c.startswith("#"), f"Missing # for t={t}"
            assert len(c) == 7, f"Wrong length for t={t}: {c}"

    def test_above_one_is_clamped(self) -> None:
        assert _interpolate_color(1.5) == _interpolate_color(1.0)

    def test_below_zero_is_clamped(self) -> None:
        assert _interpolate_color(-0.5) == _interpolate_color(0.0)


# ── GraphML renderer: XML structure ──────────────────────────────────────────


class TestGraphMLRendererStructure:
    def test_returns_render_output_with_xml_content_type(
        self, minimal_graph_state: GraphState
    ) -> None:
        renderer = GraphMLRenderer()
        output = renderer.render(minimal_graph_state, {})
        assert output.content_type == "application/xml"

    def test_content_is_well_formed_xml(
        self, minimal_graph_state: GraphState
    ) -> None:
        renderer = GraphMLRenderer()
        output = renderer.render(minimal_graph_state, {})
        root = ET.fromstring(output.content)
        assert root is not None

    def test_root_element_is_graphml(
        self, minimal_graph_state: GraphState
    ) -> None:
        renderer = GraphMLRenderer()
        output = renderer.render(minimal_graph_state, {})
        root = ET.fromstring(output.content)
        assert "graphml" in root.tag.lower()

    def test_yed_key_declarations_present(
        self, minimal_graph_state: GraphState
    ) -> None:
        renderer = GraphMLRenderer()
        output = renderer.render(minimal_graph_state, {})
        root = ET.fromstring(output.content)
        key_ids = {
            el.get("id")
            for el in root
            if el.tag.endswith("key")
        }
        assert "d3" in key_ids, "Missing node graphics key d3"
        assert "d6" in key_ids, "Missing edge graphics key d6"
        assert "d8" in key_ids, "Missing tension_score key d8"

    def test_graph_element_is_directed(
        self, minimal_graph_state: GraphState
    ) -> None:
        renderer = GraphMLRenderer()
        output = renderer.render(minimal_graph_state, {})
        root = ET.fromstring(output.content)
        ns = "{http://graphml.graphdrawing.org/graphml}"
        graph = root.find(f"{ns}graph")
        assert graph is not None
        assert graph.get("edgedefault") == "directed"


# ── GraphML renderer: nodes ───────────────────────────────────────────────────


class TestGraphMLRendererNodes:
    def _get_node_ids(self, content: str) -> set[str]:
        root = ET.fromstring(content)
        ns = "{http://graphml.graphdrawing.org/graphml}"
        graph = root.find(f"{ns}graph")
        return {el.get("id") for el in graph if el.tag == f"{ns}node"}  # type: ignore[union-attr]

    def test_narrative_node_present(
        self, minimal_graph_state: GraphState
    ) -> None:
        output = GraphMLRenderer().render(minimal_graph_state, {})
        assert "nar-1" in self._get_node_ids(output.content)

    def test_scene_node_present(
        self, minimal_graph_state: GraphState
    ) -> None:
        output = GraphMLRenderer().render(minimal_graph_state, {})
        assert "scene-1" in self._get_node_ids(output.content)

    def test_atom_node_present(
        self, minimal_graph_state: GraphState
    ) -> None:
        output = GraphMLRenderer().render(minimal_graph_state, {})
        assert "atom-1" in self._get_node_ids(output.content)

    def test_rich_state_has_all_node_types(
        self, rich_graph_state: GraphState
    ) -> None:
        output = GraphMLRenderer().render(rich_graph_state, {})
        node_ids = self._get_node_ids(output.content)
        expected = {"nar-2", "scene-2", "atom-2", "event-1", "pi-1", "pat-1",
                    "pov-1", "mood-1", "genre-1", "char-1", "ct-1", "xform-1"}
        missing = expected - node_ids
        assert not missing, f"Missing nodes: {missing}"

    def test_node_count_in_metadata(
        self, minimal_graph_state: GraphState
    ) -> None:
        output = GraphMLRenderer().render(minimal_graph_state, {})
        assert output.metadata["node_count"] >= 3


# ── GraphML renderer: edges ───────────────────────────────────────────────────


class TestGraphMLRendererEdges:
    def _get_edges(self, content: str) -> list[dict[str, str]]:
        root = ET.fromstring(content)
        ns = "{http://graphml.graphdrawing.org/graphml}"
        graph = root.find(f"{ns}graph")
        return [
            {"source": el.get("source", ""), "target": el.get("target", "")}
            for el in graph  # type: ignore[union-attr]
            if el.tag == f"{ns}edge"
        ]

    def test_has_scene_edge_present(
        self, minimal_graph_state: GraphState
    ) -> None:
        output = GraphMLRenderer().render(minimal_graph_state, {})
        edges = self._get_edges(output.content)
        assert any(e["source"] == "nar-1" and e["target"] == "scene-1" for e in edges)

    def test_contains_edge_for_atom(
        self, minimal_graph_state: GraphState
    ) -> None:
        output = GraphMLRenderer().render(minimal_graph_state, {})
        edges = self._get_edges(output.content)
        assert any(e["source"] == "scene-1" and e["target"] == "atom-1" for e in edges)

    def test_causes_relation_edge_present(
        self, rich_graph_state: GraphState
    ) -> None:
        output = GraphMLRenderer().render(rich_graph_state, {})
        edges = self._get_edges(output.content)
        assert any(e["source"] == "event-1" and e["target"] == "event-2" for e in edges)

    def test_edge_has_tension_score_data(
        self, rich_graph_state: GraphState
    ) -> None:
        output = GraphMLRenderer().render(rich_graph_state, {})
        root = ET.fromstring(output.content)
        ns = "{http://graphml.graphdrawing.org/graphml}"
        graph = root.find(f"{ns}graph")
        tension_data = [
            child
            for el in graph  # type: ignore[union-attr]
            if el.tag == f"{ns}edge"
            for child in el
            if child.get("key") == "d8"
        ]
        assert tension_data, "No tension score data elements found on edges"
        for data_el in tension_data:
            assert data_el.text is not None
            val = float(data_el.text)
            assert 0.0 <= val <= 1.0


# ── XML ID sanitisation ───────────────────────────────────────────────────────


class TestXmlId:
    def test_spaces_replaced(self) -> None:
        assert _xml_id("hello world") == "hello_world"

    def test_slashes_replaced(self) -> None:
        assert _xml_id("a/b/c") == "a_b_c"

    def test_plain_id_unchanged(self) -> None:
        assert _xml_id("atom-1") == "atom-1"

    def test_dots_unchanged(self) -> None:
        assert _xml_id("pattern.gift_exchange") == "pattern.gift_exchange"
