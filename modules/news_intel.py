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

from datetime import datetime
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


def _dedupe_and_rank(items, context, limit):
    seen_titles = set()
    ranked = []
    for item in items:
        title_key = re.sub(r"\s+", " ", item.get("title", "").lower()).strip()[:90]
        if not title_key or title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        item["relevance"] = _score_relevance(item.get("title", ""), context)
        item["sentiment"] = analyze_sentiment(item.get("title", ""))
        ranked.append(item)

    ranked.sort(key=lambda x: (x.get("relevance", 0), x.get("published")), reverse=True)
    return ranked[:limit]


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
        "Gujarati": "gu"
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
                pub_date = parsedate_to_datetime(entry.published)
            except Exception:
                pub_date = datetime.now()

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
    alt_names = [constituency] + [a for a in context.get("alt_names", []) if a]
    alt_names = [a for i, a in enumerate(alt_names) if a and a.lower() not in {x.lower() for x in alt_names[:i]}]

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

    # For local feeds, try one regional language if available.
    if news_type == "local":
        local_langs = [l for l in context.get("languages", []) if l != "English"]
        if local_langs and time.time() - start_time <= 7:
            all_items.extend(_fetch_rss(constituency, local_langs[0], limit=5))

    return _dedupe_and_rank(all_items, context, limit)


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
