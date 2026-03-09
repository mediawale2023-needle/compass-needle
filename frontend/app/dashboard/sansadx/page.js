'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPatch } from '@/lib/api';

const TABS = [
    { key: 'All', label: 'All Cases' },
    { key: 'new', label: 'New' },
    { key: 'in_progress', label: 'In Progress' },
    { key: 'resolved', label: 'Resolved' },
    { key: 'escalated', label: 'Escalated' },
    { key: 'closed', label: 'Closed' },
    { key: 'other', label: 'Other' },
];

const OTHER_CATEGORIES = ['Request', 'Greetings', 'Spam', 'Spam (Offensive)'];

// Colors matching Figma rows
function getRowStyle(status, category, color) {
    const s = (status || '').toLowerCase();
    const c = (category || '').toLowerCase();

    if (s === 'new' || s === 'escalated' || c === 'emergency') {
        return { background: '#fdf2f2', borderLeft: '4px solid #dc2626' }; // Red tinted bg + border
    }
    if (s === 'resolved' || s === 'in_progress') {
        return { background: '#f0fdf4', borderLeft: `4px solid ${color}` }; // Green tinted bg + border
    }
    return { background: '#ffffff', borderLeft: '4px solid transparent' };
}

// Figma-style status pills
function StatusPill({ status }) {
    const s = (status || 'New').toLowerCase();
    if (s === 'new') return <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded" style={{ background: '#e0f2fe', color: '#0369a1' }}>New</span>;
    if (s === 'in_progress') return <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded" style={{ background: '#fef3c7', color: '#b45309' }}>In Progress</span>;
    if (s === 'resolved') return <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded" style={{ background: '#dcfce7', color: '#15803d' }}>Resolved</span>;
    if (s === 'escalated') return <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded" style={{ background: '#fee2e2', color: '#b91c1c' }}>Escalated</span>;
    if (s === 'closed') return <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded" style={{ background: '#f3f4f6', color: '#4b5563' }}>Closed</span>;
    return <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-gray-100 text-gray-600">{status}</span>;
}

export default function BriefcasePage() {
    const { user } = useAuth();
    const [cases, setCases] = useState([]);
    const [loading, setLoading] = useState(true);
    const [statusFilter, setStatusFilter] = useState('All');

    const color = user?.theme_color || '#006a4d';

    const fetchCases = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams({ page: '1', limit: '50' });
            if (statusFilter === 'other') params.set('categories', OTHER_CATEGORIES.join(','));
            else if (statusFilter !== 'All') params.set('status', statusFilter);

            const data = await apiGet(`/api/cases?${params}`);
            setCases(data.cases || []);
        } catch (err) { console.error(err); }
        finally { setLoading(false); }
    };

    useEffect(() => { fetchCases(); }, [statusFilter]);

    return (
        <div className="space-y-4">
            <h1 className="text-lg font-bold text-gray-900">Briefcase</h1>

            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden pt-2">
                {/* Horizontal Tabs - Figma layout */}
                <div className="px-6 border-b border-gray-100 flex gap-6">
                    {TABS.map(t => (
                        <button key={t.key} onClick={() => setStatusFilter(t.key)}
                            className="text-sm font-semibold pb-3 transition-colors"
                            style={statusFilter === t.key
                                ? { color, borderBottom: `2px solid ${color}` }
                                : { color: '#6b7280', borderBottom: '2px solid transparent' }}>
                            {t.label}
                        </button>
                    ))}
                </div>

                {/* Table */}
                <div className="overflow-x-auto">
                    {loading ? (
                        <div className="text-center py-10 text-gray-400 text-sm">Loading cases...</div>
                    ) : cases.length === 0 ? (
                        <div className="text-center py-10 text-gray-400 text-sm">No cases found in this category.</div>
                    ) : (
                        <table className="sansad-table w-full">
                            <thead>
                                <tr>
                                    <th className="pl-6">#</th>
                                    <th>CONTACT</th>
                                    <th>CATEGORY</th>
                                    <th>LOCATION</th>
                                    <th>ASSEMBLY</th>
                                    <th>STATUS</th>
                                    <th>MESSAGE</th>
                                </tr>
                            </thead>
                            <tbody>
                                {cases.map((c) => (
                                    <tr key={c.id} style={getRowStyle(c.status, c.category, color)}>
                                        <td className="pl-6 text-gray-500 font-mono text-xs">{c.id}</td>
                                        <td className="font-mono text-xs text-gray-700">{c.user_phone || '—'}</td>
                                        <td className="font-medium text-gray-800">{c.category || 'General'}</td>
                                        <td className="text-gray-600">{c.location || '—'}</td>
                                        <td className="text-gray-600">{c.assembly || '—'}</td>
                                        <td><StatusPill status={c.status} /></td>
                                        <td className="max-w-[200px] text-gray-600 text-sm">
                                            <div className="truncate" title={c.raw_message}>{c.raw_message || '—'}</div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            </div>
        </div>
    );
}
