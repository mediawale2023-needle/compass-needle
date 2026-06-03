# DPDP_COMPLIANCE.md — Digital Personal Data Protection Act, 2023 (India)

> **Document type:** Legal compliance audit + remediation roadmap
> **Scope:** Compass Needle platform (backend API, MP dashboard, Admin dashboard, WhatsApp intake, PostgreSQL, AI processors)
> **Prepared as:** Senior legal advisor (app development & IT law) review
> **Posture:** Strict. Where a requirement is ambiguous, this document assumes the **stricter** reading.
> **Last reviewed:** 2026-06-03
> **Status:** ⚠️ **NOT READY FOR PUBLIC LAUNCH IN INDIA.** Multiple mandatory obligations are unmet. See §3 and §10.

---

## 0. Executive summary (read this first)

Compass Needle processes **digital personal data of identifiable Indian citizens** (Data Principals) at scale: phone numbers, verbatim grievance text, scanned letters with names/addresses, photographs, and location. This squarely triggers the **Digital Personal Data Protection Act, 2023 ("DPDP Act")** and the **DPDP Rules, 2025**.

Under the Act, the MP/tenant is almost certainly a **Data Fiduciary**, and the platform operator (us) is at minimum a **Data Processor** acting under contract, and arguably a **joint/independent Data Fiduciary** for cross-tenant analytics. **OpenAI and Google (Gemini) are sub-processors** to whom citizen PII is disclosed today **without a data processing agreement, consent, or notice**.

**Bottom line:**
- ✅ We have **strong perimeter security** (JWT, bcrypt, tenant isolation, parameterized SQL, rate limiting, HMAC webhook validation, security headers).
- ❌ We have **almost none of the DPDP-specific data-protection machinery**: no consent, no notice, no retention limits, no erasure, no Data Principal rights, no grievance/DPO channel, no children's-data handling, no breach-notification process, no encryption of PII at rest, and **no Data Processing Agreements with OpenAI/Google/Meta**.

**Maximum financial exposure** under the Schedule to the Act:
- Failure to take **reasonable security safeguards** (§8(5)): **up to ₹250 crore**.
- Failure to **notify a personal data breach** (§8(6)): **up to ₹200 crore**.
- Breach of **children's-data** obligations (§9): **up to ₹200 crore**.
- Breach of **Significant Data Fiduciary** obligations (§10), if designated: **up to ₹150 crore**.
- Breach of other obligations / Data Principal duties: **up to ₹50 crore**.

These are **per-instance** penalties imposed by the Data Protection Board of India. Our current state exposes us to the two largest heads simultaneously (security + breach notification).

---

## 1. Legal framework & how it maps to us

### 1.1 Statutory roles (DPDP Act §2)

| Role | Definition | Who, in Compass Needle |
|---|---|---|
| **Data Principal** | The individual to whom personal data relates | The **citizen** who messages the MP's WhatsApp / whose letter is scanned. For a child, includes parent/guardian. |
| **Data Fiduciary** | Determines the **purpose and means** of processing | The **MP / tenant** (and arguably **us** for cross-tenant product analytics and AI training-adjacent uses). |
| **Data Processor** | Processes on behalf of a Data Fiduciary | **Us** (the platform) under contract with each MP; **OpenAI** and **Google** as our sub-processors; **Meta** for transport. |
| **Consent Manager** | Registered platform through which consent is given/managed/withdrawn | **Not implemented.** |

> ⚖️ **Action — legal determination required.** Whether we are a Processor, a joint Fiduciary, or an independent Fiduciary changes our direct liability. This must be decided in writing and reflected in the MP onboarding contract. **Do not assume "we are only a processor"** — our cross-tenant analytics, our choice of AI vendors, and our retention defaults all look like "determining the means," which pulls us toward Fiduciary liability.

### 1.2 Applicability (§3)

The Act applies to processing of digital personal data **within India**, and to processing outside India where it relates to offering goods/services to Data Principals in India. We process Indian citizens' data → **fully in scope**. Our Railway hosting region and AI vendor regions are relevant to §16 (cross-border transfer).

### 1.3 The "government/legitimate use" question (§7, §17) — do NOT over-rely on this

Two arguments are commonly raised to avoid consent:
1. **§7(a) "voluntary provision":** the citizen voluntarily sent the grievance for a specified purpose. This can support processing of the **grievance itself** — but **only** for that purpose, only the data necessary, and it does **not** waive notice, security, retention, erasure, breach-notification, or children's-data obligations.
2. **§17(2)(a) State-instrumentality exemption:** narrow, applies to "the State and its instrumentalities" for sovereign/subsidy functions. **A private SaaS vendor is not "the State."** Even if an MP's office argued this, the exemption is partial and contested, and security/children obligations are unaffected.

> ⚖️ **Strict advice:** Build for **full consent + notice compliance**. Treat any exemption as a defensive fallback, never as the design assumption. The cost of being wrong here is the ₹250 cr / ₹200 cr heads.

---

## 2. WHAT WE HAVE TODAY (current state, evidence-based)

This section is the honest inventory. Citations are `file:line`.

### 2.1 Personal data we collect and store (the data map)

| Data category | Field(s) | Table | Location | Sensitivity |
|---|---|---|---|---|
| Citizen phone | `user_phone` | `cases` | `sansadx_backend/db.py:136` | High (identifier) |
| Verbatim grievance | `raw_message` | `cases` | `db.py:137` | High (may contain caste, health, financial, political views) |
| Replies / staff notes | `response_to_citizen`, `notes_for_staff` | `cases` | `db.py:147-148` | Medium |
| Citizen media (photos/docs/audio) | `media_data` (LargeBinary), `extracted_text`, `caption` | `case_media` | `db.py:185` | **Very high** (raw images, IDs) |
| Citizen name | `citizen_name` | `letterbox` | `db.py:313` | High |
| Citizen phone (letters) | `phone_number`, `sender_phone` | `letterbox` | `db.py:313-314` | High |
| Scanned letter image | `image_data` (LargeBinary) | `letterbox` | (model) | **Very high** |
| Full OCR of letter | `ocr_text`, `ocr_raw_text`, `document_text` | `letterbox` | (model) | **Very high** |
| Constituent profile | `phone`, `display_name`, `tags`, `notes` | `contacts` | `db.py:469` | High |
| Emergency reporter phones | `sender_events` (JSON array of `{phone, ts}`) | `incident_clusters` | (model) | High (aggregated) |
| Spam-flagged phone + preview | `phone`, `message_preview` | `spam_flags` | `db.py:497-507` | High |
| Staff PII | `phone`, `display_name` | `users` | `db.py:123` | Medium |
| Audit context (with PII) | `details`, `details_json` | `case_activity_log`, `letterbox_activity_log` | `db.py:162-352` | Medium |

**Ingestion points:** Meta WhatsApp webhook (`main.py:3320-3450`, message body at `:3404`, media at `download_meta_media()` `:2163`); PA letter upload → `letterbox_batches` → Gemini extraction (`main.py:1300-1538`); staff dashboard upload.

### 2.2 Security safeguards we DO have (these are genuinely good — keep them)

| Safeguard | Evidence | DPDP relevance |
|---|---|---|
| **Tenant isolation** on every query (dual `id + tenant_id` WHERE) | `modules/auth.py:22-40`, `api_router.py:907-948` | Prevents cross-Data-Fiduciary leakage |
| **bcrypt-only** passwords, policy enforced, no plaintext fallback | `db.py:46-68` | §8(5) safeguard |
| **JWT** HS256, 8h expiry (admin 4h), revocation blocklist via `iat` | `api_router.py:86-196`, `admin_api.py:61` | Access control |
| **Parameterized SQL** everywhere (`text()` + bound params) | `core/db_helpers.py:10-15` | Injection protection |
| **HMAC-SHA256 webhook validation** with `compare_digest` | `main.py:3341-3346` | Integrity of intake |
| **Rate limiting** (login 5/min, AI 3/min, webhook 20/min) | `core/rate_limiter.py:36-39` | Abuse / scraping resistance |
| **Security headers** incl. HSTS `max-age=31536000` | `core/security_config.py:103` | Transport hardening |
| **Cookie hardening** (Secure in prod, HttpOnly, SameSite=Strict) | `core/security_config.py:85-88` | Session protection |
| **Secrets via env only**, startup validation, no hardcoded keys | `core/security_config.py:15-20`, `scripts/security_startup_check.py` | Key hygiene |
| **Structured security event logging** to Sentry (optional) | `core/security_logger.py:25-91` | Partial monitoring |
| **No third-party web trackers / analytics cookies** | `frontend/instrumentation.js`, `admin/instrumentation.js` | ✅ Privacy-positive; no cookie-consent gap |
| **Change audit trails** (immutable letterbox log; case activity log) | `db.py:162-352` | Accountability (writes only) |

### 2.3 Partial DPDP machinery we have

| Capability | What exists | Gap |
|---|---|---|
| **Deletion** | Soft-delete (`is_deleted/deleted_at/deleted_by`), 7-day restore window | `api_router.py:1154-1190` | **Not erasure** — data is hidden, not removed; staff-only; no citizen trigger; no hard-delete job |
| **Retention** | 30-day TTL on `wa_message_dedup`; 90-day TTL on `token_blocklist` | `main.py:335-347`, `:3547-3556` | These purge **keys only**, not citizen PII. No retention limit on cases/media/letters/contacts → **indefinite storage** |
| **Data export** | CSV export of cases/letterbox; ZIP tenant export | `api_router.py:776`, `:5257`; `admin_api.py` | **Staff/admin only — not a Data Principal access right** |

---

## 3. WHAT WE DON'T HAVE — MANDATORY GAPS (the strict list)

Each item below is a **statutory obligation**, not a nice-to-have. Ordered by penalty exposure.

### 🔴 GAP 1 — No Data Processing Agreements with sub-processors (§8(2)) + uncontrolled PII disclosure
Today we transmit citizen PII to third parties with **no contract, no consent, no notice**:
- **OpenAI GPT-4o-mini** receives **verbatim citizen grievance text** + MP identity in the system prompt (`ai_engine.py:699-706`).
- **Google Gemini** receives **full scanned letter images** and is prompted to extract name, phone, village, full OCR (`modules/letterbox.py:276-282`).
- **Meta** transports all messages and stores media we download.

§8(2): a Data Fiduciary may engage a processor **only under a valid contract**. There is no DPA, no sub-processor list, no instruction-limitation, no deletion-on-termination clause in the codebase or (per this audit) on file.
> **Risk:** Every AI call is currently an **un-consented, un-contracted disclosure** of personal data. Combined with §16 (these vendors may process outside India), this is the single most acute legal exposure.

### 🔴 GAP 2 — No consent and no notice (§4, §5, §6)
- **No consent gate.** The webhook stores everything with zero opt-in (`main.py:3320+`). Searches for "consent/opt/agree/withdraw" return only taxonomy strings, never a control.
- **No itemized notice** (what data, purpose, rights, grievance route, Board complaint right) before/at collection.
- **No multilingual notice** despite us already supporting 13+ languages (`modules/localized_replies.py`) — §5 requires notice availability in English **and** Eighth Schedule languages.
- **No Consent Manager** integration (§6(7)–(9)).

### 🔴 GAP 3 — No "reasonable security safeguards" for data at rest (§8(5)) — PII stored in plaintext
- Phone numbers, grievance text, replies, **raw media (LargeBinary)**, scanned letters, and full OCR are all **plaintext** in PostgreSQL (`db.py:136-185`, letterbox/contacts models). `MEMORY.md` §3 already concedes: *"Encryption of PII fields at rest — Not built … Flagged, deferred."*
- No field-level encryption, no column masking, no tokenization of identifiers.
- DPDP Rules, 2025 enumerate expected safeguards: **encryption/obfuscation/masking**, access control, **logging & monitoring retained for a defined period**, backups, and contractual safeguards on processors. We meet access control and partial logging; we **fail encryption-at-rest and PII access logging**.
> This is the **₹250 crore** head.

### 🔴 GAP 4 — No personal-data-breach detection or notification process (§8(6))
- No breach-notification workflow to the **Data Protection Board** or to **affected Data Principals**. Sentry logs security events but there is **no exfiltration/anomaly detection** (bulk export, abnormal access), no incident runbook, no notification templates, no timelines.
- DPDP Rules require notifying affected principals **without delay** and a detailed report to the Board (broadly within **72 hours**, extendable).
> This is the **₹200 crore** head and is **fully unaddressed**.

### 🔴 GAP 5 — No children's-data handling (§9)
- **No age signal at intake**, no verifiable parental consent, no prohibition on behavioural monitoring/targeted processing of minors. A citizen messaging about a school/scholarship grievance could easily be <18.
- §9 forbids processing likely to cause detriment to a child and requires **verifiable parental consent**.
> This is a **₹200 crore** head. Even a single identified minor's record processed without parental consent is an offence.

### 🔴 GAP 6 — Data Principal rights are entirely absent (§11, §12, §13, §14)
Citizens have **no authenticated identity** in the system, so today they cannot:
- **§11 Right to access** — get a summary of their data and the identities of processors it was shared with. (Export endpoints are staff-only — `api_router.py:776`.)
- **§12 Right to correction & erasure** — no citizen-facing correction or erasure path; soft-delete is staff-only and non-destructive.
- **§13 Right to grievance redressal** — no DPO/grievance channel; support email `support@needle.in` is **not** a designated grievance officer (`frontend/.../settings/page.js:708-728`).
- **§14 Right to nominate** — not implemented.

### 🔴 GAP 7 — No retention limitation / mandatory erasure (§8(7))
- Cases, media, letters, contacts, and PII-bearing audit logs are retained **indefinitely** (no TTL anywhere except dedup/token keys).
- §8(7) requires erasure **on consent withdrawal** and **when the purpose is no longer served** (with a statutory presumption of purpose-completion after a period of Data Principal inactivity once Rules thresholds apply).

### 🟠 GAP 8 — No consent withdrawal channel (§6(4)–(6))
- No WhatsApp `STOP`/unsubscribe handling anywhere in `main.py`/`localized_replies.py`. Withdrawal must be **as easy as giving** consent. We provide neither.

### 🟠 GAP 9 — No published privacy policy / data-processing notice (§5, transparency)
- No `/privacy`, `/terms`, or notice page in either Next.js app (`frontend/app/layout.js`, `admin/app/layout.js`). No DPO contact published, no Board-complaint route disclosed.

### 🟠 GAP 10 — Cross-border transfer not governed (§16)
- OpenAI, Gemini, and Meta likely process **outside India**; Railway region unverified. §16 permits transfer except to government-restricted territories — but we must **know and control** destinations and reflect them in notice + DPAs. Currently uncontrolled.

### 🟠 GAP 11 — No data access logging (read auditing)
- We log **writes** (status/notes changes) but never log **who read which citizen's data and when** (`/cases/{id}`, `/cases/{id}/media/{id}` create no audit entry). Required to demonstrate accountability and to scope a breach. Admin audit log is **not tenant-scoped** (`admin_api.py:187-197`).

### 🟡 GAP 12 — Significant Data Fiduciary readiness (§10)
- If the Board designates us an **SDF** (likely, given volume + sensitivity + impact on electoral/civic processes), we must appoint an **India-resident DPO**, run **DPIAs**, and commission **independent annual audits**. None exist.

### 🟡 GAP 13 — Data minimisation (§6(1), §8(1))
- We store the **full raw image + full OCR + verbatim message** even after structured fields are extracted. Storing more than necessary is itself a compliance defect and enlarges breach blast-radius.

---

## 4. Obligation → Status traceability matrix

| DPDP §  | Obligation | Status | Evidence / Gap ref |
|---|---|---|---|
| §4 | Lawful ground (consent/legitimate use) before processing | ❌ | GAP 2 |
| §5 | Notice (itemized, multilingual) | ❌ | GAP 2, 9 |
| §6 | Valid consent; easy withdrawal; Consent Manager | ❌ | GAP 2, 8 |
| §7 | Legitimate uses (if relied upon) documented | ⚠️ | §1.3 — not documented |
| §8(1) | Accuracy & completeness | ⚠️ | AI-classified, no citizen correction |
| §8(2) | Processor only under valid contract | ❌ | GAP 1 |
| §8(5) | Reasonable security safeguards | ⚠️/❌ | Perimeter ✅ (§2.2); at-rest encryption ❌ (GAP 3) |
| §8(6) | Breach notification (Board + principals) | ❌ | GAP 4 |
| §8(7) | Erasure on withdrawal / purpose end; retention limit | ❌ | GAP 7 |
| §8(9)/(10) | Publish DPO/contact; grievance redressal | ❌ | GAP 6, 9 |
| §9 | Children: verifiable parental consent; no harmful processing | ❌ | GAP 5 |
| §10 | SDF: DPO-in-India, DPIA, independent audit | ❌ | GAP 12 |
| §11 | Right to access info & list of sharees | ❌ | GAP 6 |
| §12 | Right to correction & erasure | ❌ | GAP 6 |
| §13 | Right to grievance redressal | ❌ | GAP 6, 9 |
| §14 | Right to nominate | ❌ | GAP 6 |
| §16 | Cross-border transfer control | ❌ | GAP 10 |
| Rules 2025 | Logging/monitoring retention; safeguards detail | ⚠️ | GAP 3, 11 |

Legend: ✅ met · ⚠️ partial · ❌ not met.

---

## 5. Remediation roadmap (what we must build, in order)

### Phase 0 — STOP THE BLEEDING (immediate, before any further onboarding)
1. **Execute DPAs** with OpenAI, Google Cloud (Gemini), and Meta; enable each vendor's **zero-retention / no-training** processing mode. Until signed, treat AI features as legally blocked for production citizen data. *(GAP 1)*
2. **Minimise PII sent to AI:** redact phone numbers and obvious identifiers from text before the OpenAI call; for Gemini OCR, this is harder (images) — gate behind the DPA + consent. *(GAP 1, 13)*
3. **Draft & publish a privacy notice** + WhatsApp first-contact notice (multilingual, reuse `localized_replies.py`). *(GAP 2, 9)*
4. **Stand up a breach runbook** (detection criteria, 72-hour Board report template, Data Principal notice template, on-call owner). *(GAP 4)*

### Phase 1 — Lawful basis & rights (consent + Data Principal flows)
5. **Consent + notice gate** at WhatsApp first contact: itemized notice, affirmative opt-in recorded in a new `consents` table (`tenant_id, phone, purpose, version, granted_at, withdrawn_at, lang, notice_version`). *(GAP 2)*
6. **`STOP`/withdrawal keyword** handling in the webhook → mark consent withdrawn → trigger erasure workflow → localized confirmation. *(GAP 8)*
7. **Data Principal rights via WhatsApp** (no new login needed; phone-number-scoped, verified by OTP):
   - `MY DATA` → §11 access summary + list of processors (OpenAI/Gemini/Meta).
   - `CORRECT …` → §12 correction request routed to staff queue.
   - `DELETE ME` → §12 erasure request → hard-delete workflow. *(GAP 6)*
8. **Grievance/DPO channel:** designate a DPO, publish name + contact in privacy notice, dashboards, and WhatsApp; add a grievance SLA. *(GAP 6, 9)*

### Phase 2 — Security safeguards (§8(5) / Rules)
9. **Encrypt PII at rest:** field-level encryption (e.g., application-layer AES-GCM with KMS-managed keys, or pgcrypto) for `user_phone`, `raw_message`, `phone_number`, `citizen_name`, `ocr_text`, `media_data`, `contacts.phone/notes`. Add searchable blind-index for phone lookups. *(GAP 3)*
10. **Read-access audit log:** log every read of a citizen record/media (`who, tenant, record, ts`); make admin audit tenant-scoped; retain logs ≥1 year per Rules. *(GAP 11)*
11. **Anomaly/exfiltration detection:** alert on bulk exports, abnormal read volume, off-hours admin access; wire to Sentry/on-call. *(GAP 4, 11)*
12. **Verify hosting + transfer geography;** enforce DB TLS; document §16 transfer map. *(GAP 10)*

### Phase 3 — Retention, children, minimisation
13. **Retention policy + purge job:** define per-category retention (e.g., resolved-case PII purged N years after closure; raw media purged sooner once structured fields extracted); cron hard-delete; convert soft-delete to true erasure after the 7-day restore window. *(GAP 7, 13)*
14. **Children's-data flow:** age self-declaration at intake; if minor, require verifiable parental consent or refuse processing; suppress any profiling. *(GAP 5)*
15. **Right to nominate** (§14) capture. *(GAP 6)*

### Phase 4 — Governance (SDF readiness)
16. **DPIA** for the WhatsApp→AI pipeline; **appoint India-resident DPO**; schedule **independent annual audit**; maintain **RoPA** (record of processing) and sub-processor register. *(GAP 12)*

---

## 6. Acceptance criteria for "DPDP-compliant" (definition of done)

A release is compliant only when **all** of the following are true:
- [ ] Signed DPAs + zero-retention mode for OpenAI, Google, Meta; sub-processor register published.
- [ ] Multilingual notice shown and consent recorded **before** first storage; withdrawal via `STOP` works and triggers erasure.
- [ ] Data Principal can exercise access, correction, erasure, nomination, and grievance — verifiably (OTP) over WhatsApp.
- [ ] DPO designated and contact published in app + WhatsApp + notice; grievance SLA live.
- [ ] All listed PII columns encrypted at rest with KMS-managed keys; phone blind-index works.
- [ ] Read-access logging live and tenant-scoped; logs retained ≥1 year; exfiltration alerts firing in tests.
- [ ] Breach runbook tested via tabletop; Board (72h) + principal notice templates ready.
- [ ] Retention policy enforced by a tested hard-delete job; soft-delete promotes to erasure.
- [ ] Age gate + verifiable parental consent path for minors.
- [ ] DPIA completed; RoPA maintained; independent audit scheduled (if SDF).

Until every box is checked, the platform is **pilot/internal-testing only** and must not onboard new constituencies for live citizen processing.

---

## 7. Appendix — primary evidence index

- Data models / plaintext PII: `sansadx_backend/db.py:113-507, 896-937`
- WhatsApp intake + media download: `main.py:1300-1538, 2130-2300, 3320-3450`
- OpenAI disclosure: `sansadx_backend/ai_engine.py:599-706`
- Gemini disclosure: `modules/letterbox.py:222-303`; `core/gemini_client.py`
- WhatsApp send: `modules/whatsapp.py:14-69`
- Soft-delete / restore: `api_router.py:1154-1190`
- TTLs (keys only): `main.py:335-347, 3547-3556`
- Security controls: `core/security_config.py`, `core/rate_limiter.py`, `core/security_logger.py`, `modules/auth.py:22-55`, `core/db_helpers.py:10-15`, `scripts/security_startup_check.py`
- Self-flagged risks: `MEMORY.md` §3 (right-to-deletion, PII-at-rest encryption) and §4

> **Disclaimer:** This is an engineering-grade compliance audit prepared from the codebase. It is not a substitute for sign-off by qualified Indian data-protection counsel on the final design, the Fiduciary/Processor determination (§1.1), reliance on any §7/§17 ground, and the SDF question (§10).
