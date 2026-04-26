"""Unit tests for the entity extractor."""

from __future__ import annotations

import pytest

from tng.ingest.entity_extractor import extract_entities


class TestExtractEntities:
    """Tests for ``extract_entities``."""

    def test_single_mention(self):
        entities = extract_entities(["Then Alice arrived at the station."])
        names = [e.name for e in entities]
        assert "Alice" in names

    def test_multiple_mentions_raise_confidence(self):
        entities = extract_entities([
            "Then Alice walked. Alice stopped. Alice turned."
        ])
        alice = next((e for e in entities if e.name == "Alice"), None)
        assert alice is not None
        assert alice.mentions >= 2

    def test_ignores_sentence_initial_common_words(self):
        entities = extract_entities(["The river ran fast. A boat appeared."])
        names = [e.name for e in entities]
        assert "The" not in names
        assert "A" not in names

    def test_empty_input_returns_empty(self):
        entities = extract_entities([])
        assert entities == []

    def test_needs_review_flag_set_below_threshold(self):
        entities = extract_entities(
            ["Then Bob spoke."], confidence_threshold=0.99
        )
        # single-mention entity should be below 0.99
        if entities:
            assert all(e.needs_review for e in entities)

    def test_multi_word_name(self):
        entities = extract_entities(["Then Lord Blackwood entered the hall."])
        names = [e.name for e in entities]
        assert any("Blackwood" in n or "Lord" in n for n in names)

    def test_sorted_by_descending_mentions(self):
        sentences = [
            "Alice spoke. Alice ran. Bob arrived."
        ]
        entities = extract_entities(sentences)
        if len(entities) >= 2:
            assert entities[0].mentions >= entities[1].mentions
