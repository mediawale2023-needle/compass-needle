'use client';

import { useEffect, useState } from 'react';
import { apiGet, apiPost } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { Modal, SEAT_STATUS, formatDate } from './shared';

const SUPER_ROLES = ['super_admin', 'sysadmin'];

function ReassignModal({ tenantId, current, onClose, onDone }) {
    const [partners, setPartners] = useState(null); // null loading, 'error' unavailable
    const [target, setTarget] = useState(''); // '' = nothing chosen, 'direct', or a partner id
    const [reason, setReason] = useState('');
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        let cancelled = false;
        apiGet('/api/admin/partners/selectable')
            .then((r) => { if (!cancelled) setPartners(r.partners || []); })
            .catch(() => { if (!cancelled) setPartners('error'); });
        return () => { cancelled = true; };
    }, []);

    const options = Array.isArray(partners) ? partners.filter((p) => p.id !== current.partner_id) : [];
    const ready = target !== '' && reason.trim().length >= 5 && !saving;

    async function submit(e) {
        e.preventDefault();
        setSaving(true);
        setError('');
        try {
            await apiPost(`/api/admin/partners/tenants/${tenantId}/attribution/reassign`, {
                partner_id: target === 'direct' ? null : Number(target),
                reason: reason.trim(),
            });
            onDone();
        } catch (err) {
            setError(err.message || 'Could not change the attribution.');
            setSaving(false);
        }
    }

    return (
        <Modal title="Change tenant attribution" titleId="reassign-title" onClose={saving ? () => {} : onClose}>
            <form onSubmit={submit}>
                <p style={{ margin: '0 0 12px', fontSize: '0.85rem' }}>
                    The current partner loses access to this tenant immediately and the new one gains it in the same step.
                    This is recorded in the audit log with your name and the reason below.
                </p>
                {partners === 'error' ? (
                    <div role="alert" className="toast toast-error" style={{ position: 'static' }}>Partner list unavailable. Close and try again.</div>
                ) : partners === null ? (
                    <div className="admin-skeleton-row" aria-busy="true" aria-label="Loading partners" />
                ) : (
                    <div className="form-row">
                        <label className="form-label" htmlFor="reassign-target">New acquisition source *</label>
                        <select id="reassign-target" className="form-input" value={target} onChange={(e) => setTarget(e.target.value)}>
                            <option value="">— select —</option>
                            {current.channel === 'partner' && <option value="direct">Direct — Needle</option>}
                            {options.map((p) => <option key={p.id} value={p.id}>Partner — {p.name}</option>)}
                        </select>
                    </div>
                )}
                <div className="form-row">
                    <label className="form-label" htmlFor="reassign-reason">Reason * <span style={{ fontWeight: 400 }}>(min 5 characters)</span></label>
                    <textarea id="reassign-reason" className="form-input" rows={3} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
                </div>
                {error && <div role="alert" className="toast toast-error" style={{ position: 'static', margin: '8px 0' }}>{error}</div>}
                <div className="modal-footer">
                    <button type="submit" className="btn-primary" disabled={!ready}>{saving ? 'Saving…' : 'Change attribution'}</button>
                    <button type="button" className="btn-secondary" onClick={onClose} disabled={saving}>Cancel</button>
                </div>
            </form>
        </Modal>
    );
}

/** Staff-only acquisition card for Account 360. `acquisition === null` means the lookup failed. */
export default function AcquisitionPanel({ tenantId, acquisition, history = [], onChanged }) {
    const user = useAuth()?.user;
    const [changing, setChanging] = useState(false);
    const canChange = SUPER_ROLES.includes(user?.role);

    if (!acquisition) {
        return (
            <section id="acquisition" className="glass-panel" style={{ marginBottom: 16, padding: 16 }} aria-label="Acquisition">
                <div className="account360-kicker">Acquisition</div>
                <p role="status" style={{ margin: '6px 0 0', fontSize: '0.85rem' }}>Acquisition details are unavailable right now. Reload to try again.</p>
            </section>
        );
    }

    const isPartner = acquisition.channel === 'partner';
    const access = acquisition.access_status ? (SEAT_STATUS[acquisition.access_status] || { label: acquisition.access_status, badge: 'badge-slate' }) : null;

    return (
        <section id="acquisition" className="glass-panel" style={{ marginBottom: 16, padding: 16 }} aria-label="Acquisition">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
                <div>
                    <div className="account360-kicker">Acquisition</div>
                    <strong style={{ display: 'block', fontSize: '1.05rem', margin: '4px 0' }}>
                        {isPartner ? `Partner — ${acquisition.partner_name || `#${acquisition.partner_id}`}` : 'Direct — Needle'}
                    </strong>
                    {!acquisition.recorded && <small>Created before acquisition tracking; treated as direct.</small>}
                </div>
                {canChange && (
                    <button type="button" className="btn-secondary" onClick={() => setChanging(true)}>Change attribution</button>
                )}
            </div>
            {acquisition.recorded && (
                <dl style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, margin: '12px 0 0' }}>
                    <div><dt className="account360-kicker">Attributed</dt><dd style={{ margin: 0 }}>{formatDate(acquisition.attributed_at)}</dd></div>
                    <div><dt className="account360-kicker">Attributed by</dt><dd style={{ margin: 0 }}>{acquisition.attributed_by || '—'}</dd></div>
                    {isPartner && access && (
                        <div><dt className="account360-kicker">Partner access</dt><dd style={{ margin: 0 }}><span className={`badge badge-dot ${access.badge}`}>{access.label}</span></dd></div>
                    )}
                </dl>
            )}
            {history.filter((h) => h.event === 'reassigned').length > 0 && (
                <details style={{ marginTop: 12 }}>
                    <summary style={{ cursor: 'pointer', fontSize: '0.82rem' }}>Attribution changes</summary>
                    <ul style={{ margin: '8px 0 0', paddingLeft: 18, fontSize: '0.8rem' }}>
                        {history.filter((h) => h.event === 'reassigned').map((h) => (
                            <li key={h.id}>
                                {formatDate(h.created_at)} · {h.changed_by || 'unknown'}: {h.from_channel === 'partner' ? `partner #${h.from_partner_id}` : 'direct'} → {h.to_channel === 'partner' ? `partner #${h.to_partner_id}` : 'direct'} — {h.reason}
                            </li>
                        ))}
                    </ul>
                </details>
            )}
            {changing && (
                <ReassignModal tenantId={tenantId} current={acquisition} onClose={() => setChanging(false)}
                    onDone={() => { setChanging(false); onChanged?.(); }} />
            )}
        </section>
    );
}
