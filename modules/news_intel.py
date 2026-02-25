"""
News Intel — Constituency-Aware News Engine.

Fetches news from Google News RSS and ranks/filters by relevance
to the MP's constituency, state, and key issues.
"""
import feedparser
import streamlit as st
from datetime import datetime
from email.utils import parsedate_to_datetime
import urllib.parse
import json
import os
import re


# ============================================================
# CONSTITUENCY CONTEXT
# ============================================================

@st.cache_data(ttl=3600)
def _load_constituency_context():
    """Load MP profile to build constituency-aware search terms."""
    try:
        with open("tenant_profile.json", "r", encoding="utf-8") as f:
            profile = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        profile = {}

    constituency = profile.get("constituency", "")
    state = profile.get("state", "")
    mp_name = profile.get("mp_name", "")
    key_facts = profile.get("key_facts", [])

    # Build a set of location keywords for relevance scoring
    location_keywords = set()
    if constituency:
        location_keywords.add(constituency.lower())
        # Handle alternative spellings (Belagavi/Belgaum)
        if constituency.lower() == "belagavi":
            location_keywords.add("belgaum")
        elif constituency.lower() == "belgaum":
            location_keywords.add("belagavi")
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
        "location_keywords": location_keywords,
        "fact_keywords": fact_keywords,
    }


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
    """Raw RSS fetch from Google News."""
    lang_code = get_language_code(language)
    encoded_query = urllib.parse.quote(query)
    ceid = f"IN:{lang_code}" if lang_code != "en-IN" else "IN:en"
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl={lang_code}&gl=IN&ceid={ceid}"

    try:
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


def _score_relevance(title, context):
    """Score a news headline by constituency relevance (0-100)."""
    title_lower = title.lower()
    score = 0

    # Direct constituency/state mention = highest relevance
    for kw in context["location_keywords"]:
        if kw in title_lower:
            score += 50
            break  # One match is enough

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
def fetch_constituency_news(language="English", limit=10):
    """
    Fetch news specifically for the MP's constituency.
    Runs multiple targeted queries and merges + deduplicates results.
    """
    context = _load_constituency_context()
    constituency = context["constituency"]
    state = context["state"]
    mp_name = context["mp_name"]

    if not constituency:
        return []

    # Multiple targeted queries for broader coverage
    queries = [
        f"{constituency} {state}",                    # "Belagavi Karnataka"
        f"{constituency} development project",        # Development news
        f"{constituency} MP",                         # MP-related news
        f"{state} government scheme",                 # State scheme news
    ]
    if mp_name:
        queries.append(mp_name)                       # MP by name

    # Fetch from all queries
    all_items = []
    seen_titles = set()

    for q in queries:
        items = _fetch_rss(q, language, limit=8)
        for item in items:
            # Deduplicate by title similarity
            title_key = item["title"][:50].lower()
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                item["relevance"] = _score_relevance(item["title"], context)
                item["sentiment"] = analyze_sentiment(item["title"])
                all_items.append(item)

    # Sort by relevance (highest first), then by date
    all_items.sort(key=lambda x: (x["relevance"], x["published"]), reverse=True)

    return all_items[:limit]


@st.cache_data(ttl=900)
def fetch_categorized_news(language="English"):
    """
    Fetch news organized into constituency-relevant categories.
    Returns dict with categories as keys.
    """
    context = _load_constituency_context()
    constituency = context["constituency"]
    state = context["state"]

    if not constituency:
        return {}

    categories = {
        "🏛️ Constituency": f"{constituency} {state}",
        "🏗️ Development": f"{constituency} development infrastructure project",
        "📜 Parliament": f"parliament lok sabha {state}",
        "💰 Budget & Schemes": f"government scheme fund {state}",
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