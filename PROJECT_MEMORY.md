# Project Memory

This file is the persistent working memory for Compass Needle. Read it before making code changes.

## How To Use

- Update this file when a decision, rule, or project insight is likely to matter again.
- Keep entries short, concrete, and durable.
- Do not use this file for temporary scratch notes; put those in `TASK_LOG.md` or the active discussion.

## Current Operating Protocol

- Read `AGENTS.md`, this file, and `TASK_LOG.md` before making code changes.
- Share a pre-change summary with the user and wait for confirmation before editing code.
- After every completed change, update this file if the change introduced durable knowledge.
- After every GitHub push, make sure `TASK_LOG.md` reflects what was pushed and update this file if the push captured a durable project decision.

## Architecture Memory

- Backend API lives at repo root with FastAPI entrypoints in `main.py`, `api_router.py`, and `admin_api.py`.
- MP frontend lives in `frontend/` and admin frontend lives in `admin/`, both using Next.js 15 and React 19.
- The platform is multi-tenant. Every data access path must preserve `tenant_id` isolation.
- Production source of truth is AWS EC2 for backend/Postgres and Vercel for both frontends.

## Safety Rules Worth Rechecking

- Never bypass JWT, bcrypt-only auth, webhook signature validation, rate limits, or tenant scoping.
- Never build raw SQL from user input. Use bound parameters.
- Never expose raw internal errors in API responses.
- Treat WhatsApp, AI classification, and case query flows as high-impact surfaces because regressions are user-visible quickly.

## Fragile Or High-Risk Areas

- `main.py`: startup behavior, webhook handling, and background worker wiring can affect ingestion reliability.
- `api_router.py` and `admin_api.py`: large surface areas with auth and tenant-isolation risk.
- `sansadx_backend/db.py`: model changes can ripple into multiple dashboards and workflows.
- `modules/case_query_*`: natural-language query parsing and formatting are tightly coupled to live WhatsApp usage.
- `modules/whatsapp.py`: outbound messaging issues are operationally sensitive.

## Known Process Decision

- This repository now follows a discuss-first workflow: inspect, summarize, confirm, then edit.
- This repository also follows a memory-maintenance workflow: after each completed change and each GitHub push, update the repo memory files.

## Frontend Design Memory

- The MP dashboard redesign direction now uses a console-first editorial style inspired by the Claude prototype in `Needle.zip`.
- The first implementation pass intentionally changes only the shared MP dashboard chrome and `/dashboard` overview page, while preserving existing API wiring and page behavior.
- The visual language introduced in the MP frontend uses warm ivory paper surfaces, Ashoka green primary accents, saffron highlights, serif display typography, and mono metadata labels.

## Open Memory Items

- Add durable architecture or module-specific lessons here as we learn them.
