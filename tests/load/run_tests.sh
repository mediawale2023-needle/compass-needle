#!/usr/bin/env bash
# Needle Load Test Runner — Phase 3 execution script
# Usage: bash tests/load/run_tests.sh <host>
# Example: bash tests/load/run_tests.sh http://localhost:8000

HOST=${1:-"http://localhost:8000"}
RESULTS="tests/load/results"
mkdir -p "$RESULTS"

# Ensure locust is installed
pip install locust --break-system-packages -q

echo ""
echo "════════════════════════════════════════════════════"
echo "  Needle Load Test Runner"
echo "  Host: $HOST"
echo "════════════════════════════════════════════════════"

# ── Test 1+2: API Baseline (1 user) then Ramp (50→100→500) ───────────────
echo ""
echo "[T1] API Baseline — 1 user, 60s"
locust -f tests/load/locustfile.py \
  --host="$HOST" \
  --users 1 --spawn-rate 1 --run-time 60s \
  --headless --only-summary \
  --tags baseline \
  --csv="$RESULTS/t1_baseline" 2>&1

echo ""
echo "[T2a] Ramp Stage 1 — 50 users, 2 min"
locust -f tests/load/locustfile.py \
  --host="$HOST" \
  --users 50 --spawn-rate 5 --run-time 2m \
  --headless --only-summary \
  --tags ramp \
  --csv="$RESULTS/t2a_ramp_50" 2>&1

echo ""
echo "[T2b] Ramp Stage 2 — 100 users, 2 min"
locust -f tests/load/locustfile.py \
  --host="$HOST" \
  --users 100 --spawn-rate 10 --run-time 2m \
  --headless --only-summary \
  --tags ramp \
  --csv="$RESULTS/t2b_ramp_100" 2>&1

echo ""
echo "[T2c] Ramp Stage 3 — 500 users, 3 min"
locust -f tests/load/locustfile.py \
  --host="$HOST" \
  --users 500 --spawn-rate 25 --run-time 3m \
  --headless --only-summary \
  --tags ramp \
  --csv="$RESULTS/t2c_ramp_500" 2>&1

# ── Test 3: Webhook Burst ─────────────────────────────────────────────────
echo ""
echo "[T3] Webhook Burst — 500 users, 90s"
locust -f tests/load/locustfile.py \
  --host="$HOST" \
  --users 500 --spawn-rate 50 --run-time 90s \
  --headless --only-summary \
  --tags webhook \
  --csv="$RESULTS/t3_webhook_burst" 2>&1

# ── Test 4: AI Latency ────────────────────────────────────────────────────
echo ""
echo "[T4] AI Classification Latency — 20 users, 3 min"
locust -f tests/load/locustfile.py \
  --host="$HOST" \
  --users 20 --spawn-rate 2 --run-time 3m \
  --headless --only-summary \
  --tags ai \
  --csv="$RESULTS/t4_ai_latency" 2>&1

# ── Test 5: DB Stress ─────────────────────────────────────────────────────
echo ""
echo "[T5] DB Query Stress — 100 users, 3 min"
locust -f tests/load/locustfile.py \
  --host="$HOST" \
  --users 100 --spawn-rate 10 --run-time 3m \
  --headless --only-summary \
  --tags db \
  --csv="$RESULTS/t5_db_stress" 2>&1

# ── Test 6: NLP Parser ────────────────────────────────────────────────────
echo ""
echo "[T6] Case Query Parser — 200 users, 2 min"
locust -f tests/load/locustfile.py \
  --host="$HOST" \
  --users 200 --spawn-rate 20 --run-time 2m \
  --headless --only-summary \
  --tags parser \
  --csv="$RESULTS/t6_parser" 2>&1

echo ""
echo "════════════════════════════════════════════════════"
echo "  All tests complete. Results in: $RESULTS/"
echo "  Run Phase 3 analysis on CSV files to generate report."
echo "════════════════════════════════════════════════════"
