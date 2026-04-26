"""Unit tests for the text segmenter."""

from __future__ import annotations

import pytest

from tng.ingest.segmenter import segment_text, strip_markdown_frontmatter


class TestSegmentText:
    """Tests for ``segment_text``."""

    def test_single_paragraph_single_sentence(self):
        result = segment_text("Alice walked.")
        assert len(result.paragraphs) == 1
        assert result.sentences_by_paragraph[0] == ["Alice walked."]

    def test_two_paragraphs(self):
        result = segment_text("Para one.\n\nPara two.")
        assert len(result.paragraphs) == 2

    def test_multiple_sentences_in_paragraph(self):
        result = segment_text("Alice ran. Bob stopped. Carol waited.")
        sentences = result.sentences_by_paragraph[0]
        assert len(sentences) == 3
        assert sentences[0] == "Alice ran."
        assert sentences[2] == "Carol waited."

    def test_empty_input_returns_empty(self):
        result = segment_text("")
        assert result.paragraphs == []
        assert result.sentences_by_paragraph == []

    def test_extra_whitespace_stripped(self):
        result = segment_text("   Alice ran.   ")
        assert result.sentences_by_paragraph[0][0] == "Alice ran."

    def test_question_marks_split_sentences(self):
        result = segment_text("Who came? Alice did.")
        sentences = result.sentences_by_paragraph[0]
        assert len(sentences) == 2

    def test_exclamation_splits_sentences(self):
        result = segment_text("Run! Go now.")
        sentences = result.sentences_by_paragraph[0]
        assert len(sentences) == 2

    def test_multiple_newlines_treated_as_single_paragraph_boundary(self):
        result = segment_text("Para one.\n\n\n\nPara two.")
        assert len(result.paragraphs) == 2

    def test_preserves_paragraph_order(self):
        result = segment_text("First.\n\nSecond.\n\nThird.")
        assert result.paragraphs[0].startswith("First")
        assert result.paragraphs[2].startswith("Third")


class TestStripMarkdownFrontmatter:
    """Tests for ``strip_markdown_frontmatter``."""

    def test_strips_yaml_frontmatter(self):
        text = "---\ntitle: Test\n---\n\nBody text."
        result = strip_markdown_frontmatter(text)
        assert result.startswith("Body text.")

    def test_no_frontmatter_unchanged(self):
        text = "Just a plain text document."
        result = strip_markdown_frontmatter(text)
        assert result == text

    def test_incomplete_frontmatter_unchanged(self):
        text = "---\ntitle: Test\n\nNo closing fence."
        result = strip_markdown_frontmatter(text)
        assert result == text
