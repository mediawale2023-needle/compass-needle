"""Entry point for the PostgreSQL WhatsApp routing suite (tests/wa_tenant_routing_pg_suite.py).

The suite binds the whole app to a real PostgreSQL database at import time, so
it is only imported when TEST_POSTGRES_URL is set. Otherwise this file reports
a single explicit skip (and still exits 0 under scripts/run_backend_tests.sh).
"""
import os

import pytest

if os.getenv("TEST_POSTGRES_URL"):
    from tests.wa_tenant_routing_pg_suite import *  # noqa: F401,F403
else:
    def test_postgres_routing_suite_requires_test_postgres_url():
        pytest.skip("TEST_POSTGRES_URL not set — PostgreSQL routing suite skipped")
