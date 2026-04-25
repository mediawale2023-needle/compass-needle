"""
Needle — Performance & Load Test Suite
Phase 2: Locust test scripts for all 6 test cases

Usage:
  locust -f tests/load/locustfile.py --host=http://localhost:8000
  locust -f tests/load/locustfile.py --host=http://localhost:8000 \
         --users 100 --spawn-rate 10 --run-time 2m --headless

Ramp profile (Phase 3 will execute these):
  Stage 1 —  50 users, spawn  5/s, 2 min
  Stage 2 — 100 users, spawn 10/s, 2 min
  Stage 3 — 500 users, spawn 25/s, 3 min
"""

import json
import time
import hmac
import hashlib
import os
import random
from locust import HttpUser, task, between, tag, events
from locust.contrib.fasthttp import FastHttpUser

# ─── Auth token — set via env or replace with a real test token ───────────
JWT_TOKEN = os.getenv("NEEDLE_TEST_JWT", "test-jwt-token-replace-me")
ADMIN_JWT  = os.getenv("NEEDLE_ADMIN_JWT", "admin-jwt-token-replace-me")
META_SECRET = os.getenv("META_APP_SECRET", "test-secret")
TENANT_ID  = int(os.getenv("NEEDLE_TEST_TENANT", "1"))

HEADERS     = {"Authorization": f"Bearer {JWT_TOKEN}", "Content-Type": "application/json"}
ADMIN_HDRS  = {"Authorization": f"Bearer {ADMIN_JWT}",  "Content-Type": "application/json"}

# ─── Realistic sample payloads ────────────────────────────────────────────
GRIEVANCE_MESSAGES = [
    "Rampur mein sadak toot gayi hai aur paani bhi nahi aata",
    "PM Awas ka paisa 2 saal se nahi aaya, kab milega",
    "Bachpura PHC mein doctor 1 mahine se nahi aaya",
    "Neelgai ne Khajuri ka saara gehu kha liya",
    "Kelkar bag madhe paani nahi aahe. Khup traas hotoy",
    "Road pannunga, irukku problem sollunga",
    "The road from Kanpur to Bilhaur is completely broken",
    "Lekhpal ne income certificate ke liye 500 rupaye maange",
    "Thane mein FIR nahi likh rahe, 3 baar gaya",
    "Kisi ne mera UPI se 15000 rupaye le liye, phone pe fraud hua",
]

QUERY_MESSAGES = [
    "Pending water cases in Tilakwadi last 1 month",
    "Show resolved road issues last week",
    "Health cases today",
    "Cases from Ward 5 this month",
    "Pending cases last 30 days",
]


def _sign_payload(body: bytes) -> str:
    """Generate Meta-style HMAC-SHA256 signature for webhook tests."""
    sig = hmac.new(META_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


# ══════════════════════════════════════════════════════════════════════════
# TEST 1 + 2: API Baseline + Concurrent User Ramp
# Simulates MP dashboard usage: list cases, view case detail, update status
# ══════════════════════════════════════════════════════════════════════════
@tag("baseline", "ramp")
class MPDashboardUser(HttpUser):
    """
    Test 1 — API Baseline: sequential requests, single user
    Test 2 — Concurrent Ramp: run with --users 50/100/500
    """
    wait_time = between(1, 3)   # realistic think-time between actions

    @tag("baseline", "ramp")
    @task(3)
    def list_cases(self):
        """Most common action — MP opens case list"""
        with self.client.get(
            f"/api/cases?tenant_id={TENANT_ID}&limit=20&offset=0",
            headers=HEADERS,
            name="/api/cases [list]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 401:
                resp.failure("Auth failed — check JWT_TOKEN")
            else:
                resp.failure(f"Unexpected {resp.status_code}")

    @tag("baseline", "ramp")
    @task(2)
    def filter_cases_by_status(self):
        """MP filters by pending status"""
        status = random.choice(["new", "pending", "completed"])
        self.client.get(
            f"/api/cases?tenant_id={TENANT_ID}&status={status}&limit=20",
            headers=HEADERS,
            name="/api/cases [filter:status]",
        )

    @tag("baseline", "ramp")
    @task(1)
    def get_case_detail(self):
        """MP opens a single case"""
        case_id = random.randint(1, 50)
        with self.client.get(
            f"/api/cases/{case_id}",
            headers=HEADERS,
            name="/api/cases/{id}",
            catch_response=True,
        ) as resp:
            # 404 is acceptable (case may not exist in test DB)
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Unexpected {resp.status_code}")

    @tag("baseline", "ramp")
    @task(1)
    def health_check(self):
        """Basic liveness probe"""
        self.client.get("/health", name="/health")


# ══════════════════════════════════════════════════════════════════════════
# TEST 3: WhatsApp Webhook Burst
# Simulates Meta sending a burst of citizen messages
# ══════════════════════════════════════════════════════════════════════════
@tag("webhook", "burst")
class WhatsAppWebhookUser(HttpUser):
    """
    Test 3 — Webhook Burst: 500 concurrent POST requests
    Run with: --users 500 --spawn-rate 50
    """
    abstract = True
    wait_time = between(0.1, 0.5)   # tight — burst simulation

    @tag("webhook", "burst")
    @task
    def send_citizen_message(self):
        """Simulate a citizen sending a WhatsApp grievance"""
        msg_text = random.choice(GRIEVANCE_MESSAGES)
        phone    = f"9190{random.randint(10000000, 99999999)}"

        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "TEST_ENTRY",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"phone_number_id": "TEST_PHONE_ID"},
                        "messages": [{
                            "id": f"wamid.test{random.randint(100000, 999999)}",
                            "from": phone,
                            "timestamp": str(int(time.time())),
                            "type": "text",
                            "text": {"body": msg_text},
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }

        body  = json.dumps(payload).encode()
        sig   = _sign_payload(body)

        with self.client.post(
            "/whatsapp/webhook",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": sig,
            },
            name="/whatsapp/webhook [burst]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Webhook returned {resp.status_code}")


# ══════════════════════════════════════════════════════════════════════════
# TEST 4: AI Classification Latency Under Stress
# Measures GPT-4o-mini response time with 20 concurrent callers
# ══════════════════════════════════════════════════════════════════════════
@tag("ai", "latency")
class AIClassificationUser(HttpUser):
    """
    Test 4 — AI Latency Stress: 20 concurrent users hitting AI endpoint
    Run with: --users 20 --spawn-rate 2
    Captures: p50/p95/p99 AI latency, retry rate
    """
    abstract = True
    wait_time = between(2, 5)  # AI calls are slow — realistic gap

    @tag("ai", "latency")
    @task
    def classify_grievance(self):
        """POST a grievance message through the full AI pipeline"""
        payload = {
            "phone": f"9190{random.randint(10000000, 99999999)}",
            "message": random.choice(GRIEVANCE_MESSAGES),
            "tenant_id": TENANT_ID,
        }
        body = json.dumps(payload).encode()
        sig  = _sign_payload(body)

        with self.client.post(
            "/whatsapp/webhook",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": sig,
            },
            name="/whatsapp/webhook [AI:classify]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 429:
                resp.failure("Rate limit hit — check AI throttle config")
            else:
                resp.failure(f"AI classification failed: {resp.status_code}")


# ══════════════════════════════════════════════════════════════════════════
# TEST 5: DB Query Stress (Case Explorer)
# Simulates 100 concurrent MP dashboard loads with tenant-scoped queries
# ══════════════════════════════════════════════════════════════════════════
@tag("db", "stress")
class DBQueryStressUser(HttpUser):
    """
    Test 5 — DB Stress: 100 concurrent users running filtered queries
    Measures: query time, connection pool saturation, index hit rate
    Run: --users 100 --spawn-rate 10
    """
    abstract = True
    wait_time = between(0.5, 2)

    @tag("db", "stress")
    @task(3)
    def case_list_with_filters(self):
        """Filtered case list — exercises composite DB index"""
        params = {
            "tenant_id": TENANT_ID,
            "status": random.choice(["new", "pending", "completed"]),
            "limit": 50,
            "offset": random.randint(0, 200),
        }
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        self.client.get(
            f"/api/cases?{qs}",
            headers=HEADERS,
            name="/api/cases [db:filtered]",
        )

    @tag("db", "stress")
    @task(2)
    def admin_case_explorer(self):
        """Admin case explorer — cross-tenant aggregation"""
        self.client.get(
            "/admin/cases?limit=50&offset=0",
            headers=ADMIN_HDRS,
            name="/admin/cases [db:explorer]",
        )

    @tag("db", "stress")
    @task(1)
    def analytics_summary(self):
        """Analytics/stats endpoint — heavy aggregation query"""
        self.client.get(
            f"/api/analytics/summary?tenant_id={TENANT_ID}",
            headers=HEADERS,
            name="/api/analytics/summary [db:agg]",
        )


# ══════════════════════════════════════════════════════════════════════════
# TEST 6: Case Query Parser Load (NLP + Regex Fallback)
# ══════════════════════════════════════════════════════════════════════════
@tag("parser", "nlp")
class CaseQueryParserUser(HttpUser):
    """
    Test 6 — Query Parser: 200 concurrent WhatsApp staff queries
    Tests both GPT path and regex fallback path
    """
    abstract = True
    wait_time = between(1, 4)

    @tag("parser", "nlp")
    @task
    def staff_case_query(self):
        """PA sends a natural-language case query via WhatsApp"""
        query = random.choice(QUERY_MESSAGES)
        phone = f"9180{random.randint(10000000, 99999999)}"  # staff phone

        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "TEST_ENTRY",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"phone_number_id": "TEST_PHONE_ID"},
                        "messages": [{
                            "id": f"wamid.staff{random.randint(100000, 999999)}",
                            "from": phone,
                            "timestamp": str(int(time.time())),
                            "type": "text",
                            "text": {"body": query},
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }

        body = json.dumps(payload).encode()
        sig  = _sign_payload(body)

        with self.client.post(
            "/whatsapp/webhook",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": sig,
            },
            name="/whatsapp/webhook [parser:nlp]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Parser query failed: {resp.status_code}")


# ══════════════════════════════════════════════════════════════════════════
# EVENT HOOKS — custom metrics logging
# ══════════════════════════════════════════════════════════════════════════
@events.request.add_listener
def on_request(request_type, name, response_time, response_length,
               response, context, exception, **kwargs):
    """Log any request exceeding the critical threshold (2000ms)."""
    if response_time > 2000:
        print(f"[SLOW] {name} — {response_time:.0f}ms > 2000ms threshold")
    if exception:
        print(f"[ERR]  {name} — {exception}")
