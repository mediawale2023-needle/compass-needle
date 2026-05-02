# Compass Needle — Parliamentary Intelligence Platform

AI-powered constituency management system for Members of Parliament.

Citizens send grievances via WhatsApp → AI categorises & routes them → MPs manage cases, draft responses, and track constituency health from a web dashboard.

---

## Architecture

```
 ┌─────────────────┐        ┌───────────────────┐        ┌──────────────────┐
 │  WhatsApp        │──────▶ │  FastAPI Backend   │ ◀───── │  MP Dashboard    │
 │  (Meta Cloud)    │        │  (Python 3.11)     │        │  (Next.js 15)    │
 └─────────────────┘        └────────┬──────────┘        └──────────────────┘
                                     │                            ▲
                              ┌──────▼──────────┐        ┌───────┴──────────┐
                              │  PostgreSQL      │        │  Admin Dashboard  │
                              │  (Railway)       │        │  (Next.js 15)     │
                              └─────────────────┘        └──────────────────┘
```

| Service | Tech | Deployment |
|---------|------|------------|
| Backend API | FastAPI + Uvicorn | Railway (Dockerfile) |
| MP Dashboard | Next.js 15 + Tailwind | Railway (Railpack) |
| Admin Dashboard | Next.js 15 + Tailwind | Railway (Railpack) |
| Database | PostgreSQL 15 | Railway managed |
| WhatsApp | Meta Cloud API v21.0 | Webhook at `/whatsapp/webhook` |
| AI — Grievance Engine | OpenAI GPT-4o-mini | JSON mode, multi-language |
| AI — Research & Drafting | Google Gemini | Document analysis, letter drafting |

---

## Features

### MP Dashboard

| Module | Description |
|--------|-------------|
| **Dashboard** | Case stats, category breakdown, red zones, constituency news, Parliament status |
| **Letterbox** | Inbound/outbound physical letter management with Gemini Vision OCR |
| **Briefcase** | WhatsApp grievance cases — full detail modal with status actions (resolve, escalate, close) |
| **Research Desk** | Upload documents, get AI-powered intelligence briefings, chat with context |
| **Drafter** | Generate constituency letters, Parliament questions, speeches, PMB drafts |
| **Schemes** | Search 1500+ govt schemes filtered by ministry, category, beneficiary type |
| **CSR Intelligence** | Live grievance clusters → CSR company matching → DPR generation |
| **Archives** | Saved drafts and research history |
| **Settings** | MP profile, language preferences, theme selection |

### Admin Dashboard

| Module | Description |
|--------|-------------|
| **Command Centre** | MP cards, system-wide stats |
| **Create MP** | Tenant + user + profile provisioning |
| **Profiles** | Edit MP identity, drafter config, key facts |
| **Geography** | Upload polling station data, manage constituency mappings |
| **Override Rules** | Location → assembly constituency override rules |
| **Intelligence** | Platform health, case explorer, analytics |
| **Settings** | Admin password, manage editors |

---

## Project Structure

```
compass-needle/
├── main.py                     # FastAPI entry point + WhatsApp webhook
├── api_router.py               # MP-facing REST API (1400+ lines)
├── admin_api.py                # Admin REST API (1100+ lines)
│
├── sansadx_backend/
│   ├── db.py                   # Unified DB engine, ORM models, connection pooling
│   ├── ai_engine.py            # OpenAI GPT-4o-mini integration + geography context
│   └── prompts.py              # System prompts & grievance taxonomy
│
├── core/
│   ├── gemini_client.py        # Gemini AI singleton client
│   ├── db_helpers.py           # Query helpers (_q, _q_one, _parse_meta)
│   ├── rate_limiter.py         # SlowAPI rate limiting config
│   ├── security_config.py      # CORS, JWT, headers, password policy
│   └── security_logger.py      # Security event logging
│
├── modules/
│   ├── auth.py                 # JWT auth, tenant extraction, input sanitisation
│   ├── geography_resolver.py   # Location → assembly constituency mapping
│   ├── csr_pipeline.py         # CSR opportunity matching engine
│   ├── schemes_api.py          # 1500+ government schemes search
│   ├── letterbox.py            # Physical letter management
│   └── ...                     # News intel, CSR modules, fund intel
│
├── frontend/                   # MP Dashboard (Next.js 15)
│   ├── app/
│   │   ├── page.js             # Login
│   │   └── dashboard/          # Protected routes (9 pages)
│   ├── components/             # Sidebar, UI components
│   └── lib/
│       ├── api.js              # API client with JWT, retry, timeout
│       └── auth.js             # Auth context provider
│
├── admin/                      # Admin Dashboard (Next.js 15)
│   ├── app/
│   │   └── dashboard/          # Admin-only protected routes
│   └── lib/
│       ├── api.js              # Admin API client
│       └── auth.js             # Admin auth context
│
├── data/
│   └── geography/              # Polling station JSON files per constituency
│
├── Dockerfile                  # Backend container (Python 3.11-slim)
├── docker-compose.yml          # Local dev: Postgres + FastAPI + both Next.js dashboards
├── requirements.txt            # Python dependencies (pinned versions)
└── tenant_overrides.json       # WhatsApp number → tenant mapping
```

---

## Environment Variables

### Backend (Railway)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `JWT_SECRET` | ✅ | Token signing key (min 32 chars) |
| `OPENAI_API_KEY` | ✅ | GPT-4o-mini for grievance classification |
| `GEMINI_API_KEY` | ✅ | Gemini for copilot, drafter, letterbox OCR |
| `WHATSAPP_PHONE_NUMBER_ID` | ✅ | Meta WhatsApp Business phone number ID |
| `META_ACCESS_TOKEN` | ✅ | Meta permanent System User token |
| `META_VERIFY_TOKEN` | ✅ | Webhook verification token (you define it) |
| `META_APP_SECRET` | ✅ | Meta App Secret (for webhook signature validation) |
| `SENTRY_DSN` | Optional | Error monitoring |

### Frontends (Railway)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | ✅ | Backend URL (e.g. `https://needle-backend.up.railway.app`) |

---

## Database Models

| Model | Table | Purpose |
|-------|-------|---------|
| `Tenant` | `tenants` | MP organisation (name, constituency, WhatsApp number) |
| `User` | `users` | Credentials & roles (mp, admin, sysadmin, editor) |
| `Case` | `cases` | Citizen grievances from WhatsApp |
| `LetterboxItem` | `letterbox` | Physical letter records (inbound/outbound) |
| `TenantProfile` | `tenant_profiles` | MP identity, party, key facts, languages |
| `Archive` | `archives` | Saved drafts (letters, questions, speeches) |
| `DNASample` | `dna_samples` | Writing style templates |
| `ActivityHistory` | `activity_history` | User activity audit log |

---

## Core Flows

### WhatsApp Grievance Intake
```
Citizen sends WhatsApp message
  → Meta Cloud API forwards to POST /whatsapp/webhook
  → X-Hub-Signature-256 validated (HMAC-SHA256)
  → Tenant lookup (display_phone_number → DB)
  → AI Engine categorises (GPT-4o-mini, multi-language)
  → Geography resolution (location → assembly constituency)
  → Case saved to PostgreSQL
  → AI-generated response sent back to citizen
```

### MP Dashboard
```
MP logs in → JWT issued (8h expiry) → Dashboard loads
  → Briefcase: Grievance cases with detail modal + status actions
  → Letterbox: Physical letters with OCR via Gemini Vision
  → Drafter: AI-generated letters, speeches, PMBs, Parliament questions
  → Research Desk: Upload & analyse documents, chat with context
  → Schemes: Search 1500+ government schemes
  → CSR Intelligence: Live grievance-to-CSR matching + DPR generation
```

---

## Security

| Feature | Implementation |
|---------|---------------|
| Authentication | JWT (HS256, 8h expiry, 32-char+ secret enforced at startup) |
| Password hashing | bcrypt only — non-bcrypt hashes rejected |
| Role-based access | mp, admin, super_admin, sysadmin, editor |
| Webhook security | Meta X-Hub-Signature-256 HMAC validation |
| Rate limiting | Login: 5/min, AI: 3/min, Webhook: 20/min (SlowAPI) |
| SQL injection | Parameterised queries only (SQLAlchemy `text()` binds) |
| Error handling | Generic API responses — no `str(e)` leaks |
| Security headers | X-Frame-Options, X-Content-Type-Options, XSS protection |
| Multi-tenant isolation | All queries scoped by `tenant_id` from JWT |
| Production guard | `RuntimeError` if `DATABASE_URL` missing — no SQLite fallback |
| AI prompt safety | Input sanitisation + `<document_content>` tags for injection defence |
| Monitoring | Sentry integration (optional) |

---

## Local Development

### Backend
```bash
pip install -r requirements.txt

export DATABASE_URL="postgresql://user:pass@localhost:5432/needle_db"
export JWT_SECRET="your-secret-key-at-least-32-characters"
export OPENAI_API_KEY="sk-..."
export GEMINI_API_KEY="..."

uvicorn main:app --reload --port 8000
```

### MP Dashboard
```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev    # → http://localhost:3000
```

### Admin Dashboard
```bash
cd admin
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev    # → http://localhost:3001
```

---

## Deployment (Railway)

Three services from the same GitHub repo, auto-deploy on push to `main`:

| Service | Root Directory | Builder |
|---------|---------------|---------|
| Backend | `/` | Dockerfile |
| MP Frontend | `/frontend` | Railpack |
| Admin Frontend | `/admin` | Railpack |

### Production Smoke Test

After a Railway deploy, run the bundled smoke test instead of checking only the home page:

```bash
export BACKEND_URL="https://needle-backend.up.railway.app"
export MP_URL="https://compass-needle-production.up.railway.app"
export ADMIN_URL="https://admin-production.up.railway.app"
export MP_USERNAME="..."
export MP_PASSWORD="..."
export ADMIN_USERNAME="..."
export ADMIN_PASSWORD="..."
export META_APP_SECRET="..."
export TEST_SENDER="919999999999"
export WA_DISPLAY_NUMBER="15551636821"

./scripts/railway_smoke_test.sh
```

The script checks backend health, both frontends, MP login, admin login, signed webhook intake, case visibility, outbound notify, bad-signature rejection, and malformed JSON handling.

---

## License

Proprietary — MediaWale 2023. All rights reserved.
