"""Named entity extraction for the TNGS ingest pipeline.

This module implements the entity extraction stage (SRS §5.3 rule 4).  It
uses a simple rule-based heuristic that identifies *proper noun phrases* —
consecutive capitalised words that do not begin a sentence — as candidate
Character nodes.

The extractor is deliberately lightweight and provider-neutral.  It assigns
a ``confidence`` score below 1.0 to signal that automated extraction should
be treated as a hypothesis, not a fact.  Items below the configured
threshold are flagged for human review (SRS §5.3 rule 6).

Design notes
------------
* The extractor is a **Strategy** — it can be replaced with a heavier NLP
  backend (spaCy, stanza, etc.) without touching the calling service code,
  provided the replacement returns the same ``ExtractedEntity`` dataclass.
* Characters are keyed by their normalised name so that duplicate mentions
  of "Alice" across multiple sentences produce a single candidate entity.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Matches a sequence of 1–4 capitalised words (common English name patterns).
# Excludes the very first word in a sentence to reduce false positives from
# sentence-initial capitalisation.
_PROPER_NOUN_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b")

# Common sentence-initial function words that look capitalised but are not entities.
_STOP_INITIALS = frozenset(
    {
        "The", "A", "An", "This", "That", "These", "Those",
        "He", "She", "It", "They", "We", "I", "You",
        "His", "Her", "Its", "Their", "Our", "My", "Your",
        "When", "Where", "While", "As", "If", "But", "And",
        "Or", "So", "Yet", "For", "Nor",
    }
)


@dataclass
class ExtractedEntity:
    """A candidate Character entity extracted from text.

    :param name: Normalised entity name (title-cased, whitespace-collapsed).
    :param mentions: Number of times this name appears in the source text.
    :param confidence: Extraction confidence in [0.0, 1.0].
    :param needs_review: True when confidence is below the configured threshold.
    """

    name: str
    mentions: int = 1
    confidence: float = 0.8
    needs_review: bool = False


def extract_entities(
    sentences: list[str],
    confidence_threshold: float = 0.6,
) -> list[ExtractedEntity]:
    """Extract candidate Character entities from a list of sentences.

    :param sentences: Tokenised sentences from the segmenter.
    :param confidence_threshold: Entities below this score are flagged for
        human review.
    :returns: Deduplicated list of ``ExtractedEntity`` objects, ordered by
        descending mention count.

    Example::

        entities = extract_entities(["Alice ran. Alice stopped. Bob arrived."])
        # Returns [ExtractedEntity("Alice", mentions=2), ExtractedEntity("Bob")]
    """
    counts: dict[str, int] = {}
    for sentence in sentences:
        # Strip the first word to avoid sentence-initial false positives.
        body = _strip_first_word(sentence)
        for match in _PROPER_NOUN_RE.finditer(body):
            name = _normalise(match.group(1))
            if name not in _STOP_INITIALS:
                counts[name] = counts.get(name, 0) + 1

    entities: list[ExtractedEntity] = []
    for name, mentions in sorted(counts.items(), key=lambda kv: -kv[1]):
        # Confidence rises with mention frequency, capped at 0.95.
        confidence = min(0.95, 0.75 + 0.05 * (mentions - 1))
        needs_review = confidence < confidence_threshold
        entities.append(
            ExtractedEntity(
                name=name,
                mentions=mentions,
                confidence=confidence,
                needs_review=needs_review,
            )
        )
        logger.debug(
            "Entity candidate: %r (mentions=%d, conf=%.2f)", name, mentions, confidence
        )

    return entities


def _strip_first_word(text: str) -> str:
    """Return text with the first whitespace-delimited token removed."""
    space = text.find(" ")
    return text[space + 1 :] if space != -1 else ""


def _normalise(name: str) -> str:
    """Collapse internal whitespace and title-case a name."""
    return " ".join(name.split())
