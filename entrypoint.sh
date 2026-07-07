#!/bin/bash

# 1. Start the Backend (FastAPI) in the background
# We use '&' to tell it to run in the background so the script continues.
echo "Starting Backend API..."
uvicorn main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*' &

# 2. Wait 5 seconds to ensure API is ready
sleep 5

# 3. Start the Frontend (Streamlit) in the foreground
# Streamlit will take over the main port so you can see it in the browser.
echo "Starting Streamlit Dashboard..."
streamlit run mp_dashboard.py --server.port $PORT --server.address 0.0.0.0
