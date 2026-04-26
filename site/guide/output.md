# Output and Rendering

TNGS can render the current graph state to six output formats using a single
endpoint:

```bash
POST /v1/render/{narrative_id}
```

```json
{ "type": "<format>", "params": {} }
```

Every render call advances the narrative status to `rendered`.

---

## Format overview

| Type | Content-Type | Best for |
|------|-------------|----------|
| `prose` | `text/markdown` | Reading the narrative as a draft |
| `diff` | `application/json` | Reviewing what each transform changed |
| `json` | `application/json` | Consuming the full graph state programmatically |
| `cypher` | `text/x-cypher` | Replaying or migrating the narrative graph |
| `markdown` | `text/markdown` | Summaries and transform logs for human review |
| `graphml` | `application/xml` | Visual graph exploration in yEd |

---

## `prose` — Markdown draft

Renders atoms in surface order with optional scene headers and context
blocks showing the active perspective and mood.

```bash
curl -X POST http://localhost:8000/v1/render/<narrative-id> \
  -H "Content-Type: application/json" \
  -d '{"type": "prose"}' \
  | jq -r '.content'
```

Output example:

```markdown
# The Gift

## Scene 1
*Alice offered the book. She smiled.*

> POV: Alice (internal, reliable) | Mood: warm

Alice offered the book. She smiled.

## Scene 2
Bob accepted it gratefully. He nodded once.
```

---

## `diff` — Transformation diff

Returns a JSON document showing before/after state for every scene that has
been transformed.  Grouped by axis.

```bash
curl -X POST http://localhost:8000/v1/render/<narrative-id> \
  -H "Content-Type: application/json" \
  -d '{"type": "diff"}' \
  | jq '.content | fromjson'
```

Output structure:

```json
{
  "narrative_id": "...",
  "transforms": [
    {
      "transform_id": "...",
      "axis": "pov",
      "scene_id": "...",
      "before": null,
      "after": { "focalizer": "char-alice", "distance": "internal" }
    }
  ]
}
```

---

## `json` — Full graph state

Dumps the complete graph state as a structured JSON document.  Useful for
programmatic consumption, archiving, or feeding into downstream tools.

```bash
curl -X POST http://localhost:8000/v1/render/<narrative-id> \
  -H "Content-Type: application/json" \
  -d '{"type": "json"}' \
  | jq '.content | fromjson'
```

Top-level structure:

```json
{
  "narrative": {
    "id": "...", "title": "...", "status": "rendered",
    "scenes": [
      {
        "id": "...", "sequence": 1,
        "atoms": [ { "id": "...", "text": "...", "kind": "descriptive" } ],
        "events": [ { "id": "...", "verb": "offered", "tense": "past" } ],
        "current_perspective": { ... },
        "current_mood": { ... }
      }
    ]
  },
  "transforms": [ ... ],
  "characters": [ ... ],
  "event_relations": [ ... ]
}
```

---

## `cypher` — Reproducible MERGE script

Generates a Cypher script of `MERGE` statements that, when run against an
empty database, reconstructs the current graph state.  Useful for migrations,
snapshots, and sharing narrative graphs between Neo4j instances.

```bash
curl -X POST http://localhost:8000/v1/render/<narrative-id> \
  -H "Content-Type: application/json" \
  -d '{"type": "cypher"}' \
  | jq -r '.content' > narrative_snapshot.cypher

# Replay against a fresh Neo4j instance
cypher-shell -u neo4j -p <password> < narrative_snapshot.cypher
```

---

## `markdown` — Structured summary

Produces a human-readable Markdown document with:

- Narrative metadata header
- Per-scene summary tables (atoms, events, active transforms)
- Transform log sorted by `applied_at`
- Pattern instance summary

Useful for editorial review, annotation sessions, or exporting to a notebook.

```bash
curl -X POST http://localhost:8000/v1/render/<narrative-id> \
  -H "Content-Type: application/json" \
  -d '{"type": "markdown"}' \
  | jq -r '.content' > summary.md
```

---

## `graphml` — yEd graph diagram

Produces a [GraphML](http://graphml.graphdrawing.org/) document that can be
opened directly in [yEd Graph Editor](https://www.yworks.com/products/yed).
Edges are colored by **narrative tension score** on a six-stop gradient from
neutral grey to dark red.

```bash
curl -X POST http://localhost:8000/v1/render/<narrative-id> \
  -H "Content-Type: application/json" \
  -d '{"type": "graphml"}' \
  | jq -r '.content' > narrative.graphml
```

See [Reading the Graph in yEd](yed.md) for a step-by-step guide.

The render response also includes metadata:

```json
{
  "narrative_id": "...",
  "render_type": "graphml",
  "content": "<?xml ...",
  "content_type": "application/xml",
  "metadata": {
    "node_count": 24,
    "edge_count": 31,
    "format": "graphml-yed"
  }
}
```

---

## Accessing rendered content from the API

The render endpoint always returns the same envelope:

```json
{
  "narrative_id": "string",
  "render_type": "string",
  "content": "string",
  "content_type": "string"
}
```

The `content` field is always a string.  For `json` and `diff` types, parse
it with `JSON.parse()` or `jq '.content | fromjson'`.  For `graphml`, write it
directly to a `.graphml` file.

---

## Saving output to files

```bash
# Save all formats for a narrative
ID="your-narrative-id"

curl -sX POST http://localhost:8000/v1/render/$ID -H "Content-Type: application/json" \
  -d '{"type":"prose"}'    | jq -r '.content' > output_prose.md

curl -sX POST http://localhost:8000/v1/render/$ID -H "Content-Type: application/json" \
  -d '{"type":"json"}'     | jq -r '.content' > output_graph.json

curl -sX POST http://localhost:8000/v1/render/$ID -H "Content-Type: application/json" \
  -d '{"type":"cypher"}'   | jq -r '.content' > output_replay.cypher

curl -sX POST http://localhost:8000/v1/render/$ID -H "Content-Type: application/json" \
  -d '{"type":"markdown"}' | jq -r '.content' > output_summary.md

curl -sX POST http://localhost:8000/v1/render/$ID -H "Content-Type: application/json" \
  -d '{"type":"graphml"}'  | jq -r '.content' > output_graph.graphml
```
