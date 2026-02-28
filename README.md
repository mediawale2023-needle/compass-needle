# Needle — Parliamentary Intelligence Platform

AI-powered constituency management system for Members of Parliament.

Citizens send grievances via WhatsApp → AI categorizes & routes them → MPs manage cases from a web dashboard.

---

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  WhatsApp        │────▶│  FastAPI Backend  │◀────│  MP Dashboard    │
│  (Twilio)        │     │  (Python)         │     │  (Next.js)       │
└─────────────────┘     └──────┬───────────┘     └──────────────────┘
                               │                          ▲
                               │                          │
                        ┌──────▼───────────┐     ┌───────┴──────────┐
                        │  PostgreSQL       │     │  Admin Dashboard  │
                        │  (Railway)        │     │  (Next.js)        │
                        └──────────────────┘     └──────────────────┘
```

| Service | Tech | URL |
|---------|------|-----|
| Backend API | FastAPI + Python 3.11 | `needle-backend.up.railway.app` |
| MP Dashboard | Next.js 15 | `needle-frontend.up.railway.app` |
| Admin Dashboard | Next.js 15 | `needle-admin.up.railway.app` |
| Database | PostgreSQL | Railway managed |
| WhatsApp | Twilio Webhook | `/whatsapp/webhook` |
| AI Engine | OpenAI GPT-4 | Via API |

---

## Project Structure

```
compass-needle/
├── main.py                    # FastAPI entry point, WhatsApp webhook
├── api_router.py              # MP-facing REST API (1200 lines)
├── admin_api.py               # Admin REST API (1040 lines)
├── sansadx_backend/
│   ├── db.py                  # Unified DB models & engine (single source of truth)
│   ├── ai_engine.py           # OpenAI integration & geography context
│   └── prompts.py             # System prompts & taxonomy
├── db.py                      # Compatibility shim (re-exports from sansadx_backend/db.py)
├── modules/
│   ├── geography_resolver.py  # Polling station → Assembly Constituency mapping
│   ├── drafter.py             # Letter/speech/PMB drafting engine
│   ├── copilot.py             # AI document analysis & chat
│   ├── case_intelligence.py   # Case analytics & platform health
│   ├── news_intel.py          # News aggregation (national + constituency)
│   ├── sansadx.py             # Sansad TV integration
│   ├── constituencies.py      # 543 Lok Sabha constituencies list
│   ├── persistence.py         # Archives & DNA samples
│   ├── profile_loader.py      # Tenant profile management
│   └── ...                    # CSR modules, settings, translator
├── frontend/                  # MP Dashboard (Next.js)
│   ├── app/
│   │   ├── page.js            # Login
│   │   └── dashboard/         # Protected routes
│   │       ├── page.js        # Overview (cases, stats, charts)
│   │       ├── drafter/       # Letter & speech drafting
│   │       ├── copilot/       # AI document analysis
│   │       ├── csr/           # CSR project discovery
│   │       ├── archives/      # Saved drafts
│   │       ├── sansadx/       # Parliament TV
│   │       └── settings/      # Profile & preferences
│   └── lib/
│       ├── api.js             # API client with JWT auth
│       └── auth.js            # Auth context provider
├── admin/                     # Admin Dashboard (Next.js)
│   ├── app/
│   │   ├── page.js            # Admin login
│   │   └── dashboard/
│   │       ├── page.js        # Overview (MP cards, stats)
│   │       ├── mps/new/       # Create MP
│   │       ├── profiles/      # Edit MP profiles
│   │       ├── geography/     # Upload polling station data
│   │       ├── rules/         # Geography override rules
│   │       ├── intelligence/  # Case analytics (3 views)
│   │       └── settings/      # Admin password & editors
│   └── lib/
│       ├── api.js             # Admin API client
│       └── auth.js            # Admin auth context
├── data/
│   └── geography/             # Polling station JSON files per constituency
├── Dockerfile                 # Backend Docker build
├── requirements.txt           # Python dependencies
└── tenant_overrides.json      # WhatsApp number → tenant mapping
```

---

## Environment Variables

### Backend (Railway)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `JWT_SECRET` | ✅ | Token signing key (min 32 chars) |
| `OPENAI_API_KEY` | ✅ | GPT-4 API access |
| `TWILIO_ACCOUNT_SID` | ✅ | WhatsApp messaging |
| `TWILIO_AUTH_TOKEN` | ✅ | WhatsApp auth |
| `TWILIO_WHATSAPP_NUMBER` | ✅ | Twilio sandbox/number |
| `SENTRY_DSN` | Optional | Error monitoring |

### Admin Dashboard (Railway)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | ✅ | Backend URL (e.g. `https://needle-backend.up.railway.app`) |

### MP Dashboard (Railway)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | ✅ | Backend URL |

---

## Database Models

| Model | Table | Purpose |
|-------|-------|---------|
| `Tenant` | `tenants` | MP organization (name, constituency, WhatsApp number) |
| `User` | `users` | Credentials & roles (mp, admin, sysadmin, editor) |
| `Case` | `cases` | Citizen grievances from WhatsApp |
| `TenantProfile` | `tenant_profiles` | MP identity, party, key facts, languages |
| `Archive` | `archives` | Saved drafts |
| `DNASample` | `dna_samples` | Writing style templates |
| `ActivityHistory` | `activity_history` | User activity log |

---

## Core Flows

### WhatsApp Grievance Intake
```
Citizen sends WhatsApp message
  → Twilio forwards to /whatsapp/webhook
  → Tenant lookup (JSON overrides → DB fallback)
  → AI Engine categorizes (GPT-4)
  → Geography resolution (location → assembly constituency)
  → Case saved to database
  → AI-generated response sent to citizen
```

### MP Dashboard
```
MP logs in → JWT issued → Dashboard loads
  → Cases (filter by status, category, constituency)
  → Drafter (letters, speeches, PMBs, questions)
  → Copilot (upload & analyze documents)
  → News (national + constituency-level)
  → CSR (project discovery & proposals)
```

### Admin Dashboard
```
Admin logs in → JWT issued → Command Center loads
  → Create/manage MPs (tenant + user + profile)
  → Edit profiles (identity, drafter config)
  → Upload geography (polling station PDFs)
  → Override rules (location → constituency mapping)
  → Case Intelligence (health, explorer, analytics)
  → Manage editors & settings
```

---

## Local Development

### Backend
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://..."
export JWT_SECRET="your-secret-key-at-least-32-chars"
export OPENAI_API_KEY="sk-..."

# Run
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

The project runs as **3 Railway services** from the same GitHub repo:

1. **Backend** — Root directory: `/`, Builder: Dockerfile
2. **MP Frontend** — Root directory: `/frontend`, Builder: Railpack
3. **Admin Frontend** — Root directory: `/admin`, Builder: Railpack

Each service auto-deploys on push to `main`.

---

## Security

- JWT-based authentication (separate tokens for MP and admin)
- bcrypt password hashing (no plaintext storage)
- Role-based access control (mp, admin, super_admin, sysadmin, editor)
- Sentry error monitoring (optional)

---

## License

Proprietary — MediaWale 2023. All rights reserved.
