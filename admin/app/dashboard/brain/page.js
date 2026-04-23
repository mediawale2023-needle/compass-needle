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

    return (
        <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, padding: 16 }}>
            <div style={{ color: '#9ca3af', fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
                Re-index Brain
            </div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <select
                    value={tenantId}
                    onChange={e => setTenantId(e.target.value)}
                    style={{
                        background: '#1f2937', border: '1px solid #374151', color: '#e5e7eb',
                        borderRadius: 6, padding: '6px 10px', fontSize: 13,
                    }}
                >
                    <option value=''>All tenants</option>
                    {(tenants || []).map(t => (
                        <option key={t.tenant_id} value={t.tenant_id}>{t.mp_name}</option>
                    ))}
                </select>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#9ca3af', fontSize: 12, cursor: 'pointer' }}>
                    <input
                        type='checkbox'
                        checked={rebuild}
                        onChange={e => setRebuild(e.target.checked)}
                        style={{ accentColor: '#3b82f6' }}
                    />
                    Full rebuild (delete existing)
                </label>
                <button
                    onClick={start}
                    disabled={running}
                    style={{
                        background: running ? '#374151' : '#1d4ed8',
                        color: '#fff', border: 'none', borderRadius: 6,
                        padding: '7px 16px', fontSize: 13, cursor: running ? 'not-allowed' : 'pointer',
                    }}
                >
                    {running ? '⟳ Indexing…' : 'Start Re-index'}
                </button>
            </div>
            {status && (
                <div style={{
                    marginTop: 12, padding: '8px 12px',
                    background: status.error ? '#2d1f1f' : '#1f2d1f',
                    borderRadius: 6, fontSize: 12,
                    color: status.error ? '#ef4444' : '#22c55e',
                }}>
                    {status.error
                        ? `Error: ${status.error}`
                        : `Done — ${JSON.stringify(status.summary || {}).slice(0, 200)}`}
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
                    🧠 Brain Playground
                </h1>
                <p style={{ color: '#6b7280', fontSize: 13, margin: '6px 0 0' }}>
                    Test semantic retrieval over memory_chunks — exactly what the Copilot and Drafter see.
                </p>
            </div>

            {/* Tabs */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 24, flexWrap: 'wrap' }}>
                {TAB('playground', '🔍 Retrieval Playground')}
                {TAB('stats', '📊 Memory Stats')}
                {TAB('reindex', '⚙️ Re-index')}
                {TAB('global', '🌐 Global Corpus')}
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
                        marginTop: 20, background: '#111827',
                        border: '1px solid #1f2937', borderRadius: 8, padding: 16,
                    }}>
                        <div style={{ color: '#6b7280', fontSize: 12, marginBottom: 8 }}>WHAT GETS INDEXED</div>
                        <ul style={{ color: '#9ca3af', fontSize: 13, margin: 0, paddingLeft: 20, lineHeight: 1.8 }}>
                            <li><strong style={{ color: '#e5e7eb' }}>PQ Q&A</strong> — parliamentary questions + ministry answers from <code>parliamentary_questions</code></li>
                            <li><strong style={{ color: '#e5e7eb' }}>Debates</strong> — debate speeches from <code>parliamentary_debates</code></li>
                            <li><strong style={{ color: '#e5e7eb' }}>Zero Hour</strong> — zero-hour submissions from <code>zero_hour_submissions</code></li>
                            <li><strong style={{ color: '#e5e7eb' }}>Constituency Profile</strong> — all 13 sections chunked individually (challenges, priorities, economy, …)</li>
                            <li><strong style={{ color: '#e5e7eb' }}>Cases / Grievances</strong> — resolved and active WhatsApp cases</li>
                            <li><strong style={{ color: '#e5e7eb' }}>Schemes</strong> — 1500+ government schemes from <code>schemes_db.json</code> (global, shared across tenants)</li>
                        </ul>
                        <div style={{ color: '#4b5563', fontSize: 12, marginTop: 12 }}>
                            Indexing is idempotent — only re-embeds chunks whose content changed (content_hash comparison).
                            Use "Full rebuild" to delete and re-create all chunks for a tenant.
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
                    {preview && !preview.error && preview.rows_to_delete > 0 && (
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
                            {running ? '⟳ Merging…' : `Merge ${preview.rows_to_delete} dupes`}
                        </button>
                    )}
                </div>
            </div>

            {/* Preview results */}
            {preview && !preview.error && (
                <div style={{ marginTop: 10 }}>
                    <div style={{
                        display: 'flex', gap: 16, marginBottom: 8, flexWrap: 'wrap',
                    }}>
                        {[
                            ['Duplicate groups', preview.duplicate_groups, '#f59e0b'],
                            ['Rows to delete',   preview.rows_to_delete,   '#ef4444'],
                            ['After dedup',      preview.schemes_after_dedup, '#22c55e'],
                        ].map(([l, v, c]) => (
                            <div key={l} style={{ textAlign: 'center' }}>
                                <div style={{ color: c, fontSize: 16, fontWeight: 700 }}>{v}</div>
                                <div style={{ color: '#6b7280', fontSize: 10 }}>{l}</div>
                            </div>
                        ))}
                    </div>
                    {preview.examples && preview.examples.length > 0 && (
                        <div style={{
                            background: '#111827', borderRadius: 6, padding: '8px 10px',
                            maxHeight: 160, overflowY: 'auto',
                        }}>
                            <div style={{ color: '#6b7280', fontSize: 10, marginBottom: 6 }}>
                                SAMPLE DUPLICATE GROUPS
                            </div>
                            {preview.examples.map((ex, i) => (
                                <div key={i} style={{ marginBottom: 6 }}>
                                    <span style={{ color: '#4b5563', fontSize: 10 }}>
                                        [{ex.key}]&nbsp;
                                    </span>
                                    <span style={{ color: '#9ca3af', fontSize: 11 }}>
                                        {ex.schemes.join(' · ')}
                                    </span>
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
                        : `Done — ${result.groups_merged} groups merged · ${result.rows_deleted} rows deleted · ${result.schemes_remaining} schemes remain`}
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
    const [statsLoading, setStatsLoading] = useState(true);
    const [jobs, setJobs] = useState({});  // jobId → job state
    const [crawlLimit, setCrawlLimit] = useState(50);
    const [includeFailedCrawl, setIncludeFailedCrawl] = useState(false);
    const [tagLimit, setTagLimit] = useState(500);
    const [indexAnswersOnly, setIndexAnswersOnly] = useState(false);
    const [indexRebuild, setIndexRebuild] = useState(false);
    const [allowOcr, setAllowOcr] = useState(false);

    const loadStats = useCallback(() => {
        setStatsLoading(true);
        apiGet('/api/admin/brain/global-stats')
            .then(d => setGlobalStats(d))
            .catch(() => {})
            .finally(() => setStatsLoading(false));
    }, []);

    useEffect(() => { loadStats(); }, [loadStats]);

    // Poll running jobs
    useEffect(() => {
        const running = Object.entries(jobs).filter(([, j]) => j.status === 'running');
        if (!running.length) return;
        const t = setInterval(async () => {
            for (const [jid] of running) {
                try {
                    const j = await apiGet(`/api/admin/brain/global-crawl/status/${jid}`);
                    setJobs(prev => ({ ...prev, [jid]: j }));
                    if (['done', 'error', 'warning'].includes(j.status)) loadStats();
                } catch (_) {}
            }
        }, 2000);
        return () => clearInterval(t);
    }, [jobs, loadStats]);

    const trigger = async (url, body = {}) => {
        try {
            const r = await apiPost(url, body);
            setJobs(prev => ({ ...prev, [r.job_id]: { status: 'running', type: r.job_id?.split('_')[1] } }));
        } catch (e) {
            alert(e.message || 'Failed to start job');
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

    return (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>

            {/* Left: stats */}
            <div>
                <div style={{ color: '#6b7280', fontSize: 11, marginBottom: 10 }}>GLOBAL CORPUS STATUS</div>
                {statsLoading ? (
                    <div style={{ color: '#6b7280', fontSize: 13 }}>Loading…</div>
                ) : (
                    <>
                        {/* Registry summary */}
                        <div style={{
                            background: '#111827', border: '1px solid #1f2937',
                            borderRadius: 8, padding: 14, marginBottom: 12,
                        }}>
                            <div style={{ color: '#9ca3af', fontSize: 11, marginBottom: 8 }}>MP REGISTRY</div>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8 }}>
                                {[
                                    ['Total MPs', reg.total_mps ?? '—', '#e5e7eb'],
                                    ['Crawled', reg.done ?? 0, '#22c55e'],
                                    ['Pending', reg.pending ?? 0, '#f59e0b'],
                                    ['Failed', reg.failed ?? 0, '#ef4444'],
                                    ['Running', reg.running ?? 0, '#60a5fa'],
                                ].map(([l, v, c]) => (
                                    <div key={l} style={{
                                        background: '#0d1117', borderRadius: 6,
                                        padding: '8px 10px', textAlign: 'center',
                                    }}>
                                        <div style={{ color: c, fontSize: 20, fontWeight: 700 }}>{v}</div>
                                        <div style={{ color: '#6b7280', fontSize: 10 }}>{l}</div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* PQ summary */}
                        <div style={{
                            background: '#111827', border: '1px solid #1f2937',
                            borderRadius: 8, padding: 14, marginBottom: 12,
                        }}>
                            <div style={{ color: '#9ca3af', fontSize: 11, marginBottom: 8 }}>GLOBAL QUESTIONS</div>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 8, marginBottom: 10 }}>
                                {[
                                    ['Total PQs', (pqs.total_questions ?? 0).toLocaleString(), '#e5e7eb'],
                                    ['Ministries', pqs.ministries ?? 0, '#60a5fa'],
                                    ['LLM Tagged', (pqs.llm_tagged ?? 0).toLocaleString(), '#818cf8'],
                                    ['Rule Tagged', (pqs.rule_tagged ?? 0).toLocaleString(), '#6b7280'],
                                ].map(([l, v, c]) => (
                                    <div key={l} style={{
                                        background: '#0d1117', borderRadius: 6,
                                        padding: '8px 10px', textAlign: 'center',
                                    }}>
                                        <div style={{ color: c, fontSize: 18, fontWeight: 700 }}>{v}</div>
                                        <div style={{ color: '#6b7280', fontSize: 10 }}>{l}</div>
                                    </div>
                                ))}
                            </div>
                            {/* Answer coverage progress bar */}
                            {(() => {
                                const total   = coverage.total || 0;
                                const withAns = coverage.with_answers || 0;
                                const pct     = coverage.pct_covered || 0;
                                const noMatch = coverage.no_match || 0;
                                const failed  = coverage.failed || 0;
                                const barW    = Math.round(pct);
                                return (
                                    <div style={{ padding: '4px 0' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                                            <span style={{ color: '#9ca3af', fontSize: 11 }}>Answer Coverage</span>
                                            <span style={{ color: pct > 50 ? '#22c55e' : pct > 20 ? '#f59e0b' : '#ef4444', fontSize: 11, fontWeight: 700 }}>
                                                {withAns.toLocaleString()} / {total.toLocaleString()} ({pct}%)
                                            </span>
                                        </div>
                                        <div style={{ height: 6, background: '#1f2937', borderRadius: 3, overflow: 'hidden' }}>
                                            <div style={{ width: `${barW}%`, height: '100%', background: pct > 50 ? '#22c55e' : pct > 20 ? '#f59e0b' : '#3b82f6', borderRadius: 3, transition: 'width 0.5s' }} />
                                        </div>
                                        {(noMatch > 0 || failed > 0) && (
                                            <div style={{ color: '#6b7280', fontSize: 10, marginTop: 4 }}>
                                                no_match: {noMatch.toLocaleString()}  |  failed: {failed.toLocaleString()}  |  with_pdf: {(coverage.with_pdf_url || 0).toLocaleString()}
                                            </div>
                                        )}
                                    </div>
                                );
                            })()}
                        </div>

                        {/* Ministry breakdown */}
                        {mins.length > 0 && (
                            <div style={{
                                background: '#111827', border: '1px solid #1f2937',
                                borderRadius: 8, padding: 14,
                            }}>
                                <div style={{ color: '#9ca3af', fontSize: 11, marginBottom: 8 }}>TOP MINISTRIES</div>
                                {mins.slice(0, 10).map((m, i) => {
                                    const pct = pqs.total_questions
                                        ? Math.round((m.total / pqs.total_questions) * 100) : 0;
                                    return (
                                        <div key={i} style={{ marginBottom: 6 }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                                                <span style={{ color: '#d1d5db', fontSize: 11 }}>
                                                    {(m.ministry || '').slice(0, 35)}
                                                </span>
                                                <span style={{ color: '#6b7280', fontSize: 11 }}>
                                                    {m.total} ({m.with_answers} ans)
                                                </span>
                                            </div>
                                            <div style={{ height: 3, background: '#1f2937', borderRadius: 2 }}>
                                                <div style={{
                                                    width: `${pct}%`, height: '100%',
                                                    background: '#3b82f6', borderRadius: 2,
                                                }} />
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}

                        <button
                            onClick={loadStats}
                            style={{
                                marginTop: 12, background: 'none',
                                border: '1px solid #374151', color: '#9ca3af',
                                borderRadius: 6, padding: '6px 14px',
                                fontSize: 12, cursor: 'pointer',
                            }}
                        >
                            ↻ Refresh
                        </button>
                    </>
                )}

                {/* Running jobs */}
                {Object.entries(jobs).length > 0 && (
                    <div style={{ marginTop: 16 }}>
                        <div style={{ color: '#6b7280', fontSize: 11, marginBottom: 8 }}>JOBS</div>
                        {Object.entries(jobs).map(([jid, j]) => {
                            const isWarning = j.status === 'warning';
                            const bg    = j.status === 'done' ? '#1a2e1f'
                                        : j.status === 'error' ? '#2d1f1f'
                                        : isWarning ? '#2d2810'
                                        : '#1f2937';
                            const bdr   = j.status === 'done' ? '#22c55e44'
                                        : j.status === 'error' ? '#ef444444'
                                        : isWarning ? '#f59e0b44'
                                        : '#374151';
                            const clr   = j.status === 'done' ? '#22c55e'
                                        : j.status === 'error' ? '#ef4444'
                                        : isWarning ? '#f59e0b'
                                        : '#60a5fa';
                            const icon  = j.status === 'running' ? '⟳'
                                        : j.status === 'done' ? '✓'
                                        : isWarning ? '⚠' : '✗';
                            return (
                                <div key={jid} style={{
                                    padding: '8px 12px', borderRadius: 6, marginBottom: 6,
                                    background: bg, border: `1px solid ${bdr}`, fontSize: 12,
                                }}>
                                    <div style={{ color: clr, fontWeight: 600 }}>
                                        {icon} {j.type || jid.split('_')[1]} — {j.status}
                                        {j.status === 'running' && j.progress && j.progress.total > 0 && (
                                            <span style={{ color: '#6b7280', fontWeight: 400, fontSize: 11, marginLeft: 8 }}>
                                                {j.progress.done}/{j.progress.total} {j.progress.label}
                                            </span>
                                        )}
                                    </div>
                                    {j.status === 'running' && j.progress && j.progress.total > 0 && (
                                        <div style={{ margin: '5px 0 3px', height: 4, background: '#1f2937', borderRadius: 2, overflow: 'hidden' }}>
                                            <div style={{
                                                width: `${Math.round((j.progress.done / j.progress.total) * 100)}%`,
                                                height: '100%', borderRadius: 2,
                                                background: '#3b82f6',
                                                transition: 'width 0.4s ease',
                                            }} />
                                        </div>
                                    )}
                                    {j.summary && (
                                        <div style={{ color: '#9ca3af', marginTop: 4, fontSize: 11 }}>
                                            {j.summary.discovered != null
                                                ? `discovered: ${j.summary.discovered} MPs, new: ${j.summary.new}, pages: ${j.summary.pages_scanned}`
                                                : j.summary.rows_updated != null
                                                ? `PDFs: ${(j.summary.pdfs_processed||0) + (j.summary.pdfs_from_cache||0)} (${j.summary.pdfs_from_cache||0} cached) · rows updated: ${j.summary.rows_updated} · unmatched: ${j.summary.rows_unmatched} · failed: ${j.summary.pdfs_failed}`
                                                : j.summary.crawled != null
                                                ? `crawled: ${j.summary.crawled} MPs, Qs inserted: ${j.summary.inserted_total}`
                                                : j.summary.chunks_inserted != null
                                                ? `${j.summary.chunks_inserted} chunks inserted · ${j.summary.embeddings_made} embeddings · ${j.summary.chunks_new} new (${j.summary.chunks_proposed} proposed)`
                                                : j.summary.tagged != null
                                                ? `tagged: ${j.summary.tagged} · batches: ${j.summary.batches} · skipped: ${j.summary.skipped}`
                                                : j.summary.schemes_upserted != null
                                                ? `${j.summary.mode || 'run'} · schemes upserted: ${j.summary.schemes_upserted} · subjects: ${j.summary.subjects_processed ?? 0} · rule: ${j.summary.rule_matched ?? 0} · gpt calls: ${j.summary.gpt_calls ?? 0}${j.summary.prs_schemes_stats?.total_schemes != null ? ` · total in DB: ${j.summary.prs_schemes_stats.total_schemes} (${j.summary.prs_schemes_stats.ministries} ministries)` : ''}`
                                                : JSON.stringify(j.summary).slice(0, 120)
                                            }
                                        </div>
                                    )}
                                    {j.error && (
                                        <div style={{
                                            color: isWarning ? '#f59e0b' : '#ef4444',
                                            marginTop: 4, lineHeight: 1.5,
                                        }}>{j.error}</div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Right: controls */}
            <div>
                <div style={{ color: '#6b7280', fontSize: 11, marginBottom: 10 }}>PIPELINE CONTROLS</div>

                {/* Step 1 */}
                <div style={{ color: '#4b5563', fontSize: 10, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 }}>
                    Step 1 — Discover MPs
                </div>
                <BtnRow
                    label="Discover all MPs"
                    desc="Crawl PRS listing pages to find all ~543 18th Lok Sabha MPs"
                    onClick={() => trigger('/api/admin/brain/global-discover')}
                    disabled={anyRunning}
                />

                {/* Fallback: seed from JSON if PRS requires JS rendering */}
                <SeedPanel />

                {/* Step 2 */}
                <div style={{ color: '#4b5563', fontSize: 10, margin: '14px 0 6px', textTransform: 'uppercase', letterSpacing: 1 }}>
                    Step 2 — Crawl PQs
                </div>
                <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
                    <label style={{ color: '#9ca3af', fontSize: 12 }}>
                        Limit:&nbsp;
                        <input
                            type="number" min={1} max={543} value={crawlLimit}
                            onChange={e => setCrawlLimit(Math.max(1, parseInt(e.target.value) || 50))}
                            style={{
                                background: '#1f2937', border: '1px solid #374151', color: '#e5e7eb',
                                borderRadius: 4, padding: '3px 8px', fontSize: 12, width: 64,
                            }}
                        />
                        &nbsp;MPs
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#9ca3af', fontSize: 12, cursor: 'pointer' }}>
                        <input type="checkbox" checked={includeFailedCrawl} onChange={e => setIncludeFailedCrawl(e.target.checked)} style={{ accentColor: '#3b82f6' }} />
                        Retry failed
                    </label>
                </div>
                <BtnRow
                    label="Crawl pending MPs"
                    desc="Fetch PQs from PRS India for MPs not yet crawled"
                    onClick={() => trigger('/api/admin/brain/global-crawl', { limit: crawlLimit, include_failed: includeFailedCrawl })}
                    accent="#7c3aed"
                    disabled={anyRunning}
                />

                {/* Step 2.5 — Fetch Answers */}
                <div style={{ color: '#4b5563', fontSize: 10, margin: '14px 0 6px', textTransform: 'uppercase', letterSpacing: 1 }}>
                    Step 2.5 — Fetch Ministry Answers
                </div>
                <div style={{
                    background: '#0d1117', border: '1px solid #1f2937',
                    borderRadius: 8, padding: '10px 14px', marginBottom: 10,
                }}>
                    <div style={{ color: '#9ca3af', fontSize: 11, marginBottom: 8, lineHeight: 1.5 }}>
                        Downloads ministry Q&amp;A PDFs from PRS India and extracts full question + answer text.
                        Uses <strong style={{ color: '#e5e7eb' }}>shared PDF cache</strong> — PDFs already
                        fetched for your MP's questions are served instantly without re-downloading.
                        Runs pdfplumber (primary) + Gemini OCR fallback for scanned/Hindi PDFs.
                    </div>
                    <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
                        <label style={{ color: '#9ca3af', fontSize: 12 }}>
                            Batch:&nbsp;
                            <input
                                type="number" min={10} max={5000} value={answerLimit}
                                onChange={e => setAnswerLimit(Math.max(10, parseInt(e.target.value) || 100))}
                                style={{
                                    background: '#1f2937', border: '1px solid #374151', color: '#e5e7eb',
                                    borderRadius: 4, padding: '3px 8px', fontSize: 12, width: 72,
                                }}
                            />
                            &nbsp;PDFs
                        </label>
                        <label style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#9ca3af', fontSize: 12, cursor: 'pointer' }}>
                            <input type="checkbox" checked={allowOcr} onChange={e => setAllowOcr(e.target.checked)} style={{ accentColor: '#f59e0b' }} />
                            Gemini OCR&nbsp;<span style={{ color: '#6b7280', fontSize: 11 }}>(slow — for scanned PDFs)</span>
                        </label>
                        <span style={{ color: '#4b5563', fontSize: 11 }}>
                            ~49K PQs → ~2K unique PDFs (session bundles)
                        </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                        <RematchButton onDone={loadStats} />
                        <button
                            onClick={() => trigger('/api/admin/brain/global-fetch-answers', { limit: answerLimit, allow_ocr: allowOcr })}
                            disabled={anyRunning}
                            style={{
                                background: anyRunning ? '#374151' : '#059669',
                                color: '#fff', border: 'none', borderRadius: 6,
                                padding: '7px 18px', fontSize: 12,
                                cursor: anyRunning ? 'not-allowed' : 'pointer',
                            }}
                        >
                            Fetch Answers
                        </button>
                    </div>
                </div>

                {/* Step 3 */}
                <div style={{ color: '#4b5563', fontSize: 10, margin: '14px 0 6px', textTransform: 'uppercase', letterSpacing: 1 }}>
                    Step 3 — LLM Tag (optional)
                </div>
                <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 8 }}>
                    <label style={{ color: '#9ca3af', fontSize: 12 }}>
                        Limit:&nbsp;
                        <input
                            type="number" min={1} value={tagLimit}
                            onChange={e => setTagLimit(Math.max(1, parseInt(e.target.value) || 500))}
                            style={{
                                background: '#1f2937', border: '1px solid #374151', color: '#e5e7eb',
                                borderRadius: 4, padding: '3px 8px', fontSize: 12, width: 72,
                            }}
                        />
                        &nbsp;questions
                    </label>
                </div>
                <BtnRow
                    label="LLM tag questions"
                    desc="Use GPT-4o-mini to generate richer topic tags for retrieval"
                    onClick={() => trigger('/api/admin/brain/global-tag', { limit: tagLimit })}
                    accent="#0891b2"
                    disabled={anyRunning}
                />

                {/* Step 4 */}
                <div style={{ color: '#4b5563', fontSize: 10, margin: '14px 0 6px', textTransform: 'uppercase', letterSpacing: 1 }}>
                    Step 4 — Embed into Brain
                </div>
                <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#9ca3af', fontSize: 12, cursor: 'pointer' }}>
                        <input type="checkbox" checked={indexAnswersOnly} onChange={e => setIndexAnswersOnly(e.target.checked)} style={{ accentColor: '#3b82f6' }} />
                        Only Q&amp;A with answers
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#9ca3af', fontSize: 12, cursor: 'pointer' }}>
                        <input type="checkbox" checked={indexRebuild} onChange={e => setIndexRebuild(e.target.checked)} style={{ accentColor: '#ef4444' }} />
                        Full rebuild
                    </label>
                </div>
                <BtnRow
                    label="Embed global PQs"
                    desc="Index global_pq_qa chunks into memory_chunks for retrieval"
                    onClick={() => trigger('/api/admin/brain/global-index', { only_with_answers: indexAnswersOnly, rebuild: indexRebuild })}
                    accent="#166534"
                    disabled={anyRunning}
                />

                {/* Step 5 */}
                <div style={{ color: '#4b5563', fontSize: 10, margin: '14px 0 6px', textTransform: 'uppercase', letterSpacing: 1 }}>
                    Step 5 — Build Scheme Intelligence
                </div>
                <BtnRow
                    label="Build Scheme Index"
                    desc="Extract government schemes from 42K+ PQs and power the Schemes module — auto full vs incremental"
                    onClick={() => trigger('/api/admin/brain/scheme-extract', {})}
                    accent="#b45309"
                    disabled={anyRunning}
                />
                <DedupPanel disabled={anyRunning} />

                <div style={{
                    marginTop: 20, background: '#0d1117',
                    border: '1px solid #1f2937', borderRadius: 8, padding: 14,
                    fontSize: 12, color: '#6b7280', lineHeight: 1.7,
                }}>
                    <strong style={{ color: '#9ca3af' }}>How cross-MP retrieval works:</strong><br />
                    After Step 4, any Copilot or Drafter query with <code>include_cross_mp=True</code> will retrieve
                    global_pq_qa chunks alongside the tenant&apos;s own PQs. Each chunk is clearly attributed:
                    <em style={{ color: '#818cf8' }}> &quot;[asked by Shri X (Party, Constituency)]&quot;</em>.<br /><br />
                    The Drafter (PQ mode) automatically enables cross-MP retrieval to show the MP
                    what has already been asked — and what the Ministry replied — before drafting a new question.
                </div>
            </div>
        </div>
    );
}
