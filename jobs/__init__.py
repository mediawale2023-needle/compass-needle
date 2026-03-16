"""
jobs/ — Background automation jobs for the Needle CSR Intelligence Platform.

Run individually:
    python -m jobs.opportunity_sync
    python -m jobs.scoring_recompute
    python -m jobs.company_enrichment
    python -m jobs.mca_csr_sync
    python -m jobs.weekly_report

Or schedule via cron / APScheduler.
"""
