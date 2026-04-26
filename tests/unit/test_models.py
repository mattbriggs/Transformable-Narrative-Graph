"""Unit tests for domain models and enumerations."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tng.domain.enums import (
    AtomKind,
    BarthesCode,
    FocalizationDistance,
    NarrativeStatus,
    ReliabilityLevel,
    RenderType,
    TransformAxis,
)
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
    Pattern,
    PatternInstance,
    Perspective,
    Scene,
    Transform,
)


class TestEnums:
    """Enumeration value and membership tests."""

    def test_atom_kind_values(self):
        assert AtomKind.DESCRIPTIVE.value == "descriptive"
        assert AtomKind.DIALOGIC.value == "dialogic"
        assert len(AtomKind) == 5

    def test_barthes_code_values(self):
        assert BarthesCode.HERMENEUTIC.value == "hermeneutic"
        assert len(BarthesCode) == 5

    def test_transform_axis_values(self):
        assert TransformAxis.POV.value == "pov"
        assert TransformAxis.CODE_OVERLAY.value == "code_overlay"
        assert len(TransformAxis) == 6

    def test_narrative_status_values(self):
        assert NarrativeStatus.DRAFT.value == "draft"
        assert NarrativeStatus.ARCHIVED.value == "archived"
        assert len(NarrativeStatus) == 7

    def test_focalization_distance_members(self):
        assert FocalizationDistance.ZERO in FocalizationDistance
        assert FocalizationDistance.INTERNAL in FocalizationDistance
        assert FocalizationDistance.EXTERNAL in FocalizationDistance

    def test_reliability_level_members(self):
        assert ReliabilityLevel.RELIABLE in ReliabilityLevel
        assert ReliabilityLevel.UNRELIABLE in ReliabilityLevel
        assert ReliabilityLevel.AMBIGUOUS in ReliabilityLevel

    def test_render_type_members(self):
        assert RenderType.PROSE in RenderType
        assert RenderType.CYPHER in RenderType
        assert RenderType.GRAPHML in RenderType
        assert len(RenderType) == 6


class TestAtom:
    """Atom model validation tests."""

    def test_default_kind_is_descriptive(self):
        atom = Atom(id="a1", text="Hello world.")
        assert atom.kind == AtomKind.DESCRIPTIVE

    def test_confidence_clamped_at_boundaries(self):
        atom = Atom(id="a1", text=".", confidence=0.0)
        assert atom.confidence == 0.0
        atom2 = Atom(id="a2", text=".", confidence=1.0)
        assert atom2.confidence == 1.0

    def test_confidence_above_1_raises(self):
        with pytest.raises(ValidationError):
            Atom(id="a1", text=".", confidence=1.5)

    def test_confidence_below_0_raises(self):
        with pytest.raises(ValidationError):
            Atom(id="a1", text=".", confidence=-0.1)

    def test_code_tags_default_empty(self):
        atom = Atom(id="a1", text="test")
        assert atom.code_tags == []

    def test_code_tag_attachment(self):
        tag = CodeTag(id="ct1", code=BarthesCode.SEMIC, label="mood marker")
        atom = Atom(id="a1", text="test", code_tags=[tag])
        assert atom.code_tags[0].code == BarthesCode.SEMIC


class TestEvent:
    """Event model validation tests."""

    def test_defaults(self):
        event = Event(id="e1", verb="walk")
        assert event.tense == "past"
        assert event.aspect == "simple"
        assert event.confidence == 1.0

    def test_participants_default_empty(self):
        event = Event(id="e1", verb="run")
        assert event.participants == []

    def test_needs_review_default_false(self):
        event = Event(id="e1", verb="see")
        assert not event.needs_review


class TestPerspective:
    """Perspective model tests."""

    def test_defaults(self):
        p = Perspective(id="pov1", focalizer="char-001")
        assert p.distance == FocalizationDistance.ZERO
        assert p.reliability == ReliabilityLevel.RELIABLE

    def test_frozen(self):
        p = Perspective(id="pov1", focalizer="char-001")
        with pytest.raises(Exception):
            p.focalizer = "changed"  # frozen model


class TestMoodState:
    """MoodState model tests."""

    def test_valence_bounds(self):
        with pytest.raises(ValidationError):
            MoodState(id="m1", label="sad", valence=-1.5)
        with pytest.raises(ValidationError):
            MoodState(id="m1", label="sad", valence=1.5)

    def test_arousal_bounds(self):
        with pytest.raises(ValidationError):
            MoodState(id="m1", label="calm", arousal=-0.1)
        with pytest.raises(ValidationError):
            MoodState(id="m1", label="calm", arousal=1.1)


class TestScene:
    """Scene model tests."""

    def test_defaults(self):
        scene = Scene(id="s1")
        assert scene.sequence == 1
        assert scene.atoms == []
        assert scene.events == []
        assert scene.current_perspective is None

    def test_atoms_and_events_populated(self):
        atom = Atom(id="a1", text="test")
        event = Event(id="e1", verb="run")
        scene = Scene(id="s1", atoms=[atom], events=[event])
        assert len(scene.atoms) == 1
        assert len(scene.events) == 1


class TestNarrative:
    """Narrative model tests."""

    def test_default_status_is_draft(self):
        n = Narrative(id="n1", title="My Story")
        assert n.status == NarrativeStatus.DRAFT

    def test_scenes_default_empty(self):
        n = Narrative(id="n1", title="Story")
        assert n.scenes == []


class TestGraphState:
    """GraphState snapshot model tests."""

    def test_transforms_default_empty(self):
        n = Narrative(id="n1", title="S")
        gs = GraphState(narrative=n)
        assert gs.transforms == []

    def test_characters_default_empty(self):
        n = Narrative(id="n1", title="S")
        gs = GraphState(narrative=n)
        assert gs.characters == []
