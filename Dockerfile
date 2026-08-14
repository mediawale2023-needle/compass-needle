FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright's Chromium + its OS-level deps (fonts, codecs, etc.), for
# modules/govt_sync/browser_session.py — the live, staff-controllable
# government-portal browser sessions. --with-deps installs everything
# Chromium needs to actually run on this Debian-slim base, not just the
# browser binary itself.
RUN playwright install --with-deps chromium

# Copy the rest of the application
COPY . .

# Railway sets PORT env variable — do NOT hardcode a port.
# WEB_CONCURRENCY lets EC2 run multiple Uvicorn workers on larger instances.
ENV PORT=8000
ENV WEB_CONCURRENCY=1

# Start the FastAPI server using the PORT env variable.
# --timeout-graceful-shutdown 30  — gives in-flight requests 30s to complete
#   before the worker is killed on Railway redeploy (prevents mid-request drops).
# --timeout-keep-alive 75         — keeps idle connections alive for 75s
#   (Railway's load balancer uses 80s keep-alive; matching avoids premature resets).
# --proxy-headers / forwarded IPs — trust Caddy inside the private Docker network
#   so anonymous endpoint limits see the original client instead of Caddy's IP.
CMD uvicorn main:app --host 0.0.0.0 --port $PORT --workers $WEB_CONCURRENCY --proxy-headers --forwarded-allow-ips='*' --timeout-graceful-shutdown 30 --timeout-keep-alive 75
