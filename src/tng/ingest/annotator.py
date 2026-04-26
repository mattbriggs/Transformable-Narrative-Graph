"""Confidence annotation and review-flag assignment.

The annotator is the final stage of the pre-graph ingest pipeline
(SRS §5.3 rules 5–6).  It:

1. Applies the configured ``confidence_threshold`` to every automatically
   derived node.
2. Sets ``needs_review = True`` on any node whose confidence is below the
   threshold.
3. Does **not** discard low-confidence nodes — they proceed to the graph
   with a review flag so that human judgement can resolve ambiguity.

This module wraps the entity and event outputs in domain model instances
with UUIDs assigned, ready for the GraphRepository.

The annotation logic is kept separate from segmentation and extraction so
that each stage can be tested and replaced independently.
"""

from __future__ import annotations

import logging
import uuid

from tng.domain.models import Atom, Character, Event
from tng.domain.enums import AtomKind
from tng.ingest.entity_extractor import ExtractedEntity
from tng.ingest.event_detector import DetectedEvent

logger = logging.getLogger(__name__)


def make_id() -> str:
    """Return a new random UUID string.

    :returns: A random UUID4 as a hyphenated lowercase string.
    """
    return str(uuid.uuid4())


def annotate_atoms(
    sentences: list[str],
    confidence_threshold: float = 0.6,
    base_confidence: float = 0.9,
) -> list[Atom]:
    """Wrap segmented sentences as Atom domain objects with confidence scores.

    :param sentences: Ordered list of sentence strings for one scene.
    :param confidence_threshold: Atoms below this score receive
        ``needs_review = True``.
    :param base_confidence: Starting confidence for rule-based sentence
        segmentation.  Shorter or ambiguous sentences receive a slight
        penalty.
    :returns: List of ``Atom`` objects with assigned IDs and surface order.
    """
    atoms: list[Atom] = []
    for idx, sentence in enumerate(sentences):
        confidence = _sentence_confidence(sentence, base_confidence)
        needs_review = confidence < confidence_threshold
        atom = Atom(
            id=make_id(),
            text=sentence,
            kind=_classify_atom(sentence),
            surface_order=idx,
            confidence=confidence,
            needs_review=needs_review,
        )
        logger.debug(
            "Atom %d: conf=%.2f review=%s text=%r",
            idx,
            confidence,
            needs_review,
            sentence[:40],
        )
        atoms.append(atom)
    return atoms


def annotate_characters(
    entities: list[ExtractedEntity],
) -> list[Character]:
    """Convert extracted entity candidates to Character domain objects.

    :param entities: Entities from ``entity_extractor.extract_entities``.
    :returns: List of ``Character`` objects with assigned IDs.
    """
    characters: list[Character] = []
    for entity in entities:
        char = Character(
            id=make_id(),
            name=entity.name,
            role="character",
        )
        characters.append(char)
    return characters


def annotate_events(
    detected: list[DetectedEvent],
    characters: list[Character],
) -> list[Event]:
    """Convert detected verb phrases to Event domain objects.

    Participant Characters are linked to events heuristically: a Character
    whose name appears in the source sentence is added as a participant.

    :param detected: Events from ``event_detector.detect_events``.
    :param characters: Characters extracted from the same scene.
    :returns: List of ``Event`` objects with participants resolved.
    """
    events: list[Event] = []
    for det in detected:
        participants = [
            c for c in characters if c.name.lower() in det.source_sentence.lower()
        ]
        event = Event(
            id=make_id(),
            verb=det.verb,
            tense=det.tense,
            aspect=det.aspect,
            confidence=det.confidence,
            participants=participants,
            needs_review=det.needs_review,
        )
        events.append(event)
    return events


def _sentence_confidence(sentence: str, base: float) -> float:
    """Compute a confidence score for a sentence atom.

    Very short sentences (< 10 chars) or sentences lacking a verb-like
    form receive a modest penalty.

    :param sentence: The sentence to score.
    :param base: Starting confidence value.
    :returns: Adjusted confidence in [0.0, 1.0].
    """
    conf = base
    if len(sentence) < 10:
        conf -= 0.15
    if not any(c in sentence for c in ".!?"):
        conf -= 0.05
    return max(0.0, min(1.0, conf))


def _classify_atom(sentence: str) -> AtomKind:
    """Heuristically classify an atom's kind from surface text.

    :param sentence: The atom's text.
    :returns: An ``AtomKind`` value.
    """
    s = sentence.strip()
    # Dialogue detection: starts or contains a speech verb or quotation marks
    if s.startswith(('"', "'", "“", "”")) or any(
        w in s.lower() for w in ("said", "asked", "replied", "whispered", "shouted")
    ):
        return AtomKind.DIALOGIC
    # Reflexive: first-person introspection markers
    if any(w in s.lower() for w in ("thought", "felt", "wondered", "realised", "realized", "knew")):
        return AtomKind.REFLEXIVE
    # Transitional: temporal / locative connectors
    if any(
        s.lower().startswith(w)
        for w in ("then", "later", "meanwhile", "afterwards", "next", "finally")
    ):
        return AtomKind.TRANSITIONAL
    # Expository: to-be constructions, definitions, background facts
    if any(w in s.lower() for w in (" was a ", " were a ", " is a ", " are a ", " had been ")):
        return AtomKind.EXPOSITORY
    return AtomKind.DESCRIPTIVE
