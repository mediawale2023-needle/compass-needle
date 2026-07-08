#!/usr/bin/env bash
set -euo pipefail

# Installs the recurring jobs/ cron on the EC2 host. Mirrors install_backup_cron.sh:
# re-run on every deploy so the schedule can't silently disappear after a rebuild.
# Each job runs inside the backend container; flock prevents overlapping runs.

CRON_PATH="/etc/cron.d/compass-needle-jobs"
COMPOSE_FILE="${COMPOSE_FILE:-/opt/compass-needle/deploy/ec2/docker-compose.yml}"
LOG_DIR="/var/log/compass-needle-jobs"

cat <<EOF | sudo tee "$CRON_PATH" > /dev/null
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# All times UTC (IST = UTC+5:30). Cadences per each job's own docstring.
# hourly — detects active Lok Sabha sessions, triggers syncs on its own cadence
0 * * * *    ubuntu flock -n /tmp/needle-job-parlmon.lock  docker compose -f ${COMPOSE_FILE} exec -T backend python -m jobs.parliament_session_monitor >> ${LOG_DIR}/parliament_session_monitor.log 2>&1
# 01:30 UTC = 07:00 IST — morning digest of unescalated T0 emergency intakes
30 1 * * *   ubuntu flock -n /tmp/needle-job-digest.lock   docker compose -f ${COMPOSE_FILE} exec -T backend python -m jobs.t0_morning_digest >> ${LOG_DIR}/t0_morning_digest.log 2>&1
# 19:30 UTC = 01:00 IST — nightly grievance clustering
30 19 * * *  ubuntu flock -n /tmp/needle-job-cluster.lock  docker compose -f ${COMPOSE_FILE} exec -T backend python -m jobs.auto_cluster >> ${LOG_DIR}/auto_cluster.log 2>&1
# 20:30 UTC = 02:00 IST — daily match-score recompute
30 20 * * *  ubuntu flock -n /tmp/needle-job-scoring.lock  docker compose -f ${COMPOSE_FILE} exec -T backend python -m jobs.scoring_recompute >> ${LOG_DIR}/scoring_recompute.log 2>&1
# every 6 hours — refresh csr_opportunities from live grievance clusters
15 */6 * * * ubuntu flock -n /tmp/needle-job-oppsync.lock  docker compose -f ${COMPOSE_FILE} exec -T backend python -m jobs.opportunity_sync >> ${LOG_DIR}/opportunity_sync.log 2>&1
# Monday 03:00 UTC = 08:30 IST — weekly CSR intelligence report
0 3 * * 1    ubuntu flock -n /tmp/needle-job-weekly.lock   docker compose -f ${COMPOSE_FILE} exec -T backend python -m jobs.weekly_report >> ${LOG_DIR}/weekly_report.log 2>&1
EOF

sudo chmod 0644 "$CRON_PATH"
sudo install -d -m 0755 -o ubuntu -g ubuntu "$LOG_DIR"
sudo systemctl enable cron >/dev/null 2>&1 || true
sudo systemctl restart cron

echo "installed jobs cron at ${CRON_PATH}"
