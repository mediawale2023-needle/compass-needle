"""
modules/parliament_context.py — Parliamentary record context builder

Queries the tenant's scraped parliamentary data (questions, debates, PMBs,
zero_hour) and formats it into a compact, token-efficient prompt block for
injection into AI drafting and research prompts.

Three modes, each optimised for a different use-case:

  "letter"    — Surfaces prior questions on the same ministry to cite as
                supporting precedent ("This MP has raised this concern before").
                Token budget: ~600 tokens.

  "question"  — Lists questions already asked on the same ministry/topic to
                prevent duplication + suggests follow-up angles based on
                what the government has already been asked.
                Token budget: ~800 tokens.

  "research"  — Full parliamentary track record summary: top ministries
                questioned, debate topics, PMBs, zero-hour subjects.
                Gives copilot the MP's legislative identity.
                Token budget: ~1000 tokens.

Usage:
    from modules.parliament_context import build_parliament_context

    ctx = build_parliament_context(
        tenant_id=5,
        mode="question",
        ministry="Ministry of Jal Shakti",
        subject="drinking water",
    )
    # Returns a formatted string (or "" if no data)
    prompt = f"...{ctx}..."
"""

import logging
from datetime import date
from typing import Optional

from core.db_helpers import _q, _q_one

logger = logging.getLogger("needle.parliament_context")

# Maximum records to pull per data type (keeps DB queries light)
_MAX_QUESTIONS  = 25
_MAX_DEBATES    = 10
_MAX_PMBS       = 10
_MAX_ZERO_HOUR  = 10


# ─────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────

def build_parliament_context(
    tenant_id: int,
    mode: str = "research",
    ministry: Optional[str] = None,
    subject: Optional[str] = None,
) -> str:
    """
    Build a compact parliamentary context string for the given tenant.

    Args:
        tenant_id:  DB tenant id
        mode:       "letter" | "question" | "research"
        ministry:   Filter questions/debates by ministry (optional)
        subject:    Additional keyword for relevance filtering (optional)

    Returns:
        A formatted string for prompt injection, or "" if no data exists.
        Always fails gracefully — never raises.
    """
    try:
        questions  = _fetch_questions(tenant_id, ministry, subject)
        debates    = _fetch_debates(tenant_id)
        pmbs       = _fetch_pmbs(tenant_id)
        zero_hours = _fetch_zero_hour(tenant_id)

        if not any([questions, debates, pmbs, zero_hours]):
            return ""

        if mode == "letter":
            return _build_letter_context(questions, ministry)
        elif mode == "question":
            return _build_question_context(questions, debates, ministry, subject)
        else:
            return _build_research_context(questions, debates, pmbs, zero_hours)

    except Exception as e:
        logger.warning("build_parliament_context(%d, %s) failed: %s", tenant_id, mode, e)
        return ""


# ─────────────────────────────────────────
# DB FETCHERS
# ─────────────────────────────────────────

def _fetch_questions(tenant_id: int, ministry: Optional[str], subject: Optional[str]) -> list:
    """Fetch questions, preferring ministry/subject matches if provided."""
    params = {"tid": tenant_id, "lim": _MAX_QUESTIONS}

    # Build WHERE clause for optional filters
    filters = ["tenant_id = :tid"]
    if ministry:
        filters.append("(LOWER(ministry) LIKE :ministry OR LOWER(subject) LIKE :ministry)")
        params["ministry"] = f"%{ministry.lower().replace('ministry of ', '')}%"
    if subject:
        filters.append("LOWER(subject) LIKE :subject")
        params["subject"] = f"%{subject.lower()[:40]}%"

    where = " AND ".join(filters)
    rows = _q(f"""
        SELECT session_name, question_number, question_type, subject,
               ministry, date_asked
        FROM parliamentary_questions
        WHERE {where}
        ORDER BY date_asked DESC NULLS LAST
        LIMIT :lim
    """, params)

    # If filtered query returned nothing, fall back to all questions
    if not rows and (ministry or subject):
        rows = _q("""
            SELECT session_name, question_number, question_type, subject,
                   ministry, date_asked
            FROM parliamentary_questions
            WHERE tenant_id = :tid
            ORDER BY date_asked DESC NULLS LAST
            LIMIT :lim
        """, {"tid": tenant_id, "lim": _MAX_QUESTIONS})

    return [dict(r) for r in rows] if rows else []


def _fetch_debates(tenant_id: int) -> list:
    rows = _q("""
        SELECT session_name, date, topic, bill_reference
        FROM parliamentary_debates
        WHERE tenant_id = :tid
        ORDER BY date DESC NULLS LAST
        LIMIT :lim
    """, {"tid": tenant_id, "lim": _MAX_DEBATES})
    return [dict(r) for r in rows] if rows else []


def _fetch_pmbs(tenant_id: int) -> list:
    rows = _q("""
        SELECT session_name, bill_number, title, current_status, date_introduced
        FROM private_members_bills
        WHERE tenant_id = :tid
        ORDER BY date_introduced DESC NULLS LAST
        LIMIT :lim
    """, {"tid": tenant_id, "lim": _MAX_PMBS})
    return [dict(r) for r in rows] if rows else []


def _fetch_zero_hour(tenant_id: int) -> list:
    rows = _q("""
        SELECT session_name, date, subject
        FROM zero_hour_submissions
        WHERE tenant_id = :tid
        ORDER BY date DESC NULLS LAST
        LIMIT :lim
    """, {"tid": tenant_id, "lim": _MAX_ZERO_HOUR})
    return [dict(r) for r in rows] if rows else []


# ─────────────────────────────────────────
# CONTEXT FORMATTERS
# ─────────────────────────────────────────

def _fmt_date(d) -> str:
    if not d:
        return ""
    try:
        return d.strftime("%b %Y") if hasattr(d, "strftime") else str(d)[:7]
    except Exception:
        return ""


def _build_letter_context(questions: list, ministry: Optional[str]) -> str:
    """
    For letter drafting: surface prior questions on the same ministry
    as supporting precedent the AI can cite.
    """
    if not questions:
        return ""

    lines = [
        "═" * 55,
        "MP'S PRIOR PARLIAMENTARY RECORD (for reference only)",
        "Use these as supporting context — do NOT fabricate new numbers.",
        "═" * 55,
    ]

    # Group by ministry
    by_ministry: dict[str, list] = {}
    for q in questions:
        m = q.get("ministry") or "General"
        by_ministry.setdefault(m, []).append(q)

    for m, qs in list(by_ministry.items())[:5]:
        lines.append(f"\n{m}:")
        for q in qs[:5]:
            subject = q.get("subject") or "—"
            q_type  = (q.get("question_type") or "").capitalize()
            session = q.get("session_name") or ""
            date    = _fmt_date(q.get("date_asked"))
            lines.append(f"  • Q{q.get('question_number','')} ({q_type}) — {subject} [{session}{', ' + date if date else ''}]")

    lines.append("═" * 55)
    return "\n".join(lines)


def _build_question_context(questions: list, debates: list,
                             ministry: Optional[str], subject: Optional[str]) -> str:
    """
    For PQ drafting: list prior questions on the same ministry to avoid
    duplication + highlight coverage gaps for strategic follow-ups.
    """
    lines = [
        "═" * 55,
        "MP'S PRIOR PARLIAMENTARY QUESTIONS — AVOID DUPLICATION",
        "Angles already covered are listed below.",
        "Suggest FOLLOW-UP questions that deepen or extend these.",
        "═" * 55,
    ]

    if questions:
        lines.append(f"\nPrior questions on {ministry or 'this ministry'} ({len(questions)} found):")
        for q in questions[:15]:
            subject_text = q.get("subject") or "—"
            q_type       = (q.get("question_type") or "").capitalize()
            session      = q.get("session_name") or ""
            lines.append(f"  Q{q.get('question_number','')} [{q_type}] {session}: {subject_text}")

        # Identify ministries already heavily questioned
        ministries_asked = {}
        for q in questions:
            m = q.get("ministry") or "Unknown"
            ministries_asked[m] = ministries_asked.get(m, 0) + 1
        if ministries_asked:
            top = sorted(ministries_asked.items(), key=lambda x: -x[1])[:3]
            lines.append(f"\nMost questioned ministries: {', '.join(f'{m}({c})' for m, c in top)}")
    else:
        lines.append(f"\nNo prior questions on {ministry or 'this ministry'} found.")
        lines.append("This is a fresh angle — the MP can establish their position here.")

    if debates:
        lines.append(f"\nRelated debate participations ({len(debates)}):")
        for d in debates[:5]:
            lines.append(f"  • {d.get('topic') or '—'} [{d.get('session_name') or ''}]")

    lines.append("\nINSTRUCTION: Draft questions that build on or extend the above record.")
    lines.append("If an identical subject was already asked, pivot to a follow-up angle.")
    lines.append("═" * 55)
    return "\n".join(lines)


def _build_research_context(questions: list, debates: list,
                             pmbs: list, zero_hours: list) -> str:
    """
    For copilot: full parliamentary track record summary.
    Gives the AI the MP's legislative identity and areas of expertise.
    """
    lines = [
        "═" * 55,
        "MP'S 18th LOK SABHA PARLIAMENTARY RECORD",
        "═" * 55,
    ]

    # Questions summary
    if questions:
        total_q = len(questions)
        ministries = {}
        for q in questions:
            m = q.get("ministry") or "General"
            ministries[m] = ministries.get(m, 0) + 1
        top_min = sorted(ministries.items(), key=lambda x: -x[1])[:5]

        lines.append(f"\nQUESTIONS ASKED: {total_q}")
        lines.append("Top ministries questioned:")
        for m, cnt in top_min:
            lines.append(f"  • {m}: {cnt} question(s)")

        lines.append("\nRecent questions:")
        for q in questions[:8]:
            subject = q.get("subject") or "—"
            session = q.get("session_name") or ""
            q_type  = (q.get("question_type") or "").capitalize()
            lines.append(f"  [{q_type}] {subject} ({session})")

    # Debates summary
    if debates:
        lines.append(f"\nDEBATE PARTICIPATIONS: {len(debates)}")
        for d in debates[:5]:
            lines.append(f"  • {d.get('topic') or '—'} [{d.get('session_name') or ''}]")

    # PMBs
    if pmbs:
        lines.append(f"\nPRIVATE MEMBERS' BILLS: {len(pmbs)}")
        for b in pmbs:
            status = b.get("current_status") or "introduced"
            lines.append(f"  • {b.get('title') or b.get('bill_number')} ({status})")

    # Zero Hour
    if zero_hours:
        lines.append(f"\nZERO HOUR SUBMISSIONS: {len(zero_hours)}")
        for z in zero_hours[:5]:
            lines.append(f"  • {z.get('subject') or '—'} [{z.get('session_name') or ''}]")

    lines.append("\nUse this record to understand the MP's legislative priorities and areas of focus.")
    lines.append("Do NOT fabricate additional records beyond what is listed above.")
    lines.append("═" * 55)
    return "\n".join(lines)


# ─────────────────────────────────────────
# QUICK STATS (for dashboard / API summary)
# ─────────────────────────────────────────

def get_parliament_stats(tenant_id: int) -> dict:
    """
    Return a simple stats dict for the MP dashboard card / admin overview.
    Safe to call — returns zeros on any error.
    """
    try:
        q_count = (_q_one(
            "SELECT COUNT(*) AS cnt FROM parliamentary_questions WHERE tenant_id = :tid",
            {"tid": tenant_id}
        ) or {}).get("cnt", 0)

        d_count = (_q_one(
            "SELECT COUNT(*) AS cnt FROM parliamentary_debates WHERE tenant_id = :tid",
            {"tid": tenant_id}
        ) or {}).get("cnt", 0)

        pmb_count = (_q_one(
            "SELECT COUNT(*) AS cnt FROM private_members_bills WHERE tenant_id = :tid",
            {"tid": tenant_id}
        ) or {}).get("cnt", 0)

        zh_count = (_q_one(
            "SELECT COUNT(*) AS cnt FROM zero_hour_submissions WHERE tenant_id = :tid",
            {"tid": tenant_id}
        ) or {}).get("cnt", 0)

        return {
            "questions":   int(q_count  or 0),
            "debates":     int(d_count  or 0),
            "pmbs":        int(pmb_count or 0),
            "zero_hour":   int(zh_count  or 0),
            "has_data":    any([q_count, d_count, pmb_count, zh_count]),
        }
    except Exception as e:
        logger.warning("get_parliament_stats(%d) failed: %s", tenant_id, e)
        return {"questions": 0, "debates": 0, "pmbs": 0, "zero_hour": 0, "has_data": False}
