# Needle Political Advisory Network — consultancy channel

Sell Needle through political consultancies instead of selling to each aspirant. One consultancy sale = 5–20 aspirant clients, with no cap on how many it can bring. Consultancies already own the trust, the retainer and the weekly client meeting; Needle supplies the ground intelligence they currently can't produce cheaply.

**Status of the product side (as built):** partner accounts, **partner attribution during normal tenant onboarding** (Needle staff pick Direct or a partner; the partner association is created and activated automatically), audited attribution reassignment, aggregate client API, white-label HTML report, the partner web dashboard at `/partner` (MP frontend: sign-in, portfolio, client detail, report preview) and the Needle-team screen at **Customers → Partners** in the Admin app. There are **no seat limits** and partners do **not** request seats. **Not built yet:** automated billing, per-partner WhatsApp branding. See "What is and isn't live".

---

## 1. The offer (one line)

> "Give every client a live constituency war-room under your brand: every grievance on the ground, classified, mapped to wards, resolved, and reported weekly — without you hiring a single field analyst."

What the consultancy gets:
- Any number of clients (aspirant MLA/MP or sitting rep), each with its own WhatsApp grievance intake and dashboard. Needle onboards each one and attributes it to the consultancy; nothing for the consultancy to request or approve.
- A **portfolio view**: all clients, one login, side-by-side resolution rates, critical cases, volumes.
- A **white-label weekly report** per client (their logo, colour, their name on the footer). Print or PDF from the browser.
- Day-one value that doesn't depend on citizen traffic: constituency intelligence report for each seat (answers the "empty dashboard" churn risk).

What the consultancy does **not** get: citizen names, phone numbers or message text. Aggregates only. This is a feature in the pitch (DPDP-safe, no data-handler liability), not a limitation.

## 2. Commercials (placeholders — set your own numbers)

Model: **per-client, white-label, unlimited clients.** Needle invoices the consultancy only. The consultancy sets its own resale price to its client.

| | Per active client / month |
|---|---|
| Wholesale to consultancy (suggested) | ₹15,000 |
| Suggested resale to client | ₹35,000–60,000 |
| Consultancy margin | ₹20,000–45,000 |

Worked example: 10 clients × ₹40,000 resale − 10 × ₹15,000 wholesale = **₹2.5 lakh/month margin** for the consultancy; ₹1.5 lakh/month revenue for Needle from one signed partner.

Rules that protect Needle:
- No cap on clients per partner. The only gate is that Needle staff onboard each tenant.
- Pilot: **first 2 clients free for 60 days**, in exchange for an agreed case study (named or anonymised).
- No-direct-sales clause: Needle does not sell to a partner-attributed client directly during the term and 12 months after. Client attribution is the `tenant_attributions` row (with its history), and the partner's access is the `partner_seats` row.
- Billing is manual for now: the partner's `wholesale_price_inr` is stored per client; invoice monthly by **active** attributed clients (paused clients are not billed). The Partners screen shows `active clients × price` as the estimate.

## 3. Who to sign first (inbound targets)

Not "all consultancies". The first five should be:
1. Small campaign-management firms (3–15 people) running 3+ aspirants in the same state for the 2027 UP/Goa cycle.
2. Ex-political-staffer boutiques who sell "ground reports" to MPs/MLAs.
3. PR firms with an election/political vertical.

Skip big national firms at first: long procurement, and they have in-house tools.

## 4. Inbound motion (no cold calling)

The partner never needs a call from you; they need a reason to message you.

1. **Constituency snapshot, free, public.** Publish 10 ward-level snapshots (from the Belgaum Dakshin method) for seats consultancies are working on. The footer: "Run this for all your clients — Needle Political Advisory Network." Share via journalists, not DMs.
2. **/partners landing page** with a single call to action: WhatsApp click-to-chat, "Request partner access". Page copy is in section 6.
3. **Founder posts** (LinkedIn/X): one data observation per week from real grievances ("what 10,000 complaints in one ward say"), ending with the partners link.
4. **Warm-introduction hook for your journalist network:** give them the line "Needle gives consultancies a live read of the ground — ask them for the sample report." Journalists forward; consultancies ask.
5. **Partner referral:** every partner gets the public snapshot template. Their clients forward it; other consultancies see whose brand is on it.

## 5. Pitch one-pager (send on request)

**Headline:** Your clients' constituencies, in one login.

**The problem:** You report on the ground from rallies and surveys. Your client's own office knows 10x more, and nobody structures it.

**What Needle does:** Citizens message a WhatsApp number. Needle classifies each grievance, maps it to a ward, tracks it to resolution and prepares the filing for the right government portal (staff-assisted). You see all of it, for all your clients, under your brand.

**What you can promise your client next week:**
- "Govern before you're elected": a working grievance desk before the ballot.
- A weekly report with resolution rate, critical cases, top issue categories and top locations.
- A named, measurable ground presence in every ward.

**Proof (fill after pilot):** [X] grievances logged, [Y]% resolved, [Z] wards covered in [N] days.

**Terms:** Wholesale per client, you set your price, white-label reports, 60-day pilot of 2 clients. Aggregate data only; citizen details never leave Needle.

## 6. /partners landing page copy

- **H1:** Run a ground-intelligence desk for every client. Without hiring one.
- **Sub:** Needle gives political consultancies a white-label constituency dashboard: live grievances, ward maps, resolution tracking and a branded weekly report per client.
- **3 blocks:** *One login, all clients* · *Your brand on every report* · *Day-one value before the first complaint arrives*
- **Proof strip:** pilot numbers, one quote.
- **FAQ:** data privacy, who owns the client, pricing model, setup time (target: 48 hours from approval).
- **CTA:** "Request partner access" → WhatsApp click-to-chat pre-filled "Partner access for [firm name]".

## 7. Objection handling

| Objection | Answer |
|---|---|
| "You'll go to my client directly." | Contractual no-direct-sales clause; the client is attributed to you in the attribution record; Needle only invoices you. |
| "Whose data is it?" | The client's. You see aggregates, never citizen details, so you carry no data-handler risk. |
| "What if the client's inbox is empty?" | Every client starts with a constituency intelligence report, so the dashboard has content on day one. |
| "My clients are aspirants with no office." | That's the point: aspirants get a grievance desk before election day. Seat type is `mla`/`mp` with aspirant stage. |
| "Rep fears anti-incumbency if they promise and fail." | Reports show resolution rate honestly; Needle files and tracks, so promises are backed by an actual process. |
| "Too expensive." | Resale price is yours. At ₹40k resale and ₹15k wholesale, 3 clients cover a junior analyst's salary. |
| "We have our own tool." | Keep it; Needle supplies the ground-truth feed. |

## 8. Partner onboarding playbook (target: 48 hours)

**The flow:** Needle staff create the tenant → choose *Direct* or *Partner* → tenant is created → the partner association is created **and activated automatically** → the partner sees the tenant in its portfolio.

Setting up the partner (Admin → Customers → Partners; API for reference):

1. Create the partner: `POST /api/admin/partners` (name, brand name, colour, https logo URL, wholesale price per client). There is no seat limit field.
2. Create the partner login: `POST /api/admin/partners/{id}/users` returns a one-time temporary password. Send it over a secure channel; the user must change it on first login.

Bringing in a client (the normal Onboarding form, **Customers → Onboarding**, step 1):

3. Under **How did this tenant come to Needle?** keep *Direct — Needle* (default) or choose *Partner / Consultancy* and pick the partner. Only **active** partners are offered (`GET /api/admin/partners/selectable`). A partner is mandatory for Partner acquisition.
4. Submit. `POST /api/admin/mps` accepts `acquisition_channel` (`direct` | `partner`) and `partner_id`. In ONE transaction the backend creates the tenant, owner login and profile, records the attribution (channel, partner, timestamp, the staff member from the verified token) and, for partner tenants, creates the partner association with status `active`. If anything fails (including an inactive or unknown partner) nothing is created. Direct tenants get no partner association and no partner can see them.
5. The partner signs in at `/partner` on the MP frontend host and the client is already in the portfolio. (API: `GET /api/partner/clients`, `GET /api/partner/clients/{seat_id}/report`.)

Staff can see acquisition on **Account 360** (channel, partner, date, who attributed, partner access state). It is never exposed to the tenant.

**Changing attribution later** (rare, deliberately separate from the profile form): Account 360 → *Change attribution*, or `POST /api/admin/partners/tenants/{tenant_id}/attribution/reassign` with `{"partner_id": <id or null for Direct>, "reason": "..."}`.
- **Authorized:** `super_admin` / `sysadmin` only. Ordinary `admin` gets 403.
- **Required:** a reason (5–500 characters); the new partner must be active.
- **Atomic:** the previous partner's association is revoked and detached, and the new one created, in a single commit. The tenant never has two active partner associations, and the previous partner loses access in the same instant the new one gains it.
- **Audited:** an immutable row in `tenant_attribution_events` (old and new partner, reason, staff member, timestamp) plus an admin audit-log entry. `GET /api/admin/partners/tenants/{tenant_id}/attribution` returns the current attribution and history.

Other operations:
- **Pause a client** (partner loses access, attribution unchanged, not billed): `POST /api/admin/partners/{id}/seats/{seat_id}/status` with `{"status": "paused"}`; resume with `"active"`.
- **Deactivate a partner:** `PATCH /api/admin/partners/{id}` with `{"is_active": false}`. Tokens stop working on the next request; attribution is untouched; the partner can no longer be chosen for new tenants.
- **Deleting a tenant** revokes its partner association (kept as history) and logs a `tenant_deleted` event.

**Legacy seat requests.** Before attribution moved into onboarding, partners could request seats (`POST /api/partner/seat-requests`). That endpoint and the partner-side form are removed. Any old `requested`/`rejected` rows are kept as history, hidden from partners, and shown to staff under *Legacy seat requests* only when some exist; staff can link one to an existing account (goes through the same one-partner-per-tenant rule and writes the attribution) or decline it.

**Startup race.** `init_db()` (`create_all`) is not serialised across workers, so on the first deploy two workers can both try to create the new attribution tables and one gets a duplicate-relation error. `main.py` retries `init_db()` once (2 s later) so a lost race never leaves later migrations skipped; verified with `uvicorn --workers 2` on a legacy PostgreSQL DB.

**Migration (expand / contract).** The release that removed seat limits is *phase 1* and only adds: at backend startup `ensure_partner_schema` creates `tenant_attributions` and `tenant_attribution_events`, backfills one attribution row (`attributed_by = 'migration'`) for every existing active/paused seat, and **keeps** the retired `partners.seat_cap` column (giving it a column default so partners created during a rollout are never NULL for older instances). Nothing in this release reads or writes `seat_cap`. *Phase 2* drops the column later, by hand, once every instance runs this release or newer: `python scripts/partner_drop_seat_cap.py` is a dry run; add `--execute --confirm-no-old-instances` to drop it. The script takes the startup migration lock, refuses if phase 1 is incomplete, and is safe to re-run.

**Deploying (read before the first rollout).**
- *EC2* (`deploy/ec2/docker-compose.yml`): the workflow runs `docker compose up -d --build backend backend_govt_live`, which recreates the two backend services one after the other, and `backend` runs two workers (`WEB_CONCURRENCY=2`). For a while old and new code run against the same database. That is why phase 1 does not drop `seat_cap`.
- *Railway* (`railway.toml`): health-check window 120 s, restart on failure. Railway's rollout overlap behaviour is configured in the Railway project, not in this repository, so it was not verified here; the expand/contract split makes either behaviour safe.
- **Do not run phase 2 in the same deploy.** Wait until the new release is live on every service/worker, then run the script once.

**Failure handling.** Only the process that holds advisory lock `77772024` (the startup migration lock) runs the partner migration. A process that cannot take the lock does not migrate: it reports not-ready until the schema is complete and a background retry (every `PARTNER_SCHEMA_RETRY_SECONDS`, default 10) either sees the other instance finish or takes the lock itself. A genuine failure (permissions, connectivity, bad data) logs a `CRITICAL` "PARTNER SCHEMA MIGRATION FAILED" line with the cause and: `/health` returns **503** (`status: degraded`, `partner_schema`, `detail`), and the partner portal, partner admin, and tenant onboarding (`POST /api/admin/mps`) answer 503 with `Retry-After`. Citizen WhatsApp intake and the rest of the app keep serving. The retry makes recovery automatic; the migration is idempotent, so restarting is also safe.

## 9. What is and isn't live

Live in code (tests in `tests/test_partner_api.py`):
- Separate partner login with forced first-login password change and token revocation on password change.
- Partner tokens use a derived signing key, so they fail on every MP/admin route and vice versa.
- Every partner query resolves the seat by `partner_id` first; tenant ids never come from request input.
- No seat limits anywhere. One acquisition partner per tenant (DB-unique `tenant_attributions.tenant_id` and `partner_seats.tenant_id`, plus a CHECK that direct has no partner and partner has one), admin audit entries on every admin action.
- Attribution is written by the backend only, in the same transaction as tenant creation; the request can never set who attributed it, when, or the association status.
- Aggregate metrics only: total, resolved, open, critical, resolution rate, avg days to resolve, top categories/locations, 8-week trend.
- White-label report: all values HTML-escaped, https-only logo, validated hex colour, optional "Powered by Compass Needle" footer.

Partner web dashboard (`frontend/app/partner/*`, tests in `frontend/tests/partner-*.test.*`):
- `/partner` sign-in with forced first-login password change; `/partner/dashboard` portfolio (7/30/90-day period, active-client count, per-client status and numbers; no request form and no cap indicator); `/partner/dashboard/clients/{seatId}` client detail (headline numbers, 8-week chart, top categories/locations, branded report in a fully sandboxed preview, open-to-print and download).
- Partner colour and logo theme the dashboard; "Powered by" footer follows the partner's setting.
- Load failures show an explicit "unavailable" state with retry, never zeros; empty portfolio and failed load are different screens.
- Partner token is kept in `sessionStorage` under its own key, separate from MP/admin tokens.

Not built:
- Admin screen covers: create/edit partner (brand, colour, logo, wholesale price, powered-by), deactivate/reactivate, partner logins (add, reset password with a one-time temporary password, deactivate), attributed clients with pause/resume, legacy request linking/decline, and monthly wholesale estimate. Failed loads show "unavailable", never an empty list.
- Attribution UI: the Onboarding form's acquisition section and the Account 360 acquisition card (with super-admin-only *Change attribution*).
- Billing and invoicing; WhatsApp-number branding per partner.
- Per-partner login lockout beyond the shared login rate limit (5/min).
- Case-level access for partners. This is deliberate. If a partner needs it, treat it as a separate permissioned feature with a client-side consent record.

## 10. First 30 days

| Week | Do |
|---|---|
| 1 | Create one demo partner and two seats on seeded data; generate the report PDF. Publish the first 3 public snapshots. |
| 2 | Build the /partners page (copy above). Send the one-pager to journalists, not to consultancies. |
| 3 | Respond to inbound only. Sign 1–2 pilot partners (2 free seats each). |
| 4 | Collect the first resolution numbers from pilot seats; turn them into the proof strip and the case study. |
