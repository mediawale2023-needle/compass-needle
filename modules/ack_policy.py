"""Fixed communication policy for all citizen-facing acknowledgements.

This module is the single versioned "constitution" for outbound citizen
messages. Templates own sentences, code owns commitments, and the validator
(modules/ack_validator.py) guards the only lane where free text can still be
sent (staff-typed / AI-suggested notify messages from Briefcase).

Policy summary:
- Office voice ("we"), respectful `Ji,` prefix, 🙏 is the only allowed emoji.
- Receipt -> factual status -> standard closing. No exclamation marks.
- Commitments come only from the status-keyed composer templates; free text
  must not promise outcomes, deadlines, or money.
- No politics, opinions, speculation, or emotional amplifiers.
- No case reference numbers in citizen messages (explicit product decision).
"""
import re

POLICY_VERSION = "ack-policy-v1"

# Length caps (characters). Notify messages may quote context so they get a
# larger budget than intake acks.
MAX_ACK_LENGTH = 350
MAX_NOTIFY_LENGTH = 700

# Only emoji permitted in citizen messages.
ALLOWED_EMOJI = {"🙏"}

# ── Violation patterns ───────────────────────────────────────────────────────
# Each entry: (code, compiled regex, human-readable reason). Matching is
# case-insensitive on the raw text. Keep patterns conservative: in enforce
# mode a match blocks a staff message, so prefer precision over recall — the
# architectural fix (templates own sentences) is the primary defense.

_P = lambda p: re.compile(p, re.IGNORECASE)

CASE_REFERENCE_PATTERNS = [
    ("case_reference", _P(r"#\s*\d+"), "case reference numbers are not allowed in citizen messages"),
    ("case_reference", _P(r"\b(?:case|complaint|ticket|ref(?:erence)?)\s*(?:id|no\.?|number)?\s*[:#]\s*\w*\d"), "case reference numbers are not allowed in citizen messages"),
]

PROMISE_PATTERNS = [
    ("outcome_promise", _P(r"\bwill\s+be\s+(?:fixed|resolved|solved|done|completed|repaired|cleared)\b"), "promises a specific outcome"),
    ("outcome_promise", _P(r"\b(?:kaam|kam|problem|samasya)\s+(?:ho|thik|theek)\s+(?:ho\s+)?jayega\b"), "promises a specific outcome"),
    ("outcome_promise", _P(r"\bguarantee[ds]?\b|\b100\s*%\b|\bpakka\b"), "guarantees an outcome"),
    ("deadline_promise", _P(r"\bwithin\s+\d+\s*(?:hour|hours|day|days|week|weeks|ghante|ghanton|din|dino|hafte)\b"), "commits to a deadline"),
    ("deadline_promise", _P(r"\bby\s+(?:today|tonight|tomorrow|next\s+week|kal|aaj\s+shaam)\b"), "commits to a deadline"),
    ("reopen_mechanism", _P(r"\breply\s+'?no'?\s+to\s+reopen\b"), "describes a reopen mechanism that does not exist"),
]

MONETARY_PATTERNS = [
    ("monetary_amount", _P(r"(?:₹|\brs\.?\s*)\d"), "mentions a monetary amount"),
    ("monetary_promise", _P(r"\b(?:muavza|compensation)\s+(?:milega|diya\s+jayega|will\s+be\s+(?:paid|given))\b"), "promises money"),
]

# Conservative political lexicon: party names, election vocabulary. Common
# words that double as place-name fragments or ordinary speech (e.g. "aap",
# "party") are deliberately excluded.
POLITICAL_TERMS = [
    "bjp", "congress", "shiv sena", "shivsena", "ncp", "dmk", "aiadmk",
    "trinamool", "bsp", "rjd", "samajwadi party", "akali dal", "rss",
    "aam aadmi party", "election", "chunav", "matdaan", "matdan",
    "vote for", "opposition party",
]
POLITICAL_PATTERNS = [
    ("political_content", _P(r"\b" + re.escape(term) + r"\b"), f"political term: {term}")
    for term in POLITICAL_TERMS
]

AMPLIFIER_TERMS = [
    "good news", "great news", "shocking", "terrible", "disgusting",
    "horrible", "amazing", "unbelievable", "badhiya khabar", "khushkhabri",
]
AMPLIFIER_PATTERNS = [
    ("emotional_amplifier", _P(r"\b" + re.escape(term) + r"\b"), f"emotional amplifier: {term}")
    for term in AMPLIFIER_TERMS
]

CONTACT_LEAK_PATTERNS = [
    ("external_link", _P(r"https?://"), "contains a URL"),
]

FORMATTING_PATTERNS = [
    ("leftover_placeholder", _P(r"\{[a-z_]+\}"), "contains an unfilled template placeholder"),
    ("exclamation", _P(r"!"), "exclamation marks are not office voice"),
]

ALL_PATTERNS = (
    CASE_REFERENCE_PATTERNS
    + PROMISE_PATTERNS
    + MONETARY_PATTERNS
    + POLITICAL_PATTERNS
    + AMPLIFIER_PATTERNS
    + CONTACT_LEAK_PATTERNS
    + FORMATTING_PATTERNS
)

# Emoji detection: anything in the common emoji planes that is not on the
# allowlist. (🙏 = U+1F64F.) Department acronyms (PWD, BESCOM) are ordinary
# text and deliberately NOT policed.
EMOJI_SCAN = re.compile(
    "[\U0001F000-\U0001FAFF☀-➿⬀-⯿←-⇿⤀-⥿️]"
)
