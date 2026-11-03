# Delhi CM Jan Sunwai — verified capability map

Official portal: https://cmjansunwai.delhi.gov.in/  ·  Research date: 2026-10-31  ·  Status: **research evidence only; no production change**

## How this was established (and what was NOT done)
Plain `GET` requests to five public pages, exactly as a visitor's browser loads them: `/`, `/onlineComplaint`, `/ComplaintTracker`, `/SendReminder`, `/onlineFeedbackEntry`.
Facts below come from the rendered markup and the pages' **own inline scripts** (which show the requests the browser itself makes).
**Not done:** no form submitted, no OTP requested, no CAPTCHA fetched or solved, no AJAX endpoint called (`SendOtp`, `sendOTPWithVrifyCapcha`, `varifyOTP`, `fullCompDetailsOfUser`, `fetchReminderInfo`, `SendOPTreminder`, `findComplaintByMobileOrEmail`, `Captcha.jpg` are named in page scripts only), no cookie replay, no ID enumeration, no real grievance created.
A commented-out link (`resources/pdf/Post_Category_Mapping.pdf`) was seen in page source and deliberately **not** fetched (not a published link).
Everything that sits behind an OTP is therefore **UNKNOWN**: it cannot be observed without a real SMS OTP to a real mobile number and a real complaint.

**Update (2026-11-02): department/category lists.** The portal's department and category selection lists were later captured from the public selection controls and are held in `modules/data/delhi_catalogue.json` (see "Department/category catalogue" below). That capture is not a status, OTP or complaint-form observation: the statements about status retrieval, history, disposal and OTP scope in this document are unchanged.

Label key: **VERIFIED** = read from the official page/script · **UNKNOWN** = not observable without OTP/real complaint · **INFERRED** = reasonable reading, not proof.

## 1. Citizen services (home page text)
| Service | Page | Home-page description |
|---|---|---|
| Complaint Registration | modal on `/` → `/onlineComplaint` | "easy registration through mobile OTP" — VERIFIED |
| Complaint Status | `/ComplaintTracker` | "Track complaint through registered mobile number/email ID" — VERIFIED |
| Send reminders | `/SendReminder` | "If the complaint is not resolved within the stipulated time, the complainant can send a reminder" — VERIFIED |
| Your feedback | `/onlineFeedbackEntry` | feedback "on the quality of disposal… higher authorities… can revive the disposed references" — VERIFIED |
Separate **Officer Login** (`/login`, username/password) exists for officers only. A citizen "Delhi Janmitra" app/account exists (feedback page: "Don't have an account? Create Account"); whether accounts offer an OTP-free status view is **UNKNOWN** (not investigated).
Platform: Java server-rendered (`JSESSIONID`, `Server: Bramhas`), CSRF tokens, per-page `randomkey`/`randomToken`, strict CSP. Reachability from the Needle EC2 host: **UNKNOWN** (Maharashtra's portal blocks that host; Delhi not tested).

## 2. Filing (registration)
| Item | Finding | Label |
|---|---|---|
| Entry | Home page → "Complaint Registration" opens a disclaimer modal; checking "I agree that my grievance does not fall in any of the above listed categories" enables Submit, whose script navigates to `/onlineComplaint`. Excluded subjects: RTI matters; sub-judice matters; government-employee service matters incl. transfers. | VERIFIED (client-side) |
| Step 1 form (`POST /onlineComplaint`) | Mobile number (10 digits) · image CAPTCHA (6 chars, `/Captcha.jpg`) · mobile OTP (6 digits, 2-minute timer, resend) · hidden `_csrf`, `salt`, `iv`, `hdnMob` | VERIFIED |
| OTP delivery | page script: `GET SendOtp?mobileno=…&email=…&captcha=…`; response `captchaError` means wrong CAPTCHA | VERIFIED (script) — never called |
| Complaint form after OTP (fields, subject/description limits, departments/categories, attachments, address/identity data) | not observable without OTP | **UNKNOWN** |
| Reference-number generation / acknowledgement | not observable | **UNKNOWN** |
| Can submission be done over plain HTTP? | form carries CSRF + client-side encryption fields → browser interaction expected; not verified | **UNKNOWN / INFERRED: browser** |
| Reference format | the tracker only accepts a **numeric** code, input-masked to **14 digits** (`maxlength=14`, `isNumeric()`); exact length not shown. The tracker script also reads the first digit as a complaint "type". | VERIFIED (≤14 digits, numeric); exact length UNKNOWN |

## 3. Status retrieval (`/ComplaintTracker`)
Inputs (all VERIFIED): complaint code (numeric, ≤14) · **mobile (10) OR e-mail** · image CAPTCHA (6) · OTP (6).
Sequence from the page script (VERIFIED, never executed):
1. `GET /sendOTPWithVrifyCapcha?capthca=<captcha>&randomkey=<key>&mobile=<m>&email=<e>` — CAPTCHA is validated **before** the OTP is sent; a 5-character response is treated as success.
2. `GET varifyOTP?capcha=<captcha>&otp=<otp>&SessRandomKey=<key>` — `OK` means verified.
3. `GET fullCompDetailsOfUser?complanitcode=<code>&capthca=<captcha>&randomkey=<key>&otp=<otp>` — loaded in an iframe; the response is a **server-rendered page**, not JSON.
Also referenced: a helper `findComplaintByMobileOrEmail` (find your complaint numbers), and a "work tree" history view `/ajaxCheck/ajax_get_reject_delhi_MarkingTree_app_status_work_tree?comp_code=…&complaintType=…&forwardid=…` (so some forwarding/marking history exists).
| Item | Label |
|---|---|
| status text, department, officer, comments/replies, disposal details | **UNKNOWN** (post-OTP page not observable) |
| status history | **UNKNOWN** — a marking/work-tree view exists; content and access rules not observed |
| OTP/session scope | **UNKNOWN.** Heading says "Get Registered Complaints From Mobile No/Email" (suggests mobile/e-mail scope) but the details request names one complaint code; verification is tied to a per-page `randomkey` + server session. No evidence that one verification can be reused for a later lookup. |
| Needs a human CAPTCHA + SMS OTP on every lookup? | VERIFIED that both fields are required on the form; reuse **UNKNOWN** → treated as per-lookup human interaction |

## 4. Authentication classification (independent axes, per `adapters/__init__.py` rules)
| Operation | Authentication | Human verification | OTP scope | Execution in Needle |
|---|---|---|---|---|
| Registration | Mobile OTP (VERIFIED) | image CAPTCHA (VERIFIED) | per registration; reuse UNKNOWN | Manual / staff-assisted (portal tab + AI worksheet) |
| Status | Mobile **or e-mail** OTP (VERIFIED) | image CAPTCHA (VERIFIED) | **UNKNOWN** (mobile/e-mail scope suggested, not proven) | Manual / staff-assisted |
| Reminder | OTP to registered mobile/e-mail (VERIFIED) | image CAPTCHA (VERIFIED) | grievance-specific action; scope UNKNOWN | Manual / staff-assisted |
| Feedback | OTP (VERIFIED) to registered mobile | image CAPTCHA (VERIFIED) | UNKNOWN | Manual / staff-assisted |
Not AccountSession and not NoAuth for any citizen operation on the evidence available. **Automatic polling is not supportable on current evidence** (human CAPTCHA + SMS OTP appear to be needed per lookup, and the result page cannot be interpreted).

## 5. Reminders and feedback (VERIFIED field lists)
* **Reminder** (`/SendReminder`): complaint number (≤14) → search; registered mobile **or** e-mail; CAPTCHA (6); OTP (6).
* **Feedback** (`/onlineFeedbackEntry`): only for **disposed** complaints; grievance id (≤14) + registered mobile; star rating (1–2 stars send the reference back to a higher authority); free-text feedback (required); "contacted by the authority?" and "officer visited?" yes/no; CAPTCHA (6); OTP (6, 3-minute timer). Optional "User Id".

## 6. What this means for the Needle build
Buildable and testable now: Delhi tenant routing with **no CPGRAMS fallback** · AI worksheet for **subject + description** (staff choose department/category from Needle's catalogue copy of the portal lists, or type what the portal shows; the AI may only *suggest*, and staff must confirm) · filing in the real portal tab with staff-handled OTP/CAPTCHA · reference capture with the **verified numeric ≤14-digit** rule · Briefcase presentation · staff-assisted status/reminder/feedback tasks with the exact inputs the portal requires · audit events · same-case duplicate/conflict protection (cross-case duplicate-reference protection is **not implemented**).
**Not buildable honestly yet** (needs one authorised, supervised real session with a Needle-owned test mobile number): reading the status/department/officer/comments/disposal from the details page, status history, normalised statuses, snapshot/event generation from real data, the automatic poller, and any claim that Needle verified a Delhi status.

---

# Department/category catalogue (public capture, 2026-11-02)

* **Source:** the portal's public department/category selection controls, captured without registering, requesting an OTP or solving a CAPTCHA. File: `modules/data/delhi_catalogue.json` (schema v2), built by `scripts/import_delhi_catalogue.py`.
* **Coverage:** 90 departments, 1,814 category rows. 89 departments are complete. **Delhi Police is partial**: 369 rows, of which 19 long cells were repaired from screenshots and are marked `screenshot_repaired_not_text_verified`. Delhi Jal Board (15 categories) and Delhi Commission for Women were re-captured.
* **Not captured:** location lists (`locations.status = not_captured` everywhere). No location ids or location values are invented.
* **Ids:** `portal_option_value_observed` is the option value seen in the control, not a verified id; no ids are invented.
* **Text policy:** `text` equals `text_raw`; nothing is HTML-entity decoded. The data contains `&amp;`, `&#40;` and `&#41;`. Backend validation, AI suggestion membership checks, the frontend lists and saved worksheets all match the exact string, so decoding would break exact matching and saved worksheets. If a display form is ever needed, add a separate display field and leave `text` / `text_raw` unchanged.
* **Form comparison:** the catalogue has not been compared with the live filing form (`form_comparison: pending`). Staff must still check what they choose against the portal's own form.

---

# Implementation status (2026-10-31, catalogue rows updated 2026-11-02) — NOT a complete integration

Labels: **IMPLEMENTED AND TESTED** · **IMPLEMENTED, NOT FULLY TESTED** · **MANUAL / STAFF-ASSISTED** · **NOT IMPLEMENTED** · **UNKNOWN / NOT VERIFIED**. "Tested" means Needle's own behaviour (AI mocked, no portal traffic); no test uses a government response.

| Capability | Label | Notes |
|---|---|---|
| Delhi tenant → Delhi portal, **no CPGRAMS fallback** | IMPLEMENTED AND TESTED | `_resolve_govt_portal_for_tenant`; generic translate/session endpoints refuse Delhi (HTTP 400); behind `GOVT_DELHI_MANUAL_REFERENCE_ENABLED` (default off ⇒ legacy behaviour byte-for-byte) |
| AI worksheet (subject + description) | IMPLEMENTED, NOT FULLY TESTED | Endpoint + translator tested with Gemini mocked. **Live Gemini not exercised: the local key returned 402 "prepayment credits are depleted".** Department/category: UNKNOWN, so never drafted |
| Department/category catalogue (staff selection + AI suggestions) | IMPLEMENTED AND TESTED (mocked) | 90 departments, 1,814 category rows from the public selection controls; ids are never invented. **Delhi Police is PARTIAL**: 369 rows, 19 of them `screenshot_repaired_not_text_verified`. Unknown category text is a warning, not a block; AI values need explicit staff confirmation. Comparison with the live filing form is **pending** |
| Location lists | NOT CAPTURED | `locations.status = not_captured` for every department; staff type the location and it is recorded as `staff_typed_unverified` |
| Complaint-form field mapping beyond the catalogue, full field limits | UNKNOWN / NOT VERIFIED | behind the registration OTP |
| Registration/filing on the portal | MANUAL / STAFF-ASSISTED | official page opened with the verified step list; staff do CAPTCHA + OTP |
| OTP/CAPTCHA handoff | MANUAL / STAFF-ASSISTED | by design a human does both; Needle never touches them |
| Official reference capture + same-case duplicate/conflict protection | IMPLEMENTED AND TESTED (SQLite); Postgres concurrency test NOT RUN | numeric ≤14 digits (portal's own rule), idempotent repeat on the same case, 409 on a different reference, atomic guarded update. The Postgres concurrency test exists but is skipped unless `NEEDLE_PG_TEST_URL` is set. **Cross-case duplicate references are not prevented** (no unique constraint or claims table) |
| Persisted status + audit events (filing) | IMPLEMENTED AND TESTED | `govt_submission_log`: `ai_translated` (portal and draft sizes only, no draft text or worksheet), `delhi_filing_worksheet_saved` (selections and provenance codes; the location text is not logged), `delhi_ai_suggested`, `staff_submitted` (staff-reported, never portal-verified), `staff_assisted_task`; Briefcase timeline labels |
| Status retrieval (status, department, officer, comments, replies, disposal) | **NOT IMPLEMENTED** (UNKNOWN layout) | post-OTP page never observed |
| Status history / partial snapshots / change events | **NOT IMPLEMENTED** | needs real pages |
| OTP/session scope, session expiry, needs-verification state | UNKNOWN / NOT VERIFIED | |
| Automatic polling | **NOT IMPLEMENTED** — structurally excluded | `delhi_staff_assisted` adapter has `supports_unattended_status_check = False`; not supportable on evidence |
| Status check | MANUAL / STAFF-ASSISTED | audited task opening `/ComplaintTracker` with the exact inputs |
| Reminders | MANUAL / STAFF-ASSISTED | audited task opening `/SendReminder` |
| Feedback | MANUAL / STAFF-ASSISTED | audited task opening `/onlineFeedbackEntry` (disposed complaints only) |
| Briefcase: Escalate, filing panel, reference, tasks, honest status wording, timeline | IMPLEMENTED AND TESTED | jsdom tests + a real-browser rehearsal on a throwaway DB |
| Briefcase: government status panel with real data, last-checked, history, comments, disposal | NOT IMPLEMENTED | nothing real to show |
| Production readiness | NOT READY | see report |

## Demo (local, throwaway database, no government contact)
1. Backend env: `GOVT_DELHI_MANUAL_REFERENCE_ENABLED=true`, a working `GEMINI_API_KEY` (top up credits first), `DATABASE_URL` → a throwaway Postgres DB. Start the backend; startup seeds the (inactive) Delhi portal row.
2. Create a tenant with `tenant_profiles.state = 'Delhi'` and a user + a synthetic case; open Briefcase → the case → *Government submission*.
3. **Draft worksheet with AI** → copy subject/description → **Open official Delhi portal** (new tab; a person completes disclaimer → mobile → CAPTCHA → OTP → form; department/category selected in Needle's worksheet and re-checked by staff against the portal's own form) → **Record the complaint number** (digits only) → the case becomes *Submitted*.
4. Show **Check status on the portal / Send a reminder / Give feedback**: each opens the official page and lists the inputs the portal asks for; the Briefcase timeline records who opened what.
5. Show Karnataka/Maharashtra tenants: unchanged locked-Escalate flow.
**Do not** present any Delhi status as read by Needle: it cannot be.

## What would finish the integration (needs authorisation Needle does not have)
One supervised session with a Needle-owned test mobile number, run by an authorised person on the official portal, capturing the post-OTP complaint form, the registration acknowledgement, and a real status/details page (HTML only, PII scrubbed), plus whether one OTP covers several lookups. Only then can a Delhi status parser, snapshots, history, `needs_verification`, and (if reuse is real) polling be built and honestly tested.
