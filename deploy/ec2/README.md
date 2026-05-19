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
  Caddyfile             # domain reverse proxy config
```

## Deploy

```bash
cd /opt/compass-needle/app
git pull origin main
docker compose -f deploy/ec2/docker-compose.yml up -d --build
docker compose -f deploy/ec2/docker-compose.yml logs -f --tail=100
```

## GitHub Actions Deploy

The workflow at `.github/workflows/deploy-aws-ec2.yml` deploys the backend on pushes to `main`.

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

## Health Checks

```bash
curl -fsS https://YOUR_API_DOMAIN/health
curl -fsS https://YOUR_API_DOMAIN/health/db
```

## Frontend Environment

Set both Vercel projects to:

```text
NEXT_PUBLIC_API_URL=https://YOUR_API_DOMAIN
```

Then update backend `ALLOWED_ORIGINS` to include both Vercel URLs and restart:

```bash
docker compose -f deploy/ec2/docker-compose.yml up -d --build
```
