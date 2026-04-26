"""Pattern service — detects and instantiates narrative pattern templates.

Implements SRS §6.2 (Diagram 8): pattern detection is a matching operation
between incoming atoms/events and a library of Pattern templates stored in
the graph.

Architecture
------------
* The service holds a reference to the ``GraphRepository`` for template
  lookups and instance persistence.
* Pattern matching is a **Strategy**: each ``PatternMatcher`` checks a
  single template against the atom/event set and returns an optional
  ``PatternInstance`` with a confidence score.
* Multiple matchers can fire on the same scene; overlapping patterns are
  **not** collapsed — they are represented as separate ``PatternInstance``
  nodes (SRS §6.2).
* Pattern templates are loaded from the graph at startup and cached in
  memory for the lifetime of the service.

Built-in matchers
-----------------
The service ships four lightweight matchers that cover common patterns
from the SRS seed data.  Additional matchers can be registered at startup
without modifying this module.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from tng.domain.models import Atom, Event, Pattern, PatternInstance
from tng.ingest.annotator import make_id
from tng.repository.graph_repository import GraphRepository

logger = logging.getLogger(__name__)


# ── Matcher protocol ──────────────────────────────────────────────────────────


class PatternMatcher(Protocol):
    """Contract for a single-pattern matching strategy.

    :method match: Test ``atoms`` and ``events`` against a template.
        Return a ``PatternInstance`` if matched, else ``None``.
    """

    def match(
        self,
        template: Pattern,
        atoms: list[Atom],
        events: list[Event],
    ) -> PatternInstance | None:
        """Attempt to match the template against the provided atoms/events.

        :param template: The pattern template to match against.
        :param atoms: Scene atoms available for slot binding.
        :param events: Scene events available for slot binding.
        :returns: A ``PatternInstance`` on match, or ``None``.
        """
        ...


# ── Built-in matchers ─────────────────────────────────────────────────────────


@dataclass
class VerbFamilyMatcher:
    """Matches a pattern whose template name is associated with a set of verbs.

    :param verb_hints: Set of lowercase verb strings that signal this pattern.
    :param base_confidence: Confidence assigned when a hint verb is found.
    """

    verb_hints: frozenset[str]
    base_confidence: float = 0.75

    def match(
        self,
        template: Pattern,
        atoms: list[Atom],
        events: list[Event],
    ) -> PatternInstance | None:
        """Return a ``PatternInstance`` if any event verb matches a hint.

        :param template: The template to match.
        :param atoms: Scene atoms (not used by this matcher).
        :param events: Scene events whose verbs are checked.
        :returns: A ``PatternInstance`` or ``None``.
        """
        matched_events = [e for e in events if e.verb in self.verb_hints]
        if not matched_events:
            return None
        confidence = min(
            0.95, self.base_confidence + 0.05 * (len(matched_events) - 1)
        )
        instance = PatternInstance(
            id=make_id(),
            slot="scene-core",
            confidence=confidence,
            template=template,
            realized_event_ids=[e.id for e in matched_events],
        )
        logger.debug(
            "Pattern %r matched with confidence %.2f", template.name, confidence
        )
        return instance


@dataclass
class KeywordAtomMatcher:
    """Matches a pattern by searching atom texts for keyword strings.

    :param keywords: Set of lowercase keywords to search for in atom text.
    :param base_confidence: Confidence assigned on single keyword match.
    """

    keywords: frozenset[str]
    base_confidence: float = 0.70

    def match(
        self,
        template: Pattern,
        atoms: list[Atom],
        events: list[Event],
    ) -> PatternInstance | None:
        """Return a ``PatternInstance`` if keywords are found in atom text.

        :param template: The template to match.
        :param atoms: Scene atoms whose text is scanned.
        :param events: Scene events (not used by this matcher).
        :returns: A ``PatternInstance`` or ``None``.
        """
        matched_atoms = [
            a
            for a in atoms
            if any(kw in a.text.lower() for kw in self.keywords)
        ]
        if not matched_atoms:
            return None
        confidence = min(0.95, self.base_confidence + 0.04 * len(matched_atoms))
        return PatternInstance(
            id=make_id(),
            slot="scene-core",
            confidence=confidence,
            template=template,
            realized_atom_ids=[a.id for a in matched_atoms],
        )


# ── Service ───────────────────────────────────────────────────────────────────

# Default matcher registry: maps pattern.id to a ``PatternMatcher`` instance.
DEFAULT_MATCHERS: dict[str, PatternMatcher] = {
    "pattern.gift_exchange": VerbFamilyMatcher(
        verb_hints=frozenset({"give", "offer", "present", "receiv", "accept", "gift"})
    ),
    "pattern.threshold_crossing": VerbFamilyMatcher(
        verb_hints=frozenset({"cross", "enter", "leav", "depart", "arriv", "exit", "pass"})
    ),
    "pattern.revelation": KeywordAtomMatcher(
        keywords=frozenset({"reveal", "discover", "realise", "realize", "truth", "secret", "learn"})
    ),
    "pattern.conflict": VerbFamilyMatcher(
        verb_hints=frozenset({"fight", "attack", "defend", "resist", "challeng", "confront"})
    ),
}


class PatternService:
    """Detects narrative patterns in a set of atoms and events.

    :param repo: ``GraphRepository`` for template lookups.
    :param matchers: Matcher registry mapping pattern ID → matcher.
        Defaults to ``DEFAULT_MATCHERS``.
    """

    def __init__(
        self,
        repo: GraphRepository,
        matchers: dict[str, PatternMatcher] | None = None,
    ) -> None:
        self._repo = repo
        self._matchers = matchers if matchers is not None else DEFAULT_MATCHERS.copy()

    def detect_patterns(
        self,
        atoms: list[Atom],
        events: list[Event],
        narrative_id: str,
    ) -> list[PatternInstance]:
        """Run all registered matchers against the given atoms and events.

        Pattern templates are fetched from the graph by ID.  If a template
        does not exist in the graph it is silently skipped (not auto-created).

        :param atoms: Scene atoms to match against.
        :param events: Scene events to match against.
        :param narrative_id: ID of the parent narrative (for logging).
        :returns: List of ``PatternInstance`` objects (may be empty).
        """
        instances: list[PatternInstance] = []
        for pattern_id, matcher in self._matchers.items():
            template = self._repo.get_pattern(pattern_id)
            if template is None:
                logger.debug("Pattern template %r not in graph; skipping.", pattern_id)
                continue
            instance = matcher.match(template, atoms, events)
            if instance:
                instances.append(instance)
        return instances

    def register_pattern(self, pattern: Pattern, matcher: PatternMatcher) -> None:
        """Register a new pattern template and its matcher at runtime.

        The pattern template is persisted to the graph immediately.

        :param pattern: The ``Pattern`` template to add to the library.
        :param matcher: The matcher strategy for this pattern.
        """
        self._repo.save_pattern(pattern)
        self._matchers[pattern.id] = matcher
        logger.info("Registered pattern %r (%s).", pattern.id, pattern.name)
