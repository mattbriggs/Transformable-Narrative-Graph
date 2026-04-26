"""Unit tests for all five renderer implementations."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tng.domain.enums import AtomKind, NarrativeStatus, TransformAxis
from tng.domain.models import (
    Atom,
    Event,
    GraphState,
    MoodState,
    Narrative,
    Perspective,
    Scene,
    Transform,
)
from tng.domain.enums import FocalizationDistance, ReliabilityLevel
from tng.renderers.cypher_renderer import CypherRenderer
from tng.renderers.diff_renderer import DiffRenderer
from tng.renderers.json_renderer import JSONRenderer
from tng.renderers.markdown_renderer import MarkdownRenderer
from tng.renderers.prose_renderer import ProseRenderer
from tng.renderers.protocol import RendererProtocol, RenderOutput


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_graph_state(include_transforms: bool = False) -> GraphState:
    atom1 = Atom(id="a1", text="Alice walked.", kind=AtomKind.DESCRIPTIVE, surface_order=0)
    atom2 = Atom(id="a2", text="She stopped.", kind=AtomKind.DESCRIPTIVE, surface_order=1)
    event = Event(id="e1", verb="walk", tense="past")
    pov = Perspective(
        id="pov1",
        focalizer="char-001",
        distance=FocalizationDistance.INTERNAL,
        reliability=ReliabilityLevel.RELIABLE,
    )
    mood = MoodState(id="m1", label="pensive", valence=-0.2, arousal=0.4)
    scene = Scene(
        id="s1",
        sequence=1,
        summary="Opening scene.",
        atoms=[atom1, atom2],
        events=[event],
        current_perspective=pov,
        current_mood=mood,
    )
    narrative = Narrative(
        id="n1",
        title="Test Story",
        status=NarrativeStatus.TRANSFORMED,
        scenes=[scene],
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    transforms = []
    if include_transforms:
        transforms = [
            Transform(
                id="t1",
                axis=TransformAxis.POV,
                operator="alice",
                applied_at=datetime(2026, 1, 2, 10, 0, 0),
                parameters={"focalizer": "char-001"},
                scene_id="s1",
                produced_id="pov1",
            )
        ]
    return GraphState(narrative=narrative, transforms=transforms)


# ── Protocol tests ────────────────────────────────────────────────────────────


class TestRendererProtocol:
    """Verify that all renderers implement the protocol."""

    def test_prose_renderer_implements_protocol(self):
        assert isinstance(ProseRenderer(), RendererProtocol)

    def test_diff_renderer_implements_protocol(self):
        assert isinstance(DiffRenderer(), RendererProtocol)

    def test_json_renderer_implements_protocol(self):
        assert isinstance(JSONRenderer(), RendererProtocol)

    def test_cypher_renderer_implements_protocol(self):
        assert isinstance(CypherRenderer(), RendererProtocol)

    def test_markdown_renderer_implements_protocol(self):
        assert isinstance(MarkdownRenderer(), RendererProtocol)


# ── ProseRenderer tests ───────────────────────────────────────────────────────


class TestProseRenderer:
    """Tests for ``ProseRenderer``."""

    def test_output_contains_narrative_title(self):
        gs = _make_graph_state()
        output = ProseRenderer().render(gs, {})
        assert "Test Story" in output.content

    def test_output_contains_atom_text(self):
        gs = _make_graph_state()
        output = ProseRenderer().render(gs, {})
        assert "Alice walked." in output.content

    def test_output_contains_pov_context(self):
        gs = _make_graph_state()
        output = ProseRenderer().render(gs, {})
        assert "char-001" in output.content

    def test_content_type_is_markdown(self):
        gs = _make_graph_state()
        output = ProseRenderer().render(gs, {})
        assert output.content_type == "text/markdown"

    def test_atoms_in_surface_order(self):
        gs = _make_graph_state()
        output = ProseRenderer().render(gs, {})
        pos1 = output.content.find("Alice walked.")
        pos2 = output.content.find("She stopped.")
        assert pos1 < pos2

    def test_scene_with_summary_uses_summary_as_heading(self):
        gs = _make_graph_state()
        output = ProseRenderer().render(gs, {})
        assert "## Opening scene." in output.content
        assert "## Scene 1" not in output.content

    def test_scene_without_summary_falls_back_to_scene_number(self):
        atom = Atom(id="ax", text="Something happened.", kind=AtomKind.DESCRIPTIVE, surface_order=0)
        scene = Scene(id="sx", sequence=3, summary="", atoms=[atom])
        narrative = Narrative(id="nx", title="T", scenes=[scene])
        gs = GraphState(narrative=narrative)
        output = ProseRenderer().render(gs, {})
        assert "## Scene 3" in output.content


# ── DiffRenderer tests ────────────────────────────────────────────────────────


class TestDiffRenderer:
    """Tests for ``DiffRenderer``."""

    def test_output_is_valid_json(self):
        gs = _make_graph_state(include_transforms=True)
        output = DiffRenderer().render(gs, {})
        doc = json.loads(output.content)
        assert "diff_by_axis" in doc

    def test_transform_axis_present(self):
        gs = _make_graph_state(include_transforms=True)
        output = DiffRenderer().render(gs, {})
        doc = json.loads(output.content)
        assert "pov" in doc["diff_by_axis"]

    def test_empty_transforms_returns_valid_json(self):
        gs = _make_graph_state(include_transforms=False)
        output = DiffRenderer().render(gs, {})
        doc = json.loads(output.content)
        assert doc["total_transforms"] == 0

    def test_content_type_json(self):
        gs = _make_graph_state()
        output = DiffRenderer().render(gs, {})
        assert output.content_type == "application/json"


# ── JSONRenderer tests ────────────────────────────────────────────────────────


class TestJSONRenderer:
    """Tests for ``JSONRenderer``."""

    def test_output_is_valid_json(self):
        gs = _make_graph_state()
        output = JSONRenderer().render(gs, {})
        doc = json.loads(output.content)
        assert "narrative" in doc

    def test_scenes_included(self):
        gs = _make_graph_state()
        output = JSONRenderer().render(gs, {})
        doc = json.loads(output.content)
        assert len(doc["narrative"]["scenes"]) == 1

    def test_atoms_included_in_scene(self):
        gs = _make_graph_state()
        output = JSONRenderer().render(gs, {})
        doc = json.loads(output.content)
        atoms = doc["narrative"]["scenes"][0]["atoms"]
        assert len(atoms) == 2

    def test_content_type_json(self):
        gs = _make_graph_state()
        output = JSONRenderer().render(gs, {})
        assert output.content_type == "application/json"


# ── CypherRenderer tests ──────────────────────────────────────────────────────


class TestCypherRenderer:
    """Tests for ``CypherRenderer``."""

    def test_output_contains_merge_narrative(self):
        gs = _make_graph_state()
        output = CypherRenderer().render(gs, {})
        assert "MERGE (n:Narrative" in output.content

    def test_output_contains_merge_scene(self):
        gs = _make_graph_state()
        output = CypherRenderer().render(gs, {})
        assert "MERGE (s:Scene" in output.content

    def test_output_contains_atom_merge(self):
        gs = _make_graph_state()
        output = CypherRenderer().render(gs, {})
        assert "MERGE (a:Atom" in output.content

    def test_content_type_cypher(self):
        gs = _make_graph_state()
        output = CypherRenderer().render(gs, {})
        assert output.content_type == "text/x-cypher"


# ── MarkdownRenderer tests ────────────────────────────────────────────────────


class TestMarkdownRenderer:
    """Tests for ``MarkdownRenderer``."""

    def test_output_contains_title(self):
        gs = _make_graph_state()
        output = MarkdownRenderer().render(gs, {})
        assert "# Test Story" in output.content

    def test_output_contains_scene_header(self):
        gs = _make_graph_state()
        output = MarkdownRenderer().render(gs, {})
        assert "### Scene 1" in output.content

    def test_transform_table_included(self):
        gs = _make_graph_state(include_transforms=True)
        output = MarkdownRenderer().render(gs, {})
        assert "Transformation History" in output.content

    def test_empty_transforms_no_table(self):
        gs = _make_graph_state(include_transforms=False)
        output = MarkdownRenderer().render(gs, {})
        assert "Transformation History" not in output.content

    def test_content_type_markdown(self):
        gs = _make_graph_state()
        output = MarkdownRenderer().render(gs, {})
        assert output.content_type == "text/markdown"
