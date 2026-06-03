"""
PII redaction for outbound AI prompts.

DPDP Act 2023 data-minimisation: we must not disclose more personal data to
third-party processors (OpenAI, etc.) than the task requires. Grievance
classification and query parsing never need a citizen's phone number, so we
strip phone-like digit runs from text *before* it leaves our servers.

Single entry point: ``redact_pii(text)`` — safe on None/empty, never raises.

NOTE: this redacts text only. The Gemini letterbox-OCR path receives raw letter
*images* whose explicit purpose is to extract the citizen's phone; that path is
governed by consent + a processor contract, not by this module.
"""
import re

# Visible, language-neutral placeholder. The AI still parses "call me at
# [redacted]" correctly while the actual number never leaves our servers.
REDACTION_TOKEN = "[redacted]"

# Indian phone numbers in free text. Anchored on a 10-digit mobile core
# starting 6-9, with an optional +91 / 0091 / 91 / trunk-0 prefix, tolerating
# space / hyphen / dot separators between groups. The 6-9 first-digit anchor
# keeps it from eating 6-digit pincodes, years, ward numbers or rupee amounts.
_PHONE_RE = re.compile(
    r"""
    (?<![\w])                                   # left boundary (not mid-token)
    (?:(?:\+|00)?\s?91[\s\-.]?|0)?              # optional +91 / 0091 / 91 / 0
    (?:
        [6-9]\d{9}                              # 10 digits, no separators
      | [6-9]\d{4}[\s\-.]\d{5}                  # 5-5 grouping
      | [6-9]\d{2}[\s\-.]\d{3}[\s\-.]\d{4}      # 3-3-4 grouping
    )
    (?![\w])                                    # right boundary
    """,
    re.VERBOSE,
)

# Safety net: any standalone run of 10+ digits (oddly formatted numbers,
# Aadhaar's 12 digits, etc.). Still PII-correlated → redact.
_LONG_DIGITS_RE = re.compile(r"(?<!\d)\d{10,}(?!\d)")


def redact_pii(text):
    """Return ``text`` with phone numbers (and 10+ digit runs) replaced by a
    placeholder. Safe on None/empty input."""
    if not text:
        return text
    redacted = _PHONE_RE.sub(REDACTION_TOKEN, text)
    redacted = _LONG_DIGITS_RE.sub(REDACTION_TOKEN, redacted)
    return redacted


# Back-compat / explicit alias
redact_phone_numbers = redact_pii
