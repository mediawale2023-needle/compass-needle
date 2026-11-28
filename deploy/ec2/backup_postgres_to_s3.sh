#!/usr/bin/env bash
set -euo pipefail

BACKUP_ENV_PATH="${BACKUP_ENV_PATH:-/opt/compass-needle/backup.env}"

if [[ ! -f "$BACKUP_ENV_PATH" ]]; then
  echo "backup env file not found at $BACKUP_ENV_PATH" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$BACKUP_ENV_PATH"
set +a

: "${BACKUP_S3_URI:?BACKUP_S3_URI is required}"

COMPOSE_FILE="${COMPOSE_FILE:-/opt/compass-needle/deploy/ec2/docker-compose.yml}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
LOCAL_BACKUP_DIR="${LOCAL_BACKUP_DIR:-/opt/compass-needle/backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
AWS_REGION="${AWS_REGION:-ap-south-1}"
POSTGRES_DB_OVERRIDE="${POSTGRES_DB:-}"

mkdir -p "$LOCAL_BACKUP_DIR"
export AWS_REGION

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
hostname_slug="$(hostname -s | tr -cs '[:alnum:]-' '-')"
backup_basename="needle-postgres-${hostname_slug}-${timestamp}.sql.gz"
backup_path="${LOCAL_BACKUP_DIR}/${backup_basename}"
checksum_path="${backup_path}.sha256"

dump_command='db_name="${POSTGRES_DB}"'
if [[ -n "$POSTGRES_DB_OVERRIDE" ]]; then
  dump_command="db_name='${POSTGRES_DB_OVERRIDE}'"
fi
dump_command+=$'\n''export PGPASSWORD="${POSTGRES_PASSWORD}"'
# pg_dump is the last command, so its exit status is what `docker compose exec`
# returns. Compression happens on the host, inside this script's pipefail, so a
# failed dump can never produce a valid-looking .gz (it used to be piped to gzip
# inside the container's sh, which has no pipefail).
dump_command+=$'\n''exec pg_dump -U "${POSTGRES_USER}" -d "${db_name}" --no-owner --no-privileges'

partial_path="${backup_path}.partial"
trap 'rm -f "$partial_path"' EXIT
docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" sh -lc "$dump_command" | gzip -c > "$partial_path"

# Verify before publishing: archive intact, dump finished, not trivially small.
gzip -t "$partial_path"
if ! gzip -dc "$partial_path" | tail -n 5 | grep -q "PostgreSQL database dump complete"; then
  echo "backup verification failed: dump did not complete" >&2
  exit 1
fi
min_bytes="${BACKUP_MIN_BYTES:-10240}"
size_bytes="$(stat -c %s "$partial_path")"
if (( size_bytes < min_bytes )); then
  echo "backup verification failed: ${size_bytes} bytes is below the ${min_bytes}-byte minimum" >&2
  exit 1
fi
mv "$partial_path" "$backup_path"
sha256sum "$backup_path" > "$checksum_path"

s3_target="${BACKUP_S3_URI%/}/${hostname_slug}/${backup_basename}"
aws s3 cp "$backup_path" "$s3_target"
aws s3 cp "$checksum_path" "${s3_target}.sha256"

find "$LOCAL_BACKUP_DIR" -type f -name 'needle-postgres-*.sql.gz*' -mtime +"$BACKUP_RETENTION_DAYS" -delete

# Freshness marker for monitoring: a stale timestamp means backups stopped.
printf '%s %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$size_bytes" "$s3_target" > "${LOCAL_BACKUP_DIR}/last_successful_backup"

echo "backup uploaded to ${s3_target} (${size_bytes} bytes)"
