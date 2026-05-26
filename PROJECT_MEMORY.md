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
- A console-first editorial redesign for the MP dashboard was attempted and then reverted on 2026-05-26; future redesign work should be staged more incrementally and visually verified before push.

## Dashboard Refactor Memory

- The current dashboard refactor started by extracting shared dashboard tokens into `frontend/lib/dashboard-theme.js`.
- Reusable dashboard primitives now live under `frontend/components/dashboard/`, starting with `DashboardMiniBars`, `DashboardDonut`, `DashboardSectionFrame`, and `DashboardStatusBadge`.
- The current `frontend/app/dashboard/page.js` still contains major feature sections, but it now consumes shared theme/primitives instead of owning all chart and status rendering directly.
- The second refactor batch extracted the dashboard feature sections into dedicated components: KPI tiles, grievance queue, workload card, engagements card, letters card, press card, activity feed, constituency map, and empty state.
- `frontend/app/dashboard/page.js` is now primarily a data-fetching and composition layer for the overview screen.
- The third refactor batch moved overview request orchestration into `frontend/hooks/useDashboardOverview.js` and raw response normalization into `frontend/lib/dashboard-mappers.js`.
- The dashboard overview page is now mostly a thin container for auth checks, navigation handlers, and component composition.
- Final review fixes removed nondeterministic KPI chart rendering and hardened initial loading state so the overview no longer risks hydration drift or a false empty-state flash while cases are still loading.

## Briefcase Refactor Memory

- The Briefcase page lives at `frontend/app/dashboard/sansadx/page.js` and remains behavior-heavy, with live case editing, escalation, contact management, polling, and URL-synced filters.
- The first Briefcase structural extraction moved the embedded modal/viewer stack into `frontend/components/briefcase/`: shared tabs/status helpers, contact panel, escalation modal, source media viewer, and case modal.
- The next Briefcase refactor pass moved fetch, polling, filter, pagination, and bulk-action orchestration into `frontend/hooks/useBriefcaseCases.js`, leaving the route page primarily as a composition layer.
- Reusable Briefcase view sections now live under `frontend/components/briefcase/` for the header, filters, active-filter chips, bulk actions, clusters view, deleted cases view, cases table, and pagination.
- Sidebar naming now treats `/dashboard/sansadx` as `Briefcase` and `/dashboard/letterbox` as `Letterbox`, so future copy changes should preserve that naming across the MP frontend.

## Open Memory Items

- Add durable architecture or module-specific lessons here as we learn them.
