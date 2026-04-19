'use client';
import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost, apiPatch } from '@/lib/api';

// ─── Helpers ────────────────────────────────────────────────────────────────

function formatDate(iso) {
    if (!iso) return '—';
    try { return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }); }
    catch { return iso; }
}

function ConfidenceBar({ value }) {
    const pct = Math.min(100, Math.max(0, value || 0));
    const color = pct >= 85 ? '#006a4d' : pct >= 60 ? '#d97706' : '#dc2626';
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ flex: 1, height: 5, background: '#e2ebe5', borderRadius: 99, overflow: 'hidden' }}>
                <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 99, transition: 'width 0.4s' }} />
            </div>
            <span style={{ fontSize: '0.72rem', fontWeight: 600, color, minWidth: 30 }}>{pct.toFixed(0)}%</span>
        </div>
    );
}

function StatusBadge({ status }) {
    const map = {
        active:        { label: 'Confirmed',     bg: '#dcfce7', color: '#166534' },
        auto_matched:  { label: 'Auto-matched',  bg: '#dcfce7', color: '#166534' },
        needs_review:  { label: 'Needs Review',  bg: '#fef9c3', color: '#854d0e' },
        unmatched:     { label: 'Unmatched',     bg: '#fee2e2', color: '#991b1b' },
        pending:       { label: 'Pending',       bg: '#f1f5f9', color: '#475569' },
        error:         { label: 'Error',         bg: '#fee2e2', color: '#991b1b' },
        already_confirmed: { label: 'Confirmed', bg: '#dcfce7', color: '#166534' },
    };
    const s = map[status] || map.pending;
    return (
        <span style={{
            display: 'inline-block', padding: '2px 10px', borderRadius: 99,
            fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.03em',
            background: s.bg, color: s.color,
        }}>
            {s.label}
        </span>
    );
}

// ─── Row-level action panel ──────────────────────────────────────────────────

function SyncRow({ tenant, onRefresh, onToast }) {
    const [manualId, setManualId]   = useState('');
    const [saving, setSaving]       = useState(false);
    const [resolving, setResolving] = useState(false);

    const confirm = async (memberId) => {
        if (!memberId?.trim()) { onToast('Enter a valid sansad.in mpsno', 'error'); return; }
        setSaving(true);
        try {
            await apiPatch(`/api/admin/parliament/sync/${tenant.tenant_id}/confirm`, { member_id: memberId.trim() });
            onToast(`Confirmed mpsno ${memberId} for ${tenant.mp_name}`, 'success');
            onRefresh();
        } catch (e) {
            onToast(e.message || 'Failed to confirm', 'error');
        }
        setSaving(false);
    };

    const resolveOne = async () => {
        setResolving(true);
        try {
            await apiPost(`/api/admin/parliament/sync/${tenant.tenant_id}/resolve`, {});
            onToast(`Resolving ${tenant.mp_name} — refresh in a moment`, 'success');
            setTimeout(onRefresh, 4000);
        } catch (e) {
            onToast(e.message || 'Failed to start resolution', 'error');
        }
        setResolving(false);
    };

    const s = tenant.parliament_sync_status;
    const confirmed = s === 'active' || s === 'auto_matched';
    const candidate = tenant.candidate;

    return (
        <tr style={{ borderBottom: '1px solid #f0f4f2' }}>
            {/* MP */}
            <td style={{ padding: '12px 16px', verticalAlign: 'top' }}>
                <div style={{ fontWeight: 600, color: '#1a2e28', fontSize: '0.88rem' }}>{tenant.mp_name || tenant.tenant_name}</div>
                <div style={{ fontSize: '0.75rem', color: '#6b7f76', marginTop: 2 }}>{tenant.constituency}{tenant.state ? ` · ${tenant.state}` : ''}</div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: 2, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{tenant.house?.replace('_', ' ')}</div>
            </td>

            {/* Status */}
            <td style={{ padding: '12px 16px', verticalAlign: 'top' }}>
                <StatusBadge status={s} />
                {tenant.parliament_last_synced && (
                    <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: 4 }}>
                        {formatDate(tenant.parliament_last_synced)}
                    </div>
                )}
            </td>

            {/* Member ID */}
            <td style={{ padding: '12px 16px', verticalAlign: 'top' }}>
                {tenant.parliament_member_id
                    ? <a href={`https://sansad.in/ls/members/${tenant.parliament_member_id}`} target="_blank" rel="noreferrer"
                        style={{ fontFamily: 'monospace', fontSize: '0.85rem', color: '#006a4d', fontWeight: 600, textDecoration: 'none' }}>
                        {tenant.parliament_member_id}
                        <svg style={{ display: 'inline', marginLeft: 4, verticalAlign: 'middle' }} width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                    </a>
                    : <span style={{ color: '#94a3b8', fontSize: '0.8rem' }}>—</span>
                }
            </td>

            {/* Confidence / Candidate */}
            <td style={{ padding: '12px 16px', verticalAlign: 'top', minWidth: 200 }}>
                {candidate ? (
                    <div>
                        <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#1a2e28' }}>{candidate.matched_name}</div>
                        <div style={{ fontSize: '0.72rem', color: '#6b7f76', marginBottom: 6 }}>
                            {candidate.matched_constituency} · {candidate.matched_state} · {candidate.party}
                        </div>
                        <ConfidenceBar value={candidate.confidence} />
                    </div>
                ) : confirmed ? (
                    <span style={{ fontSize: '0.75rem', color: '#006a4d' }}>✓ Identity confirmed</span>
                ) : (
                    <span style={{ color: '#94a3b8', fontSize: '0.8rem' }}>—</span>
                )}
            </td>

            {/* Actions */}
            <td style={{ padding: '12px 16px', verticalAlign: 'top', minWidth: 260 }}>
                {confirmed && !candidate && (
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <span style={{ fontSize: '0.75rem', color: '#6b7f76' }}>
                            mpsno {tenant.parliament_member_id}
                        </span>
                        <button onClick={() => confirm(prompt('Enter new mpsno to override:'))}
                            style={{ fontSize: '0.72rem', color: '#6b7f76', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}>
                            Change
                        </button>
                    </div>
                )}

                {s === 'needs_review' && candidate && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        <button
                            onClick={() => confirm(candidate.member_id)}
                            disabled={saving}
                            style={{
                                padding: '6px 14px', borderRadius: 8, border: 'none', cursor: 'pointer',
                                background: saving ? '#e2ebe5' : '#006a4d', color: saving ? '#94a3b8' : 'white',
                                fontSize: '0.78rem', fontWeight: 600,
                            }}>
                            {saving ? 'Confirming…' : `✓ Confirm mpsno ${candidate.member_id}`}
                        </button>
                        <div style={{ display: 'flex', gap: 6 }}>
                            <input
                                value={manualId}
                                onChange={e => setManualId(e.target.value)}
                                placeholder="Override mpsno"
                                style={{
                                    flex: 1, padding: '5px 10px', borderRadius: 7, fontSize: '0.78rem',
                                    border: '1px solid #e2ebe5', outline: 'none', color: '#1a2e28',
                                }}
                            />
                            <button
                                onClick={() => confirm(manualId)}
                                disabled={saving || !manualId.trim()}
                                style={{
                                    padding: '5px 12px', borderRadius: 7, border: '1px solid #e2ebe5',
                                    background: 'white', color: '#1a2e28', fontSize: '0.78rem', cursor: 'pointer',
                                }}>
                                Save
                            </button>
                        </div>
                    </div>
                )}

                {(s === 'unmatched' || s === 'error' || s === 'pending') && !candidate && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        <div style={{ display: 'flex', gap: 6 }}>
                            <input
                                value={manualId}
                                onChange={e => setManualId(e.target.value)}
                                placeholder="Enter mpsno from sansad.in"
                                style={{
                                    flex: 1, padding: '5px 10px', borderRadius: 7, fontSize: '0.78rem',
                                    border: '1px solid #e2ebe5', outline: 'none', color: '#1a2e28',
                                }}
                            />
                            <button
                                onClick={() => confirm(manualId)}
                                disabled={saving || !manualId.trim()}
                                style={{
                                    padding: '5px 12px', borderRadius: 7, border: 'none',
                                    background: '#006a4d', color: 'white', fontSize: '0.78rem',
                                    fontWeight: 600, cursor: 'pointer', opacity: manualId.trim() ? 1 : 0.5,
                                }}>
                                Save
                            </button>
                        </div>
                        <button
                            onClick={resolveOne}
                            disabled={resolving}
                            style={{
                                padding: '5px 12px', borderRadius: 7, border: '1px solid #e2ebe5',
                                background: 'white', color: '#006a4d', fontSize: '0.75rem',
                                fontWeight: 600, cursor: 'pointer',
                            }}>
                            {resolving ? 'Starting…' : '↻ Try Auto-Resolve'}
                        </button>
                    </div>
                )}
            </td>
        </tr>
    );
}

// ─── Summary stats ───────────────────────────────────────────────────────────

function StatCard({ label, value, color }) {
    return (
        <div style={{
            background: 'white', borderRadius: 12, padding: '16px 20px',
            border: '1px solid #e2ebe5', flex: 1,
        }}>
            <div style={{ fontSize: '1.6rem', fontWeight: 700, color }}>{value}</div>
            <div style={{ fontSize: '0.75rem', color: '#6b7f76', marginTop: 2 }}>{label}</div>
        </div>
    );
}

// ─── Main page ───────────────────────────────────────────────────────────────

export default function ParliamentSyncPage() {
    const [data, setData]           = useState(null);
    const [loading, setLoading]     = useState(true);
    const [resolving, setResolving] = useState(false);
    const [filter, setFilter]       = useState('all');
    const [toast, setToast]         = useState(null); // { msg, type }

    const showToast = (msg, type = 'success') => {
        setToast({ msg, type });
        setTimeout(() => setToast(null), 4000);
    };

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const d = await apiGet('/api/admin/parliament/sync/status');
            setData(d);
        } catch (e) {
            showToast(e.message || 'Failed to load sync status', 'error');
        }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    const runResolveAll = async () => {
        setResolving(true);
        try {
            await apiPost('/api/admin/parliament/sync/resolve-all', {});
            showToast('Auto-resolution running in background — refresh in 30s');
            setTimeout(load, 30000);
        } catch (e) {
            showToast(e.message || 'Failed to start resolution', 'error');
        }
        setResolving(false);
    };

    const tenants = data?.tenants || [];

    const stats = {
        total:        tenants.length,
        confirmed:    tenants.filter(t => t.parliament_sync_status === 'active' || t.parliament_sync_status === 'auto_matched').length,
        needs_review: tenants.filter(t => t.parliament_sync_status === 'needs_review').length,
        unmatched:    tenants.filter(t => ['unmatched', 'error', 'pending'].includes(t.parliament_sync_status)).length,
    };

    const filtered = filter === 'all' ? tenants
        : filter === 'confirmed'    ? tenants.filter(t => t.parliament_sync_status === 'active' || t.parliament_sync_status === 'auto_matched')
        : filter === 'needs_review' ? tenants.filter(t => t.parliament_sync_status === 'needs_review')
        : tenants.filter(t => ['unmatched', 'error', 'pending'].includes(t.parliament_sync_status));

    return (
        <div>
            {/* Toast */}
            {toast && (
                <div style={{
                    position: 'fixed', top: 20, right: 20, zIndex: 9999,
                    padding: '10px 18px', borderRadius: 10, fontSize: '0.85rem', fontWeight: 500,
                    background: toast.type === 'error' ? '#fef2f2' : '#f0fdf4',
                    color: toast.type === 'error' ? '#991b1b' : '#166534',
                    border: `1px solid ${toast.type === 'error' ? '#fecaca' : '#bbf7d0'}`,
                    boxShadow: '0 4px 16px rgba(0,0,0,0.08)',
                }}>
                    {toast.msg}
                </div>
            )}

            {/* Action bar */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
                <div>
                    <p style={{ margin: 0, fontSize: '0.82rem', color: '#6b7f76' }}>
                        Maps each subscribed MP to their sansad.in parliament member ID (18th Lok Sabha).
                        Auto-resolve runs fuzzy matching · confidence ≥ 85% auto-confirms.
                    </p>
                </div>
                <div style={{ display: 'flex', gap: 10, flexShrink: 0 }}>
                    <button
                        onClick={load}
                        style={{
                            padding: '8px 16px', borderRadius: 9, border: '1px solid #e2ebe5',
                            background: 'white', color: '#1a2e28', fontSize: '0.82rem',
                            fontWeight: 600, cursor: 'pointer',
                        }}>
                        ↻ Refresh
                    </button>
                    <button
                        onClick={runResolveAll}
                        disabled={resolving}
                        style={{
                            padding: '8px 20px', borderRadius: 9, border: 'none',
                            background: resolving ? '#e2ebe5' : '#006a4d',
                            color: resolving ? '#6b7f76' : 'white',
                            fontSize: '0.82rem', fontWeight: 700, cursor: resolving ? 'default' : 'pointer',
                        }}>
                        {resolving ? 'Running…' : '⚡ Run Auto-Resolve for All'}
                    </button>
                </div>
            </div>

            {/* Stats */}
            <div style={{ display: 'flex', gap: 14, marginBottom: 24 }}>
                <StatCard label="Total MPs"     value={stats.total}        color="#1a2e28" />
                <StatCard label="Confirmed"     value={stats.confirmed}    color="#006a4d" />
                <StatCard label="Needs Review"  value={stats.needs_review} color="#d97706" />
                <StatCard label="Unmatched"     value={stats.unmatched}    color="#dc2626" />
            </div>

            {/* Filter tabs */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 16 }}>
                {[
                    { key: 'all',          label: `All  (${stats.total})` },
                    { key: 'confirmed',    label: `Confirmed  (${stats.confirmed})` },
                    { key: 'needs_review', label: `Needs Review  (${stats.needs_review})` },
                    { key: 'unmatched',    label: `Action Required  (${stats.unmatched})` },
                ].map(tab => (
                    <button
                        key={tab.key}
                        onClick={() => setFilter(tab.key)}
                        style={{
                            padding: '6px 16px', borderRadius: 8, border: 'none', cursor: 'pointer',
                            fontSize: '0.78rem', fontWeight: 600,
                            background: filter === tab.key ? '#006a4d' : '#f1f5f9',
                            color:      filter === tab.key ? 'white' : '#475569',
                        }}>
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Table */}
            <div style={{ background: 'white', borderRadius: 14, border: '1px solid #e2ebe5', overflow: 'hidden' }}>
                {loading ? (
                    <div style={{ padding: 48, textAlign: 'center', color: '#6b7f76', fontSize: '0.88rem' }}>
                        Loading sync status…
                    </div>
                ) : filtered.length === 0 ? (
                    <div style={{ padding: 48, textAlign: 'center', color: '#6b7f76', fontSize: '0.88rem' }}>
                        {filter === 'all' ? 'No MP tenants found.' : 'No MPs in this category.'}
                    </div>
                ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ background: '#f8faf9', borderBottom: '1px solid #e2ebe5' }}>
                                {['MP / Constituency', 'Status', 'Member ID', 'Matched Candidate', 'Action'].map(h => (
                                    <th key={h} style={{
                                        padding: '10px 16px', textAlign: 'left',
                                        fontSize: '0.7rem', fontWeight: 700, color: '#6b7f76',
                                        textTransform: 'uppercase', letterSpacing: '0.08em',
                                    }}>{h}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map(t => (
                                <SyncRow
                                    key={t.tenant_id}
                                    tenant={t}
                                    onRefresh={load}
                                    onToast={showToast}
                                />
                            ))}
                        </tbody>
                    </table>
                )}
            </div>

            {/* Footer hint */}
            <p style={{ marginTop: 14, fontSize: '0.72rem', color: '#94a3b8' }}>
                Member IDs link to sansad.in profiles. To look up an mpsno manually, search{' '}
                <a href="https://sansad.in/ls/members" target="_blank" rel="noreferrer"
                    style={{ color: '#006a4d' }}>sansad.in/ls/members</a>.
            </p>
        </div>
    );
}
