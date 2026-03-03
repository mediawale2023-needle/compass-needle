"""
Fund Intelligence Treemap — Streamlit Module
Visualizes ministry-wise fund allocation vs parliamentary scrutiny
using plotly.express.treemap and st.metric.

Data source: fund_intel.json (scraped from Parliament Q&A via ePARLib)
"""
import streamlit as st
import plotly.express as px
import pandas as pd
import json
import os
import re


def parse_amount(text):
    """Convert '₹60,000 Cr' → 60000 (in crores)."""
    if not text or text in ("Check Dept", "Merged in Samagra", "Replaced by PM E-DRIVE"):
        return 0
    text = text.replace("₹", "").replace(",", "").strip()
    match = re.search(r"([\d.]+)", text)
    return float(match.group(1)) if match else 0


def load_data():
    """Load fund_intel.json and schemes.json."""
    base = os.path.dirname(os.path.dirname(__file__))

    # Fund intel from parliamentary scrape
    fund_path = os.path.join(base, "fund_intel.json")
    fund_data = {}
    if os.path.exists(fund_path):
        with open(fund_path) as f:
            fund_data = json.load(f)

    # Scheme allocations
    schemes_path = os.path.join(base, "schemes.json")
    schemes = []
    if os.path.exists(schemes_path):
        with open(schemes_path) as f:
            schemes = json.load(f)

    return fund_data, schemes


def render_fund_intel():
    """Render the Fund Intelligence dashboard."""
    st.header("Fund Intelligence")
    st.caption("Parliamentary Scrutiny of Government Funds — FY 2025-26")

    fund_data, schemes = load_data()

    if not fund_data or not fund_data.get("ministries"):
        st.error("No fund intelligence data found. Run `python scripts/scrape_fund_intel.py` first.")
        return

    ministries = fund_data["ministries"]
    metadata = fund_data.get("metadata", {})

    # ────────────────────────────────────────────
    # 1. TOP METRICS
    # ────────────────────────────────────────────
    total_qs = metadata.get("total_fund_questions", 0)
    total_ministries = len(ministries)

    # Calculate total allocation from schemes
    total_alloc = sum(parse_amount(s.get("Budget_Alloc", "")) for s in schemes)
    active_schemes = sum(1 for s in schemes if "Active" in s.get("Budget_Status", "") or "High" in s.get("Budget_Status", ""))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Fund Questions Asked", f"{total_qs}", help="Total fund-related parliamentary questions in LS 18")
    c2.metric("Ministries Under Scrutiny", f"{total_ministries}", help="Ministries questioned about fund usage")
    c3.metric("Total Budget Allocation", f"₹{total_alloc:,.0f} Cr", help="Sum of all known scheme allocations")
    c4.metric("Active Schemes", f"{active_schemes}", help="Schemes with active/high budget status")

    st.divider()

    # ────────────────────────────────────────────
    # 2. MINISTRY TREEMAP
    # ────────────────────────────────────────────
    st.subheader("Ministry-wise Parliamentary Fund Scrutiny")

    # Build treemap data from parliamentary Q&A
    treemap_rows = []
    for m in ministries:
        ministry_name = m["ministry"].title()
        q_count = m["total_questions"]
        # Find matching allocation from schemes
        alloc = 0
        for s in schemes:
            s_ministry = (s.get("Ministry") or "").upper()
            if m["ministry"].upper() in s_ministry or s_ministry in m["ministry"].upper():
                alloc += parse_amount(s.get("Budget_Alloc", ""))

        treemap_rows.append({
            "Ministry": ministry_name,
            "Parent": "All Ministries",
            "Questions": q_count,
            "Allocation (₹ Cr)": alloc if alloc > 0 else None,
            "Scrutiny Level": "High" if q_count >= 20 else "Medium" if q_count >= 10 else "Low",
        })

    df = pd.DataFrame(treemap_rows)

    # Treemap sized by question count, colored by scrutiny level
    color_map = {"High": "#e74c3c", "Medium": "#f39c12", "Low": "#27ae60"}

    fig = px.treemap(
        df,
        path=["Parent", "Ministry"],
        values="Questions",
        color="Scrutiny Level",
        color_discrete_map=color_map,
        hover_data={"Allocation (₹ Cr)": True, "Questions": True},
        title="Ministry-wise Fund Questions in Parliament (FY 2025-26)",
    )
    fig.update_layout(
        font_family="Inter, sans-serif",
        margin=dict(t=50, l=10, r=10, b=10),
        height=550,
    )
    fig.update_traces(
        textinfo="label+value",
        textfont_size=12,
        hovertemplate="<b>%{label}</b><br>Questions: %{value}<br>Allocation: ₹%{customdata[0]:,.0f} Cr<extra></extra>",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.caption("Tile size = number of fund-related questions asked | Color = scrutiny level (red = most questioned)")

    st.divider()

    # ────────────────────────────────────────────
    # 3. SCHEME ALLOCATION TREEMAP
    # ────────────────────────────────────────────
    st.subheader("Scheme-wise Budget Allocation")

    scheme_rows = []
    for s in schemes:
        alloc = parse_amount(s.get("Budget_Alloc", ""))
        if alloc > 0:
            status = s.get("Budget_Status", "")
            if "Very High" in status or "Massive" in status:
                level = "Very High"
            elif "High" in status:
                level = "High"
            elif "Stagnant" in status:
                level = "Stagnant"
            else:
                level = "Active"

            scheme_rows.append({
                "Ministry": (s.get("Ministry") or "Unknown").replace("Ministry of ", ""),
                "Scheme": s.get("Scheme", ""),
                "Allocation": alloc,
                "Status": level,
                "Grant Type": s.get("Grant", ""),
            })

    if scheme_rows:
        df_schemes = pd.DataFrame(scheme_rows)
        status_colors = {
            "Very High": "#2ecc71",
            "High": "#27ae60",
            "Active": "#3498db",
            "Stagnant": "#e67e22",
        }

        fig2 = px.treemap(
            df_schemes,
            path=["Ministry", "Scheme"],
            values="Allocation",
            color="Status",
            color_discrete_map=status_colors,
            hover_data={"Allocation": True, "Grant Type": True},
            title="Scheme Allocation Treemap (₹ Crores) — Budget 2025-26",
        )
        fig2.update_layout(
            font_family="Inter, sans-serif",
            margin=dict(t=50, l=10, r=10, b=10),
            height=550,
        )
        fig2.update_traces(
            textinfo="label+value",
            textfont_size=11,
            hovertemplate="<b>%{label}</b><br>₹%{value:,.0f} Cr<br>%{customdata[1]}<extra></extra>",
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.caption("Tile size = budget allocation | Color = budget status")

    st.divider()

    # ────────────────────────────────────────────
    # 4. TOP QUESTIONED MINISTRIES TABLE
    # ────────────────────────────────────────────
    st.subheader("Top Ministries Under Fund Scrutiny")

    sorted_ministries = sorted(ministries, key=lambda x: x["total_questions"], reverse=True)

    table_data = []
    for m in sorted_ministries[:15]:
        # Sample recent questions
        recent = sorted(m.get("questions", []), key=lambda q: q.get("date", ""), reverse=True)
        latest_q = recent[0]["title"][:60] + "..." if recent else "—"

        table_data.append({
            "Ministry": m["ministry"].title(),
            "Questions": m["total_questions"],
            "Latest Question": latest_q,
        })

    st.dataframe(
        pd.DataFrame(table_data),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Ministry": st.column_config.TextColumn("Ministry", width="medium"),
            "Questions": st.column_config.NumberColumn("Qs", width="small"),
            "Latest Question": st.column_config.TextColumn("Latest Question", width="large"),
        },
    )

    # ────────────────────────────────────────────
    # 5. METADATA FOOTER
    # ────────────────────────────────────────────
    st.divider()
    st.caption(
        f"Source: ePARLib (sansad.in) | Lok Sabha {metadata.get('lok_sabha', '18')} | "
        f"FY {metadata.get('financial_year', '2025-26')} | "
        f"Last scraped: {metadata.get('scraped_at', 'N/A')}"
    )
