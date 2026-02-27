'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPatch } from '@/lib/api';

const STATUS_OPTIONS = ['All', 'new', 'in_progress', 'resolved', 'escalated', 'closed', 'other'];
const STATUS_LABELS = { new: 'New', in_progress: 'In Progress', resolved: 'Resolved', escalated: 'Escalated', closed: 'Closed', other: 'Other' };
const OTHER_CATEGORIES = ['Request', 'Greetings', 'Spam', 'Spam (Offensive)'];

function getRowStyle(c) {
    const cat = (c.category || '').toLowerCase();
    if (cat === 'emergency' || c.is_critical) return { background: '#fef2f2', borderLeft: '3px solid #dc2626' };
    if (cat === 'complaint') return { background: '#f0fdf4', borderLeft: '3px solid #16a34a' };
    return {};
}

export default function SansadXPage() {
    const { user } = useAuth();
    const [cases, setCases] = useState([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [statusFilter, setStatusFilter] = useState('All');
    const [selectedCase, setSelectedCase] = useState(null);
    const [loading, setLoading] = useState(true);

    const color = user?.theme_color || '#006a4d';

    const fetchCases = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams({ page: String(page), limit: '30' });
            if (statusFilter === 'other') {
                params.set('categories', OTHER_CATEGORIES.join(','));
            } else if (statusFilter !== 'All') {
                params.set('status', statusFilter);
            }
            const data = await apiGet(`/api/cases?${params}`);
            setCases(data.cases || []);
            setTotal(data.total || 0);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchCases(); }, [page, statusFilter]);

    const updateStatus = async (caseId, newStatus) => {
        try {
            await apiPatch(`/api/cases/${caseId}/status`, { status: newStatus });
            fetchCases();
            if (selectedCase?.id === caseId) setSelectedCase(prev => ({ ...prev, status: newStatus }));
        } catch (err) {
            alert('Failed to update status');
        }
    };

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <h1 className="text-lg font-bold text-gray-800">Briefcase</h1>
                <div className="flex items-center gap-3">
                    <span className="inline-block w-3 h-3 rounded-sm" style={{ background: '#dcfce7', border: '1px solid #16a34a' }} />
                    <span className="text-[10px] text-gray-500">Complaint</span>
                    <span className="inline-block w-3 h-3 rounded-sm" style={{ background: '#fef2f2', border: '1px solid #dc2626' }} />
                    <span className="text-[10px] text-gray-500">Emergency</span>
                    <span className="text-xs text-gray-400 ml-2">{total} total</span>
                </div>
            </div>

            {/* Status tabs */}
            <div className="sansad-tabs">
                {STATUS_OPTIONS.map((s) => (
                    <button
                        key={s}
                        onClick={() => { setStatusFilter(s); setPage(1); }}
                        className={`sansad-tab ${statusFilter === s ? 'sansad-tab-active' : ''}`}
                        style={statusFilter === s ? { color } : {}}
                    >
                        {s === 'All' ? 'All Cases' : STATUS_LABELS[s] || s}
                    </button>
                ))}
            </div>

            {/* Table */}
            {loading ? (
                <div className="text-center py-10 text-gray-400 text-sm">Loading cases...</div>
            ) : cases.length === 0 ? (
                <div className="text-center py-10 text-gray-400 text-sm bg-white border" style={{ borderColor: '#ddd' }}>
                    No cases found for this filter.
                </div>
            ) : (
                <div className="sansad-card">
                    <table className="sansad-table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Contact</th>
                                <th>Category</th>
                                <th>Location</th>
                                <th>Assembly Constituency</th>
                                <th>Status</th>
                                <th>Message</th>
                                <th>Date</th>
                            </tr>
                        </thead>
                        <tbody>
                            {cases.map((c) => (
                                <tr key={c.id} onClick={() => setSelectedCase(c)} className="cursor-pointer" style={getRowStyle(c)}>
                                    <td className="font-mono text-gray-500">#{c.id}</td>
                                    <td className="font-medium">{c.user_phone || '–'}</td>
                                    <td>
                                        {c.category ? (
                                            <span className="sansad-badge" style={{ background: `${color}15`, color }}>{c.category}</span>
                                        ) : '–'}
                                    </td>
                                    <td>{c.location || '–'}</td>
                                    <td>{c.assembly || '–'}</td>
                                    <td>
                                        <span className={`sansad-badge status-${c.status}`}>
                                            {STATUS_LABELS[c.status] || c.status || '–'}
                                        </span>
                                    </td>
                                    <td className="max-w-[200px] truncate">{c.raw_message || '–'}</td>
                                    <td className="text-gray-400 text-xs">
                                        {c.created_at ? new Date(c.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : '–'}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Pagination */}
            {total > 30 && (
                <div className="flex items-center justify-center gap-4 mt-2">
                    <button
                        onClick={() => setPage(p => Math.max(1, p - 1))}
                        disabled={page === 1}
                        className="px-4 py-1.5 text-xs font-medium border bg-white text-gray-600 disabled:opacity-30"
                        style={{ borderColor: '#ddd' }}
                    >
                        Previous
                    </button>
                    <span className="text-xs text-gray-500">Page {page} of {Math.ceil(total / 30)}</span>
                    <button
                        onClick={() => setPage(p => p + 1)}
                        disabled={page >= Math.ceil(total / 30)}
                        className="px-4 py-1.5 text-xs font-medium border bg-white text-gray-600 disabled:opacity-30"
                        style={{ borderColor: '#ddd' }}
                    >
                        Next
                    </button>
                </div>
            )}

            {/* Modal */}
            {selectedCase && (
                <CaseModal c={selectedCase} color={color} onClose={() => setSelectedCase(null)} onStatus={updateStatus} />
            )}
        </div>
    );
}

function CaseModal({ c, color, onClose, onStatus }) {
    const meta = typeof c.case_metadata === 'object' ? c.case_metadata || {} :
        (() => { try { return JSON.parse(c.case_metadata); } catch { return {}; } })();

    return (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4" onClick={onClose}>
            <div className="bg-white w-full max-w-2xl max-h-[80vh] overflow-y-auto border shadow-lg animate-fade-in" onClick={e => e.stopPropagation()} style={{ borderColor: '#ddd' }}>
                {/* Header */}
                <div className="p-5 text-white" style={{ background: color }}>
                    <div className="flex items-center justify-between">
                        <div>
                            <div className="text-xs uppercase opacity-80 font-semibold">Case Detail</div>
                            <div className="text-xl font-bold mt-0.5">#{c.id} — {c.category || 'Uncategorised'}</div>
                        </div>
                        <button onClick={onClose} className="text-white/80 hover:text-white text-lg">✕</button>
                    </div>
                </div>

                <div className="p-5 space-y-4">
                    {/* Info grid */}
                    <div className="grid grid-cols-3 gap-3">
                        {[
                            ['Contact', c.user_phone || '–'],
                            ['Status', STATUS_LABELS[c.status] || c.status],
                            ['Location', meta.matched_value || c.location || '–'],
                            ['Assembly', meta.assembly_constituency || c.assembly || '–'],
                            ['Critical', c.is_critical ? 'Yes' : 'No'],
                            ['Created', c.created_at ? new Date(c.created_at).toLocaleString('en-IN') : '–'],
                        ].map(([label, value]) => (
                            <div key={label} className="border p-3" style={{ borderColor: '#eee' }}>
                                <div className="text-[10px] text-gray-400 uppercase font-semibold">{label}</div>
                                <div className="text-sm font-medium text-gray-700 mt-0.5">{value}</div>
                            </div>
                        ))}
                    </div>

                    {/* Message */}
                    <div>
                        <div className="text-[10px] text-gray-400 uppercase font-semibold mb-1.5">Full Message</div>
                        <div className="bg-gray-50 border p-4 text-sm text-gray-700 whitespace-pre-wrap" style={{ borderColor: '#eee' }}>
                            {c.raw_message || 'No message'}
                        </div>
                    </div>

                    {/* AI Response */}
                    {c.response_to_citizen && (
                        <div>
                            <div className="text-[10px] text-gray-400 uppercase font-semibold mb-1.5">AI Response</div>
                            <div className="border p-4 text-sm text-gray-700 whitespace-pre-wrap" style={{ background: `${color}08`, borderColor: `${color}30` }}>
                                {c.response_to_citizen}
                            </div>
                        </div>
                    )}

                    {/* Update Status */}
                    <div>
                        <div className="text-[10px] text-gray-400 uppercase font-semibold mb-1.5">Update Status</div>
                        <div className="flex gap-2 flex-wrap">
                            {Object.keys(STATUS_LABELS).map(s => (
                                <button
                                    key={s}
                                    onClick={() => onStatus(c.id, s)}
                                    disabled={c.status === s}
                                    className={`px-3 py-1.5 text-xs font-semibold border ${c.status === s ? 'text-white' : 'text-gray-500 bg-white'}`}
                                    style={c.status === s ? { background: color, borderColor: color } : { borderColor: '#ddd' }}
                                >
                                    {STATUS_LABELS[s]}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
