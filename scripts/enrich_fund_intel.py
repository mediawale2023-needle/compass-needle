"""
Enriches fund_intel.json by joining with schemes_db.json budget allocations.
No internet required — works entirely on local data.

Also extracts:
- Question context tags (utilization, unspent, allocation, etc.) from titles
- Any rupee amounts mentioned in question titles
- Links fund_intel ministries to their schemes and budgets

Run:
    python scripts/enrich_fund_intel.py
"""
import json
import re
import os
from collections import defaultdict
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(__file__))

# ── Loaders ────────────────────────────────────────────────────────────────────

def load_schemes():
    with open(os.path.join(BASE, "schemes_db.json")) as f:
        return json.load(f)

def load_fund_intel():
    with open(os.path.join(BASE, "fund_intel.json")) as f:
        return json.load(f)

# ── Budget parser ───────────────────────────────────────────────────────────────

def parse_cr(s):
    """'₹60,000 Cr' → 60000.0"""
    if not s:
        return 0.0
    skip = {
        "N/A", "Check Dept", "Merged in Samagra", "Replaced by PM E-DRIVE",
        "Replaced by SMAM", "N/A (Scheme Closed)", "Subsumed",
        "Demand-based", "Demand-Based",
    }
    if s.strip() in skip:
        return 0.0
    s = s.replace("₹", "").replace(",", "").strip()
    m = re.search(r"[\d.]+", s)
    if not m:
        return 0.0
    val = float(m.group())
    if "lakh" in s.lower():
        val /= 100
    return val

# ── Ministry name normalizer ────────────────────────────────────────────────────

def norm_ministry(name):
    """Normalize ministry names for fuzzy matching."""
    name = name.upper().strip()
    for prefix in ["MINISTRY OF ", "MINISTRY FOR ", "DEPARTMENT OF ", "DEPT OF ", "MIN OF "]:
        name = name.replace(prefix, "")
    name = name.replace("&", "AND").replace("  ", " ").strip()
    return name

# ── Match fund_intel ministry → schemes_db ministry ────────────────────────────

def build_ministry_lookup(schemes):
    """Build lookup: norm_name → (full_name, budget, scheme_list)"""
    budget_by_ministry = defaultdict(float)
    schemes_by_ministry = defaultdict(list)

    for s in schemes:
        m = s.get("ministry", "")
        amt = parse_cr(s.get("budget_allocation", ""))
        budget_by_ministry[m] += amt
        schemes_by_ministry[m].append({
            "name": s["name"],
            "alloc_cr": amt,
            "focus": s.get("focus", ""),
            "budget_allocation": s.get("budget_allocation", "N/A"),
            "active": s.get("active", "Yes"),
        })

    lookup = {}  # norm → {"full": str, "budget": float, "schemes": list}
    for full, budget in budget_by_ministry.items():
        lookup[norm_ministry(full)] = {
            "full_name": full,
            "budget_cr": budget,
            "schemes": sorted(schemes_by_ministry[full], key=lambda x: -x["alloc_cr"]),
        }
    return lookup


def match_ministry(fi_name, lookup):
    """Find best match for a fund_intel ministry name in the schemes lookup."""
    fi_norm = norm_ministry(fi_name)

    # Exact match
    if fi_norm in lookup:
        return lookup[fi_norm]

    # Substring match: fi_norm in schemes norm OR schemes norm in fi_norm
    best = None
    best_score = 0
    for norm_name, data in lookup.items():
        # Score = chars in common / max length
        words_fi = set(fi_norm.split())
        words_s = set(norm_name.split())
        common = words_fi & words_s
        score = len(common) / max(len(words_fi), len(words_s))
        if score > best_score:
            best_score = score
            best = data

    return best if best_score >= 0.5 else None

# ── Question context tagger ─────────────────────────────────────────────────────

TAGS = {
    "utilization": ["utiliz", "utilis", "spent", "expenditure", "expended"],
    "unspent":     ["unspent", "unused", "lapsed", "underutilized", "under-utilized", "underspent"],
    "allocation":  ["allocat", "allotted", "allotment", "sanctioned", "sanction"],
    "release":     ["released", "release", "disbursed", "disbursement"],
    "budget":      ["budget", "provision", "revised estimate", "be "],
    "delay":       ["delay", "pending", "stuck", "slow", "progress"],
}

def tag_question(title):
    t = title.lower()
    tags = []
    for tag, keywords in TAGS.items():
        if any(kw in t for kw in keywords):
            tags.append(tag)
    return tags if tags else ["general"]

def extract_amount_from_title(title):
    """Try to pull a rupee amount from a question title."""
    # Match: ₹X,XX,XXX Cr  or  Rs X Cr  or  X crore
    patterns = [
        r"₹\s*([\d,]+(?:\.\d+)?)\s*(?:cr(?:ore)?)?",
        r"rs\.?\s*([\d,]+(?:\.\d+)?)\s*(?:cr(?:ore)?)?",
        r"([\d,]+(?:\.\d+)?)\s*(?:cr(?:ore)s?)",
    ]
    for pat in patterns:
        m = re.search(pat, title, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                pass
    return None

# ── Main enrichment ─────────────────────────────────────────────────────────────

def enrich():
    print("Loading data...")
    schemes = load_schemes()
    fund = load_fund_intel()

    lookup = build_ministry_lookup(schemes)
    print(f"  Schemes DB: {len(schemes)} schemes across {len(lookup)} ministries")
    print(f"  Fund Intel: {len(fund['ministries'])} ministries, {fund['metadata']['total_fund_questions']} questions")

    enriched_ministries = []
    total_matched = 0
    total_budget = 0

    for m in fund["ministries"]:
        # Tag each question
        tagged_qs = []
        for q in m.get("questions", []):
            title = q.get("title", "")
            tags = tag_question(title)
            amount = extract_amount_from_title(title)
            tagged_qs.append({
                **q,
                "tags": tags,
                "title_amount_cr": amount,
            })

        # Summarize tag counts for this ministry
        tag_counts = defaultdict(int)
        for q in tagged_qs:
            for tag in q["tags"]:
                tag_counts[tag] += 1

        # Match to schemes_db
        matched = match_ministry(m["ministry"], lookup)
        ministry_budget = matched["budget_cr"] if matched else 0
        ministry_schemes = matched["schemes"] if matched else []
        full_name = matched["full_name"] if matched else m["ministry"].title()

        if matched:
            total_matched += 1
            total_budget += ministry_budget

        # Compute scrutiny severity score (0–100)
        total_qs = m["total_questions"]
        unspent_qs = tag_counts.get("unspent", 0)
        delay_qs = tag_counts.get("delay", 0)
        severity = min(100, int(
            (total_qs * 2) +
            (unspent_qs * 10) +
            (delay_qs * 8)
        ))

        enriched_ministries.append({
            "ministry": m["ministry"],
            "full_name": full_name,
            "total_questions": total_qs,
            "budget_cr": round(ministry_budget, 2),
            "scheme_count": len(ministry_schemes),
            "schemes": ministry_schemes[:10],  # top 10 by budget
            "questions": tagged_qs,
            "tag_counts": dict(tag_counts),
            "severity_score": severity,
            "has_budget_data": bool(matched),
        })

    # Sort by total_questions desc
    enriched_ministries.sort(key=lambda x: -x["total_questions"])

    output = {
        "metadata": {
            **fund["metadata"],
            "enriched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_budget_cr": round(total_budget, 2),
            "ministries_matched_to_budget": total_matched,
            "enrichment_version": 2,
        },
        "ministries": enriched_ministries,
        "existing_allocations": fund.get("existing_allocations", []),
    }

    out_path = os.path.join(BASE, "fund_intel.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nDone! Enriched fund_intel.json:")
    print(f"  Ministries matched to budget: {total_matched}/{len(enriched_ministries)}")
    print(f"  Total budget tracked: ₹{total_budget:,.0f} Cr")
    print(f"  Output: {out_path}")

    # Preview top 5
    print("\nTop 5 most questioned ministries:")
    for m in enriched_ministries[:5]:
        print(f"  {m['ministry'][:40]:42} | Qs: {m['total_questions']:3} | Budget: ₹{m['budget_cr']:>10,.0f} Cr | Tags: {dict(list(m['tag_counts'].items())[:3])}")


if __name__ == "__main__":
    enrich()
