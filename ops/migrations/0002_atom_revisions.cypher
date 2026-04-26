// Migration 0002 — AtomRevision node constraints and indexes (idempotent)
// Apply with:
//   docker compose exec neo4j cypher-shell < ops/migrations/0002_atom_revisions.cypher

CREATE CONSTRAINT atom_revision_id IF NOT EXISTS
  FOR (r:AtomRevision) REQUIRE r.id IS UNIQUE;

CREATE INDEX atom_revision_atom_id IF NOT EXISTS
  FOR (r:AtomRevision) ON (r.atom_id);

CREATE INDEX atom_revision_revised_at IF NOT EXISTS
  FOR (r:AtomRevision) ON (r.revised_at);
