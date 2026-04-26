"""Unit tests for the text segmenter."""

from __future__ import annotations

import pytest

from tng.ingest.segmenter import segment_markdown, segment_text, strip_markdown_frontmatter


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


class TestSegmentMarkdown:
    """Tests for ``segment_markdown``."""

    def test_single_heading_with_prose(self):
        text = "# Chapter One\n\nAlice ran. She stopped."
        sections = segment_markdown(text)
        assert len(sections) == 1
        assert sections[0].summary == "Chapter One"
        assert "Alice ran." in sections[0].sentences

    def test_two_headings_produce_two_sections(self):
        text = "# Chapter One\n\nAlice ran.\n\n# Chapter Two\n\nBob arrived."
        sections = segment_markdown(text)
        assert len(sections) == 2
        assert sections[0].summary == "Chapter One"
        assert sections[1].summary == "Chapter Two"

    def test_prose_under_heading_merged_across_paragraphs(self):
        text = "# Ch 1\n\nFirst sentence.\n\nSecond sentence."
        sections = segment_markdown(text)
        assert len(sections) == 1
        assert len(sections[0].sentences) == 2

    def test_heading_text_not_an_atom(self):
        text = "# My Heading\n\nProse here."
        sections = segment_markdown(text)
        assert sections[0].summary == "My Heading"
        assert all("My Heading" not in s for s in sections[0].sentences)

    def test_leading_prose_before_any_heading(self):
        text = "Preface text.\n\n# Chapter One\n\nChapter prose."
        sections = segment_markdown(text)
        assert len(sections) == 2
        assert sections[0].summary == ""
        assert "Preface text." in sections[0].sentences

    def test_strips_frontmatter(self):
        text = "---\ntitle: Test\n---\n\n# Chapter One\n\nBody."
        sections = segment_markdown(text)
        assert len(sections) == 1
        assert sections[0].summary == "Chapter One"

    def test_h2_heading_creates_section(self):
        text = "## Part Two\n\nSome content."
        sections = segment_markdown(text)
        assert sections[0].summary == "Part Two"

    def test_empty_document_returns_empty_list(self):
        assert segment_markdown("") == []

    def test_heading_only_no_prose_not_included(self):
        text = "# Chapter One\n\n# Chapter Two\n\nContent."
        sections = segment_markdown(text)
        assert len(sections) == 1
        assert sections[0].summary == "Chapter Two"

    def test_multi_sentence_chapter(self):
        text = "# Opening\n\nAlice walked in. She looked around. Bob was there."
        sections = segment_markdown(text)
        assert len(sections[0].sentences) == 3


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
