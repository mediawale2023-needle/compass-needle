"""
tests/test_govt_portals_config.py — pins the two govt_portals.json
configuration corrections made after the Step 6 read-only investigation:

- UP Jansunwai (IGRS): status_check_url nulled (the previously configured
  /Grievance/GrievanceStatus.aspx 404s on the live samadhan.gov.in domain,
  confirmed by direct read-only request). status_check_mode/otp_bound left
  unchanged — no adapter capable of UP's real reference+mobile+CAPTCHA+OTP
  flow exists yet, so this is a data-only correction, not a behavior change.
- CPGRAMS: status_check_mode changed from "public_reference" to
  "login_required" (the live /Status page unconditionally returns a
  password+CAPTCHA-gated login form regardless of query params — there is
  no anonymous reference-only lookup). status_check_url/otp_bound
  unchanged.

Both corrections are no-ops on ManualAssistedAdapter.check_status()'s
observable outcome (checked=False before and after, for both portals) —
these tests pin that outcome and additionally prove no outbound HTTP
request is attempted for either row post-correction, closing the
"wasted network call to a dead/gated URL every poll cycle" issue these
corrections exist to fix.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.govt_sync.adapters.manual import ManualAssistedAdapter

_PORTALS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "modules", "data", "govt_portals.json",
)


def _load_portal(portal_name: str) -> dict:
    with open(_PORTALS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    rows = data if isinstance(data, list) else data.get("portals", data)
    for row in rows:
        if row.get("portal_name") == portal_name:
            return row
    raise AssertionError(f"portal {portal_name!r} not found in govt_portals.json")


# ─── Data-level: exact intended configuration ──────────────────────────────

def test_up_jansunwai_status_check_url_is_nulled():
    row = _load_portal("UP Jansunwai (IGRS)")
    assert row["status_check_url"] is None
    # Explicitly unchanged per the approved scope — no adapter/mode work.
    assert row["status_check_mode"] == "public_reference"
    assert row["otp_bound"] is True


def test_cpgrams_status_check_mode_is_login_required():
    row = _load_portal("CPGRAMS")
    assert row["status_check_mode"] == "login_required"
    # Explicitly unchanged per the approved scope.
    assert row["status_check_url"] == "https://pgportal.gov.in/Status"
    assert row["otp_bound"] is False


# ─── Behavior-level: both corrections are checked=False no-ops, and now ───
# ─── make zero outbound HTTP calls (the actual bug being fixed) ───────────

def _no_network_requests_get(*args, **kwargs):
    raise AssertionError(
        "check_status() made an HTTP request — expected the config guard "
        "to short-circuit before any network call for this portal row"
    )


def test_up_jansunwai_check_status_makes_no_request_and_is_unchecked(monkeypatch):
    import requests
    monkeypatch.setattr(requests, "get", _no_network_requests_get)

    row = _load_portal("UP Jansunwai (IGRS)")
    result = ManualAssistedAdapter(row).check_status("UP/2026/00012345")
    assert result.checked is False
    assert result.status == ""


def test_cpgrams_check_status_makes_no_request_and_is_unchecked(monkeypatch):
    import requests
    monkeypatch.setattr(requests, "get", _no_network_requests_get)

    row = _load_portal("CPGRAMS")
    result = ManualAssistedAdapter(row).check_status("DARPG/E/2026/00012345")
    assert result.checked is False
    assert result.status == ""
