"""Domain model classes for the Transformable Narrative Graph System.

Every class in this module is a pure Pydantic BaseModel.  No infrastructure
imports (Neo4j driver, FastAPI, etc.) are allowed here.  This keeps the
domain layer independently testable and decoupled from persistence concerns.

The class hierarchy mirrors the graph schema defined in SRS §4:
  Narrative → Scene → Atom / Event / PatternInstance
  Scene → Perspective / MoodState / GenreProfile / Chronotope
  Atom → CodeTag
  Transform → (audit trail linking to any scene-level state node)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from tng.domain.enums import (
    AtomKind,
    BarthesCode,
    FocalizationDistance,
    NarrativeStatus,
    ReliabilityLevel,
    TransformAxis,
)


# ── Leaf nodes ────────────────────────────────────────────────────────────────


class CodeTag(BaseModel):
    """A Barthesian code label attached to an Atom.

    :param id: Unique identifier for this tag.
    :param code: The Barthesian code category.
    :param label: Human-readable annotation label.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    code: BarthesCode
    label: str


class Perspective(BaseModel):
    """Focalization state for a Scene at a point in transformation history.

    :param id: Unique identifier.
    :param focalizer: ID of the Character through whose perspective events are filtered.
    :param distance: Genettean focalization distance.
    :param reliability: Narrator/focalizer credibility rating.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    focalizer: str
    distance: FocalizationDistance = FocalizationDistance.ZERO
    reliability: ReliabilityLevel = ReliabilityLevel.RELIABLE


class MoodState(BaseModel):
    """Affective/tonal state for a Scene.

    :param id: Unique identifier.
    :param label: Free-text mood label (e.g. "melancholic", "tense").
    :param valence: Sentiment polarity in [-1.0, 1.0]; negative = negative affect.
    :param arousal: Activation level in [0.0, 1.0]; high = energetic.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    valence: float = Field(default=0.0, ge=-1.0, le=1.0)
    arousal: float = Field(default=0.5, ge=0.0, le=1.0)


class GenreProfile(BaseModel):
    """Genre encoding for a Scene or Narrative.

    :param id: Unique identifier.
    :param name: Genre name (e.g. "gothic", "road novel").
    :param conventions: JSON-serialisable list of constraint strings describing
        genre-specific narrative obligations.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    conventions: list[str] = Field(default_factory=list)


class Chronotope(BaseModel):
    """Bakhtinian time-space frame for a Scene.

    :param id: Unique identifier.
    :param time_mode: One of: cyclical, linear, suspended, compressed.
    :param space_mode: One of: bounded, open, liminal, utopian.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    time_mode: str
    space_mode: str


class Character(BaseModel):
    """A participant or focalizer in the narrative.

    :param id: Unique identifier.
    :param name: Character name as it appears in the source text.
    :param role: Narrative role (e.g. "protagonist", "antagonist", "witness").
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    role: str = "character"


class Event(BaseModel):
    """An action-bearing narrative unit extracted from an Atom.

    :param id: Unique identifier.
    :param verb: Lemmatised main verb of the event clause.
    :param tense: Grammatical tense string (e.g. "past", "present").
    :param aspect: Grammatical aspect string (e.g. "simple", "progressive").
    :param confidence: Extraction confidence in [0.0, 1.0].
    :param participants: Characters who take part in this event.
    :param needs_review: True when confidence is below the configured threshold.
    """

    id: str
    verb: str
    tense: str = "past"
    aspect: str = "simple"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    participants: list[Character] = Field(default_factory=list)
    needs_review: bool = False


class Atom(BaseModel):
    """The minimal expressive narrative unit — a single clause or sentence.

    :param id: Unique identifier.
    :param text: Raw text of the atom.
    :param kind: Functional classification.
    :param surface_order: Position within its parent Scene (0-based).
    :param confidence: Segmentation / classification confidence in [0.0, 1.0].
    :param code_tags: Barthesian code labels attached to this atom.
    :param needs_review: True when confidence is below the configured threshold.
    """

    id: str
    text: str
    kind: AtomKind = AtomKind.DESCRIPTIVE
    surface_order: int = 0
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    code_tags: list[CodeTag] = Field(default_factory=list)
    needs_review: bool = False


# ── Pattern nodes ─────────────────────────────────────────────────────────────


class Pattern(BaseModel):
    """A reusable narrative template stored in the graph library.

    :param id: Unique identifier (e.g. "pattern.gift_exchange").
    :param name: Human-readable name.
    :param family: Family tag (see PatternFamily enum).
    :param description: Prose description of the pattern's narrative function.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    family: str
    description: str = ""


class PatternInstance(BaseModel):
    """Concrete realisation of a Pattern in a specific Scene.

    :param id: Unique identifier.
    :param slot: Structural slot label (e.g. "scene-core", "opening").
    :param confidence: Match confidence in [0.0, 1.0].
    :param template: The Pattern this instance realises.
    :param realized_atoms: Atom IDs that ground this instance.
    :param realized_events: Event IDs that ground this instance.
    :param needs_review: True when confidence is below the configured threshold.
    """

    id: str
    slot: str = "scene-core"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    template: Pattern | None = None
    realized_atom_ids: list[str] = Field(default_factory=list)
    realized_event_ids: list[str] = Field(default_factory=list)
    needs_review: bool = False


# ── Transform audit node ──────────────────────────────────────────────────────


class Transform(BaseModel):
    """Audit record for a single transformation operation.

    The Transform node is the spine of the transformation lineage graph.
    It links the scene it modified (``APPLIED_TO``) and the new state node
    it produced (``PRODUCED``).  It is never deleted or overwritten; the
    full sequence of transforms is always traversable.

    :param id: Unique identifier.
    :param axis: The transformation axis that was applied.
    :param operator: Identifier of the user or system that issued the transform.
    :param applied_at: UTC timestamp of the operation.
    :param parameters: Axis-specific parameters as a free dict (serialised to
        JSON when persisted).
    :param scene_id: ID of the scene this transform was applied to.
    :param produced_id: ID of the new state node produced by this transform.
    """

    id: str
    axis: TransformAxis
    operator: str = "system"
    applied_at: datetime = Field(default_factory=datetime.utcnow)
    parameters: dict[str, Any] = Field(default_factory=dict)
    scene_id: str = ""
    produced_id: str = ""


# ── Scene and Narrative ───────────────────────────────────────────────────────


class Scene(BaseModel):
    """A bounded narrative segment within a Narrative.

    :param id: Unique identifier.
    :param sequence: Ordinal position within the parent Narrative (1-based).
    :param summary: Optional human-readable summary of the scene.
    :param atoms: Ordered list of Atoms in this scene.
    :param events: Events extracted from this scene.
    :param pattern_instances: Pattern instances detected in this scene.
    :param current_perspective: Active Perspective node (if any).
    :param current_mood: Active MoodState node (if any).
    :param current_genre: Active GenreProfile node (if any).
    :param chronotope: Active Chronotope node (if any).
    """

    id: str
    sequence: int = 1
    summary: str = ""
    atoms: list[Atom] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    pattern_instances: list[PatternInstance] = Field(default_factory=list)
    current_perspective: Perspective | None = None
    current_mood: MoodState | None = None
    current_genre: GenreProfile | None = None
    chronotope: Chronotope | None = None


class Narrative(BaseModel):
    """Top-level work or draft — the root node of a TNGS narrative graph.

    :param id: Unique identifier.
    :param title: Working title of the narrative.
    :param status: Life-cycle state.
    :param source_ref: Optional reference to the originating source document.
    :param scenes: Ordered list of Scenes.
    :param created_at: UTC creation timestamp.
    """

    id: str
    title: str
    status: NarrativeStatus = NarrativeStatus.DRAFT
    source_ref: str = ""
    scenes: list[Scene] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Graph state snapshot (used by renderers) ──────────────────────────────────


class EventRelation(BaseModel):
    """A directed relationship between two Event nodes.

    Captures explicit causal and temporal connections that are stored as
    first-class relationships in the graph.  These are fetched separately
    from the event nodes themselves because they are inter-event edges
    rather than containment relationships.

    :param source_id: ID of the originating Event.
    :param target_id: ID of the destination Event.
    :param relation_type: One of ``CAUSES``, ``ENABLES``, ``PREVENTS``,
        ``PRECEDES``.
    """

    model_config = ConfigDict(frozen=True)

    source_id: str
    target_id: str
    relation_type: str


class GraphState(BaseModel):
    """A complete, self-contained snapshot of one narrative's graph state.

    Passed to renderer implementations so they never issue Cypher directly.

    :param narrative: The root Narrative with all nested scenes and atoms.
    :param transforms: Ordered transform history (oldest first).
    :param characters: All Characters referenced in this narrative.
    :param event_relations: Explicit inter-event relationships (CAUSES,
        ENABLES, PREVENTS, PRECEDES) fetched from the graph.  Used by the
        GraphML renderer to draw and score causal/temporal edges.
    """

    narrative: Narrative
    transforms: list[Transform] = Field(default_factory=list)
    characters: list[Character] = Field(default_factory=list)
    event_relations: list[EventRelation] = Field(default_factory=list)
