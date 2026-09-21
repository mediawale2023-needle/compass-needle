"""Strict, tenant-scoped source ledger linking for future checkpoint integration.

Unlike the legacy best-effort helper, failures roll back the entire batch.
Call this with the same transaction that advances a checkpoint's state.
"""
from sqlalchemy import text


def link_sources_or_raise(session, *, tenant_id: int, case_id: int, source_ledger_ids):
    ids = tuple(source_ledger_ids)
    if tenant_id <= 0 or case_id <= 0 or not ids:
        raise ValueError("missing tenant, case or source IDs")
    if any(type(i) is not int or i <= 0 for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("invalid or repeated source IDs")
    case_tenant = session.execute(
        text("SELECT tenant_id FROM cases WHERE id = :case_id"),
        {"case_id": case_id},
    ).scalar_one_or_none()
    if case_tenant != tenant_id:
        raise ValueError("case does not belong to tenant")
    for source_id in ids:
        row = session.execute(
            text("""UPDATE wa_inbound_messages
                    SET case_id = :case_id
                    WHERE id = :source_id AND tenant_id = :tenant_id
                      AND (case_id IS NULL OR case_id = :case_id)
                    RETURNING id"""),
            {"case_id": case_id, "source_id": source_id, "tenant_id": tenant_id},
        ).one_or_none()
        if row is None:
            raise ValueError("source ledger missing, cross-tenant or linked elsewhere")
    return len(ids)
