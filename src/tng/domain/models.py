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

    :ivar id: Unique identifier for this tag.
    :ivar code: The Barthesian code category.
    :ivar label: Human-readable annotation label.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    code: BarthesCode
    label: str


class Perspective(BaseModel):
    """Focalization state for a Scene at a point in transformation history.

    :ivar id: Unique identifier.
    :ivar focalizer: ID of the Character through whose perspective events are filtered.
    :ivar distance: Genettean focalization distance.
    :ivar reliability: Narrator/focalizer credibility rating.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    focalizer: str
    distance: FocalizationDistance = FocalizationDistance.ZERO
    reliability: ReliabilityLevel = ReliabilityLevel.RELIABLE


class MoodState(BaseModel):
    """Affective/tonal state for a Scene.

    :ivar id: Unique identifier.
    :ivar label: Free-text mood label (e.g. "melancholic", "tense").
    :ivar valence: Sentiment polarity in [-1.0, 1.0]; negative = negative affect.
    :ivar arousal: Activation level in [0.0, 1.0]; high = energetic.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    valence: float = Field(default=0.0, ge=-1.0, le=1.0)
    arousal: float = Field(default=0.5, ge=0.0, le=1.0)


class GenreProfile(BaseModel):
    """Genre encoding for a Scene or Narrative.

    :ivar id: Unique identifier.
    :ivar name: Genre name (e.g. "gothic", "road novel").
    :ivar conventions: JSON-serialisable list of constraint strings describing
        genre-specific narrative obligations.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    conventions: list[str] = Field(default_factory=list)


class Chronotope(BaseModel):
    """Bakhtinian time-space frame for a Scene.

    :ivar id: Unique identifier.
    :ivar time_mode: One of: cyclical, linear, suspended, compressed.
    :ivar space_mode: One of: bounded, open, liminal, utopian.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    time_mode: str
    space_mode: str


class Character(BaseModel):
    """A participant or focalizer in the narrative.

    :ivar id: Unique identifier.
    :ivar name: Character name as it appears in the source text.
    :ivar role: Narrative role (e.g. "protagonist", "antagonist", "witness").
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    role: str = "character"


class Event(BaseModel):
    """An action-bearing narrative unit extracted from an Atom.

    :ivar id: Unique identifier.
    :ivar verb: Lemmatised main verb of the event clause.
    :ivar tense: Grammatical tense string (e.g. "past", "present").
    :ivar aspect: Grammatical aspect string (e.g. "simple", "progressive").
    :ivar confidence: Extraction confidence in [0.0, 1.0].
    :ivar participants: Characters who take part in this event.
    :ivar needs_review: True when confidence is below the configured threshold.
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

    :ivar id: Unique identifier.
    :ivar text: Raw text of the atom.
    :ivar kind: Functional classification.
    :ivar surface_order: Position within its parent Scene (0-based).
    :ivar confidence: Segmentation / classification confidence in [0.0, 1.0].
    :ivar code_tags: Barthesian code labels attached to this atom.
    :ivar needs_review: True when confidence is below the configured threshold.
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

    :ivar id: Unique identifier (e.g. "pattern.gift_exchange").
    :ivar name: Human-readable name.
    :ivar family: Family tag (see PatternFamily enum).
    :ivar description: Prose description of the pattern's narrative function.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    family: str
    description: str = ""


class PatternInstance(BaseModel):
    """Concrete realisation of a Pattern in a specific Scene.

    :ivar id: Unique identifier.
    :ivar slot: Structural slot label (e.g. "scene-core", "opening").
    :ivar confidence: Match confidence in [0.0, 1.0].
    :ivar template: The Pattern this instance realises.
    :ivar realized_atoms: Atom IDs that ground this instance.
    :ivar realized_events: Event IDs that ground this instance.
    :ivar needs_review: True when confidence is below the configured threshold.
    """

    id: str
    slot: str = "scene-core"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    template: Pattern | None = None
    realized_atom_ids: list[str] = Field(default_factory=list)
    realized_event_ids: list[str] = Field(default_factory=list)
    needs_review: bool = False


# ── Transform audit node ──────────────────────────────────────────────────────


class AtomRevision(BaseModel):
    """A revised version of an Atom's text, preserving the full revision chain.

    The graph schema mirrors the transform audit pattern:
    ``(Atom)-[:CURRENT_REVISION]->(AtomRevision)`` points to the latest;
    ``(Atom)-[:HAS_REVISION]->(AtomRevision)`` retains all versions;
    ``(AtomRevision)-[:SUPERSEDES]->(AtomRevision)`` links new → old.

    :ivar id: Unique identifier.
    :ivar atom_id: ID of the parent Atom.
    :ivar text: Revised prose text.
    :ivar revised_at: UTC timestamp of the revision.
    :ivar operator: Identifier of the user or system that issued the revision.
    :ivar reason: Optional human-readable reason for the change.
    """

    id: str
    atom_id: str
    text: str
    revised_at: datetime = Field(default_factory=datetime.utcnow)
    operator: str = "system"
    reason: str = ""


class Transform(BaseModel):
    """Audit record for a single transformation operation.

    The Transform node is the spine of the transformation lineage graph.
    It links the scene it modified (``APPLIED_TO``) and the new state node
    it produced (``PRODUCED``).  It is never deleted or overwritten; the
    full sequence of transforms is always traversable.

    :ivar id: Unique identifier.
    :ivar axis: The transformation axis that was applied.
    :ivar operator: Identifier of the user or system that issued the transform.
    :ivar applied_at: UTC timestamp of the operation.
    :ivar parameters: Axis-specific parameters as a free dict (serialised to
        JSON when persisted).
    :ivar scene_id: ID of the scene this transform was applied to.
    :ivar produced_id: ID of the new state node produced by this transform.
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

    :ivar id: Unique identifier.
    :ivar sequence: Ordinal position within the parent Narrative (1-based).
    :ivar summary: Optional human-readable summary of the scene.
    :ivar atoms: Ordered list of Atoms in this scene.
    :ivar events: Events extracted from this scene.
    :ivar pattern_instances: Pattern instances detected in this scene.
    :ivar current_perspective: Active Perspective node (if any).
    :ivar current_mood: Active MoodState node (if any).
    :ivar current_genre: Active GenreProfile node (if any).
    :ivar chronotope: Active Chronotope node (if any).
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

    :ivar id: Unique identifier.
    :ivar title: Working title of the narrative.
    :ivar status: Life-cycle state.
    :ivar source_ref: Optional reference to the originating source document.
    :ivar scenes: Ordered list of Scenes.
    :ivar created_at: UTC creation timestamp.
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

    :ivar source_id: ID of the originating Event.
    :ivar target_id: ID of the destination Event.
    :ivar relation_type: One of ``CAUSES``, ``ENABLES``, ``PREVENTS``,
        ``PRECEDES``.
    """

    model_config = ConfigDict(frozen=True)

    source_id: str
    target_id: str
    relation_type: str


class GraphState(BaseModel):
    """A complete, self-contained snapshot of one narrative's graph state.

    Passed to renderer implementations so they never issue Cypher directly.

    :ivar narrative: The root Narrative with all nested scenes and atoms.
    :ivar transforms: Ordered transform history (oldest first).
    :ivar characters: All Characters referenced in this narrative.
    :ivar event_relations: Explicit inter-event relationships (CAUSES,
        ENABLES, PREVENTS, PRECEDES) fetched from the graph.  Used by the
        GraphML renderer to draw and score causal/temporal edges.
    """

    narrative: Narrative
    transforms: list[Transform] = Field(default_factory=list)
    characters: list[Character] = Field(default_factory=list)
    event_relations: list[EventRelation] = Field(default_factory=list)
