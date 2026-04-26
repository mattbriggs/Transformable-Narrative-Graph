"""Bounded enumeration types for the TNGS domain vocabulary.

All semantic axes that must stay closed (cannot be arbitrary strings) are
defined here.  Using enumerations rather than open strings makes every
vocabulary set queryable by value, prevents typo-driven divergence, and
guarantees that Pydantic validation catches unknown values at the API
boundary rather than silently persisting garbage to the graph.
"""

from enum import Enum


class AtomKind(str, Enum):
    """Functional classification of a narrative atom.

    :cvar DESCRIPTIVE: Depicts setting, appearance, or state.
    :cvar DIALOGIC: Direct or indirect speech act.
    :cvar REFLEXIVE: Character introspection or narratorial comment.
    :cvar TRANSITIONAL: Moves the narrative between scenes or moments.
    :cvar EXPOSITORY: Background information, world-building, or backstory.
    """

    DESCRIPTIVE = "descriptive"
    DIALOGIC = "dialogic"
    REFLEXIVE = "reflexive"
    TRANSITIONAL = "transitional"
    EXPOSITORY = "expository"


class BarthesCode(str, Enum):
    """Barthesian narrative codes (from *S/Z*, Roland Barthes, 1970).

    :cvar HERMENEUTIC: Mystery or enigma that propels reader anticipation.
    :cvar PROAIRETIC: Action sequence implying a consequent action.
    :cvar SEMIC: Connotative detail that builds character or atmosphere.
    :cvar SYMBOLIC: Binary or antithetical thematic opposition.
    :cvar CULTURAL: Reference to a shared body of knowledge or convention.
    """

    HERMENEUTIC = "hermeneutic"
    PROAIRETIC = "proairetic"
    SEMIC = "semic"
    SYMBOLIC = "symbolic"
    CULTURAL = "cultural"


class FocalizationDistance(str, Enum):
    """Genettean focalization distance for a Perspective node.

    :cvar ZERO: Narrator knows more than any character (omniscient).
    :cvar INTERNAL: Narrative filtered through one character's consciousness.
    :cvar EXTERNAL: Narrator records behaviour without access to interiority.
    """

    ZERO = "zero"
    INTERNAL = "internal"
    EXTERNAL = "external"


class ReliabilityLevel(str, Enum):
    """Credibility rating assigned to a narrative Perspective.

    :cvar RELIABLE: Narrator or focalizer is trustworthy.
    :cvar UNRELIABLE: Narrator or focalizer is demonstrably biased or wrong.
    :cvar AMBIGUOUS: Reliability cannot be determined from available evidence.
    """

    RELIABLE = "reliable"
    UNRELIABLE = "unreliable"
    AMBIGUOUS = "ambiguous"


class TransformAxis(str, Enum):
    """The six supported transformation axes of TNGS.

    Each axis operates on a specific domain object and produces a new
    state node rather than overwriting the existing one, preserving the
    full transformation lineage as traversable graph state.

    :cvar POV: Point-of-view / focalization shift.
    :cvar MOOD: Affective / tonal retag.
    :cvar GENRE: Genre profile swap.
    :cvar CHRONOTOPE: Bakhtinian time-space remap.
    :cvar RELIABILITY: Narrator reliability adjustment.
    :cvar CODE_OVERLAY: Barthesian code attachment to atoms.
    """

    POV = "pov"
    MOOD = "mood"
    GENRE = "genre"
    CHRONOTOPE = "chronotope"
    RELIABILITY = "reliability"
    CODE_OVERLAY = "code_overlay"


class NarrativeStatus(str, Enum):
    """Life-cycle states for a Narrative node (see state machine, SRS §7.4).

    :cvar DRAFT: Narrative created but not yet atomized.
    :cvar ATOMIZED: Ingest complete; atoms and events persisted.
    :cvar PATTERNED: Pattern detection run; instances linked.
    :cvar TRANSFORMED: At least one transformation axis applied.
    :cvar RENDERED: Render operation has been performed.
    :cvar EXPORTED: Narrative exported to an external format.
    :cvar ARCHIVED: Administratively archived; no further processing.
    """

    DRAFT = "draft"
    ATOMIZED = "atomized"
    PATTERNED = "patterned"
    TRANSFORMED = "transformed"
    RENDERED = "rendered"
    EXPORTED = "exported"
    ARCHIVED = "archived"


class PatternFamily(str, Enum):
    """High-level family tags for narrative pattern templates.

    :cvar RITUAL: Socially codified exchange or ceremony.
    :cvar TRANSITION: Movement across a threshold or boundary.
    :cvar CONFLICT: Antagonistic encounter between agents.
    :cvar REVELATION: Disclosure of previously hidden information.
    :cvar PURSUIT: Chase or quest structure.
    :cvar TRANSFORMATION: Internal or external change of state.
    """

    RITUAL = "ritual"
    TRANSITION = "transition"
    CONFLICT = "conflict"
    REVELATION = "revelation"
    PURSUIT = "pursuit"
    TRANSFORMATION = "transformation"


class RenderType(str, Enum):
    """Output format requested from the Render endpoint.

    :cvar PROSE: Atoms in surface order as a prose draft.
    :cvar DIFF: Side-by-side before/after for each transformed axis.
    :cvar JSON: Full graph state as a JSON document.
    :cvar CYPHER: Replayable Cypher MERGE script.
    :cvar MARKDOWN: Structured Markdown summary with transform log.
    :cvar GRAPHML: yEd-compatible GraphML with edges coloured by narrative
        tension.  Suitable for visual graph exploration in yEd or any tool
        that reads the GraphML + yFiles extension schema.
    """

    PROSE = "prose"
    DIFF = "diff"
    JSON = "json"
    CYPHER = "cypher"
    MARKDOWN = "markdown"
    GRAPHML = "graphml"
