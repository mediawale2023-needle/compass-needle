"""
Case Intelligence Module — Admin-only analytics and case exploration.

Three views:
1. Platform Health  — Total cases, status breakdown, MP activity, volume over time
2. Case Explorer    — Filter/search/drill into individual cases across all tenants
3. Grievance Analytics — Category trends, resolution times, growing issues
"""

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text


# ─────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────
@st.cache_resource
def _get_engine():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return create_engine(db_url)
    return create_engine("sqlite:///./sansadx.db")


def _run(query, params=None):
    """Run a query and return list of dicts."""
    engine = _get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        if result.returns_rows:
            return [dict(row._mapping) for row in result]
        return []


# ─────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────
def render_case_intelligence():
    """Main render function called from admin_dashboard.py."""

    view = st.radio(
        "Select View",
        ["Platform Health", "Case Explorer", "Grievance Analytics"],
        horizontal=True,
        label_visibility="collapsed",
    )

    st.markdown("---")

    if view == "Platform Health":
        _render_platform_health()
    elif view == "Case Explorer":
        _render_case_explorer()
    else:
        _render_grievance_analytics()


# ═══════════════════════════════════════════
# VIEW 1: PLATFORM HEALTH
# ═══════════════════════════════════════════
def _render_platform_health():
    st.markdown('<div class="section-title">Platform Health</div>', unsafe_allow_html=True)

    # A. Top-line metrics
    total_row = _run("SELECT COUNT(*) AS cnt FROM cases")
    total_cases = total_row[0]["cnt"] if total_row else 0

    tenant_row = _run("SELECT COUNT(*) AS cnt FROM tenants WHERE name != 'System Admin'")
    total_mps = tenant_row[0]["cnt"] if tenant_row else 0

    resolved_row = _run("SELECT COUNT(*) AS cnt FROM cases WHERE status = 'resolved'")
    resolved = resolved_row[0]["cnt"] if resolved_row else 0

    critical_row = _run("SELECT COUNT(*) AS cnt FROM cases WHERE is_critical = true")
    critical = critical_row[0]["cnt"] if critical_row else 0

    c1, c2, c3, c4 = st.columns(4)
    _metric_card(c1, "Total Cases", f"{total_cases:,}", "📊")
    _metric_card(c2, "Active MPs", str(total_mps), "👥")
    _metric_card(c3, "Resolved", f"{resolved:,}", "✅")
    _metric_card(c4, "Critical", str(critical), "🔴")

    st.markdown("####")

    # B. Cases by Status
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("**Cases by Status**")
        status_data = _run("""
            SELECT COALESCE(status, 'unknown') AS status, COUNT(*) AS count
            FROM cases GROUP BY status ORDER BY count DESC
        """)
        if status_data:
            df_status = pd.DataFrame(status_data)
            st.bar_chart(df_status.set_index("status"), horizontal=True)
        else:
            st.info("No case data available.")

    # C. Cases per MP
    with col_right:
        st.markdown("**Cases per MP**")
        mp_data = _run("""
            SELECT t.name, t.constituency, COUNT(c.id) AS cases
            FROM tenants t
            LEFT JOIN cases c ON t.id = c.tenant_id
            WHERE t.name != 'System Admin'
            GROUP BY t.id, t.name, t.constituency
            ORDER BY cases DESC
        """)
        if mp_data:
            df_mp = pd.DataFrame(mp_data)
            st.bar_chart(df_mp.set_index("name")["cases"])
        else:
            st.info("No MP data.")

    st.markdown("####")

    # D. MP Activity — who's active, who hasn't logged in
    st.markdown("**MP Activity**")
    activity_data = _run("""
        SELECT u.display_name, u.username, u.last_login,
               t.constituency, t.name AS mp_name,
               COUNT(c.id) AS total_cases
        FROM users u
        JOIN tenants t ON u.tenant_id = t.id
        LEFT JOIN cases c ON t.id = c.tenant_id
        WHERE u.role IN ('mp', 'user') AND t.name != 'System Admin'
        GROUP BY u.id, u.display_name, u.username, u.last_login, t.constituency, t.name
        ORDER BY total_cases DESC
    """)
    if activity_data:
        rows = []
        for a in activity_data:
            last = a["last_login"]
            if last:
                if isinstance(last, str):
                    last_str = last[:16]
                else:
                    last_str = last.strftime("%Y-%m-%d %H:%M")
            else:
                last_str = "Never"
            rows.append({
                "MP": a["display_name"] or a["username"],
                "Constituency": a["constituency"],
                "Cases": a["total_cases"],
                "Last Login": last_str,
                "Status": "🟢 Active" if last and last_str != "Never" else "⚪ Never logged in",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No MP activity data.")

    st.markdown("####")

    # E. Case volume over time (last 30 days)
    st.markdown("**Case Volume — Last 30 Days**")
    vol_data = _run("""
        SELECT DATE(created_at) AS day, COUNT(*) AS count
        FROM cases
        WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY DATE(created_at)
        ORDER BY day
    """)
    if vol_data:
        df_vol = pd.DataFrame(vol_data)
        df_vol["day"] = pd.to_datetime(df_vol["day"])
        st.line_chart(df_vol.set_index("day")["count"])
    else:
        st.info("No recent case data for volume chart.")


# ═══════════════════════════════════════════
# VIEW 2: CASE EXPLORER
# ═══════════════════════════════════════════
def _render_case_explorer():
    st.markdown('<div class="section-title">Case Explorer</div>', unsafe_allow_html=True)

    # A. Filters
    f1, f2, f3, f4 = st.columns(4)

    # Tenant filter
    tenants = _run("SELECT id, name, constituency FROM tenants WHERE name != 'System Admin' ORDER BY name")
    tenant_options = {f"{t['name']} ({t['constituency']})": t["id"] for t in tenants}

    with f1:
        selected_mp = st.selectbox("MP", ["All MPs"] + list(tenant_options.keys()))

    # Date range
    with f2:
        date_range = st.selectbox("Period", ["All Time", "Last 7 Days", "Last 30 Days", "Last 90 Days"])

    # Category
    cats = _run("SELECT DISTINCT category FROM cases WHERE category IS NOT NULL ORDER BY category")
    cat_list = [c["category"] for c in cats if c["category"]]
    with f3:
        selected_cat = st.selectbox("Category", ["All Categories"] + cat_list)

    # Status
    statuses = _run("SELECT DISTINCT status FROM cases WHERE status IS NOT NULL ORDER BY status")
    status_list = [s["status"] for s in statuses if s["status"]]
    with f4:
        selected_status = st.selectbox("Status", ["All Statuses"] + status_list)

    # Build query
    conditions = ["1=1"]
    params = {}

    if selected_mp != "All MPs":
        conditions.append("c.tenant_id = :tid")
        params["tid"] = tenant_options[selected_mp]

    if date_range == "Last 7 Days":
        conditions.append("c.created_at >= CURRENT_DATE - INTERVAL '7 days'")
    elif date_range == "Last 30 Days":
        conditions.append("c.created_at >= CURRENT_DATE - INTERVAL '30 days'")
    elif date_range == "Last 90 Days":
        conditions.append("c.created_at >= CURRENT_DATE - INTERVAL '90 days'")

    if selected_cat != "All Categories":
        conditions.append("c.category = :cat")
        params["cat"] = selected_cat

    if selected_status != "All Statuses":
        conditions.append("c.status = :st")
        params["st"] = selected_status

    where = " AND ".join(conditions)

    # Count
    count_row = _run(f"SELECT COUNT(*) AS cnt FROM cases c WHERE {where}", params)
    total = count_row[0]["cnt"] if count_row else 0
    st.caption(f"Showing {min(total, 200)} of {total:,} cases")

    # Fetch cases (limit 200 for performance)
    cases = _run(f"""
        SELECT c.id, c.tenant_id, t.name AS mp_name, t.constituency,
               c.user_phone, c.category, c.status, c.raw_message,
               c.case_metadata, c.is_critical, c.created_at, c.updated_at,
               c.response_to_citizen, c.notes_for_staff
        FROM cases c
        JOIN tenants t ON c.tenant_id = t.id
        WHERE {where}
        ORDER BY c.created_at DESC
        LIMIT 200
    """, params)

    if not cases:
        st.info("No cases match the selected filters.")
        return

    # Build display table
    rows = []
    for c in cases:
        meta = _parse_meta(c.get("case_metadata"))
        created = c["created_at"]
        if created:
            if isinstance(created, str):
                created_str = created[:16]
            else:
                created_str = created.strftime("%Y-%m-%d %H:%M")
        else:
            created_str = "-"

        rows.append({
            "ID": c["id"],
            "MP": c["mp_name"],
            "Phone": c.get("user_phone", "-"),
            "Category": c.get("category", "-"),
            "Status": c.get("status", "-"),
            "Location": meta.get("matched_value", "-"),
            "Assembly": meta.get("assembly_constituency", "-"),
            "Message": (c.get("raw_message") or "-")[:80],
            "Created": created_str,
            "Critical": "🔴" if c.get("is_critical") else "",
        })

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        column_config={
            "ID": st.column_config.NumberColumn("ID", width="small"),
            "MP": st.column_config.TextColumn("MP", width="medium"),
            "Phone": st.column_config.TextColumn("Contact", width="medium"),
            "Category": st.column_config.TextColumn("Category", width="small"),
            "Status": st.column_config.TextColumn("Status", width="small"),
            "Location": st.column_config.TextColumn("Location", width="medium"),
            "Assembly": st.column_config.TextColumn("Assembly", width="medium"),
            "Message": st.column_config.TextColumn("Message", width="large"),
            "Created": st.column_config.TextColumn("Created", width="small"),
            "Critical": st.column_config.TextColumn("!", width="small"),
        },
        use_container_width=True,
        hide_index=True,
    )

    # Case detail expander
    st.markdown("####")
    st.markdown("**Case Detail Lookup**")
    case_id_input = st.number_input("Enter Case ID to view full details", min_value=1, step=1, value=None)
    if case_id_input:
        detail = _run("""
            SELECT c.*, t.name AS mp_name, t.constituency AS mp_constituency
            FROM cases c JOIN tenants t ON c.tenant_id = t.id
            WHERE c.id = :cid
        """, {"cid": int(case_id_input)})

        if detail:
            d = detail[0]
            meta = _parse_meta(d.get("case_metadata"))

            with st.container(border=True):
                st.markdown(f"### Case #{d['id']}")
                dc1, dc2, dc3 = st.columns(3)
                with dc1:
                    st.markdown(f"**MP:** {d.get('mp_name', '-')}")
                    st.markdown(f"**Constituency:** {d.get('mp_constituency', '-')}")
                    st.markdown(f"**Phone:** {d.get('user_phone', '-')}")
                with dc2:
                    st.markdown(f"**Category:** {d.get('category', '-')}")
                    st.markdown(f"**Status:** {d.get('status', '-')}")
                    st.markdown(f"**Critical:** {'Yes 🔴' if d.get('is_critical') else 'No'}")
                with dc3:
                    st.markdown(f"**Location:** {meta.get('matched_value', d.get('location', '-'))}")
                    st.markdown(f"**Assembly:** {meta.get('assembly_constituency', d.get('ward', '-'))}")
                    st.markdown(f"**Confidence:** {meta.get('confidence', '-')}")

                st.markdown("---")
                st.markdown("**Full Message:**")
                st.text(d.get("raw_message", "-"))

                if d.get("response_to_citizen"):
                    st.markdown("**AI Response to Citizen:**")
                    st.text(d["response_to_citizen"])

                if d.get("notes_for_staff"):
                    st.markdown("**Staff Notes:**")
                    st.text(d["notes_for_staff"])

                cc1, cc2, cc3 = st.columns(3)
                with cc1:
                    created = d.get("created_at")
                    st.caption(f"Created: {created.strftime('%Y-%m-%d %H:%M') if hasattr(created, 'strftime') else str(created)[:16] if created else '-'}")
                with cc2:
                    updated = d.get("updated_at")
                    st.caption(f"Updated: {updated.strftime('%Y-%m-%d %H:%M') if hasattr(updated, 'strftime') else str(updated)[:16] if updated else '-'}")
                with cc3:
                    resolved = d.get("resolved_at")
                    st.caption(f"Resolved: {resolved.strftime('%Y-%m-%d %H:%M') if hasattr(resolved, 'strftime') else str(resolved)[:16] if resolved else '-'}")
        else:
            st.warning(f"Case #{case_id_input} not found.")


# ═══════════════════════════════════════════
# VIEW 3: GRIEVANCE ANALYTICS
# ═══════════════════════════════════════════
def _render_grievance_analytics():
    st.markdown('<div class="section-title">Grievance Analytics</div>', unsafe_allow_html=True)

    # A. Top categories across all MPs
    st.markdown("**Most Common Grievance Categories**")
    cat_data = _run("""
        SELECT COALESCE(c.category, 'Uncategorized') AS category,
               t.constituency,
               COUNT(*) AS count
        FROM cases c
        JOIN tenants t ON c.tenant_id = t.id
        WHERE t.name != 'System Admin'
        GROUP BY c.category, t.constituency
        ORDER BY count DESC
        LIMIT 30
    """)
    if cat_data:
        df_cat = pd.DataFrame(cat_data)
        # Pivot to show categories per constituency
        pivot = df_cat.pivot_table(index="category", columns="constituency", values="count", fill_value=0)
        st.bar_chart(pivot)
    else:
        st.info("No category data.")

    st.markdown("####")

    # B. Category breakdown table
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("**Category Volume (All MPs)**")
        cat_vol = _run("""
            SELECT COALESCE(category, 'Uncategorized') AS category, COUNT(*) AS count
            FROM cases WHERE tenant_id != 1
            GROUP BY category ORDER BY count DESC
        """)
        if cat_vol:
            st.dataframe(pd.DataFrame(cat_vol), use_container_width=True, hide_index=True)

    with col_r:
        st.markdown("**Status Distribution**")
        status_vol = _run("""
            SELECT COALESCE(status, 'unknown') AS status, COUNT(*) AS count
            FROM cases WHERE tenant_id != 1
            GROUP BY status ORDER BY count DESC
        """)
        if status_vol:
            st.dataframe(pd.DataFrame(status_vol), use_container_width=True, hide_index=True)

    st.markdown("####")

    # C. Resolution time analysis
    st.markdown("**Average Resolution Time**")
    resolution_data = _run("""
        SELECT t.name AS mp_name, t.constituency,
               COUNT(*) AS resolved_cases,
               AVG(EXTRACT(EPOCH FROM (c.resolved_at - c.created_at)) / 3600) AS avg_hours
        FROM cases c
        JOIN tenants t ON c.tenant_id = t.id
        WHERE c.resolved_at IS NOT NULL AND c.created_at IS NOT NULL
              AND t.name != 'System Admin'
        GROUP BY t.id, t.name, t.constituency
        ORDER BY avg_hours
    """)
    if resolution_data:
        rows = []
        for r in resolution_data:
            avg_h = r["avg_hours"]
            if avg_h is not None:
                if avg_h > 24:
                    time_str = f"{avg_h / 24:.1f} days"
                else:
                    time_str = f"{avg_h:.1f} hours"
            else:
                time_str = "-"
            rows.append({
                "MP": r["mp_name"],
                "Constituency": r["constituency"],
                "Resolved Cases": r["resolved_cases"],
                "Avg Resolution Time": time_str,
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No resolution data available yet (no cases have been resolved with timestamps).")

    st.markdown("####")

    # D. Assembly-level distribution (for MPs with geography data)
    st.markdown("**Cases by Assembly Constituency**")
    assembly_data = _run("""
        SELECT case_metadata FROM cases
        WHERE case_metadata IS NOT NULL AND tenant_id != 1
    """)
    if assembly_data:
        ac_counts = {}
        for row in assembly_data:
            meta = _parse_meta(row.get("case_metadata"))
            ac = meta.get("assembly_constituency")
            if ac:
                ac_counts[ac] = ac_counts.get(ac, 0) + 1
        if ac_counts:
            df_ac = pd.DataFrame(
                sorted(ac_counts.items(), key=lambda x: -x[1]),
                columns=["Assembly Constituency", "Cases"]
            )
            st.bar_chart(df_ac.set_index("Assembly Constituency"))
        else:
            st.info("No assembly-level data in case metadata.")
    else:
        st.info("No cases with metadata available.")


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────
def _parse_meta(meta):
    """Safely parse case_metadata (could be dict, JSON string, or None)."""
    if meta is None:
        return {}
    if isinstance(meta, dict):
        return meta
    try:
        return json.loads(meta)
    except Exception:
        return {}


def _metric_card(col, label, value, icon=""):
    """Render a styled metric card."""
    col.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #f8f9fa, #e9ecef);
        border-radius: 12px; padding: 20px; text-align: center;
        border: 1px solid #dee2e6;
    ">
        <div style="font-size: 28px; margin-bottom: 4px;">{icon}</div>
        <div style="font-size: 28px; font-weight: 800; color: #1a1a2e;">{value}</div>
        <div style="font-size: 13px; color: #666; margin-top: 4px;">{label}</div>
    </div>
    """, unsafe_allow_html=True)
