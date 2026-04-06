# MEMORY.md — Compass Needle Build Log

> **Purpose:** Prevent repeated work. Before implementing anything, check this file.
> Every significant decision, fix, and deliberate non-decision is recorded here.
> Updated: 2026-04-06

---

## 1. WHAT HAS BEEN BUILT (chronological)

### Phase 1 — Foundation & Security (PRs #28–#31)
- **Multi-tenant foundation hardened** (`01a71b29`): Tenant isolation enforced on all DB queries. Every `SELECT` on `cases`, `users`, `letterbox_items` etc. is scoped by `tenant_id`. Non-compliance is a critical security bug — never write a query without it.
- **bcrypt-only password enforcement**: Non-bcrypt hashes are rejected at login. Migration script at `scripts/migrate_passwords_to_bcrypt.py`.
- **JWT token blocklist**: `token_blocklist` table — revocation works by storing `(username, revoked_at)` and rejecting tokens with `iat < revoked_at`. Tokens are 8h expiry.
- **Per-tenant WhatsApp outbound routing** (`6d727461`): Each tenant has its own `phone_number_id` stored in DB. `get_tenant_phone_number_id(tenant_id)` in `db.py` is the authoritative lookup. Do NOT use the global `WHATSAPP_PHONE_NUMBER_ID` env var directly for outbound sends.
- **5-MP pilot hardening** (`96e6a857`): Rate limits (login: 5/min, AI: 3/min, webhook: 20/min), HMAC webhook validation, CORS locked to known Railway origins.

### Phase 2 — Geography & Location Intelligence (PRs #32–#37, multiple commits)
- **Geography data is DB-backed** (`df8cd778`, `947df7f4`, `16528fb6`): `data/geography/<District>/<Assembly>.json` files are seeded into `tenant_overrides` table on first deploy, then reconstructed from DB on every subsequent deploy. The DB is the **single source of truth** — filesystem is ephemeral on Railway.
- **4-tier location matching in main.py** (`bd899912`): Exact → Word boundary → Substring (key-in-input, min 5 chars, longest match wins) → Fuzzy (85% cutoff, similar-length filter ±30%). Do NOT collapse these tiers or change cutoffs without testing against the Aligarh dataset.
- **`awaiting_location` status** (`a06dac5e`): Cases where location cannot be matched to a constituency are held with `status='awaiting_location'`. Citizen gets a localized reply asking them to clarify. Dashboard shows these separately.
- **Localized location replies** (`67828454`): `modules/localized_replies.py` covers 13+ Indian languages. `get_awaiting_location_reply(location, detected_language)` is the only entry point — do NOT hardcode reply strings elsewhere.
- **Geography resolver reads from DB** (`16528fb6`): `geography_resolver.py` queries `tenant_overrides` table directly (type=`geography_data`). The filesystem paths in `ai_engine.py:get_jurisdiction_context()` are a fallback only — acknowledged outstanding risk, see §4.
- **`auto_generate_overrides()`** in `modules/geography_resolver.py`: Syncs locality→assembly mappings from JSON files into `tenant_overrides` DB rows. Called at startup. Idempotent.

### Phase 3 — WhatsApp Intelligence & Multi-Tenant Admin (PRs #33–#35)
- **WhatsApp case query engine** (`cd9fe217`): MPs/PAs can query live case data from WhatsApp in natural language. Pipeline: `case_query_parser.py` → `case_query_engine.py` → `case_query_formatter.py` → `whatsapp.py`. GPT-4o-mini parses NL → structured filters; regex fallback if OpenAI is down.
- **Admin: WhatsApp config editor** (`aed87af1`): Admin dashboard can set `phone_number_id` per tenant. Persisted to `tenants.config` JSON column.
- **Admin: delete MP cascades all FK tables** (`8980d9c9`): Hard delete of a tenant cascades: cases, users, letterbox, CSR, officers, escalations, contacts, tenant_overrides, activity_log. Tested — do NOT add new FK tables without updating the cascade in `admin_api.py`.
- **Staff/PA management**: PAs are `users` rows with `tenant_id`. PA phone number is stored in `users.phone`. PA whitelist check at letterbox intake: sender must match a `users.phone` for the tenant.

### Phase 4 — Production Readiness (PRs #38, direct commits `03dc8ba1`, `899ef852`)

#### Critical fixes merged directly to `main` (`03dc8ba1`):
1. **Dedup race condition closed**: Dedup INSERT moved to the webhook handler using `INSERT INTO wa_message_dedup ON CONFLICT DO NOTHING` + `rowcount` check — atomic gate before background task dispatch. Old SELECT-then-INSERT pattern removed from `_process_incoming_message`.
2. **Stuck 'processing' batch recovery**: `_sweep_stale_batches()` now resets `letterbox_batches` stuck in `'processing'` for >10 min back to `'pending'` before the sweep. Covers daemon threads killed mid-OCR during Railway redeploy.
3. **Review gate category matching fixed**: `_REVIEW_REQUIRED_CATEGORIES` is lowercase; check uses `category.lower().strip()`. Covers GPT variants like "Law and Order", "EMERGENCY".
4. **Citizen ACK retry on Meta failure**: Failed `send_whatsapp_message()` in the review gate flags case with `citizen_ack_pending: true` in metadata. `_sweep_pending_citizen_acks()` retries at every startup.
5. **Tenant config TTL cache**: `_get_tenant_daily_limit()` caches `daily_case_limit` per tenant for 5 min. Eliminates per-message `SELECT config FROM tenants` query.

#### Hardening PR (`899ef852`, merged PR #38):
- **OpenAI exponential backoff** in `ai_engine.py`: 3 attempts (1s→2s), falls back to safe `pending` dict. `_ai_retry_exhausted: True` flag in metadata for monitoring.
- **JWT storage → sessionStorage**: Both MP (`frontend/`) and Admin (`admin/`) dashboards now use `sessionStorage` instead of `localStorage`. One-time migration helper in `getAuthToken()` moves existing tokens on first load.
- **`security_startup_check.py` hardened**: Hard-fails on missing `DATABASE_URL`, empty `ALLOWED_ORIGINS`, missing API keys when `ENV=production`.
- **Dead scripts removed**: `create_user.py`, `force_user.py`, `reset_user.py` deleted — superseded by admin API. Never recreate as standalone scripts.
- **`WAMessageDedup` ORM model** added to `db.py` to match the `wa_message_dedup` table. Pruned on startup: rows older than 30 days are deleted.

---

## 2. KNOWN ARCHITECTURE DECISIONS (don't second-guess without reading this)

| Decision | Rationale | Where |
|---|---|---|
| All startup migrations inline in `main.py` | Avoids Alembic dependency; migrations are idempotent `CREATE TABLE IF NOT EXISTS` blocks protected by `pg_advisory_lock(77772024)` so only one Railway instance runs them | `main.py` lines ~220–420 |
| Background tasks via FastAPI `background_tasks` (not Celery) | No Redis dependency for pilot; acceptable at 30 MPs. Celery is Phase 3 upgrade path | `main.py` webhook handler |
| Letterbox batch timer uses `threading.Timer` + in-process dict | PA letter uploads need a 60s inactivity window; `_flush_letter_batch` uses atomic `UPDATE WHERE status='pending'` to prevent multi-instance double-processing | `main.py` `_schedule_batch_flush()` |
| Geography data in `tenant_overrides` table (type=`geography_data`) | Survives Railway ephemeral filesystem; shared across instances; admin-editable via API | `sansadx_backend/db.py`, `modules/geography_resolver.py` |
| `ALLOWED_ORIGINS = ["*"]` fallback in `main.py` | Backward compatibility with single-MP deployments where `ALLOWED_ORIGINS` env var may not be set. Acceptable because Bearer token auth is primary control | `main.py` lines ~28–30 |
| `nosec B608` on dynamic SQL WHERE clauses | Conditions are parameterized; the suppression is deliberate. Do NOT remove it without also removing the dynamic WHERE pattern | `api_router.py` |
| Gemini singleton with circuit breaker | Gemini has higher rate limits than OpenAI for OCR workloads; circuit breaker halts after 3 consecutive failures for 60s | `core/gemini_client.py` |
| `pg_advisory_lock(77772024)` on startup | Prevents two Railway instances running migrations simultaneously — could otherwise cause "column already exists" errors silently | `main.py` startup block |

---

## 3. WHAT NOT TO BUILD (already exists or deliberately excluded)

| Thing | Status | Notes |
|---|---|---|
| Alembic migrations | Deliberately skipped | Inline idempotent migrations in `main.py` chosen for simplicity. Revisit at 50+ MPs |
| Celery / Redis queue | Deferred to Phase 3 | Current threading model is acceptable at 30 MPs. Add when letterbox volume > 50 uploads/day per tenant |
| Refresh tokens | Not needed yet | 8h JWT expiry + re-login is acceptable for MP dashboard staff |
| Voice message transcription | Not built | Audio messages return a polite "please send as text" (`_handle_unsupported_message_type`). Transcription is Phase 3 |
| Per-tenant AI cost tracking | Not built | Flagged in audit as Medium risk. Add before 50 MP rollout |
| Right-to-deletion (DPDP Act) | Not built | Required before public launch. Flagged as compliance risk |
| Encryption of PII fields at rest | Not built | `user_phone`, `contacts.phone` are plaintext. Flagged, deferred |
| Urdu/Nastaliq script transliteration | Not built | Geography resolver handles Devanagari only. UP/Bihar Urdu-speaking constituencies affected |
| Mobile PWA | Not built | Phase 3 |
| Read replica for PostgreSQL | Not built | Phase 3 after 30 MP rollout |

---

## 4. KNOWN OUTSTANDING RISKS (audit findings not yet resolved)

| Risk | Severity | Notes |
|---|---|---|
| `ai_engine.py:get_jurisdiction_context()` reads filesystem | HIGH | Falls back to DB via `geography_resolver.py` but first tries `data/geography/`. On first deploy with empty DB, all cases get "Unknown" constituency. Mitigation: DB seeding runs at startup. Full fix deferred. |
| `time.sleep()` in OpenAI retry loop | MEDIUM | Blocks FastAPI thread for up to 3s per OpenAI failure. Acceptable at 30 MPs (max ~10 msgs/min). Becomes a problem at 100+ MPs during outage |
| No outbound WhatsApp message queue | MEDIUM | If Meta API is down, outbound replies are lost after 1 retry. No dead-letter mechanism beyond `citizen_ack_pending` flag for the review gate path |
| No per-tenant AI cost budget | MEDIUM | Single shared OpenAI key. A flood event at one tenant charges all tenants via shared quota |
| `is_deleted IS NULL` cases (pre-migration) | LOW | Backfill runs at startup. Any case created before the `is_deleted` column existed is backfilled to `false` on startup |

---

## 5. DB TABLES THAT EXIST (beyond the ORM models)

Some tables are created by inline migrations in `main.py`, not by SQLAlchemy `create_all`. Do not try to re-create them:

| Table | Created by | Notes |
|---|---|---|
| `token_blocklist` | `main.py` migration | JWT revocation; index on `username` and `revoked_at` |
| `wa_message_dedup` | `main.py` migration + ORM model in `db.py` | Webhook dedup; PRIMARY KEY on `message_id`; pruned 30-day TTL at startup |
| `letterbox_batches` | `main.py` migration | PA multi-page letter accumulation; `status` in ('pending', 'processing', 'done', 'failed') |
| `officers` | `main.py` migration | CRM for case escalation; `tenant_id` FK |
| `escalations` | `main.py` migration | Case → officer assignments |
| `spam_flags` | `main.py` migration | Phone-level spam tracking; index on `(tenant_id, phone)` |
| `archives` | Pre-existing | Has `tenant_id` column backfilled from `users` table on startup |

---

## 6. ACTIVE INDEXES (do not add duplicates)

Indexes added in `main.py` startup block or `scripts/add_query_indexes.sql`:

```
idx_cases_tenant_id         ON cases (tenant_id)
idx_cases_status            ON cases (status)
idx_cases_created_at        ON cases (created_at DESC)
idx_cases_tenant_status     ON cases (tenant_id, status)
idx_cases_tenant_created    ON cases (tenant_id, created_at DESC)
idx_cases_user_phone        ON cases (user_phone)
idx_cases_is_deleted        ON cases (is_deleted)
idx_cases_case_ref          ON cases (case_ref)
idx_spam_flags_tenant_phone ON spam_flags (tenant_id, phone)
idx_token_blocklist_username        ON token_blocklist (username)
idx_token_blocklist_revoked_at      ON token_blocklist (revoked_at)
idx_wa_dedup_processed_at   ON wa_message_dedup (processed_at)
idx_officers_tenant         ON officers (tenant_id)
```

---

## 7. ENVIRONMENT VARIABLES — FULL LIST

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL DSN |
| `JWT_SECRET` | Yes | Min 32 chars |
| `OPENAI_API_KEY` | Yes | GPT-4o-mini for classification + query parsing |
| `GEMINI_API_KEY` | Yes | Gemini for letter drafting + OCR |
| `WHATSAPP_PHONE_NUMBER_ID` | Yes | Default Meta phone number ID (per-tenant can override) |
| `META_ACCESS_TOKEN` | Yes | ⚠️ Use permanent System User token — temporary tokens expire |
| `META_VERIFY_TOKEN` | Yes | Webhook verification |
| `META_APP_SECRET` | Yes | HMAC signature validation for inbound webhook |
| `NEXT_PUBLIC_API_URL` | Yes (frontends) | Backend API URL for Next.js apps |
| `ALLOWED_ORIGINS` | Prod only | Comma-separated CORS origins. Defaults to `["*"]` if missing |
| `SENTRY_DSN` | Optional | Error monitoring |
| `ENV` | Optional | Set to `production` to enable hard-fail security checks |

---

## 8. PATTERNS TO FOLLOW

**Adding a new DB table:**
1. Add the SQLAlchemy model in `sansadx_backend/db.py`
2. Add an idempotent `CREATE TABLE IF NOT EXISTS` migration in `main.py` inside the `pg_advisory_lock` block
3. Add indexes in the performance indexes block in `main.py`
4. Update the DB models table in `CLAUDE.md` and the tables list in §5 of this file

**Adding a new API endpoint:**
- MP-facing → `api_router.py`, protected by `get_current_user()` + `get_tenant_or_fail()`
- Admin-facing → `admin_api.py`, protected by `get_admin_user()`
- Every query must have `tenant_id = :tid` in its WHERE clause

**Adding a new WhatsApp message type handler:**
- Add a new `_handle_*` function in `main.py`
- Route it via `background_tasks.add_task()` in the `whatsapp_webhook` handler
- Never call it synchronously inside the webhook handler — must return 200 within 20s

**Adding a new AI call:**
- Always wrap in try/except and return a safe fallback
- Always use bound parameters when building prompts (no f-string user data directly into system prompt)
- Log errors with `logger.error()`, never expose `str(e)` in API responses

---

## 9. NEXT PLANNED WORK (not yet started)

| Item | Priority | Notes |
|---|---|---|
| Geography filesystem fallback → full DB path in `ai_engine.py` | HIGH | Fix `get_jurisdiction_context()` to query DB directly when filesystem empty |
| Celery + Redis for background tasks | HIGH (Phase 3) | Required before 50+ MP rollout |
| Per-tenant AI cost budget enforcement | MEDIUM | Track daily OpenAI spend per tenant; reject with fallback at limit |
| `_ai_retry_exhausted` reprocessing job | MEDIUM | Cron job to re-classify cases where `_ai_retry_exhausted: true` |
| Morning digest push to MP/PA WhatsApp | MEDIUM | Scheduled 8am summary of new/pending/critical cases |
| 1-click letter draft from case detail | MEDIUM | Pre-fill Drafter with case data: recipient, category, summary |
| Alembic migration system | LOW (Phase 3) | Replace inline `main.py` migrations |
| DPDP Act compliance — right to deletion | MEDIUM (legal) | Required before public launch in India |
| Urdu/Nastaliq transliteration in geography resolver | MEDIUM | Affects UP/Bihar Urdu-speaking constituencies |
