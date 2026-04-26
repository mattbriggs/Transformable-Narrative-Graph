# Iteration 2 Implementation Plan

## Overview

Iteration 2 closes four workflow gaps identified during the post-iteration-1 review.
The gaps were exposed by tracing a concrete novel-editing workflow through the
existing system:

> Ingest Markdown → review graph in Neo4j → export GraphML → change an aspect →
> re-export GraphML → export revised Markdown.

| Gap | Description | Effort |
|-----|-------------|--------|
| 1 | Markdown headings not treated as scene boundaries | Medium |
| 2 | Transforms apply per-scene only — no bulk/narrative-level call | Low |
| 3 | Atom text is immutable after ingest | Medium-High |
| 4 | Prose export ignores chapter structure | Low (blocked on Gap 1) |

Implementation order: **1 → 4 → 2 → 3**.
Gaps 1 and 4 are a dependent pair. Gap 2 is independent and quick. Gap 3 is the
largest piece and is implemented last.

---

## Gap 1 — Markdown-Aware Segmenter

### Problem

`segment_text()` splits only on blank lines (double newlines). A Markdown heading
such as `# Chapter One` is treated as the prose of Scene 1 rather than a scene
boundary with a title. Chapter hierarchy is lost at ingest.

Additionally, the current ingest service sets `scene.summary = paragraph[:120]`,
which stores the first 120 characters of prose text as the summary — not a
meaningful title.

### Design

Introduce a new function `segment_markdown(text) -> list[SceneSection]` alongside
the existing `segment_text`. A `SceneSection` is the unified intermediate type
that both paths produce:

```python
@dataclass
class SceneSection:
    summary: str          # chapter/section heading, or "" for plain-text path
    sentences: list[str]  # all sentences across all paragraphs in this section
```

**Markdown segmentation rules:**

1. Strip YAML frontmatter (existing `strip_markdown_frontmatter`).
2. Walk lines. A line matching `^#{1,6}\s+(.+)` starts a new section; the
   capture group becomes `summary`.
3. Non-heading, non-empty lines accumulate as prose in the current section.
4. Within each section's prose block, split sentences using the existing
   `_split_sentences` logic.
5. A leading prose block with no preceding heading gets `summary = ""`.

**IngestService changes:**

- Replace the `segment_text` call with a dispatch:
  - `format == "markdown"` → `segment_markdown(text)` → `list[SceneSection]`
  - all other formats → `segment_text(text)`, then convert to `list[SceneSection]`
    with `summary = ""`
- Remove `summary=paragraph[:120]` from the scene construction; set
  `summary=section.summary` instead.

### Files Changed

| File | Change |
|------|--------|
| `src/tng/ingest/segmenter.py` | Add `SceneSection` dataclass + `segment_markdown()` |
| `src/tng/services/ingest_service.py` | Dispatch on format; unify loop over `SceneSection` |

### Tests Added

| File | Cases |
|------|-------|
| `tests/unit/test_segmenter.py` | `segment_markdown` with headings, frontmatter, mixed, no headings |
| `tests/unit/test_segmenter.py` | Heading-only document, heading + paragraphs, multiple heading levels |

---

## Gap 4 — Chapter-Aware Prose Renderer

### Problem

The prose renderer always emits `## Scene N` as the scene heading and renders
`scene.summary` as an italicised aside. There is no way to get back a Markdown
document that looks like the original chapter layout.

### Design

Update `ProseRenderer._render_scene`:

- If `scene.summary` is non-empty → emit `## {scene.summary}` as the heading.
- If `scene.summary` is empty → emit `## Scene {scene.sequence}` (existing fallback).
- Remove the italicised `*summary*` line (it is now the heading itself).

Because Gap 1 ensures the markdown path stores heading text in `summary` and the
plain-text path stores `""`, the renderer needs no format-awareness of its own.

### Files Changed

| File | Change |
|------|--------|
| `src/tng/renderers/prose_renderer.py` | Update `_render_scene` heading logic |

### Tests Added

| File | Cases |
|------|-------|
| `tests/unit/test_renderers.py` | Scene with summary → heading uses summary text |
| `tests/unit/test_renderers.py` | Scene without summary → fallback to `## Scene N` |

---

## Gap 2 — Bulk Transform Endpoint

### Problem

Applying a transformation across a whole narrative requires one HTTP call per
scene. There is no single endpoint to shift, for example, the POV of every scene
in one request.

### Design

New endpoint: `POST /v1/transforms/apply-bulk`

**Request:**
```json
{
  "narrative_id": "abc123",
  "axis": "mood",
  "parameters": { "label": "dread", "valence": -0.8, "arousal": 0.7 },
  "operator": "api"
}
```

**Response:**
```json
{
  "narrative_id": "abc123",
  "applied_count": 12,
  "results": [
    { "transform_id": "...", "scene_id": "...", "axis": "mood", ... },
    ...
  ]
}
```

**Implementation:**

- `GraphRepository.get_scene_ids(narrative_id) -> list[str]` — new Cypher query,
  returns scene IDs in sequence order.
- `TransformService.apply_bulk(narrative_id, axis, parameters, operator)` — loops
  over scene IDs and calls `apply()` per scene; returns list of `TransformResponse`.
- New schemas: `BulkTransformRequest`, `BulkTransformResponse`.
- New route in `src/tng/api/routers/transforms.py`.

Scenes that fail validation on a given axis (e.g. the axis is `code_overlay` which
targets a specific atom ID, not a scene) raise `ValueError` before any write; the
endpoint returns 400.

### Files Changed

| File | Change |
|------|--------|
| `src/tng/repository/cypher_queries.py` | Add `GET_SCENE_IDS_FOR_NARRATIVE` query |
| `src/tng/repository/graph_repository.py` | Add `get_scene_ids(narrative_id)` |
| `src/tng/services/transform_service.py` | Add `apply_bulk()` method |
| `src/tng/api/schemas.py` | Add `BulkTransformRequest`, `BulkTransformResponse` |
| `src/tng/api/routers/transforms.py` | Add `POST /v1/transforms/apply-bulk` route |

### Tests Added

| File | Cases |
|------|-------|
| `tests/api/test_transforms.py` | Bulk apply succeeds → `applied_count` matches scene count |
| `tests/api/test_transforms.py` | Unknown narrative → 404 |
| `tests/api/test_transforms.py` | Invalid params → 400, no partial writes |

---

## Gap 3 — Versioned Atom Text Editing

### Problem

Atom text is immutable once ingested. There is no way to revise what a sentence
says. This is the single biggest friction point in the
"change an aspect → export Markdown" cycle when the change involves actual prose.

### Design Philosophy

Match the non-destructive contract already established by the transform engine:
never delete original data; always create a new node and re-point the `CURRENT_*`
relationship. This preserves the full revision lineage.

### New Domain Model

```python
class AtomRevision(BaseModel):
    id: str
    atom_id: str
    text: str
    revised_at: datetime
    operator: str
    reason: str = ""
```

### Graph Schema

```
(Atom)-[:CURRENT_REVISION]->(AtomRevision)   # points to latest
(Atom)-[:HAS_REVISION]->(AtomRevision)        # all revisions, traversable
(AtomRevision)-[:SUPERSEDES]->(AtomRevision)  # revision chain
```

On first revision the `Atom` node gains `CURRENT_REVISION` and `HAS_REVISION`
edges to the new node. On subsequent revisions the old `CURRENT_REVISION` is
detached, the new node gets it, and a `SUPERSEDES` edge is added from new → old.

### New Endpoint

`PATCH /v1/atoms/{atom_id}` — revise atom text.

**Request:**
```json
{ "text": "She did not answer, but her silence said everything.", "operator": "user", "reason": "strengthen beat" }
```

**Response:**
```json
{ "atom_id": "...", "revision_id": "...", "text": "..." }
```

`GET /v1/atoms/{atom_id}/revisions` — list full revision history.

### Renderer Integration

`GraphRepository.get_graph_state()` resolves each atom's `CURRENT_REVISION` text
before building the `GraphState` snapshot. Renderers receive `Atom` objects with
`text` already set to the latest revision's text — no renderer changes needed.

If no revision exists, `Atom.text` is the original ingested text.

### Files Changed

| File | Change |
|------|--------|
| `src/tng/domain/models.py` | Add `AtomRevision` model |
| `src/tng/repository/cypher_queries.py` | Add `CREATE_ATOM_REVISION`, `GET_ATOM_REVISIONS`, `GET_CURRENT_REVISION_TEXT` queries |
| `src/tng/repository/graph_repository.py` | Add `revise_atom()`, `get_atom_revisions()`, and update `get_graph_state()` to resolve current revision text |
| `src/tng/api/schemas.py` | Add `AtomReviseRequest`, `AtomRevisionRecord`, `AtomRevisionListResponse` |
| `src/tng/api/routers/atoms.py` | New router: `PATCH /v1/atoms/{id}`, `GET /v1/atoms/{id}/revisions` |
| `src/tng/api/main.py` | Register atoms router |

### Tests Added

| File | Cases |
|------|-------|
| `tests/api/test_atoms.py` | Revise atom → revision created, text updated |
| `tests/api/test_atoms.py` | Second revision → supersedes chain correct |
| `tests/api/test_atoms.py` | Get revisions → ordered history returned |
| `tests/api/test_atoms.py` | Unknown atom → 404 |
| `tests/unit/test_renderers.py` | Prose renderer uses revised text when `Atom.text` updated |

---

## Dependency Graph

```
Gap 1 (markdown segmenter)
    └─► Gap 4 (prose renderer headings)   [Gap 4 reads scene.summary set by Gap 1]

Gap 2 (bulk transforms)                   [independent]

Gap 3 (atom revisions)                    [independent; repository change feeds renderers]
```

---

## Schema Migration

A new idempotent Cypher migration for the `AtomRevision` node and its constraints:

```
ops/migrations/0002_atom_revisions.cypher
```

Content:
```cypher
CREATE CONSTRAINT atom_revision_id IF NOT EXISTS
  FOR (r:AtomRevision) REQUIRE r.id IS UNIQUE;

CREATE INDEX atom_revision_atom_id IF NOT EXISTS
  FOR (r:AtomRevision) ON (r.atom_id);
```

---

## Acceptance Criteria

### End-to-end workflow must pass:

1. `POST /v1/notes/import` with `format: "markdown"` and a multi-chapter novel →
   scene summaries equal the chapter headings; chapter prose text is in atoms; no
   heading text appears as an atom.

2. `POST /v1/render/{id}` with `type: "prose"` → output Markdown uses chapter
   headings from `scene.summary`, not `## Scene N`.

3. `POST /v1/transforms/apply-bulk` with `narrative_id` and `axis: "mood"` →
   `applied_count` equals scene count; each scene has a `CURRENT_MOOD` node.

4. `PATCH /v1/atoms/{id}` → revised text appears in subsequent `prose` render
   output; `GET /v1/atoms/{id}/revisions` returns the full chain including original.

### No regressions:

- All 168 existing unit + API tests continue to pass.
- Plain-text ingest (`format: "text"`) continues to produce one scene per
  paragraph with `summary = ""`.
