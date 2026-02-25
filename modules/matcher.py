"""
Fund Intelligence HQ — The MP's most powerful funding tool.
Answers: "Which ministry has money, which scheme fits, and how do I get it?"

Tabs:
1. 💰 Fund Radar — Ministry-wise budget dashboard
2. 🎯 Scheme Finder — Filter + search + AI match
3. 📋 Scheme Explorer — Detailed scheme cards
4. 📊 Ministry Overview — Analytics & charts
"""
import streamlit as st
import pandas as pd
import json
import os
import re

# ============================================================
# DATA LOADING
# ============================================================

@st.cache_data(ttl=3600)
def load_schemes_data():
    """Load and merge scheme data from all available sources."""
    schemes = []

    # Primary source: schemes_db.json (251 schemes with budgets)
    try:
        with open("schemes_db.json", "r", encoding="utf-8") as f:
            schemes = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    if not schemes:
        return pd.DataFrame()

    df = pd.DataFrame(schemes)

    # Parse budget strings to numeric (e.g., "₹60,000 Cr" → 60000)
    if "budget_allocation" in df.columns:
        df["budget_numeric"] = df["budget_allocation"].apply(_parse_budget)

    return df


@st.cache_data(ttl=3600)
def load_kaggle_data():
    """Load enrichment data from Kaggle CSV (eligibility, benefits, application)."""
    try:
        kaggle = pd.read_csv("tests/Kaggle_schemes.csv")
        return kaggle
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def _parse_budget(budget_str):
    """Parse budget string like '₹60,000 Cr' to numeric value in Crores."""
    if not budget_str or not isinstance(budget_str, str):
        return 0
    # Remove ₹, commas, and extract number
    cleaned = re.sub(r'[₹,]', '', budget_str)
    match = re.search(r'([\d.]+)', cleaned)
    if match:
        num = float(match.group(1))
        if 'lakh' in budget_str.lower() or 'L' in budget_str:
            return num / 100  # Convert lakh to crore
        return num
    return 0


def _get_ministry_summary(df):
    """Aggregate scheme data by ministry."""
    if df.empty:
        return pd.DataFrame()

    ministry_agg = df.groupby("ministry").agg(
        scheme_count=("name", "count"),
        total_budget=("budget_numeric", "sum"),
        top_scheme=("name", "first"),
        categories=("category", lambda x: ", ".join(x.dropna().unique()[:3])),
    ).reset_index()

    ministry_agg = ministry_agg.sort_values("total_budget", ascending=False)
    return ministry_agg


def _find_kaggle_match(scheme_name, kaggle_df):
    """Find matching Kaggle entry for enrichment data."""
    if kaggle_df.empty:
        return None
    # Fuzzy match: check if scheme name keywords appear in Kaggle scheme names
    keywords = scheme_name.lower().split()[:3]  # First 3 words
    for _, row in kaggle_df.iterrows():
        kaggle_name = str(row.get("scheme_name", "")).lower()
        if sum(1 for kw in keywords if kw in kaggle_name) >= 2:
            return row
    return None


# ============================================================
# MAIN RENDERER
# ============================================================

def render_matcher(username):
    """Render the Fund Intelligence HQ."""
    st.title("🏛️ Fund Intelligence HQ")
    st.caption("Every government scheme, every ministry budget, every funding opportunity — at your fingertips.")

    df = load_schemes_data()
    kaggle_df = load_kaggle_data()

    if df.empty:
        st.error("⚠️ No scheme data found. Please ensure `schemes_db.json` is present.")
        return

    # Quick stats bar
    total_schemes = len(df)
    total_ministries = df["ministry"].nunique()
    total_budget = df["budget_numeric"].sum() if "budget_numeric" in df.columns else 0

    m1, m2, m3 = st.columns(3)
    m1.metric("📋 Total Schemes", f"{total_schemes}")
    m2.metric("🏛️ Ministries Covered", f"{total_ministries}")
    m3.metric("💰 Total Allocation", f"₹{total_budget:,.0f} Cr")

    # Tabs
    tab_radar, tab_finder, tab_explorer, tab_overview = st.tabs([
        "💰 Fund Radar",
        "🎯 Scheme Finder",
        "📋 Scheme Explorer",
        "📊 Ministry Overview",
    ])

    with tab_radar:
        _render_fund_radar(df)

    with tab_finder:
        _render_scheme_finder(df, kaggle_df, username)

    with tab_explorer:
        _render_scheme_explorer(df, kaggle_df, username)

    with tab_overview:
        _render_ministry_overview(df)


# ============================================================
# TAB 1: FUND RADAR
# ============================================================

def _render_fund_radar(df):
    """Ministry-wise budget dashboard — where is the money?"""
    st.subheader("💰 Fund Radar")
    st.info("**Which ministry has the biggest budget?** Click any ministry to see its schemes.")

    ministry_summary = _get_ministry_summary(df)

    if ministry_summary.empty:
        st.warning("No ministry data available.")
        return

    # Sortable ministry table
    for _, row in ministry_summary.iterrows():
        ministry = row["ministry"]
        count = row["scheme_count"]
        budget = row["total_budget"]
        top = row["top_scheme"]

        # Heat indicator
        if budget >= 10000:
            heat = "🟢"
            heat_label = "HIGH FUNDS"
        elif budget >= 1000:
            heat = "🟡"
            heat_label = "MODERATE"
        else:
            heat = "🔴"
            heat_label = "LIMITED"

        with st.expander(
            f"{heat} **{ministry}** — ₹{budget:,.0f} Cr | {count} schemes | {heat_label}",
            expanded=False,
        ):
            # Ministry header
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Allocation", f"₹{budget:,.0f} Cr")
            c2.metric("Active Schemes", count)
            c3.metric("Top Scheme", top[:30] + "..." if len(str(top)) > 30 else top)

            # Scheme list under this ministry
            ministry_schemes = df[df["ministry"] == ministry].sort_values(
                "budget_numeric", ascending=False
            )

            for _, scheme in ministry_schemes.iterrows():
                s_budget = scheme.get("budget_allocation", "N/A")
                s_focus = scheme.get("focus", "")
                st.write(f"• **{scheme['name']}** — {s_budget} | {s_focus}")

            st.caption(f"Categories: {row['categories']}")


# ============================================================
# TAB 2: SCHEME FINDER
# ============================================================

def _render_scheme_finder(df, kaggle_df, username):
    """Filter + search + AI-powered scheme matching."""
    st.subheader("🎯 Scheme Finder")
    st.info("**Find the right scheme for any problem.** Use filters or search by keyword.")

    # Search bar
    search_query = st.text_input(
        "🔍 Search schemes",
        placeholder="e.g., water supply, farmer loan, women empowerment, road construction...",
        key="scheme_search",
    )

    # Filters
    c1, c2, c3 = st.columns(3)
    with c1:
        all_ministries = ["All"] + sorted(df["ministry"].dropna().unique().tolist())
        sel_ministry = st.selectbox("🏛️ Ministry", all_ministries, key="sf_ministry")
    with c2:
        all_categories = ["All"] + sorted(df["category"].dropna().unique().tolist())
        sel_category = st.selectbox("📂 Category", all_categories, key="sf_category")
    with c3:
        all_focus = ["All"] + sorted(df["focus"].dropna().unique().tolist())
        sel_focus = st.selectbox("🎯 Focus Area", all_focus, key="sf_focus")

    # Apply filters
    results = df.copy()
    if sel_ministry != "All":
        results = results[results["ministry"] == sel_ministry]
    if sel_category != "All":
        results = results[results["category"] == sel_category]
    if sel_focus != "All":
        results = results[results["focus"] == sel_focus]

    # Apply search
    if search_query:
        query_lower = search_query.lower()
        results = results[
            results.apply(
                lambda row: query_lower in str(row.get("name", "")).lower()
                or query_lower in str(row.get("description", "")).lower()
                or query_lower in str(row.get("focus", "")).lower()
                or query_lower in str(row.get("category", "")).lower()
                or query_lower in str(row.get("ministry", "")).lower(),
                axis=1,
            )
        ]

        # Also search Kaggle data for broader coverage
        if not kaggle_df.empty and len(results) < 5:
            kaggle_matches = kaggle_df[
                kaggle_df.apply(
                    lambda row: query_lower in str(row.get("scheme_name", "")).lower()
                    or query_lower in str(row.get("tags", "")).lower()
                    or query_lower in str(row.get("schemeCategory", "")).lower(),
                    axis=1,
                )
            ].head(10)

            if not kaggle_matches.empty:
                st.divider()
                st.caption(f"📡 Also found **{len(kaggle_matches)}** additional matches from extended database:")
                for _, km in kaggle_matches.iterrows():
                    level_badge = "🇮🇳" if km.get("level") == "Central" else "🏛️"
                    with st.expander(f"{level_badge} {km['scheme_name']} ({km.get('level', 'N/A')})"):
                        st.write(f"**Category:** {km.get('schemeCategory', 'N/A')}")
                        benefits = str(km.get("benefits", ""))
                        if benefits and benefits != "nan":
                            st.write(f"**Benefits:** {benefits[:300]}{'...' if len(benefits) > 300 else ''}")
                        eligibility = str(km.get("eligibility", ""))
                        if eligibility and eligibility != "nan":
                            st.write(f"**Eligibility:** {eligibility[:300]}{'...' if len(eligibility) > 300 else ''}")

    # Display results
    st.divider()
    results_sorted = results.sort_values("budget_numeric", ascending=False)

    if len(results_sorted) > 0:
        st.success(f"✅ Found **{len(results_sorted)}** schemes matching your criteria.")

        for _, scheme in results_sorted.iterrows():
            budget_str = scheme.get("budget_allocation", "N/A")
            with st.expander(
                f"💰 **{scheme['name']}** — {budget_str} | {scheme.get('ministry', 'N/A')}"
            ):
                c_left, c_right = st.columns([3, 1])
                with c_left:
                    st.write(f"**Description:** {scheme.get('description', 'N/A')}")
                    st.write(f"**Ministry:** {scheme.get('ministry', 'N/A')}")
                    st.write(f"**Focus:** {scheme.get('focus', 'N/A')}")
                    st.write(f"**Budget:** {budget_str}")

                    # Enrich with Kaggle data
                    kaggle_match = _find_kaggle_match(scheme["name"], kaggle_df)
                    if kaggle_match is not None:
                        st.divider()
                        st.caption("📡 Extended Information:")
                        benefits = str(kaggle_match.get("benefits", ""))
                        if benefits and benefits != "nan":
                            st.write(f"**Benefits:** {benefits[:500]}")
                        eligibility = str(kaggle_match.get("eligibility", ""))
                        if eligibility and eligibility != "nan":
                            st.write(f"**Eligibility:** {eligibility[:500]}")
                        application = str(kaggle_match.get("application", ""))
                        if application and application != "nan":
                            with st.expander("📝 How to Apply"):
                                st.write(application[:800])

                with c_right:
                    st.metric("Budget", budget_str)
                    if st.button("✉️ Draft Letter", key=f"draft_{scheme['id']}"):
                        st.session_state["prefill_drafter"] = {
                            "scheme": scheme["name"],
                            "ministry": scheme.get("ministry", ""),
                            "budget": budget_str,
                            "description": scheme.get("description", ""),
                        }
                        st.success("✅ Scheme details saved. Go to **Drafter** to generate a request letter.")
    else:
        st.warning("⚠️ No schemes found. Try different filters or a broader search term.")


# ============================================================
# TAB 3: SCHEME EXPLORER
# ============================================================

def _render_scheme_explorer(df, kaggle_df, username):
    """Browse all schemes with full details."""
    st.subheader("📋 Scheme Explorer")
    st.info("**Browse all 251 schemes** — sorted by budget. Click any scheme for full details.")

    # Quick filters
    c1, c2 = st.columns(2)
    with c1:
        sort_by = st.selectbox(
            "Sort by",
            ["Budget (Highest First)", "Budget (Lowest First)", "Name (A-Z)", "Ministry"],
            key="explorer_sort",
        )
    with c2:
        budget_min = st.slider("Minimum Budget (₹ Cr)", 0, 50000, 0, step=100, key="explorer_budget")

    # Sort
    if sort_by == "Budget (Highest First)":
        sorted_df = df.sort_values("budget_numeric", ascending=False)
    elif sort_by == "Budget (Lowest First)":
        sorted_df = df.sort_values("budget_numeric", ascending=True)
    elif sort_by == "Name (A-Z)":
        sorted_df = df.sort_values("name")
    else:
        sorted_df = df.sort_values("ministry")

    # Filter by budget
    if budget_min > 0:
        sorted_df = sorted_df[sorted_df["budget_numeric"] >= budget_min]

    st.caption(f"Showing {len(sorted_df)} schemes")

    # Paginate for performance
    page_size = 20
    total_pages = max(1, (len(sorted_df) + page_size - 1) // page_size)
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, key="explorer_page")
    page_df = sorted_df.iloc[(page - 1) * page_size : page * page_size]

    for _, scheme in page_df.iterrows():
        budget_str = scheme.get("budget_allocation", "N/A")
        budget_num = scheme.get("budget_numeric", 0)

        # Color based on budget
        if budget_num >= 10000:
            icon = "🟢"
        elif budget_num >= 1000:
            icon = "🟡"
        else:
            icon = "🔵"

        with st.expander(f"{icon} {scheme['name']} — {budget_str}"):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"**Ministry:** {scheme.get('ministry', 'N/A')}")
                st.markdown(f"**Description:** {scheme.get('description', 'N/A')}")
                st.markdown(f"**Focus:** {scheme.get('focus', 'N/A')}")
                st.markdown(f"**Category:** {scheme.get('category', 'N/A')}")

                # Kaggle enrichment
                kaggle_match = _find_kaggle_match(scheme["name"], kaggle_df)
                if kaggle_match is not None:
                    st.divider()
                    benefits = str(kaggle_match.get("benefits", ""))
                    if benefits and benefits != "nan":
                        st.markdown(f"**💰 Benefits:** {benefits[:400]}")
                    eligibility = str(kaggle_match.get("eligibility", ""))
                    if eligibility and eligibility != "nan":
                        st.markdown(f"**✅ Eligibility:** {eligibility[:400]}")
                    docs = str(kaggle_match.get("documents", ""))
                    if docs and docs != "nan":
                        st.markdown(f"**📄 Documents Required:** {docs[:300]}")

            with col_b:
                st.metric("Budget", budget_str)
                if st.button("✉️ Request", key=f"req_{scheme['id']}"):
                    st.session_state["prefill_drafter"] = {
                        "scheme": scheme["name"],
                        "ministry": scheme.get("ministry", ""),
                        "budget": budget_str,
                    }
                    st.success("Saved! Go to Drafter →")

    st.caption(f"Page {page} of {total_pages}")


# ============================================================
# TAB 4: MINISTRY OVERVIEW
# ============================================================

def _render_ministry_overview(df):
    """Analytics and charts for scheme data."""
    st.subheader("📊 Ministry Overview")
    st.info("**Big picture view** of government funding across all ministries.")

    # Top 10 ministries by budget
    st.markdown("##### 🏛️ Top 10 Ministries by Budget Allocation")
    ministry_summary = _get_ministry_summary(df)

    if not ministry_summary.empty:
        top_10 = ministry_summary.head(10)
        # Create a horizontal bar chart using st.bar_chart
        chart_data = top_10.set_index("ministry")["total_budget"]
        chart_data.index = [m.replace("Ministry of ", "").replace("Ministry for ", "")[:25] for m in chart_data.index]
        st.bar_chart(chart_data, horizontal=True)

    st.divider()

    # Category distribution
    st.markdown("##### 📂 Schemes by Category")
    if "category" in df.columns:
        cat_counts = df["category"].value_counts()
        c1, c2 = st.columns([2, 1])
        with c1:
            st.bar_chart(cat_counts)
        with c2:
            st.dataframe(
                cat_counts.reset_index().rename(columns={"index": "Category", "category": "Category", "count": "Schemes"}),
                use_container_width=True,
            )

    st.divider()

    # Top 10 highest budget schemes
    st.markdown("##### 💰 Top 10 Highest-Budget Schemes")
    top_schemes = df.nlargest(10, "budget_numeric")[["name", "ministry", "budget_allocation", "budget_numeric"]]
    top_schemes = top_schemes.reset_index(drop=True)
    top_schemes.index += 1
    top_schemes.columns = ["Scheme", "Ministry", "Budget", "₹ Cr"]
    st.dataframe(top_schemes, use_container_width=True)

    st.divider()

    # Focus area distribution
    st.markdown("##### 🎯 Schemes by Focus Area")
    if "focus" in df.columns:
        focus_counts = df["focus"].value_counts().head(15)
        st.bar_chart(focus_counts)

    # Summary stats
    st.divider()
    st.markdown("##### 📈 Summary Statistics")
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total Schemes", len(df))
    s2.metric("Ministries", df["ministry"].nunique())
    s3.metric("Categories", df["category"].nunique() if "category" in df.columns else "N/A")
    s4.metric("Total Budget", f"₹{df['budget_numeric'].sum():,.0f} Cr")