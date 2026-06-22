#!/usr/bin/env bash
set -euo pipefail

BACKUP_ENV_PATH="${BACKUP_ENV_PATH:-/opt/compass-needle/backup.env}"
CRON_PATH="/etc/cron.d/compass-needle-postgres-backup"
SCRIPT_PATH="/opt/compass-needle/scripts/backup_postgres_to_s3.sh"
LOG_PATH="/var/log/compass-needle-postgres-backup.log"

schedule="17 2 * * *"
if [[ -f "$BACKUP_ENV_PATH" ]]; then
  schedule_from_env="$(grep -E '^BACKUP_CRON_SCHEDULE=' "$BACKUP_ENV_PATH" | tail -n 1 | cut -d= -f2- || true)"
  if [[ -n "$schedule_from_env" ]]; then
    schedule="$schedule_from_env"
  fi
fi

cat <<EOF | sudo tee "$CRON_PATH" > /dev/null
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

${schedule} ubuntu ${SCRIPT_PATH} >> ${LOG_PATH} 2>&1
EOF

sudo chmod 0644 "$CRON_PATH"
sudo touch "$LOG_PATH"
sudo chown ubuntu:ubuntu "$LOG_PATH"
sudo systemctl enable cron >/dev/null 2>&1 || true
sudo systemctl restart cron

echo "installed backup cron at ${CRON_PATH} with schedule: ${schedule}"
