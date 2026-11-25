"""
News Intel — Constituency-Aware News Engine.

Fetches news from Google News RSS and ranks/filters by relevance
to the MP's constituency, state, and key issues.
"""
import feedparser
import time
import socket


class _StubSt:
    @staticmethod
    def cache_data(ttl=0):
        def decorator(func):
            return func
        return decorator


# This module is used by FastAPI. Keep caching a no-op here to avoid Streamlit
# runtime warnings in the backend process.
st = _StubSt()

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import urllib.parse
import json
import os
import re

from modules.profile_loader import load_tenant_profile


NATIONAL_MEDIA_TERMS = [
    "ANI",
    "PTI",
    "NDTV",
    "India Today",
    "The Hindu",
    "Indian Express",
    "Hindustan Times",
    "Times of India",
    "News18",
]

LOCAL_DIGITAL_TERMS = [
    "news",
    "live",
    "digital",
    "media",
    "channel",
    "updates",
]

LOCAL_MEDIA_BY_STATE = {
    "karnataka": [
        "Public TV",
        "TV9 Kannada",
        "Vijay Karnataka",
        "Prajavani",
        "Udayavani",
        "Kannada Prabha",
        "Deccan Herald",
    ],
    "maharashtra": [
        "ABP Majha",
        "TV9 Marathi",
        "Lokmat",
        "Sakal",
        "Loksatta",
        "Maharashtra Times",
    ],
    "uttar pradesh": [
        "Amar Ujala",
        "Dainik Jagran",
        "Hindustan",
        "News18 Uttar Pradesh",
        "ABP Ganga",
    ],
    "delhi": [
        "Delhi",
        "Hindustan Times Delhi",
        "Indian Express Delhi",
        "Times of India Delhi",
    ],
}

LOCAL_LANGUAGES_BY_STATE = {
    "andhra pradesh": ["English", "Telugu", "Hindi"],
    "assam": ["English", "Assamese", "Hindi"],
    "bihar": ["English", "Hindi"],
    "delhi": ["English", "Hindi"],
    "gujarat": ["English", "Gujarati", "Hindi"],
    "haryana": ["English", "Hindi", "Punjabi"],
    "jammu and kashmir": ["English", "Hindi", "Urdu"],
    "karnataka": ["English", "Kannada", "Marathi", "Hindi"],
    "kerala": ["English", "Malayalam"],
    "madhya pradesh": ["English", "Hindi"],
    "maharashtra": ["English", "Marathi", "Hindi"],
    "odisha": ["English", "Odia", "Hindi"],
    "punjab": ["English", "Punjabi", "Hindi"],
    "rajasthan": ["English", "Hindi"],
    "tamil nadu": ["English", "Tamil"],
    "telangana": ["English", "Telugu", "Urdu", "Hindi"],
    "uttar pradesh": ["English", "Hindi", "Urdu"],
    "west bengal": ["English", "Bengali", "Hindi"],
}


# ============================================================
# CONSTITUENCY CONTEXT
# ============================================================

@st.cache_data(ttl=3600)
def _load_constituency_context(tenant_id=None):
    """Load MP profile to build constituency-aware search terms."""
    profile = load_tenant_profile(tenant_id)

    constituency = profile.get("constituency", "")
    state = profile.get("state", "")
    mp_name = profile.get("mp_name", "")
    key_facts = profile.get("key_facts", [])

    # Build a set of location keywords for relevance scoring
    location_keywords = set()
    if constituency:
        location_keywords.add(constituency.lower())

    # Add alt_names from profile (e.g. Belagavi/Belgaum)
    for alt in profile.get("alt_names", []):
        location_keywords.add(alt.lower())

    if state:
        location_keywords.add(state.lower())
    if mp_name:
        # Add last name for matching
        parts = mp_name.split()
        if parts:
            location_keywords.add(parts[-1].lower())
            location_keywords.add(mp_name.lower())

    # Extract keywords from key_facts
    fact_keywords = set()
    for fact in key_facts:
        # Pull out proper nouns and significant terms
        words = re.findall(r'[A-Z][a-z]+(?:\s[A-Z][a-z]+)*', fact)
        for w in words:
            if len(w) > 3:
                fact_keywords.add(w.lower())

    return {
        "constituency": constituency,
        "state": state,
        "mp_name": mp_name,
        "key_facts": key_facts,
        "languages": profile.get("languages", []),
        "location_keywords": location_keywords,
        "fact_keywords": fact_keywords,
        "alt_names": profile.get("alt_names", []),
    }


def _state_media_terms(state):
    return LOCAL_MEDIA_BY_STATE.get((state or "").strip().lower(), [])


def _local_feed_languages(context):
    profile_languages = [lang for lang in context.get("languages", []) if lang]
    fallback_languages = LOCAL_LANGUAGES_BY_STATE.get((context.get("state") or "").strip().lower(), ["English", "Hindi"])

    languages = []
    for lang in [*profile_languages, *fallback_languages]:
        if lang not in languages:
            languages.append(lang)
    return languages[:4]


def _unique_nonempty(items):
    seen = set()
    ordered = []
    for item in items:
        value = (item or "").strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(value)
    return ordered


def _build_place_variants(context):
    return _unique_nonempty([
        context.get("constituency", ""),
        *context.get("alt_names", []),
    ])[:4]


def _build_local_queries(context):
    constituency = context.get("constituency", "")
    state = context.get("state", "")
    mp_name = context.get("mp_name", "")
    place_variants = _build_place_variants(context)
    place_query = " OR ".join(f'"{name}"' for name in place_variants[:3])
    media_query = " OR ".join(f'"{term}"' for term in _unique_nonempty([
        *_state_media_terms(state),
        *LOCAL_DIGITAL_TERMS,
    ])[:8])

    queries = []
    if place_query and media_query:
        queries.append(f'({place_query}) ({media_query})')
    if place_query and state:
        queries.append(f'({place_query}) "{state}" news')
    if constituency:
        queries.append(f'"{constituency}" latest')
        queries.append(f'"{constituency}" local news')
    if mp_name and constituency:
        queries.append(f'"{mp_name}" "{constituency}"')
    if mp_name and place_query:
        queries.append(f'"{mp_name}" ({place_query})')

    return _unique_nonempty(queries)[:6]


def _as_naive_utc(value):
    if value is None:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _serialize_article_dates(items):
    for item in items:
        published = item.get("published")
        if hasattr(published, "isoformat"):
            item["published"] = _as_naive_utc(published).isoformat()
    return items


def _dedupe_and_rank(items, context, limit, max_age_days=None):
    seen_titles = set()
    ranked = []
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=max_age_days) if max_age_days else None
    for item in items:
        title_key = re.sub(r"\s+", " ", item.get("title", "").lower()).strip()[:90]
        if not title_key or title_key in seen_titles:
            continue
        published = _as_naive_utc(item.get("published"))
        if cutoff and published < cutoff:
            continue
        item["published"] = published
        seen_titles.add(title_key)
        item["relevance"] = _score_relevance(item.get("title", ""), context)
        item["sentiment"] = analyze_sentiment(item.get("title", ""))
        ranked.append(item)

    ranked.sort(key=lambda x: x.get("published"), reverse=True)
    return _serialize_article_dates(ranked[:limit])


def get_language_code(lang_name):
    """Maps readable language names to Google News codes."""
    codes = {
        "English": "en-IN",
        "Hindi": "hi",
        "Marathi": "mr",
        "Kannada": "kn",
        "Tamil": "ta",
        "Telugu": "te",
        "Malayalam": "ml",
        "Bengali": "bn",
        "Gujarati": "gu",
        "Punjabi": "pa",
        "Urdu": "ur",
        "Odia": "or",
        "Oriya": "or",
        "Assamese": "as",
    }
    return codes.get(lang_name, "en-IN")


# ============================================================
# NEWS FETCHING
# ============================================================

def _fetch_rss(query, language="English", limit=10):
    """Raw RSS fetch from Google News with a 3-second timeout."""
    lang_code = get_language_code(language)
    encoded_query = urllib.parse.quote(query)
    ceid = f"IN:{lang_code}" if lang_code != "en-IN" else "IN:en"
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl={lang_code}&gl=IN&ceid={ceid}"

    old_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(3)  # 3-second hard timeout for RSS fetch
        feed = feedparser.parse(rss_url)
        items = []
        for entry in feed.entries[:limit]:
            try:
                pub_date = _as_naive_utc(parsedate_to_datetime(entry.published))
            except Exception:
                pub_date = datetime.now(timezone.utc).replace(tzinfo=None)

            items.append({
                "title": entry.title,
                "link": entry.link,
                "source": entry.source.title if hasattr(entry, 'source') and hasattr(entry.source, 'title') else "News",
                "published": pub_date,
            })
        return items
    except Exception:
        return []
    finally:
        socket.setdefaulttimeout(old_timeout)


def _score_relevance(title, context):
    """Score a news headline by constituency relevance (0-100)."""
    title_lower = title.lower()
    score = 0

    # Direct constituency/state mention = highest relevance
    for kw in context["location_keywords"]:
        if kw in title_lower:
            score += 50
            break # One match is enough

    # MP name mentioned
    if context["mp_name"] and context["mp_name"].lower() in title_lower:
        score += 40

    # Key facts keywords (VTU, Suvarna, sugarcane, etc.)
    for kw in context["fact_keywords"]:
        if kw in title_lower:
            score += 20
            break

    # Issue keywords relevant to governance
    governance_keywords = [
        "infrastructure", "water", "road", "railway", "hospital", "school",
        "scheme", "fund", "budget", "development", "project", "inaugurat",
        "sanction", "approv", "grant", "mp ", "lok sabha", "parliament",
    ]
    for gk in governance_keywords:
        if gk in title_lower:
            score += 10
            break

    return min(score, 100)


def analyze_sentiment(text):
    """Simple keyword sentiment analysis."""
    positive = ["launch", "inaugurate", "win", "growth", "approve", "sanction",
                "success", "fund", "develop", "open", "boost", "record"]
    negative = ["protest", "crisis", "fail", "scam", "delay", "accident",
                "shortage", "attack", "flood", "drought", "death", "arrest"]

    text_lower = text.lower()
    if any(word in text_lower for word in positive):
        return "pos"
    elif any(word in text_lower for word in negative):
        return "neg"
    return "neu"


# ============================================================
# PUBLIC API
# ============================================================

@st.cache_data(ttl=900)
def fetch_news(query, language="English", limit=5):
    """
    Backward-compatible fetch. Used by dashboard for general queries.
    """
    return _fetch_rss(query, language, limit)


@st.cache_data(ttl=900)
def fetch_tenant_media_news(tenant_id=None, news_type="national", language="English", limit=8):
    """
    Tenant-scoped media feed.

    national: national channels/newspapers mentioning the MP or constituency.
    local: local/regional channels/newspapers mentioning the constituency/MP.
    """
    context = _load_constituency_context(tenant_id)
    constituency = context["constituency"]
    state = context["state"]
    mp_name = context["mp_name"]
    alt_names = _build_place_variants(context)

    if not constituency and not mp_name:
        return []

    media_terms = NATIONAL_MEDIA_TERMS if news_type == "national" else _state_media_terms(state)
    if not media_terms and news_type == "local":
        media_terms = [state] if state else []

    place_query = " OR ".join(f'"{name}"' for name in alt_names[:3])
    media_query = " OR ".join(f'"{term}"' for term in media_terms[:7] if term)

    queries = []
    if mp_name:
        if media_query:
            queries.append(f'"{mp_name}" ({media_query})')
        queries.append(f'"{mp_name}" "{constituency}"')
    if place_query:
        if media_query:
            queries.append(f'({place_query}) ({media_query})')
        queries.append(f'({place_query}) "{state}" news')

    all_items = []
    start_time = time.time()
    for q in queries[:4]:
        if time.time() - start_time > 7:
            break
        all_items.extend(_fetch_rss(q, language, limit=6))

    if news_type == "local":
        local_queries = _build_local_queries(context)
        for lang in _local_feed_languages(context):
            for q in local_queries:
                if time.time() - start_time > 10:
                    break
                all_items.extend(_fetch_rss(q, lang, limit=5))
            if time.time() - start_time > 10:
                break

    max_age_days = 10 if news_type == "local" else None
    return _dedupe_and_rank(all_items, context, limit, max_age_days=max_age_days)


@st.cache_data(ttl=900)
def fetch_constituency_news(tenant_id=None, language="English", limit=10):
    """
    Fetch LOCAL news about the MP and constituency — from local newspapers,
    regional TV channels, and digital media. Not generic national results.
    """
    context = _load_constituency_context(tenant_id)
    constituency = context["constituency"]
    state = context["state"]
    mp_name = context["mp_name"]
    languages = context.get("languages", [])

    if not constituency:
        return []

    # Alternate spellings for broader local coverage
    alt_names = [constituency]
    for alt in context.get("alt_names", []):
        if alt.lower() != constituency.lower():
            alt_names.append(alt)

    # Queries targeting LOCAL media and regional coverage — limit to 3 total
    queries = []
    queries.append(f'"{constituency}" news today')
    if mp_name:
        queries.append(f'"{mp_name}" "{constituency}"')
    queries.append(f'"{constituency}" latest')

    # Fetch with a time budget of 6 seconds total
    all_items = []
    seen_titles = set()
    start_time = time.time()
    TIME_BUDGET = 6  # seconds — hard cap for entire function

    # English queries
    for q in queries:
        if time.time() - start_time > TIME_BUDGET:
            break
        items = _fetch_rss(q, "English", limit=6)
        for item in items:
            title_key = item["title"][:50].lower()
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                item["relevance"] = _score_relevance(item["title"], context)
                item["sentiment"] = analyze_sentiment(item["title"])
                all_items.append(item)

    # Local language queries — only if we have time left
    local_langs = [l for l in languages if l != "English"] if languages else []
    for lang in local_langs[:1]:  # Max 1 local language
        if time.time() - start_time > TIME_BUDGET:
            break
        lang_items = _fetch_rss(f"{constituency}", lang, limit=5)
        for item in lang_items:
            title_key = item["title"][:50].lower()
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                item["relevance"] = _score_relevance(item["title"], context)
                item["sentiment"] = analyze_sentiment(item["title"])
                item["source"] = item.get("source", "") + f" ({lang})"
                all_items.append(item)

    # Sort: latest first (date descending)
    all_items.sort(key=lambda x: x["published"], reverse=True)

    return all_items[:limit]


@st.cache_data(ttl=900)
def fetch_categorized_news(tenant_id=None, language="English"):
    """
    Fetch news organized into constituency-relevant categories.
    Returns dict with categories as keys.
    """
    context = _load_constituency_context(tenant_id)
    constituency = context["constituency"]
    state = context["state"]

    if not constituency:
        return {}

    categories = {
        " Constituency": f"{constituency} {state}",
        " Development": f"{constituency} development infrastructure project",
        " Parliament": f"parliament lok sabha {state}",
        " Budget & Schemes": f"government scheme fund {state}",
    }

    result = {}
    for label, query in categories.items():
        items = _fetch_rss(query, language, limit=5)
        # Score and sort
        for item in items:
            item["relevance"] = _score_relevance(item["title"], context)
            item["sentiment"] = analyze_sentiment(item["title"])
        items.sort(key=lambda x: x["relevance"], reverse=True)
        result[label] = items

    return result


# ============================================================
# LOCAL SIGNALS (staff Overview) — constituency news, cached
# ============================================================
# Renamed Indian cities: news uses both spellings, so search both.
_CITY_ALIASES = [
    {"belgaum", "belagavi"}, {"bangalore", "bengaluru"}, {"mysore", "mysuru"}, {"hubli", "hubballi"},
    {"gulbarga", "kalaburagi"}, {"bellary", "ballari"}, {"bijapur", "vijayapura"}, {"shimoga", "shivamogga"},
    {"mangalore", "mangaluru"}, {"tumkur", "tumakuru"}, {"bombay", "mumbai"}, {"poona", "pune"},
    {"gurgaon", "gurugram"}, {"allahabad", "prayagraj"}, {"calcutta", "kolkata"}, {"madras", "chennai"},
    {"trivandrum", "thiruvananthapuram"}, {"baroda", "vadodara"}, {"aurangabad", "chhatrapati sambhajinagar"},
]
# Seat-name suffixes that are not part of the city ("Belgaum Dakshin" -> "Belgaum").
_SEAT_SUFFIXES = {
    "dakshin", "uttar", "north", "south", "east", "west", "central", "rural", "city", "urban",
    "cantonment", "cantt", "purva", "paschim", "madhya", "gramin", "nagar",
}
LOCAL_SIGNAL_TTL_SECONDS = 30 * 60
LOCAL_SIGNAL_EMPTY_TTL_SECONDS = 5 * 60
LOCAL_SIGNAL_BUDGET_SECONDS = 8.0
_LOCAL_SIGNAL_CACHE: dict = {}
_USER_AGENT = "Mozilla/5.0 (compatible; NeedleLocalDesk/1.0)"


def _title_case(value: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in value.split())


def _city_variants(*names: str) -> list[str]:
    """Constituency / seat names -> the city names news actually uses (both spellings)."""
    out = []
    for name in names:
        words = [w for w in re.split(r"[\s\-]+", (name or "").strip()) if w]
        while words and words[-1].lower() in _SEAT_SUFFIXES:
            words = words[:-1]
        base = " ".join(words).strip()
        if not base:
            continue
        out.append(_title_case(base))
        for group in _CITY_ALIASES:
            if base.lower() in group:
                out.extend(_title_case(v) for v in sorted(group - {base.lower()}))
    return _unique_nonempty(out)


def _local_signal_context(tenant_id) -> dict:
    """Place terms for one tenant, from its own records (never the legacy profile file)."""
    from core.db_helpers import _q

    ctx = {"constituency": "", "leader": "", "state": "", "cities": [], "localities": []}
    try:
        trow = _q("SELECT name, constituency, seat_type FROM tenants WHERE id = :tid", {"tid": int(tenant_id)})
    except Exception:
        trow = []
    if not trow:
        return ctx
    t = trow[0]
    constituency = (t.get("constituency") or "").strip()
    ctx["constituency"] = constituency
    ctx["leader"] = (t.get("name") or "").strip()
    try:
        prof = _q("SELECT state, mp_name FROM tenant_profiles WHERE tenant_id = :tid", {"tid": int(tenant_id)})
    except Exception:
        prof = []
    if prof:
        ctx["state"] = (prof[0].get("state") or "").strip()
        ctx["leader"] = (prof[0].get("mp_name") or ctx["leader"]).strip()
    parent = ""
    try:
        pc = _q(
            "SELECT parliamentary_constituency AS pc FROM geo_places WHERE seat_name = :sn AND status != 'deprecated' "
            "AND parliamentary_constituency IS NOT NULL LIMIT 1", {"sn": constituency})
        parent = (pc[0].get("pc") or "") if pc else ""
    except Exception:
        parent = ""
    ctx["cities"] = _city_variants(constituency, parent)
    try:
        rows = _q(
            "SELECT NULLIF(TRIM(CAST(case_metadata->>'matched_value' AS TEXT)), '') AS loc, COUNT(*) AS n FROM cases "
            "WHERE tenant_id = :tid AND COALESCE(is_deleted, FALSE) = FALSE AND created_at >= :since GROUP BY 1",
            {"tid": int(tenant_id), "since": datetime.utcnow() - timedelta(days=90)})
        locs = sorted(((r["loc"], int(r["n"] or 0)) for r in rows if r.get("loc")), key=lambda kv: (-kv[1], kv[0]))
        city_l = {c.lower() for c in ctx["cities"]}
        ctx["localities"] = [l for l, _ in locs if l.lower() not in city_l and len(l) >= 4][:6]
    except Exception:
        ctx["localities"] = []
    return ctx


def _local_signal_queries(ctx: dict) -> list[tuple[str, str]]:
    cities = ctx["cities"][:2]
    city_q = " OR ".join(f'"{c}"' for c in cities)
    queries: list[tuple[str, str]] = []
    if ctx["constituency"]:
        queries.append((f'"{ctx["constituency"]}"', "English"))
    if city_q and ctx["localities"]:
        locs = " OR ".join(f'"{l}"' for l in ctx["localities"][:4])
        queries.append((f"({city_q}) ({locs})", "English"))
    if city_q:
        queries.append((f"({city_q}) (road OR water OR police OR corporation OR MLA OR protest)", "English"))
        media = _state_media_terms(ctx["state"])[:4]
        if media:
            queries.append((f"({city_q}) (" + " OR ".join(f'"{m}"' for m in media) + ")", "English"))
    leader = ctx["leader"]
    if leader and len(leader.split()) >= 2 and city_q:
        queries.append((f'"{leader}" ({city_q})', "English"))
    for lang in LOCAL_LANGUAGES_BY_STATE.get(ctx["state"].lower(), [])[1:2]:
        if city_q:
            queries.append((f"({city_q})", lang))
    return queries[:6]


def _fetch_rss_timed(query: str, language: str, limit: int, timeout: float) -> list[dict]:
    """Thread-safe RSS fetch (per-request timeout; no process-wide socket timeout)."""
    import requests

    lang_code = get_language_code(language)
    ceid = f"IN:{lang_code}" if lang_code != "en-IN" else "IN:en"
    url = (f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl={lang_code}&gl=IN&ceid={ceid}")
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": _USER_AGENT})
        if resp.status_code != 200:
            return []
        feed = feedparser.parse(resp.content)
    except Exception:
        return []
    items = []
    for entry in feed.entries[:limit]:
        try:
            pub = _as_naive_utc(parsedate_to_datetime(entry.published))
        except Exception:
            continue  # undated items can't be placed in time; skip rather than pretend they're new
        source = entry.source.title if hasattr(entry, "source") and hasattr(entry.source, "title") else "News"
        title = re.sub(rf"\s+-\s+{re.escape(source)}\s*$", "", entry.title or "").strip()
        items.append({"title": title, "link": entry.link, "source": source, "published": pub})
    return items


def _mentions_place(title: str, ctx: dict) -> bool:
    low = title.lower()
    terms = [ctx["constituency"], *ctx["cities"], *ctx["localities"]]
    if ctx["leader"] and len(ctx["leader"].split()) >= 2:
        terms.append(ctx["leader"])
    return any(t and t.lower() in low for t in terms)


def fetch_local_signals(tenant_id, limit: int = 8, now: datetime | None = None) -> list[dict]:
    """Recent local news about the tenant's constituency, its city and its busiest localities.

    Queries run in parallel within a fixed time budget; results must name a local place;
    newest first. Cached per tenant in-process (30 min, or 5 min when nothing was found).
    """
    from concurrent.futures import ThreadPoolExecutor, wait

    now = now or datetime.utcnow()
    key = int(tenant_id) if tenant_id is not None else None
    hit = _LOCAL_SIGNAL_CACHE.get(key)
    if hit and hit[0] > time.time():
        return [dict(a) for a in hit[1]][:limit]

    ctx = _local_signal_context(tenant_id) if key is not None else None
    if not ctx or not (ctx["constituency"] or ctx["cities"]):
        return []
    queries = _local_signal_queries(ctx)
    items: list[dict] = []
    pool = ThreadPoolExecutor(max_workers=max(1, len(queries)))
    try:
        futures = [pool.submit(_fetch_rss_timed, q, lang, 10, 5.0) for q, lang in queries]
        done, _ = wait(futures, timeout=LOCAL_SIGNAL_BUDGET_SECONDS)
        for f in done:
            try:
                items.extend(f.result())
            except Exception:
                pass
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    relevant = [i for i in items if _mentions_place(i["title"], ctx)]
    out: list[dict] = []
    for max_age in (14, 30):
        cutoff = now - timedelta(days=max_age)
        seen = set()
        out = []
        for it in sorted(relevant, key=lambda x: x["published"], reverse=True):
            k = re.sub(r"\W+", " ", it["title"].lower()).strip()[:80]
            if it["published"] < cutoff or k in seen:
                continue
            seen.add(k)
            out.append(it)
        if len(out) >= 3:
            break
    result = _serialize_article_dates([dict(a) for a in out[:limit]])
    ttl = LOCAL_SIGNAL_TTL_SECONDS if result else LOCAL_SIGNAL_EMPTY_TTL_SECONDS
    _LOCAL_SIGNAL_CACHE[key] = (time.time() + ttl, result)
    return [dict(a) for a in result]
