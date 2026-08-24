"""
modules/govt_sync/adapters — one adapter per portal type, common interface.

get_adapter() is the only thing callers (api_router.py, poller.py) need —
it hides which adapter class backs a given govt_portals row so adding a new
state is "write one adapter + point portal_type/status_check_adapter at
it," not "touch the pipeline."

═══════════════════════════════════════════════════════════════════════
REFERENCE ARCHITECTURE / INVESTIGATION MAP (as of 2026-08-22)
═══════════════════════════════════════════════════════════════════════

Every portal decomposes into two operations. The classification below
applies ONLY to the second one — Filing is unaffected by any of it, for
every portal including Rajasthan:

    GovtPortalAdapter
    │
    ├── Filing (prepare_submission)
    │       staff-driven / existing live-browser workflow.
    │
    └── Status Check (check_status)
            │
            ├── Execution
            │     ├─ Manual
            │     └─ Automated HTTP
            │
            ├── Authentication
            │     ├─ None
            │     ├─ Mobile OTP
            │     ├─ Grievance OTP
            │     ├─ Account
            │     ├─ Static credential
            │     └─ Other / Unknown
            │
            └── Human verification
                  ├─ None
                  ├─ CAPTCHA
                  └─ Other / Unknown

INDEPENDENCE RULES — load-bearing, not stylistic:

  * Authentication and Human verification are INDEPENDENT axes. CAPTCHA is
    NEVER a child of Authentication. A portal can legitimately be, all at
    once: Execution=Automated HTTP, Authentication=Mobile OTP, Human
    verification=CAPTCHA. This is exactly what UP Jansunwai's real tracker
    (jansunwai.up.nic.in/ComplaintTracker) appears to need — one form
    asking for reference number + mobile + OTP AND a separate CAPTCHA
    field. A taxonomy that can't represent "both at once" can't represent
    UP, so don't collapse these two axes back into one.

  * Execution is independent of the portal's inherent authentication
    model. It describes NEEDLE'S CURRENT INTEGRATION CAPABILITY — has
    this specific portal actually been reverse-engineered and wired up —
    not what the government portal technically supports. Two portals can
    both be Mobile OTP + no CAPTCHA while one is Automated HTTP
    (Rajasthan, because the work was done) and the other stays Manual
    (because nobody has done it yet). Never read "Manual" as a statement
    about the portal; it's a statement about our own build status.

  * "Unknown" is a valid, first-class classification, not a placeholder to
    fill in with a guess. NEVER infer an authentication model from the
    mere existence of a login button on a portal's page, and never infer
    it from another state's behavior just because both ask for "mobile +
    OTP." Record Unknown explicitly and leave it there until a real,
    authorized investigation (see the procedure below) establishes
    otherwise.

CURRENT CLASSIFICATION (confirmed findings only — everything else is
Unknown, not guessed):

  Rajasthan Sampark — Execution: Automated HTTP · Authentication: Mobile
  OTP · Human verification: None · status_check_adapter:
  "rajasthan_sampark_api" (implemented). The proven reference
  implementation (OtpGatedStatusMixin below) — every future adapter is
  validated against this, not copied from it.

  CPGRAMS — Execution: Automated HTTP / existing manual-scrape path
  (status_check_mode="public_reference") · Authentication: None, based
  only on the observed search-form flow · Human verification: Unknown —
  never confirmed against a real status RESULT page for a real reference
  number, only the search form was fetched. Do not claim CPGRAMS's
  automation is fully proven end-to-end from that alone.

  UP Jansunwai — Execution: Manual (no adapter exists) · Authentication:
  OTP is present but its SCOPE IS UNKNOWN (mobile-scoped like Rajasthan,
  or grievance-scoped — not established; must come from an authorized
  live test, not an assumption) · Human verification: CAPTCHA (confirmed
  present on the real tracker form; whether it's enforced server-side is
  not yet confirmed) · status_check_adapter: none.

  The other 9 login_required states (Bihar, Karnataka, Madhya Pradesh,
  Maharashtra, Mizoram, Odisha, Punjab, Tamil Nadu, Tripura) plus
  Uttarakhand — Execution: Manual (no status adapter exists for any of
  them) · Authentication: Unknown — do NOT classify these as "Account"
  merely because status_check_mode="login_required"; that column only
  means staff must be logged in somewhere, it says nothing about what the
  portal's real backend actually enforces · Human verification: Unknown.

status_check_adapter CONFIGURED on a govt_portals row means that portal
has a real automated status-check implementation (Execution=Automated
HTTP). ABSENT means the default ManualAssistedAdapter fallback applies.

KNOWN NAMING DRIFT (not a bug, not urgent): ManualAssistedAdapter
currently covers more than one cell of this taxonomy — true Manual
(login_required portals, checked=False always) AND Automated HTTP + None
auth + None human-verification (CPGRAMS's plain scrape attempt, since
status_check_mode="public_reference" still triggers a real GET). Do not
refactor this apart just to make the class name match the taxonomy —
only worth doing once a second portal needs that Automated-HTTP-no-auth
cell distinguished from true Manual in code.

DO NOT PRE-BUILD (until a real portal actually requires it): a CAPTCHA-
handling mixin, a Grievance-OTP mixin, an Account-authentication
abstraction, or a Browser-driven-status-execution abstraction. The
discipline that produced OtpGatedStatusMixin is: investigate a real
portal -> implement that real case directly in its own adapter -> only
once a SECOND real portal repeats the same pattern, extract the shared
piece into a reusable mixin. Don't skip ahead to the abstraction for
hypothetical portals — see PROJECT_MEMORY.md for the fuller version of
this principle.

NEXT-STATE INVESTIGATION PROCEDURE (in order, before writing adapter
code):
  1. Identify the official portal.
  2. Determine the real status-check flow (trace actual network traffic
     on a real check — never assume from the page's visible form alone;
     this is how Rajasthan's real gateway API and UP's CAPTCHA were both
     found).
  3. Determine authentication.
  4. Determine authentication SCOPE (mobile vs grievance vs something
     else — this is what makes OtpGatedStatusMixin's session-caching
     actually valid to use; get this wrong and the mixin misbehaves).
  5. Determine CAPTCHA/human-verification requirements INDEPENDENTLY of
     authentication (don't assume "has OTP" means "no CAPTCHA," or the
     reverse).
  6. Determine whether the flow can actually be driven through plain
     HTTP/API, or needs a browser.
  7. Determine the real status fields and how they map onto base.py's
     STATUS_KEYWORDS.
  8. Check whether an existing capability (OtpGatedStatusMixin, etc.)
     already fits before building something new.
  9. Only then implement an adapter — see the mechanical steps below.
  10. Run a real, authorized end-to-end test (real reference number, real
      OTP/CAPTCHA if applicable) before ever enabling it in the
      background poller.

ADDING A NEW STATE'S REAL STATUS-CHECK ADAPTER, mechanically, once the
above procedure says it's worth building:

1. If it turns out to be gated by an OTP that verifies a mobile number
   rather than one grievance (step 4 above confirmed "Mobile OTP"), write
   a new adapter module implementing just the three OtpGatedStatusMixin
   hooks (base.py) — _send_otp/_validate_otp/_fetch_status — and mix it
   in ahead of ManualAssistedAdapter (mixin first, so its check_status()
   wins):
       class SomeStateAPIAdapter(OtpGatedStatusMixin, ManualAssistedAdapter): ...
   If it's gated some other way (Grievance OTP, Account, CAPTCHA the
   backend actually enforces, ...), the mixin doesn't apply as-is —
   implement check_status() directly on a GovtPortalAdapter subclass
   instead; don't force-fit a different auth shape into this mixin.
2. Register it below in _STATUS_CHECK_ADAPTERS, keyed by whatever string
   you set on that portal's govt_portals.status_check_adapter column (see
   modules/govt_sync/seed.py + modules/data/govt_portals.json).

No changes needed anywhere else — api_router.py's /govt/otp/* endpoints,
poller.py, and get_resolved_govt_portal's otp_verification field all
dispatch generically off get_adapter()/hasattr() already.
"""
from .base import GovtPortalAdapter, OtpGatedStatusMixin, StatusResult, SubmissionResult
from .manual import ManualAssistedAdapter
from .rajasthan_sampark import RajasthanSamparkAPIAdapter

# portal_type -> adapter class. All current portals (state_branded, cpgrams)
# use the manual-assisted adapter — see modules/govt_sync/__init__.py for why
# this isn't Playwright browser automation on this backend. A future portal
# with a genuine API or a remote-browser-controlled submission flow can add
# its own class here without changing callers.
_ADAPTERS = {
    "state_branded": ManualAssistedAdapter,
    "cpgrams": ManualAssistedAdapter,
}

# govt_portals.status_check_adapter (if set) picks the adapter instead of
# portal_type — this only ever changes check_status() behavior (see each
# adapter's prepare_submission(), which stays the manual-filing note for
# every portal regardless of this). Checked first; portal_type is the
# fallback for the (default) manual-assisted case. See this file's module
# docstring for how to add a new state here.
_STATUS_CHECK_ADAPTERS = {
    "rajasthan_sampark_api": RajasthanSamparkAPIAdapter,
}


def get_adapter(portal_row: dict) -> GovtPortalAdapter:
    portal_row = portal_row or {}
    status_check_adapter = portal_row.get("status_check_adapter")
    if status_check_adapter and status_check_adapter in _STATUS_CHECK_ADAPTERS:
        return _STATUS_CHECK_ADAPTERS[status_check_adapter](portal_row)
    portal_type = portal_row.get("portal_type") or "state_branded"
    adapter_cls = _ADAPTERS.get(portal_type, ManualAssistedAdapter)
    return adapter_cls(portal_row)


__all__ = ["GovtPortalAdapter", "OtpGatedStatusMixin", "StatusResult", "SubmissionResult", "get_adapter"]
