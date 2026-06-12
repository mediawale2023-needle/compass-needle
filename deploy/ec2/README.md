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
curl -fsS https://api.theneedle.in/health
curl -fsS https://api.theneedle.in/health/db
```

## Frontend Environment

Set both Vercel projects to:

```text
NEXT_PUBLIC_API_URL=https://api.theneedle.in
```

Then update backend `ALLOWED_ORIGINS` to include both Vercel URLs and deploy through GitHub Actions.
