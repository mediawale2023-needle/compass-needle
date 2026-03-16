"""
jobs/ — Background automation jobs for the Needle CSR Intelligence Platform.

Run individually:
    python -m jobs.opportunity_sync
    python -m jobs.scoring_recompute
    python -m jobs.company_enrichment
    python -m jobs.mca_csr_sync
    python -m jobs.weekly_report

    # Dataset collection jobs
    python -m jobs.datagov_district_sync   # data.gov.in + MoSPI district indicators
    python -m jobs.bse_nse_sync            # BSE/NSE market cap + financial health
    python -m jobs.dmf_nabard_sync         # District Mineral Foundation + NABARD credit plans
    python -m jobs.csr_hub_sync            # National CSR Hub benchmarks + PM CARES
    python -m jobs.csrbox_sync             # CSRBox / Tracxn historical grant data

Or schedule via cron / APScheduler.

Dataset collection schedule:
    Monthly  : mca_csr_sync, csrbox_sync
    Weekly   : bse_nse_sync, company_enrichment
    Quarterly: datagov_district_sync, dmf_nabard_sync
    Annually : csr_hub_sync
"""
