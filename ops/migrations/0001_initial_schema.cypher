// TNGS Migration 0001 — Initial schema
// All statements use IF NOT EXISTS guards; this script is fully idempotent.
// Apply: docker compose exec neo4j cypher-shell < ops/migrations/0001_initial_schema.cypher

// ── Constraints ────────────────────────────────────────────────────────────
CREATE CONSTRAINT narrative_id IF NOT EXISTS
FOR (n:Narrative) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT scene_id IF NOT EXISTS
FOR (s:Scene) REQUIRE s.id IS UNIQUE;

CREATE CONSTRAINT atom_id IF NOT EXISTS
FOR (a:Atom) REQUIRE a.id IS UNIQUE;

CREATE CONSTRAINT event_id IF NOT EXISTS
FOR (e:Event) REQUIRE e.id IS UNIQUE;

CREATE CONSTRAINT character_id IF NOT EXISTS
FOR (c:Character) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT pattern_id IF NOT EXISTS
FOR (p:Pattern) REQUIRE p.id IS UNIQUE;

CREATE CONSTRAINT pattern_instance_id IF NOT EXISTS
FOR (pi:PatternInstance) REQUIRE pi.id IS UNIQUE;

CREATE CONSTRAINT perspective_id IF NOT EXISTS
FOR (pv:Perspective) REQUIRE pv.id IS UNIQUE;

CREATE CONSTRAINT mood_state_id IF NOT EXISTS
FOR (m:MoodState) REQUIRE m.id IS UNIQUE;

CREATE CONSTRAINT genre_profile_id IF NOT EXISTS
FOR (g:GenreProfile) REQUIRE g.id IS UNIQUE;

CREATE CONSTRAINT chronotope_id IF NOT EXISTS
FOR (ch:Chronotope) REQUIRE ch.id IS UNIQUE;

CREATE CONSTRAINT code_tag_id IF NOT EXISTS
FOR (ct:CodeTag) REQUIRE ct.id IS UNIQUE;

CREATE CONSTRAINT transform_id IF NOT EXISTS
FOR (t:Transform) REQUIRE t.id IS UNIQUE;

// ── Indexes ──────────────────────────────────────��──────────────────────────
CREATE INDEX scene_sequence IF NOT EXISTS
FOR (s:Scene) ON (s.sequence);

CREATE INDEX atom_kind IF NOT EXISTS
FOR (a:Atom) ON (a.kind);

CREATE INDEX pattern_family IF NOT EXISTS
FOR (p:Pattern) ON (p.family);

CREATE INDEX transform_axis IF NOT EXISTS
FOR (t:Transform) ON (t.axis);

CREATE INDEX transform_applied_at IF NOT EXISTS
FOR (t:Transform) ON (t.applied_at);

CREATE INDEX narrative_status IF NOT EXISTS
FOR (n:Narrative) ON (n.status);

// ── Seed: pattern template library ──────────────────��──────────────────────
MERGE (p1:Pattern {id: "pattern.gift_exchange"})
SET p1.name        = "Gift Exchange",
    p1.family      = "ritual",
    p1.description = "A subject gives an object to another party under socially coded conditions";

MERGE (p2:Pattern {id: "pattern.threshold_crossing"})
SET p2.name        = "Threshold Crossing",
    p2.family      = "transition",
    p2.description = "A character crosses a meaningful physical or symbolic boundary";

MERGE (p3:Pattern {id: "pattern.revelation"})
SET p3.name        = "Revelation",
    p3.family      = "revelation",
    p3.description = "Hidden information is disclosed to a character or the reader";

MERGE (p4:Pattern {id: "pattern.conflict"})
SET p4.name        = "Conflict",
    p4.family      = "conflict",
    p4.description = "An antagonistic encounter between two or more agents";
