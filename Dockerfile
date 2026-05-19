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
CMD uvicorn main:app --host 0.0.0.0 --port $PORT --workers $WEB_CONCURRENCY --timeout-graceful-shutdown 30 --timeout-keep-alive 75
