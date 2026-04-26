#!/usr/bin/env bash
# TNGS restore script — Community Edition offline load.
# See SRS §15.5 for the full Backup and Restore Runbook.
#
# Usage:
#   ./ops/scripts/restore.sh BACKUP_DIR [RESTORE_DATA_DIR]
#
# BACKUP_DIR must contain a neo4j.dump file.
# RESTORE_DATA_DIR defaults to a timestamped directory for isolation.

set -euo pipefail

BACKUP_DIR="${1:?Usage: restore.sh BACKUP_DIR [RESTORE_DATA_DIR]}"
RESTORE_DATA="${2:-./restore-data-$(date +%Y%m%d_%H%M%S)}"
NEO4J_IMAGE="${NEO4J_ADMIN_IMAGE:-neo4j/neo4j-admin:2026.04.0}"

echo "[restore] Loading dump from $BACKUP_DIR into $RESTORE_DATA"
mkdir -p "$RESTORE_DATA"

docker run --rm \
  --volume="$RESTORE_DATA:/data" \
  --volume="$BACKUP_DIR:/backups" \
  "$NEO4J_IMAGE" \
  neo4j-admin database load neo4j --from-path=/backups

echo "[restore] Dump loaded. Verifying node counts..."
docker compose exec neo4j cypher-shell \
  -u neo4j \
  "MATCH (n) RETURN labels(n) AS label, count(n) AS count ORDER BY count DESC"

echo "[restore] Restore complete. Data directory: $RESTORE_DATA"
echo "[restore] To use as live data, stop neo4j, swap volumes, and restart."
