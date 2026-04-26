"""Unit tests for the PatternService."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tng.domain.models import Atom, Event, Pattern, PatternInstance
from tng.domain.enums import AtomKind
from tng.repository.graph_repository import GraphRepository
from tng.services.pattern_service import (
    KeywordAtomMatcher,
    PatternService,
    VerbFamilyMatcher,
)


@pytest.fixture
def gift_pattern():
    return Pattern(
        id="pattern.gift_exchange",
        name="Gift Exchange",
        family="ritual",
        description="A giving event.",
    )


@pytest.fixture
def threshold_pattern():
    return Pattern(
        id="pattern.threshold_crossing",
        name="Threshold Crossing",
        family="transition",
        description="Entering or leaving.",
    )


class TestVerbFamilyMatcher:
    """Tests for ``VerbFamilyMatcher``."""

    def test_matches_when_verb_present(self, gift_pattern):
        matcher = VerbFamilyMatcher(verb_hints=frozenset({"give"}))
        event = Event(id="e1", verb="give")
        result = matcher.match(gift_pattern, [], [event])
        assert result is not None
        assert isinstance(result, PatternInstance)

    def test_no_match_when_verb_absent(self, gift_pattern):
        matcher = VerbFamilyMatcher(verb_hints=frozenset({"give"}))
        event = Event(id="e1", verb="run")
        result = matcher.match(gift_pattern, [], [event])
        assert result is None

    def test_confidence_increases_with_multiple_matches(self, gift_pattern):
        matcher = VerbFamilyMatcher(verb_hints=frozenset({"give"}))
        events = [Event(id=f"e{i}", verb="give") for i in range(3)]
        result = matcher.match(gift_pattern, [], events)
        assert result is not None
        assert result.confidence > matcher.base_confidence

    def test_no_events_no_match(self, gift_pattern):
        matcher = VerbFamilyMatcher(verb_hints=frozenset({"give"}))
        result = matcher.match(gift_pattern, [], [])
        assert result is None


class TestKeywordAtomMatcher:
    """Tests for ``KeywordAtomMatcher``."""

    def test_matches_when_keyword_in_atom(self, threshold_pattern):
        matcher = KeywordAtomMatcher(keywords=frozenset({"secret"}))
        atom = Atom(id="a1", text="She revealed the secret truth.")
        result = matcher.match(threshold_pattern, [atom], [])
        assert result is not None

    def test_no_match_when_keyword_absent(self, threshold_pattern):
        matcher = KeywordAtomMatcher(keywords=frozenset({"secret"}))
        atom = Atom(id="a1", text="She walked home slowly.")
        result = matcher.match(threshold_pattern, [atom], [])
        assert result is None

    def test_empty_atoms_no_match(self, threshold_pattern):
        matcher = KeywordAtomMatcher(keywords=frozenset({"secret"}))
        result = matcher.match(threshold_pattern, [], [])
        assert result is None


class TestPatternService:
    """Tests for ``PatternService``."""

    def test_detect_returns_empty_when_no_templates_in_graph(self):
        repo = MagicMock(spec=GraphRepository)
        repo.get_pattern.return_value = None
        svc = PatternService(repo)
        result = svc.detect_patterns([], [], "narr-001")
        assert result == []

    def test_detect_returns_instance_on_verb_match(self, gift_pattern):
        repo = MagicMock(spec=GraphRepository)
        repo.get_pattern.side_effect = lambda pid: (
            gift_pattern if pid == "pattern.gift_exchange" else None
        )
        svc = PatternService(repo)
        event = Event(id="e1", verb="give")
        results = svc.detect_patterns([], [event], "narr-001")
        assert any(r.template == gift_pattern for r in results)

    def test_register_pattern_saves_to_repo(self, gift_pattern):
        repo = MagicMock(spec=GraphRepository)
        svc = PatternService(repo)
        matcher = VerbFamilyMatcher(verb_hints=frozenset({"give"}))
        svc.register_pattern(gift_pattern, matcher)
        repo.save_pattern.assert_called_once_with(gift_pattern)
        assert "pattern.gift_exchange" in svc._matchers
