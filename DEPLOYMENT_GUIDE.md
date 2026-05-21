# Security Deployment Guide

## Pre-Deployment Checklist

### 1. Credential Rotation (CRITICAL)

```bash
# Step 1: Generate new credentials from each service
# OpenAI: https://platform.openai.com/api-keys
# Gemini: https://aistudio.google.com/app/apikey
# Twilio: https://www.twilio.com/console/account/keys
# Database: Create new user in your database

# Step 2: Generate strong JWT_SECRET
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Step 3: Create .env file with new credentials
cp .env.example .env
# Edit .env with real values
```

### 2. Environment Setup

```bash
# Set environment variables
export ENV=production
export JWT_SECRET=<your-generated-secret>
export ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
export DATABASE_URL=postgresql://user:password@host:port/db
export OPENAI_API_KEY=sk-...
export GEMINI_API_KEY=AIza...
export WHATSAPP_PHONE_NUMBER_ID=123456789012345
export META_ACCESS_TOKEN=replace-with-permanent-system-user-token
export META_VERIFY_TOKEN=replace-with-webhook-verify-token
export META_APP_SECRET=replace-with-meta-app-secret
```

### 3. Password Migration

```bash
# Migrate all existing passwords to bcrypt
python3 scripts/migrate_passwords_to_bcrypt.py

# Verify migration
python3 -c "from db import SessionLocal, User; db = SessionLocal(); users = db.query(User).all(); print(f'Total users: {len(users)}'); hashed = sum(1 for u in users if u.password_hash.startswith('$2')); print(f'Hashed: {hashed}')"
```

### 4. Security Validation

```bash
# Run security startup checks
python3 scripts/security_startup_check.py

# Expected output:
# ✅ JWT_SECRET properly configured
# ✅ DATABASE_URL configured
# ✅ CORS configured for X origin(s)
# ✅ All API keys configured
# ✅ Running in PRODUCTION mode
# ✅ Logging level: INFO
```

### 5. Database Backup

```bash
# Create backup before deployment
pg_dump -U postgres -h localhost database_name > backup_$(date +%Y%m%d_%H%M%S).sql

# Verify backup
ls -lh backup_*.sql
```

### 6. Git Cleanup

```bash
# Remove .env from git history
git rm --cached .env
git commit -m "Remove .env from tracking"

# Verify .env is in .gitignore
grep "^\.env$" .gitignore

# Push changes
git push origin main
```

## Deployment Steps

### Option A: Docker Deployment

```bash
# Build image
docker build -t needle:latest .

# Run with environment variables
docker run -d \
  -e ENV=production \
  -e JWT_SECRET=$JWT_SECRET \
  -e DATABASE_URL=$DATABASE_URL \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -e GEMINI_API_KEY=$GEMINI_API_KEY \
  -e WHATSAPP_PHONE_NUMBER_ID=$WHATSAPP_PHONE_NUMBER_ID \
  -e META_ACCESS_TOKEN=$META_ACCESS_TOKEN \
  -e META_VERIFY_TOKEN=$META_VERIFY_TOKEN \
  -e META_APP_SECRET=$META_APP_SECRET \
  -e ALLOWED_ORIGINS=https://yourdomain.com \
  -p 8000:8000 \
  needle:latest
```

### Option B: EC2 Deployment Through GitHub Actions

```bash
# Deploy by pushing to main, or run the workflow manually:
# GitHub → Actions → Deploy Backend To AWS EC2 → Run workflow
git push origin main

# Verify after the workflow finishes
curl https://backend.coinmedia.co.in/health
```

### Option C: Emergency Manual Server Deployment

```bash
# Break-glass only. Normal deploys must use GitHub Actions.
ssh user@server.com

# Clone repository
git clone https://github.com/your-repo/compass-needle.git
cd compass-needle

# Create .env file
nano .env
# Add all environment variables

# Install dependencies
pip install -r requirements.txt

# Run migrations
python3 scripts/migrate_passwords_to_bcrypt.py

# Start application
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Post-Deployment Verification

Run the full smoke test once the deploy is live:

```bash
export BACKEND_URL="https://backend.coinmedia.co.in"
export MP_URL="https://<mp-vercel-domain>"
export ADMIN_URL="https://<admin-vercel-domain>"
export MP_USERNAME="..."
export MP_PASSWORD="..."
export ADMIN_USERNAME="..."
export ADMIN_PASSWORD="..."
export META_APP_SECRET="..."
export TEST_SENDER="919999999999"
export WA_DISPLAY_NUMBER="15551636821"

./scripts/railway_smoke_test.sh
```

This verifies:
- backend health and docs
- MP and admin web availability
- MP login and admin login
- signed WhatsApp webhook intake
- case creation visibility for the MP
- outbound citizen notification
- `403` on bad webhook signatures
- `400` on malformed signed webhook payloads

### 1. Health Check

```bash
# Test API is running
curl https://yourdomain.com/

# Expected response:
# {"status":"active","system":"Needle Backend V7"}
```

### 2. Authentication Test

```bash
# Test login endpoint
curl -X POST https://yourdomain.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}'

# Expected response:
# {"token":"eyJ...","user":{...}}
```

### 3. CORS Test

```bash
# Test CORS headers
curl -i -X OPTIONS https://yourdomain.com/api/auth/login \
  -H "Origin: https://yourdomain.com" \
  -H "Access-Control-Request-Method: POST"

# Should see:
# Access-Control-Allow-Origin: https://yourdomain.com
# Access-Control-Allow-Methods: GET, POST, PUT, DELETE, PATCH
```

### 4. Security Headers Test

```bash
# Check security headers
curl -i https://yourdomain.com/ | grep -i "X-"

# Should see:
# X-Content-Type-Options: nosniff
# X-Frame-Options: DENY
# X-XSS-Protection: 1; mode=block
```

### 5. Database Connection Test

```bash
# Test database connectivity
python3 -c "from db import SessionLocal; db = SessionLocal(); print('✅ Database connected')"
```

## Monitoring & Maintenance

### Daily Checks

```bash
# Check application logs
tail -f /var/log/needle/app.log

# Monitor database
psql -U postgres -d database_name -c "SELECT COUNT(*) FROM cases;"

# Check disk space
df -h
```

### Weekly Tasks

```bash
# Backup database
pg_dump -U postgres database_name | gzip > backup_$(date +%Y%m%d).sql.gz

# Review security logs
grep "ERROR\|WARN" /var/log/needle/app.log

# Check for updates
pip list --outdated
```

### Monthly Tasks

```bash
# Rotate credentials (if needed)
# Update dependencies
pip install --upgrade -r requirements.txt

# Run security audit
bandit -r . -ll

# Review access logs
tail -n 1000 /var/log/nginx/access.log | grep -i "error\|401\|403"
```

## Troubleshooting

### JWT Secret Error

```
ValueError: JWT_SECRET environment variable is required
```

**Solution:**
```bash
export JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
```

### Database Connection Error

```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solution:**
```bash
# Verify DATABASE_URL
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL -c "SELECT 1"
```

### CORS Error

```
Access to XMLHttpRequest blocked by CORS policy
```

**Solution:**
```bash
# Verify ALLOWED_ORIGINS
echo $ALLOWED_ORIGINS

# Add your domain if missing
export ALLOWED_ORIGINS=https://yourdomain.com
```

### Password Migration Failed

```
bcrypt.exceptions.InvalidHash: Invalid salt
```

**Solution:**
```bash
# Check password hashes in database
psql $DATABASE_URL -c "SELECT username, password_hash FROM users LIMIT 5;"

# Re-run migration
python3 scripts/migrate_passwords_to_bcrypt.py
```

## Rollback Procedure

If deployment fails:

```bash
# 1. Restore database from backup
psql -U postgres database_name < backup_YYYYMMDD_HHMMSS.sql

# 2. Revert code to previous version
git revert HEAD

# 3. Restart application
systemctl restart needle

# 4. Verify
curl https://yourdomain.com/
```

## Security Incident Response

If security issue is discovered:

1. **Immediate Actions**
   - Stop the application
   - Isolate the server
   - Preserve logs

2. **Investigation**
   - Review access logs
   - Check for unauthorized access
   - Identify affected data

3. **Remediation**
   - Rotate all credentials
   - Patch vulnerability
   - Deploy fix

4. **Recovery**
   - Restore from clean backup if needed
   - Restart application
   - Monitor for suspicious activity

5. **Post-Incident**
   - Document incident
   - Update security procedures
   - Notify stakeholders

## Support & Escalation

For security issues:
- Email: security@yourdomain.com
- Phone: +1-XXX-XXX-XXXX
- On-call: Check PagerDuty

## References

- [OWASP Deployment Checklist](https://cheatsheetseries.owasp.org/cheatsheets/Deployment_Checklist.html)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [PostgreSQL Security](https://www.postgresql.org/docs/current/sql-syntax.html)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)
