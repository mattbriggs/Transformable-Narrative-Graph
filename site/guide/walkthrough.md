# Walkthrough: The Yellow Wallpaper

This guide takes one short literary text through the complete TNGS workflow:
ingest → graph review → GraphML export → narrative transforms → atom revision
→ re-export GraphML → render revised prose.

The source is **"The Yellow Wallpaper"** by Charlotte Perkins Gilman (1892),
a first-person journal narrative well-suited to POV, reliability, and mood
analysis. The text is public domain via [Project Gutenberg](https://www.gutenberg.org/ebooks/1952).

---

## The source text

We work with a four-section curated excerpt, saved as `yellow_wallpaper.md`.
Section headings have been added to mark the natural narrative breaks; the
prose is Gilman's verbatim.

```markdown
# The Yellow Wallpaper

## The House

It is very seldom that mere ordinary people like John and myself secure
ancestral halls for the summer. A colonial mansion, a hereditary estate,
I would say a haunted house, and reach the height of romantic felicity—but
that would be asking too much of fate! Still I will proudly declare that
there is something queer about it.

John laughs at me, of course, but one expects that in marriage. John is
practical in the extreme. He has no patience with faith, an intense horror
of superstition, and he scoffs openly at any talk of things not to be felt
and seen and put down in figures.

John is a physician, and perhaps—(I would not say it to a living soul, of
course, but this is dead paper and a great relief to my mind)—perhaps that
is one reason I do not get well faster. You see, he does not believe I am
sick!

## The Room

I don't like our room a bit. I wanted one downstairs that opened on the
piazza and had roses all over the window, and such pretty old-fashioned
chintz hangings! But John would not hear of it.

It is a big, airy room, the whole floor nearly, with windows that look all
ways, and air and sunshine galore. The paint and paper look as if a boys'
school had used it. It is stripped off—the paper—in great patches all
around the head of my bed, about as far as I can reach, and in a great
place on the other side of the room low down. I never saw a worse paper
in my life.

The color is repellant, almost revolting; a smouldering, unclean yellow,
strangely faded by the slow-turning sunlight. It is a dull yet lurid
orange in some places, a sickly sulphur tint in others.

## The Pattern

I lie here on this great immovable bed—it is nailed down, I believe—and
follow that pattern about by the hour. It is as good as gymnastics, I
assure you. I know a little of the principle of design, and I know this
thing was not arranged on any laws of radiation, or alternation, or
repetition, or symmetry, or anything else that I ever heard of.

The whole thing goes horizontally, too, at least it seems so, and I exhaust
myself in trying to distinguish the order of its going in that direction.
It makes me tired to follow it. I will take a nap, I guess.

## The Figure

Behind that outside pattern the dim shapes get clearer every day. It is
always the same shape, only very numerous. And it is like a woman stooping
down and creeping about behind that pattern. I don't like it a bit.
I wonder—I begin to think—I wish John would take me away from here!

At night in any kind of light, in twilight, candlelight, lamplight, and
worst of all by moonlight, it becomes bars! The outside pattern I mean,
and the woman behind it is as plain as can be.
```

---

## Step 1 — Start the stack

```bash
# Copy the environment template and set a password
cp .env.example .env
# Edit .env: change NEO4J_PASSWORD to something secure

docker compose up -d --build

# Wait for readiness
curl http://localhost:8000/v1/health/ready
# → {"status":"ok","neo4j":"reachable"}
```

---

## Step 2 — Ingest the Markdown

Save the source text block above as `yellow_wallpaper.md` in your working
directory, then post it with `format: "markdown"` so the segmenter treats
`##` headings as scene boundaries.

The text must be JSON-encoded before it can be embedded in the request body
(newlines and quotes need escaping). Two approaches:

**Option A — `jq` (recommended if installed)**

`jq --rawfile` reads the file and handles all escaping automatically:

```bash
NARRATIVE_ID="yw-gilman-001"

jq -n \
  --arg       title "The Yellow Wallpaper" \
  --arg       id    "$NARRATIVE_ID" \
  --rawfile   text  yellow_wallpaper.md \
  '{title: $title, narrative_id: $id, format: "markdown",
    source_ref: "gutenberg.org/ebooks/1952", text: $text}' \
| curl -X POST http://localhost:8000/v1/notes/import \
    -H "Content-Type: application/json" \
    -d @-
```

**Option B — Python (no extra tools needed)**

Set `FILE` to wherever the Markdown file lives (relative or absolute path):

```bash
NARRATIVE_ID="yw-gilman-001"
FILE="yellow_wallpaper.md"

python3 -c "
import json, pathlib
print(json.dumps({
    'title': 'The Yellow Wallpaper',
    'narrative_id': '${NARRATIVE_ID}',
    'format': 'markdown',
    'source_ref': 'gutenberg.org/ebooks/1952',
    'text': pathlib.Path('${FILE}').read_text()
}))" | curl -X POST http://localhost:8000/v1/notes/import \
  -H "Content-Type: application/json" \
  -d @-
```

Response:

```json
{
  "narrative_id": "yw-gilman-001",
  "scene_count": 4,
  "atom_count": 22,
  "event_count": 14,
  "character_count": 2,
  "pattern_count": 0,
  "flagged_count": 1
}
```

Four scenes were created — one per `##` heading. The `## The House` heading
text became `scene.summary` for Scene 1; its prose became atoms. The heading
line itself is **not** an atom. One atom was flagged for review (below the
confidence threshold — likely a sentence fragment).

!!! note "Why `format: \"markdown\"` matters"
    Without it, the segmenter treats every paragraph as a separate scene and
    heading lines become atoms in Scene 1. With it, the four `##` headings
    become the four scene boundaries and scene summaries.

---

## Step 3 — Review the graph in Neo4j

Open the Neo4j Browser at `http://localhost:7474` and run:

```cypher
// See the four scenes and their summaries
MATCH (n:Narrative {id: "yw-gilman-001"})-[:HAS_SCENE]->(s:Scene)
RETURN s.sequence AS seq, s.summary AS heading, s.id AS scene_id
ORDER BY s.sequence
```

| seq | heading | scene_id |
|-----|---------|----------|
| 1 | The House | s-… |
| 2 | The Room | s-… |
| 3 | The Pattern | s-… |
| 4 | The Figure | s-… |

```cypher
// See atoms for Scene 1
MATCH (n:Narrative {id: "yw-gilman-001"})-[:HAS_SCENE]->(s:Scene {sequence: 1})
MATCH (s)-[:CONTAINS]->(a:Atom)
RETURN a.surface_order AS ord, a.text AS text, a.kind AS kind
ORDER BY a.surface_order
```

| ord | text | kind |
|-----|------|------|
| 0 | It is very seldom that mere ordinary people… | descriptive |
| 1 | A colonial mansion, a hereditary estate… | descriptive |
| 2 | Still I will proudly declare that there is something queer about it. | descriptive |
| 3 | John laughs at me, of course, but one expects that in marriage. | descriptive |
| 4 | John is practical in the extreme. | descriptive |
| … | … | … |

```cypher
// Find characters extracted across the narrative
MATCH (n:Narrative {id: "yw-gilman-001"})-[:HAS_SCENE]->(s)-[:CONTAINS]->(e:Event)
MATCH (c:Character)-[:PARTICIPATES_IN]->(e)
RETURN DISTINCT c.name AS character, c.role AS role
```

The extractor finds **John** (multiple mentions → higher confidence) and
the narrator's references to her own agency.

---

## Step 4 — Export baseline GraphML

Export the graph before any transforms to establish a baseline tension map.

```bash
curl -sX POST http://localhost:8000/v1/render/yw-gilman-001 \
  -H "Content-Type: application/json" \
  -d '{"type": "graphml"}' \
  | jq -r '.content' > yw_baseline.graphml
```

Open `yw_baseline.graphml` in yEd (File → Open), then apply Layout →
Hierarchical. At this point, most edges are **grey** (#A0A0A0) or **steel
blue** (#4682B4) — structural containment and temporal sequence only.
No high-tension crimson edges appear yet because no mood, code, or causal
transforms have been applied.

---

## Step 5 — Apply a POV transform to Scene 1

The narrator is explicitly subjective and unreliable. Tag Scene 1 to reflect
that — internal focalization through the narrator, reliability ambiguous.

First, retrieve Scene 1's ID:

```bash
SCENE_1=$(curl -s http://localhost:8000/v1/narratives/yw-gilman-001 \
  | jq -r '.scenes[0].id // empty')

# Or query directly from the JSON render:
curl -sX POST http://localhost:8000/v1/render/yw-gilman-001 \
  -H "Content-Type: application/json" \
  -d '{"type":"json"}' \
  | jq -r '.content | fromjson | .narrative.scenes[0].id'
```

Apply the POV transform:

```bash
curl -X POST http://localhost:8000/v1/transforms/apply \
  -H "Content-Type: application/json" \
  -d "{
    \"scene_id\": \"$SCENE_1\",
    \"axis\": \"pov\",
    \"parameters\": {
      \"focalizer\": \"narrator\",
      \"distance\": \"internal\",
      \"reliability\": \"unreliable\"
    },
    \"operator\": \"analyst\"
  }"
```

The graph now has a `Perspective` node attached to Scene 1:
`focalizer=narrator, distance=internal, reliability=unreliable`.

---

## Step 6 — Apply mood across all four scenes (bulk transform)

The story escalates from mild unease to paranoid fixation. Apply a single
bulk mood transform that sets the baseline affective register across the
entire narrative, then refine per scene if needed.

```bash
curl -X POST http://localhost:8000/v1/transforms/apply-bulk \
  -H "Content-Type: application/json" \
  -d '{
    "narrative_id": "yw-gilman-001",
    "axis": "mood",
    "parameters": {
      "label": "dread",
      "valence": -0.75,
      "arousal": 0.6
    },
    "operator": "analyst"
  }'
```

Response:

```json
{
  "narrative_id": "yw-gilman-001",
  "applied_count": 4,
  "results": [
    { "scene_id": "s-…", "axis": "mood", "status": "accepted", … },
    { "scene_id": "s-…", "axis": "mood", "status": "accepted", … },
    { "scene_id": "s-…", "axis": "mood", "status": "accepted", … },
    { "scene_id": "s-…", "axis": "mood", "status": "accepted", … }
  ]
}
```

All four scenes now carry `MoodState { label: "dread", valence: -0.75,
arousal: 0.6 }`. The high-arousal negative mood will raise the tension score
on edges from these scenes.

Optionally, sharpen Scene 4 (the climax) further:

```bash
curl -X POST http://localhost:8000/v1/transforms/apply \
  -H "Content-Type: application/json" \
  -d "{
    \"scene_id\": \"$SCENE_4\",
    \"axis\": \"mood\",
    \"parameters\": {
      \"label\": \"paranoia\",
      \"valence\": -0.95,
      \"arousal\": 0.9
    },
    \"operator\": \"analyst\"
  }"
```

---

## Step 7 — Tag a key atom with a hermeneutic code

The sentence *"There are things in that paper that nobody knows but me, or
ever will"* is the pivot of the story's mystery. Tag it as `hermeneutic`
(+0.4 tension) to mark it as the central enigma.

Find the atom ID from the JSON render:

```bash
curl -sX POST http://localhost:8000/v1/render/yw-gilman-001 \
  -H "Content-Type: application/json" \
  -d '{"type":"json"}' \
  | jq -r '.content | fromjson | .narrative.scenes[].atoms[]
    | select(.text | contains("nobody knows but me"))
    | {id, text}'
```

Apply the code overlay:

```bash
curl -X POST http://localhost:8000/v1/transforms/apply \
  -H "Content-Type: application/json" \
  -d "{
    \"scene_id\": \"$SCENE_3\",
    \"axis\": \"code_overlay\",
    \"parameters\": {
      \"atom_id\": \"$ENIGMA_ATOM\",
      \"code\": \"hermeneutic\",
      \"label\": \"The secret knowledge — what does she see that others cannot?\"
    },
    \"operator\": \"analyst\"
  }"
```

---

## Step 8 — Revise an atom's prose text

The original sentence in Scene 4 reads:

> *"I wonder—I begin to think—I wish John would take me away from here!"*

For a closer third-person rewrite of this passage, revise the atom directly:

```bash
ATOM_ID="<atom-id-from-json-render>"

curl -X PATCH http://localhost:8000/v1/atoms/$ATOM_ID \
  -H "Content-Type: application/json" \
  -d '{
    "text": "She wondered, and then began to think, and then knew with certainty that she wanted to leave.",
    "operator": "editor",
    "reason": "shift from first-person journal to close third-person for comparison"
  }'
```

Response:

```json
{
  "atom_id": "atom-…",
  "revision_id": "rev-…",
  "text": "She wondered, and then began to think, and then knew with certainty that she wanted to leave."
}
```

The original text is preserved in the graph under `HAS_REVISION`. To inspect
the full revision chain:

```bash
curl http://localhost:8000/v1/atoms/$ATOM_ID/revisions
```

```json
{
  "atom_id": "atom-…",
  "revisions": [
    {
      "id": "rev-…",
      "text": "She wondered, and then began to think, and then knew with certainty that she wanted to leave.",
      "revised_at": "2026-04-26T14:32:00",
      "operator": "editor",
      "reason": "shift from first-person journal to close third-person for comparison"
    }
  ]
}
```

---

## Step 9 — Re-export GraphML and compare tension

```bash
curl -sX POST http://localhost:8000/v1/render/yw-gilman-001 \
  -H "Content-Type: application/json" \
  -d '{"type": "graphml"}' \
  | jq -r '.content' > yw_transformed.graphml
```

Open `yw_transformed.graphml` in yEd alongside the baseline. The changes are
immediately visible in the edge colors:

| Edge | Baseline | After transforms |
|------|----------|-----------------|
| Scene containment (HAS_SCENE) | Grey #A0A0A0 | Grey #A0A0A0 |
| Temporal sequence (PRECEDES) | Steel blue #4682B4 | Steel blue #4682B4 |
| Mood edges from scenes with `dread` | — | Orange #FF8C00 |
| Hermeneutic code atom → events | — | Crimson #DC143C |
| Scene 4 with `paranoia` mood | — | Dark red #8B0000 |

The escalation from Scene 1 to Scene 4 is now visible as a color gradient
from orange through crimson to dark red — the graph shows the story's tension
arc spatially.

---

## Step 10 — Export revised prose

Render the narrative back to Markdown with all transforms and the atom
revision applied:

```bash
curl -sX POST http://localhost:8000/v1/render/yw-gilman-001 \
  -H "Content-Type: application/json" \
  -d '{"type": "prose"}' \
  | jq -r '.content' > yw_revised.md
```

Output structure:

```markdown
# The Yellow Wallpaper

## The House

> POV: narrator (internal, unreliable) | Mood: dread

It is very seldom that mere ordinary people like John and myself secure
ancestral halls for the summer. A colonial mansion, a hereditary estate,
I would say a haunted house, and reach the height of romantic felicity—but
that would be asking too much of fate! Still I will proudly declare that
there is something queer about it.

…

## The Room

> Mood: dread

I don't like our room a bit. …

## The Pattern

> Mood: dread

I lie here on this great immovable bed—it is nailed down, I believe—and
follow that pattern about by the hour. …

## The Figure

> Mood: paranoia

Behind that outside pattern the dim shapes get clearer every day. …
She wondered, and then began to think, and then knew with certainty
that she wanted to leave.

At night in any kind of light, in twilight, candlelight, lamplight, and
worst of all by moonlight, it becomes bars! …
```

Key things to notice:

- Section headings come from `scene.summary` (the `##` headings in the source
  Markdown), not from scene sequence numbers.
- Scene 1 shows both POV and Mood context because both transforms were applied.
- Scenes 2–3 show only Mood context.
- Scene 4 shows the sharpened `paranoia` mood.
- The revised atom text (*"She wondered, and then began to think…"*) appears
  in Scene 4 in place of the original first-person phrasing. The original is
  still in the graph, reachable via `GET /v1/atoms/{id}/revisions`.

---

## Transform audit trail

Every operation is recorded. Query the full history for the narrative:

```cypher
MATCH (n:Narrative {id: "yw-gilman-001"})-[:HAS_SCENE]->(s:Scene)
MATCH (t:Transform)-[:APPLIED_TO]->(s)
RETURN s.summary AS scene,
       t.axis     AS axis,
       t.operator AS operator,
       t.applied_at AS when
ORDER BY t.applied_at ASC
```

| scene | axis | operator | when |
|-------|------|----------|------|
| The House | pov | analyst | 2026-04-26T14:00:… |
| The House | mood | analyst | 2026-04-26T14:01:… |
| The Room | mood | analyst | 2026-04-26T14:01:… |
| The Pattern | mood | analyst | 2026-04-26T14:01:… |
| The Figure | mood | analyst | 2026-04-26T14:01:… |
| The Pattern | code_overlay | analyst | 2026-04-26T14:02:… |
| The Figure | mood | analyst | 2026-04-26T14:03:… |

---

## Summary

| Step | What happened |
|------|--------------|
| Ingest with `format: "markdown"` | 4 scenes created from `##` headings; heading text stored as `scene.summary` |
| Neo4j review | Verified scene structure, atoms, characters |
| Baseline GraphML | Structural-only edges; low tension throughout |
| POV transform (Scene 1) | Internal, unreliable narrator tagged |
| Bulk mood transform | `dread` applied across all 4 scenes in one call |
| Scene 4 mood refinement | Sharpened to `paranoia` at the climax |
| Hermeneutic code overlay | Central enigma atom tagged; +0.4 tension |
| Atom revision | First-person sentence rewritten to close third-person non-destructively |
| Transformed GraphML | Tension gradient visible — orange → crimson → dark red |
| Prose render | Chapter headings restored; annotations visible; revised atom text in place |
