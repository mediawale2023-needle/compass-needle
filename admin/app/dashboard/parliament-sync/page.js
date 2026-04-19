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
        active:            { label: 'Confirmed',    bg: '#dcfce7', color: '#166534' },
        auto_matched:      { label: 'Auto-matched', bg: '#dcfce7', color: '#166534' },
        needs_review:      { label: 'Needs Review', bg: '#fef9c3', color: '#854d0e' },
        unmatched:         { label: 'Unmatched',    bg: '#fee2e2', color: '#991b1b' },
        pending:           { label: 'Pending',      bg: '#f1f5f9', color: '#475569' },
        error:             { label: 'Error',        bg: '#fee2e2', color: '#991b1b' },
        already_confirmed: { label: 'Confirmed',    bg: '#dcfce7', color: '#166534' },
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

// ─── Parliament Data Drawer ──────────────────────────────────────────────────

const DATA_TABS = [
    { key: 'questions', label: 'Questions' },
    { key: 'debates',   label: 'Debates' },
    { key: 'pmbs',      label: 'PMBs' },
    { key: 'zero_hour', label: 'Zero Hour' },
];

function QTypeChip({ type }) {
    if (!type) return null;
    const label = type.charAt(0).toUpperCase() + type.slice(1).toLowerCase();
    const isStarred = type.toLowerCase() === 'starred';
    return (
        <span style={{
            display: 'inline-block', padding: '1px 7px', borderRadius: 6,
            fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.04em',
            background: isStarred ? '#fef9c3' : '#f1f5f9',
            color: isStarred ? '#854d0e' : '#475569',
        }}>
            {label}
        </span>
    );
}

function DataDrawer({ tenant, onClose, onToast }) {
    const [activeTab, setActiveTab]   = useState('questions');
    const [records, setRecords]       = useState([]);
    const [counts, setCounts]         = useState({});
    const [total, setTotal]           = useState(0);
    const [loading, setLoading]       = useState(false);
    const [page, setPage]             = useState(0);
    const [backfilling, setBackfilling] = useState(false);
    const PAGE_SIZE = 30;

    const loadRecords = useCallback(async (tab, pg) => {
        setLoading(true);
        try {
            const d = await apiGet(
                `/api/admin/parliament/data/${tenant.tenant_id}?data_type=${tab}&limit=${PAGE_SIZE}&offset=${pg * PAGE_SIZE}`
            );
            setRecords(d.records || []);
            setTotal(d.total || 0);
        } catch (e) {
            onToast(e.message || 'Failed to load records', 'error');
        }
        setLoading(false);
    }, [tenant.tenant_id, onToast]);

    // Load counts for all 4 tabs once
    useEffect(() => {
        const fetchCounts = async () => {
            const results = {};
            await Promise.all(DATA_TABS.map(async ({ key }) => {
                try {
                    const d = await apiGet(`/api/admin/parliament/data/${tenant.tenant_id}?data_type=${key}&limit=1&offset=0`);
                    results[key] = d.total || 0;
                } catch { results[key] = 0; }
            }));
            setCounts(results);
        };
        fetchCounts();
    }, [tenant.tenant_id]);

    useEffect(() => {
        setPage(0);
        loadRecords(activeTab, 0);
    }, [activeTab, loadRecords]);

    const triggerBackfill = async () => {
        setBackfilling(true);
        try {
            const r = await apiPost(`/api/admin/parliament/backfill/${tenant.tenant_id}`, {});
            onToast(`Backfill started for ${tenant.mp_name} — check back in ~30s`);
            setTimeout(() => loadRecords(activeTab, page), 35000);
        } catch (e) {
            onToast(e.message || 'Backfill failed to start', 'error');
        }
        setBackfilling(false);
    };

    const totalPages = Math.ceil(total / PAGE_SIZE);
    const hasData = Object.values(counts).some(c => c > 0);

    return (
        <>
            {/* Backdrop */}
            <div
                onClick={onClose}
                style={{
                    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.25)',
                    zIndex: 1000, backdropFilter: 'blur(2px)',
                }}
            />

            {/* Drawer panel */}
            <div style={{
                position: 'fixed', top: 0, right: 0, bottom: 0, width: 720,
                background: 'white', zIndex: 1001, boxShadow: '-4px 0 32px rgba(0,0,0,0.12)',
                display: 'flex', flexDirection: 'column', overflow: 'hidden',
            }}>
                {/* Drawer header */}
                <div style={{
                    padding: '20px 24px', borderBottom: '1px solid #e2ebe5',
                    display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
                    flexShrink: 0,
                }}>
                    <div>
                        <div style={{ fontSize: '1rem', fontWeight: 700, color: '#1a2e28' }}>
                            {tenant.mp_name || tenant.tenant_name}
                        </div>
                        <div style={{ fontSize: '0.78rem', color: '#6b7f76', marginTop: 2 }}>
                            {tenant.constituency}
                            {tenant.state ? ` · ${tenant.state}` : ''}
                            {tenant.parliament_member_id
                                ? <> · <a href={`https://sansad.in/ls/members/${tenant.parliament_member_id}`}
                                    target="_blank" rel="noreferrer"
                                    style={{ color: '#006a4d', textDecoration: 'none', fontWeight: 600 }}>
                                    mpsno {tenant.parliament_member_id} ↗
                                  </a></>
                                : null
                            }
                        </div>
                    </div>
                    <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                        <button
                            onClick={triggerBackfill}
                            disabled={backfilling}
                            style={{
                                padding: '7px 14px', borderRadius: 8, border: 'none', cursor: 'pointer',
                                background: backfilling ? '#e2ebe5' : '#006a4d',
                                color: backfilling ? '#94a3b8' : 'white',
                                fontSize: '0.78rem', fontWeight: 600,
                            }}>
                            {backfilling ? 'Starting…' : '↓ Backfill Data'}
                        </button>
                        <button
                            onClick={onClose}
                            style={{
                                width: 32, height: 32, borderRadius: 8,
                                border: '1px solid #e2ebe5', background: 'white',
                                cursor: 'pointer', fontSize: '1rem', color: '#6b7f76',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                fontWeight: 700,
                            }}>
                            ✕
                        </button>
                    </div>
                </div>

                {/* Data type tabs */}
                <div style={{
                    display: 'flex', gap: 0, borderBottom: '1px solid #e2ebe5',
                    padding: '0 24px', flexShrink: 0,
                }}>
                    {DATA_TABS.map(({ key, label }) => {
                        const count = counts[key] ?? '…';
                        const active = activeTab === key;
                        return (
                            <button
                                key={key}
                                onClick={() => setActiveTab(key)}
                                style={{
                                    padding: '12px 18px', border: 'none', background: 'none',
                                    cursor: 'pointer', fontSize: '0.82rem', fontWeight: 600,
                                    color: active ? '#006a4d' : '#6b7f76',
                                    borderBottom: active ? '2px solid #006a4d' : '2px solid transparent',
                                    marginBottom: -1,
                                    display: 'flex', alignItems: 'center', gap: 6,
                                }}>
                                {label}
                                <span style={{
                                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                                    minWidth: 20, height: 18, padding: '0 5px',
                                    borderRadius: 99, fontSize: '0.65rem', fontWeight: 700,
                                    background: active ? '#006a4d' : '#e2ebe5',
                                    color: active ? 'white' : '#6b7f76',
                                }}>
                                    {count}
                                </span>
                            </button>
                        );
                    })}
                </div>

                {/* Records area */}
                <div style={{ flex: 1, overflow: 'auto', padding: '0 0 16px' }}>
                    {loading ? (
                        <div style={{ padding: 40, textAlign: 'center', color: '#6b7f76', fontSize: '0.85rem' }}>
                            Loading…
                        </div>
                    ) : records.length === 0 ? (
                        <div style={{ padding: 40, textAlign: 'center' }}>
                            <div style={{ color: '#94a3b8', fontSize: '0.88rem', marginBottom: 10 }}>
                                No {activeTab.replace('_', ' ')} found.
                            </div>
                            {!hasData && (
                                <div style={{ fontSize: '0.78rem', color: '#6b7f76' }}>
                                    Run <strong>Backfill Data</strong> above to scrape this MP's 18th Lok Sabha record from sansad.in.
                                </div>
                            )}
                        </div>
                    ) : (
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                            <thead>
                                <tr style={{ background: '#f8faf9', position: 'sticky', top: 0 }}>
                                    {activeTab === 'questions' && (
                                        <>
                                            <Th>Session</Th>
                                            <Th>Q No.</Th>
                                            <Th>Type</Th>
                                            <Th w={260}>Subject</Th>
                                            <Th w={160}>Ministry</Th>
                                            <Th>Date</Th>
                                        </>
                                    )}
                                    {activeTab === 'debates' && (
                                        <>
                                            <Th>Session</Th>
                                            <Th w={300}>Topic</Th>
                                            <Th w={180}>Bill Reference</Th>
                                            <Th>Date</Th>
                                        </>
                                    )}
                                    {activeTab === 'pmbs' && (
                                        <>
                                            <Th>Session</Th>
                                            <Th>Bill No.</Th>
                                            <Th w={280}>Title</Th>
                                            <Th>Status</Th>
                                            <Th>Introduced</Th>
                                        </>
                                    )}
                                    {activeTab === 'zero_hour' && (
                                        <>
                                            <Th>Session</Th>
                                            <Th w={380}>Subject</Th>
                                            <Th>Date</Th>
                                        </>
                                    )}
                                </tr>
                            </thead>
                            <tbody>
                                {records.map((r, i) => (
                                    <tr key={i} style={{ borderBottom: '1px solid #f0f4f2' }}>
                                        {activeTab === 'questions' && (
                                            <>
                                                <Td muted>{r.session_name || '—'}</Td>
                                                <Td mono>{r.question_number || '—'}</Td>
                                                <Td><QTypeChip type={r.question_type} /></Td>
                                                <Td w={260}>{r.subject || '—'}</Td>
                                                <Td w={160} muted>{r.ministry || '—'}</Td>
                                                <Td muted>{formatDate(r.date_asked)}</Td>
                                            </>
                                        )}
                                        {activeTab === 'debates' && (
                                            <>
                                                <Td muted>{r.session_name || '—'}</Td>
                                                <Td w={300}>{r.topic || '—'}</Td>
                                                <Td w={180} muted>{r.bill_reference || '—'}</Td>
                                                <Td muted>{formatDate(r.date)}</Td>
                                            </>
                                        )}
                                        {activeTab === 'pmbs' && (
                                            <>
                                                <Td muted>{r.session_name || '—'}</Td>
                                                <Td mono>{r.bill_number || '—'}</Td>
                                                <Td w={280}>{r.title || '—'}</Td>
                                                <Td>
                                                    <span style={{
                                                        display: 'inline-block', padding: '1px 8px', borderRadius: 6,
                                                        fontSize: '0.68rem', fontWeight: 600,
                                                        background: '#f1f5f9', color: '#475569',
                                                    }}>
                                                        {r.current_status || 'Introduced'}
                                                    </span>
                                                </Td>
                                                <Td muted>{formatDate(r.date_introduced)}</Td>
                                            </>
                                        )}
                                        {activeTab === 'zero_hour' && (
                                            <>
                                                <Td muted>{r.session_name || '—'}</Td>
                                                <Td w={380}>{r.subject || '—'}</Td>
                                                <Td muted>{formatDate(r.date)}</Td>
                                            </>
                                        )}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>

                {/* Pagination footer */}
                {totalPages > 1 && (
                    <div style={{
                        padding: '12px 24px', borderTop: '1px solid #e2ebe5',
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        flexShrink: 0, background: 'white',
                    }}>
                        <span style={{ fontSize: '0.75rem', color: '#6b7f76' }}>
                            {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
                        </span>
                        <div style={{ display: 'flex', gap: 8 }}>
                            <PaginBtn disabled={page === 0} onClick={() => { const p = page - 1; setPage(p); loadRecords(activeTab, p); }}>← Prev</PaginBtn>
                            <PaginBtn disabled={page >= totalPages - 1} onClick={() => { const p = page + 1; setPage(p); loadRecords(activeTab, p); }}>Next →</PaginBtn>
                        </div>
                    </div>
                )}
            </div>
        </>
    );
}

// Small table helpers
function Th({ children, w }) {
    return (
        <th style={{
            padding: '8px 14px', textAlign: 'left', fontSize: '0.67rem',
            fontWeight: 700, color: '#6b7f76', textTransform: 'uppercase',
            letterSpacing: '0.07em', borderBottom: '1px solid #e2ebe5',
            whiteSpace: 'nowrap', maxWidth: w || undefined,
        }}>{children}</th>
    );
}

function Td({ children, muted, mono, w }) {
    return (
        <td style={{
            padding: '9px 14px', color: muted ? '#6b7f76' : '#1a2e28',
            fontFamily: mono ? 'monospace' : 'inherit',
            fontSize: mono ? '0.82rem' : '0.8rem',
            maxWidth: w || undefined,
            overflow: 'hidden', textOverflow: 'ellipsis',
            whiteSpace: w ? 'nowrap' : undefined,
            verticalAlign: 'top',
        }}>{children}</td>
    );
}

function PaginBtn({ children, disabled, onClick }) {
    return (
        <button
            onClick={onClick}
            disabled={disabled}
            style={{
                padding: '5px 14px', borderRadius: 7, border: '1px solid #e2ebe5',
                background: 'white', fontSize: '0.75rem', fontWeight: 600,
                color: disabled ? '#94a3b8' : '#1a2e28', cursor: disabled ? 'default' : 'pointer',
            }}>
            {children}
        </button>
    );
}

// ─── Row-level action panel ──────────────────────────────────────────────────

function SyncRow({ tenant, onRefresh, onToast, onViewData }) {
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
                {confirmed && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {/* View Data button */}
                        <button
                            onClick={() => onViewData(tenant)}
                            style={{
                                padding: '6px 14px', borderRadius: 8, border: '1px solid #e2ebe5',
                                background: 'white', color: '#006a4d', fontSize: '0.78rem',
                                fontWeight: 600, cursor: 'pointer', textAlign: 'left',
                                display: 'flex', alignItems: 'center', gap: 6,
                            }}>
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>
                            </svg>
                            View Records
                        </button>
                        {!candidate && (
                            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                                <span style={{ fontSize: '0.72rem', color: '#6b7f76' }}>
                                    mpsno {tenant.parliament_member_id}
                                </span>
                                <button onClick={() => confirm(prompt('Enter new mpsno to override:'))}
                                    style={{ fontSize: '0.72rem', color: '#6b7f76', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}>
                                    Change
                                </button>
                            </div>
                        )}
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
    const [toast, setToast]         = useState(null);
    const [drawerTenant, setDrawerTenant] = useState(null);

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

            {/* Data drawer */}
            {drawerTenant && (
                <DataDrawer
                    tenant={drawerTenant}
                    onClose={() => setDrawerTenant(null)}
                    onToast={showToast}
                />
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
                <StatCard label="Total MPs"    value={stats.total}        color="#1a2e28" />
                <StatCard label="Confirmed"    value={stats.confirmed}    color="#006a4d" />
                <StatCard label="Needs Review" value={stats.needs_review} color="#d97706" />
                <StatCard label="Unmatched"    value={stats.unmatched}    color="#dc2626" />
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
                                    onViewData={setDrawerTenant}
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
                Confirmed MPs show a <strong>View Records</strong> button to preview scraped data.
            </p>
        </div>
    );
}
