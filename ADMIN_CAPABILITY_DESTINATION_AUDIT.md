# Admin Capability Destination Audit

Date: 2026-10-01  
Branch: `admin-briefcase-phase1`

This checklist verifies that the Admin redesign preserves the pre-existing operator capabilities. It records the canonical destination and the compatibility route where one exists. It does not assert new backend behavior.

| Previous capability | Canonical destination | Compatibility / context | Status |
|---|---|---|---|
| Admin overview and aggregate statistics | `/dashboard` | Command Centre uses existing stats, alerts, health, and accounts APIs | Preserved |
| Create customer account | `/dashboard/accounts/new` | `/dashboard/mps/new` redirects here | Preserved |
| Browse and edit account profiles/credentials | `/dashboard/accounts` and `/dashboard/accounts/registry` | Searchable registry; WhatsApp and geography edits link to their canonical tenant surfaces | Preserved |
| Tenant setup and launch readiness | `/dashboard/mps/[tenant_id]` and `/dashboard/mps/[tenant_id]/setup` | Account queue links retain tenant context | Preserved |
| Tenant WhatsApp routing configuration | `/dashboard/mps/[tenant_id]#whatsapp` | Linked from account profile editor | Preserved |
| Tenant staff context and support access | `/dashboard/mps/[tenant_id]` plus `/dashboard/staff-access/users` | Existing tenant-approved support-session controls unchanged | Preserved |
| Seat registry | `/dashboard/seats` | `/dashboard/shared-geography` redirects to the registry | Preserved |
| Seat detail, shared geography, boundary, quality, linked accounts | `/dashboard/seats/[seatKey]` | Existing shared-seat data ownership unchanged | Preserved |
| Shared geography workspace and manual corrections | `/dashboard/shared-geography/workspace` | `/dashboard/geography` and `/dashboard/shared-geography/rules` redirect here; `tenant_id` is retained by the rules redirect | Preserved |
| Seat boundary/map generation and import | `/dashboard/seat-maps` | Existing import and job APIs unchanged | Preserved |
| Constituency intelligence profile generation/editing/indexing | `/dashboard/constituency` | Directly reachable from persistent Case Operations navigation | Preserved |
| Case Explorer / platform diagnosis | `/dashboard/cases-intelligence/explorer` | `/dashboard/intelligence` and `/dashboard/cases-intelligence` redirect here | Preserved |
| Knowledge readiness and content coverage | `/dashboard/cases-intelligence/knowledge` | `/dashboard/knowledge` redirects here | Preserved |
| AI engine configuration/diagnostics | `/dashboard/cases-intelligence/engine` | `/dashboard/brain` redirects here | Preserved |
| Usage analytics | `/dashboard/cases-intelligence/analytics` | `/dashboard/analytics` redirects here | Preserved |
| WhatsApp health, tenant routing, outbound failures and retry review | `/dashboard/system/whatsapp` | Overview/Outbound/Failures/Retry Queue anchors; retries only on confirmed failures | Preserved and safety clarified |
| WhatsApp inbound processing ledger | `/dashboard/system/whatsapp-inbound` | Failed rows retain existing audited retry endpoint; in-flight rows require investigation | Preserved and safety clarified |
| Parliament identity/data/answer sync | `/dashboard/system/parliament-sync` | `/dashboard/parliament-sync` redirects here; existing resolution/backfill semantics unchanged | Preserved |
| Government portal filing/status/history | MP Briefcase case workflow | This is tenant/case operational work, not an Admin-wide sync system; no fictitious Admin control was added | Preserved at existing destination |
| Tenant activity health | `/dashboard/system/health` | `/dashboard/health` redirects here | Preserved |
| Background/admin-triggered job history | `/dashboard/system/jobs` | Includes existing seat-map, boundary, Parliament resolution, and backfill operations | Preserved |
| Staff creation, role edit, reassignment, suspension/reactivation | `/dashboard/staff-access/users` | `/dashboard/staff` and `/dashboard/staff-access` redirect here | Preserved |
| Administrative audit log and structured geography changes | `/dashboard/staff-access/audit` | `/dashboard/audit` redirects here | Preserved |
| Platform announcements | `/dashboard/system/announcements` | `/dashboard/announcements` redirects here | Preserved |
| Admin password and restricted editor management | `/dashboard/system/settings` | `/dashboard/settings` redirects here; editor removal now confirmation-gated | Preserved |

## Safety and architecture checks

- No backend API, database model, migration, authentication, authorization, tenant filter, WhatsApp processor, government adapter, or Parliament sync implementation changed in this redesign.
- Existing destructive actions remain confirmation-gated; editor access removal now also uses confirmation.
- Operational failures are distinct from healthy/empty results on the Command Centre, account profile, WhatsApp, tenant health, jobs, and audit surfaces.
- Parliament Sync status, record counts, and record loads now preserve `unavailable` separately from zero/empty results; unsafe bulk resolution is disabled while sync status is unavailable.
- Tables used in the revised high-density workflows have labelled horizontal overflow regions for narrow displays.
- The global domain navigation remains available below 1024px through a labelled, backdrop-dismissable menu; Parliament record drawers expose dialog semantics, focus containment, Escape close, focus restoration, and keyboard-operable question expansion.
- Old route-shaped entry points remain redirects unless they still own a unique capability (`/dashboard/constituency`).

## Final verification

- Admin unit tests: 8 files / 19 tests passed.
- Admin Playwright: 3/3 passed on an isolated port, including sign-in, account creation, and 390px navigation.
- Admin production build: passed.
- MP frontend unit tests: 9 files / 75 tests passed.
- MP frontend production build: passed.
- Backend: 1007 passed / 14 failed. The failures are outside this frontend-only diff and group into a missing local `slowapi` dependency, stale seat-association fixtures, and WhatsApp fixtures whose receiver number no longer resolves to a tenant.
- MP Playwright authentication: reproduced before implementation as a pre-existing dev-server/Fast Refresh navigation failure; the PR branch and `origin/main` auth/page/spec files were byte-identical, and no MP authentication code was changed.
- The Impeccable detector reported two side-accent cards and four width transitions; all six were corrected. The contextual finish review's four P1 findings (mobile navigation, Parliament unavailable states, Parliament drawer keyboard/dialog semantics, and muted-text contrast) were also corrected and reverified.
