"""Verb-phrase / event detection for the TNGS ingest pipeline.

Implements SRS §5.3 rule 3: sentence-level verb phrases are candidates for
``Event`` nodes with ``tense`` and ``aspect`` properties.

The detector uses a regex-based approach targeting common English verb
patterns.  It is intentionally simple and provider-neutral.  The goal is
to provide a reasonable baseline; higher-precision extraction can be plugged
in by substituting this module's ``detect_events`` function with an
alternative implementation that returns the same ``DetectedEvent`` dataclass.

Tense heuristics
----------------
* Past-tense markers: ``-ed`` endings, auxiliaries "was/were/had", past
  irregular forms (limited set).
* Present-tense markers: ``-s`` third-person endings, "is/are/am".
* Future markers: "will", "shall", "going to".
* Progressive aspect: auxiliary "was/were/is/are" + ``-ing`` form.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Auxiliary + main verb pattern (simplified)
_VERB_PHRASE_RE = re.compile(
    r"\b"
    r"(?:"
    # Modal / auxiliary group
    r"(?:will|shall|would|could|should|may|might|must|can)\s+\w+|"
    # Be + -ing (progressive)
    r"(?:is|are|was|were|am)\s+\w+ing|"
    # Have + past participle
    r"(?:has|have|had)\s+\w+ed|"
    # Simple verb (3+ letters, lowercase — avoids matching proper nouns)
    r"[a-z]{3,}(?:ed|ing|s)?\b"
    r")"
)

_PAST_MARKERS = re.compile(
    r"\b(?:was|were|had|did)\b|\b\w+ed\b", re.IGNORECASE
)
_FUTURE_MARKERS = re.compile(r"\b(?:will|shall|going to)\b", re.IGNORECASE)
_PROGRESSIVE_MARKERS = re.compile(
    r"\b(?:is|are|was|were|am)\s+\w+ing\b", re.IGNORECASE
)


@dataclass
class DetectedEvent:
    """A candidate Event extracted from a sentence.

    :param verb: The lemmatised main verb (lowercase, stripped of auxiliaries).
    :param tense: Grammatical tense: ``"past"``, ``"present"``, or ``"future"``.
    :param aspect: Grammatical aspect: ``"simple"`` or ``"progressive"``.
    :param source_sentence: The sentence this event was extracted from.
    :param confidence: Extraction confidence in [0.0, 1.0].
    :param needs_review: True when confidence is below the configured threshold.
    """

    verb: str
    tense: str = "past"
    aspect: str = "simple"
    source_sentence: str = ""
    confidence: float = 0.75
    needs_review: bool = False


def detect_events(
    sentences: list[str],
    confidence_threshold: float = 0.6,
) -> list[DetectedEvent]:
    """Detect verb-phrase events in a list of sentences.

    Returns at most one event per sentence (the most prominent verb phrase).

    :param sentences: Tokenised sentences from the segmenter.
    :param confidence_threshold: Events below this score are flagged for
        human review.
    :returns: List of ``DetectedEvent`` objects (one per non-empty sentence).

    Example::

        events = detect_events(["Alice walked slowly.", "She had arrived."])
        # events[0].verb == "walked", events[0].tense == "past"
        # events[1].verb == "arrived", events[1].tense == "past"
    """
    results: list[DetectedEvent] = []
    for sentence in sentences:
        event = _extract_event(sentence, confidence_threshold)
        if event:
            results.append(event)
    return results


def _extract_event(sentence: str, threshold: float) -> DetectedEvent | None:
    """Extract the primary event from a single sentence.

    :param sentence: A single sentence string.
    :param threshold: Confidence threshold for review flagging.
    :returns: A ``DetectedEvent`` or ``None`` if no verb phrase found.
    """
    matches = _VERB_PHRASE_RE.findall(sentence.lower())
    if not matches:
        return None

    verb_phrase = matches[0]
    verb = _lemmatise_verb(verb_phrase)
    tense = _detect_tense(sentence)
    aspect = "progressive" if _PROGRESSIVE_MARKERS.search(sentence) else "simple"
    confidence = 0.75
    needs_review = confidence < threshold

    logger.debug("Detected event: %r (tense=%s, aspect=%s)", verb, tense, aspect)
    return DetectedEvent(
        verb=verb,
        tense=tense,
        aspect=aspect,
        source_sentence=sentence,
        confidence=confidence,
        needs_review=needs_review,
    )


def _detect_tense(sentence: str) -> str:
    """Infer grammatical tense from surface markers.

    :param sentence: Source sentence.
    :returns: ``"past"``, ``"present"``, or ``"future"``.
    """
    if _FUTURE_MARKERS.search(sentence):
        return "future"
    if _PAST_MARKERS.search(sentence):
        return "past"
    return "present"


def _lemmatise_verb(verb_phrase: str) -> str:
    """Strip common auxiliaries and inflectional suffixes to get a base form.

    :param verb_phrase: A matched verb phrase string (lowercase).
    :returns: The stripped main verb.
    """
    tokens = verb_phrase.split()
    # Drop leading auxiliaries
    auxiliaries = {
        "will", "shall", "would", "could", "should", "may", "might",
        "must", "can", "is", "are", "was", "were", "am", "has", "have",
        "had", "did",
    }
    main = next((t for t in tokens if t not in auxiliaries), tokens[-1])
    # Strip common suffixes
    for suffix in ("ing", "ed", "s"):
        if main.endswith(suffix) and len(main) > len(suffix) + 2:
            return main[: -len(suffix)]
    return main
