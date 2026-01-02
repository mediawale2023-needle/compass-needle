import feedparser
import streamlit as st
from datetime import datetime
from email.utils import parsedate_to_datetime
import urllib.parse

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

# 👇 This is the function main.py is looking for!
def fetch_news(query, language="English", limit=5):
    """
    Fetches news based on Query + Language.
    """
    lang_code = get_language_code(language)
    encoded_query = urllib.parse.quote(query)
    
    # Google News RSS URL Construction
    ceid = f"IN:{lang_code}" if lang_code != "en-IN" else "IN:en"
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl={lang_code}&gl=IN&ceid={ceid}"
    
    try:
        feed = feedparser.parse(rss_url)
        news_items = []
        
        for entry in feed.entries[:limit]:
            try:
                pub_date = parsedate_to_datetime(entry.published)
            except:
                pub_date = datetime.now()
                
            news_items.append({
                "title": entry.title,
                "link": entry.link,
                "source": entry.source.title if 'source' in entry else "News",
                "published": pub_date
            })
            
        return news_items
    except Exception as e:
        return []

def analyze_sentiment(text):
    """Simple keyword sentiment analysis."""
    positive = ["launch", "inaugurate", "win", "growth", "approve", "sanction", "success"]
    negative = ["protest", "crisis", "fail", "scam", "delay", "accident", "shortage", "attack"]
    
    text_lower = text.lower()
    if any(word in text_lower for word in positive): return "pos"
    elif any(word in text_lower for word in negative): return "neg"
    return "neu"