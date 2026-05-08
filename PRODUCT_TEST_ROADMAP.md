# Product Test Roadmap

## Goal

Build and maintain a product-wide test system that covers:

- Backend APIs and state transitions
- MP dashboard frontend behavior
- Admin dashboard frontend behavior
- Browser smoke workflows across services
- CI gates that stop regressions before deploy

This roadmap reflects the current monorepo state and should stay honest about what is already implemented versus what still needs deeper coverage.

## Sprint 1: Completed Baseline

Sprint 1 is complete. Its purpose was not to cover every product page; it was to create a reliable, repo-owned testing foundation that future work can extend without starting from zero.

Completed Sprint 1 scope:

- Backend pytest baseline kept green
- MP Vitest harness added
- MP Playwright harness added
- Admin Vitest harness added
- Admin Playwright harness added
- MP login/dashboard smoke coverage added
- MP Briefcase smoke coverage added
- Admin login/dashboard smoke coverage added
- Admin MP creation smoke coverage added
- Root `npm run test:all` command added
- GitHub Actions product test workflow added
- Full suite passed locally at the time Sprint 1 was completed

## Current Implemented Baseline

The repo now has a local full-stack test baseline:

- Backend tests run through `npm run test:backend`
- MP frontend integration tests run through `npm run test:mp`
- Admin frontend integration tests run through `npm run test:admin`
- MP browser smoke tests run through `npm run test:e2e:mp`
- Admin browser smoke tests run through `npm run test:e2e:admin`
- All suites run together through `npm run test:all`
- CI runs the product suite through `.github/workflows/product-tests.yml`

Implemented test stack:

- `frontend/vitest.config.js`
- `frontend/test/setup.js`
- `frontend/playwright.config.js`
- `frontend/tests/login.test.jsx`
- `frontend/tests/dashboard.test.jsx`
- `frontend/e2e/auth.spec.js`
- `frontend/e2e/briefcase.spec.js`
- `admin/vitest.config.js`
- `admin/test/setup.js`
- `admin/playwright.config.js`
- `admin/tests/login.test.jsx`
- `admin/tests/dashboard.test.jsx`
- `admin/e2e/auth.spec.js`
- `admin/e2e/mps.spec.js`
- `.github/workflows/product-tests.yml`

## Definition Of Done

We should consider the product "fully covered enough to trust releases" only when all of the following exist:

1. Backend critical APIs have passing automated coverage.
2. MP dashboard critical workflows have passing browser tests.
3. Admin dashboard critical workflows have passing browser tests.
4. Permission and tenant-isolation boundaries are covered.
5. A blocking CI suite runs on every push/PR.
6. A broader confidence suite runs nightly or before release.

## Do Not Overbuild

Testing should grow deliberately. The goal is confidence, not page-count theater.

- Add only 2-3 reliable workflows or test cases per sprint, unless a small fixture/helper change naturally supports more.
- Expand from existing fixtures and helpers before inventing new setup.
- Prefer critical workflow depth over broad brittle page-count coverage.
- Keep blocking tests small, deterministic, and fast enough to run every time.
- Push exploratory, slow, or highly visual coverage into non-blocking suites later.

## Seed And Fixture Strategy

Stable fixtures are the foundation for frontend and browser tests.

- Backend tests should use deterministic SQLite/TestClient fixtures unless the test explicitly requires another setup.
- Browser tests should mock or seed the minimum data needed for the workflow under test.
- Prefer stable fixture data owned by the test suite over shared local or production-like data.
- Keep auth/session setup reusable for MP and admin browser tests.
- Every tenant-scoped fixture must include at least two tenants when testing isolation.
- External integrations must be monkeypatched, mocked, or routed through deterministic test doubles.
- Fixture changes should be additive and shared when they support multiple future tests.

## Current Product Surfaces

### Backend API

MP-facing APIs in `api_router.py`:

- Auth and session
- Dashboard summary
- Briefcase / cases
- Team and officers
- Escalations
- Profile and news
- Copilot
- Drafter
- Schemes
- SansadAI
- Parliament and Parliament Intel
- CSR
- Reports and history
- Letterbox
- Contacts
- Clusters
- Announcements

Admin-facing APIs in `admin_api.py`:

- Admin auth
- MP management
- Geography upload and curation
- Staff and editors
- Cases health, explorer, analytics
- Tenant analytics and health
- Announcements
- Audit and alerts
- Constituency profile generation/upload
- Parliament sync and answer fetch
- Brain indexing, crawl, classification, and scheme pipelines

### MP Frontend Pages

Located under `frontend/app/dashboard`:

- `page.js`
- `sansadx/page.js`
- `letterbox/page.js`
- `drafter/page.js`
- `copilot/page.js`
- `schemes/page.js`
- `sansadai/page.js`
- `parliament/page.js`
- `parliament-intel/page.js`
- `csr/page.js`
- `archives/page.js`
- `settings/page.js`

### Admin Frontend Pages

Located under `admin/app/dashboard`:

- `page.js`
- `analytics/page.js`
- `announcements/page.js`
- `audit/page.js`
- `brain/page.js`
- `constituency/page.js`
- `geography/page.js`
- `health/page.js`
- `intelligence/page.js`
- `mps/new/page.js`
- `mps/[tenant_id]/page.js`
- `mps/[tenant_id]/setup/page.js`
- `parliament-sync/page.js`
- `profiles/page.js`
- `rules/page.js`
- `settings/page.js`
- `staff/page.js`

## Next Recommended Sprint

The next sprint should deepen the highest-risk boundaries without adding too many tests at once.

Scope:

- Backend tenant isolation coverage
- Backend role restriction coverage
- MP Letterbox smoke depth
- Admin Geography smoke depth
- README test command documentation

Expected files added or extended:

- `tests/test_tenant_isolation_api.py`
- `tests/test_role_restrictions_api.py`
- `frontend/e2e/letterbox.spec.js`
- `admin/e2e/geography.spec.js`
- `README.md`

Definition of done:

- `npm run test:backend` passes
- `npm run test:e2e:mp` passes
- `npm run test:e2e:admin` passes
- `npm run test:all` passes locally
- `.github/workflows/product-tests.yml` includes the same blocking command through `npm run test:all`

## Phase 1: Backend Coverage Expansion

### Objective

Cover high-risk backend API boundaries with special attention to tenant isolation, role restrictions, and external side-effect control.

### Priority 1A: MP API Critical Paths

Add or extend tests for:

- `api_router.py` auth:
  - `/api/auth/login`
  - `/api/logout`
  - `/api/auth/me`
- Team management:
  - `/api/team`
  - `/api/team/{member_id}`
- Officer management:
  - `/api/officers`
- Briefcase adjacent flows:
  - `/api/staff`
  - `/api/profile`
  - `/api/news`
  - `/api/contacts/{phone}`
  - `/api/clusters`
  - `/api/announcements/active`

Expected files added or extended:

- `tests/test_auth_api.py`
- `tests/test_team_api.py`
- `tests/test_officers_api.py`
- `tests/test_contacts_api.py`
- `tests/test_announcements_api.py`
- `tests/test_tenant_isolation_api.py`
- `tests/test_role_restrictions_api.py`

Definition of done:

- Every privileged backend area touched in the sprint has at least one success-path test.
- Every privileged backend area touched in the sprint has role-restriction coverage.
- Tenant isolation is asserted on every tenant-scoped route group touched in the sprint.
- External integrations are monkeypatched in tests.
- `npm run test:backend` passes.
- `npm run test:all` passes locally.
- `.github/workflows/product-tests.yml` includes backend coverage through `npm run test:all`.

### Priority 1B: MP Feature APIs

Add or extend tests for:

- Copilot session lifecycle and failure paths
- Drafter generation permission/error handling
- Schemes browse/intelligence endpoints
- SansadAI intelligence endpoints
- Parliament data views
- Parliament Intel views
- CSR companies, proposals, pipeline, analytics
- Reports and history endpoints

Expected files added or extended:

- `tests/test_copilot_api.py`
- `tests/test_drafter_api.py`
- `tests/test_schemes_api.py`
- `tests/test_sansadai_endpoints.py`
- `tests/test_parliament_api.py`
- `tests/test_parliament_intel_api.py`
- `tests/test_csr_api.py`
- `tests/test_reports_api.py`
- `tests/test_history_api.py`

Definition of done:

- 2-3 reliable MP feature API tests are added per sprint.
- Fixtures are shared with existing backend tests where possible.
- `npm run test:backend` passes.
- `npm run test:all` passes locally.
- `.github/workflows/product-tests.yml` includes the command through `npm run test:all`.

### Priority 1C: Admin API Critical Paths

Add or extend tests for:

- Admin auth
- MP create/edit/delete lifecycle
- Geography CRUD and upload flows
- Staff and editors CRUD
- Announcements CRUD
- Cases explorer/health/analytics
- Tenant analytics and health
- Audit and alerts

Expected files added or extended:

- `tests/test_admin_auth_api.py`
- `tests/test_admin_mps_api.py`
- `tests/test_admin_geography_api.py`
- `tests/test_admin_staff_api.py`
- `tests/test_admin_announcements_api.py`
- `tests/test_admin_cases_api.py`
- `tests/test_admin_analytics_api.py`

Definition of done:

- 2-3 reliable admin API tests are added per sprint.
- Admin role restrictions are asserted for every privileged area touched.
- Tenant-scoped admin reads/writes include isolation assertions where applicable.
- `npm run test:backend` passes.
- `npm run test:all` passes locally.
- `.github/workflows/product-tests.yml` includes the command through `npm run test:all`.

## Phase 2: MP Frontend Coverage Expansion

### Objective

Extend the existing MP Vitest and Playwright harness into deeper workflow coverage.

Already implemented:

- `frontend/vitest.config.js`
- `frontend/test/setup.js`
- `frontend/playwright.config.js`
- `frontend/tests/login.test.jsx`
- `frontend/tests/dashboard.test.jsx`
- `frontend/e2e/auth.spec.js`
- `frontend/e2e/briefcase.spec.js`

Future MP browser flows:

- Letterbox review/update flow
- Drafter generation flow
- Copilot upload/analyse/chat flow
- CSR list and pipeline edit flow
- Settings save flow
- Logout

Expected files added or extended:

- `frontend/e2e/letterbox.spec.js`
- `frontend/e2e/drafter.spec.js`
- `frontend/e2e/copilot.spec.js`
- `frontend/e2e/csr.spec.js`
- `frontend/e2e/settings.spec.js`
- `frontend/tests/briefcase.test.jsx`
- `frontend/tests/letterbox.test.jsx`

Definition of done:

- 2-3 reliable MP frontend/browser tests are added per sprint.
- Existing MP fixtures are reused or minimally extended.
- `npm run test:mp` passes.
- `npm run test:e2e:mp` passes.
- `npm run test:all` passes locally.
- `.github/workflows/product-tests.yml` includes MP frontend and browser coverage through `npm run test:all`.

## Phase 3: Admin Frontend Coverage Expansion

### Objective

Extend the existing admin Vitest and Playwright harness into deeper configuration workflow coverage.

Already implemented:

- `admin/vitest.config.js`
- `admin/test/setup.js`
- `admin/playwright.config.js`
- `admin/tests/login.test.jsx`
- `admin/tests/dashboard.test.jsx`
- `admin/e2e/auth.spec.js`
- `admin/e2e/mps.spec.js`

Future admin browser flows:

- Geography upload and review
- Staff management
- Announcements CRUD
- Cases health/explorer navigation
- Parliament sync action + status polling
- Brain job trigger + status polling

Expected files added or extended:

- `admin/e2e/geography.spec.js`
- `admin/e2e/staff.spec.js`
- `admin/e2e/announcements.spec.js`
- `admin/e2e/cases.spec.js`
- `admin/e2e/parliament-sync.spec.js`
- `admin/e2e/brain.spec.js`
- `admin/tests/geography.test.jsx`
- `admin/tests/staff.test.jsx`
- `admin/tests/announcements.test.jsx`

Definition of done:

- 2-3 reliable admin frontend/browser tests are added per sprint.
- Existing admin fixtures are reused or minimally extended.
- `npm run test:admin` passes.
- `npm run test:e2e:admin` passes.
- `npm run test:all` passes locally.
- `.github/workflows/product-tests.yml` includes admin frontend and browser coverage through `npm run test:all`.

## Phase 4: Cross-Product End-To-End Flows

### Objective

Cover flows that span multiple product surfaces and are most likely to break silently.

Required flows:

- Citizen webhook intake -> Briefcase visibility
- Briefcase notify -> resolved status -> activity log
- Briefcase escalation -> officer escalation history
- Admin geography change -> downstream MP behavior changes
- Admin announcement -> MP dashboard visibility
- Admin tenant setup -> MP login and dashboard access

Expected files added or extended:

- `tests/test_cross_product_flows.py`
- `frontend/e2e/briefcase.spec.js`
- `admin/e2e/geography.spec.js`
- `admin/e2e/mps.spec.js`

Definition of done:

- 1-2 cross-product workflows are added per sprint.
- Workflows use deterministic seeded data or explicit browser mocks.
- `npm run test:backend` passes for backend-seeded flows.
- `npm run test:e2e:mp` and/or `npm run test:e2e:admin` passes for browser flows touched.
- `npm run test:all` passes locally.
- `.github/workflows/product-tests.yml` includes the command through `npm run test:all`.

## Phase 5: CI And Release Gates

### Objective

Keep regressions hard to merge and make test expectations visible.

Already implemented:

- `.github/workflows/product-tests.yml`
- Blocking CI command: `npm run test:all`

Future CI/release work:

- Add README documentation for test commands.
- Split slow confidence suites from blocking suites only if `npm run test:all` becomes too slow or flaky.
- Add nightly or pre-release workflows for broader browser coverage when the smoke suite is stable.

Expected files added or extended:

- `.github/workflows/product-tests.yml`
- `README.md`

Definition of done:

- `README.md` documents `npm run test:backend`, `npm run test:mp`, `npm run test:admin`, `npm run test:e2e:mp`, `npm run test:e2e:admin`, and `npm run test:all`.
- CI uses the same blocking command developers run locally.
- `npm run test:all` passes locally.
- GitHub Actions runs `npm run test:all` on push/PR.

## Blocking Vs Confidence Matrix

### Blocking

- Auth/session
- Tenant isolation
- Role restrictions
- Briefcase
- Letterbox
- Drafter basic flow
- Copilot basic flow
- CSR basic flow
- Admin MP management
- Admin geography
- Admin staff
- Admin announcements

### Confidence

- SansadAI depth views
- Parliament historical data exploration
- CSR analytics depth views
- Brain long-running tools
- Advanced report/export views

## Maintenance Rule

Once this roadmap starts landing, every change to a covered product area should:

1. Update or add tests in the relevant suite.
2. Run `npm run test:all`.
3. Avoid marking work complete if blocking tests fail.
