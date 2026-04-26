"""Graph repository — single point of contact with Neo4j.

All Cypher queries are executed here and nowhere else.  Service-layer code
receives domain objects; it never sees raw driver records.  This enforces
the boundary described in SRS §3.2 (Diagram 2).

Connection lifecycle
--------------------
The repository accepts a ``neo4j.Driver`` instance.  The driver manages
its own connection pool; one driver per process is the correct pattern.
The ``close()`` method must be called at application shutdown to release
pool resources.

Transaction discipline
----------------------
* **Writes** — all multi-statement writes use managed transactions
  (``session.execute_write``) so that failures roll back atomically.
* **Small reads** — bounded single-record reads use ``execute_query``.
* **Streaming reads** — render queries that may return many rows use
  ``session.run`` with lazy cursor iteration.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from neo4j import Driver, GraphDatabase

from tng.config import Settings
from tng.domain.enums import NarrativeStatus, TransformAxis
from tng.domain.models import (
    Atom,
    Character,
    CodeTag,
    Chronotope,
    Event,
    EventRelation,
    GenreProfile,
    GraphState,
    MoodState,
    Narrative,
    Pattern,
    PatternInstance,
    Perspective,
    Scene,
    Transform,
)
from tng.repository import cypher_queries as Q

logger = logging.getLogger(__name__)


def _dt_str(dt: datetime) -> str:
    """Serialise datetime to ISO-8601 string for Neo4j parameters."""
    return dt.isoformat()


class GraphRepository:
    """Abstracts all Neo4j interactions for the TNGS application.

    :param driver: An authenticated ``neo4j.Driver`` instance.
    :param database: Name of the Neo4j database to target.
    """

    def __init__(self, driver: Driver, database: str = "neo4j") -> None:
        self._driver = driver
        self._db = database

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Release driver connection pool resources."""
        self._driver.close()

    # ── Health ────────────────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Return True when Neo4j is reachable and the database responds.

        :returns: ``True`` on success.
        :raises Exception: On Neo4j connectivity failure — callers decide how to
            handle it.
        """
        result = self._driver.execute_query(
            Q.HEALTH_PING, database_=self._db
        )
        return bool(result.records)

    # ── Schema bootstrap ──────────────────────────────────────────────────────

    def apply_schema(self) -> None:
        """Apply all constraints and indexes idempotently.

        Safe to call on every startup; uses ``IF NOT EXISTS`` guards.
        """
        with self._driver.session(database=self._db) as session:
            for stmt in Q.SCHEMA_CONSTRAINTS + Q.SCHEMA_INDEXES:
                session.run(stmt)
        logger.info("Schema constraints and indexes verified.")

    # ── Narrative ─────────────────────────────────────────────────────────────

    def save_narrative(self, narrative: Narrative) -> Narrative:
        """Persist or update a Narrative node.

        :param narrative: The domain Narrative to persist.
        :returns: The same narrative (unchanged — the graph write is
            idempotent via MERGE).
        """

        def _write(tx: Any) -> None:
            tx.run(
                Q.MERGE_NARRATIVE,
                id=narrative.id,
                title=narrative.title,
                status=narrative.status.value,
                source_ref=narrative.source_ref,
                created_at=_dt_str(narrative.created_at),
            )

        with self._driver.session(database=self._db) as session:
            session.execute_write(_write)
        logger.debug("Saved narrative %s", narrative.id)
        return narrative

    def get_narrative(self, narrative_id: str) -> Narrative | None:
        """Retrieve a Narrative by ID with all nested scenes and atoms.

        :param narrative_id: The narrative's unique identifier.
        :returns: A populated ``Narrative`` or ``None`` if not found.
        """
        records, _, _ = self._driver.execute_query(
            Q.GET_NARRATIVE, id=narrative_id, database_=self._db
        )
        if not records:
            return None
        node = records[0]["n"]
        narrative = Narrative(
            id=node["id"],
            title=node["title"],
            status=NarrativeStatus(node.get("status", "draft")),
            source_ref=node.get("source_ref", ""),
            created_at=_parse_dt(node.get("created_at")),
        )
        narrative.scenes = self._get_scenes(narrative_id)
        return narrative

    def update_narrative_status(
        self, narrative_id: str, status: NarrativeStatus
    ) -> None:
        """Update the status property on a Narrative node.

        :param narrative_id: Target narrative ID.
        :param status: New status value.
        """

        def _write(tx: Any) -> None:
            tx.run(
                Q.UPDATE_NARRATIVE_STATUS,
                id=narrative_id,
                status=status.value,
            )

        with self._driver.session(database=self._db) as session:
            session.execute_write(_write)

    def update_narrative_status_for_scene(
        self, scene_id: str, status: NarrativeStatus
    ) -> None:
        """Update the status of the Narrative that contains a given scene.

        :param scene_id: ID of a scene whose parent narrative should be updated.
        :param status: New status value.
        """

        def _write(tx: Any) -> None:
            tx.run(
                """
                MATCH (n:Narrative)-[:HAS_SCENE]->(s:Scene {id: $scene_id})
                SET n.status = $status
                """,
                scene_id=scene_id,
                status=status.value,
            )

        with self._driver.session(database=self._db) as session:
            session.execute_write(_write)

    def archive_narrative(self, narrative_id: str) -> bool:
        """Set a Narrative's status to archived.

        :param narrative_id: Target narrative ID.
        :returns: ``True`` if the narrative was found and archived.
        """

        def _write(tx: Any) -> Any:
            return tx.run(Q.ARCHIVE_NARRATIVE, id=narrative_id).single()

        with self._driver.session(database=self._db) as session:
            result = session.execute_write(_write)
        return result is not None

    # ── Scene ─────────────────────────────────────────────────────────────────

    def save_scene(self, scene: Scene, narrative_id: str) -> Scene:
        """Persist a Scene and link it to its parent Narrative.

        :param scene: The domain Scene to persist.
        :param narrative_id: The parent narrative's ID.
        :returns: The saved scene.
        """

        def _write(tx: Any) -> None:
            tx.run(
                Q.MERGE_SCENE,
                id=scene.id,
                sequence=scene.sequence,
                summary=scene.summary,
                narrative_id=narrative_id,
            )
            for atom in scene.atoms:
                self._save_atom_tx(tx, atom, scene.id)
            for event in scene.events:
                self._save_event_tx(tx, event, scene.id)
            for instance in scene.pattern_instances:
                self._save_pattern_instance_tx(tx, instance, scene.id)

        with self._driver.session(database=self._db) as session:
            session.execute_write(_write)
        return scene

    def _get_scenes(self, narrative_id: str) -> list[Scene]:
        records, _, _ = self._driver.execute_query(
            Q.GET_SCENES_FOR_NARRATIVE,
            narrative_id=narrative_id,
            database_=self._db,
        )
        scenes = []
        for rec in records:
            node = rec["s"]
            scene = Scene(
                id=node["id"],
                sequence=node.get("sequence", 1),
                summary=node.get("summary", ""),
            )
            scene.atoms = self._get_atoms(scene.id)
            scenes.append(scene)
        return scenes

    # ── Atom ──────────────────────────────────────────────────────────────────

    def get_scene_ids(self, narrative_id: str) -> list[str]:
        """Return scene IDs for a narrative in sequence order.

        :param narrative_id: The narrative's unique identifier.
        :returns: List of scene ID strings, ordered by sequence.
        """
        records, _, _ = self._driver.execute_query(
            Q.GET_SCENE_IDS_FOR_NARRATIVE,
            narrative_id=narrative_id,
            database_=self._db,
        )
        return [rec["scene_id"] for rec in records]

    def _save_atom_tx(self, tx: Any, atom: Atom, scene_id: str) -> None:
        tx.run(
            Q.MERGE_ATOM,
            id=atom.id,
            text=atom.text,
            kind=atom.kind.value,
            surface_order=atom.surface_order,
            confidence=atom.confidence,
            needs_review=atom.needs_review,
            scene_id=scene_id,
        )
        for tag in atom.code_tags:
            tx.run(
                Q.MERGE_CODE_TAG,
                id=tag.id,
                code=tag.code.value,
                label=tag.label,
                atom_id=atom.id,
            )

    def _get_atoms(self, scene_id: str) -> list[Atom]:
        records, _, _ = self._driver.execute_query(
            Q.GET_ATOMS_FOR_SCENE, scene_id=scene_id, database_=self._db
        )
        atoms = []
        for rec in records:
            node = rec["a"]
            from tng.domain.enums import AtomKind
            atoms.append(
                Atom(
                    id=node["id"],
                    text=rec["resolved_text"],
                    kind=AtomKind(node.get("kind", "descriptive")),
                    surface_order=node.get("surface_order", 0),
                    confidence=node.get("confidence", 1.0),
                    needs_review=node.get("needs_review", False),
                )
            )
        return atoms

    # ── Event ─────────────────────────────────────────────────────────────────

    def _save_event_tx(self, tx: Any, event: Event, scene_id: str) -> None:
        tx.run(
            Q.MERGE_EVENT,
            id=event.id,
            verb=event.verb,
            tense=event.tense,
            aspect=event.aspect,
            confidence=event.confidence,
            needs_review=event.needs_review,
            scene_id=scene_id,
        )
        for char in event.participants:
            tx.run(
                Q.MERGE_CHARACTER,
                id=char.id,
                name=char.name,
                role=char.role,
            )
            tx.run(
                Q.LINK_CHARACTER_TO_EVENT,
                character_id=char.id,
                event_id=event.id,
            )

    # ── Pattern ───────────────────────────────────────────────────────────────

    def save_pattern(self, pattern: Pattern) -> Pattern:
        """Persist a Pattern template.

        :param pattern: The pattern to save.
        :returns: The same pattern (unchanged).
        """

        def _write(tx: Any) -> None:
            tx.run(
                Q.MERGE_PATTERN,
                id=pattern.id,
                name=pattern.name,
                family=pattern.family,
                description=pattern.description,
            )

        with self._driver.session(database=self._db) as session:
            session.execute_write(_write)
        return pattern

    def get_pattern(self, pattern_id: str) -> Pattern | None:
        """Retrieve a single Pattern template by ID.

        :param pattern_id: The pattern's unique identifier.
        :returns: A ``Pattern`` or ``None`` if not found.
        """
        records, _, _ = self._driver.execute_query(
            Q.GET_PATTERN, id=pattern_id, database_=self._db
        )
        if not records:
            return None
        node = records[0]["p"]
        return Pattern(
            id=node["id"],
            name=node["name"],
            family=node["family"],
            description=node.get("description", ""),
        )

    def list_patterns(self, family: str | None = None) -> list[Pattern]:
        """List pattern templates, optionally filtered by family.

        :param family: If provided, only return patterns of this family.
        :returns: List of matching patterns.
        """
        records, _, _ = self._driver.execute_query(
            Q.LIST_PATTERNS, family=family, database_=self._db
        )
        return [
            Pattern(
                id=r["p"]["id"],
                name=r["p"]["name"],
                family=r["p"]["family"],
                description=r["p"].get("description", ""),
            )
            for r in records
        ]

    def _save_pattern_instance_tx(
        self, tx: Any, instance: PatternInstance, scene_id: str
    ) -> None:
        if instance.template is None:
            return
        tx.run(
            Q.MERGE_PATTERN_INSTANCE,
            id=instance.id,
            slot=instance.slot,
            confidence=instance.confidence,
            needs_review=instance.needs_review,
            scene_id=scene_id,
            pattern_id=instance.template.id,
        )
        for atom_id in instance.realized_atom_ids:
            tx.run(
                Q.LINK_INSTANCE_TO_ATOM,
                instance_id=instance.id,
                atom_id=atom_id,
            )
        for event_id in instance.realized_event_ids:
            tx.run(
                Q.LINK_INSTANCE_TO_EVENT,
                instance_id=instance.id,
                event_id=event_id,
            )

    def list_pattern_instances(self, narrative_id: str) -> list[dict[str, Any]]:
        """List all PatternInstances for a narrative with context.

        :param narrative_id: The narrative to query.
        :returns: List of dicts with instance, pattern, and scene_id.
        """
        records, _, _ = self._driver.execute_query(
            Q.LIST_PATTERN_INSTANCES,
            narrative_id=narrative_id,
            database_=self._db,
        )
        return [
            {
                "instance_id": r["pi"]["id"],
                "slot": r["pi"]["slot"],
                "confidence": r["pi"]["confidence"],
                "pattern_id": r["p"]["id"],
                "pattern_name": r["p"]["name"],
                "pattern_family": r["p"]["family"],
                "scene_id": r["scene_id"],
            }
            for r in records
        ]

    # ── Transforms ────────────────────────────────────────────────────────────

    def apply_transform(self, transform: Transform) -> Transform:
        """Dispatch and persist a transformation on a scene.

        Routes to the appropriate axis-specific Cypher query.  The old
        state node is detached (not deleted) and the new state node is
        created in a single managed transaction.

        :param transform: Fully populated Transform domain object.
        :returns: The same transform (with ``produced_id`` set if applicable).
        :raises ValueError: For unknown or unsupported axis values.
        """
        axis = transform.axis
        dispatch = {
            TransformAxis.POV: self._apply_pov,
            TransformAxis.MOOD: self._apply_mood,
            TransformAxis.GENRE: self._apply_genre,
            TransformAxis.CHRONOTOPE: self._apply_chronotope,
            TransformAxis.RELIABILITY: self._apply_reliability,
            TransformAxis.CODE_OVERLAY: self._apply_code_overlay,
        }
        handler = dispatch.get(axis)
        if handler is None:
            raise ValueError(f"Unknown transform axis: {axis}")
        return handler(transform)

    def _apply_pov(self, transform: Transform) -> Transform:
        p = transform.parameters
        perspective_id = f"pov-{transform.id}"

        def _write(tx: Any) -> None:
            tx.run(
                Q.APPLY_POV_TRANSFORM,
                scene_id=transform.scene_id,
                perspective_id=perspective_id,
                focalizer=p.get("focalizer", ""),
                distance=p.get("distance", "zero"),
                reliability=p.get("reliability", "reliable"),
                transform_id=transform.id,
                operator=transform.operator,
                applied_at=_dt_str(transform.applied_at),
                parameters=json.dumps(p),
            )

        with self._driver.session(database=self._db) as session:
            session.execute_write(_write)
        transform.produced_id = perspective_id
        return transform

    def _apply_mood(self, transform: Transform) -> Transform:
        p = transform.parameters
        mood_id = f"mood-{transform.id}"

        def _write(tx: Any) -> None:
            tx.run(
                Q.APPLY_MOOD_TRANSFORM,
                scene_id=transform.scene_id,
                mood_id=mood_id,
                label=p.get("label", "neutral"),
                valence=float(p.get("valence", 0.0)),
                arousal=float(p.get("arousal", 0.5)),
                transform_id=transform.id,
                operator=transform.operator,
                applied_at=_dt_str(transform.applied_at),
                parameters=json.dumps(p),
            )

        with self._driver.session(database=self._db) as session:
            session.execute_write(_write)
        transform.produced_id = mood_id
        return transform

    def _apply_genre(self, transform: Transform) -> Transform:
        p = transform.parameters
        genre_id = f"genre-{transform.id}"

        def _write(tx: Any) -> None:
            tx.run(
                Q.APPLY_GENRE_TRANSFORM,
                scene_id=transform.scene_id,
                genre_id=genre_id,
                name=p.get("name", ""),
                conventions=json.dumps(p.get("conventions", [])),
                transform_id=transform.id,
                operator=transform.operator,
                applied_at=_dt_str(transform.applied_at),
                parameters=json.dumps(p),
            )

        with self._driver.session(database=self._db) as session:
            session.execute_write(_write)
        transform.produced_id = genre_id
        return transform

    def _apply_chronotope(self, transform: Transform) -> Transform:
        p = transform.parameters
        chronotope_id = f"ct-{transform.id}"

        def _write(tx: Any) -> None:
            tx.run(
                Q.APPLY_CHRONOTOPE_TRANSFORM,
                scene_id=transform.scene_id,
                chronotope_id=chronotope_id,
                time_mode=p.get("time_mode", "linear"),
                space_mode=p.get("space_mode", "bounded"),
                transform_id=transform.id,
                operator=transform.operator,
                applied_at=_dt_str(transform.applied_at),
                parameters=json.dumps(p),
            )

        with self._driver.session(database=self._db) as session:
            session.execute_write(_write)
        transform.produced_id = chronotope_id
        return transform

    def _apply_reliability(self, transform: Transform) -> Transform:
        p = transform.parameters
        perspective_id = f"pov-rel-{transform.id}"

        def _write(tx: Any) -> None:
            tx.run(
                Q.APPLY_RELIABILITY_TRANSFORM,
                scene_id=transform.scene_id,
                perspective_id=perspective_id,
                reliability=p.get("reliability", "reliable"),
                transform_id=transform.id,
                operator=transform.operator,
                applied_at=_dt_str(transform.applied_at),
                parameters=json.dumps(p),
            )

        with self._driver.session(database=self._db) as session:
            session.execute_write(_write)
        transform.produced_id = perspective_id
        return transform

    def _apply_code_overlay(self, transform: Transform) -> Transform:
        p = transform.parameters
        tag_id = f"tag-{transform.id}"

        def _write(tx: Any) -> None:
            tx.run(
                Q.APPLY_CODE_OVERLAY_TRANSFORM,
                tag_id=tag_id,
                code=p.get("code", "semic"),
                label=p.get("label", ""),
                atom_id=p.get("atom_id", ""),
                transform_id=transform.id,
                operator=transform.operator,
                applied_at=_dt_str(transform.applied_at),
                parameters=json.dumps(p),
            )

        with self._driver.session(database=self._db) as session:
            session.execute_write(_write)
        transform.produced_id = tag_id
        return transform

    def get_transform(self, transform_id: str) -> dict[str, Any] | None:
        """Retrieve a Transform audit record by ID.

        :param transform_id: The transform's unique identifier.
        :returns: A dict with transform details or ``None`` if not found.
        """
        records, _, _ = self._driver.execute_query(
            Q.GET_TRANSFORM, id=transform_id, database_=self._db
        )
        if not records:
            return None
        r = records[0]
        return {
            "id": transform_id,
            "scene_id": r.get("scene_id"),
            "produced_type": r.get("produced_type"),
            "produced_id": r.get("produced_id"),
        }

    def get_transform_history(self, scene_id: str) -> list[dict[str, Any]]:
        """Return the ordered transformation history for a scene.

        :param scene_id: The scene to query.
        :returns: List of transform dicts ordered by applied_at ASC.
        """
        records, _, _ = self._driver.execute_query(
            Q.GET_TRANSFORM_HISTORY, scene_id=scene_id, database_=self._db
        )
        return [dict(r) for r in records]

    # ── Render support ────────────────────────────────────────────────────────

    def get_atoms_with_context(self, narrative_id: str) -> list[dict[str, Any]]:
        """Fetch atoms in surface order with their current scene context.

        Used by the prose renderer.

        :param narrative_id: The narrative to render.
        :returns: Row dicts with atom text, scene metadata, and perspective/mood.
        """
        records, _, _ = self._driver.execute_query(
            Q.GET_ATOMS_WITH_CONTEXT,
            narrative_id=narrative_id,
            database_=self._db,
        )
        return [dict(r) for r in records]

    def get_graph_state(self, narrative_id: str) -> GraphState | None:
        """Return a complete in-memory snapshot of a narrative's graph state.

        :param narrative_id: The narrative to snapshot.
        :returns: A ``GraphState`` or ``None`` if the narrative doesn't exist.
        """
        narrative = self.get_narrative(narrative_id)
        if narrative is None:
            return None
        transforms_raw = []
        for scene in narrative.scenes:
            transforms_raw.extend(self.get_transform_history(scene.id))

        transforms = [
            Transform(
                id=r["id"],
                axis=TransformAxis(r["axis"]),
                operator=r.get("operator", "system"),
                applied_at=_parse_dt(r.get("applied_at")),
                parameters=json.loads(r.get("parameters") or "{}"),
                scene_id=r.get("scene_id", ""),
                produced_id=r.get("produced_id", ""),
            )
            for r in transforms_raw
        ]
        event_relations = self.get_event_relations(narrative_id)
        return GraphState(
            narrative=narrative,
            transforms=transforms,
            event_relations=event_relations,
        )

    # ── Atom revisions ────────────────────────────────────────────────────────

    def revise_atom(
        self,
        atom_id: str,
        revision_id: str,
        text: str,
        revised_at: datetime,
        operator: str,
        reason: str,
    ) -> bool:
        """Create an AtomRevision node and re-point CURRENT_REVISION.

        The old CURRENT_REVISION edge is detached (not deleted) and a
        SUPERSEDES edge is added from the new revision to the old one.

        :param atom_id: The target Atom's ID.
        :param revision_id: Pre-generated ID for the new AtomRevision node.
        :param text: Revised prose text.
        :param revised_at: UTC timestamp.
        :param operator: Identifier of the requesting user/system.
        :param reason: Optional reason for the change.
        :returns: ``True`` if the atom was found and revised.
        """

        def _write(tx: Any) -> Any:
            return tx.run(
                Q.CREATE_ATOM_REVISION,
                atom_id=atom_id,
                revision_id=revision_id,
                text=text,
                revised_at=_dt_str(revised_at),
                operator=operator,
                reason=reason,
            ).single()

        with self._driver.session(database=self._db) as session:
            result = session.execute_write(_write)
        return result is not None

    def get_atom_revisions(self, atom_id: str) -> list[dict[str, Any]]:
        """Return all AtomRevision nodes for an atom, oldest first.

        :param atom_id: The target Atom's ID.
        :returns: List of revision dicts with ``id``, ``text``, ``revised_at``,
            ``operator``, and ``reason`` keys.
        """
        records, _, _ = self._driver.execute_query(
            Q.GET_ATOM_REVISIONS, atom_id=atom_id, database_=self._db
        )
        return [
            {
                "id": rec["r"]["id"],
                "atom_id": rec["r"]["atom_id"],
                "text": rec["r"]["text"],
                "revised_at": rec["r"]["revised_at"],
                "operator": rec["r"].get("operator", "system"),
                "reason": rec["r"].get("reason", ""),
            }
            for rec in records
        ]

    def get_event_relations(self, narrative_id: str) -> list[EventRelation]:
        """Fetch all inter-event causal and temporal relationships.

        Returns ``CAUSES``, ``ENABLES``, ``PREVENTS``, and ``PRECEDES``
        edges between events within the narrative's scenes.  Used by the
        GraphML renderer to draw and tension-score causal graph structure.

        :param narrative_id: The narrative to query.
        :returns: List of ``EventRelation`` objects.
        """
        records, _, _ = self._driver.execute_query(
            Q.GET_EVENT_RELATIONS,
            narrative_id=narrative_id,
            database_=self._db,
        )
        return [
            EventRelation(
                source_id=r["source_id"],
                target_id=r["target_id"],
                relation_type=r["relation_type"],
            )
            for r in records
        ]


# ── Factory ───────────────────────────────────────────────────────────────────


def create_driver(settings: Settings) -> Driver:
    """Create and return an authenticated Neo4j driver.

    :param settings: Application settings containing Neo4j URI and credentials.
    :returns: A connected ``neo4j.Driver`` instance.
    """
    return GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )


def _parse_dt(value: Any) -> datetime:
    """Parse a datetime value from a Neo4j result field.

    :param value: Raw value from a Neo4j record (may be a Neo4j DateTime,
        ISO string, or None).
    :returns: A Python ``datetime`` (UTC-naive).
    """
    if value is None:
        return datetime.utcnow()
    if isinstance(value, datetime):
        return value
    if hasattr(value, "to_native"):
        return value.to_native()
    return datetime.fromisoformat(str(value))
