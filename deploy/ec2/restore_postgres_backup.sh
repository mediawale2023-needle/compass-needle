#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  restore_postgres_backup.sh --source <s3://...sql.gz|/path/to/file.sql.gz> --target-db <db_name>

Notes:
  - Reads container/db connection config from /opt/compass-needle/backup.env
  - Restores into the specified target DB
  - Creates the target DB if it does not already exist
EOF
}

BACKUP_ENV_PATH="${BACKUP_ENV_PATH:-/opt/compass-needle/backup.env}"
if [[ ! -f "$BACKUP_ENV_PATH" ]]; then
  echo "backup env file not found at $BACKUP_ENV_PATH" >&2
  exit 1
fi

source_path=""
target_db=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source)
      source_path="${2:-}"
      shift 2
      ;;
    --target-db)
      target_db="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$source_path" || -z "$target_db" ]]; then
  usage
  exit 1
fi

if [[ ! "$target_db" =~ ^[A-Za-z0-9_]+$ ]]; then
  echo "target database name must contain only letters, numbers, and underscores" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$BACKUP_ENV_PATH"
set +a

COMPOSE_FILE="${COMPOSE_FILE:-/opt/compass-needle/deploy/ec2/docker-compose.yml}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
AWS_REGION="${AWS_REGION:-ap-south-1}"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

local_backup_path="${tmp_dir}/restore.sql.gz"

if [[ "$source_path" == s3://* ]]; then
  export AWS_REGION
  aws s3 cp "$source_path" "$local_backup_path"
else
  cp "$source_path" "$local_backup_path"
fi

create_db_command=$(cat <<EOF
export PGPASSWORD="\${POSTGRES_PASSWORD}"
if ! psql -U "\${POSTGRES_USER}" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '${target_db}'" | grep -q 1; then
  createdb -U "\${POSTGRES_USER}" "${target_db}"
fi
EOF
)

docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" sh -lc "$create_db_command"

restore_command=$(cat <<EOF
export PGPASSWORD="\${POSTGRES_PASSWORD}"
psql -U "\${POSTGRES_USER}" -d "${target_db}"
EOF
)

gzip -dc "$local_backup_path" | docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" sh -lc "$restore_command"

echo "restore completed into database ${target_db}"
