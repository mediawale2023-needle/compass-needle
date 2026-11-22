"""PR 3: GET /api/partner/clients/{seat_id}/dashboard/overview.

The generic route-enumeration tests in test_partner_route_security.py also pick this route up automatically
(ownership, paused, revoked, tenant-override and PII checks). These tests add the overview-specific guarantees.
"""
import json

from sqlalchemy import text

from tests.test_partner_api import (  # noqa: F401
    PHONE, RAW_MESSAGE, _admin_headers, _attach, _create_partner, _partner_session, _seed_database, client,
    test_engine,
)
from tests.test_partner_route_security import pii_findings

PATH = "/api/partner/clients/{seat}/dashboard/overview"


def _world():
    _seed_database()
    admin = _admin_headers()
    pa, pb = _create_partner(admin, "Alpha Advisory"), _create_partner(admin, "Bravo Campaigns")
    ha = _partner_session(admin, pa, "a@alpha.in")
    hb = _partner_session(admin, pb, "b@bravo.in")
    return admin, pa, pb, ha, hb, _attach(admin, pa, 2), _attach(admin, pb, 3)


def test_overview_requires_partner_token_and_owned_seat():
    admin, pa, pb, ha, hb, seat_a, seat_b = _world()
    assert client.get(PATH.format(seat=seat_a)).status_code in (401, 403)
    assert client.get(PATH.format(seat=seat_a), headers=admin).status_code in (401, 403)
    assert client.get(PATH.format(seat=seat_b), headers=ha).status_code == 404
    assert client.get(PATH.format(seat=seat_a), headers=hb).status_code == 404
    assert client.get(PATH.format(seat=999999), headers=ha).status_code == 404
    assert client.get(PATH.format(seat=seat_a), headers=ha).status_code == 200


def test_overview_is_counts_only_and_tenant_scoped():
    admin, pa, pb, ha, hb, seat_a, seat_b = _world()
    body = client.get(PATH.format(seat=seat_a), headers=ha).json()
    ov = body["overview"]
    assert ov["mode"] == "partner" and ov["validation"]["counts_only"] is True
    assert "attention_queue" not in ov and "recent_movement" not in ov
    # tenant 2: 5 non-deleted cases (no date window on the Overview; #5 is soft-deleted); tenant 3: 2
    assert ov["validation"]["thread_count"] == 5
    assert client.get(PATH.format(seat=seat_b), headers=hb).json()["overview"]["validation"]["thread_count"] == 2
    blob = json.dumps(body)
    assert PHONE not in blob and RAW_MESSAGE not in blob and "Ramesh" not in blob and "Ward 5" not in blob
    assert pii_findings(body) == []


def test_overview_ignores_tenant_overrides():
    admin, pa, pb, ha, hb, seat_a, seat_b = _world()
    base = client.get(PATH.format(seat=seat_a), headers=ha).json()
    for override in ({"tenant_id": 3}, {"tid": 3}, {"partner_id": pb}):
        assert client.get(PATH.format(seat=seat_a), params=override, headers=ha).json() == base


def test_paused_seat_returns_409_without_data():
    admin, pa, pb, ha, hb, seat_a, seat_b = _world()
    r = client.post(f"/api/admin/partners/{pa}/seats/{seat_a}/status", json={"status": "paused"}, headers=admin)
    assert r.status_code == 200
    resp = client.get(PATH.format(seat=seat_a), headers=ha)
    assert resp.status_code == 409 and "overview" not in resp.text
