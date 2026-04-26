#!/usr/bin/env bash
# TNGS backup script — Community Edition offline dump.
# See SRS §15.5 for the full Backup and Restore Runbook.
#
# Usage:
#   ./ops/scripts/backup.sh [BACKUP_DIR]
#
# Defaults BACKUP_DIR to ./backups/$(date +%Y%m%d_%H%M%S)

set -euo pipefail

BACKUP_DIR="${1:-./backups/$(date +%Y%m%d_%H%M%S)}"
NEO4J_IMAGE="${NEO4J_ADMIN_IMAGE:-neo4j/neo4j-admin:2026.04.0}"
DATA_DIR="${DATA_DIR:-$PWD/ops/neo4j/data}"

echo "[backup] Stopping app container to prevent writes during dump..."
docker compose stop app

mkdir -p "$BACKUP_DIR"

echo "[backup] Running neo4j-admin database dump → $BACKUP_DIR"
docker run --rm \
  --volume="$DATA_DIR:/data" \
  --volume="$BACKUP_DIR:/backups" \
  "$NEO4J_IMAGE" \
  neo4j-admin database dump neo4j --to-path=/backups

echo "[backup] Starting app container..."
docker compose start app

echo "[backup] Done. Dump written to $BACKUP_DIR"
