#!/usr/bin/env bash
# SmartClinic — nightly Postgres backup.
#
# - Dumps every application database to /var/backups/smartclinic
#   (format=custom, compressed, portable across Postgres minor versions).
# - Also anchors the Clinical hash-chain head into the backup set — an
#   auditor can later prove the dump was consistent with the live chain.
# - Rotates: keeps 14 dailies, 8 weeklies (Sunday), 6 monthlies (1st).
# - Optional: if BACKUP_S3_BUCKET is set in /opt/smartclinic/.env and the
#   `aws` CLI is installed, copies the dump off-host via `aws s3 cp`.
#
# Installed at /usr/local/bin/smartclinic-backup by ops/deploy/bootstrap.sh

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/smartclinic}"
APP_DIR="${APP_DIR:-/opt/smartclinic}"
ENV_FILE="$APP_DIR/.env"
RETAIN_DAYS="${RETAIN_DAYS:-14}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a; source "$ENV_FILE"; set +a
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DOW="$(date +%u)"      # 1..7  (7 = Sunday)
DOM="$(date +%d)"      # 01..31

mkdir -p "$BACKUP_DIR"/{daily,weekly,monthly}

# Databases to dump (one per bounded context + keycloak + saga)
DATABASES=(patient_identity scheduling clinical_write clinical_read pharmacy laboratory billing saga keycloak)

for db in "${DATABASES[@]}"; do
  OUT="$BACKUP_DIR/daily/${STAMP}_${db}.dump"
  echo "▸ dumping $db"
  docker exec -i smartclinic-postgres \
    pg_dump -U postgres -Fc --no-owner --no-acl "$db" > "$OUT"
  gzip -f "$OUT"
done

# Anchor the clinical hash-chain head
ANCHOR="$BACKUP_DIR/daily/${STAMP}_clinical_chain_heads.json"
docker exec -i smartclinic-postgres psql -U postgres -d clinical_write -AtX -c \
  "SELECT json_agg(json_build_object('aggregate_id', aggregate_id, 'head_hash', hash, 'version', aggregate_version))
   FROM (
     SELECT DISTINCT ON (aggregate_id) aggregate_id, hash, aggregate_version
     FROM events ORDER BY aggregate_id, aggregate_version DESC
   ) s;" > "$ANCHOR" 2>/dev/null || echo "[]" > "$ANCHOR"

# Promote on Sunday / 1st of month
if [[ "$DOW" == "7" ]]; then
  cp "$BACKUP_DIR"/daily/${STAMP}_*.gz "$BACKUP_DIR"/weekly/ 2>/dev/null || true
  cp "$ANCHOR"                           "$BACKUP_DIR"/weekly/ 2>/dev/null || true
fi
if [[ "$DOM" == "01" ]]; then
  cp "$BACKUP_DIR"/daily/${STAMP}_*.gz "$BACKUP_DIR"/monthly/ 2>/dev/null || true
  cp "$ANCHOR"                           "$BACKUP_DIR"/monthly/ 2>/dev/null || true
fi

# Rotation: dailies > 14 days, weeklies > 8 weeks, monthlies > 6 months
find "$BACKUP_DIR/daily"    -type f -mtime +"$RETAIN_DAYS"   -delete
find "$BACKUP_DIR/weekly"   -type f -mtime +56 -delete
find "$BACKUP_DIR/monthly"  -type f -mtime +186 -delete

# Off-host copy (optional)
if [[ -n "${BACKUP_S3_BUCKET:-}" ]] && command -v aws &>/dev/null; then
  echo "▸ copying daily dumps to s3://$BACKUP_S3_BUCKET/daily/"
  aws s3 sync "$BACKUP_DIR/daily" "s3://$BACKUP_S3_BUCKET/daily/" \
    --only-show-errors --storage-class STANDARD_IA
fi

echo "✓ backup complete · $(ls "$BACKUP_DIR/daily" | wc -l) files on-disk"
