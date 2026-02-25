"""
Shared UI Theme — Parliamentary Design System.
Import inject_theme() at the top of every render function.
Based on sansad.in design language.
"""
import streamlit as st

# Emerald green from sansad.in
PRIMARY = "#006a4d"
PRIMARY_LIGHT = "#f0f7f4"
TEXT_DARK = "#1a1a1a"
TEXT_MUTED = "#666"
BG_SECONDARY = "#f5f5f5"
BORDER = "#e0e0e0"

THEME_CSS = """
<style>
    /* --- Page header with green underline --- */
    .page-header {
        border-bottom: 3px solid #006a4d;
        padding-bottom: 10px;
        margin-bottom: 20px;
    }
    .page-header h1 {
        font-size: 1.5rem;
        font-weight: 600;
        color: #1a1a1a;
        letter-spacing: 0.02em;
        margin-bottom: 2px;
    }
    .page-header p {
        font-size: 0.82rem;
        color: #666;
        margin-top: 0;
    }

    /* --- Section label (uppercase, small) --- */
    .section-label {
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #888;
        margin-bottom: 6px;
        font-weight: 600;
    }

    /* --- Status badge with green left border --- */
    .status-badge {
        background: #f5f5f5;
        border-left: 4px solid #006a4d;
        padding: 10px 14px;
        border-radius: 0 4px 4px 0;
        margin-bottom: 14px;
        font-size: 0.9rem;
    }
    .status-badge strong {
        color: #006a4d;
    }

    /* --- Card container --- */
    .theme-card {
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        padding: 16px;
        background: #fafafa;
        margin-bottom: 12px;
    }

    /* --- Result container --- */
    .result-container {
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        padding: 20px;
        background: #fafafa;
        line-height: 1.7;
    }

    /* --- Chat message (user) --- */
    .chat-user {
        background: #f0f7f4;
        border-left: 3px solid #006a4d;
        padding: 8px 12px;
        margin: 4px 0;
        border-radius: 0 4px 4px 0;
        font-weight: 500;
    }

    /* --- Clean metric boxes --- */
    .metric-box {
        text-align: center;
        padding: 12px;
        background: #f5f5f5;
        border-radius: 4px;
        border-top: 3px solid #006a4d;
    }
    .metric-box .value {
        font-size: 1.4rem;
        font-weight: 700;
        color: #006a4d;
    }
    .metric-box .label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #888;
        margin-top: 2px;
    }

    /* --- News items --- */
    .news-item {
        padding: 6px 0;
        border-bottom: 1px solid #f0f0f0;
        font-size: 0.9rem;
    }
    .news-item a {
        color: #1a1a1a;
        text-decoration: none;
    }
    .news-item a:hover {
        color: #006a4d;
    }

    /* --- Table styling --- */
    .dataframe {
        font-size: 0.85rem;
    }

    /* --- Remove default streamlit footer padding --- */
    .block-container {
        padding-top: 1.5rem;
    }
</style>
"""


def inject_theme():
    """Call this once at the top of every render function."""
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def page_header(title, subtitle=""):
    """Render a page header with green underline."""
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
    """Render a green left-border status badge."""
    st.markdown(f'<div class="status-badge">{text}</div>', unsafe_allow_html=True)


def metric_box(value, label):
    """Render a clean metric card."""
    st.markdown(f"""
    <div class="metric-box">
        <div class="value">{value}</div>
        <div class="label">{label}</div>
    </div>
    """, unsafe_allow_html=True)
