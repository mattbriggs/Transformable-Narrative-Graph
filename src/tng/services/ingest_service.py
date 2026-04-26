"""Ingest service — orchestrates the full ingest pipeline (SRS §6.1, Diagram 7).

Responsibilities
----------------
1. Accept a raw text payload (plain text, Markdown, or pre-structured JSON).
2. Segment text into scenes and atoms via the ``segmenter``.
3. Extract entities and events via ``entity_extractor`` and ``event_detector``.
4. Apply confidence scoring and review flags via ``annotator``.
5. Delegate pattern detection to ``PatternService``.
6. Persist the complete result via ``GraphRepository`` in a single pass.
7. Return an ``IngestResult`` summary to the caller.

The service never issues Cypher directly; it only calls the repository.
All pre-processing runs in memory before any graph write, ensuring the
graph is never left in a partially-atomized state (SRS Diagram 7 note).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from tng.config import Settings
from tng.domain.enums import NarrativeStatus
from tng.domain.models import (
    Character,
    Narrative,
    PatternInstance,
    Scene,
)
from tng.ingest.annotator import (
    annotate_atoms,
    annotate_characters,
    annotate_events,
    make_id,
)
from tng.ingest.entity_extractor import extract_entities
from tng.ingest.event_detector import detect_events
from tng.ingest.segmenter import (
    SceneSection,
    segment_markdown,
    segment_text,
    strip_markdown_frontmatter,
)
from tng.repository.graph_repository import GraphRepository
from tng.services.pattern_service import PatternService

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    """Summary returned to the API after a successful ingest operation.

    :param narrative_id: ID of the created or updated Narrative.
    :param scene_count: Number of scenes persisted.
    :param atom_count: Total atoms written to the graph.
    :param event_count: Total events written.
    :param character_count: Total characters written.
    :param pattern_count: Number of pattern instances created.
    :param flagged_count: Number of nodes flagged for human review.
    """

    narrative_id: str
    scene_count: int = 0
    atom_count: int = 0
    event_count: int = 0
    character_count: int = 0
    pattern_count: int = 0
    flagged_count: int = 0


@dataclass
class IngestPayload:
    """Normalised input payload for the IngestService.

    :param title: Narrative title.
    :param text: Raw prose or pre-structured text to ingest.
    :param narrative_id: Optional; generated if absent.
    :param source_ref: Optional provenance reference.
    :param format: Input format hint: ``"text"``, ``"markdown"``, or ``"json"``.
    :param annotations: Optional pre-annotations dict (from JSON payloads).
    """

    title: str
    text: str
    narrative_id: str = field(default_factory=make_id)
    source_ref: str = ""
    format: str = "text"
    annotations: dict = field(default_factory=dict)


class IngestService:
    """Orchestrates the ingest pipeline from raw text to persisted graph.

    :param repo: An open ``GraphRepository`` instance.
    :param pattern_service: A ``PatternService`` for pattern detection.
    :param settings: Application settings (used for ``confidence_threshold``).
    """

    def __init__(
        self,
        repo: GraphRepository,
        pattern_service: PatternService,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._pattern_service = pattern_service
        self._threshold = settings.confidence_threshold

    def ingest(self, payload: IngestPayload) -> IngestResult:
        """Run the full ingest pipeline and persist the result.

        :param payload: Normalised input payload.
        :returns: ``IngestResult`` summary.
        """
        logger.info("Starting ingest for narrative %r", payload.narrative_id)

        sections = self._segment(payload)

        narrative = Narrative(
            id=payload.narrative_id,
            title=payload.title,
            status=NarrativeStatus.DRAFT,
            source_ref=payload.source_ref,
        )
        self._repo.save_narrative(narrative)

        total_atoms = total_events = total_chars = total_patterns = flagged = 0

        for seq, section in enumerate(sections, start=1):
            atoms = annotate_atoms(section.sentences, self._threshold)
            entities = extract_entities(section.sentences, self._threshold)
            characters = annotate_characters(entities)
            detected = detect_events(section.sentences, self._threshold)
            events = annotate_events(detected, characters)

            pattern_instances = self._pattern_service.detect_patterns(
                atoms, events, payload.narrative_id
            )

            scene = Scene(
                id=make_id(),
                sequence=seq,
                summary=section.summary,
                atoms=atoms,
                events=events,
                pattern_instances=pattern_instances,
            )

            self._repo.save_scene(scene, payload.narrative_id)

            total_atoms += len(atoms)
            total_events += len(events)
            total_chars += len(characters)
            total_patterns += len(pattern_instances)
            flagged += sum(1 for a in atoms if a.needs_review)
            flagged += sum(1 for e in events if e.needs_review)

        self._repo.update_narrative_status(
            payload.narrative_id, NarrativeStatus.PATTERNED
        )
        logger.info(
            "Ingest complete: atoms=%d events=%d patterns=%d flagged=%d",
            total_atoms,
            total_events,
            total_patterns,
            flagged,
        )
        return IngestResult(
            narrative_id=payload.narrative_id,
            scene_count=len(sections),
            atom_count=total_atoms,
            event_count=total_events,
            character_count=total_chars,
            pattern_count=total_patterns,
            flagged_count=flagged,
        )

    def _segment(self, payload: IngestPayload) -> list[SceneSection]:
        """Segment the payload text into scene sections.

        Dispatches to ``segment_markdown`` when ``format == "markdown"`` so
        heading lines become scene boundaries with a populated ``summary``.
        All other formats use the paragraph-boundary segmenter and produce
        sections with ``summary = ""``.

        :param payload: The ingest payload.
        :returns: Ordered list of ``SceneSection`` instances.
        """
        text = payload.text.strip()
        if payload.format == "markdown":
            return segment_markdown(text)
        segmented = segment_text(strip_markdown_frontmatter(text))
        return [
            SceneSection(summary="", sentences=sentences)
            for sentences in segmented.sentences_by_paragraph
        ]
