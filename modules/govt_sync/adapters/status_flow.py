"""
modules/govt_sync/adapters/status_flow.py — descriptive + runtime-state types
for STATUS-CHECK INTERACTION: portals whose status lookup itself requires a
live human to solve a CAPTCHA and/or relay an OTP, at call time, per lookup
(confirmed via live evidence for Karnataka iPGRS and Maharashtra Aaple
Sarkar — see PROJECT_MEMORY.md's reference-architecture entries and this
package's __init__.py investigation map).

THIS IS A DIFFERENT ABSTRACTION FROM OtpGatedStatusMixin (base.py) — DO NOT
MERGE THEM. OtpGatedStatusMixin is for PORTAL ACCESS VERIFICATION: staff
verifies once, out of band, and the resulting session is cached
(govt_otp_sessions) and reused for many later, fully-automated,
zero-interaction check_status() calls — Rajasthan Sampark's confirmed
shape. InteractiveStatusCheckMixin below is for STATUS-CHECK INTERACTION:
the lookup itself is a live, multi-round-trip conversation with a human,
with no evidence (for any portal, yet) that one lookup's verification can
be reused to skip human input on the next. A portal is either
"verify once, then many free automated checks" or "every single lookup
needs a live human," never both on the same adapter, unless future
evidence proves a genuinely third shape — and even then that's a new
mechanism, not a merge of these two.

Nothing in this module is wired into any real adapter yet. It exists so a
future Karnataka/Maharashtra adapter has somewhere to plug in without
redesigning the base interface again — see
modules/govt_sync/adapters/__init__.py's module docstring for the
investigation procedure that must happen BEFORE any adapter uses this.
"""
from dataclasses import dataclass, field
from enum import Enum

from .base import StatusResult


# ─── Static description of a portal's real status-check protocol ──────
# (the "map" — what a future adapter's describe_flow() would return;
# purely descriptive, no execution logic lives here)

class TransportKind(str, Enum):
    AJAX_JSON = "ajax_json"
    HTML_FORM_POST = "html_form_post"


class SessionRequirement(str, Enum):
    NONE = "none"
    # Produced by an earlier stage of THIS SAME flow-execution (e.g.
    # Maharashtra's `cid`, handed back after stage 1's OTP verification —
    # worthless outside that one flow-execution, never cached or reused).
    FRESH_THIS_FLOW = "fresh_this_flow"
    # Produced by a SEPARATE, previously-completed, out-of-band process —
    # this is how Rajasthan's OtpGatedStatusMixin session plugs into this
    # taxonomy conceptually, WITHOUT living inside a StatusCheckFlow at
    # all. Rajasthan's check_status() never touches this module.
    PERSISTED_PRIOR_VERIFICATION = "persisted_prior_verification"


@dataclass
class HumanVerificationRequirement:
    # Deliberately no sub-fields (expiry, channel, retry count) — only
    # Maharashtra's OTP gave any timing detail at all ("~2 minutes"), and
    # inventing structure neither portal's evidence actually describes
    # would be exactly the kind of speculative field this design was
    # told to avoid.
    kind: str  # "captcha" | "otp" | "other"


@dataclass
class StatusCheckStage:
    name: str
    inputs: list[str] = field(default_factory=list)
    produced_values: list[str] = field(default_factory=list)
    human_verification: list[HumanVerificationRequirement] = field(default_factory=list)
    transport: TransportKind = TransportKind.AJAX_JSON
    session_requirement: SessionRequirement = SessionRequirement.NONE


@dataclass
class StatusCheckFlow:
    stages: list[StatusCheckStage]


# ─── Runtime execution state — the "you are here" on that map ─────────
# One instance per in-progress, staff-driven lookup. Persistence (a DB
# table, in-memory, whatever survives between the two-or-more HTTP
# requests a real staff-driven continuation needs) is deliberately NOT
# decided here — that's a Karnataka-implementation-time decision, not
# part of this additive change.

class StatusCheckAttemptState(str, Enum):
    AWAITING_CHALLENGE = "awaiting_challenge"      # about to fetch a CAPTCHA image / trigger an OTP
    AWAITING_HUMAN_INPUT = "awaiting_human_input"  # challenge issued, waiting on staff's answer
    READY_TO_SUBMIT = "ready_to_submit"            # have everything this stage needs, about to POST
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class StatusCheckAttempt:
    attempt_id: str
    case_id: int
    tenant_id: int
    reference_number: str
    current_stage_index: int = 0
    state: StatusCheckAttemptState = StatusCheckAttemptState.AWAITING_CHALLENGE
    collected_values: dict = field(default_factory=dict)
    pending_human_verification: list[HumanVerificationRequirement] | None = None
    result: StatusResult | None = None  # populated only once state == COMPLETE


# ─── The capability itself ─────────────────────────────────────────────

class InteractiveStatusCheckMixin:
    """Mix into a GovtPortalAdapter subclass for portals where the status
    LOOKUP ITSELF requires live human input (CAPTCHA and/or OTP) at call
    time, per lookup — confirmed for Karnataka iPGRS and Maharashtra Aaple
    Sarkar, see modules/govt_sync/adapters/__init__.py's investigation map.
    See this module's docstring for why this is NOT an extension of, and
    must never be combined with, OtpGatedStatusMixin.

    Order matters when mixing in — put this mixin FIRST, same convention
    as OtpGatedStatusMixin, so its check_status() wins in MRO:

        class SomeStateAPIAdapter(InteractiveStatusCheckMixin, ManualAssistedAdapter):
            def describe_flow(self): ...
            def start(self, reference_number, tenant_id, initial_inputs): ...
            def advance(self, attempt, verification_answers, next_inputs=None): ...

    check_status() is provided here concretely, not left abstract: it
    always reports checked=False, honestly, because an interactive lookup
    cannot complete inside one synchronous call — this satisfies
    GovtPortalAdapter's abstract method without ever pretending a lookup
    happened. supports_unattended_status_check is set False so
    poller.py's background loop never even attempts one of these (see
    base.py / poller.py) — a structural exclusion, not exception-based
    control flow.

    describe_flow()/start()/advance() are intentionally left
    NotImplementedError here — no concrete portal uses this mixin yet, so
    there is nothing real to generalize a body from. Implement all three
    on a concrete adapter only once a real portal is actually being
    built; do not pre-guess their bodies for a hypothetical one.
    """

    supports_unattended_status_check = False

    def check_status(self, reference_number: str, tenant_id: int | None = None) -> StatusResult:
        return StatusResult(
            status="",
            checked=False,
            raw_portal_status="This portal needs a live, staff-present interactive check — see status_flow.start().",
        )

    def describe_flow(self) -> StatusCheckFlow:
        raise NotImplementedError

    def start(self, reference_number: str, tenant_id: int, initial_inputs: dict) -> StatusCheckAttempt:
        raise NotImplementedError

    def advance(self, attempt: StatusCheckAttempt, verification_answers: dict,
                next_inputs: dict | None = None) -> StatusCheckAttempt:
        raise NotImplementedError
