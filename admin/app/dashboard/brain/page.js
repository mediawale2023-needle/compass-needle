'use client';
import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost } from '@/lib/api';

// ─── Source type colour mapping ───────────────────────────────────────────────
const SOURCE_COLORS = {
    pq_qa:           { bg: '#1e3a5f', border: '#3b82f6', label: 'PQ Q&A' },
    global_pq_qa:    { bg: '#1e2d5f', border: '#818cf8', label: 'Cross-MP PQ' },
    debate_speech:   { bg: '#1e3a2f', border: '#22c55e', label: 'Debate' },
    zero_hour:       { bg: '#2d1e3f', border: '#a855f7', label: 'Zero Hour' },
    const_overview:  { bg: '#1f2937', border: '#6b7280', label: 'Constituency' },
    const_challenge: { bg: '#3b1f1f', border: '#ef4444', label: 'Challenge' },
    const_priority:  { bg: '#1f3b2f', border: '#10b981', label: 'Priority' },
    const_political: { bg: '#1f2d3b', border: '#38bdf8', label: 'Political' },
    const_assembly:  { bg: '#1f2d3b', border: '#0ea5e9', label: 'Assembly' },
    const_economy:   { bg: '#1f3020', border: '#4ade80', label: 'Economy' },
    const_social:    { bg: '#2d2020', border: '#fb923c', label: 'Social' },
    const_culture:   { bg: '#1f1f30', border: '#818cf8', label: 'Culture' },
    const_fact:      { bg: '#1f1f1f', border: '#9ca3af', label: 'Fact' },
    case_summary:    { bg: '#3b2d1f', border: '#f59e0b', label: 'Grievance' },
    scheme:          { bg: '#1f3020', border: '#34d399', label: 'Scheme' },
    news:            { bg: '#1f2d3b', border: '#60a5fa', label: 'News' },
};

const SOURCE_TYPE_OPTIONS = Object.entries(SOURCE_COLORS).map(([k, v]) => ({
    value: k, label: v.label,
}));

function Badge({ sourceType }) {
    const c = SOURCE_COLORS[sourceType] || { bg: '#1f2937', border: '#6b7280', label: sourceType };
    return (
        <span style={{
            background: c.bg, border: `1px solid ${c.border}`,
            color: c.border, borderRadius: 4, padding: '1px 7px',
            fontSize: 11, fontWeight: 600, whiteSpace: 'nowrap',
        }}>
            {c.label}
        </span>
    );
}

function ScoreBar({ score }) {
    const pct = Math.round((score || 0) * 100);
    const color = pct >= 70 ? '#22c55e' : pct >= 45 ? '#f59e0b' : '#ef4444';
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
                flex: 1, height: 6, background: '#374151', borderRadius: 3, overflow: 'hidden',
            }}>
                <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3 }} />
            </div>
            <span style={{ fontSize: 11, color, minWidth: 32, textAlign: 'right' }}>{pct}%</span>
        </div>
    );
}

function ChunkCard({ chunk, index }) {
    const [expanded, setExpanded] = useState(false);
    return (
        <div style={{
            background: '#111827', border: '1px solid #1f2937',
            borderRadius: 8, padding: 16, marginBottom: 12,
        }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 8 }}>
                <span style={{ color: '#6b7280', fontSize: 13, minWidth: 24, fontWeight: 700 }}>
                    [{index}]
                </span>
                <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
                        <Badge sourceType={chunk.source_type} />
                        {chunk.ministry && (
                            <span style={{ fontSize: 11, color: '#9ca3af' }}>{chunk.ministry}</span>
                        )}
                        {chunk.date_ref && (
                            <span style={{ fontSize: 11, color: '#6b7280' }}>{chunk.date_ref}</span>
                        )}
                    </div>
                    <div style={{ color: '#e5e7eb', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
                        {chunk.title}
                    </div>
                    <div style={{ color: '#9ca3af', fontSize: 11, marginBottom: 6 }}>
                        {chunk.citation}
                    </div>
                    <ScoreBar score={chunk.score} />
                </div>
            </div>

            {/* Content preview */}
            <div style={{
                background: '#0d1117', borderRadius: 4, padding: '8px 12px',
                fontFamily: 'monospace', fontSize: 12, color: '#d1d5db',
                whiteSpace: 'pre-wrap', lineHeight: 1.6, marginTop: 8,
                maxHeight: expanded ? 'none' : 120, overflow: 'hidden',
                position: 'relative',
            }}>
                {chunk.content_preview}
                {!expanded && (chunk.content_preview || '').length >= 550 && (
                    <div style={{
                        position: 'absolute', bottom: 0, left: 0, right: 0,
                        background: 'linear-gradient(transparent, #0d1117)',
                        height: 40,
                    }} />
                )}
            </div>
            {(chunk.content_preview || '').length >= 550 && (
                <button
                    onClick={() => setExpanded(e => !e)}
                    style={{
                        background: 'none', border: 'none', color: '#3b82f6',
                        fontSize: 12, cursor: 'pointer', padding: '4px 0', marginTop: 4,
                    }}
                >
                    {expanded ? '▲ Collapse' : '▼ Show full preview'}
                </button>
            )}

            {/* Tags */}
            {chunk.topic_tags && chunk.topic_tags.length > 0 && (
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 8 }}>
                    {chunk.topic_tags.map(t => (
                        <span key={t} style={{
                            background: '#1f2937', color: '#6b7280',
                            fontSize: 10, padding: '2px 6px', borderRadius: 3,
                        }}>
                            {t}
                        </span>
                    ))}
                </div>
            )}
        </div>
    );
}

// ─── Stats panel ─────────────────────────────────────────────────────────────
function StatsPanel({ stats, loading }) {
    if (loading) return <div style={{ color: '#6b7280', fontSize: 13 }}>Loading stats…</div>;
    if (!stats) return null;

    const global = stats.global || {};
    const perTenant = stats.per_tenant || [];

    return (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
            <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, padding: 16 }}>
                <div style={{ color: '#6b7280', fontSize: 11, marginBottom: 4 }}>TOTAL CHUNKS</div>
                <div style={{ color: '#fff', fontSize: 28, fontWeight: 700 }}>
                    {(global.total_chunks || 0).toLocaleString()}
                </div>
                <div style={{ color: '#6b7280', fontSize: 11 }}>
                    Last indexed: {global.last_indexed ? global.last_indexed.slice(0, 16) : '—'}
                </div>
            </div>

            {Object.entries(global.per_source_type || {}).map(([st, info]) => {
                const c = SOURCE_COLORS[st] || { border: '#6b7280', label: st };
                return (
                    <div key={st} style={{
                        background: '#111827',
                        border: `1px solid ${c.border}20`,
                        borderLeft: `3px solid ${c.border}`,
                        borderRadius: 8, padding: 12,
                    }}>
                        <div style={{ color: c.border, fontSize: 10, marginBottom: 2 }}>{c.label || st}</div>
                        <div style={{ color: '#fff', fontSize: 20, fontWeight: 700 }}>{info.count}</div>
                        <div style={{ color: '#4b5563', fontSize: 10 }}>
                            {info.last_indexed ? info.last_indexed.slice(0, 10) : '—'}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

// ─── Reindex panel ────────────────────────────────────────────────────────────
function ReindexPanel({ tenants, onDone }) {
    const [tenantId, setTenantId] = useState('');
    const [rebuild, setRebuild] = useState(false);
    const [running, setRunning] = useState(false);
    const [jobId, setJobId] = useState(null);
    const [status, setStatus] = useState(null);

    const start = async () => {
        setRunning(true);
        setStatus(null);
        try {
            const url = tenantId
                ? `/api/admin/brain/reindex/${tenantId}`
                : '/api/admin/brain/reindex-all';
            const r = await apiPost(url, { rebuild });
            setJobId(r.job_id);
        } catch (e) {
            setStatus({ error: e.message });
            setRunning(false);
        }
    };

    // Poll job
    useEffect(() => {
        if (!jobId) return;
        const t = setInterval(async () => {
            try {
                const j = await apiGet(`/api/admin/brain/reindex/status/${jobId}`);
                if (j.status === 'done') {
                    setStatus(j);
                    setRunning(false);
                    setJobId(null);
                    clearInterval(t);
                    onDone && onDone();
                } else if (j.status === 'error') {
                    setStatus(j);
                    setRunning(false);
                    setJobId(null);
                    clearInterval(t);
                }
            } catch (_) {}
        }, 2500);
        return () => clearInterval(t);
    }, [jobId, onDone]);

    const selectedTenant = tenantId
        ? (tenants || []).find(t => String(t.tenant_id) === String(tenantId))?.mp_name || 'Selected tenant'
        : 'All MPs and shared sources';
    const summary = status?.summary || {};
    const updatedCount = summary.chunks_inserted ?? summary.rows_updated ?? summary.indexed ?? summary.total ?? null;

    return (
        <div style={{
            background: '#fff', border: '1px solid #e2ebe5',
            borderRadius: 14, padding: 22, boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
        }}>
            <div style={{
                display: 'flex', justifyContent: 'space-between', gap: 18,
                alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: 18,
            }}>
                <div style={{ maxWidth: 620 }}>
                    <div style={{
                        color: '#006a4d', fontSize: '0.72rem', fontWeight: 850,
                        textTransform: 'uppercase', letterSpacing: '0.12em',
                    }}>
                        Knowledge Refresh
                    </div>
                    <h2 style={{ margin: '7px 0 0', color: '#1a2e28', fontSize: '1.35rem', fontWeight: 900 }}>
                        Update the searchable knowledge base
                    </h2>
                    <p style={{ margin: '7px 0 0', color: '#6b7f76', fontSize: '0.86rem', lineHeight: 1.55 }}>
                        Refresh what Copilot and Drafter can retrieve from Parliament work, constituency profiles, cases, and schemes.
                    </p>
                </div>
                <div style={{
                    minWidth: 190, background: '#f8faf9', border: '1px solid #e2ebe5',
                    borderRadius: 12, padding: '12px 14px',
                }}>
                    <div style={{ color: '#6b7f76', fontSize: '0.72rem', fontWeight: 800 }}>Scope</div>
                    <div style={{ color: '#1a2e28', fontSize: '0.92rem', fontWeight: 850, marginTop: 5 }}>
                        {selectedTenant}
                    </div>
                </div>
            </div>

            <div style={{
                display: 'flex', gap: 12, alignItems: 'end', flexWrap: 'wrap',
            }}>
                <label style={{ display: 'grid', gap: 6, flex: '1 1 260px' }}>
                    <span style={{ color: '#4a635a', fontSize: '0.74rem', fontWeight: 750 }}>Refresh scope</span>
                    <select
                        value={tenantId}
                        onChange={e => setTenantId(e.target.value)}
                        className="form-input"
                        style={{ minHeight: 38 }}
                    >
                        <option value=''>All tenants</option>
                        {(tenants || []).map(t => (
                            <option key={t.tenant_id} value={t.tenant_id}>{t.mp_name}</option>
                        ))}
                    </select>
                </label>
                <label style={{
                    display: 'flex', alignItems: 'center', gap: 8, color: '#4a635a',
                    fontSize: '0.8rem', cursor: 'pointer', minHeight: 38,
                    padding: '0 4px', whiteSpace: 'nowrap',
                }}>
                    <input
                        type='checkbox'
                        checked={rebuild}
                        onChange={e => setRebuild(e.target.checked)}
                        style={{ accentColor: '#006a4d' }}
                    />
                    Full rebuild
                </label>
                <button
                    onClick={start}
                    disabled={running}
                    className="btn-primary"
                    style={{ minHeight: 38, padding: '9px 18px' }}
                >
                    {running ? 'Refreshing...' : 'Start Refresh'}
                </button>
            </div>

            <div style={{
                marginTop: 12, color: '#6b7f76', fontSize: '0.76rem',
                lineHeight: 1.5,
            }}>
                By default, refresh only updates content that changed. Use full rebuild when source formatting or extraction logic was repaired.
            </div>

            {status && (
                <div style={{
                    marginTop: 14, padding: '11px 14px',
                    background: status.error ? '#fff1f2' : '#f0fdf4',
                    border: `1px solid ${status.error ? '#fecdd3' : '#bbf7d0'}`,
                    borderRadius: 10, fontSize: '0.82rem',
                    color: status.error ? '#be123c' : '#15803d',
                    fontWeight: 650,
                }}>
                    {status.error
                        ? `Refresh could not start: ${status.error}`
                        : updatedCount != null
                        ? `Refresh complete. ${Number(updatedCount).toLocaleString()} records updated.`
                        : 'Refresh complete.'}
                </div>
            )}
        </div>
    );
}

// ─── Main playground ──────────────────────────────────────────────────────────
export default function BrainPlaygroundPage() {
    const [tenants, setTenants] = useState([]);
    const [stats, setStats] = useState(null);
    const [statsLoading, setStatsLoading] = useState(true);

    // Query form
    const [query, setQuery] = useState('');
    const [tenantId, setTenantId] = useState('');
    const [sourceTypes, setSourceTypes] = useState([]);
    const [ministry, setMinistry] = useState('');
    const [k, setK] = useState(12);
    const [includeGlobal, setIncludeGlobal] = useState(true);
    const [includeCrossMP, setIncludeCrossMP] = useState(false);

    // Results
    const [chunks, setChunks] = useState(null);
    const [searching, setSearching] = useState(false);
    const [error, setError] = useState('');

    const [activeTab, setActiveTab] = useState('playground'); // playground | stats | reindex

    const loadStats = useCallback(() => {
        setStatsLoading(true);
        apiGet('/api/admin/brain/stats')
            .then(d => setStats(d))
            .catch(() => {})
            .finally(() => setStatsLoading(false));
    }, []);

    useEffect(() => {
        apiGet('/api/admin/tenants')
            .then(d => setTenants(d.tenants || d || []))
            .catch(() => {});
        loadStats();
    }, [loadStats]);

    const runQuery = async () => {
        if (!query.trim()) return;
        setSearching(true);
        setError('');
        setChunks(null);
        try {
            const body = {
                query,
                k,
                include_global: includeGlobal,
                include_cross_mp: includeCrossMP,
            };
            if (tenantId) body.tenant_id = parseInt(tenantId);
            if (ministry) body.ministry = ministry;
            if (sourceTypes.length) body.source_types = sourceTypes;

            const r = await apiPost('/api/admin/brain/retrieve', body);
            setChunks(r.chunks || []);
        } catch (e) {
            setError(e.message || 'Retrieval failed');
        } finally {
            setSearching(false);
        }
    };

    const toggleSourceType = (st) => {
        setSourceTypes(prev =>
            prev.includes(st) ? prev.filter(x => x !== st) : [...prev, st]
        );
    };

    const TAB = (id, label) => (
        <button
            key={id}
            onClick={() => setActiveTab(id)}
            style={{
                background: activeTab === id ? '#1e40af' : 'transparent',
                color: activeTab === id ? '#fff' : '#9ca3af',
                border: activeTab === id ? '1px solid #3b82f6' : '1px solid transparent',
                borderRadius: 6, padding: '6px 16px', fontSize: 13,
                cursor: 'pointer', fontWeight: activeTab === id ? 600 : 400,
            }}
        >
            {label}
        </button>
    );

    return (
        <div style={{ padding: 32, maxWidth: 1100, margin: '0 auto', fontFamily: 'system-ui, sans-serif' }}>
            {/* Header */}
            <div style={{ marginBottom: 28 }}>
                <h1 style={{ color: '#fff', fontSize: 22, fontWeight: 700, margin: 0 }}>
                    Intelligence Engine
                </h1>
                <p style={{ color: '#6b7280', fontSize: 13, margin: '6px 0 0' }}>
                    National intelligence, knowledge readiness, and AI diagnostics for Copilot and Drafter.
                </p>
            </div>

            {/* Tabs */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 24, flexWrap: 'wrap' }}>
                {TAB('playground', 'Retrieval Diagnostics')}
                {TAB('stats', 'Memory Health')}
                {TAB('reindex', 'Knowledge Refresh')}
                {TAB('global', 'National Intelligence')}
            </div>

            {/* ── PLAYGROUND TAB ── */}
            {activeTab === 'playground' && (
                <div>
                    {/* Query input */}
                    <div style={{
                        background: '#111827', border: '1px solid #1f2937',
                        borderRadius: 10, padding: 20, marginBottom: 20,
                    }}>
                        <div style={{ marginBottom: 12 }}>
                            <label style={{ color: '#9ca3af', fontSize: 12, display: 'block', marginBottom: 6 }}>
                                QUERY (what the copilot/drafter would ask)
                            </label>
                            <div style={{ display: 'flex', gap: 10 }}>
                                <textarea
                                    value={query}
                                    onChange={e => setQuery(e.target.value)}
                                    placeholder='e.g. "drinking water quality in Khanapur Taluka" or "Ministry of Jal Shakti flood relief"'
                                    onKeyDown={e => { if (e.key === 'Enter' && e.metaKey) runQuery(); }}
                                    style={{
                                        flex: 1, background: '#1f2937', border: '1px solid #374151',
                                        color: '#e5e7eb', borderRadius: 6, padding: '10px 14px',
                                        fontSize: 14, resize: 'vertical', minHeight: 60,
                                        fontFamily: 'inherit',
                                    }}
                                />
                                <button
                                    onClick={runQuery}
                                    disabled={searching || !query.trim()}
                                    style={{
                                        background: searching ? '#374151' : '#1d4ed8',
                                        color: '#fff', border: 'none', borderRadius: 6,
                                        padding: '10px 22px', fontSize: 14,
                                        cursor: searching || !query.trim() ? 'not-allowed' : 'pointer',
                                        alignSelf: 'flex-end', whiteSpace: 'nowrap',
                                    }}
                                >
                                    {searching ? '⟳ Searching…' : 'Retrieve ⌘↵'}
                                </button>
                            </div>
                        </div>

                        {/* Filters row */}
                        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
                            <div>
                                <label style={{ color: '#6b7280', fontSize: 11, display: 'block', marginBottom: 4 }}>TENANT</label>
                                <select
                                    value={tenantId}
                                    onChange={e => setTenantId(e.target.value)}
                                    style={{
                                        background: '#1f2937', border: '1px solid #374151', color: '#e5e7eb',
                                        borderRadius: 6, padding: '6px 10px', fontSize: 12,
                                    }}
                                >
                                    <option value=''>— All / Global —</option>
                                    {tenants.map(t => (
                                        <option key={t.tenant_id || t.id} value={t.tenant_id || t.id}>
                                            {t.mp_name || t.name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label style={{ color: '#6b7280', fontSize: 11, display: 'block', marginBottom: 4 }}>MINISTRY FILTER</label>
                                <input
                                    value={ministry}
                                    onChange={e => setMinistry(e.target.value)}
                                    placeholder='e.g. Jal Shakti'
                                    style={{
                                        background: '#1f2937', border: '1px solid #374151', color: '#e5e7eb',
                                        borderRadius: 6, padding: '6px 10px', fontSize: 12, width: 160,
                                    }}
                                />
                            </div>
                            <div>
                                <label style={{ color: '#6b7280', fontSize: 11, display: 'block', marginBottom: 4 }}>TOP-K</label>
                                <input
                                    type='number' min={1} max={50} value={k}
                                    onChange={e => setK(Math.max(1, Math.min(50, parseInt(e.target.value) || 12)))}
                                    style={{
                                        background: '#1f2937', border: '1px solid #374151', color: '#e5e7eb',
                                        borderRadius: 6, padding: '6px 10px', fontSize: 12, width: 64,
                                    }}
                                />
                            </div>
                            <div style={{ display: 'flex', gap: 14 }}>
                                <label style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#9ca3af', fontSize: 12, cursor: 'pointer' }}>
                                    <input type='checkbox' checked={includeGlobal} onChange={e => setIncludeGlobal(e.target.checked)} style={{ accentColor: '#3b82f6' }} />
                                    Global (schemes)
                                </label>
                                <label style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#9ca3af', fontSize: 12, cursor: 'pointer' }}>
                                    <input type='checkbox' checked={includeCrossMP} onChange={e => setIncludeCrossMP(e.target.checked)} style={{ accentColor: '#a855f7' }} />
                                    Cross-MP
                                </label>
                            </div>
                        </div>

                        {/* Source type filter pills */}
                        <div style={{ marginTop: 12 }}>
                            <label style={{ color: '#6b7280', fontSize: 11, display: 'block', marginBottom: 6 }}>
                                SOURCE TYPES (empty = all)
                            </label>
                            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                                {SOURCE_TYPE_OPTIONS.map(({ value, label }) => {
                                    const active = sourceTypes.includes(value);
                                    const c = SOURCE_COLORS[value] || { border: '#6b7280' };
                                    return (
                                        <button
                                            key={value}
                                            onClick={() => toggleSourceType(value)}
                                            style={{
                                                background: active ? `${c.border}22` : '#1f2937',
                                                border: `1px solid ${active ? c.border : '#374151'}`,
                                                color: active ? c.border : '#6b7280',
                                                borderRadius: 4, padding: '3px 9px',
                                                fontSize: 11, cursor: 'pointer',
                                            }}
                                        >
                                            {label}
                                        </button>
                                    );
                                })}
                                {sourceTypes.length > 0 && (
                                    <button
                                        onClick={() => setSourceTypes([])}
                                        style={{
                                            background: 'none', border: '1px solid #374151',
                                            color: '#ef4444', borderRadius: 4,
                                            padding: '3px 9px', fontSize: 11, cursor: 'pointer',
                                        }}
                                    >
                                        Clear
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Error */}
                    {error && (
                        <div style={{
                            background: '#2d1f1f', border: '1px solid #ef444455',
                            borderRadius: 8, padding: 12, color: '#ef4444', fontSize: 13, marginBottom: 16,
                        }}>
                            {error}
                        </div>
                    )}

                    {/* Empty state */}
                    {!searching && chunks === null && !error && (
                        <div style={{
                            background: '#0d1117', border: '1px dashed #1f2937',
                            borderRadius: 10, padding: 48, textAlign: 'center',
                        }}>
                            <div style={{ fontSize: 36, marginBottom: 12 }}>🧠</div>
                            <div style={{ color: '#4b5563', fontSize: 14 }}>
                                Enter a query to see what the brain would retrieve.
                            </div>
                            <div style={{ color: '#374151', fontSize: 12, marginTop: 8 }}>
                                Try: "drinking water contamination" · "farmer subsidy schemes" · "road infrastructure"
                            </div>
                        </div>
                    )}

                    {/* Results */}
                    {chunks !== null && (
                        <div>
                            <div style={{
                                display: 'flex', justifyContent: 'space-between',
                                alignItems: 'center', marginBottom: 14,
                            }}>
                                <div style={{ color: '#9ca3af', fontSize: 13 }}>
                                    {chunks.length === 0
                                        ? 'No chunks found. Try a broader query or check if the brain is indexed.'
                                        : `${chunks.length} chunk${chunks.length !== 1 ? 's' : ''} retrieved`}
                                </div>
                            </div>
                            {chunks.map((c, i) => (
                                <ChunkCard key={c.id || i} chunk={c} index={i + 1} />
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* ── STATS TAB ── */}
            {activeTab === 'stats' && (
                <div>
                    <StatsPanel stats={stats} loading={statsLoading} />
                    {stats && stats.per_tenant && stats.per_tenant.length > 0 && (
                        <div style={{ marginTop: 24 }}>
                            <div style={{ color: '#6b7280', fontSize: 12, marginBottom: 10 }}>PER-TENANT BREAKDOWN</div>
                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                                <thead>
                                    <tr>
                                        {['Tenant ID', 'MP Name', 'Total Chunks', 'Last Indexed'].map(h => (
                                            <th key={h} style={{
                                                color: '#6b7280', textAlign: 'left',
                                                padding: '8px 12px', borderBottom: '1px solid #1f2937',
                                                fontSize: 11,
                                            }}>{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {stats.per_tenant.map((r, i) => (
                                        <tr key={i} style={{ borderBottom: '1px solid #111827' }}>
                                            <td style={{ padding: '8px 12px', color: '#6b7280' }}>{r.tenant_id ?? '—'}</td>
                                            <td style={{ padding: '8px 12px', color: '#e5e7eb' }}>{r.tenant_name || '(global)'}</td>
                                            <td style={{ padding: '8px 12px', color: '#fff', fontWeight: 600 }}>
                                                {(r.total_chunks || 0).toLocaleString()}
                                            </td>
                                            <td style={{ padding: '8px 12px', color: '#6b7280' }}>
                                                {r.last_indexed ? r.last_indexed.slice(0, 16) : '—'}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                    <button
                        onClick={loadStats}
                        style={{
                            marginTop: 16, background: 'none', border: '1px solid #374151',
                            color: '#9ca3af', borderRadius: 6, padding: '6px 14px',
                            fontSize: 12, cursor: 'pointer',
                        }}
                    >
                        ↻ Refresh
                    </button>
                </div>
            )}

            {/* ── REINDEX TAB ── */}
            {activeTab === 'reindex' && (
                <div>
                    <ReindexPanel tenants={tenants} onDone={loadStats} />
                    <div style={{
                        marginTop: 18, background: '#fff',
                        border: '1px solid #e2ebe5', borderRadius: 14, padding: 18,
                        boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
                    }}>
                        <div style={{
                            display: 'flex', justifyContent: 'space-between', gap: 16,
                            alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: 14,
                        }}>
                            <div>
                                <h3 style={{ margin: 0, color: '#1a2e28', fontSize: '0.98rem', fontWeight: 900 }}>
                                    Sources Included
                                </h3>
                                <p style={{ margin: '5px 0 0', color: '#6b7f76', fontSize: '0.8rem', lineHeight: 1.45 }}>
                                    These records become available to search, Copilot, and drafting workflows after refresh.
                                </p>
                            </div>
                            <span className="badge badge-green">Changed content only</span>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
                            {[
                                ['Parliament Q&A', 'Questions and ministry answers used for evidence-backed drafting.'],
                                ['Debates', 'Debate speeches and relevant parliamentary interventions.'],
                                ['Zero Hour', 'Zero-hour submissions and constituency-linked matters.'],
                                ['Constituency Profile', 'Key facts, challenges, priorities, economy, culture, and assembly context.'],
                                ['Cases and Grievances', 'Resolved and active WhatsApp cases for local issue memory.'],
                                ['Government Schemes', 'Shared scheme knowledge available across all tenants.'],
                            ].map(([title, detail]) => (
                                <div key={title} style={{
                                    border: '1px solid #e2ebe5', background: '#f8faf9',
                                    borderRadius: 10, padding: '12px 13px',
                                }}>
                                    <div style={{ color: '#1a2e28', fontSize: '0.83rem', fontWeight: 850 }}>
                                        {title}
                                    </div>
                                    <div style={{ color: '#6b7f76', fontSize: '0.74rem', lineHeight: 1.45, marginTop: 4 }}>
                                        {detail}
                                    </div>
                                </div>
                            ))}
                        </div>
                        <div style={{ color: '#6b7f76', fontSize: '0.76rem', marginTop: 12, lineHeight: 1.5 }}>
                            Rebuild mode regenerates the selected scope when source formatting or extraction logic has changed.
                        </div>
                    </div>
                </div>
            )}

            {/* ── GLOBAL CORPUS TAB ── */}
            {activeTab === 'global' && <GlobalCorpusTab />}
        </div>
    );
}

// ─── Rematch Button — reset no_match rows so improved matcher retries them ───
function RematchButton({ onDone }) {
    const [status, setStatus] = useState(null);
    const [running, setRunning] = useState(false);

    const run = async () => {
        setRunning(true);
        setStatus(null);
        try {
            const r = await apiPost('/api/admin/brain/global-rematch', {});
            setStatus({ ok: true, msg: `↺ Reset ${r.rows_reset} no_match rows for retry` });
            onDone && onDone();
        } catch (e) {
            setStatus({ ok: false, msg: e.message || 'Rematch failed' });
        } finally {
            setRunning(false);
        }
    };

    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button
                onClick={run}
                disabled={running}
                style={{
                    background: 'none', border: '1px solid #374151',
                    color: '#9ca3af', borderRadius: 6,
                    padding: '6px 12px', fontSize: 11,
                    cursor: running ? 'not-allowed' : 'pointer',
                }}
            >
                {running ? '⟳ Resetting…' : '↺ Rematch no_match'}
            </button>
            {status && (
                <span style={{ fontSize: 11, color: status.ok ? '#22c55e' : '#ef4444' }}>
                    {status.msg}
                </span>
            )}
        </div>
    );
}

// ─── Seed Panel (fallback when PRS listing needs JS rendering) ────────────────
function SeedPanel() {
    const [open,       setOpen]       = useState(false);
    const [seedJson,   setSeedJson]   = useState('');
    const [seedStatus, setSeedStatus] = useState('');

    const handleSeed = async () => {
        setSeedStatus('Seeding…');
        try {
            const rows = JSON.parse(seedJson);
            const r = await apiPost('/api/admin/brain/global-seed', rows);
            setSeedStatus(`✓ Seeded ${r.seeded} MPs (${r.new} new)`);
        } catch (e) {
            setSeedStatus(`✗ ${e.message || 'Parse/seed error — check JSON syntax'}`);
        }
    };

    return (
        <div style={{ marginBottom: 12 }}>
            <button
                onClick={() => setOpen(o => !o)}
                style={{
                    background: 'none', border: 'none', color: '#6b7280',
                    fontSize: 11, cursor: 'pointer', padding: '4px 0',
                    textAlign: 'left',
                }}
            >
                {open ? '▾' : '▸'} Fallback: seed MP list manually (if Discover returns 0)
            </button>
            {open && (
                <div style={{
                    background: '#0d1117', border: '1px solid #2d2810',
                    borderRadius: 6, padding: 12, marginTop: 6,
                }}>
                    <div style={{ color: '#f59e0b', fontSize: 11, marginBottom: 8 }}>
                        If "Discover all MPs" finds 0 MPs, the PRS site likely requires JavaScript
                        rendering. Run{' '}
                        <code style={{ background: '#1f2937', padding: '1px 5px', borderRadius: 3 }}>
                            python scripts/diagnose_prs_listing.py
                        </code>{' '}
                        locally to inspect the real HTML, then paste a JSON array of MPs here.
                    </div>
                    <textarea
                        value={seedJson}
                        onChange={e => setSeedJson(e.target.value)}
                        placeholder={'[\n  {"prs_slug": "supriya-sule", "mp_name": "Supriya Sule", "party": "NCP", "constituency": "Baramati", "state": "Maharashtra"},\n  ...\n]'}
                        style={{
                            width: '100%', minHeight: 90, background: '#1f2937',
                            border: '1px solid #374151', color: '#e5e7eb',
                            borderRadius: 4, padding: 8, fontSize: 11,
                            fontFamily: 'monospace', resize: 'vertical', boxSizing: 'border-box',
                        }}
                    />
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 8 }}>
                        <button
                            onClick={handleSeed}
                            disabled={!seedJson.trim()}
                            style={{
                                background: seedJson.trim() ? '#b45309' : '#374151',
                                color: '#fff', border: 'none', borderRadius: 5,
                                padding: '6px 14px', fontSize: 12,
                                cursor: seedJson.trim() ? 'pointer' : 'not-allowed',
                            }}
                        >
                            Seed Registry
                        </button>
                        {seedStatus && (
                            <span style={{
                                fontSize: 11,
                                color: seedStatus.startsWith('✓') ? '#22c55e' : seedStatus === 'Seeding…' ? '#60a5fa' : '#ef4444',
                            }}>
                                {seedStatus}
                            </span>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}


// ─── Normalize Ministry Button ────────────────────────────────────────────────
function NormalizeMinistryBtn({ disabled }) {
    const [status, setStatus] = useState(null);
    const [running, setRunning] = useState(false);

    const run = async () => {
        setRunning(true);
        setStatus(null);
        try {
            const r = await apiPost('/api/admin/brain/scheme-normalize-ministries', {});
            setStatus({ ok: true, msg: `✓ ${r.rows_updated} ministry names normalized (${r.rows_checked} checked)` });
        } catch (e) {
            setStatus({ ok: false, msg: e.message || 'Failed' });
        } finally {
            setRunning(false);
        }
    };

    return (
        <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '10px 14px', background: '#0d1117',
            border: '1px solid #1f2937', borderRadius: 8, marginBottom: 10,
        }}>
            <div>
                <div style={{ color: '#d6d3d1', fontSize: 12, fontWeight: 600 }}>
                    Normalize Ministry Names
                </div>
                <div style={{ color: '#6b7280', fontSize: 11, marginTop: 2 }}>
                    Fix &amp; → and, collapse spaces, expand abbreviations — run before dedup
                </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {status && (
                    <span style={{ fontSize: 11, color: status.ok ? '#22c55e' : '#ef4444' }}>
                        {status.msg}
                    </span>
                )}
                <button
                    onClick={run}
                    disabled={disabled || running}
                    style={{
                        background: (disabled || running) ? '#374151' : '#1e3a5f',
                        color: '#fff', border: 'none', borderRadius: 6,
                        padding: '6px 14px', fontSize: 11,
                        cursor: (disabled || running) ? 'not-allowed' : 'pointer',
                        whiteSpace: 'nowrap',
                    }}
                >
                    {running ? '⟳ Normalizing…' : 'Normalize'}
                </button>
            </div>
        </div>
    );
}


// ─── Scheme Dedup Panel ───────────────────────────────────────────────────────
function DedupPanel({ disabled }) {
    const [preview, setPreview] = useState(null);
    const [loading, setLoading] = useState(false);
    const [running, setRunning] = useState(false);
    const [result,  setResult]  = useState(null);

    const loadPreview = async () => {
        setLoading(true);
        setPreview(null);
        setResult(null);
        try {
            const d = await apiGet('/api/admin/brain/scheme-dedup-preview');
            setPreview(d);
        } catch (e) {
            setPreview({ error: e.message });
        } finally {
            setLoading(false);
        }
    };

    const runDedup = async () => {
        setRunning(true);
        setResult(null);
        try {
            const d = await apiPost('/api/admin/brain/scheme-dedup', {});
            setResult(d);
            setPreview(null);
        } catch (e) {
            setResult({ error: e.message });
        } finally {
            setRunning(false);
        }
    };

    return (
        <div style={{
            background: '#0d1117', border: '1px solid #292524',
            borderRadius: 8, padding: '10px 14px', marginBottom: 10,
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <div style={{ color: '#d6d3d1', fontSize: 12, fontWeight: 600 }}>
                        Deduplicate Schemes
                    </div>
                    <div style={{ color: '#6b7280', fontSize: 11, marginTop: 2 }}>
                        Merge near-duplicates (PM vs Pradhan Mantri, Mission vs Abhiyan, etc.)
                    </div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                    <button
                        onClick={loadPreview}
                        disabled={disabled || loading || running}
                        style={{
                            background: 'none', border: '1px solid #44403c',
                            color: '#a8a29e', borderRadius: 6,
                            padding: '6px 12px', fontSize: 11,
                            cursor: (disabled || loading || running) ? 'not-allowed' : 'pointer',
                        }}
                    >
                        {loading ? '⟳ Checking…' : 'Preview'}
                    </button>
                    {preview && !preview.error && ((preview.rows_to_delete ?? 0) + (preview.acronym_pairs_found ?? 0) + (preview.substring_pairs_found ?? 0)) > 0 && (
                        <button
                            onClick={runDedup}
                            disabled={running}
                            style={{
                                background: running ? '#374151' : '#92400e',
                                color: '#fff', border: 'none', borderRadius: 6,
                                padding: '6px 14px', fontSize: 11,
                                cursor: running ? 'not-allowed' : 'pointer',
                            }}
                        >
                            {running ? '⟳ Merging…' : `Merge ${(preview.rows_to_delete ?? 0) + (preview.acronym_pairs_found ?? 0) + (preview.substring_pairs_found ?? 0)} dupes`}
                        </button>
                    )}
                </div>
            </div>

            {/* Preview results */}
            {preview && !preview.error && (
                <div style={{ marginTop: 10 }}>
                    <div style={{ display: 'flex', gap: 16, marginBottom: 10, flexWrap: 'wrap' }}>
                        {[
                            ['Semantic groups',  preview.duplicate_groups,          '#f59e0b'],
                            ['Acronym pairs',    preview.acronym_pairs_found,        '#818cf8'],
                            ['Substring pairs',  preview.substring_pairs_found,      '#f97316'],
                            ['Rows to delete',   (preview.rows_to_delete ?? 0) + (preview.acronym_pairs_found ?? 0) + (preview.substring_pairs_found ?? 0), '#ef4444'],
                            ['After dedup',      (preview.schemes_after_dedup ?? 0) - (preview.acronym_pairs_found ?? 0) - (preview.substring_pairs_found ?? 0), '#22c55e'],
                        ].map(([l, v, c]) => (
                            <div key={l} style={{ textAlign: 'center' }}>
                                <div style={{ color: c, fontSize: 16, fontWeight: 700 }}>{v ?? '—'}</div>
                                <div style={{ color: '#6b7280', fontSize: 10 }}>{l}</div>
                            </div>
                        ))}
                    </div>

                    {/* Semantic duplicates */}
                    {preview.examples && preview.examples.length > 0 && (
                        <div style={{
                            background: '#111827', borderRadius: 6, padding: '8px 10px',
                            maxHeight: 130, overflowY: 'auto', marginBottom: 8,
                        }}>
                            <div style={{ color: '#6b7280', fontSize: 10, marginBottom: 6 }}>
                                SEMANTIC DUPLICATES (PM vs Pradhan Mantri, Mission vs Abhiyan…)
                            </div>
                            {preview.examples.map((ex, i) => (
                                <div key={i} style={{ marginBottom: 5 }}>
                                    <span style={{ color: '#4b5563', fontSize: 10 }}>[{ex.key}]&nbsp;</span>
                                    <span style={{ color: '#9ca3af', fontSize: 11 }}>{ex.schemes.join(' · ')}</span>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Acronym pairs */}
                    {preview.acronym_pairs && preview.acronym_pairs.length > 0 && (
                        <div style={{
                            background: '#111827', borderRadius: 6, padding: '8px 10px',
                            maxHeight: 120, overflowY: 'auto', marginBottom: 8,
                        }}>
                            <div style={{ color: '#6b7280', fontSize: 10, marginBottom: 6 }}>
                                ACRONYM MATCHES (PMAY → Pradhan Mantri Awas Yojana…)
                            </div>
                            {preview.acronym_pairs.map((p, i) => (
                                <div key={i} style={{ marginBottom: 5 }}>
                                    <span style={{ color: '#818cf8', fontSize: 11, fontWeight: 600 }}>{p.acronym}</span>
                                    <span style={{ color: '#4b5563', fontSize: 11 }}> → </span>
                                    <span style={{ color: '#9ca3af', fontSize: 11 }}>{p.full_name}</span>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Substring pairs */}
                    {preview.substring_pairs && preview.substring_pairs.length > 0 && (
                        <div style={{
                            background: '#111827', borderRadius: 6, padding: '8px 10px',
                            maxHeight: 120, overflowY: 'auto',
                        }}>
                            <div style={{ color: '#6b7280', fontSize: 10, marginBottom: 6 }}>
                                SUBSTRING CONTAINED ('Capital Subsidy Scheme' ⊂ 'Credit Linked Capital Subsidy Scheme'…)
                            </div>
                            {preview.substring_pairs.map((p, i) => (
                                <div key={i} style={{ marginBottom: 5 }}>
                                    <span style={{ color: '#f97316', fontSize: 11 }}>{p.contained}</span>
                                    <span style={{ color: '#4b5563', fontSize: 11 }}> ⊂ </span>
                                    <span style={{ color: '#9ca3af', fontSize: 11 }}>{p.parent}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Merge result */}
            {result && (
                <div style={{
                    marginTop: 10, padding: '7px 10px', borderRadius: 6, fontSize: 12,
                    background: result.error ? '#2d1f1f' : '#1a2e1f',
                    color: result.error ? '#ef4444' : '#22c55e',
                }}>
                    {result.error
                        ? `Error: ${result.error}`
                        : `Done — ${result.groups_merged ?? 0} semantic + ${result.acronym_pairs_merged ?? 0} acronym + ${result.substring_pairs_merged ?? 0} substring · ${(result.rows_deleted ?? 0) + (result.acronym_pairs_merged ?? 0) + (result.substring_pairs_merged ?? 0)} removed · ${result.schemes_remaining ?? '?'} remain`}
                </div>
            )}

            {preview?.error && (
                <div style={{ marginTop: 8, color: '#ef4444', fontSize: 11 }}>
                    {preview.error}
                </div>
            )}
        </div>
    );
}


// ─── Global Corpus Tab ────────────────────────────────────────────────────────
function GlobalCorpusTab() {
    const [globalStats, setGlobalStats] = useState(null);
    const [topicStats, setTopicStats] = useState(null);
    const [governmentIntelStats, setGovernmentIntelStats] = useState(null);
    const [statsLoading, setStatsLoading] = useState(true);
    const [jobs, setJobs] = useState({});  // jobId → job state
    const [crawlLimit, setCrawlLimit] = useState(50);
    const [includeFailedCrawl, setIncludeFailedCrawl] = useState(false);
    const [tagLimit, setTagLimit] = useState(500);
    const [classifyLimit, setClassifyLimit] = useState(2000);
    const [governmentIntelLimit, setGovernmentIntelLimit] = useState(25);
    const [governmentIntelStaleOnly, setGovernmentIntelStaleOnly] = useState(false);
    const [governmentIntelRebuild, setGovernmentIntelRebuild] = useState(false);
    const [indexAnswersOnly, setIndexAnswersOnly] = useState(false);
    const [indexRebuild, setIndexRebuild] = useState(false);
    const [allowOcr, setAllowOcr] = useState(false);
    const [advancedOpen, setAdvancedOpen] = useState(false);
    const [actionNotice, setActionNotice] = useState(null);

    const loadStats = useCallback(() => {
        setStatsLoading(true);
        apiGet('/api/admin/brain/global-stats')
            .then(d => setGlobalStats(d))
            .catch(() => {})
            .finally(() => setStatsLoading(false));
    }, []);

    const loadTopicStats = useCallback(() => {
        apiGet('/api/admin/brain/classify-topics/stats')
            .then(d => setTopicStats(d))
            .catch(() => setTopicStats(null));
    }, []);

    const loadGovernmentIntelStats = useCallback(() => {
        apiGet('/api/admin/brain/government-intel/stats')
            .then(d => setGovernmentIntelStats(d))
            .catch(() => setGovernmentIntelStats(null));
    }, []);

    const refreshOverview = useCallback(() => {
        loadStats();
        loadTopicStats();
        loadGovernmentIntelStats();
    }, [loadStats, loadTopicStats, loadGovernmentIntelStats]);

    useEffect(() => { refreshOverview(); }, [refreshOverview]);

    // Poll running jobs
    useEffect(() => {
        const running = Object.entries(jobs).filter(([, j]) => j.status === 'running');
        if (!running.length) return;
        const t = setInterval(async () => {
            for (const [jid] of running) {
                try {
                    const statusPath = jid.startsWith('classify_topics_')
                        ? `/api/admin/brain/classify-topics/status/${jid}`
                        : jid.startsWith('government_intel_')
                        ? `/api/admin/brain/government-intel/status/${jid}`
                        : `/api/admin/brain/global-crawl/status/${jid}`;
                    const j = await apiGet(statusPath);
                    setJobs(prev => ({ ...prev, [jid]: j }));
                    if (['done', 'error', 'warning'].includes(j.status)) refreshOverview();
                } catch (_) {}
            }
        }, 2000);
        return () => clearInterval(t);
    }, [jobs, refreshOverview]);

    const trigger = async (url, body = {}, label = 'Update') => {
        setActionNotice({ type: 'info', text: `${label} is starting...` });
        try {
            const r = await apiPost(url, body);
            if (r.job_id) {
                const jobType = r.job_id
                    .replace(/^global_/, '')
                    .replace(/^scheme_/, 'scheme_')
                    .replace(/^classify_/, 'classify_')
                    .split('_')
                    .slice(0, 2)
                    .join(' ');
                setJobs(prev => ({
                    ...prev,
                    [r.job_id]: {
                        status: 'running',
                        type: jobType || label,
                    },
                }));
                setActionNotice({ type: 'success', text: `${label} started. Progress will appear under Refresh Activity.` });
            } else {
                setActionNotice({ type: 'success', text: `${label} completed.` });
                refreshOverview();
            }
        } catch (e) {
            setActionNotice({ type: 'error', text: e.message || `Failed to start ${label.toLowerCase()}` });
        }
    };

    const BtnRow = ({ label, desc, onClick, accent = '#1d4ed8', disabled = false }) => (
        <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '12px 16px', background: '#0d1117',
            border: '1px solid #1f2937', borderRadius: 8, marginBottom: 10,
        }}>
            <div>
                <div style={{ color: '#e5e7eb', fontSize: 13, fontWeight: 600 }}>{label}</div>
                <div style={{ color: '#6b7280', fontSize: 11, marginTop: 2 }}>{desc}</div>
            </div>
            <button
                onClick={onClick}
                disabled={disabled}
                style={{
                    background: disabled ? '#374151' : accent,
                    color: '#fff', border: 'none', borderRadius: 6,
                    padding: '7px 16px', fontSize: 12,
                    cursor: disabled ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap',
                }}
            >
                {label.split(' ')[0]}
            </button>
        </div>
    );

    const anyRunning = Object.values(jobs).some(j => j.status === 'running');
    const reg      = globalStats?.corpus?.registry  || {};
    const pqs      = globalStats?.corpus?.questions || {};
    const coverage = globalStats?.coverage || {};
    const mins     = globalStats?.ministries || [];
    const [answerLimit, setAnswerLimit] = useState(100);
    const topicCoverage = topicStats?.coverage || {};
    const classifiedTopics = topicCoverage.classified || 0;
    const totalTopicRows = topicCoverage.total || 0;
    const topicPct = totalTopicRows ? Math.round((classifiedTopics / totalTopicRows) * 100) : 0;
    const answerPct = coverage.pct_covered || 0;
    const totalQuestions = pqs.total_questions || 0;
    const govIntel = governmentIntelStats || {};
    const govIntelReady = govIntel.ready || 0;
    const govIntelPending = govIntel.pending || 0;
    const govIntelStale = govIntel.stale || 0;
    const govIntelFailed = govIntel.failed || 0;
    const govIntelCandidates = govIntel.candidate_groups || 0;
    const govIntelPct = govIntel.coverage_pct || 0;
    const schemeMentions = govIntel.scheme_mentions || 0;
    const govIntelScope = govIntel.selection_scope;
    const corpusLabel = anyRunning
        ? 'Refreshing'
        : totalQuestions === 0
        ? 'Needs Setup'
        : answerPct < 50 || topicPct < 50 || (govIntelCandidates > 0 && govIntelPct < 50)
        ? 'Needs Refresh'
        : 'Ready';
    const corpusTone = corpusLabel === 'Ready' ? '#006a4d' : corpusLabel === 'Refreshing' ? '#2563eb' : '#d97706';

    const SoftCard = ({ title, value, detail, tone = '#006a4d' }) => (
        <div style={{
            background: '#fff', border: '1px solid #e2ebe5',
            borderRadius: 12, padding: 16, boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
        }}>
            <div style={{ color: '#6b7f76', fontSize: '0.7rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                {title}
            </div>
            <div style={{ color: tone, fontSize: '1.45rem', fontWeight: 850, marginTop: 8, lineHeight: 1 }}>
                {value}
            </div>
            <div style={{ color: '#6b7f76', fontSize: '0.76rem', marginTop: 8, lineHeight: 1.45 }}>
                {detail}
            </div>
        </div>
    );

    const CoverageRow = ({ label, value, hint, pct }) => {
        const tone = pct >= 75 ? '#006a4d' : pct >= 40 ? '#d97706' : '#dc2626';
        return (
            <div style={{ padding: '12px 0', borderBottom: '1px solid #eef2ef' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center' }}>
                    <div>
                        <div style={{ color: '#1a2e28', fontSize: '0.86rem', fontWeight: 800 }}>{label}</div>
                        <div style={{ color: '#6b7f76', fontSize: '0.74rem', marginTop: 2 }}>{hint}</div>
                    </div>
                    <div style={{ color: tone, fontWeight: 850, fontSize: '0.9rem', whiteSpace: 'nowrap' }}>{value}</div>
                </div>
                {pct !== null && pct !== undefined && (
                    <div style={{ height: 6, background: '#edf3ef', borderRadius: 99, overflow: 'hidden', marginTop: 10 }}>
                        <div style={{ width: `${Math.min(100, Math.max(0, pct))}%`, height: '100%', background: tone, borderRadius: 99 }} />
                    </div>
                )}
            </div>
        );
    };

    const ActionCard = ({ title, detail, button, onClick, tone = '#006a4d', disabled }) => (
        <div style={{
            background: '#fff', border: '1px solid #e2ebe5',
            borderRadius: 12, padding: 14,
            display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center',
        }}>
            <div>
                <div style={{ color: '#1a2e28', fontWeight: 850, fontSize: '0.86rem' }}>{title}</div>
                <div style={{ color: '#6b7f76', fontSize: '0.75rem', marginTop: 3, lineHeight: 1.45 }}>{detail}</div>
            </div>
            <button
                onClick={onClick}
                disabled={disabled}
                style={{
                    background: disabled ? '#d9e3de' : tone,
                    color: '#fff', border: 'none', borderRadius: 9,
                    padding: '8px 14px', fontSize: '0.76rem', fontWeight: 800,
                    cursor: disabled ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap',
                }}
            >
                {button}
            </button>
        </div>
    );

    const JobsPanel = () => Object.entries(jobs).length > 0 && (
        <div style={{
            background: '#fff', border: '1px solid #e2ebe5',
            borderRadius: 12, padding: 16, boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
        }}>
            <div style={{ color: '#1a2e28', fontSize: '0.9rem', fontWeight: 850, marginBottom: 10 }}>Refresh Activity</div>
            {Object.entries(jobs).map(([jid, j]) => {
                const isWarning = j.status === 'warning';
                const color = j.status === 'done' ? '#006a4d'
                    : j.status === 'error' ? '#dc2626'
                    : isWarning ? '#d97706'
                    : '#2563eb';
                return (
                    <div key={jid} style={{
                        padding: '9px 0', borderTop: '1px solid #eef2ef',
                        color: '#6b7f76', fontSize: '0.76rem',
                    }}>
                        <div style={{ color, fontWeight: 850, textTransform: 'capitalize' }}>
                            {(j.type || jid.split('_')[1] || 'refresh').replace('_', ' ')} - {j.status}
                            {j.status === 'running' && j.progress && j.progress.total > 0 && (
                                <span style={{ color: '#6b7f76', fontWeight: 500, marginLeft: 8 }}>
                                    {j.progress.done}/{j.progress.total} {j.progress.label}
                                </span>
                            )}
                        </div>
                        {j.status === 'running' && j.progress && j.progress.total > 0 && (
                            <div style={{ marginTop: 6, height: 5, background: '#edf3ef', borderRadius: 99, overflow: 'hidden' }}>
                                <div style={{
                                    width: `${Math.round((j.progress.done / j.progress.total) * 100)}%`,
                                    height: '100%', background: '#2563eb', borderRadius: 99,
                                }} />
                            </div>
                        )}
                        {j.summary && (
                            <div style={{ marginTop: 4, lineHeight: 1.5 }}>
                                {j.summary.rows_updated != null
                                    ? `Ministry answers updated: ${j.summary.rows_updated}. PDFs processed: ${(j.summary.pdfs_processed || 0) + (j.summary.pdfs_from_cache || 0)}.`
                                    : j.summary.crawled != null
                                    ? `National questions refreshed for ${j.summary.crawled} MPs. New questions: ${j.summary.inserted_total || 0}.`
                                    : j.summary.classified != null
                                    ? `Issues organized: ${j.summary.classified}.`
                                    : j.summary.generated != null
                                    ? `Government Intel prepared: ${j.summary.generated}/${j.summary.selected || 0} briefs. Failed: ${j.summary.failed || 0}. No answers: ${j.summary.no_answers || 0}. Remaining: ${j.summary.remaining || 0}.${j.summary.selection_scope === 'all_answered_fallback' ? ' Used all answered issue groups.' : ''}`
                                    : j.summary.chunks_inserted != null
                                    ? `Search readiness updated with ${j.summary.chunks_inserted} entries.`
                                    : j.summary.schemes_upserted != null
                                    ? `Scheme intelligence updated: ${j.summary.schemes_upserted} schemes.`
                                    : 'Refresh completed.'}
                            </div>
                        )}
                        {j.error && <div style={{ marginTop: 4, color }}>{j.error}</div>}
                    </div>
                );
            })}
        </div>
    );

    return (
        <div style={{ display: 'grid', gap: 18, color: '#1a2e28' }}>
            <div style={{
                background: '#fff', border: '1px solid #e2ebe5',
                borderRadius: 14, padding: 22,
                display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 20,
                boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
            }}>
                <div>
                    <div style={{ color: '#006a4d', fontSize: '0.72rem', fontWeight: 850, textTransform: 'uppercase', letterSpacing: '0.12em' }}>
                        National Intelligence
                    </div>
                    <h2 style={{ margin: '7px 0 0', color: '#1a2e28', fontSize: '1.35rem', fontWeight: 900 }}>
                        Shared Parliament and scheme intelligence
                    </h2>
                    <p style={{ margin: '7px 0 0', color: '#6b7f76', fontSize: '0.86rem', lineHeight: 1.55, maxWidth: 720 }}>
                        The system tracks national Parliament questions, ministry replies, issue categories, and scheme signals so MPs can act with broader context.
                    </p>
                </div>
                <div style={{ textAlign: 'right', minWidth: 180 }}>
                    <div style={{ color: corpusTone, fontSize: '1.1rem', fontWeight: 900 }}>{corpusLabel}</div>
                    <div style={{ marginTop: 5, color: '#6b7f76', fontSize: '0.74rem' }}>
                        {anyRunning ? 'A refresh is currently running.' : totalQuestions ? `${totalQuestions.toLocaleString()} questions available` : 'No national questions loaded yet'}
                    </div>
                    <button
                        onClick={() => trigger('/api/admin/brain/global-crawl', { limit: crawlLimit, include_failed: false }, 'National intelligence refresh')}
                        disabled={anyRunning}
                        style={{
                            marginTop: 12, background: anyRunning ? '#d9e3de' : '#006a4d',
                            color: '#fff', border: 'none', borderRadius: 10,
                            padding: '9px 16px', fontSize: '0.82rem', fontWeight: 850,
                            cursor: anyRunning ? 'not-allowed' : 'pointer',
                        }}
                    >
                        Refresh Intelligence
                    </button>
                </div>
            </div>

            {statsLoading ? (
                <div className="glass-panel" style={{ color: '#6b7f76' }}>Loading national intelligence...</div>
            ) : (
                <>
                    {actionNotice && (
                        <div style={{
                            border: `1px solid ${actionNotice.type === 'error' ? '#fecaca' : actionNotice.type === 'success' ? '#bbf7d0' : '#bfdbfe'}`,
                            background: actionNotice.type === 'error' ? '#fef2f2' : actionNotice.type === 'success' ? '#f0fdf4' : '#eff6ff',
                            color: actionNotice.type === 'error' ? '#991b1b' : actionNotice.type === 'success' ? '#166534' : '#1d4ed8',
                            borderRadius: 12,
                            padding: '10px 14px',
                            fontSize: '0.82rem',
                            fontWeight: 750,
                        }}>
                            {actionNotice.text}
                        </div>
                    )}

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 12 }}>
                        <SoftCard title="Parliament Questions" value={(totalQuestions || 0).toLocaleString()} detail={`${reg.done || 0} MPs refreshed, ${reg.pending || 0} pending`} tone="#006a4d" />
                        <SoftCard title="Ministry Answers" value={`${answerPct}%`} detail={`${(coverage.with_answers || 0).toLocaleString()} of ${(coverage.total || 0).toLocaleString()} questions have replies`} tone={answerPct >= 60 ? '#006a4d' : '#d97706'} />
                        <SoftCard title="Issue Categories" value={`${topicPct}%`} detail={`${classifiedTopics.toLocaleString()} questions organized for issue intelligence`} tone={topicPct >= 70 ? '#006a4d' : '#d97706'} />
                        <SoftCard title="Government Intel" value={`${govIntelPct}%`} detail={`${govIntelReady.toLocaleString()} ready, ${(govIntelPending + govIntelStale + govIntelFailed).toLocaleString()} need work`} tone={govIntelPct >= 70 ? '#006a4d' : '#d97706'} />
                        <SoftCard title="Active Ministries" value={pqs.ministries || 0} detail="Ministries represented in national question data" tone="#2563eb" />
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                        <div style={{
                            background: '#fff', border: '1px solid #e2ebe5',
                            borderRadius: 12, padding: 18, boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
                        }}>
                            <h3 style={{ margin: 0, color: '#1a2e28', fontSize: '0.98rem', fontWeight: 900 }}>Intelligence Coverage</h3>
                            <CoverageRow label="Parliament Questions" value={totalQuestions ? 'Available' : 'Not loaded'} hint="National question base across MPs" pct={totalQuestions ? 100 : 0} />
                            <CoverageRow label="Ministry Answers" value={`${answerPct}%`} hint="Full ministry replies available for question drafting and comparison" pct={answerPct} />
                            <CoverageRow label="Issue Categories" value={`${topicPct}%`} hint="Questions organized into useful public issue areas" pct={topicPct} />
                            <CoverageRow
                                label="Government Intel"
                                value={govIntelCandidates ? `${govIntelReady}/${govIntelCandidates} ready` : 'Needs issue data'}
                                hint={govIntelScope === 'all_answered_fallback'
                                    ? 'Scheme extraction covers most answers, so the builder is using all answered issue groups'
                                    : schemeMentions
                                    ? 'Non-scheme Parliament answers converted into cached ministry issue briefs'
                                    : 'Run scheme intelligence first so scheme PQs can be separated out'}
                                pct={govIntelCandidates ? govIntelPct : 0}
                            />
                            <CoverageRow
                                label="Scheme Intelligence"
                                value={totalQuestions ? 'Ready to update' : 'Needs questions first'}
                                hint={totalQuestions ? 'Scheme mentions can be refreshed from national question answers' : 'Refresh national questions before updating scheme intelligence'}
                                pct={totalQuestions ? 65 : 0}
                            />
                        </div>

                        <div style={{
                            background: '#fff', border: '1px solid #e2ebe5',
                            borderRadius: 12, padding: 18, boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
                        }}>
                            <h3 style={{ margin: 0, color: '#1a2e28', fontSize: '0.98rem', fontWeight: 900 }}>Recommended Actions</h3>
                            <div style={{ display: 'grid', gap: 10, marginTop: 12 }}>
                                <ActionCard
                                    title="Refresh national questions"
                                    detail="Bring in newer Parliament questions for MPs that have not been refreshed."
                                    button="Refresh"
                                    onClick={() => trigger('/api/admin/brain/global-crawl', { limit: crawlLimit, include_failed: false }, 'National questions refresh')}
                                    disabled={anyRunning}
                                />
                                <ActionCard
                                    title="Complete ministry answers"
                                    detail="Fill missing ministry replies so recommendations and PQ drafts have stronger evidence."
                                    button="Complete"
                                    tone="#059669"
                                    onClick={() => trigger('/api/admin/brain/global-fetch-answers', { limit: answerLimit, allow_ocr: false }, 'Ministry answer completion')}
                                    disabled={anyRunning || !totalQuestions}
                                />
                                <ActionCard
                                    title="Organize national issues"
                                    detail="Classify unanswered issue areas into a clean map of public concerns."
                                    button="Organize"
                                    tone="#2563eb"
                                    onClick={() => trigger('/api/admin/brain/classify-topics', { limit: classifyLimit }, 'Issue organization')}
                                    disabled={anyRunning || !totalQuestions}
                                />
                                <ActionCard
                                    title="Update scheme intelligence"
                                    detail="Refresh scheme mentions discovered in Parliament answers."
                                    button="Update"
                                    tone="#b45309"
                                    onClick={() => trigger('/api/admin/brain/scheme-extract', {}, 'Scheme intelligence update')}
                                    disabled={anyRunning || !totalQuestions}
                                />
                                <ActionCard
                                    title="Prepare Government Intel"
                                    detail="Generate ministry issue briefs from non-scheme Parliament answers before MPs open the tab."
                                    button="Prepare"
                                    tone="#7c3aed"
                                    onClick={() => trigger('/api/admin/brain/government-intel/build', { limit: governmentIntelLimit, stale_only: false, rebuild: false }, 'Government Intel preparation')}
                                    disabled={anyRunning || !totalQuestions}
                                />
                            </div>
                        </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: mins.length ? '1fr 1fr' : '1fr', gap: 16 }}>
                        <JobsPanel />
                        {mins.length > 0 && (
                            <div style={{
                                background: '#fff', border: '1px solid #e2ebe5',
                                borderRadius: 12, padding: 18, boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
                            }}>
                                <h3 style={{ margin: 0, color: '#1a2e28', fontSize: '0.98rem', fontWeight: 900 }}>Ministry Signals</h3>
                                <div style={{ marginTop: 12 }}>
                                    {mins.slice(0, 8).map((m, i) => {
                                        const pct = totalQuestions ? Math.round((m.total / totalQuestions) * 100) : 0;
                                        return (
                                            <div key={i} style={{ marginBottom: 10 }}>
                                                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14, marginBottom: 4 }}>
                                                    <span style={{ color: '#1a2e28', fontSize: '0.78rem', fontWeight: 750 }}>{m.ministry || 'Unknown ministry'}</span>
                                                    <span style={{ color: '#6b7f76', fontSize: '0.74rem' }}>{m.total} questions</span>
                                                </div>
                                                <div style={{ height: 5, background: '#edf3ef', borderRadius: 99, overflow: 'hidden' }}>
                                                    <div style={{ width: `${pct}%`, height: '100%', background: '#006a4d', borderRadius: 99 }} />
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        )}
                    </div>

                    <div style={{
                        background: '#fff', border: '1px solid #e2ebe5',
                        borderRadius: 12, overflow: 'hidden', boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
                    }}>
                        <button
                            onClick={() => setAdvancedOpen(open => !open)}
                            style={{
                                width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                background: '#f8faf9', border: 'none', borderBottom: advancedOpen ? '1px solid #e2ebe5' : 'none',
                                padding: '13px 16px', cursor: 'pointer', color: '#1a2e28',
                                fontWeight: 900, fontSize: '0.86rem',
                            }}
                        >
                            Advanced Maintenance
                            <span style={{ color: '#6b7f76', fontWeight: 700 }}>{advancedOpen ? 'Hide' : 'Show'}</span>
                        </button>
                        {advancedOpen && (
                            <div style={{ padding: 16, background: '#111827' }}>
                                <div style={{
                                    marginBottom: 14, background: '#0d1117',
                                    border: '1px solid #1f2937', borderRadius: 8, padding: 14,
                                    fontSize: 12, color: '#9ca3af', lineHeight: 1.7,
                                }}>
                                    These controls operate the underlying data maintenance jobs. Use them when the simple actions above are not enough.
                                </div>

                                <BtnRow
                                    label="Discover all MPs"
                                    desc="Refresh the national MP registry from source listings"
                                    onClick={() => trigger('/api/admin/brain/global-discover', {}, 'MP registry refresh')}
                                    disabled={anyRunning}
                                />
                                <SeedPanel />

                                <div style={{ display: 'flex', gap: 12, alignItems: 'center', margin: '14px 0 8px', flexWrap: 'wrap' }}>
                                    <label style={{ color: '#9ca3af', fontSize: 12 }}>
                                        Question refresh limit:&nbsp;
                                        <input
                                            type="number" min={1} max={543} value={crawlLimit}
                                            onChange={e => setCrawlLimit(Math.max(1, parseInt(e.target.value) || 50))}
                                            style={{
                                                background: '#1f2937', border: '1px solid #374151', color: '#e5e7eb',
                                                borderRadius: 4, padding: '3px 8px', fontSize: 12, width: 64,
                                            }}
                                        />
                                    </label>
                                    <label style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#9ca3af', fontSize: 12, cursor: 'pointer' }}>
                                        <input type="checkbox" checked={includeFailedCrawl} onChange={e => setIncludeFailedCrawl(e.target.checked)} style={{ accentColor: '#3b82f6' }} />
                                        Include failed records
                                    </label>
                                </div>
                                <BtnRow
                                    label="Refresh national questions"
                                    desc="Bring in question records for MPs that need updates"
                                    onClick={() => trigger('/api/admin/brain/global-crawl', { limit: crawlLimit, include_failed: includeFailedCrawl }, 'National questions refresh')}
                                    accent="#7c3aed"
                                    disabled={anyRunning}
                                />

                                <div style={{
                                    background: '#0d1117', border: '1px solid #1f2937',
                                    borderRadius: 8, padding: '10px 14px', marginBottom: 10,
                                }}>
                                    <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
                                        <label style={{ color: '#9ca3af', fontSize: 12 }}>
                                            Answer batch:&nbsp;
                                            <input
                                                type="number" min={10} max={5000} value={answerLimit}
                                                onChange={e => setAnswerLimit(Math.max(10, parseInt(e.target.value) || 100))}
                                                style={{
                                                    background: '#1f2937', border: '1px solid #374151', color: '#e5e7eb',
                                                    borderRadius: 4, padding: '3px 8px', fontSize: 12, width: 72,
                                                }}
                                            />
                                        </label>
                                        <label style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#9ca3af', fontSize: 12, cursor: 'pointer' }}>
                                            <input type="checkbox" checked={allowOcr} onChange={e => setAllowOcr(e.target.checked)} style={{ accentColor: '#f59e0b' }} />
                                            Use OCR for scanned PDFs
                                        </label>
                                    </div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                                        <RematchButton onDone={loadStats} />
                                        <button
                                            onClick={() => trigger('/api/admin/brain/global-fetch-answers', { limit: answerLimit, allow_ocr: allowOcr }, 'Ministry answer completion')}
                                            disabled={anyRunning}
                                            style={{
                                                background: anyRunning ? '#374151' : '#059669',
                                                color: '#fff', border: 'none', borderRadius: 6,
                                                padding: '7px 18px', fontSize: 12,
                                                cursor: anyRunning ? 'not-allowed' : 'pointer',
                                            }}
                                        >
                                            Complete Ministry Answers
                                        </button>
                                    </div>
                                </div>

                                <BtnRow
                                    label="Organize issue categories"
                                    desc="Classify national questions into issue areas"
                                    onClick={() => trigger('/api/admin/brain/classify-topics', { limit: classifyLimit }, 'Issue organization')}
                                    accent="#2563eb"
                                    disabled={anyRunning}
                                />
                                <BtnRow
                                    label="Update scheme intelligence"
                                    desc="Extract scheme mentions from national question answers"
                                    onClick={() => trigger('/api/admin/brain/scheme-extract', {}, 'Scheme intelligence update')}
                                    accent="#b45309"
                                    disabled={anyRunning}
                                />
                                <div style={{
                                    background: '#0d1117', border: '1px solid #1f2937',
                                    borderRadius: 8, padding: '10px 14px', marginBottom: 10,
                                }}>
                                    <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
                                        <label style={{ color: '#9ca3af', fontSize: 12 }}>
                                            Government Intel batch:&nbsp;
                                            <input
                                                type="number" min={1} max={250} value={governmentIntelLimit}
                                                onChange={e => setGovernmentIntelLimit(Math.max(1, parseInt(e.target.value) || 25))}
                                                style={{
                                                    background: '#1f2937', border: '1px solid #374151', color: '#e5e7eb',
                                                    borderRadius: 4, padding: '3px 8px', fontSize: 12, width: 72,
                                                }}
                                            />
                                        </label>
                                        <label style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#9ca3af', fontSize: 12, cursor: 'pointer' }}>
                                            <input type="checkbox" checked={governmentIntelStaleOnly} onChange={e => setGovernmentIntelStaleOnly(e.target.checked)} style={{ accentColor: '#7c3aed' }} />
                                            Only stale briefs
                                        </label>
                                        <label style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#9ca3af', fontSize: 12, cursor: 'pointer' }}>
                                            <input type="checkbox" checked={governmentIntelRebuild} onChange={e => setGovernmentIntelRebuild(e.target.checked)} style={{ accentColor: '#ef4444' }} />
                                            Rebuild ready briefs
                                        </label>
                                    </div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                                        <div style={{ color: '#6b7280', fontSize: 11 }}>
                                            Reads non-scheme PQ answers and writes cached ministry issue briefs.
                                        </div>
                                        <button
                                            onClick={() => trigger('/api/admin/brain/government-intel/build', {
                                                limit: governmentIntelLimit,
                                                stale_only: governmentIntelStaleOnly,
                                                rebuild: governmentIntelRebuild,
                                            }, 'Government Intel preparation')}
                                            disabled={anyRunning || !totalQuestions}
                                            style={{
                                                background: anyRunning || !totalQuestions ? '#374151' : '#7c3aed',
                                                color: '#fff', border: 'none', borderRadius: 6,
                                                padding: '7px 18px', fontSize: 12,
                                                cursor: anyRunning || !totalQuestions ? 'not-allowed' : 'pointer',
                                            }}
                                        >
                                            Prepare Government Intel
                                        </button>
                                    </div>
                                </div>
                                <NormalizeMinistryBtn disabled={anyRunning} />
                                <DedupPanel disabled={anyRunning} />

                                <BtnRow
                                    label="Improve search labels"
                                    desc="Generate richer issue tags for retrieval"
                                    onClick={() => trigger('/api/admin/brain/global-tag', { limit: tagLimit }, 'Search label improvement')}
                                    accent="#0891b2"
                                    disabled={anyRunning}
                                />
                                <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
                                    <label style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#9ca3af', fontSize: 12, cursor: 'pointer' }}>
                                        <input type="checkbox" checked={indexAnswersOnly} onChange={e => setIndexAnswersOnly(e.target.checked)} style={{ accentColor: '#3b82f6' }} />
                                        Only records with answers
                                    </label>
                                    <label style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#9ca3af', fontSize: 12, cursor: 'pointer' }}>
                                        <input type="checkbox" checked={indexRebuild} onChange={e => setIndexRebuild(e.target.checked)} style={{ accentColor: '#ef4444' }} />
                                        Repair from scratch
                                    </label>
                                </div>
                                <BtnRow
                                    label="Update search readiness"
                                    desc="Make refreshed national intelligence available to Copilot and Drafter"
                                    onClick={() => trigger('/api/admin/brain/global-index', { only_with_answers: indexAnswersOnly, rebuild: indexRebuild }, 'Search readiness update')}
                                    accent="#166534"
                                    disabled={anyRunning}
                                />
                            </div>
                        )}
                    </div>
                </>
            )}
        </div>
    );

}
