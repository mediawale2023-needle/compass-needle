# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Compass Needle serves Indian political offices and the platform operators who support them. The Admin application is used by trusted platform administrators to provision and launch MP, MLA, and aspirant accounts; maintain shared constituency data; diagnose case and AI quality; and operate messaging, government-data, and background-processing systems.

## Product Purpose

Compass Needle turns citizen grievance intake, constituency context, operational casework, and government follow-up into a tenant-safe working system. The Admin application is its control plane: it should make readiness gaps, failures, ownership, and the safest next action immediately legible.

## Positioning

Unlike a generic customer dashboard, Needle Admin connects account readiness, shared-seat geography, grievance intelligence, WhatsApp operations, government/parliament sync, and audit history without collapsing their distinct safety and ownership boundaries.

## Operating Context

- Administrators primarily work on desktop under time pressure, often moving from a global alert to one account, message, case, seat, or job run.
- Customer data belongs to tenants; shared geography belongs to a seat and may be used by multiple same-seat accounts.
- WhatsApp and government-sync operations require traceability, honest capability states, idempotent retry behavior, and clear account scope.
- Existing backend APIs and operational safeguards are the source of truth. The interface must not imply capabilities or metrics the system does not provide.

## Capabilities and Constraints

- The Admin information architecture is Command Centre; Accounts and Onboarding; Seats, Geography, and Maps; Case Intelligence, Knowledge, AI Engine, and Usage Analytics; WhatsApp and sync operations; System Health, Jobs, and diagnostics; Staff, Audit, Announcements, and Settings.
- Preserve authentication, authorization, tenant isolation, account creation, database schema, WhatsApp routing and auditing, government history semantics, Parliament sync semantics, and all existing safety checks.
- Government Sync and Parliament Sync are separate systems. Security-blocked or incomplete capabilities must be represented honestly.
- Operational data failures must render as unavailable, never as an empty or healthy state.
- No production deployment, direct push to `main`, or PR merge is part of the redesign work.

## Brand Commitments

The product name is Compass Needle. Admin should feel like the administrative counterpart of the MP Briefcase: warm, restrained, institutional, highly legible, and operationally efficient. Briefcase is the visual reference, while Admin owns independent semantic tokens and components.

## Evidence on Hand

- MP visual reference: `frontend/app/globals.css`, `frontend/components/Sidebar.js`, and `frontend/components/briefcase/`.
- Admin routes and real operational data contracts: `admin/app/dashboard/`, `admin/components/admin-domains/`, and `admin_api.py`.
- Durable architecture and safety constraints: `AGENTS.md` and `PROJECT_MEMORY.md`.
- Existing Admin unit and browser tests under `admin/tests/` and `admin/e2e/`.
- No fabricated testimonials, benchmarks, operational metrics, or unsupported sync capabilities may be introduced.

## Product Principles

1. Put urgent, actionable operational truth before summary reporting.
2. Preserve account, seat, case, message, and operation context across navigation.
3. Distinguish empty, healthy, loading, unavailable, blocked, and failed states explicitly.
4. Prefer direct task access and persistent local navigation over directory-style landing pages.
5. Make ownership and safety boundaries visible without exposing secrets or sensitive payloads.

## Accessibility & Inclusion

The web interface must remain keyboard navigable, provide visible focus, labelled controls, readable tables and responsive overflow, adequate contrast, reduced-motion support, and resilient layouts for long Indian names and constituency labels. It is desktop-first but must remain usable on narrower screens.
