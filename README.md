# Transformable Narrative Graph System

A graph-native system for representing, transforming, and rendering literary narratives. TNGS stores narratives as property graphs in Neo4j and applies auditable literary transformations across six axes: POV, mood, genre, time-space framing, reliability, and narrative code overlay.

## Requirements

- Python 3.12+
- Docker Engine 26+, Docker Compose v2
- Neo4j 2025.x Community (via Docker)

## Quick Start (Docker)

```bash
# 1. Create the Neo4j credentials secret file
mkdir -p secrets
echo "neo4j/CHANGE_ME_BEFORE_DEPLOY" > secrets/neo4j_auth.txt

# 2. Start the full stack
docker compose up -d --build

# 3. Confirm readiness (waits for Neo4j health check)
curl http://localhost:8000/v1/health/ready

# 4. Ingest a narrative
curl -X POST http://localhost:8000/v1/notes/import \
  -H "Content-Type: application/json" \
  -d '{
    "title": "The Gift",
    "text": "Alice offered the book. She smiled.\n\nBob accepted it gratefully."
  }'

# 5. Open the interactive API docs
open http://localhost:8000/docs
```

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
  renderers/       # Five output renderers + RendererProtocol
  api/             # FastAPI app, Pydantic schemas, routers, dependency injection
  config.py        # Settings (pydantic-settings, reads .env.local)

tests/
  unit/            # Pure unit tests — no database
  api/             # FastAPI TestClient tests — mock repo injected
  integration/     # Live-database tests — skipped unless NEO4J_URI is set

ops/
  migrations/      # Idempotent Cypher schema migrations
  scripts/         # backup.sh, restore.sh

docs/              # MkDocs source (Material theme + Mermaid.js)
```

## Transformation Axes

Apply a transformation with `POST /v1/transforms/apply`:

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

| Axis | Parameters |
|------|-----------|
| `pov` | `focalizer`, `distance` (zero/internal/external), `reliability` |
| `mood` | `label`, `valence` [-1,1], `arousal` [0,1] |
| `genre` | `name`, `conventions` (list) |
| `chronotope` | `time_mode` (cyclical/linear/suspended/compressed), `space_mode` (bounded/open/liminal/utopian) |
| `reliability` | `reliability` (reliable/unreliable/ambiguous) |
| `code_overlay` | `atom_id`, `code` (hermeneutic/proairetic/semic/symbolic/cultural) |

## Render Outputs

Render the current graph state with `POST /v1/render/{narrative_id}`:

| Type | Content |
|------|---------|
| `prose` | Markdown prose draft in surface order |
| `diff` | JSON transformation diff by axis |
| `json` | Full graph state as JSON |
| `cypher` | Reproducible Cypher MERGE script |
| `markdown` | Structured summary with patterns and transform log |
| `graphml` | yEd-compatible GraphML with tension-colored edges |

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
See [GraphML Export design doc](site/design/graphml-export.md) for full scoring tables.

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
# Apply the initial schema (idempotent)
docker compose exec neo4j cypher-shell \
  < ops/migrations/0001_initial_schema.cypher
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
