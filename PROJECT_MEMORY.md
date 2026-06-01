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
- Primary account identity is now split across `tenants.tenant_type` and `users.role`: new top-level customer accounts are created with `role='owner'` and a `tenant_type` of `mp`, `mla`, or `aspirant`, while older `role='mp'` tenants remain supported for backward compatibility.
- Auth payloads now expose `tenant_type` to the MP frontend, and primary-account checks should treat both `owner` and legacy `mp` roles as equivalent until the full migration is complete.
- The MP frontend now centralizes account/session interpretation in `frontend/lib/account.js`; new UI gating and account labels should reuse those helpers instead of re-implementing role checks inline.
- Session payloads from `/api/auth/login` and `/api/auth/me` now include `tenant_type`, `is_primary_account`, and `account_label`, which are the preferred frontend contract for account-aware behavior.
- Feature locking is now tenant-type-aware: aspirant accounts must be blocked from `Sansad AI` and `Convergence` in both frontend navigation/routes and backend API handlers, while core modules like Briefcase, Letterbox, Drafter, and Schemes remain available.
- `frontend/lib/account.js` now owns the feature-level access helpers (`canAccessSansadAI`, `canAccessConvergence`); use those instead of broad “MP-only” role checks when adding or editing gated UI.
- Primary-account identity has now been normalized further into two axes on `tenants`: `account_stage` (`aspirant` or `elected`) and `seat_type` (`mp` or `mla`). Keep `users.role` for permissions (`owner`, `staff`, `admin`) and treat legacy `tenant_type` as a backward-compatibility shim rather than the future source of truth.
- Shared geography is now seat-scoped rather than tenant-scoped. Persist base geography rows once per seat using keys like `mp:<seat>/<assembly>` or `mla:<seat>/<assembly>`, allow multiple tenants to reference the same seat, and keep only generated `geo_override` / `geo_alias` rows tenant-specific.
- Same-seat rivals are now a supported model: multiple aspirants and an elected office can share one constituency/seat safely as long as tenant-owned data remains filtered by `tenant_id` and any geography/bootstrap helper uses `tenant_id -> seat` instead of `seat -> tenant_id`.
- The admin geography workflow is now seat-aware at the UI layer too: `admin/app/dashboard/geography/page.js` lets operators choose `MP Seat` vs `MLA Seat`, stores shared geography through the existing global admin routes using `seat_type` query parameters, and shows saved geography grouped by seat rather than assuming every record is a Lok Sabha constituency.
- The launch-readiness `Configure geography` action now routes to the dedicated geography page with `tenant_id` context. In tenant-aware mode, the geography page should prefill the account seat, offer a first-class `reuse existing shared seat geography` path for rival/same-seat accounts, and only fall back to PDF upload when no suitable shared seat geography exists yet.
- Admin overview and geography/rules copy should now prefer `account`, `tenant`, and `seat` language over `MP`-only phrasing unless a page is truly parliamentary-only.
- Shared seat geography fan-out is now covered by backend tests: `auto_generate_overrides()` must create separate `geo_override` rows for every tenant on the same seat without leaking MLA-seat geography into MP-seat tenants.
- Admin staff management must never treat primary political accounts as ordinary staff. `owner` and legacy `mp` users are now excluded from `/api/admin/staff` and blocked from staff suspend/reassign/edit flows; staff tooling is for non-primary tenant users only.
- The ORM `User` model now explicitly includes `phone`, matching the existing migration and the live staff/WhatsApp features. Future user-facing phone work should rely on the ORM field rather than assuming it exists only via raw SQL migrations.
- Updating a tenant constituency through the admin constituency endpoint must keep `users.constituency`, `tenants.constituency`, and `tenant_profiles.constituency` aligned so tenant-aware flows like geography reuse and readiness checklists do not drift across tables.
- `modules/geography_resolver.py` must keep three location-matching safeguards in place: MLA tenant assembly names should be resolved up to their parent parliamentary constituency for `scope_parliamentary` filtering, fuzzy keyword matching should stay at the narrower-but-usable `>93` threshold for Indian spelling variants, and newline-separated locality strings should seed each line independently so prefixes like `Nath Pai Circle` remain directly matchable.
- The geography resolver index is now seat-aware internally: assembly buckets are keyed by `seat_type + seat_name + assembly`, and tenant-scoped resolution should prefer the tenant's own seat context over broad parliamentary-string filtering. This avoids collisions when different seats reuse the same assembly name.
- Legacy override bulk saves in `save_overrides_to_db()` must never wipe shared geography or generated alias rows. Only `phone_mapping` and `geo_override` rows are safe to replace wholesale; `geography_data` and `geo_alias` rows are durable shared assets.
- Geography onboarding now has two tiers of validation: weak coverage remains a warning in the returned validation payload, while generated alias collisions against another assembly on the same seat are blocking errors and must stop the save. New save paths should surface `validation.blocking_errors` instead of silently accepting dangerous shared-seat ambiguity.
- WhatsApp geography decisions now persist structured `geography_diagnostics` inside `case_metadata`, including attempted resolution sources, tenant scope, match type/confidence, rejected AI assemblies, and final resolved/unresolved state. Future ops/debug tooling should read that field before inferring why a case stayed blank.
- Historical blank geography is now repairable through `scripts/backfill_case_geography.py`, which is intentionally tenant-scoped and fills blank `location` / `assembly` values from the raw message while also writing backfill diagnostics into `case_metadata`.
- The WhatsApp ingestion wrapper in `main.py` must stay signature-aligned with `modules/whatsapp_geography.finalize_geography_decision()`. A mismatch on `location_required` caused live tenant cases to save without geography even though tenant aliases and the resolver were healthy.
- The aspirant-facing UI copy direction is now `workspace`/`team` oriented rather than `MP office` oriented. High-visibility MP frontend surfaces such as Settings, schedule cards, and Briefcase triage notes should prefer labels like `Your profile`, `Workspace details`, `Role / Position`, `Team`, and `Constituency Workspace` when the copy does not need to imply elected authority.
- A second UI-only wording pass extended that same direction into fallback labels and helper text: avoid defaults like `MP`, `Member`, `PA / Staff`, or `MP Office` on shared workspace screens unless the feature is specifically parliamentary or elected-office only.

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
- The dashboard's press widget should preserve the older tenant-aware `Media Centre` behavior: separate `National` and `Local` feeds, both fetched in parallel from `/api/news`, with the local feed remaining driven by the current tenant's profile (`tenant_id`, languages, state, and constituency aliases) rather than any hardcoded constituency.
- Dashboard mobile responsiveness should preserve the same desktop information architecture as much as possible. Preferred tactics are grid collapse, wrapped controls, tighter spacing, and horizontal overflow for dense tables rather than separate phone-only alternate layouts.
- The dashboard constituency map is no longer purely mocked for supported seats. Real seat outlines now live under `frontend/public/maps/<seat_type>/`, and `frontend/lib/constituency-map-data.js` maps `(seat_type, constituency)` plus locality aliases to hotspot anchor positions. `DashboardConstituencyMap.jsx` should prefer that seat-aware real-outline path and fall back to the legacy mock only when no seat asset/config exists yet.

## Briefcase Refactor Memory

- The Briefcase page lives at `frontend/app/dashboard/sansadx/page.js` and remains behavior-heavy, with live case editing, escalation, contact management, polling, and URL-synced filters.
- The first Briefcase structural extraction moved the embedded modal/viewer stack into `frontend/components/briefcase/`: shared tabs/status helpers, contact panel, escalation modal, source media viewer, and case modal.
- The next Briefcase refactor pass moved fetch, polling, filter, pagination, and bulk-action orchestration into `frontend/hooks/useBriefcaseCases.js`, leaving the route page primarily as a composition layer.
- Reusable Briefcase view sections now live under `frontend/components/briefcase/` for the header, filters, active-filter chips, bulk actions, clusters view, deleted cases view, cases table, and pagination.
- Sidebar naming now treats `/dashboard/sansadx` as `Briefcase` and `/dashboard/letterbox` as `Letterbox`, so future copy changes should preserve that naming across the MP frontend.
- The current Briefcase redesign direction is based on the `Needle-2.zip` prototype, using the `Needs you` triage screen as the default live state and borrowing the selected-state treatment from the `All cases` artboard.
- The live Briefcase page now uses a triage-first composition with prototype-inspired header, KPI strip, promoted-clusters banner, status tabs, two-row filter toolbar, editorial table styling, and dark-green bulk action bar while keeping the existing backend APIs and case workflows intact.
- Briefcase now defaults back to `All cases`, and the `Others` tab is restored as a first-class bucket using the backend-supported `bucket=other` filter for greetings, spam/offensive messages, and personal/request-style cases.
- `Needs you` is no longer a Briefcase tab. That concept now remains only as a triage metric, while the actual Briefcase tabs are `All cases`, `New`, `In progress`, `Resolved`, `Others`, plus the auxiliary `Clusters` and `Deleted`.
- The shared dashboard chrome should not stack its own route header above the page-level Briefcase header. On `/dashboard/sansadx`, only the Briefcase header should render; the generic “Operations Dashboard” header is suppressed there.
- The attempted mobile-specific Briefcase layouts were reverted on 2026-05-26. The preferred responsive direction is to preserve the desktop structure and visual hierarchy on mobile as much as possible, using wrapping, narrower spacing, and stacked controls only where necessary rather than introducing separate phone-only card layouts.

## Open Memory Items

- Add durable architecture or module-specific lessons here as we learn them.

## Citizen Intake Memory

- WhatsApp citizen intake now follows an `ack first, clarify later` rule: even when a case is missing location or is otherwise incomplete, the first reply should stay a normal acknowledgment instead of immediately asking follow-up questions.
- Missing-location and missing-details clarification now use delayed follow-ups driven by case metadata (`clarification_follow_up_*`) and background timers/startup sweeps, rather than sending the clarification inline during the original webhook request.
- Clarification replies from the same citizen should enrich the original recent incomplete case instead of creating a second case row; the intake flow now treats recent clarification-pending cases as update targets.
- Case enrichment now persists `detected_language` into `case_metadata` (`detected_language` and legacy `language`) so UI surfaces do not have to infer citizen language from raw text on every render.
- Historical language gaps can be repaired with `scripts/backfill_case_languages.py`, which is tenant-scoped and only backfills rows whose stored language is missing or clearly a bad default-English label compared to the case text.

## Media Intake Memory

- WhatsApp voice-note transcription now prefers Sarvam STT (`core/sarvam_client.py`) for `media_type="audio"` and falls back to the older Gemini multimodal normalization only when Sarvam is unavailable. Image and document normalization remain Gemini-backed.
- Voice-note intake is now two-stage: Sarvam produces the raw transcript, then `modules/voice_note_normalizer.py` uses tenant-scoped geography candidates plus Gemini cleanup to create a safer normalized complaint text before the normal grievance pipeline sees it. Keep both `raw_transcript` and `normalized_text` available in media metadata for audit/debug.

## Classification Memory

- `sansadx_backend/unified_taxonomy.py` now includes a narrow high-confidence override for official-corruption complaints: if the text clearly combines bribery/corruption or payment-demand semantics with office-official context (`talathi`, `patwari`, `tehsildar`, `babu`, etc.), taxonomy normalization must force `Bureaucratic / Administrative -> Bribery/Corruption` even if the model guessed a generic infrastructure/roads label. Keep this override structural and cross-language rather than tied to one exact sentence or script.

## API Contract Memory

- Case-facing timestamps from `api_router.py` should be emitted as explicit UTC ISO strings with a trailing `Z`, even when the underlying DB values are naive UTC datetimes or SQLite-style datetime strings. Frontend age/date widgets like Briefcase `received` should not have to guess timezone semantics from raw case timestamps.
