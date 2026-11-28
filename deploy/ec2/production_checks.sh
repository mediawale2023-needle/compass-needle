#!/usr/bin/env bash
# Production readiness checks, run on the EC2 host by .github/workflows/production-checks.yml.
#
#   production_checks.sh config         Report production settings. Never prints a secret:
#                                       secrets are reported as set / not set (and, for the
#                                       JWT pair, whether they differ), never their values.
#   production_checks.sh restore-drill  Take a fresh verified backup, restore it into a
#                                       throwaway database on the same server, compare row
#                                       counts with production, drop the throwaway database
#                                       and append the result to backups/restore_drills.log.
#                                       Production data is only read.
set -euo pipefail

ROOT="${NEEDLE_ROOT:-/opt/compass-needle}"
APP="${ROOT}/app"
COMPOSE="${ROOT}/deploy/ec2/docker-compose.yml"
BACKUP_DIR="${ROOT}/backups"
dc() { docker compose -f "$COMPOSE" "$@"; }
pg() { dc exec -T postgres sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -X -q -tA -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" "$@"' psql "$@"; }

config() {
  echo "== Backend settings (values only for non-secret settings)"
  dc exec -T backend python - <<'PY'
import hashlib, os
def val(k, default="(not set)"):
    v = os.environ.get(k)
    return v if v not in (None, "") else default
def is_set(k):
    return "set" if os.environ.get(k) else "NOT SET"
jwt = os.environ.get("JWT_SECRET", "")
adm = os.environ.get("ADMIN_JWT_SECRET", "")
rows = [
    ("ENV", val("ENV")),
    ("JWT_SECRET", f"{is_set('JWT_SECRET')}, length {'>= 32' if len(jwt) >= 32 else '< 32 (TOO SHORT)'}"),
    ("ADMIN_JWT_SECRET", "NOT SET (falls back to JWT_SECRET)" if not adm else
        ("set, SAME AS JWT_SECRET" if hashlib.sha256(adm.encode()).digest() == hashlib.sha256(jwt.encode()).digest() else "set, differs from JWT_SECRET")),
    ("ALLOWED_ORIGINS", val("ALLOWED_ORIGINS")),
    ("ALLOWED_ORIGIN_REGEX", val("ALLOWED_ORIGIN_REGEX", r"(not set: default https://.*\.vercel\.app)")),
    ("CLASSIFICATION_MODE", val("CLASSIFICATION_MODE", "(not set: default shadow)")),
    ("GOVT_LIVE_AUTOMATION_ENABLED", val("GOVT_LIVE_AUTOMATION_ENABLED", "(not set: default true)")),
    ("GOVT_DELHI_MANUAL_REFERENCE_ENABLED", val("GOVT_DELHI_MANUAL_REFERENCE_ENABLED", "(not set: default false)")),
    ("WA_TEXT_BUFFER_ENABLED", val("WA_TEXT_BUFFER_ENABLED", "(not set: default on)")),
    ("SENTRY_DSN", is_set("SENTRY_DSN")),
    ("META_APP_SECRET", is_set("META_APP_SECRET")),
    ("META_ACCESS_TOKEN", is_set("META_ACCESS_TOKEN")),
    ("WHATSAPP_PHONE_NUMBER_ID", is_set("WHATSAPP_PHONE_NUMBER_ID")),
    ("OPENAI_API_KEY", is_set("OPENAI_API_KEY")),
    ("GEMINI_API_KEY", is_set("GEMINI_API_KEY")),
    ("WEB_CONCURRENCY", val("WEB_CONCURRENCY")),
]
for k, v in rows:
    print(f"{k:38} {v}")
PY
  echo
  echo "== Per-tenant classification overrides"
  local overrides
  overrides="$(pg -d "$(dc exec -T postgres printenv POSTGRES_DB | tr -d '\r')" -c \
    "SELECT 'tenant ' || key || ' = ' || value FROM tenant_overrides WHERE override_type = 'classification_mode' ORDER BY key" 2>/dev/null || true)"
  echo "${overrides:-(none: every tenant uses CLASSIFICATION_MODE)}"
  echo
  echo "== Backups"
  if [[ -f "${ROOT}/backup.env" ]]; then echo "backup.env: present"; else echo "backup.env: MISSING — nightly backups cannot run"; fi
  if [[ -f /etc/cron.d/compass-needle-postgres-backup ]]; then echo "backup cron: $(grep -v '^[A-Z]' /etc/cron.d/compass-needle-postgres-backup | grep -v '^$' | awk '{print $1, $2, $3, $4, $5}')"; else echo "backup cron: MISSING"; fi
  if [[ -f "${BACKUP_DIR}/last_successful_backup" ]]; then echo "last successful backup: $(cut -d' ' -f1,2 "${BACKUP_DIR}/last_successful_backup") bytes"; else echo "last successful backup: no record (marker added with the fixed backup script)"; fi
  if [[ -f /var/log/compass-needle-postgres-backup.log ]]; then echo "backup log tail:"; tail -n 5 /var/log/compass-needle-postgres-backup.log | sed 's/^/  /'; fi
  if [[ -f "${BACKUP_DIR}/restore_drills.log" ]]; then echo "restore drills:"; tail -n 3 "${BACKUP_DIR}/restore_drills.log" | sed 's/^/  /'; fi
  echo
  echo "== Deployed commit: $(git -C "$APP" rev-parse --short HEAD)"
}

restore_drill() {
  local prod_db drill_db started db_bytes free_bytes src status=PASS
  prod_db="$(dc exec -T postgres printenv POSTGRES_DB | tr -d '\r')"
  drill_db="restore_drill_$(date -u +%Y%m%d%H%M%S)"
  started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  db_bytes="$(pg -d "$prod_db" -c "SELECT pg_database_size(current_database())")"
  free_bytes="$(df --output=avail -B1 /var/lib/docker 2>/dev/null | tail -1 || df --output=avail -B1 / | tail -1)"
  echo "production database ${prod_db}: ${db_bytes} bytes; free disk ${free_bytes} bytes"
  if (( free_bytes < db_bytes * 3 + 1073741824 )); then
    echo "not enough free disk for a safe drill (need 3x database size + 1 GiB)" >&2
    exit 1
  fi

  echo "== 1. Fresh backup (verified, uploaded)"
  BACKUP_ENV_PATH="${ROOT}/backup.env" bash "${APP}/deploy/ec2/backup_postgres_to_s3.sh"
  src="$(cut -d' ' -f3 "${BACKUP_DIR}/last_successful_backup")"

  echo "== 2. Restore ${src} into ${drill_db}"
  trap 'pg -d postgres -c "DROP DATABASE IF EXISTS ${drill_db}" >/dev/null 2>&1 || true' EXIT
  local t0=$SECONDS
  BACKUP_ENV_PATH="${ROOT}/backup.env" bash "${APP}/deploy/ec2/restore_postgres_backup.sh" --source "$src" --target-db "$drill_db"
  local restore_seconds=$(( SECONDS - t0 ))

  echo "== 3. Compare row counts (counts only)"
  printf '%-26s %12s %12s\n' table production restored
  local tables="tenants users cases case_activity_log contacts letterbox wa_inbound_messages wa_outbound_messages govt_submission_log admin_audit_log"
  local summary=""
  for t in $tables; do
    local p r
    p="$(pg -d "$prod_db" -c "SELECT COUNT(*) FROM ${t}" 2>/dev/null || echo missing)"
    r="$(pg -d "$drill_db" -c "SELECT COUNT(*) FROM ${t}" 2>/dev/null || echo missing)"
    printf '%-26s %12s %12s\n' "$t" "$p" "$r"
    summary+="${t}=${r}/${p} "
    # Production may gain rows after the dump; the restore must never have more, or none.
    if [[ "$r" == missing || "$p" == missing ]]; then status=FAIL
    elif (( r > p )) || { (( p > 0 )) && (( r == 0 )); }; then status=FAIL
    fi
  done
  local tables_prod tables_drill
  tables_prod="$(pg -d "$prod_db" -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")"
  tables_drill="$(pg -d "$drill_db" -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")"
  echo "public tables: production ${tables_prod}, restored ${tables_drill}"
  [[ "$tables_prod" == "$tables_drill" ]] || status=FAIL

  pg -d postgres -c "DROP DATABASE IF EXISTS ${drill_db}" >/dev/null
  trap - EXIT
  echo "dropped ${drill_db}"

  local line="${started} ${status} source=${src} restore_seconds=${restore_seconds} tables=${tables_drill}/${tables_prod} ${summary}"
  echo "$line" >> "${BACKUP_DIR}/restore_drills.log"
  echo "== RESULT: ${line}"
  [[ "$status" == PASS ]]
}

case "${1:-}" in
  config) config ;;
  restore-drill) restore_drill ;;
  *) echo "usage: $0 config|restore-drill" >&2; exit 2 ;;
esac
