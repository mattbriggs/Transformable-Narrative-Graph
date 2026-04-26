"""Text segmentation — splits raw prose into scene-level and atom-level units.

The segmenter is the first stage of the ingest pipeline (SRS §5.3, Diagram 6).
It is implemented as a pure-Python, rule-based strategy that requires no
external model downloads, making it usable out of the box in CI and tests.

Segmentation rules
------------------
1. **Paragraph boundaries** (double newlines) delimit candidate scenes.
2. **Sentence boundaries** (period/question mark/exclamation followed by
   optional whitespace and an upper-case letter, or end-of-string) delimit
   candidate atoms within each scene.
3. Empty paragraphs and empty sentences are discarded.
4. Leading/trailing whitespace is stripped from every unit.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Matches the end of a sentence: ., !, or ? optionally followed by quotes/parens,
# then a mandatory space + uppercase letter, or end-of-string.
_SENTENCE_BOUNDARY = re.compile(
    r'(?<=[.!?])["\')]?\s+(?=[A-Z])|(?<=[.!?])["\')]?$'
)


@dataclass
class SegmentedText:
    """Result of segmenting a block of prose.

    :param paragraphs: List of paragraph strings.
    :param sentences_by_paragraph: For each paragraph, an ordered list of
        sentence strings.
    """

    paragraphs: list[str] = field(default_factory=list)
    sentences_by_paragraph: list[list[str]] = field(default_factory=list)


def segment_text(text: str) -> SegmentedText:
    """Segment raw prose into paragraphs and sentences.

    :param text: Raw input text (plain text or stripped Markdown).
    :returns: A ``SegmentedText`` containing paragraphs and their sentences.

    Example::

        result = segment_text("Alice walked. She stopped.\\n\\nBob arrived.")
        # result.paragraphs == ["Alice walked. She stopped.", "Bob arrived."]
        # result.sentences_by_paragraph[0] == ["Alice walked.", "She stopped."]
        # result.sentences_by_paragraph[1] == ["Bob arrived."]
    """
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    logger.debug("Segmented text into %d paragraph(s).", len(paragraphs))

    sentences_by_paragraph: list[list[str]] = []
    for para in paragraphs:
        sentences = _split_sentences(para)
        sentences_by_paragraph.append(sentences)
        logger.debug("Paragraph → %d sentence(s).", len(sentences))

    return SegmentedText(
        paragraphs=paragraphs,
        sentences_by_paragraph=sentences_by_paragraph,
    )


def _split_sentences(paragraph: str) -> list[str]:
    """Split a single paragraph into sentences.

    :param paragraph: A paragraph-level text block.
    :returns: List of individual sentence strings with leading/trailing
        whitespace stripped.
    """
    parts = _SENTENCE_BOUNDARY.split(paragraph)
    sentences = [s.strip() for s in parts if s.strip()]
    return sentences


def strip_markdown_frontmatter(text: str) -> str:
    """Remove YAML frontmatter from a Markdown document.

    :param text: Raw Markdown text, possibly containing a leading
        ``---`` frontmatter block.
    :returns: Text with frontmatter stripped.
    """
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            return text[end + 3 :].lstrip()
    return text
