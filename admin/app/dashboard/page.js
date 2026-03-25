'use client';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { apiGet } from '@/lib/api';

export default function DashboardOverview() {
    const [stats, setStats] = useState(null);
    const [mps, setMps] = useState([]);
    const [search, setSearch] = useState('');

    useEffect(() => {
        apiGet('/api/admin/stats').then(setStats).catch(() => { });
        apiGet('/api/admin/mps').then(r => setMps(r.mps || [])).catch(() => { });
    }, []);

    const filteredMps = search
        ? mps.filter(m =>
            m.display_name.toLowerCase().includes(search.toLowerCase()) ||
            m.username.toLowerCase().includes(search.toLowerCase()) ||
            m.parliamentary_constituency.toLowerCase().includes(search.toLowerCase())
        )
        : mps;

    return (
        <>
            {/* Stat Cards */}
            {stats && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 16, marginBottom: '1.5rem' }}>
                    <StatCard icon="👥" value={stats.total_mps} label="Total MPs" accent="#006a4d" />
                    <StatCard icon="🏛️" value={stats.lok_sabha} label="Lok Sabha" accent="#059669" />
                    <StatCard icon="🏛️" value={stats.rajya_sabha} label="Rajya Sabha" accent="#8d153a" />
                    <StatCard icon="⚡" value={stats.total_prs || 0} label="Ambassador" accent="#2563eb" />
                    <StatCard icon="📋" value={stats.total_profiles} label="Profiles" accent="#d97706" />
                    <StatCard icon="📩" value={stats.total_cases} label="Total Cases" accent="#0891b2" />
                </div>
            )}

            {/* MP Management */}
            <div className="section-title">Members of Parliament</div>

            <div style={{ display: 'flex', gap: 12, marginBottom: '1rem', alignItems: 'center' }}>
                <input
                    type="text"
                    className="form-input"
                    placeholder="Search by name, constituency, or username..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    style={{ flex: 1 }}
                />
                <Link href="/dashboard/prs/new" className="btn-secondary" style={{ textDecoration: 'none', whiteSpace: 'nowrap', padding: '10px 16px' }}>
                    + Create PR (Ambassador)
                </Link>
                <Link href="/dashboard/mps/new" className="btn-primary" style={{ textDecoration: 'none', whiteSpace: 'nowrap' }}>
                    + Add New MP
                </Link>
            </div>

            {filteredMps.length === 0 ? (
                <div className="glass-panel" style={{ textAlign: 'center', color: '#6b7f76', padding: '2rem' }}>
                    {search ? 'No MPs match your search.' : 'No MPs registered yet. Click "Add New MP" to create one.'}
                </div>
            ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                    {filteredMps.map((mp) => (
                        <MpCard key={mp.user_id} mp={mp} />
                    ))}
                </div>
            )}
        </>
    );
}

function StatCard({ icon, value, label, accent }) {
    return (
        <div className="stat-card">
            <div style={{ fontSize: '1.4rem', marginBottom: 6 }}>{icon}</div>
            <div style={{ fontSize: '2rem', fontWeight: 800, color: accent, lineHeight: 1 }}>{value}</div>
            <div style={{ color: '#6b7f76', fontSize: '0.78rem', fontWeight: 500, marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.8px' }}>{label}</div>
        </div>
    );
}

function MpCard({ mp }) {
    const isPR = mp.role === 'pr';
    const initials = mp.display_name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();
    const isLS = mp.house === 'Lok Sabha';
    const completeness = mp.completeness || 0;
    const fillClass = completeness >= 70 ? 'fill-good' : completeness >= 40 ? 'fill-mid' : 'fill-low';

    let bgStyle = 'linear-gradient(135deg, #1f2937, #111827)'; // Dark Gray for PR
    let tagLabel = 'PR';
    let tagStyle = { background: '#e0e7ff', color: '#3730a3', border: '1px solid #c7d2fe' };

    if (!isPR) {
        bgStyle = isLS ? 'linear-gradient(135deg, #006a4d, #00875f)' : 'linear-gradient(135deg, #8d153a, #b91c50)';
        tagLabel = isLS ? 'LS' : 'RS';
        tagStyle = isLS ? { background: '#ecfdf5', color: '#047857' } : { background: '#fdf2f8', color: '#be185d' };
    }

    return (
        <div className="mp-card">
            <div style={{
                width: 44, height: 44, borderRadius: 12,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontWeight: 700, fontSize: '1rem', color: 'white', flexShrink: 0,
                background: bgStyle,
            }}>
                {initials}
            </div>
            <div style={{ flex: 1 }}>
                <div style={{ color: '#1a2e28', fontWeight: 600, fontSize: '0.9rem' }}>{mp.display_name}</div>
                <div style={{ color: '#6b7f76', fontSize: '0.75rem', marginTop: 2 }}>
                    @{mp.username} · {mp.parliamentary_constituency}
                </div>
                <div className="completeness-bar" style={{ marginTop: 6 }}>
                    <div className={`completeness-fill ${fillClass}`} style={{ width: `${completeness}%` }} />
                </div>
            </div>
            <span className="tag" style={tagStyle}>{tagLabel}</span>
        </div>
    );
}
