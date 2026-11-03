"""
modules/govt_sync/delhi_portal.py — facts about Delhi CM Jan Sunwai that were
VERIFIED from the official public pages (2026-10-31), and nothing else.
Evidence and the list of what is still UNKNOWN: DELHI_CM_JAN_SUNWAI_CAPABILITY_MAP.md.

Scope discipline (read before extending):
  * Everything here comes from the portal's own markup and page scripts. Nothing
    was inferred from another state's portal and nothing behind an OTP was
    observed, so department/category options, the post-OTP complaint form, the
    status/details page layout, history and disposal fields are NOT modelled.
  * Every citizen operation on the portal (registration, status, reminder,
    feedback) needs a human to solve an image CAPTCHA and receive an SMS/e-mail
    OTP. These are therefore exposed as STAFF-ASSISTED tasks: Needle prepares,
    opens the right official page and says exactly what the portal will ask for;
    a person does the CAPTCHA/OTP. Needle never claims it read a Delhi status.
  * No HTTP request to the portal is made from this module (or by the Delhi
    code paths built on it).
"""
import re

PORTAL_NAME = "Delhi CM Jan Sunwai"
STATE = "Delhi"
BASE_URL = "https://cmjansunwai.delhi.gov.in/"
EVIDENCE_DATE = "2026-10-31"

# The tracker accepts only a numeric complaint code, masked/maxlength 14
# (isNumeric() + maxlength=14 in the portal's own page). Exact length is NOT shown
# anywhere on the public pages, so any 1..14 digit value is accepted.
REFERENCE_RE = re.compile(r"^[0-9]{1,14}$")
REFERENCE_RULE_TEXT = "The Delhi complaint number is numeric, up to 14 digits (the portal's own tracker rejects anything else)."

# Soft drafting targets for the AI worksheet. The portal's real subject/description
# limits are UNKNOWN (the complaint form sits behind the OTP step); these are NOT
# portal limits and the worksheet says so.
SOFT_SUBJECT_CHARS = 150
SOFT_DESCRIPTION_CHARS = 1500

_COMMON_HUMAN_STEPS = {
    "captcha": "image CAPTCHA (6 characters) shown on the portal page",
    "otp": "one-time password (OTP, 6 digits) sent by SMS to the registered mobile (or by e-mail where the page allows e-mail)",
}

TASK_KEYS = ("file", "status", "reminder", "feedback")


def normalize_reference(raw) -> str | None:
    """Digits-only complaint number, or None if it does not satisfy the portal's own rule."""
    ref = str(raw or "").strip()
    return ref if REFERENCE_RE.match(ref) else None


def staff_assisted_tasks(base_url: str = BASE_URL) -> list[dict]:
    """The four citizen operations, each with the OFFICIAL page and the exact inputs
    the portal asks for (verified from the pages). `automation` is always "none":
    a human solves the CAPTCHA and OTP every time."""
    base = base_url.rstrip("/")
    return [
        {
            "key": "file",
            "label": "File the complaint",
            "url": base + "/",
            "available": "before a complaint number is recorded",
            "automation": "none",
            "steps": [
                "On the portal home page choose Complaint Registration.",
                "Read the disclaimer (RTI matters, sub-judice matters and government-employee service matters cannot be filed) and tick the agreement.",
                "Enter the mobile number and the CAPTCHA shown, request the OTP, then enter the OTP that arrives on that mobile (it expires in about 2 minutes).",
                "Complete the complaint form using the Needle worksheet. Select the department, category and location on the portal exactly as saved in the Needle filing worksheet; the portal shows its own lists once you are logged in, and Needle never chooses them for you.",
                "Note the complaint number the portal shows, then record it in Needle.",
            ],
            "inputs": ["mobile number (10 digits)", _COMMON_HUMAN_STEPS["captcha"], _COMMON_HUMAN_STEPS["otp"]],
        },
        {
            "key": "status",
            "label": "Check status on the portal",
            "url": base + "/ComplaintTracker",
            "available": "after the complaint number is recorded",
            "automation": "none",
            "steps": [
                "Open the official Complaint Status page.",
                "Enter the complaint number, the registered mobile number (or e-mail ID) and the CAPTCHA, then Send OTP.",
                "Enter the OTP and Submit to see the details.",
                "Needle cannot read this page: report what you see to the MP office through the usual channel.",
            ],
            "inputs": ["complaint number (numeric, up to 14 digits)", "registered mobile number (10 digits) or e-mail ID",
                       _COMMON_HUMAN_STEPS["captcha"], _COMMON_HUMAN_STEPS["otp"]],
        },
        {
            "key": "reminder",
            "label": "Send a reminder",
            "url": base + "/SendReminder",
            "available": "after the complaint number is recorded, if the complaint is not resolved within the stipulated time",
            "automation": "none",
            "steps": [
                "Open the official Send Reminder page.",
                "Enter the complaint number and press Search, then give the registered mobile number (or e-mail ID) and the CAPTCHA.",
                "Generate the OTP, enter it and verify to send the reminder.",
            ],
            "inputs": ["complaint number (numeric, up to 14 digits)", "registered mobile number or e-mail ID",
                       _COMMON_HUMAN_STEPS["captcha"], _COMMON_HUMAN_STEPS["otp"]],
        },
        {
            "key": "feedback",
            "label": "Give feedback on a disposed complaint",
            "url": base + "/onlineFeedbackEntry",
            "available": "only after the portal shows the complaint as disposed",
            "automation": "none",
            "steps": [
                "Open the official feedback page (it applies to disposed complaints only).",
                "Enter the registered complaint number and registered mobile number.",
                "Give the star rating (1 or 2 stars send the reference back to a higher authority), written feedback and the two yes/no answers.",
                "Enter the CAPTCHA and the OTP (valid about 3 minutes) and submit.",
            ],
            "inputs": ["complaint number (numeric, up to 14 digits)", "registered mobile number (10 digits)", "star rating, feedback text, two yes/no answers",
                       _COMMON_HUMAN_STEPS["captcha"], _COMMON_HUMAN_STEPS["otp"]],
        },
    ]


def task_by_key(key: str, base_url: str = BASE_URL) -> dict | None:
    return next((t for t in staff_assisted_tasks(base_url) if t["key"] == key), None)
