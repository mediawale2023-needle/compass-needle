"""Tamil Nadu authenticated HTTP status adapter.

Uses only an encrypted, backend-owned cookie session captured after a staff
member signs in through the existing Playwright live-session flow. No login,
OTP, CAPTCHA, ticket enumeration, filing, or mutation happens here.
"""
from __future__ import annotations

import logging
from urllib.parse import urlsplit

import requests

from modules.govt_sync import cookie_sessions
# Imported from the neutral constants module, NOT from
# modules.govt_sync.status.tamil_nadu — that edge created a real import
# cycle (status.tamil_nadu -> adapters.base -> adapters/__init__ ->
# tamil_nadu_http -> status.tamil_nadu) that broke any import order which
# reached the status package first. See tamil_nadu_constants' docstring.
from modules.govt_sync.tamil_nadu_constants import _ACTION_TAKEN_UNAVAILABLE

from .base import StatusResult, normalize_status_keywords
from .manual import ManualAssistedAdapter

logger = logging.getLogger("needle.govt_sync.adapter.tamil_nadu_http")

_REQUEST_TIMEOUT_SECONDS = 15
_USER_AGENT = "Mozilla/5.0 (compatible; NeedleGovtSync/1.0)"
_VERIFY_NOTE = "Tamil Nadu access needs verification. Please sign in again."


class TamilNaduHTTPStatusAdapter(ManualAssistedAdapter):
    """Primary inboard status path for Tamil Nadu when a cookie session exists."""

    def _portal_id(self) -> int | None:
        return self.portal.get("portal_id") or self.portal.get("id")

    def verification_state(self, tenant_id: int) -> dict:
        portal_id = self._portal_id()
        if not portal_id:
            return {"status": "not_started", "captured_at": None, "last_used_at": None, "last_auth_failed_at": None, "expires_at": None}
        return cookie_sessions.cookie_session_state(tenant_id, int(portal_id))

    def check_status(self, reference_number: str, tenant_id: int | None = None) -> StatusResult:
        portal_id = self._portal_id()
        if not tenant_id or not portal_id:
            return StatusResult(status="", checked=False, needs_verification=True, raw_portal_status=_VERIFY_NOTE)

        try:
            session = cookie_sessions.load_cookie_session(int(tenant_id), int(portal_id))
        except cookie_sessions.CookieSessionKeyError:
            logger.warning("Tamil Nadu cookie session key missing/invalid; status check requires verification")
            return StatusResult(status="", checked=False, needs_verification=True, raw_portal_status=_VERIFY_NOTE)
        except cookie_sessions.CookieSessionDecryptError:
            cookie_sessions.mark_cookie_session_auth_failed(int(tenant_id), int(portal_id))
            return StatusResult(status="", checked=False, needs_verification=True, raw_portal_status=_VERIFY_NOTE)

        if not session:
            return StatusResult(status="", checked=False, needs_verification=True, raw_portal_status=_VERIFY_NOTE)

        reference = (reference_number or "").strip().upper()
        record_id = (session.ticket_mappings or {}).get(reference)
        if not record_id:
            return StatusResult(status="", checked=False, needs_verification=True, raw_portal_status=_VERIFY_NOTE)

        base_url = str(self.portal.get("base_url") or "https://cmhelpline.tnega.org").rstrip("/")
        host = urlsplit(base_url).netloc
        cookie_header = cookie_sessions.cookies_to_header(session.cookie_jar, host)
        if not cookie_header:
            cookie_sessions.mark_cookie_session_auth_failed(int(tenant_id), int(portal_id))
            return StatusResult(status="", checked=False, needs_verification=True, raw_portal_status=_VERIFY_NOTE)

        headers = {
            "Accept": "application/json, text/plain, */*",
            "Cookie": cookie_header,
            "User-Agent": _USER_AGENT,
        }
        try:
            ticket_resp = requests.get(
                f"{base_url}/portal/api/tickets/{record_id}",
                headers=headers,
                timeout=_REQUEST_TIMEOUT_SECONDS,
                allow_redirects=False,
            )
        except requests.Timeout:
            return StatusResult(status="", checked=False, raw_portal_status="Tamil Nadu portal timed out.")
        except requests.RequestException:
            return StatusResult(status="", checked=False, raw_portal_status="Tamil Nadu portal could not be reached.")

        if ticket_resp.status_code in (401, 403):
            cookie_sessions.mark_cookie_session_auth_failed(int(tenant_id), int(portal_id))
            return StatusResult(status="", checked=False, needs_verification=True, raw_portal_status=_VERIFY_NOTE)
        if ticket_resp.status_code == 404:
            return StatusResult(status="", checked=False, raw_portal_status="Tamil Nadu ticket was not found.")
        if 500 <= ticket_resp.status_code < 600:
            return StatusResult(status="", checked=False, raw_portal_status="Tamil Nadu portal is temporarily unavailable.")
        if ticket_resp.status_code != 200:
            return StatusResult(status="", checked=False, raw_portal_status="Tamil Nadu status check was inconclusive.")

        try:
            ticket = ticket_resp.json()
        except ValueError:
            return StatusResult(status="", checked=False, raw_portal_status="Tamil Nadu returned an unreadable response.")

        parsed = _parse_ticket_payload(ticket, reference)
        if not parsed:
            return StatusResult(status="", checked=False, raw_portal_status="Tamil Nadu response did not match the recorded grievance.")

        conversations = _fetch_conversations(base_url, record_id, headers)
        if conversations is not None:
            parsed["replies"] = conversations

        raw_status = parsed.get("raw_detail_status") or parsed.get("raw_list_status") or ""
        normalized = _normalize_tn_status(raw_status)
        if not normalized:
            return StatusResult(status="", checked=False, raw_portal_status=raw_status or "Tamil Nadu status was unreadable.")

        cookie_sessions.mark_cookie_session_used(int(tenant_id), int(portal_id))
        return StatusResult(
            status=normalized,
            raw_portal_status=raw_status,
            checked=True,
            needs_verification=False,
            portal_detail={
                "status_text": parsed.get("raw_detail_status"),
                "sub_status_text": parsed.get("raw_list_status"),
                "department_name": parsed.get("department"),
                "last_action_date": parsed.get("last_updated"),
                "pendency_details": parsed.get("action_taken_report"),
                "raw_list_status": parsed.get("raw_list_status"),
                "raw_detail_status": parsed.get("raw_detail_status"),
                "replies": parsed.get("replies") or [],
                "channel": "tn_cookie_http_status",
            },
        )


def _normalize_tn_status(raw_status: str) -> str | None:
    normalized = normalize_status_keywords(raw_status)
    if normalized:
        return normalized
    if (raw_status or "").strip().lower() == "pending action":
        return "submitted"
    return None


def _parse_ticket_payload(payload: dict, reference: str) -> dict | None:
    ticket = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(ticket, dict):
        return None

    candidates = [
        ticket.get("reference_number"),
        ticket.get("referenceNumber"),
        ticket.get("ticket_number"),
        ticket.get("ticketNumber"),
        ticket.get("petition_number"),
        ticket.get("petitionNumber"),
        ticket.get("display_id"),
        ticket.get("displayId"),
    ]
    text_blob = " ".join(str(v) for v in candidates if v)
    if reference.lower() not in text_blob.lower():
        return None

    raw_status = (
        ticket.get("status")
        or ticket.get("status_name")
        or ticket.get("statusName")
        or ticket.get("state")
        or ticket.get("current_status")
    )
    department = (
        ticket.get("department")
        or ticket.get("department_name")
        or ticket.get("departmentName")
        or ticket.get("departmentNameEnglish")
    )
    last_updated = ticket.get("updated_at") or ticket.get("updatedAt") or ticket.get("last_updated") or ticket.get("lastUpdated")
    atr = ticket.get("action_taken_report") or ticket.get("actionTakenReport") or ticket.get("atr")
    if atr is None and ticket.get("atr_iframe") is not None:
        atr = _ACTION_TAKEN_UNAVAILABLE
    return {
        "raw_detail_status": str(raw_status).strip() if raw_status else None,
        "raw_list_status": str(ticket.get("list_status") or ticket.get("listStatus") or "").strip() or None,
        "department": str(department).strip() if department else None,
        "last_updated": str(last_updated).strip() if last_updated else None,
        "action_taken_report": str(atr).strip() if atr else None,
    }


def _fetch_conversations(base_url: str, record_id: str, headers: dict) -> list | None:
    try:
        resp = requests.get(
            f"{base_url}/portal/api/tickets/{record_id}/conversations",
            headers=headers,
            timeout=_REQUEST_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    try:
        payload = resp.json()
    except ValueError:
        return None
    items = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return None
    replies = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = item.get("text") or item.get("message") or item.get("body") or item.get("content")
        if not text:
            continue
        replies.append({
            "id": item.get("id") or item.get("message_id") or item.get("messageId"),
            "text": str(text),
            "author": item.get("author") or item.get("created_by") or item.get("createdBy"),
            "timestamp": item.get("created_at") or item.get("createdAt") or item.get("timestamp"),
            "parent_id": item.get("parent_id") or item.get("parentId"),
        })
    return replies
