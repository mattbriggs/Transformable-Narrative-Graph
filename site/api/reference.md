# API Reference

The TNGS REST API is served at port `8000`. Interactive Swagger UI is available at `/docs` when the server is running.

**Base URL:** `http://localhost:8000`  
**Authentication:** Bearer token (header: `Authorization: Bearer <token>`)  
**Content-Type:** `application/json`

---

## Health

### `GET /v1/health/live`

Liveness probe. Always returns 200.

**Response 200:**
```json
{"status": "ok"}
```

---

### `GET /v1/health/ready`

Readiness probe. Returns 200 when Neo4j is reachable, 503 otherwise.

**Response 200:**
```json
{"status": "ok", "neo4j": "reachable"}
```

**Response 503:**
```json
{"detail": {"status": "degraded", "neo4j": "Connection refused"}}
```

---

## Ingest

### `POST /v1/notes/import`

Ingest raw text, Markdown, or pre-structured JSON. Runs the full pipeline and persists the narrative graph.

**Request body:**
```json
{
  "title": "My Story",
  "text": "Alice walked slowly. She stopped.\n\nBob arrived at last.",
  "narrative_id": "my-id-001",
  "source_ref": "notebook-2026-04.txt",
  "format": "text"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | ✓ | Narrative title |
| `text` | string | | Raw prose to ingest |
| `narrative_id` | string | | Generated if absent |
| `source_ref` | string | | Provenance reference |
| `format` | string | | `text` (default), `markdown`, `json`, `csv` |

**Response 201:**
```json
{
  "narrative_id": "my-id-001",
  "scene_count": 2,
  "atom_count": 3,
  "event_count": 2,
  "character_count": 2,
  "pattern_count": 0,
  "flagged_count": 0
}
```

---

## Narratives

### `GET /v1/narratives/{id}`

Retrieve a narrative's current state.

**Path:** `narrative_id` — the narrative's unique ID

**Response 200:**
```json
{
  "id": "my-id-001",
  "title": "My Story",
  "status": "patterned",
  "source_ref": "notebook-2026-04.txt",
  "scene_count": 2,
  "created_at": "2026-04-26T10:00:00"
}
```

**Response 404:** Narrative not found.

---

### `DELETE /v1/narratives/{id}`

Archive a narrative (sets `status` to `archived`).

**Response 204:** No content.  
**Response 404:** Narrative not found.

---

## Patterns

### `POST /v1/patterns`

Register a new pattern template.

**Request body:**
```json
{
  "id": "pattern.pursuit",
  "name": "Pursuit",
  "family": "pursuit",
  "description": "A chase or quest structure."
}
```

**Response 201:**
```json
{"id": "pattern.pursuit", "name": "Pursuit", "family": "pursuit", "description": "..."}
```

---

### `GET /v1/patterns`

List all registered patterns, optionally filtered by family.

**Query params:**
- `family` (optional) — filter by pattern family string

**Response 200:** Array of pattern records.

---

### `GET /v1/patterns/{id}/instances`

List concrete pattern instances in a narrative.

**Path:** `pattern_id`  
**Query:** `narrative_id` (required)

**Response 200:** Array of instance records.  
**Response 404:** Pattern template not found.

---

## Transforms

### `POST /v1/transforms/apply`

Apply a transformation axis to a scene.

**Request body:**
```json
{
  "scene_id": "scene-abc",
  "axis": "pov",
  "parameters": {
    "focalizer": "char-alice",
    "distance": "internal",
    "reliability": "unreliable"
  },
  "operator": "matt"
}
```

**Axis parameter reference:**

| Axis | Required parameters |
|------|---------------------|
| `pov` | `focalizer` (string) |
| `mood` | `label` (string); optional: `valence` [-1,1], `arousal` [0,1] |
| `genre` | `name` (string); optional: `conventions` (string list) |
| `chronotope` | `time_mode` (cyclical/linear/suspended/compressed), `space_mode` (bounded/open/liminal/utopian) |
| `reliability` | `reliability` (reliable/unreliable/ambiguous) |
| `code_overlay` | `atom_id` (string), `code` (hermeneutic/proairetic/semic/symbolic/cultural) |

**Response 200:**
```json
{
  "transform_id": "uuid",
  "scene_id": "scene-abc",
  "axis": "pov",
  "produced_id": "pov-uuid",
  "status": "accepted"
}
```

**Response 400:** Invalid axis parameters.  
**Response 422:** Invalid request body schema.

---

### `GET /v1/transforms/{id}`

Retrieve a transform audit record.

**Response 200:**
```json
{
  "id": "transform-uuid",
  "scene_id": "scene-abc",
  "produced_type": ["Perspective"],
  "produced_id": "pov-uuid"
}
```

---

## Render

### `POST /v1/render/{id}`

Render the current graph state to an output format.

**Path:** `narrative_id`

**Request body:**
```json
{
  "type": "prose",
  "params": {}
}
```

| `type` value | Output | Content-Type |
|-------------|--------|--------------|
| `prose` | Markdown prose draft | `text/markdown` |
| `diff` | Transformation diff JSON | `application/json` |
| `json` | Full graph state JSON | `application/json` |
| `cypher` | Replayable MERGE script | `text/x-cypher` |
| `markdown` | Structured summary | `text/markdown` |
| `graphml` | yEd-compatible GraphML with tension-colored edges | `application/xml` |

!!! note "GraphML / yEd"
    The `graphml` render type produces a yEd-compatible GraphML file.  Edges
    are colored on a six-stop gradient (grey → blue → gold → orange → crimson →
    dark-red) by narrative tension score.  See [GraphML Export](../design/graphml-export.md)
    for full details.

**Response 200:**
```json
{
  "narrative_id": "my-id-001",
  "render_type": "prose",
  "content": "# My Story\n\n## Scene 1\n...",
  "content_type": "text/markdown"
}
```

**Response 404:** Narrative not found.  
**Response 422:** Invalid render type.

---

## Module Reference

::: tng.domain.models
::: tng.domain.enums
::: tng.services.ingest_service
::: tng.services.transform_service
::: tng.services.pattern_service
::: tng.services.render_service
::: tng.repository.graph_repository
