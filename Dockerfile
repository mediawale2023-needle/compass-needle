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

# Railway sets PORT env variable — do NOT hardcode a port
ENV PORT=8000

# Start the FastAPI server using the PORT env variable
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
