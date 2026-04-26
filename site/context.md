# Context

## What Problem Does TNGS Solve?

Literary narratives have structure — causal chains, recurring patterns, focalization choices, tonal registers — but most digital text tools treat narrative as an undifferentiated string. When a writer asks "what happens if I shift this scene to an external narrator?" or "how does the chronotope change if I compress the time frame?", they have no computational tool for exploring the answer systematically.

TNGS makes narrative structure explicit as a property graph and provides auditable operations for transforming that structure along defined literary axes. The output is not final prose — it is a graph state that can be rendered into prose, diffed against a prior state, exported, or further transformed.

## Theoretical Foundations

### Genettean Narratology

Gérard Genette's *Narrative Discourse* (1972) provides the vocabulary for focalization: **zero** (omniscient narrator), **internal** (filtered through one character's consciousness), and **external** (recording behaviour without interiority). TNGS encodes these as the `FocalizationDistance` enumeration on `Perspective` nodes.

### Bakhtinian Chronotope

Mikhail Bakhtin's concept of the chronotope (in *The Dialogic Imagination*, 1975) describes the intrinsic connection between time and space in narrative. A road novel has an **open/linear** chronotope; a fairy tale has a **bounded/cyclical** one. TNGS's `Chronotope` node captures `time_mode` and `space_mode`.

### Barthesian Codes

Roland Barthes's *S/Z* (1970) identified five codes operating on narrative text:
- **Hermeneutic** — creates mystery and anticipation
- **Proairetic** — action implying a consequent action
- **Semic** — connotative detail building character or atmosphere
- **Symbolic** — binary or antithetical thematic opposition
- **Cultural** — reference to shared knowledge or convention

TNGS attaches these as `CodeTag` nodes on individual atoms via the `code_overlay` transformation axis.

## Design Philosophy

1. **Ambiguity is data.** Human annotation varies. Confidence fields and review flags represent ambiguity rather than forcing false certainty. An atom with `confidence=0.45` and `needs_review=True` is a valid graph node that awaits human resolution.

2. **Transformations are non-destructive.** Every transform creates a new state node and detaches (but does not delete) the previous edge. The full lineage is always traversable in the graph.

3. **The graph controls structure; prose style is downstream.** TNGS determines what is said, in what order, from whose perspective, in what mood. How it is *phrased* is the responsibility of a rendering layer that may use templates, rule-based generation, or LLM-assisted writing.

4. **Provider neutrality.** No mandatory dependency on any LLM vendor. The ingest pipeline is rule-based; the rendering layer is pluggable.

## Who Is This For?

| User | Use Case |
|------|----------|
| **Experimental writers** | Exploring alternative narrative paths, perspectives, or genres for the same story material |
| **Computational narratologists** | Studying pattern families, transformation sequences, and inter-text comparison at corpus scale |
| **Digital humanists** | Encoding and querying literary structure in a graph database |
| **Knowledge-graph engineers** | Building narrative-aware knowledge representations |

## Relationship to the White Paper

This system is the reference implementation of the theory described in the companion white paper *"Transformable Narrative Graph: A Formal Model for Literary Narrative as Mutable Graph Structure."* The SRS is the operational specification; the white paper provides the theoretical justification for the design choices.
