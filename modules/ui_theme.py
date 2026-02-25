"""
Shared UI Theme — Parliamentary Design System.
Dynamically themed: Green for Lok Sabha, Maroon for Rajya Sabha.
Import inject_theme() at the top of every render function.
"""
import streamlit as st
import json
import os

# ============================================================
# COLOR PALETTES
# ============================================================

PALETTES = {
    "Lok Sabha": {
        "primary": "#006a4d",
        "primary_light": "#f0f7f4",
        "primary_rgb": "0, 106, 77",
    },
    "Rajya Sabha": {
        "primary": "#8d153a",
        "primary_light": "#f7f0f2",
        "primary_rgb": "141, 21, 58",
    },
}


def _get_house():
    """Read house from tenant_profile.json. Defaults to Lok Sabha."""
    try:
        with open("tenant_profile.json", "r") as f:
            return json.load(f).get("house", "Lok Sabha")
    except Exception:
        return "Lok Sabha"


def _get_palette():
    """Return the active color palette based on house."""
    house = _get_house()
    return PALETTES.get(house, PALETTES["Lok Sabha"])


def _build_css(p):
    """Build the theme CSS string for the current palette."""
    return f"""
<style>
    /* --- Page header with accent underline --- */
    .page-header {{
        border-bottom: 3px solid {p['primary']};
        padding-bottom: 10px;
        margin-bottom: 20px;
    }}
    .page-header h1 {{
        font-size: 1.5rem;
        font-weight: 600;
        color: #1a1a1a;
        letter-spacing: 0.02em;
        margin-bottom: 2px;
    }}
    .page-header p {{
        font-size: 0.82rem;
        color: #666;
        margin-top: 0;
    }}

    /* --- Section label (uppercase, small) --- */
    .section-label {{
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #888;
        margin-bottom: 6px;
        font-weight: 600;
    }}

    /* --- Status badge with accent left border --- */
    .status-badge {{
        background: #f5f5f5;
        border-left: 4px solid {p['primary']};
        padding: 10px 14px;
        border-radius: 0 4px 4px 0;
        margin-bottom: 14px;
        font-size: 0.9rem;
    }}
    .status-badge strong {{
        color: {p['primary']};
    }}

    /* --- Card container --- */
    .theme-card {{
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        padding: 16px;
        background: #fafafa;
        margin-bottom: 12px;
    }}

    /* --- Result container --- */
    .result-container {{
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        padding: 20px;
        background: #fafafa;
        line-height: 1.7;
    }}

    /* --- Chat message (user) --- */
    .chat-user {{
        background: {p['primary_light']};
        border-left: 3px solid {p['primary']};
        padding: 8px 12px;
        margin: 4px 0;
        border-radius: 0 4px 4px 0;
        font-weight: 500;
    }}

    /* --- Metric boxes --- */
    .metric-box {{
        text-align: center;
        padding: 12px;
        background: #f5f5f5;
        border-radius: 4px;
        border-top: 3px solid {p['primary']};
    }}
    .metric-box .value {{
        font-size: 1.4rem;
        font-weight: 700;
        color: {p['primary']};
    }}
    .metric-box .label {{
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #888;
        margin-top: 2px;
    }}

    /* --- News items --- */
    .news-item {{
        padding: 6px 0;
        border-bottom: 1px solid #f0f0f0;
        font-size: 0.9rem;
    }}
    .news-item a {{
        color: #1a1a1a;
        text-decoration: none;
    }}
    .news-item a:hover {{
        color: {p['primary']};
    }}

    /* --- Streamlit overrides --- */
    .block-container {{
        padding-top: 1.5rem;
    }}
    /* Tab underline color */
    .stTabs [data-baseweb="tab-highlight"] {{
        background-color: {p['primary']};
    }}
    /* Primary button */
    .stButton > button[kind="primary"] {{
        background-color: {p['primary']};
        border-color: {p['primary']};
    }}
    .stButton > button[kind="primary"]:hover {{
        background-color: {p['primary']};
        opacity: 0.9;
    }}
</style>
"""


def inject_theme():
    """Call once at the top of every render function. Picks Lok Sabha or Rajya Sabha palette."""
    p = _get_palette()
    st.markdown(_build_css(p), unsafe_allow_html=True)


def page_header(title, subtitle=""):
    """Render a page header with accent underline."""
    sub_html = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(f"""
    <div class="page-header">
        <h1>{title}</h1>
        {sub_html}
    </div>
    """, unsafe_allow_html=True)


def section_label(text):
    """Render an uppercase section label."""
    st.markdown(f'<p class="section-label">{text}</p>', unsafe_allow_html=True)


def status_badge(text):
    """Render an accent left-border status badge."""
    st.markdown(f'<div class="status-badge">{text}</div>', unsafe_allow_html=True)


def metric_box(value, label):
    """Render a clean metric card."""
    st.markdown(f"""
    <div class="metric-box">
        <div class="value">{value}</div>
        <div class="label">{label}</div>
    </div>
    """, unsafe_allow_html=True)


def get_primary_color():
    """Return the current primary color hex for use in charts, etc."""
    return _get_palette()["primary"]
