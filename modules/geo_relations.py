"""Spatial relation parsing for Indian complaint language.

Citizens overwhelmingly describe locations relative to landmarks: "bus stand
ke peeche", "mandir ke saamne", "school javal", "behind the water tank".
These relation words are currently noise welded onto the extracted span —
the source of fragments like "ke paas wale compound".

This parser splits a location phrase into ``(relation, anchor)`` so the
resolver matches the *anchor* (a real place entity) and the relation is
preserved as a qualifier on the case ("behind Central Bus Stand" tells the
crew which side to go to). The vocabulary is closed and small per language —
deterministic, no AI.

Canonical relations: near | behind | opposite | beside | front | inside.
"""
from __future__ import annotations

import re

# Postposition patterns: "<anchor> <marker>" — Hindi/Marathi/Kannada-style.
# Ordered longest-first so "ke thik saamne" wins over "saamne".
_POSTPOSITION_MARKERS: list[tuple[str, str]] = [
    # Hindi / Hinglish
    (r"ke\s+(?:thik\s+)?saa?mne(?:\s+(?:wal[aei]|me[in]n?|par))?", "front"),
    (r"ke\s+pee?chh?e(?:\s+(?:wal[aei]|me[in]n?))?", "behind"),
    (r"ke\s+paa?s(?:\s+(?:wal[aei]|me[in]n?))?", "near"),
    (r"ke\s+bagal(?:\s+(?:wal[aei]|me[in]n?))?", "beside"),
    (r"ke\s+baju(?:\s+(?:wal[aei]|me[in]n?))?", "beside"),
    (r"ke\s+andar", "inside"),
    (r"ke\s+nazdee?k", "near"),
    (r"ke\s+qaree?b", "near"),
    # Marathi (romanized)
    (r"chya\s+maa?ge", "behind"),
    (r"chya\s+samor", "front"),
    (r"chya\s+javal", "near"),
    (r"chya\s+shejari", "beside"),
    (r"javal", "near"),
    (r"samor", "front"),
    # Kannada (romanized)
    (r"hattira", "near"),
    (r"hinde", "behind"),
    (r"edurige", "opposite"),
    (r"eduru", "opposite"),
    (r"pakkadalli", "beside"),
    (r"pakka", "beside"),
    (r"olage", "inside"),
]

# Preposition patterns: "<marker> <anchor>" — English-style.
_PREPOSITION_MARKERS: list[tuple[str, str]] = [
    (r"in\s+front\s+of", "front"),
    (r"opposite(?:\s+to|\s+of)?", "opposite"),
    (r"behind", "behind"),
    (r"beside", "beside"),
    (r"next\s+to", "beside"),
    (r"near(?:by)?", "near"),
    (r"close\s+to", "near"),
    (r"inside", "inside"),
]

_POST_RES = [
    (re.compile(rf"^(?P<anchor>.+?)\s+(?:{pat})\s*(?P<rest>.*)$", re.IGNORECASE), rel)
    for pat, rel in _POSTPOSITION_MARKERS
]
_PRE_RES = [
    (re.compile(rf"^(?:{pat})\s+(?P<anchor>.+)$", re.IGNORECASE), rel)
    for pat, rel in _PREPOSITION_MARKERS
]

# Trailing filler that survives after a postposition marker is removed
# ("... ke paas wale compound mein" → rest "compound mein"). The rest is NOT
# part of the anchor; it's the citizen's descriptive tail and gets dropped
# from matching (it can never be an entity anyway).
_LEADING_ARTICLES = re.compile(r"^(?:the|a|an|old|new|main)\s+", re.IGNORECASE)


def parse_location_phrase(text: str) -> dict:
    """Split a location phrase into relation + anchor.

    Returns {"relation": str|None, "anchor": str, "raw": str}. When no
    relation marker is present the whole phrase is the anchor.
    """
    raw = str(text or "").strip()
    cleaned = re.sub(r"\s+", " ", raw)
    if not cleaned:
        return {"relation": None, "anchor": "", "raw": raw}

    for regex, relation in _PRE_RES:
        m = regex.match(cleaned)
        if m:
            anchor = _LEADING_ARTICLES.sub("", m.group("anchor").strip())
            return {"relation": relation, "anchor": anchor, "raw": raw}

    for regex, relation in _POST_RES:
        m = regex.match(cleaned)
        if m:
            anchor = _LEADING_ARTICLES.sub("", m.group("anchor").strip())
            return {"relation": relation, "anchor": anchor, "raw": raw}

    return {"relation": None, "anchor": cleaned, "raw": raw}
