# EC2 Backend Deployment

Target: AWS EC2 in Mumbai (`ap-south-1`) running the FastAPI backend with Docker and Caddy.

## Recommended Instance

- AMI: Ubuntu 24.04 LTS ARM64
- Type: `t4g.small`
- Disk: 20 GB gp3
- Security group inbound: `22` from your IP, `80` and `443` from anywhere
- Elastic IP: recommended for stable DNS

## Server Layout

```text
/opt/compass-needle/
  app/                  # git checkout of this repo
  .env                  # production secrets, never committed
  backup.env            # backup/S3 settings, never committed
  backups/              # last few local backup files before S3 handoff
  scripts/              # installed backup / restore helpers
  Caddyfile             # installed from deploy/ec2/Caddyfile during deploy
```

## Deploy

Deployments are GitHub-Actions-only. Push to `main`, or run **Deploy Backend To AWS EC2** manually from the GitHub Actions tab. Do not SSH from a laptop for normal deploys.

The workflow at `.github/workflows/deploy-aws-ec2.yml`:

1. Temporarily opens SSH only from the GitHub runner IP.
2. Reboots the instance if SSH is not reachable.
3. Resets `/opt/compass-needle/app` to the exact pushed commit.
4. Installs the repo-owned Caddyfile.
5. Rebuilds/restarts the backend and Caddy services.
6. Verifies `https://api.theneedle.in/health`.
7. Removes the temporary SSH ingress rule.
8. Installs repo-owned Postgres backup / restore scripts plus a nightly cron.

Add these repository secrets in GitHub:

```text
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_EC2_HOST
AWS_EC2_USER
AWS_EC2_SSH_KEY
```

For the current Mumbai EC2 setup:

```text
AWS_EC2_HOST=3.6.228.105
AWS_EC2_USER=ubuntu
```

The workflow temporarily opens SSH only from the GitHub runner's public IP, deploys, then removes that SSH rule.

## Nightly Postgres Backup

Create `/opt/compass-needle/backup.env` on the EC2 host from `deploy/ec2/backup.env.example`:

```text
BACKUP_S3_URI=s3://your-bucket/compass-needle/postgres
AWS_REGION=ap-south-1
BACKUP_RETENTION_DAYS=30
BACKUP_CRON_SCHEDULE=17 2 * * *
LOCAL_BACKUP_DIR=/opt/compass-needle/backups
COMPOSE_FILE=/opt/compass-needle/deploy/ec2/docker-compose.yml
POSTGRES_SERVICE=postgres
POSTGRES_DB=
```

The EC2 host needs AWS credentials that can write/read that S3 prefix, preferably through an instance IAM role.

The deploy workflow installs:

- `/opt/compass-needle/scripts/backup_postgres_to_s3.sh`
- `/opt/compass-needle/scripts/restore_postgres_backup.sh`
- `/opt/compass-needle/scripts/install_backup_cron.sh`

And sets a nightly cron at `/etc/cron.d/compass-needle-postgres-backup`.

Run an immediate backup manually:

```bash
/opt/compass-needle/scripts/backup_postgres_to_s3.sh
```

## Restore Drill

Rehearse one restore into a fresh database:

```bash
/opt/compass-needle/scripts/restore_postgres_backup.sh \
  --source s3://your-bucket/compass-needle/postgres/<host>/needle-postgres-YYYYMMDDTHHMMSSZ.sql.gz \
  --target-db needle_restore_drill
```

Then verify:

```bash
docker compose -f /opt/compass-needle/deploy/ec2/docker-compose.yml exec -T postgres \
  sh -lc 'export PGPASSWORD="${POSTGRES_PASSWORD}"; psql -U "${POSTGRES_USER}" -d needle_restore_drill -c "SELECT COUNT(*) FROM cases;"'
```

## Health Checks

```bash
curl -fsS https://api.theneedle.in/health
curl -fsS https://api.theneedle.in/health/db
```

## Frontend Environment

Set both Vercel projects to:

```text
NEXT_PUBLIC_API_URL=https://api.theneedle.in
```

Then update backend `ALLOWED_ORIGINS` to include both Vercel URLs and deploy through GitHub Actions.
