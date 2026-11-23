"""Overview dashboard builders.

Two deliberately separate data-access modes share the grouping rules but
nothing else:

* ``build_mp_overview``      - the MP Overview aggregate. This is the logic that
  used to live inline in ``api_router.dashboard_overview``, moved verbatim.
  Its output is pinned by ``tests/test_dashboard_overview_golden.py``.
* ``build_partner_overview`` - counts-only aggregate for partner (political
  consultancy) seats. It runs its OWN queries that never select citizen
  contact data, complaint text, case references, government reference numbers,
  notes, assignee names or free-text locations. It is NOT the MP response with
  fields stripped afterwards, and it is not routed anywhere in this PR.

The helpers that touch ``api_router`` internals (briefcase grouping, geography
correction, DB lookups) are injected through ``OverviewDeps`` instead of
imported, which avoids a circular import and lets the route keep resolving them
at call time (existing tests patch ``api_router._dashboard_govt_sync_map``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from modules.synthetic_cases import sql_is_live


@dataclass
class OverviewDeps:
    q: Callable[..., list]
    q_one: Callable[..., Any]
    group_bundles: Callable[..., list]
    coerce_iso: Callable[[Any], Any]
    coerce_datetime: Callable[[Any], Any]
    utcnow: Callable[[], datetime]
    # MP mode only
    prepare_case: Callable[..., dict] | None = None
    govt_sync_map: Callable[..., dict] | None = None
    inbound_map: Callable[..., dict] | None = None
    latest_citizen_activity: Callable[..., Any] | None = None
    parse_meta: Callable[[Any], dict] | None = None
    # Partner mode only
    assembly_belongs: Callable[..., bool] | None = None


ACTIVE_STATUSES = {"new", "pending", "pending_review", "awaiting_location", "in_progress"}
BUCKET_ORDER = ["needs_review", "needs_location", "sync_issues", "govt_updates", "ready_to_file"]
_FILED_STATUSES = {
    "submitted", "registered", "forwarded", "under_review",
    "escalated", "resolved", "rejected", "disposed",
}


# --------------------------------------------------------------------------
# Pure helpers (moved verbatim from api_router)
# --------------------------------------------------------------------------

def is_govt_filed(case: dict) -> bool:
    if str(case.get("govt_reference_number") or "").strip():
        return True
    return str(case.get("govt_status") or "").strip().lower() in _FILED_STATUSES


def govt_stage(case: dict) -> str:
    status = str(case.get("govt_status") or "").strip().lower()
    if status in {"resolved", "disposed"}:
        return "resolved"
    if status in {"under_review", "escalated", "forwarded"}:
        return "department"
    if is_govt_filed(case):
        return "registered"
    if status == "pending_staff_submit":
        return "ready"
    return "none"


def action_for_case(case: dict, sync: dict | None = None) -> dict | None:
    status = str(case.get("status") or "").strip().lower()
    sync_state = (sync or {}).get("govt_sync_state")
    if status == "pending_review":
        return {"label": "Review case", "href": f"/dashboard/sansadx?case_id={case.get('id')}"}
    if status == "awaiting_location":
        return {"label": "Add location", "href": f"/dashboard/sansadx?case_id={case.get('id')}"}
    if sync_state in {"failed", "verification", "inconclusive"}:
        return {"label": "Review sync issue", "href": f"/dashboard/sansadx?case_id={case.get('id')}"}
    if sync_state == "changed":
        return {"label": "View govt update", "href": f"/dashboard/sansadx?case_id={case.get('id')}"}
    if not is_govt_filed(case):
        if status in {"resolved", "completed", "closed", "irrelevant", "offensive"}:
            return None
        return {"label": "File grievance", "href": f"/dashboard/sansadx?case_id={case.get('id')}"}
    if str(case.get("govt_status") or "").strip().lower() in {"resolved", "disposed", "rejected"}:
        return None
    return {"label": "Check portal status", "href": f"/dashboard/sansadx?case_id={case.get('id')}"}


def state_label(case: dict, sync: dict | None = None) -> str:
    status = str(case.get("status") or "").strip().lower()
    stage = govt_stage(case)
    sync_state = (sync or {}).get("govt_sync_state")
    if status == "pending_review":
        return "Needs Review"
    if status == "awaiting_location":
        return "Needs Location"
    if sync_state in {"failed", "verification", "inconclusive"}:
        return "Sync Issue"
    if sync_state == "changed":
        return "Govt Update"
    if stage == "ready":
        return "Ready to File"
    if stage == "registered":
        return "Govt Registered"
    if stage == "department":
        return "Department Action"
    if status in {"new", "pending"} and not case.get("assigned_to"):
        return "Unassigned"
    if status == "resolved":
        return "Resolved"
    return (case.get("status") or "New").replace("_", " ").title()


def issue_label(case: dict) -> str:
    return (
        case.get("problem_subdomain")
        or case.get("problem_domain")
        or case.get("category")
        or "General grievance"
    )


def location_label(case: dict) -> str:
    parts = [
        str(case.get("location") or "").strip(),
        str(case.get("assembly") or "").strip(),
    ]
    return " · ".join([p for p in parts if p and p.lower() != "unknown"]) or "Location pending"


def time_ago(value, deps: OverviewDeps) -> str:
    dt = deps.coerce_datetime(value)
    if not dt:
        return ""
    # prepare_case / coerce_iso hand back tz-aware "Z" strings, but utcnow()
    # is naive UTC - normalise to naive UTC before subtracting.
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    diff = max(deps.utcnow() - dt, timedelta(seconds=0))
    minutes = int(diff.total_seconds() // 60)
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    return f"{diff.days}d"


# --------------------------------------------------------------------------
# MP mode (moved verbatim from api_router.dashboard_overview)
# --------------------------------------------------------------------------

def build_mp_overview(tid: int, user: dict, deps: OverviewDeps) -> dict:
    tenant_row = deps.q_one(
        "SELECT constituency FROM tenants WHERE id = :tid",
        {"tid": tid},
    ) or {}
    tenant_constituency = tenant_row.get("constituency")

    raw_cases = deps.q(
        f"""
        SELECT c.id, c.case_ref, c.user_phone, c.category, c.problem_domain,
               c.problem_subdomain, c.convergence_program_type, c.status, c.raw_message,
               COALESCE(c.location, c.case_metadata->>'matched_value') AS location,
               COALESCE(c.assembly, c.case_metadata->>'assembly_constituency') AS assembly,
               c.case_metadata, c.is_critical, c.created_at, c.updated_at,
               c.response_to_citizen, c.notes_for_staff, c.assigned_to,
               c.govt_status, c.govt_reference_number, c.govt_status_updated_at,
               c.govt_portal_id, c.govt_department, p.portal_name AS govt_portal_name,
               p.state AS govt_portal_state
        FROM cases c
        LEFT JOIN govt_portals p ON p.id = c.govt_portal_id
        WHERE c.tenant_id = :tid
          AND (c.is_deleted = false OR c.is_deleted IS NULL)
          AND {sql_is_live("c")}
        ORDER BY c.created_at DESC, c.id DESC
        """,
        {"tid": tid},
    )

    bundles = deps.group_bundles(raw_cases, sort="newest")
    filing_ids = []
    for bundle in bundles:
        anchor = bundle["anchor"]
        filing_ids.append(anchor.get("govt_filing_case_id") or anchor.get("id"))
    sync_map = deps.govt_sync_map(tid, [cid for cid in filing_ids if cid is not None])

    # Attention Queue ordering is driven by the newest inbound citizen message
    # across every case in a thread, so the map covers all members, not just
    # the anchors. Tenant-scoped in the query as well as by the id list.
    member_case_ids = [
        member.get("id")
        for bundle in bundles
        for member in bundle["members_by_received"]
        if member.get("id") is not None
    ]
    inbound_map = deps.inbound_map(tid, member_case_ids)

    counts = {
        "needs_review": 0,
        "needs_location": 0,
        "sync_issues": 0,
        "govt_updates": 0,
        "ready_to_file": 0,
    }
    bucketed = []
    stage_counts = {"ready": 0, "registered": 0, "department": 0, "resolved": 0}
    location_counts: dict[str, int] = {}
    issue_counts: dict[str, dict] = {}
    unassigned_count = 0
    active_statuses = {"new", "pending", "pending_review", "awaiting_location", "in_progress"}

    for bundle in bundles:
        anchor = deps.prepare_case(dict(bundle["anchor"]), tenant_constituency, tid, 0)
        members = bundle["members_by_received"]
        sync = sync_map.get(anchor.get("govt_filing_case_id") or anchor.get("id"), {})
        member_statuses = {str(m.get("status") or "").strip().lower() for m in members}
        anchor_status = str(anchor.get("status") or "").strip().lower()
        stage = govt_stage(anchor)
        if stage in stage_counts:
            stage_counts[stage] += 1
        if any(str(m.get("assigned_to") or "").strip() == "" and str(m.get("status") or "").strip().lower() in active_statuses for m in members):
            unassigned_count += 1

        loc = str(anchor.get("location") or "").strip()
        if loc:
            location_counts[loc] = location_counts.get(loc, 0) + 1
        issue = issue_label(anchor)
        bucket = issue_counts.setdefault(issue, {"title": issue, "count": 0, "locations": {}})
        bucket["count"] += 1
        if loc:
            bucket["locations"][loc] = bucket["locations"].get(loc, 0) + 1

        if "pending_review" in member_statuses:
            attention_bucket = "needs_review"
        elif "awaiting_location" in member_statuses:
            attention_bucket = "needs_location"
        elif sync.get("govt_sync_state") in {"failed", "verification", "inconclusive"}:
            attention_bucket = "sync_issues"
        elif sync.get("govt_changed"):
            attention_bucket = "govt_updates"
        elif anchor_status in active_statuses and not is_govt_filed(anchor):
            attention_bucket = "ready_to_file"
        else:
            attention_bucket = None

        if attention_bucket:
            counts[attention_bucket] += 1
            action = action_for_case(anchor, sync)
            thread_count = int(anchor.get("thread_case_count") or 1)
            latest_activity_at, has_inbound = deps.latest_citizen_activity(members, inbound_map)
            govt_status_raw = str(anchor.get("govt_status") or "").strip()
            govt_status_label = govt_status_raw.replace("_", " ").title() if govt_status_raw else "Not filed"
            assigned_to = str(anchor.get("assigned_to") or "").strip()
            channel = "WhatsApp" if str(anchor.get("user_phone") or "").strip() else "—"
            bucketed.append({
                "id": anchor.get("id"),
                "case_ref": anchor.get("case_ref") or f"#{anchor.get('id')}",
                "thread_count": thread_count,
                "channel": channel,
                "meta": " · ".join([
                    "Thread" if thread_count > 1 else "Case",
                    f"{thread_count} complaint" + ("" if thread_count == 1 else "s"),
                    time_ago(latest_activity_at, deps),
                ]).strip(" ·"),
                "message": anchor.get("raw_message") or "",
                "issue": issue_label(anchor),
                "location": location_label(anchor),
                "state": state_label(anchor, sync),
                "needle_status": (anchor.get("status") or "new").replace("_", " ").title(),
                "govt_status": govt_status_label,
                "assigned_to": assigned_to or None,
                "recency": time_ago(latest_activity_at, deps),
                "action": action,
                "critical": bool(anchor.get("is_critical")),
                "bucket": attention_bucket,
                "created_at": anchor.get("created_at"),
                "updated_at": anchor.get("updated_at"),
                "latest_citizen_message_at": deps.coerce_iso(latest_activity_at),
                "has_inbound_citizen_message": has_inbound,
                "_sort_at": latest_activity_at,
            })

    # Newest citizen message first. Deliberately NOT keyed on bucket priority,
    # status, creation time or case id: a ten-day-old case that just received a
    # WhatsApp message outranks one created minutes ago. Cases with no inbound
    # ledger row fall back to their newest creation time (see
    # latest_citizen_activity) so legacy rows still place sensibly.
    # datetime.min keeps rows with no usable timestamp at the bottom instead of
    # raising on the None comparison, and case id descending breaks ties so the
    # order is deterministic for identical timestamps.
    bucketed.sort(
        key=lambda row: (row.get("_sort_at") or datetime.min, int(row.get("id") or 0)),
        reverse=True,
    )
    for row in bucketed:
        row.pop("_sort_at", None)
    attention_queue = bucketed[:12]

    sync_issue_rows = [row for row in bucketed if row["bucket"] == "sync_issues"][:3]
    issue_pressure = []
    for item in sorted(issue_counts.values(), key=lambda r: (-r["count"], r["title"]))[:4]:
        top_locations = sorted(item["locations"].items(), key=lambda kv: (-kv[1], kv[0]))[:2]
        issue_pressure.append({
            "title": item["title"],
            "place": " + ".join([name for name, _count in top_locations]) or "Location pending",
            "count": item["count"],
        })

    letter_new = deps.q_one(
        "SELECT COUNT(*) AS cnt FROM letterbox WHERE tenant_id = :tid AND direction = 'inbox' "
        "AND status IN ('new', 'needs_review', 'processing') "
        "AND (is_deleted = false OR is_deleted IS NULL)",
        {"tid": tid},
    ) or {}
    draft_pending = deps.q_one(
        "SELECT COUNT(*) AS cnt FROM letterbox WHERE tenant_id = :tid AND direction = 'outbox' "
        "AND status = 'drafted' "
        "AND (is_deleted = false OR is_deleted IS NULL)",
        {"tid": tid},
    ) or {}

    history_rows = deps.q(
        """
        SELECT id, activity_type, title, metadata, created_at
        FROM activity_history
        WHERE tenant_id = :tid
        ORDER BY created_at DESC
        LIMIT 4
        """,
        {"tid": tid},
    )
    movement = []
    for row in history_rows:
        meta = deps.parse_meta(row.get("metadata"))
        href = meta.get("href") or meta.get("url") or meta.get("path") or "/dashboard/archives"
        if not isinstance(href, str) or not href.startswith("/"):
            href = "/dashboard/archives"
        movement.append({
            "id": row.get("id"),
            "time": time_ago(row.get("created_at"), deps),
            "item": row.get("title") or str(row.get("activity_type") or "Activity").replace("_", " ").title(),
            "tone": "green" if row.get("activity_type") in {"draft_letter", "draft_question"} else "rust",
            "href": href,
        })

    hotspots = [
        {"name": name, "count": count}
        for name, count in sorted(location_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    ]

    return {
        "seat": tenant_constituency or user.get("constituency") or "Constituency",
        "date_label": "Today",
        "attention_counts": [
            {"key": "needs_review", "label": "Needs review", "value": counts["needs_review"], "tone": "red"},
            {"key": "needs_location", "label": "Needs location", "value": counts["needs_location"], "tone": "amber"},
            {"key": "sync_issues", "label": "Sync issues", "value": counts["sync_issues"], "tone": "rust"},
            {"key": "govt_updates", "label": "Govt updates", "value": counts["govt_updates"], "tone": "green"},
            {"key": "ready_to_file", "label": "Ready to file", "value": counts["ready_to_file"], "tone": "green"},
        ],
        "attention_queue": attention_queue,
        "government_tracking": {
            "ready": stage_counts["ready"],
            "registered": stage_counts["registered"],
            "department": stage_counts["department"],
            "resolved": stage_counts["resolved"],
            "sync_issues": counts["sync_issues"],
            "issues": [
                f"{item['case_ref']} · {item['state']}" for item in sync_issue_rows
            ],
        },
        "constituency_pressure": hotspots,
        "issue_pressure": issue_pressure,
        "office_pending": [
            {"key": "letters", "label": f"{int(letter_new.get('cnt') or 0)} new letters need intake review", "href": "/dashboard/letterbox"},
            {"key": "drafts", "label": f"{int(draft_pending.get('cnt') or 0)} drafts awaiting MP approval", "href": "/dashboard/letterbox?direction=outbox&status=drafted"},
            {"key": "unassigned", "label": f"{unassigned_count} unassigned cases need owner", "href": "/dashboard/sansadx"},
        ],
        "recent_movement": movement,
        "validation": {
            "thread_count": len(bundles),
            "attention_bucket_total": sum(counts.values()),
            "bucket_precedence": list(BUCKET_ORDER),
            "govt_updates_definition": "latest persisted govt_submission_log action=status_polled with payload.changed=true",
            "case_unit": "Briefcase CASE/THREAD rows, not individual complaint members",
            "pagination_independent": True,
        },
    }


# --------------------------------------------------------------------------
# Partner mode: separate, minimal-column, counts-only data access
# --------------------------------------------------------------------------

# Columns the partner queries are allowed to read. Anything else (user_phone,
# raw_message, case_ref, response_to_citizen, notes_for_staff, assigned_to
# value, govt_reference_number value, free-text location, case_metadata blob)
# is never selected. tests/test_dashboard_overview_partner.py asserts this on
# the SQL text that is actually executed.
PARTNER_CASE_SQL = """
    SELECT c.id, c.category, c.problem_domain, c.problem_subdomain, c.status,
           c.govt_status, c.govt_status_updated_at, c.created_at,
           COALESCE(c.assembly, c.case_metadata->>'assembly_constituency') AS assembly,
           c.case_metadata->>'contact_thread_id' AS thread_id,
           CASE WHEN c.govt_reference_number IS NOT NULL
                 AND TRIM(c.govt_reference_number) <> '' THEN 1 ELSE 0 END AS govt_has_ref,
           CASE WHEN c.assigned_to IS NULL OR TRIM(c.assigned_to) = '' THEN 1 ELSE 0 END AS unassigned
    FROM cases c
    WHERE c.tenant_id = :tid
      AND (c.is_deleted = false OR c.is_deleted IS NULL)
      AND {live}
    ORDER BY c.created_at DESC, c.id DESC
"""

# Latest govt-sync event per filing case. Selects the action and a single
# boolean extracted from the payload - never the payload itself.
PARTNER_SYNC_SQL = """
    SELECT id, case_id, action, changed FROM (
        SELECT l.id, l.case_id, l.action,
               CASE WHEN LOWER(CAST(l.payload->>'changed' AS TEXT)) IN ('true', '1', 't')
                    THEN 1 ELSE 0 END AS changed,
               ROW_NUMBER() OVER (PARTITION BY l.case_id ORDER BY l.id DESC) AS rn
        FROM govt_submission_log l
        WHERE l.tenant_id = :tid
          AND l.action IN ('status_polled', 'status_check_failed',
                           'status_check_needs_verification', 'status_check_inconclusive')
    ) ranked
    WHERE rn = 1
"""
# NOTE: a single pass with ROW_NUMBER() (portable to Postgres and SQLite). The earlier correlated
# "id = (SELECT MAX(id) ...)" form was quadratic in poll events per case: ~12s vs ~0.2s on a
# 200k-row log, which exceeded the partner UI's 15s request timeout.

PARTNER_LETTER_SQL = (
    "SELECT COUNT(*) AS cnt FROM letterbox WHERE tenant_id = :tid AND direction = :direction "
    "AND status IN ({statuses}) AND (is_deleted = false OR is_deleted IS NULL)"
)

_SYNC_ACTION_STATE = {
    "status_check_failed": "failed",
    "status_check_needs_verification": "verification",
    "status_check_inconclusive": "inconclusive",
}


def _partner_case_row(row: dict) -> dict:
    """Shape a minimal row so the shared Briefcase grouping can bundle it.

    The grouping helper only needs the thread id (read from case_metadata) and
    the govt ranking fields. The thread id is a server-generated opaque token;
    the reference-number slot receives a constant sentinel when a reference
    exists, so the number itself never enters memory.
    """
    out = dict(row)
    thread_id = str(row.get("thread_id") or "").strip()
    out["case_metadata"] = {"contact_thread_id": thread_id} if thread_id else None
    out["govt_reference_number"] = "1" if row.get("govt_has_ref") else None
    return out


def build_partner_overview(tid: int, deps: OverviewDeps) -> dict:
    """Counts-only Overview aggregate for a partner's view of one tenant.

    ``tid`` must come from the partner seat resolver (``_owned_seat``), never
    from the request. No individual or anonymised case rows are returned.
    """
    tenant_row = deps.q_one(
        "SELECT constituency FROM tenants WHERE id = :tid", {"tid": tid}
    ) or {}
    tenant_constituency = tenant_row.get("constituency")

    rows = deps.q(PARTNER_CASE_SQL.format(live=sql_is_live("c")), {"tid": tid})
    bundles = deps.group_bundles([_partner_case_row(r) for r in rows], sort="newest")

    filing_ids = {
        b["anchor"].get("govt_filing_case_id") or b["anchor"].get("id") for b in bundles
    }
    sync_by_case: dict[int, dict] = {}
    for srow in deps.q(PARTNER_SYNC_SQL, {"tid": tid}):
        if srow.get("case_id") not in filing_ids:
            continue
        action = srow.get("action") or ""
        if action == "status_polled":
            sync_by_case[srow["case_id"]] = {
                "govt_sync_state": "changed" if srow.get("changed") else "ok",
                "govt_changed": bool(srow.get("changed")),
            }
        else:
            sync_by_case[srow["case_id"]] = {
                "govt_sync_state": _SYNC_ACTION_STATE.get(action, "inconclusive"),
                "govt_changed": False,
            }

    counts = {key: 0 for key in BUCKET_ORDER}
    govt = {
        "ready": 0, "submitted": 0, "registered": 0, "forwarded": 0,
        "awaiting_action": 0, "resolved": 0, "disposed": 0, "rejected": 0,
        "awaiting_verification": 0, "sync_issues": 0,
    }
    govt_status_key = {
        "pending_staff_submit": "ready", "submitted": "submitted", "registered": "registered",
        "forwarded": "forwarded", "under_review": "awaiting_action", "escalated": "awaiting_action",
        "resolved": "resolved", "disposed": "disposed", "rejected": "rejected",
    }
    area_counts: dict[str, int] = {}
    belongs_cache: dict[str, bool] = {}
    issue_counts: dict[str, int] = {}
    unassigned = 0

    for bundle in bundles:
        anchor = bundle["anchor"]
        members = bundle["members_by_received"]
        sync = sync_by_case.get(anchor.get("govt_filing_case_id") or anchor.get("id"), {})
        member_statuses = {str(m.get("status") or "").strip().lower() for m in members}
        anchor_status = str(anchor.get("status") or "").strip().lower()

        key = govt_status_key.get(str(anchor.get("govt_status") or "").strip().lower())
        if key:
            govt[key] += 1
        state = sync.get("govt_sync_state")
        if state == "verification":
            govt["awaiting_verification"] += 1
        if state in {"failed", "verification", "inconclusive"}:
            govt["sync_issues"] += 1

        if any(
            m.get("unassigned") and str(m.get("status") or "").strip().lower() in ACTIVE_STATUSES
            for m in members
        ):
            unassigned += 1

        assembly = str(anchor.get("assembly") or "").strip()
        if assembly and assembly not in belongs_cache:
            # assembly_belongs scans the whole geography index, so ask once per distinct name.
            belongs_cache[assembly] = bool(
                assembly.lower() != "unknown"
                and tenant_constituency
                and deps.assembly_belongs(assembly, tenant_constituency)
            )
        if assembly and belongs_cache[assembly]:
            area_counts[assembly] = area_counts.get(assembly, 0) + 1
        issue = issue_label(anchor)
        issue_counts[issue] = issue_counts.get(issue, 0) + 1

        if "pending_review" in member_statuses:
            counts["needs_review"] += 1
        elif "awaiting_location" in member_statuses:
            counts["needs_location"] += 1
        elif state in {"failed", "verification", "inconclusive"}:
            counts["sync_issues"] += 1
        elif sync.get("govt_changed"):
            counts["govt_updates"] += 1
        elif anchor_status in ACTIVE_STATUSES and not is_govt_filed(anchor):
            counts["ready_to_file"] += 1

    letters_new = deps.q_one(
        PARTNER_LETTER_SQL.format(statuses="'new', 'needs_review', 'processing'"),
        {"tid": tid, "direction": "inbox"},
    ) or {}
    drafts_pending = deps.q_one(
        PARTNER_LETTER_SQL.format(statuses="'drafted'"),
        {"tid": tid, "direction": "outbox"},
    ) or {}

    return {
        "mode": "partner",
        "seat": tenant_constituency or "Constituency",
        "date_label": "Today",
        "attention_counts": [
            {"key": "needs_review", "label": "Needs review", "value": counts["needs_review"], "tone": "red"},
            {"key": "needs_location", "label": "Needs location", "value": counts["needs_location"], "tone": "amber"},
            {"key": "sync_issues", "label": "Sync issues", "value": counts["sync_issues"], "tone": "rust"},
            {"key": "govt_updates", "label": "Govt updates", "value": counts["govt_updates"], "tone": "green"},
            {"key": "ready_to_file", "label": "Ready to file", "value": counts["ready_to_file"], "tone": "green"},
        ],
        # Government-side outcomes only. Needle's internal resolution is a
        # different statistic and is intentionally not mixed in here.
        "government_tracking": govt,
        "constituency_pressure": [
            {"name": name, "count": count}
            for name, count in sorted(area_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        ],
        "issue_pressure": [
            {"title": title, "count": count}
            for title, count in sorted(issue_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:4]
        ],
        "office_pending": [
            {"key": "letters", "label": "New letters awaiting intake review", "value": int(letters_new.get("cnt") or 0)},
            {"key": "drafts", "label": "Drafts awaiting MP approval", "value": int(drafts_pending.get("cnt") or 0)},
            {"key": "unassigned", "label": "Cases needing an owner", "value": unassigned},
        ],
        "validation": {
            "thread_count": len(bundles),
            "attention_bucket_total": sum(counts.values()),
            "bucket_precedence": list(BUCKET_ORDER),
            "case_unit": "Briefcase CASE/THREAD rows, counted - never listed",
            "counts_only": True,
        },
    }
