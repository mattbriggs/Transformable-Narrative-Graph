# Transformable Narrative Graph System

A graph-native system for representing, transforming, and rendering literary narratives. TNGS stores narratives as property graphs in Neo4j and applies auditable literary transformations across six axes: POV, mood, genre, time-space framing, reliability, and narrative code overlay.

## Requirements

- Python 3.12+
- Docker Engine 26+, Docker Compose v2
- Neo4j 2025.x Community (via Docker)

## Quick Start (Docker)

```bash
# 1. Set your Neo4j password
cp .env.example .env
# Edit .env and change NEO4J_PASSWORD to something secure

# 2. Start the full stack
docker compose up -d --build

# 3. Confirm readiness (waits for Neo4j health check)
curl http://localhost:8000/v1/health/ready

# 4. Ingest a Markdown narrative (chapter headings become scene boundaries)
curl -X POST http://localhost:8000/v1/notes/import \
  -H "Content-Type: application/json" \
  -d '{
    "title": "The Yellow Wallpaper",
    "format": "markdown",
    "text": "## The House\n\nIt is very seldom that mere ordinary people like John and myself secure ancestral halls for the summer.\n\n## The Room\n\nI do not like our room a bit."
  }'

# 5. Open the interactive API docs
open http://localhost:8000/docs
```

For a complete end-to-end example using Gilman's *The Yellow Wallpaper*, see the [Walkthrough](site/guide/walkthrough.md).

## Local Development

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Run unit tests (no Neo4j required)
pytest -m "not integration"

# Run with coverage report
pytest -m "not integration" --cov=src/tng --cov-report=term-missing

# Start the API server (requires a running Neo4j)
NEO4J_URI=bolt://localhost:7687 NEO4J_PASSWORD=neo4j \
  uvicorn tng.api.main:app --reload
```

## Running Tests

```bash
# Unit + API tests only (no live database)
pytest -m "not integration" -v

# All tests including integration (requires NEO4J_URI env var)
NEO4J_URI=bolt://localhost:7687 \
NEO4J_USER=neo4j \
NEO4J_PASSWORD=your-password \
pytest -v

# Coverage HTML report
pytest -m "not integration" --cov=src/tng --cov-report=html
open htmlcov/index.html
```

## Project Structure

```
src/tng/
  domain/          # Pure Python domain models and enumerations
  repository/      # GraphRepository + all Cypher queries
  ingest/          # Text segmenter, entity extractor, event detector, annotator
  services/        # IngestService, PatternService, TransformService, RenderService
  renderers/       # Six output renderers + RendererProtocol
  api/             # FastAPI app, Pydantic schemas, routers, dependency injection
  config.py        # Settings (pydantic-settings, reads .env.local)

tests/
  unit/            # Pure unit tests — no database
  api/             # FastAPI TestClient tests — mock repo injected
  integration/     # Live-database tests — skipped unless NEO4J_URI is set

ops/
  migrations/      # Idempotent Cypher schema migrations
  scripts/         # backup.sh, restore.sh

docs/              # MkDocs built HTML (served by GitHub Pages)
site/              # MkDocs source (Material theme + Mermaid.js)
design/            # SRS and implementation plans
```

## Ingesting Markdown

Pass `"format": "markdown"` to treat `#`/`##` headings as scene boundaries.
Each heading becomes a scene whose `summary` is the heading text; the prose
under the heading becomes that scene's atoms. Without this flag every
paragraph is its own scene and headings are treated as prose.

```json
{
  "title": "My Novel",
  "format": "markdown",
  "text": "## Chapter One\n\nAlice arrived at dusk. She knocked twice.\n\n## Chapter Two\n\nBob opened the door slowly."
}
```

Result: 2 scenes. Scene 1 `summary = "Chapter One"`, Scene 2 `summary = "Chapter Two"`.

## Transformation Axes

Apply a transformation to one scene with `POST /v1/transforms/apply`:

```json
{
  "scene_id": "my-scene-id",
  "axis": "pov",
  "parameters": {
    "focalizer": "character-id",
    "distance": "internal",
    "reliability": "unreliable"
  }
}
```

Apply a transformation to **every scene** in a narrative with `POST /v1/transforms/apply-bulk`:

```json
{
  "narrative_id": "my-narrative-id",
  "axis": "mood",
  "parameters": { "label": "dread", "valence": -0.8, "arousal": 0.7 }
}
```

| Axis | Parameters |
|------|-----------|
| `pov` | `focalizer`, `distance` (zero/internal/external), `reliability` |
| `mood` | `label`, `valence` [-1,1], `arousal` [0,1] |
| `genre` | `name`, `conventions` (list) |
| `chronotope` | `time_mode` (cyclical/linear/suspended/compressed), `space_mode` (bounded/open/liminal/utopian) |
| `reliability` | `reliability` (reliable/unreliable/ambiguous) |
| `code_overlay` | `atom_id`, `code` (hermeneutic/proairetic/semic/symbolic/cultural) |

All transforms are **non-destructive** — the previous state is detached but never deleted.

## Revising Atom Text

Atom text can be revised non-destructively after ingest. The original is
preserved; all renderers use the latest revision.

```bash
# Revise a sentence
curl -X PATCH http://localhost:8000/v1/atoms/<atom-id> \
  -H "Content-Type: application/json" \
  -d '{
    "text": "She hesitated at the threshold, then stepped inside.",
    "operator": "editor",
    "reason": "strengthen the beat"
  }'

# List full revision history
curl http://localhost:8000/v1/atoms/<atom-id>/revisions
```

## Render Outputs

Render the current graph state with `POST /v1/render/{narrative_id}`:

| Type | Content |
|------|---------|
| `prose` | Markdown draft — chapter headings from `scene.summary`, POV/mood annotations |
| `diff` | JSON transformation diff by axis |
| `json` | Full graph state as JSON |
| `cypher` | Reproducible Cypher MERGE script |
| `markdown` | Structured summary with patterns and transform log |
| `graphml` | yEd-compatible GraphML with tension-colored edges |

The `prose` render uses `scene.summary` as the Markdown heading when set
(populated by the Markdown segmenter from `##` headings), falling back to
`## Scene N` for plain-text ingested narratives.

## GraphML Export (yEd)

Export any narrative as a graph diagram that can be opened in [yEd Graph Editor](https://www.yworks.com/products/yed):

```bash
# Export GraphML
curl -X POST http://localhost:8000/v1/render/<narrative_id> \
  -H "Content-Type: application/json" \
  -d '{"type": "graphml"}' \
  | jq -r '.content' > narrative.graphml

# Open in yEd: File → Open → narrative.graphml
# Apply layout: Layout → Hierarchical (or Organic)
```

**Edge color legend — narrative tension (grey → dark red):**

| Color | Score | Meaning |
|-------|-------|---------|
| Grey `#A0A0A0` | 0.0 | Structural (HAS_SCENE, CONTAINS) |
| Steel blue `#4682B4` | 0.2 | Temporal sequence (PRECEDES) |
| Goldenrod `#DAA520` | 0.4 | Enabling / participation |
| Orange `#FF8C00` | 0.6 | Causal chain (CAUSES) |
| Crimson `#DC143C` | 0.8 | Strong causal + mystery code |
| Dark red `#8B0000` | 1.0 | Prevention + high-arousal negative mood |

Tension is a composite of relationship type, narrative code tags (mystery/enigma codes add up to +0.4, action codes up to +0.3), and scene mood (high arousal × negative valence).

## Documentation

Source files live in `site/`. The built HTML is written to `docs/` and served
by GitHub Pages from the `main` branch `docs/` folder.

```bash
# Install docs dependencies
pip install -e ".[docs]"

# Live-reload preview
mkdocs serve
# Open http://127.0.0.1:8000

# Build static HTML into docs/ (for GitHub Pages commit)
mkdocs build
```

**Doc sections:**

| Section | Source |
|---------|--------|
| Home / overview | `site/index.md` |
| Context & theory | `site/context.md` |
| **Guide: Walkthrough** | `site/guide/walkthrough.md` |
| Guide: Parsing | `site/guide/parsing.md` |
| Guide: Transforming | `site/guide/transforming.md` |
| Guide: Output & rendering | `site/guide/output.md` |
| Guide: Reading in yEd | `site/guide/yed.md` |
| Design: Architecture | `site/design/architecture.md` |
| Design: Data model | `site/design/data-model.md` |
| Design: Transform engine | `site/design/transformation-engine.md` |
| Design: GraphML export | `site/design/graphml-export.md` |
| API reference | `site/api/reference.md` |

## Schema Migrations

```bash
# Apply the initial schema (idempotent — safe to run on every startup)
docker compose exec -T neo4j cypher-shell \
  -u "${NEO4J_USER:-neo4j}" -p "${NEO4J_PASSWORD:-CHANGE_ME_BEFORE_DEPLOY}" \
  < ops/migrations/0001_initial_schema.cypher

# Apply the atom revisions schema (iteration 2)
docker compose exec -T neo4j cypher-shell \
  -u "${NEO4J_USER:-neo4j}" -p "${NEO4J_PASSWORD:-CHANGE_ME_BEFORE_DEPLOY}" \
  < ops/migrations/0002_atom_revisions.cypher
```

## Backup and Restore

```bash
# Community Edition offline dump
./ops/scripts/backup.sh ./backups/$(date +%Y%m%d)

# Restore to an isolated directory for verification
./ops/scripts/restore.sh ./backups/20260426 ./restore-test
```

## License

MIT
