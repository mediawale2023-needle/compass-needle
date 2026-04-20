"""
modules/brain_chunker.py — Convert raw DB rows / JSON profiles into
"chunks" suitable for embedding + retrieval.

A chunk is the unit of memory in the Needle Brain. One chunk = one
self-contained slice of context that will be embedded once and later
retrieved by semantic similarity to a copilot/drafter query.

Public API:

    chunk_pq_row(row)               → list[dict]    (questions + answers)
    chunk_debate_row(row)           → list[dict]
    chunk_zero_hour_row(row)        → list[dict]
    chunk_constituency_profile(tid, profile_dict)   → list[dict]
    chunk_case_row(row)             → list[dict]
    chunk_scheme(scheme_obj)        → list[dict]    (global, tenant_id=None)

All chunkers return list-of-dict with this shape:

    {
        "tenant_id":    int | None,
        "source_type":  str,           # see SOURCE_TYPES
        "source_id":    str,           # primary key of the row
        "source_table": str,           # 'parliamentary_questions' etc.
        "title":        str,
        "content":      str,           # ≤ ~8000 chars per chunk
        "metadata":     dict,          # JSON-serialisable
        "ministry":     str | None,
        "date_ref":     str | None,    # 'YYYY-MM-DD'
        "topic_tags":   list[str],
    }

Pure functions — no DB writes, no network calls.
"""

from __future__ import annotations

import re
import logging
from typing import Any, Optional

logger = logging.getLogger("needle.brain_chunker")

# ─────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────

# Hard caps per chunk to stay well below OpenAI 8191-token limit on
# text-embedding-3-small. Roughly 1 token = 4 chars in English.
MAX_CHUNK_CHARS    = 7000
SOFT_CHUNK_CHARS   = 5500     # split bigger paragraphs for debates
MIN_CHUNK_CHARS    = 30       # don't bother embedding micro-snippets

SOURCE_TYPES = {
    "pq_qa",                    # parliamentary question + ministry answer
    "debate_speech",            # one speech / paragraph
    "zero_hour",                # zero-hour submission
    "const_overview",
    "const_political",
    "const_assembly",
    "const_economy",
    "const_social",
    "const_culture",
    "const_challenge",
    "const_priority",
    "const_fact",
    "case_summary",
    "scheme",
    "news",
    "budget_line",
}


# ─────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────

def _fmt_date(d) -> Optional[str]:
    if d is None:
        return None
    if isinstance(d, str):
        return d[:10]
    try:
        return d.strftime("%Y-%m-%d")
    except Exception:
        return str(d)[:10]


def _clean(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _split_paragraphs(text: str, max_chars: int = SOFT_CHUNK_CHARS) -> list[str]:
    """Split a long body of text into ≤ max_chars chunks at paragraph
    boundaries. Final chunks are guaranteed not to exceed MAX_CHUNK_CHARS."""
    text = _clean(text)
    if len(text) <= max_chars:
        return [text]

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    bufsize = 0
    for p in paragraphs:
        plen = len(p)
        if plen > MAX_CHUNK_CHARS:
            # Single huge paragraph — sentence-split
            for s in re.split(r"(?<=[.!?])\s+", p):
                if not s.strip():
                    continue
                if bufsize + len(s) + 1 > max_chars and buf:
                    chunks.append("\n\n".join(buf))
                    buf, bufsize = [], 0
                buf.append(s)
                bufsize += len(s) + 1
            continue

        if bufsize + plen + 2 > max_chars and buf:
            chunks.append("\n\n".join(buf))
            buf, bufsize = [], 0
        buf.append(p)
        bufsize += plen + 2

    if buf:
        chunks.append("\n\n".join(buf))

    # Hard-truncate any remaining oversize chunk
    return [c[:MAX_CHUNK_CHARS] for c in chunks if len(c) >= MIN_CHUNK_CHARS]


# ─────────────────────────────────────────────────────────────────────────
# CHUNKERS — one per source
# ─────────────────────────────────────────────────────────────────────────

def chunk_pq_row(row: dict) -> list[dict]:
    """
    Convert one parliamentary_questions row into chunks.
    Strategy: combine question + answer into a single chunk (they are most
    valuable retrieved together). If the answer is large, split into
    a 'header' chunk (Q + first answer paragraph) and additional answer
    paragraph chunks all linked back to the same source_id.
    """
    q = _clean(row.get("question_text") or "")
    a = _clean(row.get("answer_text") or "")
    subject  = (row.get("subject") or "").strip()
    ministry = (row.get("ministry") or "").strip()
    date_ref = _fmt_date(row.get("date_asked"))

    if not q and not a:
        # Nothing useful to embed
        return []

    qtype = (row.get("question_type") or "").strip().lower()
    real_qn = (row.get("real_question_number") or "").strip()
    qn      = real_qn or str(row.get("question_number") or "").strip()
    house   = (row.get("house") or "lok_sabha")
    session = (row.get("session_name") or "").strip()

    title_bits = []
    if qtype:
        title_bits.append(qtype.title())
    title_bits.append("PQ")
    if qn:
        title_bits.append(f"#{qn}")
    if ministry:
        title_bits.append(f"({ministry})")
    title = " ".join(title_bits) + (f" — {subject}" if subject else "")
    title = title[:240]

    # Build content body
    parts = [f"SUBJECT: {subject}" if subject else "",
             f"MINISTRY: {ministry}" if ministry else "",
             f"DATE: {date_ref}" if date_ref else "",
             f"SESSION: {session}" if session else "",
             "",
             "QUESTION:",
             q or "(question text not available)",
             "",
             "ANSWER:",
             a or "(answer not yet fetched)"]
    body = "\n".join(p for p in parts if p is not None).strip()

    base_meta = {
        "subject":         subject,
        "ministry":        ministry,
        "house":           house,
        "session_name":    session,
        "question_number": qn,
        "real_question_number": real_qn,
        "question_type":   qtype,
        "pdf_url":         row.get("question_pdf_url") or None,
    }

    if len(body) <= MAX_CHUNK_CHARS:
        return [{
            "tenant_id":    row.get("tenant_id"),
            "source_type":  "pq_qa",
            "source_id":    str(row["id"]),
            "source_table": "parliamentary_questions",
            "title":        title,
            "content":      body,
            "metadata":     base_meta,
            "ministry":     ministry or None,
            "date_ref":     date_ref,
            "topic_tags":   _topic_tags_from_subject(subject),
        }]

    # Long answer — split into multiple chunks; first carries Q + first slice.
    answer_chunks = _split_paragraphs(a, max_chars=SOFT_CHUNK_CHARS)
    chunks: list[dict] = []
    for i, ac in enumerate(answer_chunks):
        suffix = "" if i == 0 else f" [part {i+1}/{len(answer_chunks)}]"
        chunk_body = (
            f"SUBJECT: {subject}\nMINISTRY: {ministry}\nDATE: {date_ref}\n"
            f"SESSION: {session}\n\n"
            + (f"QUESTION:\n{q}\n\n" if i == 0 else "")
            + f"ANSWER (part {i+1}/{len(answer_chunks)}):\n{ac}"
        ).strip()
        chunks.append({
            "tenant_id":    row.get("tenant_id"),
            "source_type":  "pq_qa",
            "source_id":    f"{row['id']}#{i}",
            "source_table": "parliamentary_questions",
            "title":        (title + suffix)[:240],
            "content":      chunk_body[:MAX_CHUNK_CHARS],
            "metadata":     {**base_meta, "part": i, "parts_total": len(answer_chunks)},
            "ministry":     ministry or None,
            "date_ref":     date_ref,
            "topic_tags":   _topic_tags_from_subject(subject),
        })
    return chunks


def chunk_debate_row(row: dict) -> list[dict]:
    """
    Convert a parliamentary_debates row to chunks. Today the speech text
    is rarely populated (only `topic`/`bill_reference`/`pdf_url`); we still
    create one summary chunk so at least the metadata is searchable.
    Once Phase 1B (debate-PDF extraction) lands, the speech body will be
    paragraph-chunked.
    """
    speech = _clean(row.get("speech_excerpt") or "")
    topic  = (row.get("topic") or "").strip()
    bill   = (row.get("bill_reference") or "").strip()
    debate_type = (row.get("debate_type") or "").strip()
    date_ref = _fmt_date(row.get("date"))
    session = (row.get("session_name") or "").strip()

    if not speech and not topic:
        return []

    title_parts = []
    if debate_type:
        title_parts.append(debate_type.title())
    title_parts.append("Debate")
    if topic:
        title_parts.append(f"— {topic}")
    title = " ".join(title_parts)[:240]

    base_meta = {
        "topic":          topic,
        "bill_reference": bill,
        "debate_type":    debate_type,
        "session_name":   session,
        "pdf_url":        row.get("pdf_url") or None,
    }

    if not speech:
        body = (
            f"DEBATE TOPIC: {topic}\n"
            f"BILL REFERENCE: {bill}\n"
            f"TYPE: {debate_type}\n"
            f"DATE: {date_ref}\n"
            f"SESSION: {session}\n"
        ).strip()
        return [{
            "tenant_id":    row.get("tenant_id"),
            "source_type":  "debate_speech",
            "source_id":    str(row["id"]),
            "source_table": "parliamentary_debates",
            "title":        title,
            "content":      body,
            "metadata":     base_meta,
            "ministry":     None,
            "date_ref":     date_ref,
            "topic_tags":   _topic_tags_from_subject(topic),
        }]

    # We have actual speech text — paragraph-chunk it.
    chunks: list[dict] = []
    for i, para in enumerate(_split_paragraphs(speech)):
        chunks.append({
            "tenant_id":    row.get("tenant_id"),
            "source_type":  "debate_speech",
            "source_id":    f"{row['id']}#{i}",
            "source_table": "parliamentary_debates",
            "title":        (title + (f" [part {i+1}]" if i else ""))[:240],
            "content":      f"DEBATE: {topic}\nBILL: {bill}\nDATE: {date_ref}\n\n{para}"[:MAX_CHUNK_CHARS],
            "metadata":     {**base_meta, "part": i},
            "ministry":     None,
            "date_ref":     date_ref,
            "topic_tags":   _topic_tags_from_subject(topic),
        })
    return chunks


def chunk_zero_hour_row(row: dict) -> list[dict]:
    """One chunk per zero-hour submission row."""
    subject = (row.get("subject") or "").strip()
    if not subject:
        return []
    date_ref = _fmt_date(row.get("date"))
    session = (row.get("session_name") or "").strip()
    body = f"ZERO HOUR SUBMISSION\nSUBJECT: {subject}\nDATE: {date_ref}\nSESSION: {session}"
    return [{
        "tenant_id":    row.get("tenant_id"),
        "source_type":  "zero_hour",
        "source_id":    str(row["id"]),
        "source_table": "zero_hour_submissions",
        "title":        f"Zero Hour — {subject}"[:240],
        "content":      body[:MAX_CHUNK_CHARS],
        "metadata":     {"subject": subject, "session_name": session},
        "ministry":     None,
        "date_ref":     date_ref,
        "topic_tags":   _topic_tags_from_subject(subject),
    }]


def chunk_constituency_profile(tenant_id: int, profile: dict) -> list[dict]:
    """
    Slice a 13-section constituency profile into multiple semantic chunks
    so retrieval can pull only the relevant slice (e.g. just the
    Mahadayi water dispute, not the whole Belagavi profile).
    """
    if not profile or not isinstance(profile, dict):
        return []

    meta_blk = profile.get("meta") or {}
    constituency_name = meta_blk.get("name") or ""
    state             = meta_blk.get("state") or ""

    chunks: list[dict] = []

    def _add(source_type: str, key_suffix: str, title: str,
             content: str, extra_meta: dict | None = None,
             topic_tags: list[str] | None = None):
        text = _clean(content)
        if len(text) < MIN_CHUNK_CHARS:
            return
        m = {"constituency": constituency_name, "state": state}
        if extra_meta:
            m.update(extra_meta)
        chunks.append({
            "tenant_id":    tenant_id,
            "source_type":  source_type,
            "source_id":    f"profile-{tenant_id}-{key_suffix}",
            "source_table": "constituency_profiles",
            "title":        title[:240],
            "content":      text[:MAX_CHUNK_CHARS],
            "metadata":     m,
            "ministry":     None,
            "date_ref":     meta_blk.get("last_updated"),
            "topic_tags":   topic_tags or [],
        })

    # Overview
    geo = profile.get("geography") or {}
    demo = profile.get("demographics") or {}
    overview = (
        f"CONSTITUENCY: {constituency_name}, {state}\n"
        f"AKA: {', '.join(meta_blk.get('also_known_as', []))}\n"
        f"REGION: {meta_blk.get('region', '')}\n"
        f"COORDINATES: {meta_blk.get('coordinates', '')}\n"
        f"TOTAL ELECTORS (2024): {meta_blk.get('total_electors_2024', '')}\n"
        f"\nGEOGRAPHY:\n{_dump(geo)}\n"
        f"\nDEMOGRAPHICS:\n{_dump(demo)}"
    )
    _add("const_overview", "overview", f"Overview — {constituency_name}", overview)

    # Political history
    pol = profile.get("political_history")
    if pol:
        _add("const_political", "political", f"Political History — {constituency_name}",
             _dump(pol))

    # Assembly segments — one big chunk; small enough
    assy = profile.get("assembly_segments")
    summary23 = profile.get("assembly_summary_2023")
    if assy or summary23:
        _add("const_assembly", "assembly",
             f"Assembly Segments — {constituency_name}",
             "ASSEMBLY SEGMENTS:\n" + _dump(assy or {}) +
             "\n\n2023 ASSEMBLY SUMMARY:\n" + _dump(summary23 or {}))

    # Economy + infrastructure
    eco = profile.get("economy")
    infra = profile.get("infrastructure")
    if eco or infra:
        _add("const_economy", "economy",
             f"Economy & Infrastructure — {constituency_name}",
             "ECONOMY:\n" + _dump(eco or {}) +
             "\n\nINFRASTRUCTURE:\n" + _dump(infra or {}))

    # Social indicators
    soc = profile.get("social_indicators")
    if soc:
        _add("const_social", "social",
             f"Social Indicators — {constituency_name}", _dump(soc))

    # Cultural profile
    cul = profile.get("cultural_profile")
    if cul:
        _add("const_culture", "culture",
             f"Cultural Profile — {constituency_name}", _dump(cul))

    # Key challenges — ONE CHUNK PER CHALLENGE so retrieval can pull only
    # the one relevant to a query (e.g. "Mahadayi water dispute").
    for i, ch in enumerate(profile.get("key_challenges") or []):
        if isinstance(ch, dict):
            t = ch.get("title", "")
            d = ch.get("detail", "")
            content = f"CHALLENGE: {t}\n\n{d}"
        else:
            t = str(ch)[:80]
            content = f"CHALLENGE: {ch}"
        _add("const_challenge", f"challenge-{i}",
             f"Challenge: {t} — {constituency_name}",
             content,
             extra_meta={"challenge_title": t},
             topic_tags=_topic_tags_from_subject(t))

    # Development priorities
    for i, p in enumerate(profile.get("development_priorities") or []):
        if isinstance(p, dict):
            t = p.get("title", "")
            d = p.get("detail", "")
            content = f"PRIORITY: {t}\n\n{d}"
        else:
            t = str(p)[:80]
            content = f"PRIORITY: {p}"
        _add("const_priority", f"priority-{i}",
             f"Priority: {t} — {constituency_name}",
             content,
             extra_meta={"priority_title": t},
             topic_tags=_topic_tags_from_subject(t))

    # Notable facts (often a list)
    facts = profile.get("notable_facts") or []
    if facts:
        _add("const_fact", "facts",
             f"Notable Facts — {constituency_name}",
             "NOTABLE FACTS:\n" + (
                 "\n".join(f"- {x}" for x in facts) if isinstance(facts, list)
                 else _dump(facts)
             ))

    return chunks


def chunk_case_row(row: dict) -> list[dict]:
    """
    One chunk per resolved/active case from the WhatsApp letterbox.
    The brain uses these to surface 'real citizen demand' when drafting
    constituency-grounded letters or PQs.
    """
    msg = _clean(row.get("raw_message") or "")
    cat = (row.get("category") or "General").strip()
    loc = (row.get("location") or "").strip()
    ward = (row.get("ward") or "").strip()
    if not msg:
        return []
    title = f"Citizen grievance: {cat}"
    if loc:
        title += f" ({loc})"
    body = (
        f"CATEGORY: {cat}\n"
        f"LOCATION: {loc}\nWARD: {ward}\n"
        f"STATUS: {row.get('status', '')}\n"
        f"CRITICAL: {row.get('is_critical', False)}\n"
        f"\nGRIEVANCE TEXT:\n{msg}"
    )
    return [{
        "tenant_id":    row.get("tenant_id"),
        "source_type":  "case_summary",
        "source_id":    str(row["id"]),
        "source_table": "cases",
        "title":        title[:240],
        "content":      body[:MAX_CHUNK_CHARS],
        "metadata":     {
            "category":     cat,
            "location":     loc,
            "ward":         ward,
            "status":       row.get("status"),
            "is_critical":  bool(row.get("is_critical")),
            "case_ref":     row.get("case_ref"),
        },
        "ministry":     None,
        "date_ref":     _fmt_date(row.get("created_at")),
        "topic_tags":   [cat.lower()] + _topic_tags_from_subject(msg[:200]),
    }]


def chunk_scheme(scheme: dict) -> list[dict]:
    """
    Convert one scheme entry from schemes_db.json into a global chunk
    (tenant_id = None — every MP can retrieve it).
    """
    name = (scheme.get("name") or "").strip()
    if not name:
        return []
    desc = (scheme.get("description") or "").strip()
    ministry = (scheme.get("ministry") or "").strip()
    cat = (scheme.get("category") or "").strip()
    body = (
        f"SCHEME: {name}\n"
        f"MINISTRY: {ministry}\n"
        f"CATEGORY: {cat}\n"
        f"FOCUS: {scheme.get('focus', '')}\n"
        f"BUDGET: {scheme.get('budget_allocation', '')}\n"
        f"ACTIVE: {scheme.get('active', '')}\n"
        f"\nDESCRIPTION: {desc}"
    )
    return [{
        "tenant_id":    None,                # global
        "source_type":  "scheme",
        "source_id":    scheme.get("id") or name[:60],
        "source_table": "schemes_db",
        "title":        f"Scheme: {name}"[:240],
        "content":      body[:MAX_CHUNK_CHARS],
        "metadata":     {
            "name":     name,
            "ministry": ministry,
            "category": cat,
            "focus":    scheme.get("focus"),
            "budget":   scheme.get("budget_allocation"),
        },
        "ministry":     ministry or None,
        "date_ref":     None,
        "topic_tags":   [cat.lower()] if cat else [],
    }]


# ─────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────

def _dump(o: Any, depth: int = 0) -> str:
    """Dump a nested dict/list as plain readable text (not JSON) for the
    embedder. The embedder cares about prose, not punctuation."""
    if o is None:
        return ""
    if isinstance(o, str):
        return o
    if isinstance(o, (int, float, bool)):
        return str(o)
    pad = "  " * depth
    if isinstance(o, list):
        return "\n".join(f"{pad}- {_dump(x, depth + 1)}" for x in o)
    if isinstance(o, dict):
        out = []
        for k, v in o.items():
            v_str = _dump(v, depth + 1)
            if "\n" in v_str:
                out.append(f"{pad}{k}:\n{v_str}")
            else:
                out.append(f"{pad}{k}: {v_str}")
        return "\n".join(out)
    return str(o)


# Cheap rule-based topic tagger — Phase 4 will replace with LLM auto-tag.
_TOPIC_KEYWORDS = {
    "water":          ["water", "drinking water", "river", "dam", "tank", "borewell",
                       "jal jeevan", "irrigation", "mahadayi", "krishna", "kalasa"],
    "health":         ["health", "hospital", "medical", "ayushman", "doctor", "vaccination"],
    "education":      ["education", "school", "college", "university", "skill", "literacy"],
    "agriculture":    ["agriculture", "farmer", "kisan", "crop", "fasal", "msp", "fertiliser"],
    "infrastructure": ["road", "highway", "railway", "rail", "metro", "airport", "bridge", "infra"],
    "energy":         ["energy", "electricity", "power", "solar", "renewable", "ujjwala", "lpg"],
    "employment":     ["employment", "job", "unemployment", "mgnrega", "skill", "rozgar"],
    "housing":        ["housing", "awas", "pmay", "slum", "shelter"],
    "minorities":     ["minority", "muslim", "scheduled caste", "sc/st", "tribal", "obc", "kannada", "marathi", "hindi", "urdu"],
    "environment":    ["environment", "pollution", "forest", "wildlife", "climate", "carbon"],
    "law_and_order":  ["police", "crime", "law", "border", "naxal", "terror"],
    "industry":       ["industry", "msme", "manufacturing", "make in india", "psu"],
}


def _topic_tags_from_subject(text: str) -> list[str]:
    if not text:
        return []
    t = text.lower()
    tags = []
    for tag, kws in _TOPIC_KEYWORDS.items():
        for kw in kws:
            if kw in t:
                tags.append(tag)
                break
    return tags
