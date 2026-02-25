"""
Fund Intelligence HQ — The MP's most powerful funding tool.
Answers: "Which ministry has money, which scheme fits, and how do I get it?"

Tabs:
1. Fund Radar — Ministry-wise budget dashboard
2. Scheme Finder — Search + filter + detailed cards
3. Citizen Matcher — Enter citizen profile → get applicable schemes
4. Ministry Overview — Analytics & charts
"""
import streamlit as st
import pandas as pd
import json
import os
import re
from modules.ui_theme import inject_theme, page_header, section_label

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
    cleaned = re.sub(r'[₹,]', '', budget_str)
    match = re.search(r'([\d.]+)', cleaned)
    if match:
        num = float(match.group(1))
        if 'lakh' in budget_str.lower() or 'L' in budget_str:
            return num / 100
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
    keywords = scheme_name.lower().split()[:3]
    for _, row in kaggle_df.iterrows():
        kaggle_name = str(row.get("scheme_name", "")).lower()
        if sum(1 for kw in keywords if kw in kaggle_name) >= 2:
            return row
    return None


def _render_scheme_card(scheme, kaggle_df, button_prefix="s"):
    """Render a single scheme detail card (reusable component)."""
    budget_str = scheme.get("budget_allocation", "N/A")

    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.markdown(f"**Ministry:** {scheme.get('ministry', 'N/A')}")
        st.markdown(f"**Description:** {scheme.get('description', 'N/A')}")
        st.markdown(f"**Focus:** {scheme.get('focus', 'N/A')} | **Category:** {scheme.get('category', 'N/A')}")
        st.markdown(f"**Budget:** {budget_str}")

        # Kaggle enrichment
        kaggle_match = _find_kaggle_match(scheme.get("name", ""), kaggle_df)
        if kaggle_match is not None:
            st.divider()
            benefits = str(kaggle_match.get("benefits", ""))
            if benefits and benefits != "nan":
                st.markdown(f"** Benefits:** {benefits[:500]}")
            eligibility = str(kaggle_match.get("eligibility", ""))
            if eligibility and eligibility != "nan":
                st.markdown(f"** Eligibility:** {eligibility[:500]}")
            docs = str(kaggle_match.get("documents", ""))
            if docs and docs != "nan":
                st.markdown(f"** Documents:** {docs[:300]}")
            application = str(kaggle_match.get("application", ""))
            if application and application != "nan":
                with st.expander(" How to Apply"):
                    st.write(application[:800])

    with col_b:
        st.metric("Budget", budget_str)
        if st.button(" Draft Letter", key=f"{button_prefix}_{scheme.get('id', '')}"):
            st.session_state["prefill_drafter"] = {
                "scheme": scheme.get("name", ""),
                "ministry": scheme.get("ministry", ""),
                "budget": budget_str,
                "description": scheme.get("description", ""),
            }
            st.success(" Saved! Go to **Drafter** →")


# ============================================================
# CITIZEN ELIGIBILITY PROFILES
# ============================================================

CITIZEN_SCHEME_MAP = {
    "Women": [
        "Gruha Lakshmi", "Shakti", "Beti Bachao", "Udyogini", "Stand-Up India",
        "Mahila Samman", "Mahila", "Women", "Stree", "Nari",
    ],
    "Farmers": [
        "KISAN", "Fasal Bima", "Krishi", "Agriculture", "MSP", "Soil Health",
        "e-NAM", "Kisan Credit", "PM-KISAN", "Farmer",
    ],
    "SC/ST": [
        "SC/ST", "Tribal", "Scheduled", "Stand-Up India", "Adivasi",
        "Post Matric Scholarship", "Pre Matric",
    ],
    "BPL Families": [
        "Awas", "Ayushman", "Anna Bhagya", "BPL", "Ration", "PMJAY",
        "Ujjwala", "Housing", "Below Poverty",
    ],
    "Youth / Students": [
        "Yuva Nidhi", "Scholarship", "Skill", "Education", "SHRI Schools",
        "NEP", "Vidya", "Student", "Training",
    ],
    "Senior Citizens": [
        "Pension", "Senior", "Vridha", "Old Age", "Elderly",
    ],
    "Entrepreneurs / MSME": [
        "Mudra", "SVANidhi", "Vishwakarma", "MSME", "Startup", "Stand-Up",
        "Entrepreneurship", "Business",
    ],
    "Disabled / PwD": [
        "Disability", "Divyang", "PwD", "Handicapped", "Accessible",
    ],
    "Rural Residents": [
        "MGNREGA", "Gramin", "Rural", "PMGSY", "Gram Sadak", "Village",
        "Panchayat",
    ],
    "Urban Residents": [
        "AMRUT", "Smart City", "Urban", "Metro", "Municipal", "Swachh Bharat",
    ],
}


# ============================================================
# MAIN RENDERER
# ============================================================

def render_matcher(username):
    """Render the Fund Intelligence HQ."""
    inject_theme()
    page_header("Fund Intelligence HQ", "Ministry budgets, scheme search, and citizen eligibility")
    st.caption("Every government scheme, every ministry budget, every funding opportunity — at your fingertips.")

    df = load_schemes_data()
    kaggle_df = load_kaggle_data()

    if df.empty:
        st.error(" No scheme data found. Please ensure `schemes_db.json` is present.")
        return

    # Quick stats bar
    total_schemes = len(df)
    total_ministries = df["ministry"].nunique()
    total_budget = df["budget_numeric"].sum() if "budget_numeric" in df.columns else 0

    m1, m2, m3 = st.columns(3)
    m1.metric(" Total Schemes", f"{total_schemes}")
    m2.metric(" Ministries", f"{total_ministries}")
    m3.metric(" Total Allocation", f"₹{total_budget:,.0f} Cr")

    tab_overview, tab_radar, tab_finder, tab_citizen = st.tabs([
        "Ministry Overview",
        "Fund Radar",
        "Scheme Finder",
        "Citizen Matcher",
    ])

    with tab_overview:
        _render_ministry_overview(df)

    with tab_radar:
        _render_fund_radar(df)

    with tab_finder:
        _render_scheme_finder(df, kaggle_df)

    with tab_citizen:
        _render_citizen_matcher(df, kaggle_df)


# ============================================================
# TAB 1: FUND RADAR
# ============================================================

def _render_fund_radar(df):
    """Ministry-wise budget dashboard — where is the money?"""
    st.subheader("Fund Radar")
    st.info("**Which ministry has the biggest budget?** Sorted by allocation. Click any ministry to see its schemes.")

    ministry_summary = _get_ministry_summary(df)

    if ministry_summary.empty:
        st.warning("No ministry data available.")
        return

    for _, row in ministry_summary.iterrows():
        ministry = row["ministry"]
        count = row["scheme_count"]
        budget = row["total_budget"]
        top = row["top_scheme"]

        if budget >= 10000:
            heat = ""
        elif budget >= 1000:
            heat = ""
        else:
            heat = ""

        with st.expander(
            f"{heat} **{ministry}** — ₹{budget:,.0f} Cr | {count} schemes",
            expanded=False,
        ):
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Allocation", f"₹{budget:,.0f} Cr")
            c2.metric("Active Schemes", count)
            c3.metric("Flagship", top[:30] + "..." if len(str(top)) > 30 else top)

            ministry_schemes = df[df["ministry"] == ministry].sort_values(
                "budget_numeric", ascending=False
            )

            for _, scheme in ministry_schemes.iterrows():
                s_budget = scheme.get("budget_allocation", "N/A")
                s_focus = scheme.get("focus", "")
                st.write(f"• **{scheme['name']}** — {s_budget} | {s_focus}")


# ============================================================
# TAB 2: SCHEME FINDER
# ============================================================

def _render_scheme_finder(df, kaggle_df):
    """Unified search + filter + detail cards for all schemes."""
    st.subheader("Scheme Finder")
    st.info("**Search any scheme by name, keyword, or problem.** Use filters to narrow down.")

    # Search bar (prominent)
    search_query = st.text_input(
        " Search",
        placeholder="e.g., water supply, farmer loan, women empowerment, road construction...",
        key="scheme_search",
    )

    # Compact filters
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        all_ministries = ["All"] + sorted(df["ministry"].dropna().unique().tolist())
        sel_ministry = st.selectbox(" Ministry", all_ministries, key="sf_ministry")
    with c2:
        all_categories = ["All"] + sorted(df["category"].dropna().unique().tolist())
        sel_category = st.selectbox(" Category", all_categories, key="sf_category")
    with c3:
        all_focus = ["All"] + sorted(df["focus"].dropna().unique().tolist())
        sel_focus = st.selectbox(" Focus", all_focus, key="sf_focus")
    with c4:
        sort_by = st.selectbox(" Sort", ["Budget ↓", "Budget ↑", "Name A-Z"], key="sf_sort")

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
        q = search_query.lower()
        results = results[
            results.apply(
                lambda row: q in str(row.get("name", "")).lower()
                or q in str(row.get("description", "")).lower()
                or q in str(row.get("focus", "")).lower()
                or q in str(row.get("category", "")).lower()
                or q in str(row.get("ministry", "")).lower(),
                axis=1,
            )
        ]

    # Sort
    if sort_by == "Budget ↓":
        results = results.sort_values("budget_numeric", ascending=False)
    elif sort_by == "Budget ↑":
        results = results.sort_values("budget_numeric", ascending=True)
    else:
        results = results.sort_values("name")

    # Results
    st.divider()

    if len(results) > 0:
        st.success(f" **{len(results)}** schemes found.")

        # Paginate
        page_size = 15
        total_pages = max(1, (len(results) + page_size - 1) // page_size)
        if total_pages > 1:
            page = st.number_input("Page", 1, total_pages, 1, key="finder_page")
        else:
            page = 1
        page_df = results.iloc[(page - 1) * page_size : page * page_size]

        for _, scheme in page_df.iterrows():
            budget_str = scheme.get("budget_allocation", "N/A")
            budget_num = scheme.get("budget_numeric", 0)

            icon = "" if budget_num >= 10000 else "" if budget_num >= 1000 else ""

            with st.expander(f"{icon} **{scheme['name']}** — {budget_str} | {scheme.get('ministry', '')[:40]}"):
                _render_scheme_card(scheme, kaggle_df, button_prefix="find")

        if total_pages > 1:
            st.caption(f"Page {page} of {total_pages}")

        # Kaggle supplementary results for search
        if search_query and not kaggle_df.empty and len(results) < 10:
            q = search_query.lower()
            kaggle_hits = kaggle_df[
                kaggle_df.apply(
                    lambda row: q in str(row.get("scheme_name", "")).lower()
                    or q in str(row.get("tags", "")).lower()
                    or q in str(row.get("schemeCategory", "")).lower(),
                    axis=1,
                )
            ].head(10)

            if not kaggle_hits.empty:
                st.divider()
                st.markdown(f"##### {len(kaggle_hits)} more from Extended Database (3,400 schemes)")
                for _, km in kaggle_hits.iterrows():
                    badge = " Central" if km.get("level") == "Central" else " State"
                    with st.expander(f"{badge} | {km['scheme_name']}"):
                        st.write(f"**Category:** {km.get('schemeCategory', 'N/A')}")
                        for field, label in [("benefits", " Benefits"), ("eligibility", " Eligibility"), ("application", " How to Apply")]:
                            val = str(km.get(field, ""))
                            if val and val != "nan":
                                st.write(f"**{label}:** {val[:500]}")
    else:
        st.warning(" No schemes found. Try a broader search or reset filters.")


# ============================================================
# TAB 3: CITIZEN MATCHER
# ============================================================

def _render_citizen_matcher(df, kaggle_df):
    """Enter a citizen's profile → get all applicable schemes."""
    st.subheader("Citizen Eligibility Matcher")
    st.info("**Select a citizen's profile** and instantly see every scheme they qualify for.")

    # Citizen profile inputs
    c1, c2 = st.columns(2)
    with c1:
        selected_groups = st.multiselect(
            " Citizen belongs to:",
            list(CITIZEN_SCHEME_MAP.keys()),
            default=["BPL Families"],
            key="citizen_groups",
        )
    with c2:
        gender = st.radio("Gender", ["Any", "Male", "Female"], horizontal=True, key="citizen_gender")
        location = st.radio("Location", ["Any", "Rural", "Urban"], horizontal=True, key="citizen_loc")

    if not selected_groups:
        st.caption("Select at least one group to see matched schemes.")
        return

    # Build keyword list from selected groups
    all_keywords = []
    for group in selected_groups:
        all_keywords.extend(CITIZEN_SCHEME_MAP.get(group, []))

    if gender == "Female":
        all_keywords.extend(["Women", "Mahila", "Stree", "Nari", "Girl"])
    if location == "Rural":
        all_keywords.extend(["Rural", "Gramin", "Village", "Gram"])
    elif location == "Urban":
        all_keywords.extend(["Urban", "City", "Municipal", "Smart City"])

    # Match schemes
    matched = df[
        df.apply(
            lambda row: any(
                kw.lower() in str(row.get("name", "")).lower()
                or kw.lower() in str(row.get("description", "")).lower()
                or kw.lower() in str(row.get("focus", "")).lower()
                for kw in all_keywords
            ),
            axis=1,
        )
    ].sort_values("budget_numeric", ascending=False)

    # Also match from Kaggle
    kaggle_matched = pd.DataFrame()
    if not kaggle_df.empty:
        kaggle_matched = kaggle_df[
            kaggle_df.apply(
                lambda row: any(
                    kw.lower() in str(row.get("scheme_name", "")).lower()
                    or kw.lower() in str(row.get("tags", "")).lower()
                    or kw.lower() in str(row.get("schemeCategory", "")).lower()
                    for kw in all_keywords
                ),
                axis=1,
            )
        ]
        # Filter by level if location specified
        if location == "Rural":
            kaggle_matched = kaggle_matched[kaggle_matched["level"] != "Urban"]
        elif location == "Urban":
            kaggle_matched = kaggle_matched[kaggle_matched["level"] != "Rural"]

    st.divider()

    # Display profile summary
    profile_str = ", ".join(selected_groups)
    if gender != "Any":
        profile_str += f" | {gender}"
    if location != "Any":
        profile_str += f" | {location}"

    total_found = len(matched) + min(len(kaggle_matched), 15)
    st.success(f" **{total_found}** schemes found for: **{profile_str}**")

    # Primary matches (with budget data)
    if not matched.empty:
        st.markdown(f"##### Central Schemes with Budget Data ({len(matched)})")
        for _, scheme in matched.iterrows():
            budget_str = scheme.get("budget_allocation", "N/A")
            with st.expander(f" **{scheme['name']}** — {budget_str}"):
                _render_scheme_card(scheme, kaggle_df, button_prefix="cit")

    # Kaggle matches (extended database)
    if not kaggle_matched.empty:
        st.divider()
        st.markdown(f"##### Extended Matches ({len(kaggle_matched)} found, showing top 15)")
        for _, km in kaggle_matched.head(15).iterrows():
            badge = "" if km.get("level") == "Central" else ""
            with st.expander(f"{badge} {km['scheme_name']}"):
                for field, label in [
                    ("benefits", " Benefits"),
                    ("eligibility", " Eligibility"),
                    ("application", " How to Apply"),
                    ("documents", " Documents"),
                ]:
                    val = str(km.get(field, ""))
                    if val and val != "nan":
                        st.write(f"**{label}:** {val[:500]}")


# ============================================================
# TAB 4: MINISTRY OVERVIEW
# ============================================================

def _render_ministry_overview(df):
    """Analytics and charts for scheme data."""
    st.subheader("Ministry Overview")
    st.info("**Big picture view** of government funding across all ministries.")

    # Top 10 ministries by budget
    st.markdown("##### Top 10 Ministries by Budget")
    ministry_summary = _get_ministry_summary(df)

    if not ministry_summary.empty:
        top_10 = ministry_summary.head(10)
        chart_data = top_10.set_index("ministry")["total_budget"]
        chart_data.index = [
            m.replace("Ministry of ", "").replace("Ministry for ", "")[:25]
            for m in chart_data.index
        ]
        st.bar_chart(chart_data, horizontal=True)

    st.divider()

    # Top 10 highest budget schemes
    st.markdown("##### Top 10 Highest-Budget Schemes")
    top_schemes = df.nlargest(10, "budget_numeric")[
        ["name", "ministry", "budget_allocation", "budget_numeric"]
    ].reset_index(drop=True)
    top_schemes.index += 1
    top_schemes.columns = ["Scheme", "Ministry", "Budget", "₹ Cr"]
    st.dataframe(top_schemes, use_container_width=True)

    st.divider()

    # Category distribution
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("##### By Category")
        if "category" in df.columns:
            cat_counts = df["category"].value_counts()
            st.bar_chart(cat_counts)

    with col_r:
        st.markdown("##### By Focus Area")
        if "focus" in df.columns:
            focus_counts = df["focus"].value_counts().head(10)
            st.bar_chart(focus_counts)

    # Summary
    st.divider()
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total Schemes", len(df))
    s2.metric("Ministries", df["ministry"].nunique())
    s3.metric("Categories", df["category"].nunique() if "category" in df.columns else "N/A")
    s4.metric("Total Budget", f"₹{df['budget_numeric'].sum():,.0f} Cr")