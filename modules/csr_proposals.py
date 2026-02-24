"""
CSR Proposals Tab — Shows grievance clusters that qualify for CSR funding.

Displays:
- CSR-Ready clusters (≥200 complaints) with matched companies and proposal generation
- Monitoring clusters (100-199) with progress bars toward threshold
"""
import streamlit as st
import json
from modules.csr_pipeline import (
    get_csr_candidates,
    get_monitoring_clusters,
    match_companies,
    generate_csr_proposal,
    CSR_PROPOSAL_THRESHOLD,
)
from modules.persistence import save_draft
from modules.utils import show_download_button, track_action


def render_csr_proposals(username):
    """Render the CSR Proposals tab — data-backed funding opportunities from citizen complaints."""
    st.header("🚨 CSR Proposals")
    st.caption("Grievance clusters that qualify for CSR-funded intervention. Data-backed, ready to pitch.")

    tenant_id = st.session_state.get("tenant_id", 1)
    constituency = st.session_state.get("constituency", "the constituency")

    # Load CSR company database for matching
    csr_data = []
    try:
        with open("csr_db.json", "r") as f:
            csr_data = json.load(f)
    except FileNotFoundError:
        pass
    try:
        with open("csr_discovery.json", "r") as f:
            csr_data += json.load(f)
    except FileNotFoundError:
        pass

    # ═══════════════════════════════════════
    # SECTION A: CSR-READY CLUSTERS (≥200)
    # ═══════════════════════════════════════
    st.subheader("🟢 CSR-Ready (Qualified for Proposal)")

    candidates = get_csr_candidates(tenant_id)

    if candidates:
        st.success(f"**{len(candidates)} clusters** have crossed the {CSR_PROPOSAL_THRESHOLD}-complaint threshold.")

        for i, cluster in enumerate(candidates):
            badge = "🔴 CRITICAL" if cluster["volume"] >= 500 else "🟠 MAJOR" if cluster["volume"] >= 300 else "🟢 QUALIFIED"

            with st.expander(
                f"{badge} | {cluster['category']} in {cluster['area']} — {cluster['volume']} complaints",
                expanded=(i == 0),
            ):
                # Cluster details
                c1, c2, c3 = st.columns(3)
                c1.metric("Complaints", cluster["volume"])
                c2.metric("CSR Sector", cluster["csr_sector"])

                date_range = "N/A"
                if cluster.get("first_report") and cluster.get("last_report"):
                    try:
                        date_range = f"{cluster['first_report'].strftime('%d %b %Y')} → {cluster['last_report'].strftime('%d %b %Y')}"
                    except Exception:
                        date_range = "Date range unavailable"
                c3.metric("Period", date_range)

                st.divider()

                # Matched companies
                matches = match_companies(cluster["csr_sector"], csr_data)
                if matches:
                    st.write("**🏢 Matched CSR Companies:**")
                    company_names = [m.get("Company", "Unknown") for m in matches]

                    for j, company in enumerate(matches):
                        col_a, col_b = st.columns([3, 1])
                        col_a.write(f"• **{company.get('Company', 'Unknown')}** — {company.get('Sector', 'General')}")

                        if col_b.button(
                            "📄 Generate DPR",
                            key=f"dpr_{i}_{j}_{company.get('Company', '')}",
                        ):
                            with st.spinner(f"Generating proposal for {company.get('Company')}..."):
                                proposal = generate_csr_proposal(
                                    cluster, company.get("Company", "Unknown"), constituency
                                )
                                st.subheader("📄 Generated Proposal")
                                with st.container(border=True):
                                    st.markdown(proposal)

                                save_draft(
                                    username,
                                    f"CSR DPR: {company.get('Company')} — {cluster['area']} ({cluster['category']})",
                                    proposal,
                                    "CSR Proposal",
                                )
                                show_download_button(proposal, f"DPR_{company.get('Company')}_{cluster['area']}")
                                track_action(f"Generated CSR DPR for {company.get('Company')} ({cluster['area']})")
                else:
                    st.info("No matching companies found in the CSR database for this sector.")

    else:
        st.info(
            f"No clusters have reached the {CSR_PROPOSAL_THRESHOLD}-complaint threshold yet. "
            f"Monitor the pipeline below to see which issues are approaching eligibility."
        )

    # ═══════════════════════════════════════
    # SECTION B: MONITORING (100-199)
    # ═══════════════════════════════════════
    st.divider()
    st.subheader("📊 Monitoring Pipeline (Approaching Threshold)")

    monitoring = get_monitoring_clusters(tenant_id)

    if monitoring:
        for cluster in monitoring:
            col_left, col_right = st.columns([3, 1])
            with col_left:
                st.write(f"**{cluster['category']}** in **{cluster['area']}**")
                st.progress(
                    cluster["progress_pct"] / 100,
                    text=f"{cluster['volume']} / {CSR_PROPOSAL_THRESHOLD} complaints ({cluster['progress_pct']}%)",
                )
            with col_right:
                st.metric("Count", cluster["volume"])
    else:
        st.caption("No clusters currently approaching the threshold.")
