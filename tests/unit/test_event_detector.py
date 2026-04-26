"""Unit tests for the event detector."""

from __future__ import annotations

import pytest

from tng.ingest.event_detector import detect_events


class TestDetectEvents:
    """Tests for ``detect_events``."""

    def test_simple_past_tense(self):
        events = detect_events(["Alice walked to the door."])
        assert len(events) == 1
        assert events[0].tense == "past"

    def test_simple_present_tense(self):
        events = detect_events(["She runs every morning."])
        assert len(events) >= 1

    def test_future_tense_detected(self):
        events = detect_events(["She will arrive tomorrow."])
        assert any(e.tense == "future" for e in events)

    def test_progressive_aspect(self):
        events = detect_events(["He was walking down the street."])
        assert any(e.aspect == "progressive" for e in events)

    def test_empty_input_returns_empty(self):
        events = detect_events([])
        assert events == []

    def test_source_sentence_preserved(self):
        sentence = "Alice ran quickly."
        events = detect_events([sentence])
        assert events[0].source_sentence == sentence

    def test_needs_review_flag_below_threshold(self):
        events = detect_events(["Bob ran."], confidence_threshold=0.99)
        if events:
            assert events[0].needs_review

    def test_needs_review_false_above_threshold(self):
        events = detect_events(["Bob ran."], confidence_threshold=0.1)
        if events:
            assert not events[0].needs_review

    def test_confidence_between_0_and_1(self):
        events = detect_events(["She had arrived late."])
        if events:
            assert 0.0 <= events[0].confidence <= 1.0
