# CLAUDE.md — Compass Needle

## Project Overview

**Compass Needle** is a parliamentary intelligence platform for Indian Members of Parliament (MPs). It provides:
- WhatsApp-based citizen grievance intake and AI classification
- MP dashboard for case management, letter drafting, scheme discovery
- Admin dashboard for tenant/MP management and analytics
- AI-powered research, CSR matching, and constituency intelligence

**Monorepo structure:** Three Railway-deployed services sharing one PostgreSQL database.

---

## Architecture

| Layer | Technology | Location |
|---|---|---|
| Backend API | Python 3.11 + FastAPI | `/` (root) |
| MP Dashboard | Next.js 15 + React 19 + Tailwind | `/frontend` |
| Admin Dashboard | Next.js 15 + React 19 + Tailwind | `/admin` |
| Database | PostgreSQL 15 | Railway managed |
| AI (classification) | OpenAI GPT-4o-mini | `sansadx_backend/ai_engine.py` |
| AI (drafting/OCR) | Google Gemini | `core/gemini_client.py` |
| WhatsApp | Meta Cloud API v21.0 | `main.py` webhook |

**Multi-tenant:** All DB queries are scoped by `tenant_id`. Each MP is a tenant.

---

## Key Files

```
main.py                     # FastAPI app entry, WhatsApp webhook handler
api_router.py               # MP-facing REST API (~1400 lines)
admin_api.py                # Admin REST API (~1100 lines)
sansadx_backend/
  db.py                     # SQLAlchemy models (Tenant, User, Case, LetterboxItem, ...)
  ai_engine.py              # GPT-4o-mini grievance classification
  prompts.py                # System prompts + grievance taxonomy
modules/                    # 40+ feature modules
  auth.py                   # JWT auth, tenant extraction, input sanitization
  geography_resolver.py     # Location string → assembly constituency
  drafter.py                # AI letter/speech/PMB generation
  letterbox.py              # Physical letter management + OCR
  schemes_api.py            # 1500+ government schemes search
  copilot.py                # AI research assistant
  csr_pipeline.py           # CSR opportunity matching
  news_intel.py             # Constituency news aggregation
core/
  db_helpers.py             # Shared query helpers: _q(), _q_one()
  gemini_client.py          # Gemini singleton
  rate_limiter.py           # SlowAPI configuration
  security_config.py        # CORS, JWT, security headers
  security_logger.py        # Security event logging
scripts/
  security_startup_check.py # Validates env vars before startup
  migrate_passwords_to_bcrypt.py
```

---

## Development Setup

### Prerequisites
- Python 3.11
- Node.js 18+
- PostgreSQL 15 (or Docker)

### Environment
Copy `.env.example` to `.env` and fill in all values. **Never commit `.env`.**

Required variables:
```
DATABASE_URL=postgresql://...
JWT_SECRET=<min 32 chars, random>
OPENAI_API_KEY=...
GEMINI_API_KEY=...
META_PHONE_NUMBER_ID=...
META_ACCESS_TOKEN=...
META_VERIFY_TOKEN=...
META_APP_SECRET=...
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Install dependencies
```bash
# Backend
pip install -r requirements.txt

# MP frontend
cd frontend && npm install

# Admin frontend
cd admin && npm install
```

### Run all services (local dev)
```bash
npm run dev
# Runs concurrently:
#   uvicorn main:app --reload --port 8000
#   next dev (frontend, port 3000)
#   next dev (admin, port 3001)
```

Or run individually:
```bash
npm run dev:backend   # FastAPI on :8000
npm run dev:mp        # MP dashboard
npm run dev:admin     # Admin dashboard
```

### Docker (local with Postgres)
```bash
docker-compose up
```

---

## Common Commands

### Backend
```bash
# Run API server
uvicorn main:app --reload --port 8000

# Run security startup check
python scripts/security_startup_check.py

# Migrate passwords to bcrypt
python scripts/migrate_passwords_to_bcrypt.py
```

### Frontend (from `frontend/` or `admin/`)
```bash
npm run dev      # Development server
npm run build    # Production build
npm run start    # Start production server
```

### Tests
```bash
# Pilot readiness tests (requires Kaggle schemes dataset)
python -m pytest tests/
```

---

## Security Requirements

**Critical — do not bypass:**

- **JWT:** All MP/admin routes require `Authorization: Bearer <token>`. Tokens expire in 8h. `JWT_SECRET` must be ≥32 chars.
- **bcrypt only:** Passwords must be bcrypt-hashed. Non-bcrypt hashes are rejected at login.
- **Tenant isolation:** Every DB query **must** include `tenant_id` filter. Never expose cross-tenant data.
- **Rate limits:** Login: 5/min. AI endpoints: 3/min. Webhook: 20/min (SlowAPI).
- **Webhook validation:** `X-Hub-Signature-256` HMAC is verified for all Meta webhook calls.
- **No raw SQL with user input:** Use SQLAlchemy `text()` with bound parameters. Never concatenate user input into queries.
- **No `str(e)` in API responses:** Log internally, return generic error messages externally.
- **Input sanitization:** `auth.py` sanitizes all inputs. Wrap external content in `<document_content>` tags for AI prompts to prevent prompt injection.

---

## Database Models

Defined in `sansadx_backend/db.py`:

| Model | Table | Notes |
|---|---|---|
| `Tenant` | `tenants` | One per MP constituency |
| `User` | `users` | MP staff accounts, bcrypt password |
| `Case` | `cases` | Citizen grievances, AI-classified |
| `LetterboxItem` | `letterbox_items` | Physical letters, OCR extracted |
| `CSROpportunity` | `csr_opportunities` | CSR matching results |
| `NewsItem` | `news_items` | Constituency news cache |

---

## API Structure

- `GET/POST /api/*` → `api_router.py` — MP-facing endpoints (JWT required)
- `GET/POST /admin/*` → `admin_api.py` — Admin endpoints (admin JWT required)
- `GET/POST /whatsapp/webhook` → `main.py` — Meta webhook (HMAC validated, no JWT)

---

## Deployment

Deployed on **Railway** — three services auto-deploy on push to `main`:

| Service | Root Dir | Builder |
|---|---|---|
| Backend API | `/` | Dockerfile |
| MP Frontend | `/frontend` | Railpack (Next.js) |
| Admin Frontend | `/admin` | Railpack (Next.js) |

**Before deploying to production**, run through `DEPLOYMENT_GUIDE.md`:
1. Rotate all credentials (OpenAI, Gemini, Meta, JWT secret)
2. Validate all env vars with `scripts/security_startup_check.py`
3. Run bcrypt password migration
4. Confirm `.env` is not in git history

---

## Data Files

Static JSON loaded at startup (not in DB):
- `modules/data/csr_db.json` — CSR opportunities database
- `modules/data/schemes_db.json` — Government schemes (1500+)
- `modules/data/fund_intel.json` — Fund intelligence
- `tenant_overrides.json` — WhatsApp number → tenant ID overrides
- `modules/constituency_library/` — Regional constituency data

---

## AI Integration Notes

- **GPT-4o-mini** (`sansadx_backend/ai_engine.py`): Grievance classification, multi-language support
- **Gemini** (`core/gemini_client.py`): Singleton client. Used for letter drafting, letterbox OCR, copilot research
- AI prompts are in `sansadx_backend/prompts.py` and `modules/drafter.py`
- Grievance taxonomy is defined in `sansadx_backend/taxonomy.json`

---

## Branch & Git Notes

- Production deploys from `main` (Railway watches this branch)
- Development branch convention: `claude/<feature>-<id>`
- Git user configured as `Claude (noreply@anthropic.com)` in this environment
