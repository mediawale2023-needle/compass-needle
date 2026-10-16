"""Authoritative WhatsApp number → tenant routing.

One rule set, used by the inbound webhook, outbound sends, and the Admin
dashboard, so all three always agree on who owns a number.

Authority
---------
The assignment Admin edits on the tenant row is the only source of truth:

  * ``tenants.config->>'meta_phone_number_id'`` — Meta's stable Phone Number ID
    (preferred: it is what the webhook carries in ``metadata.phone_number_id``)
  * ``tenants.whatsapp_number`` — the E.164 display number

Both are read fresh from the database on every call. There is deliberately no
in-process cache: a reassignment committed by any worker is visible to every
worker on the very next message.

Legacy ``tenant_overrides`` rows of type ``phone_mapping`` are consulted only for
a number/ID that no tenant's Admin assignment claims, so they can never outrank
or contradict Admin. Every such use logs a warning; Admin reassignment deletes
the rows for the numbers it touches.

Fail-safe
---------
Every path that cannot name exactly one active owner returns ``tenant_id=None``
with a reason. There is no default tenant. Callers must drop (and the inbound
ledger keeps) the message rather than guess.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

from sqlalchemy import bindparam, text

logger = logging.getLogger("needle.wa_routing")

# Returned by outbound lookups when the tenant has no number it is allowed to
# send from. send_whatsapp_message() refuses it instead of falling back to the
# global env number (which may belong to a different tenant).
OUTBOUND_BLOCKED_PHONE_NUMBER_ID = "blocked:no-authorised-number"

_DIGITS = re.compile(r"\D")


def normalize_display_number(raw: str | None) -> str:
    """'+91 98765-43210' / '919876543210' / 'whatsapp:+91…' → '+919876543210' ('' if none)."""
    digits = _DIGITS.sub("", str(raw or "").replace("whatsapp:", ""))
    return f"+{digits}" if digits else ""


def normalize_phone_number_id(raw: str | None) -> str:
    return _DIGITS.sub("", str(raw or ""))


def mask(value: str | None) -> str:
    """Last-4 only — for logs, audit rows and API responses."""
    value = str(value or "")
    return f"***{value[-4:]}" if value else ""


@dataclass
class RoutingResolution:
    tenant_id: int | None
    source: str                      # phone_number_id | display_number | legacy_override | none
    reason: str = ""                 # set when tenant_id is None, or on a warning
    candidates: list[int] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.tenant_id is not None


def _pnid_expr(conn) -> str:
    if conn.dialect.name == "postgresql":
        return "(config->>'meta_phone_number_id')"
    return "json_extract(config, '$.meta_phone_number_id')"


def _connect(conn):
    if conn is not None:
        return conn, False
    from sansadx_backend.db import engine
    return engine.connect(), True


def _tenants_claiming(conn, *, display: str = "", pnid: str = "") -> list[dict]:
    clauses, params = [], {}
    if display:
        clauses.append("whatsapp_number IN (:disp_plus, :disp_bare)")
        params.update(disp_plus=display, disp_bare=display.lstrip("+"))
    if pnid:
        clauses.append(f"{_pnid_expr(conn)} = :pnid")
        params["pnid"] = pnid
    if not clauses:
        return []
    rows = conn.execute(
        text(
            f"SELECT id, is_active, whatsapp_number, {_pnid_expr(conn)} AS pnid "
            f"FROM tenants WHERE {' OR '.join(clauses)} ORDER BY id"
        ),
        params,
    ).mappings().all()
    return [dict(r) for r in rows]


def resolve_whatsapp_tenant(
    display_number: str | None = None,
    phone_number_id: str | None = None,
    *,
    conn=None,
) -> RoutingResolution:
    """Resolve the single tenant that owns an inbound WhatsApp identity.

    ``display_number`` may also be a bare-digit Phone Number ID: legacy PA
    helpers substitute the WHATSAPP_PHONE_NUMBER_ID env var when the webhook
    gave them no receiver. A value without a leading '+' is therefore tried as
    both identities.
    """
    raw_display = str(display_number or "").strip()
    pnid = normalize_phone_number_id(phone_number_id)
    display = normalize_display_number(raw_display)
    if raw_display and not raw_display.startswith("+") and not pnid:
        pnid = normalize_phone_number_id(raw_display)

    if not display and not pnid:
        return RoutingResolution(None, "none", "no_receiver_identity")

    conn, owned = _connect(conn)
    try:
        rows = _tenants_claiming(conn, display=display, pnid=pnid)
        by_pnid = {r["id"] for r in rows if pnid and str(r["pnid"] or "") == pnid}
        by_display = {
            r["id"] for r in rows
            if display and normalize_display_number(r["whatsapp_number"]) == display
        }
        active = {r["id"]: bool(r["is_active"]) for r in rows}

        if by_pnid:
            claimants = sorted(by_pnid | by_display)
            if len(claimants) > 1:
                return RoutingResolution(None, "phone_number_id", "ambiguous_assignment", claimants)
            tid = claimants[0]
            if not active.get(tid):
                return RoutingResolution(None, "phone_number_id", "tenant_inactive", claimants)
            return RoutingResolution(tid, "phone_number_id", candidates=claimants)

        if by_display:
            claimants = sorted(by_display)
            if len(claimants) > 1:
                return RoutingResolution(None, "display_number", "ambiguous_assignment", claimants)
            tid = claimants[0]
            if not active.get(tid):
                return RoutingResolution(None, "display_number", "tenant_inactive", claimants)
            owner_pnid = next((str(r["pnid"] or "") for r in rows if r["id"] == tid), "")
            warning = "phone_number_id_mismatch" if (pnid and owner_pnid and owner_pnid != pnid) else ""
            return RoutingResolution(tid, "display_number", warning, claimants)

        return _resolve_legacy_override(conn, display=display, pnid=pnid)
    finally:
        if owned:
            conn.close()


def _resolve_legacy_override(conn, *, display: str, pnid: str) -> RoutingResolution:
    keys = [k for k in {display, display.lstrip("+"), pnid} if k]
    rows = conn.execute(
        text(
            "SELECT DISTINCT value FROM tenant_overrides "
            "WHERE override_type = 'phone_mapping' AND key IN :keys"
        ).bindparams(bindparam("keys", expanding=True)),
        {"keys": keys},
    ).fetchall()
    targets = sorted({int(r[0]) for r in rows if str(r[0]).strip().isdigit()})
    if not targets:
        return RoutingResolution(None, "none", "unassigned_number")
    if len(targets) > 1:
        return RoutingResolution(None, "legacy_override", "ambiguous_assignment", targets)
    tid = targets[0]
    owner = conn.execute(
        text("SELECT id, is_active FROM tenants WHERE id = :tid"),
        {"tid": tid},
    ).mappings().first()
    if not owner or not owner["is_active"]:
        return RoutingResolution(None, "legacy_override", "tenant_inactive", targets)
    # Reached only when NO tenant's Admin assignment claims this number or ID,
    # so the row cannot contradict Admin. Admin reassignment deletes these rows.
    return RoutingResolution(tid, "legacy_override", "legacy_override_in_use", targets)


def log_resolution_failure(res: RoutingResolution, display_number: str | None, phone_number_id: str | None) -> None:
    logger.critical(
        "TENANT_RESOLUTION_FAILED reason=%s source=%s receiver=%s phone_number_id=%s candidates=%s — "
        "message will NOT be routed to any tenant",
        res.reason, res.source, mask(display_number), mask(phone_number_id), res.candidates,
    )


# ─────────────────────────────────────────
# Outbound
# ─────────────────────────────────────────

def _global_phone_number_id() -> str:
    return normalize_phone_number_id(
        os.getenv("WHATSAPP_PHONE_NUMBER_ID") or os.getenv("META_PHONE_NUMBER_ID", "")
    )


def outbound_phone_number_id_for_tenant(tenant_id: int, *, conn=None) -> str | None:
    """The Phone Number ID ``tenant_id`` is authorised to send from.

    * its own assigned ID, if no other tenant also claims it;
    * else the global env ID, only if no *other* tenant owns that number;
    * else OUTBOUND_BLOCKED_PHONE_NUMBER_ID (send must refuse, not fall back).
    Returns None only when nothing is configured anywhere.
    """
    conn, owned = _connect(conn)
    try:
        row = conn.execute(
            text(f"SELECT {_pnid_expr(conn)} AS pnid FROM tenants WHERE id = :tid"),
            {"tid": tenant_id},
        ).mappings().first()
        if not row:
            return OUTBOUND_BLOCKED_PHONE_NUMBER_ID
        own = normalize_phone_number_id(row["pnid"])
        candidate = own or _global_phone_number_id()
        if not candidate:
            return None
        owners = {r["id"] for r in _tenants_claiming(conn, pnid=candidate)}
        if owners - {tenant_id}:
            logger.critical(
                "OUTBOUND_BLOCKED tenant=%s phone_number_id=%s is assigned to tenant(s) %s",
                tenant_id, mask(candidate), sorted(owners - {tenant_id}),
            )
            return OUTBOUND_BLOCKED_PHONE_NUMBER_ID
        return candidate
    finally:
        if owned:
            conn.close()


def outbound_number_conflict(tenant_id: int | None, phone_number_id: str | None) -> list[int]:
    """Tenants other than ``tenant_id`` that own ``phone_number_id`` (empty = allowed)."""
    pnid = normalize_phone_number_id(phone_number_id)
    if tenant_id is None or not pnid:
        return []
    conn, owned = _connect(None)
    try:
        return sorted({r["id"] for r in _tenants_claiming(conn, pnid=pnid)} - {int(tenant_id)})
    finally:
        if owned:
            conn.close()
