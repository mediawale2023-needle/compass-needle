# Task Log

Chronological log of completed repository work. Read before making changes to understand recent context.

## Entry Template

- Date: YYYY-MM-DD
- Request:
- Summary:
- Files touched:
- Risks or follow-ups:

## Entries

- Date: 2026-06-01
- Request: Implement Phase 3 of the constituency-map architecture.
- Summary: Added DB-backed seat map manifest storage via the new `seat_map_manifests` model, upgraded `modules/seat_maps.py` to prefer admin-managed manifests over repo fallback, and introduced admin APIs to list, fetch, and upsert seat maps without requiring dashboard code changes. Added tests proving tenant map lookup still works and that an admin-upserted manifest overrides the repo default for the same seat key. Verified with `venv/bin/python -m pytest tests/test_dashboard_map_manifest_api.py -q`, `venv/bin/python -m py_compile sansadx_backend/db.py modules/seat_maps.py api_router.py admin_api.py tests/test_dashboard_map_manifest_api.py`, and `npm run test --prefix frontend -- --run tests/dashboard.test.jsx`.
- Files touched: `sansadx_backend/db.py`, `modules/seat_maps.py`, `admin_api.py`, `tests/test_dashboard_map_manifest_api.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The storage/control plane is ready, but there is still no admin UI for editing these manifests. Phase 4 should build a lightweight admin screen over `/api/admin/seat-maps` and eventually support asset upload/validation workflows rather than requiring raw JSON payloads.

- Date: 2026-06-01
- Request: Build Phase 2 of the constituency-map architecture.
- Summary: Added a tenant-safe backend seat-manifest contract at `/api/maps/seat-manifest`, backed by the new `modules/seat_maps.py` loader over the shared frontend map registry/manifests. Updated the dashboard overview hook to fetch the manifest from the API and pass it into the map renderer, while keeping the local manifest loader as a fallback. Added backend contract tests and refreshed the dashboard frontend test. Verified with `venv/bin/python -m pytest tests/test_dashboard_map_manifest_api.py -q`, `venv/bin/python -m py_compile api_router.py modules/seat_maps.py tests/test_dashboard_map_manifest_api.py`, and `npm run test --prefix frontend -- --run tests/dashboard.test.jsx`.
- Files touched: `modules/seat_maps.py`, `api_router.py`, `frontend/hooks/useDashboardOverview.js`, `frontend/app/dashboard/page.js`, `frontend/components/dashboard/DashboardConstituencyMap.jsx`, `frontend/tests/dashboard.test.jsx`, `tests/test_dashboard_map_manifest_api.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Map manifests are still repo-backed and served through the backend; Phase 3 should move registry/manifest management into admin-facing workflows or DB-backed storage so new seats do not require code changes or app redeploys.

- Date: 2026-06-01
- Request: Start building the constituency-map architecture phase by phase.
- Summary: Implemented Phase 1 by formalizing the first live map into a generic seat-registry and seat-manifest structure. Added `frontend/data/maps/registry.json`, moved Belgaum Dakshin hotspot/asset metadata into `frontend/data/maps/mla/belgaum-dakshin.manifest.json`, and refactored `frontend/lib/constituency-map-data.js` into a manifest loader instead of a one-seat config blob. Verified with `npm run test --prefix frontend -- --run tests/dashboard.test.jsx`.
- Files touched: `frontend/data/maps/registry.json`, `frontend/data/maps/mla/belgaum-dakshin.manifest.json`, `frontend/lib/constituency-map-data.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This phase still uses a static in-frontend manifest registry; the next phase should move toward a backend/API seat-manifest contract so new constituencies do not require frontend code deploys.

- Date: 2026-06-01
- Request: Push the first real constituency-map implementation to GitHub.
- Summary: Pushed commit `c0dedf04` (`Build first real constituency map`) to `origin/main`, publishing the Belgaum Dakshin real-seat SVG, seat-aware hotspot config, and the dashboard fallback strategy for unmapped constituencies.
- Files touched: `frontend/components/dashboard/DashboardConstituencyMap.jsx`, `frontend/lib/constituency-map-data.js`, `frontend/public/maps/mla/belgaum-dakshin-outline.svg`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The live map currently has real coverage only for Belgaum Dakshin; additional constituencies should be added through the same generic asset-plus-anchor contract rather than new component logic.

- Date: 2026-06-01
- Request: Replace the mocked dashboard constituency map with a real Belgaum Dakshin outline and real hotspot placement.
- Summary: Added a seat-aware constituency map config layer, extracted a clean Belgaum Dakshin SVG outline into `frontend/public/maps/mla/`, and rewired `DashboardConstituencyMap.jsx` to place live `red_zones` hotspots against the real seat outline for supported constituencies while preserving the previous mock map as a fallback for unmapped seats. Verified with `npm run test --prefix frontend -- --run tests/dashboard.test.jsx`.
- Files touched: `frontend/components/dashboard/DashboardConstituencyMap.jsx`, `frontend/lib/constituency-map-data.js`, `frontend/public/maps/mla/belgaum-dakshin-outline.svg`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The first real map only covers Belgaum Dakshin and uses curated hotspot anchors rather than true ward polygons; additional seats should reuse the same asset-plus-anchor pattern, and a future step can replace anchor heuristics with polygon/centroid data where available.

- Date: 2026-06-01
- Request: Push the UTC case-timestamp serialization fix to GitHub.
- Summary: Pushed commit `aed0b630` (`Fix case timestamp UTC serialization`) to `origin/main`, publishing the explicit-UTC `Z` timestamp contract for Briefcase case APIs so frontend `received` ages no longer drift by local timezone offsets.
- Files touched: `api_router.py`, `tests/test_briefcase_api.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Production still needs a backend deploy/restart before live Briefcase rows pick up the corrected timestamp contract; other API surfaces may still need the same UTC pass if they serialize naive datetimes separately.

- Date: 2026-06-01
- Request: Fix Briefcase `received` ages that were drifting by about 5.5 hours because case timestamps were serialized without timezone information.
- Summary: Updated `api_router.py` so case-list/detail/export/media timestamps are normalized through `_coerce_iso()` into explicit UTC ISO strings with `Z`, including SQLite-style naive datetime strings in tests. Added Briefcase API assertions to lock the UTC contract and prevent frontend age drift from naive timestamp parsing.
- Files touched: `api_router.py`, `tests/test_briefcase_api.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This fixes the backend contract for affected case APIs; any remaining screens showing drift are likely consuming other endpoints that still need the same UTC serialization pass.

- Date: 2026-06-01
- Request: Push the case-language persistence and backfill batch to GitHub.
- Summary: Pushed commit `6c4e76a6` (`Persist and backfill case languages`) to `origin/main`, publishing detected-language persistence in case metadata, neutral Briefcase `UNK` fallback instead of fake `EN`, and the tenant-scoped language backfill script/tests.
- Files touched: `main.py`, `frontend/components/briefcase/briefcase-shared.jsx`, `scripts/backfill_case_languages.py`, `tests/test_case_language_backfill.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Existing rows still need the backfill script run per tenant; until then the UI will truthfully show `UNK` for missing-language historical cases instead of pretending they are English.

- Date: 2026-06-01
- Request: Fix Briefcase language badges that were showing `EN` for Marathi/Hinglish messages and add a backfill path for old cases.
- Summary: Persisted `detected_language` into case metadata during enrichment in `main.py`, changed the Briefcase language badge helper to show real mapped tags or `UNK` instead of defaulting missing values to English, and added `scripts/backfill_case_languages.py` plus focused tests to repair tenant-scoped historical rows whose language is missing or clearly mislabeled as English.
- Files touched: `main.py`, `frontend/components/briefcase/briefcase-shared.jsx`, `scripts/backfill_case_languages.py`, `tests/test_case_language_backfill.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Existing rows need the backfill script run per tenant to show corrected badges; the frontend now stops lying about missing values, so unbackfilled rows will surface as `UNK` until repaired.

- Date: 2026-06-01
- Request: Push the generalized official-corruption routing fix to GitHub.
- Summary: Pushed commit `1f81a5a0` (`Generalize corruption routing override`) to `origin/main`, publishing the structural cross-language override that rescues official bribery/payment-demand complaints into `Bureaucratic / Administrative -> Bribery/Corruption` instead of bad generic infrastructure labels.
- Files touched: `sansadx_backend/unified_taxonomy.py`, `tests/test_ai_location_grounding.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Production still needs a backend deploy/restart before live classifications pick up this generalized routing fix; future expansion should stay structural and not drift into brittle language-specific phrase hardcoding.

- Date: 2026-06-01
- Request: Fix wrong category routing for official-bribery complaints like `तलाठी पैसे मागत आहे`.
- Summary: Added a narrow high-confidence taxonomy override in `sansadx_backend/unified_taxonomy.py` so bribery or payment-demand semantics in official/revenue-office context now force `Bureaucratic / Administrative -> Bribery/Corruption` instead of falling back to bad generic infrastructure labels. Generalized the rule away from single-language phrase matching and added focused regressions covering both Marathi-script and English office-corruption complaints plus the AI normalization path.
- Files touched: `sansadx_backend/unified_taxonomy.py`, `tests/test_ai_location_grounding.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The override is intentionally narrow; if more official-corruption patterns surface in other languages, extend the structural signal sets carefully and only when they clearly outweigh model guesses.

- Date: 2026-06-01
- Request: Push the voice-note normalization hardening batch to GitHub.
- Summary: Pushed commit `60e6dcf3` (`Harden voice note normalization pipeline`) to `origin/main`, publishing the new voice-note normalization layer, tenant-aware location candidate grounding, and raw-versus-normalized transcript preservation for future voice-note cases.
- Files touched: `modules/geography_resolver.py`, `modules/voice_note_normalizer.py`, `modules/whatsapp_media_intake.py`, `main.py`, `tests/test_voice_note_normalizer.py`, `tests/test_whatsapp_media_intake.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Production still needs a backend deploy/restart before live WhatsApp voice notes start using the new normalization pass, and ambiguous transcripts should continue to fall back to clarification or review instead of forced certainty.

- Date: 2026-05-31
- Request: Push the geography validation/diagnostics/backfill hardening batch to GitHub.
- Summary: Pushed commit `1ec273d7` (`Harden geography validation and diagnostics`) to `origin/main`, publishing seat-safe onboarding validation, persisted `geography_diagnostics`, and the tenant-scoped geography backfill script/tests together as one coherent hardening batch.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: The backend now stores diagnostics and has a repair tool, but there is still no dedicated admin/Briefcase UI surface for operators to inspect `geography_diagnostics` without reading raw case metadata.

- Date: 2026-05-31
- Request: Add stronger geography onboarding validation, persist geography diagnostics per case, and create a tenant-scoped backfill path for blank historical case geography.
- Summary: Extended `sanitize_and_validate_stations()` with same-seat generated-alias collision detection and weak-coverage warnings, wired all seat-geography save endpoints to reject blocking alias collisions, persisted structured `geography_diagnostics` into case metadata through `finalize_geography_decision()`/`main.py`, and added `scripts/backfill_case_geography.py` for tenant-scoped blank-geometry repair. Added focused tests for onboarding blocking behavior, diagnostics persistence, and backfill safety.
- Files touched: `modules/geography_resolver.py`, `modules/whatsapp_geography.py`, `admin_api.py`, `main.py`, `scripts/backfill_case_geography.py`, `tests/test_geography_onboarding_api.py`, `tests/test_whatsapp_geography_decision.py`, `tests/test_case_geography_backfill.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This batch does not yet add a UI for ops to view `geography_diagnostics`; the data is stored in case metadata now, but an admin/Briefcase surface would be the natural next step.

- Date: 2026-05-31
- Request: Harden geography resolution so location and assembly mapping stay tenant-safe and reliable for all current and future tenants.
- Summary: Made the geography resolver seat-aware internally by indexing assembly buckets with `seat_type + seat_name + assembly`, preferring tenant seat context during resolution, and keeping parliamentary fallback only for non-tenant-scoped lookups. Also made `save_overrides_to_db()` replace only legacy `phone_mapping` and `geo_override` rows so shared `geography_data` and generated `geo_alias` rows survive admin override saves. Added regressions for same-name cross-seat assemblies and override persistence safety.
- Files touched: `modules/geography_resolver.py`, `sansadx_backend/db.py`, `tests/test_geography_resolver.py`, `tests/test_override_persistence.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This is the first hardening phase; onboarding validation, resolver diagnostics, and blank-case geography backfill are still the next improvements if we want consistently high accuracy in production.

- Date: 2026-05-31
- Request: Push the Briefcase delete-control restore to GitHub.
- Summary: Pushed commit `6e5c23f3` (`Restore Briefcase delete controls`) to `origin/main`, restoring visible bulk delete and per-row delete actions on the Briefcase dashboard while keeping the shared modal delete flow aligned with the same hook helper.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: The delete controls are now back in GitHub, but a production deploy is still required before the live Briefcase UI will show them.

- Date: 2026-05-31
- Request: Restore visible individual and bulk delete controls in the Briefcase dashboard after the table-design rollback removed them.
- Summary: Added a shared `deleteCase`/`bulkDelete` path to `useBriefcaseCases`, wired bulk delete into `BriefcaseBulkActions`, restored a per-row delete action in `BriefcaseCasesTable`, and pointed the case modal delete button at the same shared hook so Briefcase deletions now update the list, selection state, and totals consistently.
- Files touched: `frontend/hooks/useBriefcaseCases.js`, `frontend/components/briefcase/BriefcaseBulkActions.jsx`, `frontend/components/briefcase/BriefcaseCasesTable.jsx`, `frontend/components/briefcase/BriefcaseCaseModal.jsx`, `frontend/app/dashboard/sansadx/page.js`, `TASK_LOG.md`
- Risks or follow-ups: This was a frontend-only repair on top of the restored table design; a quick browser smoke test is still the best next check before pushing to production.

- Date: 2026-05-31
- Request: Push the one-file Briefcase table design restore to GitHub.
- Summary: Pushed commit `12eaceed` (`Restore Briefcase cases table design`) to `origin/main`, restoring the `2641837d` editorial All Cases table look in `frontend/components/briefcase/BriefcaseCasesTable.jsx`.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is a UI-only restore and should be browser-verified against the current Briefcase data shape before any further related design restores.

- Date: 2026-05-31
- Request: Restore only the reverted Briefcase All Cases table design from commit `2641837d`.
- Summary: Replaced `frontend/components/briefcase/BriefcaseCasesTable.jsx` with the earlier editorial table layout from `2641837d`, bringing back the denser fixed-column All Cases design without restoring the broader mobile or backend commits from that reverted batch.
- Files touched: `frontend/components/briefcase/BriefcaseCasesTable.jsx`, `TASK_LOG.md`
- Risks or follow-ups: This is a single-file visual restoration and has not yet been browser-verified against the current Briefcase data shape; if any newer props or interactions drifted, the next step should be a quick frontend smoke test before push.

- Date: 2026-05-31
- Request: Push the WhatsApp geography wrapper fix to GitHub.
- Summary: Pushed commit `78f7a5d8` (`Fix WhatsApp geography wrapper arg`) to `origin/main`, publishing the webhook fix that restores `location_required` pass-through into `finalize_geography_decision()`.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: Production still needs a backend deploy/restart on the EC2 host to pick up this commit, and OpenAI quota issues may still affect classification separately.

- Date: 2026-05-31
- Request: Fix the live WhatsApp geography regression that left new tenant 10 cases without location or assembly after ingestion.
- Summary: Patched `main.py` so `_finalize_whatsapp_geography_decision()` once again accepts and forwards the `location_required` argument to `modules.whatsapp_geography.finalize_geography_decision()`. This removes the runtime `unexpected keyword argument 'location_required'` failure that was aborting geography enrichment after case insertion.
- Files touched: `main.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This fixes the webhook argument mismatch, but live OpenAI quota issues can still degrade classification separately; production should be redeployed and retested with a fresh WhatsApp message.

- Date: 2026-05-31
- Request: Reintroduce the location-matching improvements that help MLA aspirant geography resolve real localities again after the earlier revert.
- Summary: Restored three targeted resolver fixes in `modules/geography_resolver.py`: assembly-to-parent-parliamentary scoping for MLA tenants, fuzzy keyword threshold `>93` for common Indian spelling variants, and independent indexing of newline-separated locality lines. Added resolver regressions covering multiline localities and MLA tenant scoping.
- Files touched: `modules/geography_resolver.py`, `tests/test_geography_resolver.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This improves matching coverage without restoring the broader reverted commit stack, but if tenant 10's saved geography itself is incomplete we may still need alias/data cleanup for missing localities.

- Date: 2026-05-31
- Request: Revert all GitHub pushes newer than `127fce16` while keeping `166db58e` and `127fce16`.
- Summary: Safely reverted the 14 commits on `main` that landed after `127fce16`, including the later seed-endpoint fixes, debug endpoints, geography persistence fixes, WhatsApp reply changes, fuzzy-matching tweak, and Briefcase table redesign. The revert was done with standard `git revert` commits so history remains intact.
- Files touched: `admin_api.py`, `api_router.py`, `frontend/components/briefcase/BriefcaseCasesTable.jsx`, `main.py`, `sansadx_backend/db.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The repository is now back to the state represented by `127fce16` plus earlier history; any functionality introduced only by the reverted commits will need to be reintroduced deliberately later if still needed.

- Date: 2026-05-29
- Request: Push the constituency-specific synthetic grievance seeder to GitHub.
- Summary: Pushed commit `166db58e` (`Add constituency case seed endpoint`) to `origin/main`, including the protected `/api/admin/seed-constituency-cases` endpoint, geography-aware synthetic seed generation capped at 500 cases, selective rerun cleanup for prior synthetic cases, and focused API tests.
- Files touched: `admin_api.py`, `tests/test_constituency_case_seed_api.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The endpoint is now in Git history, but actually populating the live `Jadhav` tenant still requires the backend deployment to pick up this commit and an authenticated admin request against production.

- Date: 2026-05-29
- Request: Implement a safer constituency-specific synthetic grievance seeder for aspirant/demo accounts, capped at 500 cases.
- Summary: Added a protected `/api/admin/seed-constituency-cases` endpoint that targets one tenant by `tenant_id` or `username`, clears only prior synthetic seeded cases for that tenant, and generates up to 500 tagged synthetic grievances using shared seat geography localities and assemblies when available, with focused API tests covering geography-aware insertion and rerun replacement behavior.
- Files touched: `admin_api.py`, `tests/test_constituency_case_seed_api.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The endpoint is implemented and tested locally, but actually populating the real `Jadhav` tenant on `backend.coinmedia.co.in` still requires authenticated admin access to that live backend.

- Date: 2026-05-29
- Request: Push the tenant-aware geography reuse flow to GitHub.
- Summary: Pushed commit `9c4387a5` (`Add tenant-aware geography reuse flow`) to `origin/main`, including the launch-readiness geography redirect, the tenant-aware reuse-vs-upload chooser on the geography page, the constituency sync fix across tenant/profile/user records, and focused admin test coverage.
- Files touched: `admin/app/dashboard/mps/[tenant_id]/setup/page.js`, `admin/app/dashboard/geography/page.js`, `admin_api.py`, `admin/tests/setup-checklist.test.jsx`, `admin/tests/geography.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Shared geography reuse still relies on exact seat-name matching; if operators later need alias-based or fuzzy seat matching, that should be added intentionally.

- Date: 2026-05-29
- Request: Make the launch-readiness geography step support either uploading new geography or reusing existing shared seat geography from rival/same-seat accounts.
- Summary: Redirected the setup checklist geography CTA to the dedicated geography page, added a tenant-aware chooser flow there that prefills the tenant seat and offers `use existing shared geography` before the upload form, and fixed the admin constituency update endpoint to keep tenant/profile/user constituency fields aligned when an account is linked to an existing saved seat.
- Files touched: `admin/app/dashboard/mps/[tenant_id]/setup/page.js`, `admin/app/dashboard/geography/page.js`, `admin_api.py`, `admin/tests/setup-checklist.test.jsx`, `admin/tests/geography.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This reuses shared geography by seat name; if operators later need fuzzy matching or alias-based seat selection, we should add that deliberately instead of auto-linking near matches.

- Date: 2026-05-29
- Request: Push the aspirant rollout and follow-up Briefcase permission fix to GitHub.
- Summary: Rebasing local commits onto `origin/main` after the upstream Briefcase mobile merge, then pushed `a6bd8137` (`Add aspirant seat model and shared geography flow`) and `f235d7a0` (`Align Briefcase modal with primary accounts`) to `origin/main`.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: Remote history now contains the full aspirant/account-stage rollout plus the final Briefcase primary-account alignment; remaining follow-up work is optional cleanup only.

- Date: 2026-05-29
- Request: Finish the account-model rollout by aligning the remaining Briefcase modal actions with primary-account permissions before pushing.
- Summary: Updated the Briefcase case modal to use shared `isPrimaryAccount` logic for citizen notifications, adjusted the related UI copy from MP-only wording to primary-account wording, and allowed `owner` accounts to retain delete-case access alongside legacy `mp` and `pr` roles.
- Files touched: `frontend/components/briefcase/BriefcaseCaseModal.jsx`, `TASK_LOG.md`
- Risks or follow-ups: This closes an omitted frontend permission check from the larger rollout; deeper parliamentary drafting/research wording remains intentionally elected-office-specific.

- Date: 2026-05-29
- Request: Begin the aspirant/MP identity rollout by implementing Phase 1 of the account model changes.
- Summary: Added explicit `tenant_type` handling to tenant creation and auth payloads, switched new primary customer accounts to `role='owner'` while keeping legacy `role='mp'` accounts compatible, updated key admin/frontend screens to recognize the new owner identity, and exposed account type selection in the admin create-account flow.
- Files touched: `admin_api.py`, `api_router.py`, `admin/app/dashboard/mps/new/page.js`, `admin/app/dashboard/rules/page.js`, `frontend/app/dashboard/page.js`, `frontend/app/dashboard/layout.js`, `frontend/app/dashboard/settings/page.js`, `frontend/components/Sidebar.js`, `frontend/components/briefcase/BriefcaseHeader.jsx`, `frontend/components/briefcase/BriefcaseCaseModal.jsx`, `frontend/app/dashboard/sansadai/page.js`, `frontend/app/dashboard/csr/page.js`, `frontend/app/dashboard/schemes/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Geography/setup helpers still contain same-constituency assumptions and module access is not yet gated by `tenant_type`; those belong to the next rollout phases.

- Date: 2026-05-29
- Request: Implement Phase 2 of the aspirant/MP rollout by making session/account-type handling consistent across the frontend.
- Summary: Added shared frontend account helpers, enriched login and `/auth/me` payloads with `is_primary_account` and `account_label`, switched key frontend module gates to use centralized account-type logic, and normalized remaining “MP-only” messaging to “primary account” or “elected-office accounts” where appropriate.
- Files touched: `api_router.py`, `frontend/lib/account.js`, `frontend/app/dashboard/page.js`, `frontend/app/dashboard/layout.js`, `frontend/components/Sidebar.js`, `frontend/components/briefcase/BriefcaseHeader.jsx`, `frontend/components/briefcase/BriefcaseCaseModal.jsx`, `frontend/app/dashboard/settings/page.js`, `frontend/app/dashboard/sansadai/page.js`, `frontend/app/dashboard/csr/page.js`, `frontend/app/dashboard/schemes/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Phase 2 centralizes frontend gating logic, but actual business feature locks by `tenant_type` still need explicit backend enforcement in the next phase.

- Date: 2026-05-29
- Request: Implement Phase 3 of the aspirant/MP rollout by locking Sansad AI and Convergence for aspirants.
- Summary: Added backend feature-access enforcement for Sansad AI and Convergence APIs, refined frontend access helpers so only those two modules are gated by tenant type, hid the protected nav/buttons/routes for aspirants, added a direct Convergence route guard on company detail pages, and restored Schemes as an allowed module instead of incorrectly bundling it into the elected-office lock.
- Files touched: `api_router.py`, `frontend/lib/account.js`, `frontend/components/Sidebar.js`, `frontend/app/dashboard/layout.js`, `frontend/components/briefcase/BriefcaseHeader.jsx`, `frontend/app/dashboard/page.js`, `frontend/components/dashboard/DashboardEmptyState.jsx`, `frontend/app/dashboard/sansadai/page.js`, `frontend/app/dashboard/csr/page.js`, `frontend/app/dashboard/csr/company/[slug]/page.js`, `frontend/app/dashboard/schemes/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Same-constituency helper assumptions in geography/setup flows still need cleanup, and future module launches should choose feature-specific tenant-type gates instead of reusing old MP-only role checks.

- Date: 2026-05-29
- Request: Implement the post-Phase-3 account-model expansion for aspirant MP/MLA accounts and build Phase 4 geography safety.
- Summary: Split tenant identity into `account_stage` and `seat_type`, updated admin create/edit flows plus auth/session payloads to carry those fields, kept legacy `tenant_type` compatibility, and moved geography persistence to shared seat-level keys so multiple aspirants and elected accounts can safely share one seat while generated overrides remain tenant-specific.
- Files touched: `sansadx_backend/db.py`, `main.py`, `modules/geography_resolver.py`, `admin_api.py`, `api_router.py`, `frontend/lib/account.js`, `frontend/components/Sidebar.js`, `frontend/app/dashboard/layout.js`, `frontend/app/dashboard/page.js`, `frontend/app/dashboard/sansadai/page.js`, `frontend/app/dashboard/csr/page.js`, `frontend/app/dashboard/csr/company/[slug]/page.js`, `frontend/app/dashboard/schemes/page.js`, `frontend/components/dashboard/DashboardEmptyState.jsx`, `admin/app/dashboard/mps/new/page.js`, `admin/app/dashboard/profiles/page.js`, `admin/app/dashboard/mps/[tenant_id]/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The generic admin geography routes are still MP-seat-shaped (`/geography/{pc}/...`), so a later cleanup should either add explicit seat-type-aware admin tooling or rename those routes/UI concepts to a more neutral seat model.

- Date: 2026-05-29
- Request: Make the admin geography UX seat-aware and validate the new shared-seat model with focused tests.
- Summary: Extended the global admin geography routes to accept `seat_type`, rebuilt the admin geography upload/browser page around explicit `MP Seat` vs `MLA Seat` selection, updated nearby admin copy from MP-only language to account/seat language, refreshed overview stats/cards for the broader account model, and added a focused geography UI test alongside updated admin dashboard coverage.
- Files touched: `admin_api.py`, `admin/app/dashboard/geography/page.js`, `admin/app/dashboard/rules/page.js`, `admin/app/dashboard/layout.js`, `admin/app/dashboard/page.js`, `admin/app/dashboard/mps/[tenant_id]/setup/page.js`, `admin/tests/dashboard.test.jsx`, `admin/tests/geography.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The generic route names still use legacy `parliamentary`/`pc` terminology under the hood; a future cleanup can rename that API surface more neutrally once downstream callers are ready.

- Date: 2026-05-29
- Request: Finish the same-seat safety pass and permission audit after the seat-aware rollout.
- Summary: Verified shared-seat geography fan-out with a backend isolation test, hardened admin staff APIs so primary `owner`/legacy `mp` accounts cannot appear in staff management or be manipulated via staff endpoints, aligned the staff UI copy to tenant/account language, and fixed the ORM/User schema drift by adding the existing `phone` column to the `User` model.
- Files touched: `admin_api.py`, `sansadx_backend/db.py`, `admin/app/dashboard/staff/page.js`, `tests/test_same_seat_isolation.py`, `tests/test_admin_staff_api.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The permission audit found plenty of MP-specific copy/prompting in parliamentary research and drafting modules, but those are product-language issues rather than tenant-isolation bugs; they can be normalized later if the product expands beyond parliamentary positioning.

- Date: 2026-05-29
- Request: Apply the first aspirant-facing UI copy pass on the MP frontend.
- Summary: Updated high-visibility user-facing copy to feel more intentional for aspirants by shifting settings/profile language toward `workspace` and `team`, replacing an `MP office` triage note in Briefcase, and renaming the dashboard schedule reference from `Constituency Office` to `Constituency Workspace`.
- Files touched: `frontend/app/dashboard/settings/page.js`, `frontend/components/dashboard/DashboardEngagementsCard.jsx`, `frontend/components/briefcase/BriefcaseTriageStrip.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This was intentionally a narrow copy pass; deeper product-language normalization in drafting/research/parliamentary modules should stay separate so we do not blur features that are still meant only for elected-office contexts.

- Date: 2026-05-29
- Request: Do a broader UI-only frontend wording cleanup after the first aspirant copy pass.
- Summary: Normalized more shared-workspace labels across the MP frontend by replacing remaining generic fallbacks like `MP`, `Member`, `PA / Staff`, and `MP Office` on non-parliamentary screens, including Briefcase header/escalation copy, dashboard layout fallback initials, and settings/team action labels.
- Files touched: `frontend/components/briefcase/BriefcaseHeader.jsx`, `frontend/components/briefcase/BriefcaseEscalationModal.jsx`, `frontend/app/dashboard/layout.js`, `frontend/app/dashboard/settings/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Parliamentary drafting/research flows still intentionally use MP-specific language; those should only be generalized later if the underlying product behavior changes too.

- Date: 2026-05-26
- Request: Establish a repo memory and confirmation-first workflow before future code changes.
- Summary: Added a mandatory pre-change protocol to `AGENTS.md` and created `PROJECT_MEMORY.md` plus `TASK_LOG.md` as persistent context files for future sessions.
- Files touched: `AGENTS.md`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The workflow depends on consistently updating memory after meaningful changes; future tasks should keep these files current.

- Date: 2026-05-26
- Request: Make memory-file maintenance mandatory after each change and each GitHub push, then push the workflow docs.
- Summary: Updated the repo protocol so `PROJECT_MEMORY.md` and `TASK_LOG.md` must be maintained after every completed change and every GitHub push.
- Files touched: `AGENTS.md`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The process is only effective if every future task closes by updating these files before or alongside the push.

- Date: 2026-05-26
- Request: Push the repo memory workflow to GitHub.
- Summary: Pushed commit `afcda31f` (`Add repo memory workflow`) to `origin/main` so the new discuss-first and memory-maintenance process is now shared in GitHub.
- Files touched: `AGENTS.md`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Future pushes should continue adding a short push record here to preserve deployment and workflow history.

- Date: 2026-05-26
- Request: Revert the MP dashboard redesign and push the rollback.
- Summary: Reverted commit `5c031838` (`Redesign MP dashboard experience`) after the user judged the redesign not ready, restoring the prior MP dashboard implementation and documenting the rollback in repo memory.
- Files touched: `frontend/app/layout.js`, `frontend/app/globals.css`, `frontend/components/Sidebar.js`, `frontend/app/dashboard/layout.js`, `frontend/app/dashboard/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Any future redesign should be applied in smaller slices and visually verified before pushing to `main`.

- Date: 2026-05-26
- Request: Start refactoring the current Claude-built dashboard into reusable structure without changing the design.
- Summary: Completed the first refactor batch by extracting dashboard theme tokens and shared visual primitives, wiring the live dashboard page to use them, and updating the dashboard test to match the current console dashboard copy.
- Files touched: `frontend/lib/dashboard-theme.js`, `frontend/components/dashboard/DashboardMiniBars.jsx`, `frontend/components/dashboard/DashboardDonut.jsx`, `frontend/components/dashboard/DashboardSectionFrame.jsx`, `frontend/components/dashboard/DashboardStatusBadge.jsx`, `frontend/app/dashboard/page.js`, `frontend/tests/dashboard.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The dashboard page is still structurally large; the next batch should extract feature sections like KPI tiles, grievance queue, workload, letters, press, and activity feed into `frontend/components/dashboard/`.

- Date: 2026-05-26
- Request: Implement Batch 2 of the dashboard refactor by extracting feature sections into reusable components.
- Summary: Moved the major dashboard sections out of `frontend/app/dashboard/page.js` into dedicated `frontend/components/dashboard/` modules, leaving the page as an overview composer with fetching and routing logic.
- Files touched: `frontend/components/dashboard/DashboardKpiTiles.jsx`, `frontend/components/dashboard/DashboardGrievanceQueue.jsx`, `frontend/components/dashboard/DashboardWorkloadCard.jsx`, `frontend/components/dashboard/DashboardEngagementsCard.jsx`, `frontend/components/dashboard/DashboardLettersCard.jsx`, `frontend/components/dashboard/DashboardPressCard.jsx`, `frontend/components/dashboard/DashboardActivityFeed.jsx`, `frontend/components/dashboard/DashboardConstituencyMap.jsx`, `frontend/components/dashboard/DashboardEmptyState.jsx`, `frontend/app/dashboard/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The next batch should separate data shaping and request orchestration into a dashboard hook and mapper layer so the page no longer owns fetch timing or response normalization.

- Date: 2026-05-26
- Request: Implement Batch 3 of the dashboard refactor by moving fetch orchestration and response shaping out of the page.
- Summary: Added `frontend/hooks/useDashboardOverview.js` for overview data loading and `frontend/lib/dashboard-mappers.js` for response normalization and derived state, then refactored `frontend/app/dashboard/page.js` to consume the hook as a composition-only screen.
- Files touched: `frontend/hooks/useDashboardOverview.js`, `frontend/lib/dashboard-mappers.js`, `frontend/app/dashboard/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The current dashboard structure is now much healthier; the next improvements would be smaller polish items such as moving remaining inline layout styles into reusable wrappers or extending the extracted dashboard system into other MP frontend pages.

- Date: 2026-05-26
- Request: Review the dashboard refactor and push it if clean.
- Summary: Reviewed the refactor, fixed two issues before push: nondeterministic KPI chart rendering in `DashboardKpiTiles` and a false empty-state flash risk in `useDashboardOverview` when summary loaded before cases.
- Files touched: `frontend/components/dashboard/DashboardKpiTiles.jsx`, `frontend/hooks/useDashboardOverview.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The dashboard refactor is now structurally sound enough to push; future work can focus on broader reuse and smaller visual cleanup rather than core architecture.

- Date: 2026-05-26
- Request: Push the dashboard refactor to GitHub.
- Summary: Pushed commit `79a43a5d` (`Refactor dashboard into reusable modules`) to `origin/main`, including the extracted dashboard component system, theme tokens, mapper layer, overview hook, updated tests, and final review fixes.
- Files touched: `frontend/app/dashboard/page.js`, `frontend/hooks/useDashboardOverview.js`, `frontend/lib/dashboard-mappers.js`, `frontend/lib/dashboard-theme.js`, `frontend/components/dashboard/*`, `frontend/tests/dashboard.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Future work can now focus on reusing the dashboard system in other MP pages or doing targeted polish, rather than untangling overview-page architecture.

- Date: 2026-05-26
- Request: Start reusing the refactor pattern in Briefcase and rename the sidebar labels to Briefcase and Letterbox.
- Summary: Extracted the embedded Briefcase modal/viewer stack into `frontend/components/briefcase/`, moved shared Briefcase tabs and status helpers into a dedicated module, and renamed the sidebar labels from Grievances/Letters to Briefcase/Letterbox without changing the live Briefcase behavior.
- Files touched: `frontend/components/Sidebar.js`, `frontend/app/dashboard/sansadx/page.js`, `frontend/components/briefcase/briefcase-shared.jsx`, `frontend/components/briefcase/BriefcaseContactPanel.jsx`, `frontend/components/briefcase/BriefcaseEscalationModal.jsx`, `frontend/components/briefcase/BriefcaseSourceMediaViewer.jsx`, `frontend/components/briefcase/BriefcaseCaseModal.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: `frontend/app/dashboard/sansadx/page.js` is still large because the toolbar, bulk-action bar, and main case table are still inline; the next Briefcase batch should extract those higher-level sections or move state orchestration into a dedicated hook.

- Date: 2026-05-26
- Request: Complete the Briefcase structural refactor before review and push.
- Summary: Finished the remaining Briefcase extraction by moving page orchestration into `frontend/hooks/useBriefcaseCases.js` and splitting the route view into dedicated components for header, filters, active filters, bulk actions, clusters, deleted cases, main case table, and pagination.
- Files touched: `frontend/app/dashboard/sansadx/page.js`, `frontend/hooks/useBriefcaseCases.js`, `frontend/components/briefcase/BriefcaseHeader.jsx`, `frontend/components/briefcase/BriefcaseNewCasesNotice.jsx`, `frontend/components/briefcase/BriefcaseFiltersBar.jsx`, `frontend/components/briefcase/BriefcaseActiveFilters.jsx`, `frontend/components/briefcase/BriefcaseBulkActions.jsx`, `frontend/components/briefcase/BriefcaseClustersView.jsx`, `frontend/components/briefcase/BriefcaseDeletedCasesView.jsx`, `frontend/components/briefcase/BriefcaseCasesTable.jsx`, `frontend/components/briefcase/BriefcasePagination.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The Briefcase page is now structurally modular, so future work should focus on visual standardization or extracting any remaining shared patterns across Letterbox, Drafter, and Sansad AI rather than further untangling `sansadx/page.js`.

- Date: 2026-05-26
- Request: Push the completed Briefcase refactor to GitHub.
- Summary: Pushed commit `d35fd3de` (`Refactor Briefcase into reusable modules`) to `origin/main`, including the Briefcase hook/component extraction, sidebar naming updates, and repo memory updates.
- Files touched: `frontend/app/dashboard/sansadx/page.js`, `frontend/hooks/useBriefcaseCases.js`, `frontend/components/briefcase/*`, `frontend/components/Sidebar.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The Briefcase page is now structurally ready for future visual-system work; the next reuse target can move to Letterbox or another MP module without carrying the old monolith shape forward.

- Date: 2026-05-26
- Request: Remove the desktop `Owner` column from the dashboard grievance queue so `Category` and `Subject` have more room.
- Summary: Removed the `Owner` column from the desktop grievance queue table in the dashboard overview and updated the empty-state column span so the queue layout can give more space to the remaining columns.
- Files touched: `frontend/components/dashboard/DashboardGrievanceQueue.jsx`, `TASK_LOG.md`
- Risks or follow-ups: This is a dashboard-overview-only change; if the same column should disappear elsewhere, Briefcase and other queue-style tables would need separate updates.

- Date: 2026-05-26
- Request: Push the dashboard grievance queue column change to GitHub.
- Summary: Pushed commit `4293f1a3` (`Remove owner column from dashboard queue`) to `origin/main`, including the desktop grievance queue column removal and the task log update.
- Files touched: `frontend/components/dashboard/DashboardGrievanceQueue.jsx`, `TASK_LOG.md`
- Risks or follow-ups: This only changes the dashboard overview queue; other queue/table surfaces still retain their current columns unless changed separately.

- Date: 2026-05-26
- Request: Add clearer separation between the dashboard queue `Category` and `Subject` columns on desktop.
- Summary: Added truncation plus a vertical divider to the `Category` cell and extra left padding on `Subject` so long category values no longer visually merge into the subject text.
- Files touched: `frontend/components/dashboard/DashboardGrievanceQueue.jsx`, `TASK_LOG.md`
- Risks or follow-ups: This is still a desktop dashboard-queue adjustment only; if tighter spacing appears elsewhere, those tables will need their own spacing pass.

- Date: 2026-05-26
- Request: Push the dashboard queue spacing fix to GitHub.
- Summary: Pushed commit `84778752` (`Adjust dashboard queue column spacing`) to `origin/main`, including the category/subject spacing fix and the task log update.
- Files touched: `frontend/components/dashboard/DashboardGrievanceQueue.jsx`, `TASK_LOG.md`
- Risks or follow-ups: This remains scoped to the dashboard overview queue; any similar spacing issues elsewhere will need separate changes.

- Date: 2026-05-26
- Request: Rebuild Briefcase to match the `Needle-2.zip` prototype as closely as possible while preserving the live workflows.
- Summary: Translated the prototype into the live Briefcase route by shifting the default state to `Needs you`, adding a triage KPI strip and promoted-clusters banner, redesigning the filters/bulk action shell, restyling the clusters and deleted views, and wiring the route composition to the new prototype-based Briefcase surface.
- Files touched: `frontend/app/dashboard/sansadx/page.js`, `frontend/hooks/useBriefcaseCases.js`, `frontend/components/briefcase/briefcase-shared.jsx`, `frontend/components/briefcase/BriefcaseHeader.jsx`, `frontend/components/briefcase/BriefcaseFiltersBar.jsx`, `frontend/components/briefcase/BriefcaseBulkActions.jsx`, `frontend/components/briefcase/BriefcaseActiveFilters.jsx`, `frontend/components/briefcase/BriefcaseClustersView.jsx`, `frontend/components/briefcase/BriefcaseDeletedCasesView.jsx`, `frontend/components/briefcase/BriefcaseNewCasesNotice.jsx`, `frontend/components/briefcase/BriefcaseTriageStrip.jsx`, `frontend/components/briefcase/BriefcaseClustersBanner.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The visual translation is now in place, but the remaining gap to the prototype is mostly fine-grain polish in table density and modal/detail surfaces rather than core layout or architecture.

- Date: 2026-05-26
- Request: Push the Needle-2 Briefcase redesign to GitHub.
- Summary: Pushed commit `8ae4f3c8` (`Redesign Briefcase to match prototype`) to `origin/main`, including the triage-first Briefcase layout, promoted cluster banner, redesigned filters and bulk actions, and the supporting Briefcase hook/state updates.
- Files touched: `frontend/app/dashboard/sansadx/page.js`, `frontend/hooks/useBriefcaseCases.js`, `frontend/components/briefcase/*`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The core prototype translation is now live in Git history; any future iteration should focus on smaller visual polish passes rather than another large structural shift.

- Date: 2026-05-26
- Request: Revert commits `ee0be990` and `f1839330` because the mobile pass changed the Briefcase structure too much.
- Summary: Reverted commit `f1839330` (`Log Briefcase mobile push`) and commit `ee0be990` (`Make Briefcase mobile friendly`). The clarified direction is that mobile responsiveness should keep the desktop structure aligned as closely as possible instead of switching to alternate mobile-specific layouts.
- Files touched: `frontend/app/dashboard/layout.js`, `frontend/components/briefcase/BriefcaseHeader.jsx`, `frontend/components/briefcase/BriefcaseTriageStrip.jsx`, `frontend/components/briefcase/BriefcaseClustersBanner.jsx`, `frontend/components/briefcase/BriefcaseFiltersBar.jsx`, `frontend/components/briefcase/BriefcaseBulkActions.jsx`, `frontend/components/briefcase/BriefcaseCasesTable.jsx`, `frontend/components/briefcase/BriefcaseDeletedCasesView.jsx`, `frontend/components/briefcase/BriefcaseClustersView.jsx`, `frontend/components/briefcase/BriefcasePagination.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The next mobile pass should focus on alignment-preserving responsive refinement rather than separate phone-only structures.

- Date: 2026-05-26
- Request: Push the Briefcase mobile rollback to GitHub.
- Summary: Pushed the rollback sequence to `origin/main`: `72b1491f` (`Revert "Log Briefcase mobile push"`), `514076c7` (`Revert "Make Briefcase mobile friendly"`), and `7b861b15` (`Document Briefcase mobile rollback`).
- Files touched: `frontend/app/dashboard/layout.js`, `frontend/components/briefcase/*`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Future MP mobile responsiveness work should preserve desktop structure and alignment first, then apply only minimal responsive adaptations.

- Date: 2026-05-27
- Request: Make `All cases` the first and default Briefcase tab, and restore `Others` for greetings, offensive/spam, and personal request messages.
- Summary: Reordered the Briefcase tabs so `All cases` is first and becomes the default when no status query param is present, restored `Others` as a real tab, and wired it to the backend-supported `bucket=other` filter path instead of a custom frontend-only parameter.
- Files touched: `frontend/components/briefcase/briefcase-shared.jsx`, `frontend/hooks/useBriefcaseCases.js`, `frontend/app/dashboard/sansadx/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: `Others` currently follows the backend's `other` bucket definitions plus the shared frontend labels; if you want to refine exactly which categories count as “personal request,” we should align the backend bucket list too.

- Date: 2026-05-27
- Request: Push the Briefcase default-tab and `Others` restoration to GitHub.
- Summary: Pushed commit `9915251c` (`Restore Briefcase all-cases default`) to `origin/main`, including the `All cases` default/tab order change and the restored `Others` bucket using the backend-supported `bucket=other` filter.
- Files touched: `frontend/components/briefcase/briefcase-shared.jsx`, `frontend/hooks/useBriefcaseCases.js`, `frontend/app/dashboard/sansadx/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: If `Others` needs a more exact “personal request” definition, the backend bucket list should be tuned alongside the frontend labels.

- Date: 2026-05-27
- Request: Remove the `Needs you` Briefcase tab but keep the same idea in the triage stats.
- Summary: Removed `Needs you` from the Briefcase tab strip and quick filters, kept `All cases` as the default operational view, and retained the “needs attention” number only in the triage metrics derived from new, pending-review, awaiting-location, and escalated cases.
- Files touched: `frontend/components/briefcase/briefcase-shared.jsx`, `frontend/hooks/useBriefcaseCases.js`, `frontend/components/briefcase/BriefcaseFiltersBar.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The triage stat still reflects the same attention bucket, but there is no dedicated one-click tab for it anymore.

- Date: 2026-05-27
- Request: Push the Briefcase `Needs you` tab removal to GitHub.
- Summary: Pushed commit `261e3315` (`Remove Briefcase needs-you tab`) to `origin/main`, keeping the triage “needs attention” metric while removing the tab itself from Briefcase.
- Files touched: `frontend/components/briefcase/briefcase-shared.jsx`, `frontend/hooks/useBriefcaseCases.js`, `frontend/components/briefcase/BriefcaseFiltersBar.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The triage number remains available, but users can no longer jump directly into that subset through a dedicated Briefcase tab.

- Date: 2026-05-27
- Request: Remove the duplicate global dashboard header on Briefcase so only the Briefcase header shows there.
- Summary: Updated the shared dashboard layout to suppress its generic route header on `/dashboard/sansadx`, leaving the page-level Briefcase header as the only visible header on that route.
- Files touched: `frontend/app/dashboard/layout.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This is intentionally scoped to Briefcase; other pages still use the shared “Operations Dashboard” header until we decide otherwise.

- Date: 2026-05-27
- Request: Push the Briefcase duplicate-header fix to GitHub.
- Summary: Pushed commit `0a90e89d` (`Hide shared header on Briefcase`) to `origin/main`, so the Briefcase route now shows only its own page header instead of stacking the shared dashboard header above it.
- Files touched: `frontend/app/dashboard/layout.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The suppression is route-specific to Briefcase; if we want the same behavior on other pages later, we should make that a deliberate shared-layout rule.

- Date: 2026-05-27
- Request: Restore the older Media Centre behavior on the dashboard so press monitoring shows separate national and local feeds again, while keeping the logic tenant-aware.
- Summary: Replaced the simplified single-feed press card with a dual-tab `Media Centre`, updated the overview hook and mappers to fetch and normalize both `national` and `local` news feeds in parallel, and expanded the tenant-aware local news query strategy in `modules/news_intel.py` to use profile languages, constituency aliases, and broader digital-media search terms without hardcoding any single constituency.
- Files touched: `frontend/components/dashboard/DashboardPressCard.jsx`, `frontend/hooks/useDashboardOverview.js`, `frontend/lib/dashboard-mappers.js`, `modules/news_intel.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The local feed is now broader and more multilingual, but it still depends on Google News-indexed sources; true direct social-handle/page monitoring would need a separate ingestion layer later.

- Date: 2026-05-27
- Request: Push the restored tenant-aware Media Centre to GitHub.
- Summary: Pushed commit `1d0e4dc7` (`Restore tenant-aware dashboard media centre`) to `origin/main`, restoring separate dashboard media tabs for national and local coverage while keeping the feed logic tenant-driven through the existing profile-based backend model.
- Files touched: `frontend/components/dashboard/DashboardPressCard.jsx`, `frontend/hooks/useDashboardOverview.js`, `frontend/lib/dashboard-mappers.js`, `modules/news_intel.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The dashboard now again exposes both feed types, but local social/page coverage is still limited to sources discoverable through the current Google News-based ingestion path.

- Date: 2026-05-27
- Request: Improve mobile responsiveness on the dashboard overview without changing the desktop structure.
- Summary: Updated the dashboard overview grids and section wrappers to collapse cleanly on smaller screens, made KPI tiles responsive, allowed the grievance queue controls to wrap while keeping the table structure via horizontal overflow, stacked Media Centre controls on narrow widths, and made map/category sections adapt better to phones without introducing alternate mobile-only layouts.
- Files touched: `frontend/app/dashboard/page.js`, `frontend/components/dashboard/DashboardSectionFrame.jsx`, `frontend/components/dashboard/DashboardKpiTiles.jsx`, `frontend/components/dashboard/DashboardGrievanceQueue.jsx`, `frontend/components/dashboard/DashboardPressCard.jsx`, `frontend/components/dashboard/DashboardConstituencyMap.jsx`, `frontend/components/dashboard/DashboardActivityFeed.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This pass is intentionally overview-only; if you want the same alignment-preserving responsive treatment on other MP pages, we should do them individually rather than assume one pattern fits all.

- Date: 2026-05-27
- Request: Push the dashboard mobile responsiveness update to GitHub.
- Summary: Pushed commit `a2bfd2bf` (`Improve dashboard mobile responsiveness`) to `origin/main`, keeping the dashboard’s desktop structure intact while making its grids, controls, and dense sections behave better on smaller screens.
- Files touched: `frontend/app/dashboard/page.js`, `frontend/components/dashboard/DashboardSectionFrame.jsx`, `frontend/components/dashboard/DashboardKpiTiles.jsx`, `frontend/components/dashboard/DashboardGrievanceQueue.jsx`, `frontend/components/dashboard/DashboardPressCard.jsx`, `frontend/components/dashboard/DashboardConstituencyMap.jsx`, `frontend/components/dashboard/DashboardActivityFeed.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This push only covers the dashboard overview; Briefcase, Letterbox, Sansad AI, and other MP pages will need their own responsive passes.

- Date: 2026-05-29
- Request: Redesign the Briefcase cases table to match the "All cases" variant from the Needle-3 design ZIP.
- Summary: Rewrote `BriefcaseCasesTable.jsx` as a fixed-layout native `<table>` with `<colgroup>` pixel widths matching the design. Added: left 3px accent bar (saffron=critical, green=selected), stacked citizen name + phone, stacked sub-category + domain, stacked location + assembly, `StatusPill` with icon+label from `briefcasePalette`, language badge + 2-line clamped message, hover-reveal action buttons, and skeleton loader rows. Pushed as commit `2641837d`.
- Files touched: `frontend/components/briefcase/BriefcaseCasesTable.jsx`, `TASK_LOG.md`
- Risks or follow-ups: Frontend deploys via Vercel on push to main. Backend (EC2) has no changes in this commit. Visual verification against the design should be done once Vercel deploy completes.

- Date: 2026-05-29
- Request: Fix Jadhav's seeded cases showing only "Nanawadi" — data looked fake for demo.
- Summary: Root cause was twofold: (1) seed was called with count=1 in a loop, so idx=0 always picked localities[0]="Nanawadi"; (2) count>500 bulk seed failed because SQLAlchemy 2.x batches session.add() objects into a typed executemany that casts String columns as ::VARCHAR, rejected when assigned_to column is still INTEGER. Fixed by adding db.flush() after each Case add (forces individual single-row INSERTs, NULL sent untyped). Seeded 500 cases across all 69 Belgaum dakshin localities for tenant_id=10. Commits: 41c9193e, f48bd38c, 5e3349dd.
- Files touched: `admin_api.py`, `TASK_LOG.md`
- Risks or follow-ups: The assigned_to INTEGER column is still on the DB — the startup migration keeps getting skipped. The flush workaround is solid but the ALTER COLUMN migration should be investigated and cleaned up later.

- Date: 2026-05-31
- Request: Change citizen WhatsApp intake so the first response stays a normal acknowledgment, clarification for missing location/details is delayed by 2–3 minutes, and later citizen clarifications update the original case automatically.
- Summary: Added a shared citizen-case enrichment path in `main.py`, delayed clarification scheduling via case metadata plus background timers/startup sweep, and a follow-up intercept that enriches the original recent clarification-pending case instead of inserting a new one. The first citizen reply now stays generic even for `awaiting_location` / `incomplete`, while the delayed second message asks for location or more detail only when needed.
- Files touched: `main.py`, `tests/test_citizen_clarification_flow.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The timing is handled in-process plus startup recovery, so truly guaranteed delayed delivery across crashes would eventually benefit from a dedicated job queue; for now the metadata + startup sweep path covers deploy/restart recovery.

- Date: 2026-05-31
- Request: Push the delayed citizen clarification follow-up flow to GitHub.
- Summary: Pushed commit `abb16bfe` (`Delay citizen clarification follow-ups`) to `origin/main`, including the delayed clarification scheduler, same-case clarification enrichment, and focused citizen intake tests.
- Files touched: `main.py`, `tests/test_citizen_clarification_flow.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This is pushed but not yet deployed to EC2, so live WhatsApp behavior will not change until the backend is redeployed.

- Date: 2026-05-31
- Request: Switch WhatsApp voice-note reading from the old multimodal path to Sarvam AI because the current transcription quality is poor.
- Summary: Added `core/sarvam_client.py` and routed `modules/whatsapp_media_intake.py` to use Sarvam STT first for `media_type="audio"`, while keeping Gemini as the fallback and leaving image/document handling unchanged. Added focused media-intake test coverage for the Sarvam-first audio path.
- Files touched: `core/sarvam_client.py`, `modules/whatsapp_media_intake.py`, `tests/test_whatsapp_media_intake.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This is an audio-only provider swap. If Sarvam’s API shape or auth header changes, voice notes will fall back to Gemini, so production should be tested with real WhatsApp OGG voice notes after deploy.

- Date: 2026-05-31
- Request: Push the Sarvam voice-note transcription swap to GitHub.
- Summary: Pushed commit `036bcfbf` (`Use Sarvam for voice note transcription`) to `origin/main`, publishing the new Sarvam-first audio transcription path with Gemini fallback and the focused media-intake tests.
- Files touched: `core/sarvam_client.py`, `modules/whatsapp_media_intake.py`, `tests/test_whatsapp_media_intake.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The live backend still needs a deploy/restart before WhatsApp voice notes start using Sarvam in production.

- Date: 2026-05-31
- Request: Improve future voice-note reading and mapping accuracy across languages and issue types, not just for a single corrected case.
- Summary: Added a new `modules/voice_note_normalizer.py` layer that sits between Sarvam transcription and grievance classification, builds a tenant-scoped shortlist of likely localities using resolver candidates, and uses Gemini to conservatively clean ASR drift without translating the citizen’s language. Media intake now preserves both the raw transcript and normalized complaint text in source-media metadata, and the geography resolver exposes `suggest_location_candidates()` for voice-note grounding.
- Files touched: `modules/geography_resolver.py`, `modules/voice_note_normalizer.py`, `modules/whatsapp_media_intake.py`, `main.py`, `tests/test_voice_note_normalizer.py`, `tests/test_whatsapp_media_intake.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This materially improves the pipeline, but true production confidence still depends on live OpenAI/Gemini quota health and real-world evaluation across diverse voice notes; ambiguous cases should still fall back to clarification or review instead of forced certainty.

- Date: 2026-06-01
- Request: Build Phase 4 of the constituency map architecture so seat maps can be managed operationally instead of through raw JSON or code-only edits.
- Summary: Added a new admin seat-map management page at `/dashboard/seat-maps`, linked it into the admin sidebar/layout, and wired it to `/api/admin/seat-maps` for listing and saving DB-backed seat manifests. The UI supports seat metadata, aliases, asset configuration, features, and fallback anchors with client-side validation for missing required fields, duplicate aliases, and invalid anchor coordinates.
- Files touched: `admin/app/dashboard/layout.js`, `admin/components/Sidebar.js`, `admin/app/dashboard/seat-maps/page.js`, `admin/tests/seat-maps.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Asset management is still path-based rather than upload-based, so Phase 4 is operational but not yet a full asset pipeline. Future work can add asset upload/storage and stronger server-side manifest validation if needed.

- Date: 2026-06-01
- Request: Push and deploy the constituency map architecture through Phase 4.
- Summary: Pushed commit `c23f4315` (`Build seat map admin architecture`) to `origin/main`, covering the Phase 2 backend manifest API, Phase 3 DB-backed/admin-managed manifest storage, and Phase 4 admin seat-map management UI. Deployed the backend manually on EC2 by pulling `main`, rebuilding `ec2-backend-1`, and verifying `https://backend.coinmedia.co.in/health` returned `ok`. Temporary SSH ingress on the EC2 security group was revoked after deploy.
- Files touched: `PROJECT_MEMORY.md`, `TASK_LOG.md`, deployment host `/opt/compass-needle/app`
- Risks or follow-ups: Vercel still needs to pick up the pushed frontend/admin changes through its normal deployment flow. Backend APIs are live; if the admin UI does not appear immediately, wait for the Vercel build to finish or redeploy the frontend projects.

- Date: 2026-06-01
- Request: Add a one-click constituency map generator so a seat map can be created without uploading any asset manually.
- Summary: Added `modules/seat_map_generator.py`, which builds a generated SVG background plus locality feature anchors directly from shared seat geography (`geography_data`). Added `POST /api/admin/seat-maps/generate` to create/update a DB-backed seat manifest in one click, relaxed seat-map save validation to accept `asset.inline_svg` instead of only `asset.path`, updated the Seat Maps admin page with a new `Generate map` action, and taught the dashboard map renderer to display generated inline SVG assets through a data URI. Verified with `venv/bin/python -m pytest tests/test_seat_map_generator.py -q`, `npm run test --prefix admin -- --run tests/seat-maps.test.jsx tests/dashboard.test.jsx tests/geography.test.jsx`, `npm run test --prefix frontend -- --run tests/dashboard.test.jsx`, and `venv/bin/python -m py_compile admin_api.py modules/seat_map_generator.py modules/seat_maps.py`.
- Files touched: `modules/seat_map_generator.py`, `admin_api.py`, `admin/app/dashboard/seat-maps/page.js`, `frontend/components/dashboard/DashboardConstituencyMap.jsx`, `admin/tests/seat-maps.test.jsx`, `tests/test_seat_map_generator.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The one-click output is an operationally useful generated SVG, not a legally precise boundary geometry. It depends on shared seat geography already being present; if geography has not been uploaded for a seat, generation should fail and ask ops to upload geography first.

- Date: 2026-06-01
- Request: Remove the low-level Seat Maps admin editor and replace it with a shared-geography reuse workflow.
- Summary: Rebuilt `/dashboard/seat-maps` as a workflow-first operations screen backed by a new `GET /api/admin/seat-maps/workflow` summary endpoint. The page now lists seats by readiness, shows shared geography presence, map status, assembly/locality counts, and tenant usage, and offers a single generate/regenerate action instead of raw manifest fields. Added backend tests for the workflow endpoint and kept generation tied to shared seat geography so one generated map can safely serve every tenant on the same constituency.
- Files touched: `admin/app/dashboard/seat-maps/page.js`, `admin_api.py`, `modules/seat_maps.py`, `tests/test_dashboard_map_manifest_api.py`, `admin/tests/seat-maps.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This intentionally hides raw manifest editing from ops. If advanced overrides are ever needed later, they should be exposed in a separate expert-only surface rather than by reintroducing the full low-level editor into the main Seat Maps workflow.

- Date: 2026-06-01
- Request: Build the proper boundary-first map system: architecture first, real boundary ingestion path, and blob fallback only as backup.
- Summary: Added a new `seat_boundary_assets` registry model plus `modules/seat_boundaries.py` for real constituency geometry storage and lookup. Added admin boundary ingestion APIs (`GET /api/admin/seat-boundaries/by-key`, `POST /api/admin/seat-boundaries`), extended seat-map workflow summaries with `boundary_ready`/`boundary_type`/`boundary_source`, and updated one-click seat-map generation so it prefers a registered real boundary asset and only falls back to the generated blob when no real boundary exists. Reworked the Seat Maps admin workflow to expose real boundary registration directly in the seat operations screen. Verified with `venv/bin/python -m pytest tests/test_dashboard_map_manifest_api.py tests/test_seat_map_generator.py -q`, `npm run test --prefix admin -- --run tests/seat-maps.test.jsx tests/dashboard.test.jsx tests/geography.test.jsx`, `npm run test --prefix frontend -- --run tests/dashboard.test.jsx`, and `venv/bin/python -m py_compile admin_api.py modules/seat_maps.py modules/seat_map_generator.py modules/seat_boundaries.py tests/test_dashboard_map_manifest_api.py tests/test_seat_map_generator.py`.
- Files touched: `sansadx_backend/db.py`, `modules/seat_boundaries.py`, `modules/seat_maps.py`, `modules/seat_map_generator.py`, `admin_api.py`, `admin/app/dashboard/seat-maps/page.js`, `admin/tests/seat-maps.test.jsx`, `tests/test_dashboard_map_manifest_api.py`, `tests/test_seat_map_generator.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The system is now architecturally correct, but it still depends on real boundary assets actually being registered seat by seat. Without those, the generator will still use the blob backup tier; that fallback should be hidden or avoided in demos whenever a real boundary asset can be provided.

- Date: 2026-06-01
- Request: Push and deploy the boundary-first seat map system.
- Summary: Pushed commit `c7ba5224` (`Build boundary-first seat map system`) to `origin/main`, publishing the `seat_boundary_assets` registry, boundary ingestion APIs, boundary-aware workflow status, and real-boundary-first generation behavior. Deployed the backend manually on EC2 by pulling `main`, rebuilding `ec2-backend-1`, confirming `https://backend.coinmedia.co.in/health` returned `ok`, and revoking the temporary SSH ingress rule afterward.
- Files touched: `PROJECT_MEMORY.md`, `TASK_LOG.md`, deployment host `/opt/compass-needle/app`
- Risks or follow-ups: Backend support is live now, but the admin/frontend UI still depends on Vercel finishing the latest deploy from `main`. Real maps will only stop using the blob fallback once real boundary assets are actually registered seat by seat.

- Date: 2026-06-01
- Request: Push and deploy the workflow-first Seat Maps generator system.
- Summary: Pushed commit `0b51b5e5` (`Build seat map workflow generator`) to `origin/main`, publishing the shared-geography-driven one-click seat map generator, the new `/api/admin/seat-maps/workflow` endpoint, and the rebuilt Seat Maps admin surface. Deployed the backend manually on EC2 by pulling `main`, rebuilding `ec2-backend-1`, confirming `https://backend.coinmedia.co.in/health` returned `ok`, and revoking the temporary SSH ingress rule afterward.
- Files touched: `PROJECT_MEMORY.md`, `TASK_LOG.md`, deployment host `/opt/compass-needle/app`
- Risks or follow-ups: Backend APIs are live now. The updated admin/frontend UI depends on Vercel picking up the new `main` push; if the new Seat Maps workflow page does not appear immediately, wait for the frontend/admin deploy to finish or trigger a Vercel redeploy.

- Date: 2026-06-01
- Request: Make the real seat-boundary system practical by importing real parliamentary boundaries from the downloaded open map dataset and rendering GeoJSON directly instead of requiring manual SVG conversion.
- Summary: Added `modules/parliamentary_boundary_importer.py` plus `scripts/import_parliamentary_boundaries.py` to ingest MP constituency boundaries from the Datameet `maps-master.zip` / `india_pc_2019_simplified.geojson` dataset into `seat_boundary_assets` as `asset.type="geojson"`. Added `POST /api/admin/seat-boundaries/import-parliamentary` for seat-specific admin import, updated one-click seat-map generation to treat GeoJSON boundaries as real assets, and taught `DashboardConstituencyMap.jsx` to render GeoJSON boundary geometry directly in the dashboard. The Seat Maps admin workflow now includes a file-based parliamentary dataset import action for MP seats, and regression coverage was added for GeoJSON boundary import/generation.
- Files touched: `modules/parliamentary_boundary_importer.py`, `scripts/import_parliamentary_boundaries.py`, `admin_api.py`, `modules/seat_maps.py`, `modules/seat_map_generator.py`, `frontend/components/dashboard/DashboardConstituencyMap.jsx`, `admin/app/dashboard/seat-maps/page.js`, `tests/test_dashboard_map_manifest_api.py`, `tests/test_seat_map_generator.py`, `tests/test_parliamentary_boundary_importer.py`, `admin/tests/seat-maps.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This importer currently targets the parliamentary GeoJSON path only, so it solves MP boundaries first. MLA boundary ingestion still needs a dedicated shapefile/GeoJSON conversion and validation path before it should be exposed as a similar one-click workflow.

- Date: 2026-06-01
- Request: Push and deploy the parliamentary boundary importer and GeoJSON-first map rendering changes.
- Summary: Pushed commit `7eac8ee5` (`Add parliamentary boundary importer`) to `origin/main`, publishing the MP boundary importer, admin upload path, and GeoJSON dashboard rendering updates. Deployed the backend manually on EC2 by pulling `main`, rebuilding `ec2-backend-1`, confirming `https://backend.coinmedia.co.in/health` returned `ok`, and revoking the temporary SSH ingress rule afterward.
- Files touched: `TASK_LOG.md`, deployment host `/opt/compass-needle/app`
- Risks or follow-ups: Backend support is live now, but the admin/frontend UI still depends on Vercel finishing the latest `main` deploy. The new importer currently covers the parliamentary GeoJSON path only; MLA boundary ingestion remains a follow-up.

- Date: 2026-06-01
- Request: Remove the MP dataset upload requirement and make seat selection use the built-in parliamentary boundary library automatically.
- Summary: Added the Datameet parliamentary GeoJSON into the repo at `data/maps/parliamentary/india_pc_2019_simplified.geojson`, taught `modules/parliamentary_boundary_importer.py` to load that built-in library, added `POST /api/admin/seat-boundaries/import-parliamentary-auto`, and updated `modules/seat_map_generator.py` so MP map generation attempts a built-in boundary import before any blob fallback. The Seat Maps admin UI now offers `Import MP boundary automatically` instead of requiring a file upload.
- Files touched: `data/maps/parliamentary/india_pc_2019_simplified.geojson`, `modules/parliamentary_boundary_importer.py`, `modules/seat_map_generator.py`, `admin_api.py`, `admin/app/dashboard/seat-maps/page.js`, `tests/test_dashboard_map_manifest_api.py`, `tests/test_parliamentary_boundary_importer.py`, `admin/tests/seat-maps.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This closes the upload requirement for MP seats only. MLA boundaries still need a safe built-in ingestion path before the same experience can be exposed there.

- Date: 2026-06-01
- Request: Push the built-in parliamentary boundary library change to GitHub.
- Summary: Pushed commit `84996e26` (`Bundle parliamentary boundary library`) to `origin/main`, publishing the in-repo MP boundary dataset, automatic parliamentary boundary import endpoint, and the no-upload Seat Maps admin flow for MP constituencies.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is pushed but not deployed yet. The new no-upload MP boundary flow will appear live only after the backend and admin frontend are redeployed.

- Date: 2026-06-01
- Request: Extend the no-upload built-in boundary ingestion system to MLA seats as well, so admins never need to upload constituency datasets manually.
- Summary: Normalized the Datameet assembly shapefile into a built-in GeoJSON library at `data/maps/assembly/india_ac_normalized.geojson`, added `modules/assembly_boundary_importer.py`, generalized the admin endpoint to `POST /api/admin/seat-boundaries/import-auto`, and updated seat-map generation so both MP and MLA seats attempt built-in boundary import before any blob fallback. The Seat Maps UI now uses a single `Import real boundary automatically` action for both seat types.
- Files touched: `data/maps/assembly/india_ac_normalized.geojson`, `modules/assembly_boundary_importer.py`, `modules/seat_map_generator.py`, `admin_api.py`, `admin/app/dashboard/seat-maps/page.js`, `tests/test_dashboard_map_manifest_api.py`, `tests/test_seat_map_generator.py`, `tests/test_assembly_boundary_importer.py`, `admin/tests/seat-maps.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The built-in MLA library comes from the normalized Datameet assembly source, which still has known delimitation/naming caveats in some states. The admin experience is now upload-free, but boundary accuracy should still be spot-checked for high-stakes constituencies.

- Date: 2026-06-01
- Request: Push the built-in assembly boundary library and unified auto-import flow to GitHub.
- Summary: Pushed commit `0ddc1b8e` (`Bundle assembly boundary library`) to `origin/main`, publishing the in-repo MLA boundary dataset, `modules/assembly_boundary_importer.py`, and the shared no-upload `import-auto` seat-boundary flow for both MP and MLA seats.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is pushed but not deployed yet. The live admin workflow will keep the older behavior until the backend and admin frontend are redeployed.
