"""
jobs/extract_prs_schemes.py — Build prs_schemes from global_parliamentary_questions.

Two modes:
  full      — process all subjects (first-time setup)
  incremental — process only subjects with id > last watermark

Rule-based extraction catches ~80% of Indian govt scheme names for free.
GPT-4o-mini only runs on ambiguous subjects, minimising token cost.

Usage:
  python -m jobs.extract_prs_schemes --full
  python -m jobs.extract_prs_schemes --incremental
  python -m jobs.extract_prs_schemes --stats
"""
from __future__ import annotations

import os
import re
import sys
import json
import time
import logging
from typing import Optional

from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from sansadx_backend.db import engine

logger = logging.getLogger("needle.extract_prs_schemes")

# ── Watermark key stored in a simple settings table ───────────────────────────
_WATERMARK_KEY = "extract_prs_schemes.last_pq_id"

# ── Rule-based patterns for Indian govt scheme names ─────────────────────────
_RULE_PATTERNS = [
    # Pradhan Mantri / PM prefix
    r"(?:Pradhan\s+Mantri|PM)[\s\-]+[A-Z][A-Za-z\s\-]+(?:Yojana|Scheme|Mission|Programme|Abhiyan|Nidhi|Samman|Kisan|Awas|Gram|Sadak|Jeevan|Ujjwala|Mudra|KISAN|PMAY|PMGSY|PMJAY)?",
    # Named schemes ending in Yojana/Mission/Abhiyan/Programme/Scheme
    r"[A-Z][A-Za-z\s]{3,40}(?:Yojana|Abhiyan|Mission|Programme|Scheme|Initiative|Fund|Authority|Board)",
    # Known acronyms
    r"\b(?:MGNREGS?|MGNREGA|PMJAY|PMKVY|PMGSY|PMAY|NREGA|JAM|DBT|NEP|AMRUT|JNNURM|RKVY|NHM|ICDS|MDM|SSA|RMSA|NLEP|NPCDCS)\b",
    # Ayushman / Jal / Swachh / Beti / Skill
    r"(?:Ayushman|Jal\s+Jeevan|Jal\s+Shakti|Swachh\s+Bharat|Beti\s+Bachao|Skill\s+India|Make\s+in\s+India|Digital\s+India|Start[- ]?up\s+India|Stand[- ]?Up\s+India|Atmanirbhar)[A-Za-z\s]*",
    # National + noun + Mission/Programme/Policy
    r"National\s+[A-Z][A-Za-z\s]{2,35}(?:Mission|Programme|Policy|Scheme|Authority|Fund|Initiative|Board)",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _RULE_PATTERNS]

# Common stop-words that indicate a subject is NOT a scheme name
_NON_SCHEME_WORDS = {
    "status", "implementation", "details", "information", "funds", "allocation",
    "utilisation", "utilization", "expenditure", "release", "pending", "progress",
    "report", "update", "review", "committee", "meeting", "statement",
}

GPT_BATCH_SIZE = 150   # subjects per GPT call
MIN_ANSWER_COUNT = 2   # minimum answers to include a scheme


# ── Watermark helpers ─────────────────────────────────────────────────────────

def _get_watermark() -> int:
    try:
        with engine.connect() as conn:
            r = conn.execute(text(
                "SELECT value FROM app_settings WHERE key = :k"
            ), {"k": _WATERMARK_KEY}).mappings().fetchone()
        return int(r["value"]) if r else 0
    except Exception:
        return 0


def _set_watermark(val: int):
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO app_settings (key, value)
                VALUES (:k, :v)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """), {"k": _WATERMARK_KEY, "v": str(val)})
    except Exception as e:
        logger.warning("Could not save watermark: %s", e)


def _ensure_settings_table():
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key   VARCHAR(200) PRIMARY KEY,
                    value TEXT
                )
            """))
    except Exception as e:
        logger.warning("app_settings table create failed: %s", e)


# ── Rule-based extraction ─────────────────────────────────────────────────────

def _extract_by_rules(subject: str) -> list[str]:
    """Extract scheme name candidates from a subject using regex patterns."""
    found = []
    for pat in _COMPILED:
        for m in pat.finditer(subject):
            candidate = m.group(0).strip()
            words = candidate.lower().split()
            if len(candidate) < 5 or all(w in _NON_SCHEME_WORDS for w in words):
                continue
            found.append(candidate)

    # Drop any candidate whose text is fully contained within a longer candidate.
    # Prevents "Capital Subsidy Scheme" surviving alongside
    # "Credit Linked Capital Subsidy Scheme" from the same subject.
    deduped = [
        c for c in found
        if not any(
            c.lower() in other.lower() and c.lower() != other.lower()
            for other in found
        )
    ]
    return deduped


# ── GPT extraction for ambiguous subjects ────────────────────────────────────

def _gpt_extract_batch(subjects: list[str]) -> list[dict]:
    """
    Send a batch of subjects to GPT-4o-mini.
    Returns list of {name, full_name, ministry} dicts.
    """
    try:
        import openai
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    except Exception as e:
        logger.warning("OpenAI not available: %s", e)
        return []

    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(subjects))
    prompt = (
        "These are Indian parliamentary question subjects. "
        "Extract every government scheme name mentioned. "
        "Return JSON array: [{\"name\": \"<short canonical name>\", "
        "\"full_name\": \"<full official name or same as name>\", "
        "\"ministry\": \"<ministry if inferable else null>\"}]. "
        "Skip subjects with no scheme. Return [] if none found.\n\n"
        f"Subjects:\n{numbered}"
    )
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Extract scheme names only. Return valid JSON array."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=800,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        # GPT sometimes wraps in {"schemes": [...]}
        for v in data.values():
            if isinstance(v, list):
                return v
        return []
    except Exception as e:
        logger.warning("GPT batch extraction failed: %s", e)
        return []


# ── Normalisation & dedup ─────────────────────────────────────────────────────

# Ordered longest-first so the right prefix is consumed
_STRIP_PREFIXES = [
    "centrally sponsored ", "government of india ", "govt of india ",
    "pradhan mantri ", "prime minister ", "national ", "central ", "pm-", "pm ",
]
_STRIP_SUFFIXES = [
    " programme", " initiative", " authority", " campaign", " abhiyan",
    " mission", " project", " scheme", " policy", " yojana", " nidhi",
    " board", " fund",
]


def _normalise(name: str) -> str:
    """Canonical form: normalise spaces, strip trailing punctuation."""
    name = re.sub(r"\s+", " ", name).strip()
    name = name.rstrip(".,;:-")
    return name


def _canonical_key(name: str) -> str:
    """Lowercase, no punctuation, no spaces — for exact dedup comparison."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _semantic_key(name: str) -> str:
    """
    Strip common Indian govt scheme prefix/suffix terms for similarity grouping.
    'Pradhan Mantri Awas Yojana', 'PM Awas Yojana', 'PM Awas Scheme' → 'awas'
    'Swachh Bharat Mission', 'Swachh Bharat Abhiyan' → 'swachhbharat'
    """
    s = re.sub(r"[^a-z0-9\s]", " ", name.lower())
    s = re.sub(r"\s+", " ", s).strip()
    for p in _STRIP_PREFIXES:
        if s.startswith(p):
            s = s[len(p):].strip()
            break
    for sfx in _STRIP_SUFFIXES:
        if s.endswith(sfx):
            s = s[:-len(sfx)].strip()
            break
    return re.sub(r"\s+", "", s)


def _expand_name(name: str) -> str:
    """Expand 'PM ' prefix to 'Pradhan Mantri ' before upsert for consistency."""
    return re.sub(r"^PM[\s\-]+", "Pradhan Mantri ", name.strip(), flags=re.IGNORECASE)


# ── DB upsert ────────────────────────────────────────────────────────────────

def _upsert_scheme(name: str, full_name: str, ministry: Optional[str],
                   alias: Optional[str], date_seen: Optional[str],
                   _sem_cache: Optional[dict] = None):
    """
    Insert or update a scheme in prs_schemes.
    _sem_cache: optional {semantic_key → id} dict for batch-mode dedup.
    """
    canonical = _normalise(_expand_name(name))
    if not canonical or len(canonical) < 4:
        return

    sem_key = _semantic_key(canonical)

    try:
        with engine.begin() as conn:
            existing = None

            # 1. Exact canonical match (fast path via DB index)
            existing = conn.execute(text("""
                SELECT id, name, aliases FROM prs_schemes
                WHERE LOWER(REGEXP_REPLACE(name, '[^a-zA-Z0-9]', '', 'g'))
                    = LOWER(REGEXP_REPLACE(:cname, '[^a-zA-Z0-9]', '', 'g'))
            """), {"cname": canonical}).mappings().fetchone()

            # 2. Semantic key match via in-memory cache (avoids full-table scan)
            if not existing and _sem_cache is not None and len(sem_key) >= 5:
                existing_id = _sem_cache.get(sem_key)
                if existing_id:
                    existing = conn.execute(text(
                        "SELECT id, name, aliases FROM prs_schemes WHERE id = :id"
                    ), {"id": existing_id}).mappings().fetchone()

            if existing:
                # Update last_seen, add alias if new
                new_aliases = list(existing["aliases"] or [])
                if alias and alias not in new_aliases and alias != canonical:
                    new_aliases.append(alias)
                conn.execute(text("""
                    UPDATE prs_schemes
                    SET last_seen = GREATEST(last_seen, CAST(:d AS DATE)),
                        aliases   = :aliases,
                        updated_at = NOW()
                    WHERE id = :id
                """), {
                    "d":       date_seen or "2024-01-01",
                    "aliases": new_aliases,
                    "id":      existing["id"],
                })
                if _sem_cache is not None and len(sem_key) >= 5:
                    _sem_cache.setdefault(sem_key, existing["id"])
            else:
                aliases_arr = [alias] if alias and alias != canonical else []
                result = conn.execute(text("""
                    INSERT INTO prs_schemes
                        (name, full_name, ministry, aliases, first_seen, last_seen)
                    VALUES
                        (:name, :full_name, :ministry, :aliases,
                         CAST(:first AS DATE), CAST(:last AS DATE))
                    ON CONFLICT (name) DO UPDATE SET
                        last_seen  = GREATEST(prs_schemes.last_seen, CAST(:last AS DATE)),
                        updated_at = NOW()
                    RETURNING id
                """), {
                    "name":      canonical,
                    "full_name": _normalise(_expand_name(full_name)) if full_name else canonical,
                    "ministry":  ministry,
                    "aliases":   aliases_arr,
                    "first":     date_seen or "2024-01-01",
                    "last":      date_seen or "2024-01-01",
                })
                if _sem_cache is not None and len(sem_key) >= 5:
                    row = result.fetchone()
                    if row:
                        _sem_cache.setdefault(sem_key, row[0])
    except Exception as e:
        logger.debug("Upsert scheme '%s' failed: %s", canonical, e)


# ── Answer count refresh ──────────────────────────────────────────────────────

def refresh_answer_counts():
    """Update prs_schemes.answer_count based on current global_parliamentary_questions."""
    logger.info("Refreshing answer counts for all schemes...")
    try:
        with engine.connect() as conn:
            schemes = conn.execute(text(
                "SELECT id, name, aliases FROM prs_schemes"
            )).mappings().all()

        for s in schemes:
            aliases = list(s["aliases"] or []) + [s["name"]]
            # Build ILIKE conditions for all aliases
            conditions = " OR ".join(
                f"(subject ILIKE :a{i} OR answer_text ILIKE :a{i})"
                for i in range(len(aliases))
            )
            params = {f"a{i}": f"%{a}%" for i, a in enumerate(aliases)}
            sql = f"""
                SELECT COUNT(*) AS cnt
                FROM global_parliamentary_questions
                WHERE answer_text IS NOT NULL AND answer_text != ''
                  AND ({conditions})
            """
            with engine.connect() as conn:
                r = conn.execute(text(sql), params).mappings().fetchone()
                count = int(r["cnt"]) if r else 0

            with engine.begin() as conn:
                conn.execute(text(
                    "UPDATE prs_schemes SET answer_count = :c WHERE id = :id"
                ), {"c": count, "id": s["id"]})

        logger.info("Answer counts refreshed for %d schemes", len(schemes))
    except Exception as e:
        logger.error("refresh_answer_counts failed: %s", e)


# ── Main extraction ───────────────────────────────────────────────────────────

def run_extraction(full: bool = False, _progress: dict = None) -> dict:
    """
    Extract schemes from global_parliamentary_questions subjects.

    full=True  → process all records (first-time setup)
    full=False → process only records with id > last watermark (incremental)
    _progress  → mutable dict updated in-place for live polling (done/total/label)
    """
    def _upd(done, total, label):
        if _progress is not None:
            _progress["done"] = done
            _progress["total"] = total
            _progress["label"] = label

    _ensure_settings_table()

    watermark = 0 if full else _get_watermark()
    logger.info("Starting extraction (full=%s, watermark=%d)", full, watermark)

    _upd(0, 0, "loading subjects…")

    # Fetch subjects from DB
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, subject, ministry, date_asked
            FROM global_parliamentary_questions
            WHERE id > :w
              AND subject IS NOT NULL AND subject != ''
            ORDER BY id
        """), {"w": watermark}).mappings().all()

    if not rows:
        logger.info("No new subjects to process.")
        return {"subjects_processed": 0, "rule_matched": 0, "gpt_subjects": 0,
                "gpt_calls": 0, "schemes_upserted": 0, "new_watermark": watermark}

    total_rows = len(rows)
    logger.info("Processing %d subjects", total_rows)
    max_id = max(r["id"] for r in rows)

    _upd(0, total_rows, "subjects (rule pass)")

    # Build semantic key cache from existing schemes to prevent batch duplicates
    _sem_cache: dict[str, int] = {}
    try:
        with engine.connect() as conn:
            existing_schemes = conn.execute(text(
                "SELECT id, name FROM prs_schemes"
            )).mappings().all()
        for s in existing_schemes:
            key = _semantic_key(s["name"])
            if len(key) >= 5:
                _sem_cache.setdefault(key, s["id"])
    except Exception:
        pass  # cache is optional; fall back to exact-match only

    rule_matched = 0
    gpt_subjects = []
    gpt_meta: dict[str, dict] = {}  # subject → {ministry, date}
    schemes_upserted = 0

    for idx, row in enumerate(rows):
        subject  = row["subject"] or ""
        ministry = row["ministry"] or None
        date_str = row["date_asked"].isoformat() if row["date_asked"] else None

        found = _extract_by_rules(subject)
        if found:
            rule_matched += 1
            for scheme_name in found:
                _upsert_scheme(scheme_name, scheme_name, ministry, None, date_str,
                               _sem_cache=_sem_cache)
                schemes_upserted += 1
        else:
            gpt_subjects.append(subject)
            gpt_meta[subject] = {"ministry": ministry, "date": date_str}

        if idx % 200 == 0:
            _upd(idx, total_rows, "subjects (rule pass)")

    _upd(total_rows, total_rows, "subjects (rule pass)")

    # GPT pass for ambiguous subjects
    gpt_calls = 0
    if gpt_subjects:
        total_batches = (len(gpt_subjects) + GPT_BATCH_SIZE - 1) // GPT_BATCH_SIZE
        _upd(0, total_batches, "GPT batches")
        logger.info("%d subjects going to GPT (%d caught by rules)",
                    len(gpt_subjects), rule_matched)
        for i in range(0, len(gpt_subjects), GPT_BATCH_SIZE):
            batch = gpt_subjects[i: i + GPT_BATCH_SIZE]
            extracted = _gpt_extract_batch(batch)
            for item in extracted:
                name = (item.get("name") or "").strip()
                if not name or len(name) < 4:
                    continue
                ministry = item.get("ministry") or None
                if not ministry:
                    for subj in batch:
                        if name.lower()[:8] in subj.lower():
                            ministry = gpt_meta[subj]["ministry"]
                            break
                date_str = None
                for subj in batch:
                    if name.lower()[:8] in subj.lower():
                        date_str = gpt_meta[subj]["date"]
                        break
                _upsert_scheme(name, item.get("full_name") or name, ministry, None, date_str,
                               _sem_cache=_sem_cache)
                schemes_upserted += 1
            gpt_calls += 1
            _upd(gpt_calls, total_batches, "GPT batches")
            if i + GPT_BATCH_SIZE < len(gpt_subjects):
                time.sleep(0.3)

    # Update watermark
    _set_watermark(max_id)

    # Refresh answer counts after extraction
    _upd(0, 1, "refreshing answer counts")
    refresh_answer_counts()
    _upd(1, 1, "refreshing answer counts")

    summary = {
        "subjects_processed": len(rows),
        "rule_matched":        rule_matched,
        "gpt_subjects":        len(gpt_subjects),
        "gpt_calls":           gpt_calls,
        "schemes_upserted":    schemes_upserted,
        "new_watermark":       max_id,
    }
    logger.info("Extraction done: %s", summary)
    return summary


def get_stats() -> dict:
    """Quick stats on current prs_schemes table."""
    try:
        with engine.connect() as conn:
            r = conn.execute(text("""
                SELECT
                    COUNT(*)                                  AS total_schemes,
                    COUNT(*) FILTER (WHERE answer_count >= 2) AS schemes_with_answers,
                    COUNT(DISTINCT ministry)                  AS ministries,
                    SUM(answer_count)                         AS total_answers
                FROM prs_schemes
            """)).mappings().fetchone()
        return dict(r) if r else {}
    except Exception as e:
        return {"error": str(e)}


# ── Deduplication ─────────────────────────────────────────────────────────────

def deduplicate_schemes(dry_run: bool = False) -> dict:
    """
    Find and merge near-duplicate scheme names in prs_schemes.

    Groups schemes by semantic key (strips common PM/National prefixes and
    Yojana/Mission/Scheme suffixes). Within each duplicate group, the row
    with the highest answer_count wins; losers are added as aliases and deleted.

    dry_run=True returns the duplicate report without making any changes.
    """
    from collections import defaultdict

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, name, full_name, ministry, aliases, answer_count, first_seen, last_seen
            FROM prs_schemes
            ORDER BY COALESCE(answer_count, 0) DESC, first_seen ASC NULLS LAST
        """)).mappings().all()

    total_before = len(rows)

    # Group by semantic key; skip keys that are too short (false-positive risk)
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        key = _semantic_key(row["name"])
        if len(key) >= 5:
            groups[key].append(dict(row))

    duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}

    if dry_run:
        examples = [
            {"key": k, "schemes": [s["name"] for s in v]}
            for k, v in sorted(duplicate_groups.items(),
                               key=lambda x: len(x[1]), reverse=True)[:20]
        ]
        return {
            "duplicate_groups": len(duplicate_groups),
            "rows_to_delete": sum(len(v) - 1 for v in duplicate_groups.values()),
            "total_schemes": total_before,
            "schemes_after_dedup": total_before - sum(len(v) - 1 for v in duplicate_groups.values()),
            "examples": examples,
        }

    merged = 0
    deleted = 0

    with engine.begin() as conn:
        for key, schemes in duplicate_groups.items():
            winner = schemes[0]  # highest answer_count (ORDER BY above)
            losers  = schemes[1:]

            all_aliases  = list(winner.get("aliases") or [])
            total_count  = winner.get("answer_count") or 0

            for loser in losers:
                if loser["name"] not in all_aliases and loser["name"] != winner["name"]:
                    all_aliases.append(loser["name"])
                for a in (loser.get("aliases") or []):
                    if a not in all_aliases and a != winner["name"]:
                        all_aliases.append(a)
                total_count += loser.get("answer_count") or 0
                deleted += 1

            conn.execute(text("""
                UPDATE prs_schemes
                SET aliases = :aliases, answer_count = :count, updated_at = NOW()
                WHERE id = :id
            """), {"aliases": all_aliases, "count": total_count, "id": winner["id"]})

            loser_ids   = [l["id"]   for l in losers]
            loser_names = [l["name"] for l in losers]
            conn.execute(text("DELETE FROM prs_schemes WHERE id = ANY(:ids)"),
                         {"ids": loser_ids})
            conn.execute(text(
                "DELETE FROM scheme_intelligence_cache WHERE scheme_name = ANY(:names)"
            ), {"names": loser_names})

            merged += 1

    # Invalidate runtime ministry overview cache
    try:
        from modules.schemes_api import _runtime_cache
        _runtime_cache.clear()
    except Exception:
        pass

    logger.info("Dedup done: %d groups merged, %d rows deleted", merged, deleted)
    return {
        "groups_merged":     merged,
        "rows_deleted":      deleted,
        "schemes_before":    total_before,
        "schemes_remaining": total_before - deleted,
    }


# ── Acronym deduplication ─────────────────────────────────────────────────────

# Known acronym → canonical full name. Used as first-pass lookup before
# the pattern generator runs. Add entries here when new common acronyms appear.
_ACRONYM_DICT: dict[str, str] = {
    "MGNREGS":  "Mahatma Gandhi National Rural Employment Guarantee Scheme",
    "MGNREGA":  "Mahatma Gandhi National Rural Employment Guarantee Act",
    "NREGA":    "National Rural Employment Guarantee Act",
    "PMJAY":    "Pradhan Mantri Jan Arogya Yojana",
    "PMKVY":    "Pradhan Mantri Kaushal Vikas Yojana",
    "PMGSY":    "Pradhan Mantri Gram Sadak Yojana",
    "PMAY":     "Pradhan Mantri Awas Yojana",
    "PMFBY":    "Pradhan Mantri Fasal Bima Yojana",
    "PMJDY":    "Pradhan Mantri Jan Dhan Yojana",
    "PMKISAN":  "Pradhan Mantri Kisan Samman Nidhi",
    "PMKUSUM":  "Pradhan Mantri Kisan Urja Suraksha evam Utthan Mahabhiyan",
    "PMEGP":    "Pradhan Mantri Employment Generation Programme",
    "PMVVY":    "Pradhan Mantri Vaya Vandana Yojana",
    "PMMSY":    "Pradhan Mantri Matsya Sampada Yojana",
    "PMSBY":    "Pradhan Mantri Suraksha Bima Yojana",
    "PMJJBY":   "Pradhan Mantri Jeevan Jyoti Bima Yojana",
    "AMRUT":    "Atal Mission for Rejuvenation and Urban Transformation",
    "JNNURM":   "Jawaharlal Nehru National Urban Renewal Mission",
    "RKVY":     "Rashtriya Krishi Vikas Yojana",
    "NHM":      "National Health Mission",
    "NRHM":     "National Rural Health Mission",
    "NUHM":     "National Urban Health Mission",
    "ICDS":     "Integrated Child Development Services",
    "MDM":      "Mid Day Meal Scheme",
    "SSA":      "Sarva Shiksha Abhiyan",
    "RMSA":     "Rashtriya Madhyamik Shiksha Abhiyan",
    "RUSA":     "Rashtriya Uchchatar Shiksha Abhiyan",
    "NEP":      "National Education Policy",
    "DBT":      "Direct Benefit Transfer",
    "JAM":      "Jan Dhan Aadhaar Mobile",
    "UDAN":     "Ude Desh ka Aam Naagrik",
    "HRIDAY":   "Heritage City Development and Augmentation Yojana",
    "PRASAD":   "Pilgrimage Rejuvenation and Spiritual Augmentation Drive",
    "SWAYAM":   "Study Webs of Active Learning for Young Aspiring Minds",
    "SMILE":    "Support for Marginalised Individuals for Livelihood and Enterprise",
    "TULIP":    "The Urban Learning Internship Programme",
    "ASPIRE":   "A Scheme for Promotion of Innovation Rural Industries and Entrepreneurship",
    "MUDRA":    "Micro Units Development and Refinance Agency",
    "ATAL":     "Atal Innovation Mission",
    "PLI":      "Production Linked Incentive",
    "FAME":     "Faster Adoption and Manufacturing of Hybrid and Electric Vehicles",
    "POSHAN":   "Prime Ministers Overarching Scheme for Holistic Nourishment",
    "NIPUN":    "National Initiative for Proficiency in Reading with Understanding and Numeracy",
}

_ACRONYM_RE = re.compile(r"^[A-Z][A-Z0-9\-]{1,9}$")

_ACRONYM_STOPWORDS = {
    "of", "for", "the", "and", "in", "under", "to", "a", "an", "on", "at",
    "from", "by", "with", "its", "their",
}


def _generate_acronyms(name: str) -> set[str]:
    """
    Generate candidate acronyms from a multi-word scheme name.
    'Pradhan Mantri Awas Yojana' → {'PMAY'}
    'Mahatma Gandhi National Rural Employment Guarantee Scheme' → {'MGNREGS', 'MGNREG'}
    """
    candidates: set[str] = set()
    words = [w for w in re.sub(r"[^a-zA-Z0-9\s]", " ", name).split() if w]
    if len(words) < 2:
        return candidates

    # All-words first letter
    candidates.add("".join(w[0].upper() for w in words))

    # Without stop words (generates alternate forms)
    filtered = [w for w in words if w.lower() not in _ACRONYM_STOPWORDS]
    if 1 < len(filtered) < len(words):
        candidates.add("".join(w[0].upper() for w in filtered))

    return candidates


def deduplicate_acronyms(dry_run: bool = False) -> dict:
    """
    Match acronym-form scheme rows (PMAY, NHM, MGNREGS …) to their full-name
    counterparts using two strategies:

    1. Hardcoded _ACRONYM_DICT — catches known/irregular pairs
    2. Pattern generation — first letter of each word in every full name;
       if that string matches an acronym row, merge them

    Full-name row is always the winner; acronym becomes an alias.
    Should be run AFTER deduplicate_schemes() on clean data.
    """
    with engine.connect() as conn:
        all_rows = conn.execute(text("""
            SELECT id, name, full_name, ministry, aliases, answer_count
            FROM prs_schemes
            ORDER BY COALESCE(answer_count, 0) DESC
        """)).mappings().all()

    schemes    = [dict(r) for r in all_rows]
    acronyms   = [s for s in schemes if _ACRONYM_RE.match(s["name"].strip())]
    full_names = [s for s in schemes if not _ACRONYM_RE.match(s["name"].strip())]

    # Build reverse lookup: generated acronym string → full-name scheme
    # (first scheme with highest answer_count wins when there are collisions)
    acr_to_full: dict[str, dict] = {}
    for s in full_names:
        for acr in _generate_acronyms(s["name"]):
            acr_to_full.setdefault(acr, s)

    # Also index full names by semantic key for dict-based lookup
    sem_to_full: dict[str, dict] = {}
    for s in full_names:
        key = _semantic_key(s["name"])
        if len(key) >= 4:
            sem_to_full.setdefault(key, s)

    merge_pairs: list[tuple[dict, dict]] = []
    seen_full_ids: set[int] = set()

    for acro in acronyms:
        raw  = acro["name"].strip()
        norm = raw.upper().replace("-", "").replace(" ", "")

        target = None

        # Strategy 1 — hardcoded dictionary
        canon = _ACRONYM_DICT.get(norm) or _ACRONYM_DICT.get(raw)
        if canon:
            target = sem_to_full.get(_semantic_key(canon))

        # Strategy 2 — pattern generation
        if not target:
            target = acr_to_full.get(norm)

        if target and target["id"] != acro["id"] and target["id"] not in seen_full_ids:
            merge_pairs.append((acro, target))
            seen_full_ids.add(target["id"])

    if dry_run:
        return {
            "acronym_pairs_found": len(merge_pairs),
            "acronym_pairs": [
                {"acronym": a["name"], "full_name": f["name"]}
                for a, f in merge_pairs[:40]
            ],
        }

    merged = 0
    with engine.begin() as conn:
        for acro, full in merge_pairs:
            all_aliases = list(full.get("aliases") or [])
            if acro["name"] not in all_aliases:
                all_aliases.append(acro["name"])
            for a in (acro.get("aliases") or []):
                if a not in all_aliases and a != full["name"]:
                    all_aliases.append(a)

            total_count = (full.get("answer_count") or 0) + (acro.get("answer_count") or 0)

            conn.execute(text("""
                UPDATE prs_schemes
                SET aliases = :aliases, answer_count = :count, updated_at = NOW()
                WHERE id = :id
            """), {"aliases": all_aliases, "count": total_count, "id": full["id"]})

            conn.execute(text("DELETE FROM prs_schemes WHERE id = :id"),
                         {"id": acro["id"]})
            conn.execute(text(
                "DELETE FROM scheme_intelligence_cache WHERE scheme_name = :name"
            ), {"name": acro["name"]})

            merged += 1

    try:
        from modules.schemes_api import _runtime_cache
        _runtime_cache.clear()
    except Exception:
        pass

    logger.info("Acronym dedup done: %d pairs merged", merged)
    return {
        "acronym_pairs_merged": merged,
        "schemes_before":       len(schemes),
        "schemes_remaining":    len(schemes) - merged,
    }


# ── Substring containment dedup ───────────────────────────────────────────────

def deduplicate_substrings(dry_run: bool = False) -> dict:
    """
    Pass 3: within each ministry, merge a scheme whose name is a suffix-match
    or consecutive-word-match inside a longer scheme name.

    'Capital Subsidy Scheme' (suffix of 'Credit Linked Capital Subsidy Scheme') → alias
    'Kisan Mission'          (suffix of 'Pradhan Mantri Kisan Mission')           → alias

    Minimum candidate length: 12 chars (prevents over-merging short tokens).
    Only considers pairs within the same ministry to avoid cross-ministry collisions.
    Should run AFTER semantic + acronym passes on clean data.
    """
    from collections import defaultdict

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, name, ministry, aliases, answer_count
            FROM prs_schemes
            WHERE ministry IS NOT NULL AND ministry != ''
            ORDER BY ministry, LENGTH(name) DESC, COALESCE(answer_count, 0) DESC
        """)).mappings().all()

    ministry_groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        ministry_groups[r["ministry"]].append(dict(r))

    def _is_contained(short: str, long_: str) -> bool:
        """True if short is a meaningful sub-sequence of long_."""
        s = short.lower().strip()
        l = long_.lower().strip()
        if s == l or len(s) < 12:
            return False
        # Suffix match (most common extraction artifact)
        if l.endswith(" " + s) or l.endswith(s):
            return True
        # Consecutive-word match
        s_words = s.split()
        l_words = l.split()
        if len(s_words) >= 2:
            for i in range(len(l_words) - len(s_words) + 1):
                if l_words[i: i + len(s_words)] == s_words:
                    return True
        return False

    merge_pairs: list[tuple[dict, dict]] = []
    absorbed: set[int] = set()

    for schemes in ministry_groups.values():
        for i, short in enumerate(schemes):
            if short["id"] in absorbed:
                continue
            for long_ in schemes[:i]:   # longer names come first (sorted by LENGTH DESC)
                if long_["id"] in absorbed:
                    continue
                if _is_contained(short["name"], long_["name"]):
                    merge_pairs.append((short, long_))
                    absorbed.add(short["id"])
                    break

    if dry_run:
        return {
            "substring_pairs_found": len(merge_pairs),
            "substring_pairs": [
                {"contained": a["name"], "parent": b["name"]}
                for a, b in merge_pairs[:40]
            ],
        }

    merged = 0
    with engine.begin() as conn:
        for short, parent in merge_pairs:
            all_aliases = list(parent.get("aliases") or [])
            if short["name"] not in all_aliases:
                all_aliases.append(short["name"])
            for a in (short.get("aliases") or []):
                if a not in all_aliases and a != parent["name"]:
                    all_aliases.append(a)

            total_count = (parent.get("answer_count") or 0) + (short.get("answer_count") or 0)

            conn.execute(text("""
                UPDATE prs_schemes
                SET aliases = :aliases, answer_count = :count, updated_at = NOW()
                WHERE id = :id
            """), {"aliases": all_aliases, "count": total_count, "id": parent["id"]})

            conn.execute(text("DELETE FROM prs_schemes WHERE id = :id"),
                         {"id": short["id"]})
            conn.execute(text(
                "DELETE FROM scheme_intelligence_cache WHERE scheme_name = :name"
            ), {"name": short["name"]})

            merged += 1

    try:
        from modules.schemes_api import _runtime_cache
        _runtime_cache.clear()
    except Exception:
        pass

    logger.info("Substring dedup done: %d pairs merged", merged)
    return {
        "substring_pairs_merged": merged,
        "schemes_before":         len(rows),
        "schemes_remaining":      len(rows) - merged,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    ap = argparse.ArgumentParser(description="Extract PRS schemes from parliamentary questions")
    ap.add_argument("--full", action="store_true", help="Process all subjects (first-time setup)")
    ap.add_argument("--incremental", action="store_true", help="Process only new subjects")
    ap.add_argument("--stats", action="store_true", help="Show current stats")
    ap.add_argument("--refresh-counts", action="store_true", help="Refresh answer counts only")
    args = ap.parse_args()

    if args.stats:
        print(json.dumps(get_stats(), indent=2, default=str))
    elif args.refresh_counts:
        refresh_answer_counts()
    elif args.full or args.incremental:
        result = run_extraction(full=args.full)
        print(json.dumps(result, indent=2, default=str))
    else:
        ap.print_help()
