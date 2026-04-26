"""Cypher query constants for the TNGS graph repository.

Every production Cypher query is defined as a named constant here so that:

* Query strings are never constructed by string interpolation (mitigating
  Cypher injection).
* All parameterised queries are testable in isolation.
* The query surface area is auditable from a single file.

Parameters are always passed as driver parameters (``$name`` placeholders),
never embedded in the query strings themselves.
"""

# ── Health ──────────────────────────────────────────────────────────────────

HEALTH_PING = "RETURN 1 AS ok"

# ── Schema bootstrap (idempotent) ────────────────────────────────────────────

SCHEMA_CONSTRAINTS = [
    "CREATE CONSTRAINT narrative_id IF NOT EXISTS FOR (n:Narrative) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT scene_id IF NOT EXISTS FOR (s:Scene) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT atom_id IF NOT EXISTS FOR (a:Atom) REQUIRE a.id IS UNIQUE",
    "CREATE CONSTRAINT event_id IF NOT EXISTS FOR (e:Event) REQUIRE e.id IS UNIQUE",
    "CREATE CONSTRAINT character_id IF NOT EXISTS FOR (c:Character) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT pattern_id IF NOT EXISTS FOR (p:Pattern) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT pattern_instance_id IF NOT EXISTS FOR (pi:PatternInstance) REQUIRE pi.id IS UNIQUE",
    "CREATE CONSTRAINT perspective_id IF NOT EXISTS FOR (pv:Perspective) REQUIRE pv.id IS UNIQUE",
    "CREATE CONSTRAINT mood_state_id IF NOT EXISTS FOR (m:MoodState) REQUIRE m.id IS UNIQUE",
    "CREATE CONSTRAINT genre_profile_id IF NOT EXISTS FOR (g:GenreProfile) REQUIRE g.id IS UNIQUE",
    "CREATE CONSTRAINT chronotope_id IF NOT EXISTS FOR (ch:Chronotope) REQUIRE ch.id IS UNIQUE",
    "CREATE CONSTRAINT code_tag_id IF NOT EXISTS FOR (ct:CodeTag) REQUIRE ct.id IS UNIQUE",
    "CREATE CONSTRAINT transform_id IF NOT EXISTS FOR (t:Transform) REQUIRE t.id IS UNIQUE",
]

SCHEMA_INDEXES = [
    "CREATE INDEX scene_sequence IF NOT EXISTS FOR (s:Scene) ON (s.sequence)",
    "CREATE INDEX atom_kind IF NOT EXISTS FOR (a:Atom) ON (a.kind)",
    "CREATE INDEX pattern_family IF NOT EXISTS FOR (p:Pattern) ON (p.family)",
    "CREATE INDEX transform_axis IF NOT EXISTS FOR (t:Transform) ON (t.axis)",
    "CREATE INDEX transform_applied_at IF NOT EXISTS FOR (t:Transform) ON (t.applied_at)",
    "CREATE INDEX narrative_status IF NOT EXISTS FOR (n:Narrative) ON (n.status)",
]

# ── Narrative CRUD ────────────────────────────────────────────────────────────

MERGE_NARRATIVE = """
MERGE (n:Narrative {id: $id})
SET n.title      = $title,
    n.status     = $status,
    n.source_ref = $source_ref,
    n.created_at = $created_at
RETURN n
"""

GET_NARRATIVE = """
MATCH (n:Narrative {id: $id})
RETURN n
"""

LIST_NARRATIVES = """
MATCH (n:Narrative)
RETURN n
ORDER BY n.created_at DESC
"""

ARCHIVE_NARRATIVE = """
MATCH (n:Narrative {id: $id})
SET n.status = 'archived'
RETURN n
"""

UPDATE_NARRATIVE_STATUS = """
MATCH (n:Narrative {id: $id})
SET n.status = $status
RETURN n
"""

# ── Scene CRUD ────────────────────────────────────────────────────────────────

MERGE_SCENE = """
MERGE (s:Scene {id: $id})
SET s.sequence = $sequence,
    s.summary  = $summary
WITH s
MATCH (n:Narrative {id: $narrative_id})
MERGE (n)-[:HAS_SCENE]->(s)
RETURN s
"""

GET_SCENES_FOR_NARRATIVE = """
MATCH (n:Narrative {id: $narrative_id})-[:HAS_SCENE]->(s:Scene)
RETURN s
ORDER BY s.sequence
"""

# ── Atom CRUD ─────────────────────────────────────────────────────────────────

MERGE_ATOM = """
MERGE (a:Atom {id: $id})
SET a.text          = $text,
    a.kind          = $kind,
    a.surface_order = $surface_order,
    a.confidence    = $confidence,
    a.needs_review  = $needs_review
WITH a
MATCH (s:Scene {id: $scene_id})
MERGE (s)-[:CONTAINS]->(a)
RETURN a
"""

GET_ATOMS_FOR_SCENE = """
MATCH (s:Scene {id: $scene_id})-[:CONTAINS]->(a:Atom)
RETURN a
ORDER BY a.surface_order
"""

MERGE_CODE_TAG = """
MERGE (ct:CodeTag {id: $id})
SET ct.code  = $code,
    ct.label = $label
WITH ct
MATCH (a:Atom {id: $atom_id})
MERGE (a)-[:TAGGED_AS]->(ct)
RETURN ct
"""

# ── Event CRUD ────────────────────────────────────────────────────────────────

MERGE_EVENT = """
MERGE (e:Event {id: $id})
SET e.verb         = $verb,
    e.tense        = $tense,
    e.aspect       = $aspect,
    e.confidence   = $confidence,
    e.needs_review = $needs_review
WITH e
MATCH (s:Scene {id: $scene_id})
MERGE (s)-[:CONTAINS]->(e)
RETURN e
"""

MERGE_CHARACTER = """
MERGE (c:Character {id: $id})
SET c.name = $name,
    c.role = $role
RETURN c
"""

LINK_CHARACTER_TO_EVENT = """
MATCH (c:Character {id: $character_id})
MATCH (e:Event {id: $event_id})
MERGE (c)-[:PARTICIPATES_IN]->(e)
"""

# ── Pattern CRUD ──────────────────────────────────────────────────────────────

MERGE_PATTERN = """
MERGE (p:Pattern {id: $id})
SET p.name        = $name,
    p.family      = $family,
    p.description = $description
RETURN p
"""

GET_PATTERN = """
MATCH (p:Pattern {id: $id})
RETURN p
"""

LIST_PATTERNS = """
MATCH (p:Pattern)
WHERE ($family IS NULL OR p.family = $family)
RETURN p
ORDER BY p.family, p.name
"""

MERGE_PATTERN_INSTANCE = """
MERGE (pi:PatternInstance {id: $id})
SET pi.slot        = $slot,
    pi.confidence  = $confidence,
    pi.needs_review = $needs_review
WITH pi
MATCH (s:Scene {id: $scene_id})
MERGE (s)-[:CONTAINS]->(pi)
WITH pi
MATCH (p:Pattern {id: $pattern_id})
MERGE (pi)-[:INSTANCE_OF]->(p)
RETURN pi
"""

LINK_INSTANCE_TO_ATOM = """
MATCH (pi:PatternInstance {id: $instance_id})
MATCH (a:Atom {id: $atom_id})
MERGE (pi)-[:REALIZES]->(a)
"""

LINK_INSTANCE_TO_EVENT = """
MATCH (pi:PatternInstance {id: $instance_id})
MATCH (e:Event {id: $event_id})
MERGE (pi)-[:REALIZES]->(e)
"""

LIST_PATTERN_INSTANCES = """
MATCH (pi:PatternInstance)-[:INSTANCE_OF]->(p:Pattern)
MATCH (s:Scene)-[:CONTAINS]->(pi)
MATCH (n:Narrative)-[:HAS_SCENE]->(s)
WHERE n.id = $narrative_id
RETURN pi, p, s.id AS scene_id
ORDER BY pi.confidence DESC
"""

# ── Transform operations ──────────────────────────────────────────────────────

APPLY_POV_TRANSFORM = """
MATCH (s:Scene {id: $scene_id})
OPTIONAL MATCH (s)-[old:CURRENT_PERSPECTIVE]->(:Perspective)
DELETE old
WITH s
MERGE (pov:Perspective {id: $perspective_id})
SET pov.focalizer   = $focalizer,
    pov.distance    = $distance,
    pov.reliability = $reliability
MERGE (s)-[:CURRENT_PERSPECTIVE]->(pov)
WITH s, pov
MERGE (t:Transform {id: $transform_id})
SET t.axis       = 'pov',
    t.operator   = $operator,
    t.applied_at = $applied_at,
    t.parameters = $parameters
MERGE (t)-[:APPLIED_TO]->(s)
MERGE (t)-[:PRODUCED]->(pov)
RETURN t, pov
"""

APPLY_MOOD_TRANSFORM = """
MATCH (s:Scene {id: $scene_id})
OPTIONAL MATCH (s)-[old:CURRENT_MOOD]->(:MoodState)
DELETE old
WITH s
MERGE (m:MoodState {id: $mood_id})
SET m.label   = $label,
    m.valence = $valence,
    m.arousal = $arousal
MERGE (s)-[:CURRENT_MOOD]->(m)
WITH s, m
MERGE (t:Transform {id: $transform_id})
SET t.axis       = 'mood',
    t.operator   = $operator,
    t.applied_at = $applied_at,
    t.parameters = $parameters
MERGE (t)-[:APPLIED_TO]->(s)
MERGE (t)-[:PRODUCED]->(m)
RETURN t, m
"""

APPLY_GENRE_TRANSFORM = """
MATCH (s:Scene {id: $scene_id})
OPTIONAL MATCH (s)-[old:CURRENT_GENRE]->(:GenreProfile)
DELETE old
WITH s
MERGE (g:GenreProfile {id: $genre_id})
SET g.name        = $name,
    g.conventions = $conventions
MERGE (s)-[:CURRENT_GENRE]->(g)
WITH s, g
MERGE (t:Transform {id: $transform_id})
SET t.axis       = 'genre',
    t.operator   = $operator,
    t.applied_at = $applied_at,
    t.parameters = $parameters
MERGE (t)-[:APPLIED_TO]->(s)
MERGE (t)-[:PRODUCED]->(g)
RETURN t, g
"""

APPLY_CHRONOTOPE_TRANSFORM = """
MATCH (s:Scene {id: $scene_id})
OPTIONAL MATCH (s)-[old:IN_CHRONOTOPE]->(:Chronotope)
DELETE old
WITH s
MERGE (ch:Chronotope {id: $chronotope_id})
SET ch.time_mode  = $time_mode,
    ch.space_mode = $space_mode
MERGE (s)-[:IN_CHRONOTOPE]->(ch)
WITH s, ch
MERGE (t:Transform {id: $transform_id})
SET t.axis       = 'chronotope',
    t.operator   = $operator,
    t.applied_at = $applied_at,
    t.parameters = $parameters
MERGE (t)-[:APPLIED_TO]->(s)
MERGE (t)-[:PRODUCED]->(ch)
RETURN t, ch
"""

APPLY_RELIABILITY_TRANSFORM = """
MATCH (s:Scene {id: $scene_id})-[:CURRENT_PERSPECTIVE]->(pov:Perspective)
OPTIONAL MATCH (s)-[old:CURRENT_PERSPECTIVE]->(pov)
DELETE old
WITH s, pov
MERGE (new_pov:Perspective {id: $perspective_id})
SET new_pov.focalizer   = pov.focalizer,
    new_pov.distance    = pov.distance,
    new_pov.reliability = $reliability
MERGE (s)-[:CURRENT_PERSPECTIVE]->(new_pov)
WITH s, new_pov
MERGE (t:Transform {id: $transform_id})
SET t.axis       = 'reliability',
    t.operator   = $operator,
    t.applied_at = $applied_at,
    t.parameters = $parameters
MERGE (t)-[:APPLIED_TO]->(s)
MERGE (t)-[:PRODUCED]->(new_pov)
RETURN t, new_pov
"""

APPLY_CODE_OVERLAY_TRANSFORM = """
MERGE (ct:CodeTag {id: $tag_id})
SET ct.code  = $code,
    ct.label = $label
WITH ct
MATCH (a:Atom {id: $atom_id})
MERGE (a)-[:TAGGED_AS]->(ct)
WITH a, ct
MATCH (s:Scene)-[:CONTAINS]->(a)
MERGE (t:Transform {id: $transform_id})
SET t.axis       = 'code_overlay',
    t.operator   = $operator,
    t.applied_at = $applied_at,
    t.parameters = $parameters
MERGE (t)-[:APPLIED_TO]->(s)
MERGE (t)-[:PRODUCED]->(ct)
RETURN t, ct
"""

GET_TRANSFORM = """
MATCH (t:Transform {id: $id})
OPTIONAL MATCH (t)-[:APPLIED_TO]->(s)
OPTIONAL MATCH (t)-[:PRODUCED]->(produced)
RETURN t, s.id AS scene_id, labels(produced) AS produced_type, produced.id AS produced_id
"""

GET_TRANSFORM_HISTORY = """
MATCH (t:Transform)-[:APPLIED_TO]->(s:Scene {id: $scene_id})
OPTIONAL MATCH (t)-[:PRODUCED]->(produced)
RETURN t.id AS id,
       t.axis AS axis,
       t.operator AS operator,
       t.applied_at AS applied_at,
       t.parameters AS parameters,
       s.id AS scene_id,
       produced.id AS produced_id
ORDER BY t.applied_at ASC
"""

# ── Render queries ────────────────────────────────────────────────────────────

GET_ATOMS_WITH_CONTEXT = """
MATCH (n:Narrative {id: $narrative_id})-[:HAS_SCENE]->(s:Scene)
MATCH (s)-[:CONTAINS]->(a:Atom)
OPTIONAL MATCH (s)-[:CURRENT_PERSPECTIVE]->(pov:Perspective)
OPTIONAL MATCH (s)-[:CURRENT_MOOD]->(mood:MoodState)
OPTIONAL MATCH (s)-[:CURRENT_GENRE]->(genre:GenreProfile)
RETURN s.id AS scene_id,
       s.sequence AS scene_sequence,
       s.summary AS scene_summary,
       a.id AS atom_id,
       a.text AS atom_text,
       a.surface_order AS surface_order,
       a.kind AS atom_kind,
       pov.focalizer AS focalizer,
       pov.distance AS pov_distance,
       pov.reliability AS reliability,
       mood.label AS mood_label,
       mood.valence AS mood_valence,
       genre.name AS genre_name
ORDER BY s.sequence, a.surface_order
"""

GET_FULL_GRAPH_STATE = """
MATCH (n:Narrative {id: $narrative_id})
OPTIONAL MATCH (n)-[:HAS_SCENE]->(s:Scene)
OPTIONAL MATCH (s)-[:CONTAINS]->(a:Atom)
OPTIONAL MATCH (s)-[:CONTAINS]->(e:Event)
OPTIONAL MATCH (s)-[:CONTAINS]->(pi:PatternInstance)-[:INSTANCE_OF]->(p:Pattern)
OPTIONAL MATCH (s)-[:CURRENT_PERSPECTIVE]->(pov:Perspective)
OPTIONAL MATCH (s)-[:CURRENT_MOOD]->(mood:MoodState)
OPTIONAL MATCH (s)-[:CURRENT_GENRE]->(genre:GenreProfile)
OPTIONAL MATCH (s)-[:IN_CHRONOTOPE]->(ch:Chronotope)
RETURN n, s, a, e, pi, p, pov, mood, genre, ch
"""

GET_EVENT_RELATIONS = """
MATCH (n:Narrative {id: $narrative_id})-[:HAS_SCENE]->(s:Scene)
MATCH (s)-[:CONTAINS]->(src:Event)
MATCH (src)-[r:CAUSES|ENABLES|PREVENTS|PRECEDES]->(tgt:Event)
RETURN src.id AS source_id,
       tgt.id AS target_id,
       type(r)  AS relation_type
ORDER BY src.id
"""
