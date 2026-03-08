"""
API Router — REST endpoints for the Next.js frontend.
Mounted in main.py as app.include_router(api_router, prefix="/api")
"""
import os
import json
import bcrypt
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt
from jwt.exceptions import PyJWTError as JWTError
from sqlalchemy import text

# ─── Single DB engine from db.py (fixes dual-engine bug) ───
from sansadx_backend.db import engine, SessionLocal
from core.db_helpers import _q, _q_one, _parse_meta

logger = logging.getLogger("needle.api")

# ─── Rate limiting (optional) ───
try:
    from core.rate_limiter import limiter, RATE_AI, RATE_LOGIN
    _limit_login = limiter.limit(RATE_LOGIN)
    _limit_ai = limiter.limit(RATE_AI)
except Exception:
    def _noop(f): return f
    _limit_login = _noop
    _limit_ai = _noop

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", "")
if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise ValueError("JWT_SECRET env var must be set and at least 32 characters long.")

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 1

security = HTTPBearer()
router = APIRouter()


# ─────────────────────────────────────────
# JWT HELPERS
# ─────────────────────────────────────────
def create_token(data: dict) -> str:
    payload = {**data, "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(401, "Invalid token")
        user = _q_one("SELECT * FROM users WHERE username = :u", {"u": username})
        if not user:
            raise HTTPException(401, "User not found")
        return user
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")


# ─────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
@_limit_login
def login(req: LoginRequest, request: Request):
    user = _q_one("SELECT * FROM users WHERE username = :u", {"u": req.username})
    if not user:
        raise HTTPException(401, "Invalid credentials")

    stored_hash = user.get("password_hash", "")
    valid = False

    try:
        if stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$"):
            valid = bcrypt.checkpw(req.password.encode(), stored_hash.encode())
    except Exception:
        pass

    if not valid:
        raise HTTPException(401, "Invalid credentials")

    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE users SET last_login = :now WHERE username = :u"),
                {"now": datetime.utcnow(), "u": req.username}
            )
    except Exception:
        pass

    tenant = _q_one("SELECT * FROM tenants WHERE id = :tid", {"tid": user.get("tenant_id", 1)})
    house = user.get("house") or "Lok Sabha"
    token = create_token({"sub": user["username"], "tid": user.get("tenant_id", 1), "role": user.get("role", "user")})

    return {
        "token": token,
        "user": {
            "username": user["username"],
            "display_name": user.get("display_name") or user["username"].title(),
            "role": user.get("role", "user"),
            "tenant_id": user.get("tenant_id", 1),
            "constituency": tenant.get("constituency", "India") if tenant else "India",
            "house": house,
            "theme_color": "#006a4d" if house == "Lok Sabha" else "#8d153a",
        }
    }


@router.get("/auth/me")
def get_me(user=Depends(get_current_user)):
    tenant = _q_one("SELECT * FROM tenants WHERE id = :tid", {"tid": user.get("tenant_id", 1)})
    house = user.get("house") or "Lok Sabha"
    return {
        "username": user["username"],
        "display_name": user.get("display_name") or user["username"].title(),
        "role": user.get("role", "user"),
        "tenant_id": user.get("tenant_id", 1),
        "constituency": tenant.get("constituency", "India") if tenant else "India",
        "house": house,
        "theme_color": "#006a4d" if house == "Lok Sabha" else "#8d153a",
    }


# ─────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────
@router.get("/dashboard/summary")
def dashboard_summary(user=Depends(get_current_user)):
    tid = user.get("tenant_id", 1)

    cats = _q(
        "SELECT category, COUNT(*) as count FROM cases WHERE tenant_id = :tid GROUP BY category ORDER BY count DESC",
        {"tid": tid}
    )
    category_breakdown = {c["category"]: c["count"] for c in cats if c["category"]}

    statuses = _q(
        "SELECT status, COUNT(*) as count FROM cases WHERE tenant_id = :tid GROUP BY status",
        {"tid": tid}
    )
    status_breakdown = {s["status"]: s["count"] for s in statuses if s["status"]}
    total = sum(status_breakdown.values())

    critical = _q_one(
        "SELECT COUNT(*) as cnt FROM cases WHERE tenant_id = :tid AND is_critical = true",
        {"tid": tid}
    )

    # Try PostgreSQL JSON syntax first, fall back to SQLite
    try:
        red_zones = _q("""
            SELECT case_metadata->>'assembly_constituency' as ac, COUNT(*) as cnt
            FROM cases WHERE tenant_id = :tid AND case_metadata IS NOT NULL
            GROUP BY ac HAVING COUNT(*) > 20
        """, {"tid": tid})
    except Exception:
        red_zones = []

    return {
        "total_cases": total,
        "category_breakdown": category_breakdown,
        "status_breakdown": status_breakdown,
        "critical_count": critical["cnt"] if critical else 0,
        "red_zones": [r["ac"] for r in red_zones if r.get("ac")],
    }


# ─────────────────────────────────────────
# CASES
# ─────────────────────────────────────────
@router.get("/cases")
def get_cases(
    user=Depends(get_current_user),
    status: Optional[str] = None,
    category: Optional[str] = None,
    categories: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    tid = user.get("tenant_id", 1)
    conditions = ["c.tenant_id = :tid"]
    params = {"tid": tid}

    if status:
        conditions.append("c.status = :st")
        params["st"] = status
    if category:
        conditions.append("c.category = :cat")
        params["cat"] = category
    if categories:
        cat_list = [c.strip() for c in categories.split(",") if c.strip()]
        if cat_list:
            placeholders = ", ".join(f":cat_{i}" for i in range(len(cat_list)))
            conditions.append(f"c.category IN ({placeholders})")
            for i, c in enumerate(cat_list):
                params[f"cat_{i}"] = c

    where = " AND ".join(conditions)
    offset = (page - 1) * limit

    count_row = _q_one(f"SELECT COUNT(*) as cnt FROM cases c WHERE {where}", params)
    total = count_row["cnt"] if count_row else 0

    cases = _q(f"""
        SELECT c.id, c.user_phone, c.category, c.status, c.raw_message,
               c.case_metadata, c.is_critical, c.created_at, c.updated_at,
               c.response_to_citizen, c.notes_for_staff
        FROM cases c WHERE {where}
        ORDER BY c.created_at DESC
        LIMIT :lim OFFSET :off
    """, {**params, "lim": limit, "off": offset})

    for c in cases:
        meta = c.get("case_metadata")
        if meta and isinstance(meta, dict):
            c["location"] = meta.get("matched_value", "")
            c["assembly"] = meta.get("assembly_constituency", "")
        elif meta and isinstance(meta, str):
            try:
                m = json.loads(meta)
                c["location"] = m.get("matched_value", "")
                c["assembly"] = m.get("assembly_constituency", "")
            except Exception:
                c["location"] = ""
                c["assembly"] = ""
        else:
            c["location"] = ""
            c["assembly"] = ""

        for field in ["created_at", "updated_at"]:
            val = c.get(field)
            if val and hasattr(val, "isoformat"):
                c[field] = val.isoformat()

    return {"cases": cases, "total": total, "page": page, "limit": limit}


@router.get("/cases/{case_id}")
def get_case(case_id: int, user=Depends(get_current_user)):
    tid = user.get("tenant_id", 1)
    case = _q_one("""
        SELECT c.*, t.name as mp_name, t.constituency as mp_constituency
        FROM cases c JOIN tenants t ON c.tenant_id = t.id
        WHERE c.id = :cid AND c.tenant_id = :tid
    """, {"cid": case_id, "tid": tid})

    if not case:
        raise HTTPException(404, "Case not found")

    for field in ["created_at", "updated_at", "resolved_at"]:
        val = case.get(field)
        if val and hasattr(val, "isoformat"):
            case[field] = val.isoformat()

    return case


class StatusUpdate(BaseModel):
    status: str


@router.patch("/cases/{case_id}/status")
def update_case_status(case_id: int, body: StatusUpdate, user=Depends(get_current_user)):
    tid = user.get("tenant_id", 1)
    with engine.begin() as conn:
        result = conn.execute(text(
            "UPDATE cases SET status = :st, updated_at = :now WHERE id = :cid AND tenant_id = :tid"
        ), {"st": body.status, "now": datetime.utcnow(), "cid": case_id, "tid": tid})
    if result.rowcount == 0:
        raise HTTPException(404, "Case not found")
    return {"success": True}


# ─────────────────────────────────────────
# PROFILE
# ─────────────────────────────────────────
@router.get("/profile")
def get_profile(user=Depends(get_current_user)):
    tid = user.get("tenant_id", 1)
    profile = _q_one("SELECT * FROM tenant_profiles WHERE tenant_id = :tid", {"tid": tid})
    if profile:
        val = profile.get("profile_data")
        if val and isinstance(val, str):
            try:
                profile["profile_data"] = json.loads(val)
            except Exception:
                pass
    return profile or {}


# ─────────────────────────────────────────
# NEWS
# ─────────────────────────────────────────
@router.get("/news")
def get_news(news_type: str = "national", user=Depends(get_current_user)):
    try:
        if news_type == "national":
            from modules.news_intel import fetch_news
            display_name = user.get("display_name") or user.get("username", "")
            articles = fetch_news(query=f'"{display_name}"', limit=8)
        else:
            from modules.news_intel import fetch_constituency_news
            articles = fetch_constituency_news(tenant_id=user.get("tenant_id"), limit=8)
        return {"articles": articles or []}
    except Exception:
        return {"articles": []}


# ─────────────────────────────────────────
# COPILOT
# ─────────────────────────────────────────
from fastapi import File, UploadFile


class CopilotRequest(BaseModel):
    message: str
    history: list = []
    document_context: str = ""


@router.post("/copilot/upload")
async def copilot_upload(file: UploadFile = File(...), user=Depends(get_current_user)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")
    try:
        import pymupdf
        content = await file.read()
        doc = pymupdf.open(stream=content, filetype="pdf")
        pages = []
        for i, page in enumerate(doc):
            text_content = page.get_text()
            if text_content.strip():
                pages.append({"page": i + 1, "text": text_content})
        doc.close()
        return {"filename": file.filename, "pages": len(pages), "content": pages}
    except Exception as e:
        raise HTTPException(500, f"Failed to process PDF: {str(e)}")


class AnalyseRequest(BaseModel):
    document_text: str
    filename: str = "document"
    language: str = "English"
    depth: str = "Quick Scan"


@router.post("/copilot/analyse")
@_limit_ai
def copilot_analyse(req: AnalyseRequest, request: Request, user=Depends(get_current_user)):
    if not req.document_text:
        return {"analysis": "No document content provided."}
    try:
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {"analysis": "Error: GEMINI_API_KEY not configured."}
        client = genai.Client(api_key=api_key)
        lang_note = "Respond in Hindi (Devanagari script)." if "Hindi" in req.language else ""
        depth_note = "Focus on top 5 most significant findings." if req.depth == "Quick Scan" else "Be comprehensive."
        prompt = f"""
ROLE: Senior Parliamentary Research Officer.
TASK: Intelligence briefing on this document for a Member of Parliament.
{lang_note} {depth_note}
DOCUMENT: {req.filename}
{req.document_text[:80000]}

PRODUCE THESE SECTIONS:
## Executive Summary
3-4 line summary: what this document is and why it matters.

## Key Risks and Red Flags
| Clause/Section | Risk Level | Issue | Implication |
|---|---|---|---|

## Stakeholder Impact
- Beneficiaries: who gains and how
- Adversely Affected: who loses and how
- Constituency Impact: effect on voters

## Talking Points for Parliament
3-5 ready-to-use arguments — both FOR and AGAINST positions.

## Recommended Action
Support, oppose, or seek amendments — with specific justification.
"""
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return {"analysis": response.text}
    except Exception as e:
        return {"analysis": f"Error: {str(e)}"}


@router.post("/copilot/chat")
@_limit_ai
def copilot_chat(req: CopilotRequest, request: Request, user=Depends(get_current_user)):
    try:
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {"response": "Error: GEMINI_API_KEY not configured."}
        client = genai.Client(api_key=api_key)
        context_block = ""
        if req.document_context:
            context_block = f"\n\nDOCUMENT CONTEXT:\n{req.document_context[:60000]}"
        history_text = "\n".join(
            f"{'User' if m.get('role') == 'user' else 'Assistant'}: {m.get('content', '')}"
            for m in req.history[-10:]
        )
        prompt = f"""System: You are 'Needle', a parliamentary intelligence assistant.
Keep answers concise and actionable. Reference specific clauses/sections when discussing documents.
{context_block}
{history_text}
User: {req.message}"""
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return {"response": response.text}
    except Exception as e:
        return {"response": f"Error: {str(e)}"}


# ─────────────────────────────────────────
# DRAFTER
# ─────────────────────────────────────────
class DraftRequest(BaseModel):
    mode: str = "letter"
    topic: str = ""
    subject: str = ""
    recipient_name: str = ""
    recipient_type: str = "Cabinet Minister"
    ministry: str = ""
    reference: str = ""
    key_points: str = ""
    tone: str = "Assertive (Opposition Style)"
    language: str = "English"
    context: str = ""


TONE_PRESETS = {
    "Assertive (Opposition Style)": {
        "instruction": "Use firm, demanding language. Cite facts, demand timelines, imply consequences.",
        "salutation": "Sir",
        "close": "Yours faithfully"
    },
    "Requesting (Ministerial Courtesy)": {
        "instruction": "Use polite but firm language. Frame demands as requests. Acknowledge prior efforts.",
        "salutation": "Dear Sir/Madam",
        "close": "Yours sincerely"
    },
    "Formal (Neutral)": {
        "instruction": "Strictly professional, no emotional language. State facts, request action.",
        "salutation": "Dear Sir/Madam",
        "close": "Yours sincerely"
    },
}


@router.post("/drafter/generate")
@_limit_ai
def generate_draft(req: DraftRequest, request: Request, user=Depends(get_current_user)):
    try:
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {"content": "Error: GEMINI_API_KEY not configured."}
        client = genai.Client(api_key=api_key)
        tid = user.get("tenant_id", 1)
        tenant = _q_one("SELECT * FROM tenants WHERE id = :tid", {"tid": tid})
        mp_name = user.get("display_name") or user.get("username", "").title()
        constituency = tenant.get("constituency", "India") if tenant else "India"
        house = user.get("house") or "Lok Sabha"
        tone_config = TONE_PRESETS.get(req.tone, TONE_PRESETS["Formal (Neutral)"])
        lang_note = "Write in Hindi (Devanagari script). Use formal Rajbhasha." if req.language == "Hindi" else ""

        if req.mode == "letter":
            prompt = f"""
You are drafting a formal letter as {mp_name}, Member of Parliament ({house}) representing {constituency}.
RECIPIENT: {req.recipient_name}
RECIPIENT TYPE: {req.recipient_type}
MINISTRY/OFFICE: {req.ministry}
SUBJECT: {req.subject or req.topic}
REFERENCE: {req.reference or "None"}
{tone_config['instruction']}
{lang_note}
LETTER FORMAT:
- Government of India letter format
- File Reference: MP/GEN/{datetime.utcnow().year}/[SEQ]
- Date: {datetime.utcnow().strftime("%d %B %Y")}
- From: {mp_name}, Member of Parliament, {constituency} ({house})
- Salutation: {tone_config['salutation']}
- Closing: {tone_config['close']}
KEY POINTS TO COVER:
{req.key_points or req.context or req.topic}
RULES:
- Generate ONLY the letter text, no explanations
- Do NOT invent statistics, dates, or case numbers not provided
- Use formal parliamentary language
- If data is missing, use [...] placeholders
"""
        elif req.mode == "question":
            prompt = f"""
You are drafting a Parliament Question for {mp_name}, Member of Parliament ({house}) representing {constituency}.
SUBJECT: {req.subject or req.topic}
MINISTRY: {req.ministry or "Relevant Ministry"}
{lang_note}
CONTEXT/POINTS:
{req.key_points or req.context or req.topic}
FORMAT — STARRED QUESTION:
(a) Whether the Government is aware of [issue]?
(b) If so, the details thereof?
(c) The State-wise / Year-wise data?
(d) The steps taken / being taken by the Government?
(e) The timeline for implementation?
Each sub-part (a) to (e) must be ONE sentence only.
Do NOT invent statistics. Generate ONLY the question text.
"""
        else:
            prompt = f"""
You are drafting a formal document for {mp_name}, Member of Parliament ({house}) representing {constituency}.
TOPIC: {req.topic or req.subject}
CONTEXT: {req.context or req.key_points}
{lang_note}
Generate a professional parliamentary document. Do NOT invent statistics.
"""
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=genai.types.GenerateContentConfig(temperature=0.2),
        )
        return {"content": response.text}
    except Exception as e:
        return {"content": f"Error generating draft: {str(e)}"}


# ─────────────────────────────────────────
# SCHEMES
# ─────────────────────────────────────────
class SchemeSearchRequest(BaseModel):
    query: str
    category: Optional[str] = None
    ministry: Optional[str] = None


class CitizenMatchRequest(BaseModel):
    groups: list
    gender: Optional[str] = "Any"
    location: Optional[str] = "Any"


def _parse_budget(budget_str):
    if not budget_str or not isinstance(budget_str, str):
        return 0
    import re
    cleaned = re.sub(r'[₹,]', '', budget_str)
    match = re.search(r'([\d.]+)', cleaned)
    if match:
        num = float(match.group(1))
        if 'lakh' in budget_str.lower():
            return num / 100
        return num
    return 0


import time

# ─── In-memory cache for JSON data (5 min TTL) ───
_cache = {}
_CACHE_TTL = 300  # seconds

def _cached_load(key, loader_fn):
    now = time.time()
    if key in _cache and (now - _cache[key]["ts"]) < _CACHE_TTL:
        return _cache[key]["data"]
    data = loader_fn()
    _cache[key] = {"data": data, "ts": now}
    return data


def _load_schemes():
    try:
        with open("schemes_db.json", "r", encoding="utf-8") as f:
            schemes = json.load(f)
        for s in schemes:
            s["budget_numeric"] = _parse_budget(s.get("budget_allocation", ""))
        return schemes
    except (FileNotFoundError, json.JSONDecodeError):
        return []


@router.post("/schemes/search")
def search_schemes(req: SchemeSearchRequest, user=Depends(get_current_user)):
    schemes = _cached_load("schemes", _load_schemes)
    if not schemes:
        return {"schemes": [], "total": 0}
    query_lower = req.query.lower()
    keywords = query_lower.split()
    results = []
    for s in schemes:
        text_blob = f"{s.get('name', '')} {s.get('description', '')} {s.get('focus', '')} {s.get('category', '')} {s.get('ministry', '')}".lower()
        score = sum(1 for kw in keywords if kw in text_blob)
        if score > 0:
            results.append({**s, "_score": score})
    if req.category:
        results = [r for r in results if r.get("category", "").lower() == req.category.lower()]
    if req.ministry:
        results = [r for r in results if req.ministry.lower() in r.get("ministry", "").lower()]
    results.sort(key=lambda x: x["_score"], reverse=True)
    for r in results:
        r.pop("_score", None)
    return {"schemes": results[:50], "total": len(results)}


@router.get("/schemes/all")
def get_all_schemes(user=Depends(get_current_user), category: Optional[str] = None, ministry: Optional[str] = None):
    from collections import defaultdict
    schemes = _cached_load("schemes", _load_schemes)
    all_schemes = schemes[:]
    if category:
        schemes = [s for s in schemes if s.get("category", "").lower() == category.lower()]
    if ministry:
        schemes = [s for s in schemes if ministry.lower() in s.get("ministry", "").lower()]
    categories = sorted(set(s.get("category", "OTHER") for s in all_schemes))
    ministries = sorted(set(s.get("ministry", "") for s in all_schemes if s.get("ministry")))
    ministry_agg = defaultdict(lambda: {"count": 0, "budget": 0, "top": "", "categories": set()})
    for s in all_schemes:
        m = s.get("ministry", "Unknown")
        ministry_agg[m]["count"] += 1
        ministry_agg[m]["budget"] += s.get("budget_numeric", 0)
        if not ministry_agg[m]["top"]:
            ministry_agg[m]["top"] = s.get("name", "")
        ministry_agg[m]["categories"].add(s.get("category", ""))
    ministry_summary = [
        {"ministry": m, "count": d["count"], "budget": d["budget"], "top_scheme": d["top"],
         "categories": list(d["categories"])[:3]}
        for m, d in ministry_agg.items()
    ]
    ministry_summary.sort(key=lambda x: x["budget"], reverse=True)
    top_schemes = sorted(all_schemes, key=lambda x: x.get("budget_numeric", 0), reverse=True)[:10]
    return {
        "schemes": schemes, "total": len(schemes),
        "categories": categories, "ministries": ministries,
        "ministry_summary": ministry_summary[:20],
        "top_schemes": top_schemes,
        "stats": {
            "total": len(all_schemes),
            "ministries": len(set(s.get("ministry", "") for s in all_schemes)),
            "total_budget": sum(s.get("budget_numeric", 0) for s in all_schemes),
        },
    }


CITIZEN_SCHEME_MAP = {
    "Women": ["Gruha Lakshmi", "Shakti", "Beti Bachao", "Udyogini", "Stand-Up India", "Mahila", "Women", "Stree", "Nari"],
    "Farmers": ["KISAN", "Fasal Bima", "Krishi", "Agriculture", "MSP", "Soil Health", "e-NAM", "Kisan Credit", "PM-KISAN", "Farmer"],
    "SC/ST": ["SC/ST", "Tribal", "Scheduled", "Stand-Up India", "Adivasi", "Post Matric Scholarship", "Pre Matric"],
    "BPL Families": ["Awas", "Ayushman", "Anna Bhagya", "BPL", "Ration", "PMJAY", "Ujjwala", "Housing", "Below Poverty"],
    "Youth / Students": ["Yuva Nidhi", "Scholarship", "Skill", "Education", "Student", "Training", "Vidya", "NEP"],
    "Senior Citizens": ["Pension", "Senior", "Vridha", "Old Age", "Elderly"],
    "Entrepreneurs / MSME": ["Mudra", "SVANidhi", "Vishwakarma", "MSME", "Startup", "Stand-Up", "Entrepreneurship", "Business"],
    "Disabled / PwD": ["Disability", "Divyang", "PwD", "Handicapped", "Accessible"],
    "Rural Residents": ["MGNREGA", "Gramin", "Rural", "PMGSY", "Gram Sadak", "Village", "Panchayat"],
    "Urban Residents": ["AMRUT", "Smart City", "Urban", "Metro", "Municipal", "Swachh Bharat"],
}


@router.post("/schemes/citizen-match")
def match_citizen_schemes(req: CitizenMatchRequest, user=Depends(get_current_user)):
    schemes = _cached_load("schemes", _load_schemes)
    keywords = []
    for g in req.groups:
        keywords.extend(CITIZEN_SCHEME_MAP.get(g, []))
    if req.gender == "Female":
        keywords.extend(["Women", "Mahila", "Stree", "Nari", "Girl"])
    if req.location == "Rural":
        keywords.extend(["Rural", "Gramin", "Village", "Gram"])
    elif req.location == "Urban":
        keywords.extend(["Urban", "City", "Municipal", "Smart City"])
    matched = []
    for s in schemes:
        blob = f"{s.get('name', '')} {s.get('description', '')} {s.get('focus', '')}".lower()
        if any(kw.lower() in blob for kw in keywords):
            matched.append(s)
    matched.sort(key=lambda x: x.get("budget_numeric", 0), reverse=True)
    return {"schemes": matched, "total": len(matched), "profile": ", ".join(req.groups)}


def _load_fund_intel():
    try:
        with open("fund_intel.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


@router.get("/schemes/fund-intel")
def get_fund_intel(user=Depends(get_current_user)):
    """Serve parliamentary fund intelligence data for treemap visualization."""
    fund_data = _cached_load("fund_intel", _load_fund_intel)
    if not fund_data:
        return {"ministries": [], "metadata": {}, "existing_allocations": []}

    # Also merge with scheme allocation data for richer treemap
    schemes = _cached_load("schemes", _load_schemes)
    from collections import defaultdict
    ministry_alloc = defaultdict(float)
    for s in schemes:
        m = (s.get("ministry") or "").upper()
        ministry_alloc[m] += s.get("budget_numeric", 0)

    # Enrich ministry data with allocation
    for m in fund_data.get("ministries", []):
        m_name = m["ministry"].upper()
        m["allocation"] = ministry_alloc.get(m_name, 0)
        # Also check approximate matches
        if not m["allocation"]:
            for k, v in ministry_alloc.items():
                if m_name in k or k in m_name:
                    m["allocation"] = v
                    break

    return fund_data


# ─────────────────────────────────────────
# PARLIAMENT SESSION STATUS
# ─────────────────────────────────────────
_parliament_cache = {"data": None, "ts": None}


@router.get("/parliament/status")
def get_parliament_status(user=Depends(get_current_user)):
    from datetime import date
    import requests as http_requests

    now = datetime.utcnow()
    if _parliament_cache["data"] and _parliament_cache["ts"] and (now - _parliament_cache["ts"]).total_seconds() < 1800:
        return _parliament_cache["data"]

    today = date.today()
    house = user.get("house", "Lok Sabha")

    SESSIONS_2026 = [
        {"name": "Budget Session (Part I)", "start": date(2026, 1, 31), "end": date(2026, 2, 14)},
        {"name": "Budget Session (Part II)", "start": date(2026, 3, 2), "end": date(2026, 5, 8)},
        {"name": "Monsoon Session", "start": date(2026, 7, 20), "end": date(2026, 8, 14)},
        {"name": "Winter Session", "start": date(2026, 11, 25), "end": date(2026, 12, 20)},
    ]
    SESSIONS_2025 = [
        {"name": "Budget Session (Part I)", "start": date(2025, 1, 31), "end": date(2025, 2, 13)},
        {"name": "Budget Session (Part II)", "start": date(2025, 3, 10), "end": date(2025, 5, 9)},
        {"name": "Monsoon Session", "start": date(2025, 7, 21), "end": date(2025, 8, 13)},
        {"name": "Winter Session", "start": date(2025, 11, 24), "end": date(2025, 12, 20)},
    ]
    all_sessions = SESSIONS_2025 + SESSIONS_2026

    current_session = None
    for sess in all_sessions:
        if sess["start"] <= today <= sess["end"]:
            current_session = sess
            break

    is_weekend = today.weekday() >= 5

    business_items = []
    try:
        house_path = "ls" if "lok" in house.lower() else "rs"
        resp = http_requests.get(f"https://sansad.in/{house_path}", timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        if resp.ok:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup.find_all(["li", "p", "div"], class_=lambda c: c and ("agenda" in str(c).lower() or "business" in str(c).lower())):
                text_val = tag.get_text(strip=True)
                if text_val and 10 < len(text_val) < 500:
                    business_items.append(text_val)
    except Exception:
        pass

    if current_session and not is_weekend:
        session_day = (today - current_session["start"]).days + 1
        result = {
            "in_session": True,
            "session_name": current_session["name"],
            "house": house,
            "session_day": session_day,
            "date": today.strftime("%d %B %Y"),
            "day": today.strftime("%A"),
            "business_items": business_items or [
                "Question Hour (11:00 AM - 12:00 PM)",
                "Zero Hour (12:00 PM - 1:00 PM)",
                "Legislative Business / Government Business",
            ],
            "sansad_link": f"https://sansad.in/{'ls' if 'lok' in house.lower() else 'rs'}",
        }
    elif current_session and is_weekend:
        result = {
            "in_session": False,
            "reason": "weekend",
            "session_name": current_session["name"],
            "house": house,
            "message": f"Parliament is in {current_session['name']} but does not sit on {today.strftime('%A')}s.",
            "sansad_link": f"https://sansad.in/{'ls' if 'lok' in house.lower() else 'rs'}",
        }
    else:
        next_session = next((s for s in all_sessions if s["start"] > today), None)
        result = {
            "in_session": False,
            "reason": "recess",
            "house": house,
            "message": "Parliament is not in session.",
            "next_session": next_session["name"] if next_session else None,
            "next_session_date": next_session["start"].strftime("%d %b %Y") if next_session else None,
            "sansad_link": f"https://sansad.in/{'ls' if 'lok' in house.lower() else 'rs'}",
        }

    _parliament_cache["data"] = result
    _parliament_cache["ts"] = now
    return result


# ─────────────────────────────────────────
# CSR
# ─────────────────────────────────────────
def _load_csr_data():
    all_data = []
    for path in ["csr_db.json", "csr_discovery.json"]:
        try:
            with open(path, "r") as f:
                all_data += json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    seen = set()
    deduped = []
    for item in all_data:
        name = item.get("Company", "")
        if name and name not in seen:
            seen.add(name)
            deduped.append(item)
    return deduped


@router.get("/csr/companies")
def get_csr_companies(
    user=Depends(get_current_user),
    district: Optional[str] = None,
    sector: Optional[str] = None,
    company_type: Optional[str] = None,
):
    data = _cached_load("csr_data", _load_csr_data)
    if not data:
        return {"companies": [], "total": 0, "districts": [], "sectors": []}
    districts = sorted(set(d.get("District", "") for d in data if d.get("District")))
    sectors = sorted(set(d.get("Sector", "") for d in data if d.get("Sector")))
    filtered = data
    if district:
        filtered = [d for d in filtered if d.get("District") == district]
    if sector:
        filtered = [d for d in filtered if d.get("Sector") == sector]
    if company_type:
        filtered = [d for d in filtered if company_type.lower() in d.get("Type", "").lower()]
    return {"companies": filtered, "total": len(filtered), "districts": districts, "sectors": sectors}


@router.get("/csr/watchdog")
def get_csr_watchdog(user=Depends(get_current_user), district: Optional[str] = None):
    data = _cached_load("csr_data", _load_csr_data)
    violators = [
        d for d in data
        if "Local" in d.get("Type", "") and "ZERO SPEND" in d.get("Status", "")
        and (not district or d.get("District") == district)
    ]
    return {"violators": violators, "total": len(violators)}


@router.get("/csr/proposals")
def get_csr_proposals(user=Depends(get_current_user)):
    tid = user.get("tenant_id", 1)
    try:
        from modules.csr_pipeline import get_csr_candidates, get_monitoring_clusters
        candidates = get_csr_candidates(tid)
        monitoring = get_monitoring_clusters(tid)
        return {"candidates": candidates or [], "monitoring": monitoring or []}
    except Exception as e:
        return {"candidates": [], "monitoring": [], "error": str(e)}


# ─── FIX: get_live_gaps defined here (was called but never defined) ───
def get_live_gaps(tenant_id: int):
    """
    Returns top grievance clusters (category, volume, area) for a tenant.
    Used by CSR strategic matching to find high-volume issues needing CSR funding.
    """
    try:
        # Try PostgreSQL JSON syntax
        rows = _q("""
            SELECT category, COUNT(*) as volume,
                   COALESCE(
                       case_metadata::json->>'assembly_constituency',
                       case_metadata::json->>'matched_value',
                       'Unknown'
                   ) as area
            FROM cases
            WHERE tenant_id = :tid
              AND status NOT IN ('irrelevant', 'offensive')
            GROUP BY category, area
            HAVING COUNT(*) >= 100
            ORDER BY volume DESC
            LIMIT 10
        """, {"tid": tenant_id})
    except Exception:
        try:
            # SQLite fallback
            rows = _q("""
                SELECT category, COUNT(*) as volume, 'Unknown' as area
                FROM cases
                WHERE tenant_id = :tid
                  AND status NOT IN ('irrelevant', 'offensive')
                GROUP BY category
                HAVING COUNT(*) >= 100
                ORDER BY volume DESC
                LIMIT 10
            """, {"tid": tenant_id})
        except Exception:
            rows = []

    return [(r.get("category", "Unknown"), r.get("volume", 0), r.get("area", "Unknown")) for r in rows]


class CSRDraftRequest(BaseModel):
    company: str
    district: str
    total_3y: str = ""
    sector: str = ""
    spend_history: dict = {}
    letter_type: str = "upscale"


@router.post("/csr/draft-letter")
@_limit_ai
def csr_draft_letter(req: CSRDraftRequest, request: Request, user=Depends(get_current_user)):
    try:
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {"content": "Error: GEMINI_API_KEY not configured."}
        client = genai.Client(api_key=api_key)
        tid = user.get("tenant_id", 1)
        tenant = _q_one("SELECT * FROM tenants WHERE id = :tid", {"tid": tid})
        mp_name = user.get("display_name") or user.get("username", "").title()
        constituency = tenant.get("constituency", "India") if tenant else "India"
        history_str = "\n".join(f"  {k}: {v}" for k, v in req.spend_history.items()) if req.spend_history else "N/A"

        if req.letter_type == "upscale":
            prompt = f"""Write a strategic letter from {mp_name}, Member of Parliament for {constituency}.
TO: CSR Head, {req.company}
SUBJECT: Deepening CSR Partnership in {req.district}
CONTEXT:
- {req.company} has spent {req.total_3y} in {req.district} over the past 3 years.
- Sector Focus: {req.sector}
- Spending History:
{history_str}
TONE: Professional gratitude leading to a bigger ask. FORMAT: Formal Indian government letter. No emojis.
Generate ONLY the letter text."""
        else:
            prompt = f"""Write a stern D.O. Letter from {mp_name}, Member of Parliament for {constituency}.
TO: CEO/Managing Director, {req.company}
SUBJECT: Zero CSR Expenditure in {req.district} Despite Local Operations
CONTEXT: {req.company} has factory/office in {req.district}. MCA data shows ZERO CSR spend. History:
{history_str}
Reference Section 135 of Companies Act. Demand explanation within 15 days.
TONE: Formal, Authoritative, Firm. FORMAT: D.O. Letter. No emojis.
Generate ONLY the letter text."""

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=genai.types.GenerateContentConfig(temperature=0.2),
        )
        return {"content": response.text}
    except Exception as e:
        return {"content": f"Error generating draft: {str(e)}"}


class CSRStrategicMatchRequest(BaseModel):
    district: Optional[str] = None


@router.post("/csr/strategic-matches")
def get_strategic_matches(req: CSRStrategicMatchRequest = None, user=Depends(get_current_user)):
    tid = user.get("tenant_id", 1)
    csr_data = _cached_load("csr_data", _load_csr_data)
    gaps = get_live_gaps(tid)

    category_to_sector = {
        "water": ["Water", "Rural Dev"], "road": ["Infrastructure", "Community Dev"],
        "electricity": ["Infrastructure", "Community Dev"], "health": ["Health"],
        "education": ["Education"], "sanitation": ["Health", "Water"],
        "housing": ["Rural Dev", "Community Dev"], "crime": ["Community Dev"],
        "employment": ["Skill Dev", "Education"],
    }

    matches = []
    for (cat, volume, area) in gaps:
        cat_lower = cat.lower()
        matched_sectors = next(
            (sectors for key, sectors in category_to_sector.items() if key in cat_lower),
            ["Community Dev"]
        )
        matched_companies = []
        for company in csr_data:
            if any(s.lower() in (company.get("Sector") or "").lower() for s in matched_sectors):
                if req and req.district and company.get("District") != req.district:
                    continue
                matched_companies.append({
                    "Company": company.get("Company"),
                    "Sector": company.get("Sector"),
                    "Total_3Y": company.get("Total_3Y"),
                    "District": company.get("District"),
                })
        seen = set()
        unique_companies = []
        for c in matched_companies:
            if c["Company"] not in seen:
                seen.add(c["Company"])
                unique_companies.append(c)

        badge = "CRITICAL" if volume >= 500 else "MAJOR" if volume >= 200 else "HIGH DEMAND"
        matches.append({
            "category": cat,
            "volume": volume,
            "area": area,
            "badge": badge,
            "matched_sectors": matched_sectors,
            "matched_companies": unique_companies[:5],
        })

    return {"matches": matches, "total": len(matches)}


class CSRDPRRequest(BaseModel):
    category: str
    area: str
    volume: int
    company: str
    sector: str = ""


@router.post("/csr/generate-dpr")
@_limit_ai
def generate_csr_dpr(req: CSRDPRRequest, request: Request, user=Depends(get_current_user)):
    try:
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {"content": "Error: GEMINI_API_KEY not configured."}
        client = genai.Client(api_key=api_key)  # FIX: was using undefined `model` variable
        tid = user.get("tenant_id", 1)
        tenant = _q_one("SELECT * FROM tenants WHERE id = :tid", {"tid": tid})
        mp_name = user.get("display_name") or user.get("username", "").title()
        constituency = tenant.get("constituency", "India") if tenant else "India"

        prompt = f"""Generate a formal CSR Partnership Proposal / Detailed Project Report (DPR).
FROM: Office of {mp_name}, Member of Parliament, {constituency}
TO: CSR Head, {req.company}
PROJECT DETAILS:
- Issue: {req.category}
- Location: {req.area}
- Evidence: {req.volume} verified citizen complaints/reports
- Target Sector: {req.sector or req.category}
DOCUMENT STRUCTURE:
1. COVER NOTE
2. EXECUTIVE SUMMARY
3. PROBLEM STATEMENT (backed by {req.volume} citizen reports)
4. PROPOSED INTERVENTION (scope, timeline 12-18 months, budget breakdown)
5. IMPACT METRICS & KPIs
6. SDG ALIGNMENT
7. IMPLEMENTATION PARTNERS
8. MONITORING & EVALUATION FRAMEWORK
9. MP'S ENDORSEMENT LINE
TONE: Professional, data-driven. No emojis. Generate ONLY the DPR document text."""

        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return {"content": response.text}
    except Exception as e:
        return {"content": f"Error generating DPR: {str(e)}"}


# ─────────────────────────────────────────
# ACTIVITY HISTORY
# ─────────────────────────────────────────
class SaveActivityRequest(BaseModel):
    activity_type: str
    title: str
    content: str
    metadata: dict = {}


@router.post("/history/save")
def save_activity(req: SaveActivityRequest, user=Depends(get_current_user)):
    tid = user.get("tenant_id", 1)
    username = user.get("username", "")
    meta_json = json.dumps(req.metadata) if req.metadata else "{}"
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO activity_history (tenant_id, username, activity_type, title, content, metadata)
                VALUES (:tid, :u, :atype, :title, :content, :meta)
            """), {"tid": tid, "u": username, "atype": req.activity_type, "title": req.title,
                   "content": req.content, "meta": meta_json})
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, f"Failed to save: {str(e)}")


@router.get("/history")
def get_history(user=Depends(get_current_user), activity_type: Optional[str] = None, limit: int = 50):
    tid = user.get("tenant_id", 1)
    conditions = ["tenant_id = :tid"]
    params = {"tid": tid}
    if activity_type:
        conditions.append("activity_type = :atype")
        params["atype"] = activity_type
    where = " AND ".join(conditions)
    rows = _q(f"""
        SELECT id, activity_type, title, content, metadata, created_at
        FROM activity_history WHERE {where}
        ORDER BY created_at DESC LIMIT :lim
    """, {**params, "lim": limit})
    for r in rows:
        if r.get("created_at") and hasattr(r["created_at"], "isoformat"):
            r["created_at"] = r["created_at"].isoformat()
        if r.get("metadata") and isinstance(r["metadata"], str):
            try:
                r["metadata"] = json.loads(r["metadata"])
            except Exception:
                pass
    return {"items": rows, "total": len(rows)}


@router.delete("/history/{item_id}")
def delete_history_item(item_id: int, user=Depends(get_current_user)):
    tid = user.get("tenant_id", 1)
    try:
        with engine.begin() as conn:
            result = conn.execute(text(
                "DELETE FROM activity_history WHERE id = :id AND tenant_id = :tid"
            ), {"id": item_id, "tid": tid})
        if result.rowcount == 0:
            raise HTTPException(404, "Item not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ─────────────────────────────────────────
# ADMIN — SEED & DEBUG (secured, POST only)
# ─────────────────────────────────────────
ADMIN_KEY = os.getenv("ADMIN_SECRET_KEY", "")
if ADMIN_KEY and len(ADMIN_KEY) < 32:
    raise ValueError("ADMIN_SECRET_KEY must be at least 32 characters long.")


def verify_admin(request: Request):
    """Verify admin key from Authorization header (not URL params)."""
    auth = request.headers.get("Authorization", "")
    if not ADMIN_KEY or not auth.startswith("Bearer ") or auth[7:] != ADMIN_KEY:
        raise HTTPException(403, "Admin access denied")


@router.post("/admin/seed-test-cases")
def seed_test_cases(tid: int = 1, request: Request = None, _=Depends(verify_admin)):
    """Seed test cases for CSR pipeline testing. Secured by ADMIN_SECRET_KEY header."""
    from sansadx_backend.db import SessionLocal, Case, Tenant
    from datetime import timedelta
    import random

    db = SessionLocal()
    try:
        if tid == 0:
            first_tenant = db.query(Tenant).first()
            tid = first_tenant.id if first_tenant else 1

        db.query(Case).filter(Case.tenant_id == tid, Case.user_phone.like("9199%")).delete(synchronize_session=False)
        db.commit()

        clusters = [
            {"category": "Water", "location": "Kelkar Bag", "count": 230},
            {"category": "Infrastructure (State)", "location": "Tilakwadi", "count": 210},
            {"category": "Education (Central)", "location": "Shahapur", "count": 150},
        ]
        phones = [f"9199{i:07d}" for i in range(600)]
        messages = {
            "Water": ["paani nahi aahe ithe", "water supply band aahe", "nali tutli aahe"],
            "Infrastructure (State)": ["rasta khrab aahe", "khade aahet rastawar", "street light nahi"],
            "Education (Central)": ["school madhe teacher nahi", "classroom tutla", "toilet nahi school la"],
        }

        total_inserted = 0
        for cluster in clusters:
            for i in range(cluster["count"]):
                msg_list = messages.get(cluster["category"], ["complaint"])
                case = Case(
                    tenant_id=tid,
                    user_phone=random.choice(phones),
                    raw_message=random.choice(msg_list),
                    category=cluster["category"],
                    status="completed",
                    location=cluster["location"],
                    ward=cluster["location"],
                    is_critical=(i % 20 == 0),
                    response_to_citizen="Noted",
                    case_metadata=json.dumps({
                        "user_intent": "complaint",
                        "location_resolved": True,
                        "matched_value": cluster["location"],
                        "assembly_constituency": cluster["location"],
                    }),
                    created_at=datetime.utcnow() - timedelta(days=random.randint(1, 90)),
                )
                db.add(case)
                total_inserted += 1

        db.commit()
        return {"status": "seeded", "tenant_id_used": tid, "total_cases": total_inserted}
    finally:
        db.close()


@router.get("/admin/tenants")
def debug_tenants(request: Request, _=Depends(verify_admin)):
    """Debug endpoint to check tenants. Secured by ADMIN_SECRET_KEY header."""
    from sansadx_backend.db import SessionLocal, Tenant, Case
    from sqlalchemy import func

    db = SessionLocal()
    try:
        tenants = db.query(Tenant).all()
        result = []
        for t in tenants:
            case_count = db.query(func.count(Case.id)).filter(Case.tenant_id == t.id).scalar()
            result.append({"id": t.id, "name": t.name, "constituency": t.constituency, "cases": case_count})
        return {"tenants": result}
    finally:
        db.close()