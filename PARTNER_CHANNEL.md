# Needle Political Advisory Network — consultancy channel

Sell Needle through political consultancies instead of selling to each aspirant. One consultancy sale = 5–20 aspirant seats. Consultancies already own the trust, the retainer and the weekly client meeting; Needle supplies the ground intelligence they currently can't produce cheaply.

**Status of the product side (as built):** partner accounts, seat requests, admin approval/linking, aggregate client API, white-label HTML report, the partner web dashboard at `/partner` (MP frontend: sign-in, portfolio, client detail, report preview, seat requests) and the Needle-team screen at **Customers → Partners** in the Admin app. **Not built yet:** automated billing, per-partner WhatsApp branding. See "What is and isn't live".

---

## 1. The offer (one line)

> "Give every client a live constituency war-room under your brand: every grievance on the ground, classified, mapped to wards, resolved, and reported weekly — without you hiring a single field analyst."

What the consultancy gets:
- A seat per client (aspirant MLA/MP or sitting rep), each with its own WhatsApp grievance intake and dashboard.
- A **portfolio view**: all clients, one login, side-by-side resolution rates, critical cases, volumes.
- A **white-label weekly report** per client (their logo, colour, their name on the footer). Print or PDF from the browser.
- Day-one value that doesn't depend on citizen traffic: constituency intelligence report for each seat (answers the "empty dashboard" churn risk).

What the consultancy does **not** get: citizen names, phone numbers or message text. Aggregates only. This is a feature in the pitch (DPDP-safe, no data-handler liability), not a limitation.

## 2. Commercials (placeholders — set your own numbers)

Model: **per-client seats, white-label.** Needle invoices the consultancy only. The consultancy sets its own resale price to its client.

| | Per seat / month |
|---|---|
| Wholesale to consultancy (suggested) | ₹15,000 |
| Suggested resale to client | ₹35,000–60,000 |
| Consultancy margin | ₹20,000–45,000 |

Worked example: 10 clients × ₹40,000 resale − 10 × ₹15,000 wholesale = **₹2.5 lakh/month margin** for the consultancy; ₹1.5 lakh/month revenue for Needle from one signed partner.

Rules that protect Needle:
- `seat_cap` per partner (default 5, raise on request) — set when the partner is created.
- Pilot: **first 2 seats free for 60 days**, in exchange for an agreed case study (named or anonymised).
- No-direct-sales clause: Needle does not sell to a partner-attributed client directly during the term and 12 months after. Client attribution is the `partner_seats` row.
- Billing is manual for now: the partner's `wholesale_price_inr` is stored; invoice monthly by active seat count.

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

**Terms:** Wholesale per seat, you set your price, white-label reports, 60-day pilot of 2 seats. Aggregate data only; citizen details never leave Needle.

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
| "You'll go to my client directly." | Contractual no-direct-sales clause; the client is attributed to you in the seat record; Needle only invoices you. |
| "Whose data is it?" | The client's. You see aggregates, never citizen details, so you carry no data-handler risk. |
| "What if the client's inbox is empty?" | Every seat starts with a constituency intelligence report, so the dashboard has content on day one. |
| "My clients are aspirants with no office." | That's the point: aspirants get a grievance desk before election day. Seat type is `mla`/`mp` with aspirant stage. |
| "Rep fears anti-incumbency if they promise and fail." | Reports show resolution rate honestly; Needle files and tracks, so promises are backed by an actual process. |
| "Too expensive." | Resale price is yours. At ₹40k resale and ₹15k wholesale, 3 clients cover a junior analyst's salary. |
| "We have our own tool." | Keep it; Needle supplies the ground-truth feed. |

## 8. Partner onboarding playbook (target: 48 hours)

Done from **Admin → Customers → Partners** (API endpoints listed for reference):

1. Admin creates the partner: `POST /api/admin/partners` (name, brand name, colour, https logo URL, `seat_cap`, wholesale price).
2. Admin creates the partner user: `POST /api/admin/partners/{id}/users` returns a one-time temporary password. Send it over a secure channel; the user must change it on first login.
3. Partner logs in at `POST /api/partner/auth/login`, changes password, then requests seats: `POST /api/partner/seat-requests`.
4. Needle provisions the client tenant with the normal aspirant flow (admin `POST /api/admin/mps`, then WhatsApp number and geography).
5. Admin links it: `POST /api/admin/partners/{id}/seats/{seat_id}/activate` with `tenant_id`.
6. Partner signs in at `/partner` on the MP frontend host and sees the portfolio, client pages and branded reports. (Underlying API: `GET /api/partner/clients`, `GET /api/partner/clients/{seat_id}/report`.)

Pause a client: `POST .../seats/{seat_id}/status` with `{"status": "paused"}` (stops the partner seeing that client's data immediately). Deactivate a partner: `PATCH /api/admin/partners/{id}` with `{"is_active": false}`; tokens stop working on the next request.

## 9. What is and isn't live

Live in code (tests in `tests/test_partner_api.py`):
- Separate partner login with forced first-login password change and token revocation on password change.
- Partner tokens use a derived signing key, so they fail on every MP/admin route and vice versa.
- Every partner query resolves the seat by `partner_id` first; tenant ids never come from request input.
- Seat cap, one tenant per seat (DB unique), admin audit entries on every admin action.
- Aggregate metrics only: total, resolved, open, critical, resolution rate, avg days to resolve, top categories/locations, 8-week trend.
- White-label report: all values HTML-escaped, https-only logo, validated hex colour, optional "Powered by Compass Needle" footer.

Partner web dashboard (`frontend/app/partner/*`, tests in `frontend/tests/partner-*.test.*`):
- `/partner` sign-in with forced first-login password change; `/partner/dashboard` portfolio (7/30/90-day period, seat usage, per-client status and numbers, seat request form); `/partner/dashboard/clients/{seatId}` client detail (headline numbers, 8-week chart, top categories/locations, branded report in a fully sandboxed preview, open-to-print and download).
- Partner colour and logo theme the dashboard; "Powered by" footer follows the partner's setting.
- Load failures show an explicit "unavailable" state with retry, never zeros; empty portfolio and failed load are different screens.
- Partner token is kept in `sessionStorage` under its own key, separate from MP/admin tokens.

Not built:
- Admin screen covers: create/edit partner (brand, colour, logo, seat cap, wholesale price, powered-by), deactivate/reactivate, partner logins (add, reset password with a one-time temporary password, deactivate), seat requests queue, activate (link an unlinked customer account), decline, pause/resume. Failed loads show "unavailable", never an empty queue.
- Creating the customer account itself still happens in Onboarding; the activate dialog links there.
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
