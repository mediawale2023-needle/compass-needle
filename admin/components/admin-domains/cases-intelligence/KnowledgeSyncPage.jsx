'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { apiGet } from '@/lib/api';
import ConstituencyIntelPage from '@/app/dashboard/constituency/page';
import ParliamentSyncPage from '@/components/admin-domains/system/ParliamentSyncPage';

const TABS = [
    { key: 'overview', label: 'Overview' },
    { key: 'constituency', label: 'Constituency Profiles' },
    { key: 'parliament', label: 'Parliament Records' },
    { key: 'quality', label: 'Quality Checks' },
];

const STATUS_TONE = {
    ready: { label: 'Ready', bg: '#dcfce7', color: '#166534' },
    review: { label: 'Review', bg: '#fef9c3', color: '#854d0e' },
    missing: { label: 'Missing', bg: '#fee2e2', color: '#991b1b' },
    partial: { label: 'Partial', bg: '#dbeafe', color: '#1d4ed8' },
};

function Badge({ tone = 'partial', children }) {
    const t = STATUS_TONE[tone] || STATUS_TONE.partial;
    return (
        <span style={{
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            borderRadius: 999, padding: '2px 9px', fontSize: '0.68rem',
            fontWeight: 800, background: t.bg, color: t.color,
        }}>
            {children || t.label}
        </span>
    );
}

function fmtDate(value) {
    if (!value) return '—';
    try {
        return new Date(value).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
    } catch {
        return String(value).slice(0, 10);
    }
}

function pctTone(value) {
    if (value >= 80) return '#006a4d';
    if (value >= 40) return '#d97706';
    return '#dc2626';
}

function StatCard({ label, value, tone = '#006a4d', hint }) {
    return (
        <div className="stat-card">
            <div style={{ fontSize: '1.65rem', fontWeight: 850, color: tone, lineHeight: 1 }}>{value}</div>
            <div style={{ marginTop: 6, color: '#6b7f76', fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                {label}
            </div>
            {hint && <div style={{ marginTop: 4, color: '#94a3a0', fontSize: '0.7rem' }}>{hint}</div>}
        </div>
    );
}

function normalizeBrainRows(stats) {
    return (stats?.per_tenant || []).filter(r => r.tenant_id).map(r => ({
        tenant_id: r.tenant_id,
        total_chunks: r.total_chunks || 0,
        last_indexed: r.last_indexed || null,
    }));
}

function buildRows({ mps, profiles, parliament, coverage, brain }) {
    const profileByTenant = new Map();
    profiles.forEach(p => {
        if (p.tenant_id) profileByTenant.set(Number(p.tenant_id), p);
    });

    const parliamentByTenant = new Map();
    parliament.forEach(p => parliamentByTenant.set(Number(p.tenant_id), p));

    const coverageByTenant = new Map();
    coverage.forEach(c => coverageByTenant.set(Number(c.tenant_id), c));

    const brainByTenant = new Map();
    brain.forEach(b => brainByTenant.set(Number(b.tenant_id), b));

    return mps.map(mp => {
        const tid = Number(mp.tenant_id);
        const constProfile = profileByTenant.get(tid);
        const parl = parliamentByTenant.get(tid);
        const cov = coverageByTenant.get(tid);
        const brainStats = brainByTenant.get(tid);
        const parliamentReady = ['active', 'auto_matched'].includes(parl?.parliament_sync_status);
        const parliamentNeedsReview = parl?.parliament_sync_status === 'needs_review';
        const profileReady = !!constProfile;
        const brainReady = (brainStats?.total_chunks || 0) > 0;
        const answerPct = cov?.pct_covered ?? null;

        const issues = [];
        if ((mp.completeness || 0) < 70) issues.push('Low MP profile');
        if (!profileReady) issues.push('Missing constituency profile');
        if (!parliamentReady) issues.push(parliamentNeedsReview ? 'Parliament match needs review' : 'Parliament ID missing');
        if (parliamentReady && !cov) issues.push('No PQ answer coverage');
        if (cov && answerPct < 50) issues.push('Low answer coverage');
        if (!brainReady) issues.push('Brain not indexed');

        return {
            tenant_id: tid,
            name: mp.display_name || mp.mp_name || mp.username,
            username: mp.username,
            constituency: mp.parliamentary_constituency,
            state: constProfile?.state || parl?.state || mp.profile?.state || '',
            profileCompleteness: mp.completeness || 0,
            constProfile,
            parliament: parl,
            coverage: cov,
            brain: brainStats,
            issues,
        };
    });
}

function KnowledgeOverview() {
    const [data, setData] = useState({
        mps: [],
        profiles: [],
        parliament: [],
        coverage: [],
        brain: [],
    });
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [filter, setFilter] = useState('all');

    useEffect(() => {
        let cancelled = false;
        async function load() {
            setLoading(true);
            setError('');
            try {
                const [mpsRes, profilesRes, parliamentRes, coverageRes, brainRes] = await Promise.all([
                    apiGet('/api/admin/mps').catch(() => ({ mps: [] })),
                    apiGet('/api/admin/constituency-profiles').catch(() => ({ profiles: [] })),
                    apiGet('/api/admin/parliament/sync/status').catch(() => ({ tenants: [] })),
                    apiGet('/api/admin/parliament/answer-coverage').catch(() => ({ tenants: [] })),
                    apiGet('/api/admin/brain/stats').catch(() => ({ per_tenant: [] })),
                ]);
                if (cancelled) return;
                setData({
                    mps: (mpsRes.mps || []).filter(m => m.role !== 'admin' && m.tenant_id),
                    profiles: profilesRes.profiles || [],
                    parliament: parliamentRes.tenants || [],
                    coverage: coverageRes.tenants || [],
                    brain: normalizeBrainRows(brainRes),
                });
            } catch (e) {
                if (!cancelled) setError(e.message || 'Failed to load knowledge sync overview');
            } finally {
                if (!cancelled) setLoading(false);
            }
        }
        load();
        return () => { cancelled = true; };
    }, []);

    const rows = useMemo(() => buildRows(data), [data]);
    const filteredRows = rows.filter(r => {
        if (filter === 'ready') return r.issues.length === 0;
        if (filter === 'action') return r.issues.length > 0;
        if (filter === 'missing_constituency') return !r.constProfile;
        if (filter === 'parliament_review') return !['active', 'auto_matched'].includes(r.parliament?.parliament_sync_status);
        if (filter === 'brain_missing') return !(r.brain?.total_chunks > 0);
        return true;
    });

    const stats = {
        total: rows.length,
        ready: rows.filter(r => r.issues.length === 0).length,
        missingProfiles: rows.filter(r => !r.constProfile).length,
        parliamentAction: rows.filter(r => !['active', 'auto_matched'].includes(r.parliament?.parliament_sync_status)).length,
        brainMissing: rows.filter(r => !(r.brain?.total_chunks > 0)).length,
    };

    if (loading) {
        return (
            <div style={{ display: 'grid', gap: 12 }}>
                {[...Array(5)].map((_, i) => <div key={i} className="glass-panel skeleton" style={{ height: 86 }} />)}
            </div>
        );
    }

    return (
        <div style={{ display: 'grid', gap: 18 }}>
            {error && <div className="toast toast-error" style={{ position: 'relative' }}>{error}</div>}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(0, 1fr))', gap: 12 }}>
                <StatCard label="Tenants" value={stats.total} tone="#1a2e28" />
                <StatCard label="Knowledge Ready" value={stats.ready} tone="#006a4d" />
                <StatCard label="Missing Profiles" value={stats.missingProfiles} tone="#dc2626" />
                <StatCard label="Parliament Action" value={stats.parliamentAction} tone="#d97706" />
                <StatCard label="Brain Missing" value={stats.brainMissing} tone="#7c3aed" />
            </div>

            <div className="glass-panel">
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, marginBottom: 16 }}>
                    <div>
                        <h2 style={{ margin: 0, color: '#1a2e28', fontSize: '1rem', fontWeight: 850 }}>Tenant Knowledge Readiness</h2>
                        <p style={{ margin: '5px 0 0', color: '#6b7f76', fontSize: '0.82rem' }}>
                            One control plane for constituency profile, parliament record sync, answer coverage, and brain index status.
                        </p>
                    </div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                        {[
                            ['all', 'All'],
                            ['action', 'Action Required'],
                            ['ready', 'Ready'],
                            ['missing_constituency', 'Missing Profile'],
                            ['parliament_review', 'Parliament Review'],
                            ['brain_missing', 'Brain Missing'],
                        ].map(([key, label]) => (
                            <button
                                key={key}
                                className={filter === key ? 'btn-primary' : 'btn-secondary'}
                                style={{ padding: '6px 11px', fontSize: '0.72rem' }}
                                onClick={() => setFilter(key)}
                            >
                                {label}
                            </button>
                        ))}
                    </div>
                </div>

                <div style={{ overflow: 'auto', border: '1px solid #e2ebe5', borderRadius: 12 }}>
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Tenant</th>
                                <th>MP Profile</th>
                                <th>Constituency Profile</th>
                                <th>Parliament Sync</th>
                                <th>PQ Answers</th>
                                <th>Brain Index</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filteredRows.map(row => {
                                const parliamentStatus = row.parliament?.parliament_sync_status || 'pending';
                                const parliamentTone = ['active', 'auto_matched'].includes(parliamentStatus)
                                    ? 'ready' : parliamentStatus === 'needs_review' ? 'review' : 'missing';
                                const profileTone = row.constProfile ? 'ready' : 'missing';
                                const brainTone = row.brain?.total_chunks > 0 ? 'ready' : 'missing';
                                const answerTone = !row.coverage ? 'missing' : row.coverage.pct_covered >= 70 ? 'ready' : 'review';

                                return (
                                    <tr key={row.tenant_id}>
                                        <td>
                                            <div style={{ fontWeight: 800, color: '#1a2e28' }}>{row.name}</div>
                                            <div style={{ color: '#6b7f76', fontSize: '0.72rem', marginTop: 2 }}>
                                                Tenant #{row.tenant_id} · {row.constituency || '—'}
                                            </div>
                                            {row.issues.length > 0 && (
                                                <div style={{ color: '#dc2626', fontSize: '0.68rem', marginTop: 4, fontWeight: 650 }}>
                                                    {row.issues.slice(0, 2).join(', ')}{row.issues.length > 2 ? ` +${row.issues.length - 2}` : ''}
                                                </div>
                                            )}
                                        </td>
                                        <td>
                                            <div style={{ color: pctTone(row.profileCompleteness), fontWeight: 850 }}>{row.profileCompleteness}%</div>
                                            <div className="completeness-bar" style={{ width: 90, height: 5, marginTop: 5 }}>
                                                <div className={`completeness-fill ${row.profileCompleteness >= 70 ? 'fill-good' : row.profileCompleteness >= 40 ? 'fill-mid' : 'fill-low'}`} style={{ width: `${row.profileCompleteness}%` }} />
                                            </div>
                                        </td>
                                        <td>
                                            <Badge tone={profileTone}>{row.constProfile ? 'Linked' : 'Missing'}</Badge>
                                            <div style={{ marginTop: 5, color: '#6b7f76', fontSize: '0.7rem' }}>
                                                {row.constProfile ? `${row.constProfile.name} · ${fmtDate(row.constProfile.last_updated)}` : 'No profile JSON'}
                                            </div>
                                        </td>
                                        <td>
                                            <Badge tone={parliamentTone}>{parliamentStatus.replace('_', ' ')}</Badge>
                                            <div style={{ marginTop: 5, color: '#6b7f76', fontSize: '0.7rem' }}>
                                                {row.parliament?.parliament_member_id ? `mpsno ${row.parliament.parliament_member_id}` : 'No member ID'}
                                            </div>
                                        </td>
                                        <td>
                                            <Badge tone={answerTone}>{row.coverage ? `${row.coverage.pct_covered}%` : 'No data'}</Badge>
                                            <div style={{ marginTop: 5, color: '#6b7f76', fontSize: '0.7rem' }}>
                                                {row.coverage ? `${row.coverage.with_answer}/${row.coverage.total} answered` : 'Run parliament backfill first'}
                                            </div>
                                        </td>
                                        <td>
                                            <Badge tone={brainTone}>{row.brain?.total_chunks ? `${row.brain.total_chunks} chunks` : 'Missing'}</Badge>
                                            <div style={{ marginTop: 5, color: '#6b7f76', fontSize: '0.7rem' }}>
                                                {row.brain?.last_indexed ? fmtDate(row.brain.last_indexed) : 'Not indexed'}
                                            </div>
                                        </td>
                                        <td>
                                            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                                <Link className="btn-secondary" style={{ padding: '5px 10px', fontSize: '0.72rem', textDecoration: 'none' }} href={`/dashboard/mps/${row.tenant_id}`}>
                                                    Tenant 360
                                                </Link>
                                                <Link className="btn-secondary" style={{ padding: '5px 10px', fontSize: '0.72rem', textDecoration: 'none' }} href={`/dashboard/accounts/registry?tenant_id=${row.tenant_id}`}>
                                                    MP Profile
                                                </Link>
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                    {filteredRows.length === 0 && (
                        <div style={{ padding: 28, color: '#6b7f76', textAlign: 'center', fontSize: '0.85rem' }}>
                            No tenants match this filter.
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function QualityChecks() {
    return (
        <div className="glass-panel">
            <h2 style={{ margin: 0, color: '#1a2e28', fontSize: '1rem', fontWeight: 850 }}>Quality Checks</h2>
            <p style={{ margin: '6px 0 18px', color: '#6b7f76', fontSize: '0.82rem' }}>
                Use the overview table for now. This tab is reserved for deeper cross-source consistency checks.
            </p>
            <div style={{ display: 'grid', gap: 10 }}>
                {[
                    'Tenant profile name, constituency, and state should match constituency profile metadata.',
                    'Every active MP tenant should have one linked constituency profile JSON.',
                    'Confirmed parliament identities should have records in at least one parliamentary data table.',
                    'Question answer coverage below 50% should be reviewed after backfill.',
                    'Brain chunks should exist after constituency and parliament sources are updated.',
                ].map(item => (
                    <div key={item} style={{ border: '1px solid #e2ebe5', borderRadius: 10, padding: '10px 12px', color: '#1a2e28', fontSize: '0.82rem', background: '#f8faf9' }}>
                        {item}
                    </div>
                ))}
            </div>
        </div>
    );
}

export default function KnowledgeSyncPage() {
    const [tab, setTab] = useState('overview');

    return (
        <div style={{ display: 'grid', gap: 18 }}>
            <div className="glass-panel" style={{ padding: 14 }}>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {TABS.map(t => (
                        <button
                            key={t.key}
                            className={tab === t.key ? 'btn-primary' : 'btn-secondary'}
                            style={{ padding: '8px 14px', fontSize: '0.78rem' }}
                            onClick={() => setTab(t.key)}
                        >
                            {t.label}
                        </button>
                    ))}
                </div>
                <div style={{ marginTop: 10, color: '#6b7f76', fontSize: '0.75rem' }}>
                    Standalone routes remain available: <Link href="/dashboard/constituency" style={{ color: '#006a4d', fontWeight: 700 }}>Constituency Intel</Link>
                    {' '}and{' '}
                    <Link href="/dashboard/system/parliament-sync" style={{ color: '#006a4d', fontWeight: 700 }}>Parliament Sync</Link>.
                </div>
            </div>

            {tab === 'overview' && <KnowledgeOverview />}
            {tab === 'constituency' && <ConstituencyIntelPage />}
            {tab === 'parliament' && <ParliamentSyncPage />}
            {tab === 'quality' && <QualityChecks />}
        </div>
    );
}
