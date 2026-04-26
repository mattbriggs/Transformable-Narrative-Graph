"""Unit tests for the ingest annotator."""

from __future__ import annotations

import pytest

from tng.domain.enums import AtomKind
from tng.ingest.annotator import annotate_atoms, annotate_characters, annotate_events
from tng.ingest.entity_extractor import ExtractedEntity
from tng.ingest.event_detector import DetectedEvent


class TestAnnotateAtoms:
    """Tests for ``annotate_atoms``."""

    def test_returns_one_atom_per_sentence(self):
        sentences = ["Alice ran.", "Bob stopped.", "Carol watched."]
        atoms = annotate_atoms(sentences)
        assert len(atoms) == 3

    def test_surface_order_is_sequential(self):
        sentences = ["First.", "Second.", "Third."]
        atoms = annotate_atoms(sentences)
        orders = [a.surface_order for a in atoms]
        assert orders == [0, 1, 2]

    def test_each_atom_has_unique_id(self):
        sentences = ["One.", "Two.", "Three."]
        atoms = annotate_atoms(sentences)
        ids = [a.id for a in atoms]
        assert len(set(ids)) == 3

    def test_short_sentence_lower_confidence(self):
        atoms = annotate_atoms(["Hi."])
        assert atoms[0].confidence < 0.9

    def test_review_flag_set_below_threshold(self):
        atoms = annotate_atoms(["Hi."], confidence_threshold=0.99)
        assert atoms[0].needs_review

    def test_dialogic_classification(self):
        atoms = annotate_atoms(['"Hello," she said.'])
        assert atoms[0].kind == AtomKind.DIALOGIC

    def test_reflexive_classification(self):
        atoms = annotate_atoms(["She thought about the past."])
        assert atoms[0].kind == AtomKind.REFLEXIVE

    def test_transitional_classification(self):
        atoms = annotate_atoms(["Then the door opened."])
        assert atoms[0].kind == AtomKind.TRANSITIONAL

    def test_expository_classification(self):
        atoms = annotate_atoms(["She was a doctor."])
        assert atoms[0].kind == AtomKind.EXPOSITORY

    def test_default_descriptive(self):
        atoms = annotate_atoms(["The rain fell heavily."])
        assert atoms[0].kind == AtomKind.DESCRIPTIVE

    def test_empty_sentences_returns_empty(self):
        atoms = annotate_atoms([])
        assert atoms == []


class TestAnnotateCharacters:
    """Tests for ``annotate_characters``."""

    def test_creates_character_per_entity(self):
        entities = [
            ExtractedEntity(name="Alice", mentions=2),
            ExtractedEntity(name="Bob", mentions=1),
        ]
        chars = annotate_characters(entities)
        assert len(chars) == 2

    def test_character_names_match_entities(self):
        entities = [ExtractedEntity(name="Carol")]
        chars = annotate_characters(entities)
        assert chars[0].name == "Carol"

    def test_all_characters_have_unique_ids(self):
        entities = [ExtractedEntity(name=f"Person{i}") for i in range(5)]
        chars = annotate_characters(entities)
        assert len({c.id for c in chars}) == 5

    def test_empty_entities_returns_empty(self):
        chars = annotate_characters([])
        assert chars == []


class TestAnnotateEvents:
    """Tests for ``annotate_events``."""

    def test_creates_event_per_detected(self):
        detected = [
            DetectedEvent(verb="walk", source_sentence="Alice walked."),
            DetectedEvent(verb="run", source_sentence="Bob ran."),
        ]
        events = annotate_events(detected, [])
        assert len(events) == 2

    def test_participant_linked_when_name_in_sentence(self):
        from tng.domain.models import Character
        char = Character(id="c1", name="Alice", role="protagonist")
        detected = [DetectedEvent(verb="walk", source_sentence="Alice walked.")]
        events = annotate_events(detected, [char])
        assert char in events[0].participants

    def test_no_participant_when_name_absent(self):
        from tng.domain.models import Character
        char = Character(id="c1", name="Bob", role="character")
        detected = [DetectedEvent(verb="walk", source_sentence="Alice walked.")]
        events = annotate_events(detected, [char])
        assert events[0].participants == []

    def test_empty_detected_returns_empty(self):
        events = annotate_events([], [])
        assert events == []
