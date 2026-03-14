'use client';

import { useState, useEffect, Suspense } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPatch } from '@/lib/api';
import { useSearchParams, useRouter } from 'next/navigation';

const TABS = [
    { key: 'All', label: 'All Cases' },
    { key: 'new', label: 'New' },
    { key: 'in_progress', label: 'In Progress' },
    { key: 'resolved', label: 'Resolved' },
    { key: 'escalated', label: 'Escalated' },
    { key: 'closed', label: 'Closed' },
    { key: 'other', label: 'Other' },
];

const STATUS_OPTIONS = [
    { value: 'new', label: 'New', bg: '#e0f2fe', fg: '#0369a1' },
    { value: 'in_progress', label: 'In Progress', bg: '#fef3c7', fg: '#b45309' },
    { value: 'resolved', label: 'Resolved', bg: '#dcfce7', fg: '#15803d' },
    { value: 'escalated', label: 'Escalated', bg: '#fee2e2', fg: '#b91c1c' },
    { value: 'closed', label: 'Closed', bg: '#f3f4f6', fg: '#4b5563' },
    { value: 'irrelevant', label: 'Irrelevant', bg: '#f3f4f6', fg: '#9ca3af' },
];

const OTHER_CATEGORIES = ['Request', 'Greetings', 'Spam', 'Spam (Offensive)'];

function getRowStyle(status, category, color) {
    const s = (status || '').toLowerCase();
    const c = (category || '').toLowerCase();
    if (s === 'new' || s === 'escalated' || c === 'emergency') {
        return { background: '#fdf2f2', borderLeft: '4px solid #dc2626' };
    }
    if (s === 'resolved' || s === 'in_progress') {
        return { background: '#f0fdf4', borderLeft: `4px solid ${color}` };
    }
    return { background: '#ffffff', borderLeft: '4px solid transparent' };
}

function StatusPill({ status }) {
    const opt = STATUS_OPTIONS.find(o => o.value === (status || '').toLowerCase());
    if (opt) return <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded" style={{ background: opt.bg, color: opt.fg }}>{opt.label}</span>;
    return <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-gray-100 text-gray-600">{status}</span>;
}


// ═══════════════════════════════════════════
// CASE DETAIL MODAL
// ═══════════════════════════════════════════
function CaseModal({ caseItem, color, onClose, onStatusChange }) {
    const [updating, setUpdating] = useState(null);

    const c = caseItem;
    const meta = c.case_metadata || {};
    const createdAt = c.created_at ? new Date(c.created_at) : null;
    const updatedAt = c.updated_at ? new Date(c.updated_at) : null;

    const handleStatusChange = async (newStatus) => {
        setUpdating(newStatus);
        try {
            await apiPatch(`/api/cases/${c.id}/status`, { status: newStatus });
            onStatusChange(c.id, newStatus);
        } catch (err) {
            console.error('Status update failed:', err);
        } finally {
            setUpdating(null);
        }
    };

    const currentStatus = (c.status || 'new').toLowerCase();

    return (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4" onClick={onClose}>
            <div className="bg-white w-[95%] sm:max-w-2xl max-h-[85vh] overflow-y-auto rounded-xl border shadow-2xl"
                style={{ borderColor: '#e5e7eb' }} onClick={e => e.stopPropagation()}>

                {/* Header */}
                <div className="p-5 text-white rounded-t-xl" style={{ background: color }}>
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <div className="text-[10px] uppercase opacity-80 font-semibold tracking-widest">
                                Grievance · #{c.id}
                            </div>
                            <div className="text-lg font-bold mt-1 leading-tight">
                                {c.category || 'General'}
                            </div>
                        </div>
                        <button onClick={onClose} className="text-white/80 hover:text-white text-xl">✕</button>
                    </div>
                </div>

                {/* Metadata Grid */}
                <div className="p-5 space-y-4">
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                        {[
                            ['Contact', c.user_phone || '—'],
                            ['Category', c.category || 'General'],
                            ['Status', currentStatus],
                            ['Location', meta.matched_value || c.location || '—'],
                            ['Assembly', meta.assembly_constituency || c.assembly || '—'],
                            ['Date', createdAt ? createdAt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'],
                            ['Time', createdAt ? createdAt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '—'],
                            ['Critical', c.is_critical ? 'Yes' : 'No'],
                            ['Last Updated', updatedAt ? updatedAt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'],
                        ].map(([label, value]) => (
                            <div key={label} className="border rounded-lg p-3" style={{ borderColor: '#e5e7eb' }}>
                                <div className="text-[10px] text-gray-400 uppercase font-semibold">{label}</div>
                                <div className="text-sm font-medium text-gray-700 mt-0.5">{value}</div>
                            </div>
                        ))}
                    </div>

                    {/* Full Message */}
                    <div>
                        <div className="text-[10px] text-gray-400 uppercase font-semibold mb-1.5">Full Message</div>
                        <div className="bg-gray-50 border rounded-lg p-4 text-sm text-gray-700 whitespace-pre-wrap leading-relaxed min-h-[80px]"
                            style={{ borderColor: '#e5e7eb' }}>
                            {c.raw_message || 'No content available.'}
                        </div>
                    </div>

                    {/* Summary */}
                    {meta.summary && (
                        <div>
                            <div className="text-[10px] text-gray-400 uppercase font-semibold mb-1.5">AI Summary</div>
                            <div className="bg-gray-50 border rounded-lg p-4 text-sm text-gray-700 whitespace-pre-wrap leading-relaxed"
                                style={{ borderColor: '#e5e7eb' }}>
                                {meta.summary}
                            </div>
                        </div>
                    )}

                    {/* AI Response */}
                    {c.response_to_citizen && (
                        <div>
                            <div className="text-[10px] text-gray-400 uppercase font-semibold mb-1.5">Response Sent</div>
                            <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                                {c.response_to_citizen}
                            </div>
                        </div>
                    )}

                    {/* Staff Notes */}
                    {c.notes_for_staff && (
                        <div>
                            <div className="text-[10px] text-gray-400 uppercase font-semibold mb-1.5">Staff Notes</div>
                            <div className="bg-yellow-50 border border-yellow-100 rounded-lg p-4 text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                                {c.notes_for_staff}
                            </div>
                        </div>
                    )}

                    {/* Status Actions */}
                    <div className="pt-2 border-t" style={{ borderColor: '#e5e7eb' }}>
                        <div className="text-[10px] text-gray-400 uppercase font-semibold mb-2">Update Status</div>
                        <div className="flex flex-wrap gap-2">
                            {STATUS_OPTIONS.filter(o => o.value !== currentStatus).map(opt => (
                                <button
                                    key={opt.value}
                                    onClick={() => handleStatusChange(opt.value)}
                                    disabled={updating === opt.value}
                                    className="px-3 py-2 text-xs font-bold rounded-lg border transition-all hover:shadow-md disabled:opacity-60"
                                    style={{
                                        background: opt.bg,
                                        color: opt.fg,
                                        borderColor: opt.fg + '30',
                                    }}>
                                    {updating === opt.value ? 'Updating...' : `Mark ${opt.label}`}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Close button */}
                    <div className="flex justify-end pt-2">
                        <button onClick={onClose}
                            className="px-5 py-2.5 text-sm font-medium border rounded-lg text-gray-500 hover:bg-gray-50"
                            style={{ borderColor: '#e5e7eb' }}>
                            Close
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}


// ═══════════════════════════════════════════
// INNER PAGE — reads URL params
// ═══════════════════════════════════════════
function BriefcaseInner() {
    const { user } = useAuth();
    const router = useRouter();
    const searchParams = useSearchParams();

    const color = user?.theme_color || '#006a4d';

    const [cases, setCases]               = useState([]);
    const [loading, setLoading]           = useState(true);
    const [statusFilter, setStatusFilter] = useState('All');
    const [categoryFilter, setCategoryFilter] = useState('');
    const [selected, setSelected]         = useState(null);

    // Sync URL params → state whenever the URL changes
    useEffect(() => {
        const status = searchParams.get('status') || 'All';
        const cat    = searchParams.get('category') || '';
        setStatusFilter(status);
        setCategoryFilter(cat);
    }, [searchParams]);

    // Fetch whenever filters change
    useEffect(() => {
        fetchCases();
    }, [statusFilter, categoryFilter]);

    async function fetchCases() {
        setLoading(true);
        try {
            const params = new URLSearchParams({ page: '1', limit: '100' });

            if (statusFilter === 'other') {
                params.set('categories', OTHER_CATEGORIES.join(','));
            } else if (statusFilter !== 'All') {
                params.set('status', statusFilter);
            }

            if (categoryFilter) {
                params.set('category', categoryFilter);
            }

            const data = await apiGet(`/api/cases?${params}`);
            setCases(data.cases || []);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    }

    function switchTab(key) {
        setStatusFilter(key);
        // Update URL without navigation so back-button works correctly
        const url = new URL(window.location.href);
        if (key === 'All') url.searchParams.delete('status');
        else url.searchParams.set('status', key);
        // keep category param if any
        window.history.replaceState({}, '', url.toString());
    }

    function clearCategoryFilter() {
        setCategoryFilter('');
        const url = new URL(window.location.href);
        url.searchParams.delete('category');
        window.history.replaceState({}, '', url.toString());
    }

    const handleStatusChange = (caseId, newStatus) => {
        setCases(prev => prev.map(c => c.id === caseId ? { ...c, status: newStatus } : c));
        setSelected(prev => prev && prev.id === caseId ? { ...prev, status: newStatus } : prev);
    };

    return (
        <div className="space-y-4">
            <h1 className="text-lg font-bold text-gray-900">Briefcase</h1>

            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden pt-2">

                {/* Status Tabs */}
                <div className="px-6 border-b border-gray-100 flex gap-6 overflow-x-auto whitespace-nowrap scrollbar-hide">
                    {TABS.map(t => (
                        <button key={t.key} onClick={() => switchTab(t.key)}
                            className="text-sm font-semibold pb-3 transition-colors"
                            style={statusFilter === t.key
                                ? { color, borderBottom: `2px solid ${color}` }
                                : { color: '#6b7280', borderBottom: '2px solid transparent' }}>
                            {t.label}
                        </button>
                    ))}
                </div>

                {/* Active Category Filter Chip */}
                {categoryFilter && (
                    <div className="px-6 py-2.5 border-b border-gray-100 flex items-center gap-2">
                        <span className="text-xs text-gray-500">Filtered by category:</span>
                        <span className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full text-white"
                            style={{ background: color }}>
                            {categoryFilter}
                            <button onClick={clearCategoryFilter}
                                className="opacity-75 hover:opacity-100 text-sm leading-none">
                                ×
                            </button>
                        </span>
                        <span className="text-xs text-gray-400 ml-1">
                            {loading ? '…' : `${cases.length} case${cases.length !== 1 ? 's' : ''}`}
                        </span>
                    </div>
                )}

                {/* Table */}
                <div className="overflow-x-auto">
                    {loading ? (
                        <div className="text-center py-10 text-gray-400 text-sm">Loading cases…</div>
                    ) : cases.length === 0 ? (
                        <div className="text-center py-10 text-gray-400 text-sm">
                            No cases found{categoryFilter ? ` in "${categoryFilter}"` : ''}{statusFilter !== 'All' ? ` with status "${statusFilter}"` : ''}.
                        </div>
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
                                    <tr key={c.id}
                                        style={getRowStyle(c.status, c.category, color)}
                                        className="cursor-pointer"
                                        onClick={() => setSelected(c)}>
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

            {/* Case Detail Modal */}
            {selected && (
                <CaseModal
                    caseItem={selected}
                    color={color}
                    onClose={() => setSelected(null)}
                    onStatusChange={handleStatusChange}
                />
            )}
        </div>
    );
}


// ═══════════════════════════════════════════
// BRIEFCASE PAGE — wraps inner in Suspense
// (required by Next.js for useSearchParams)
// ═══════════════════════════════════════════
export default function BriefcasePage() {
    return (
        <Suspense fallback={<div className="text-center py-10 text-gray-400 text-sm">Loading…</div>}>
            <BriefcaseInner />
        </Suspense>
    );
}
