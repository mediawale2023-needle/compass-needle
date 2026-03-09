'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet } from '@/lib/api';

const TYPE_LABELS = {
    draft_letter: 'Letter',
    draft_question: 'Question',
    analysis: 'Research',
    copilot_chat: 'Research',
};
const TYPE_COLORS = {
    Letter: { background: '#eff6ff', color: '#2563eb' },
    Question: { background: '#fef3c7', color: '#d97706' },
    Research: { background: '#f0fdf4', color: '#16a34a' },
};
const TABS = [
    { key: 'all', label: 'All' },
    { key: 'draft_letter', label: 'Letters' },
    { key: 'draft_question', label: 'Questions' },
    { key: 'analysis', label: 'Research' },
];

export default function ArchivesPage() {
    const { user } = useAuth();
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('all');
    const [selected, setSelected] = useState(null);
    const color = user?.theme_color || '#006a4d';

    const fetchItems = async () => {
        setLoading(true);
        try {
            const params = filter !== 'all' ? `?activity_type=${filter}` : '';
            const data = await apiGet(`/api/history${params}`);
            setItems(data.items || []);
        } catch (err) { console.error(err); }
        finally { setLoading(false); }
    };

    useEffect(() => { fetchItems(); }, [filter]);

    const downloadItem = (item, e) => {
        e.stopPropagation();
        const blob = new Blob([item.content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${item.title?.replace(/[^a-zA-Z0-9]/g, '_').slice(0, 40) || 'document'}.txt`;
        a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <div className="space-y-5">
            <h1 className="text-lg font-bold text-gray-800">Archives</h1>

            {/* Tabs */}
            <div className="sansad-tabs">
                {TABS.map(t => (
                    <button key={t.key}
                        onClick={() => setFilter(t.key)}
                        className={`sansad-tab ${filter === t.key ? 'sansad-tab-active' : ''}`}
                        style={filter === t.key ? { color } : {}}
                    >
                        {t.label}
                    </button>
                ))}
            </div>

            {loading ? (
                <div className="text-center py-10 text-gray-400 text-sm">Loading archives...</div>
            ) : items.length === 0 ? (
                <div className="sansad-card">
                    <div className="sansad-card-body text-center py-16 text-sm text-gray-400">
                        No saved items yet. Use the Drafter or Research Desk to save documents.
                    </div>
                </div>
            ) : (
                <div className="sansad-card">
                    <table className="sansad-table">
                        <thead>
                            <tr>
                                <th style={{ width: 40 }}>#</th>
                                <th>Title</th>
                                <th style={{ width: 120 }}>Type</th>
                                <th style={{ width: 110 }}>Date</th>
                                <th style={{ width: 80 }}>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {items.map((item, idx) => {
                                const typeLabel = TYPE_LABELS[item.activity_type] || 'Research';
                                const style = TYPE_COLORS[typeLabel] || TYPE_COLORS.Research;
                                return (
                                    <tr key={item.id} onClick={() => setSelected(item)} className="cursor-pointer">
                                        <td className="text-gray-400">{idx + 1}</td>
                                        <td className="font-medium text-gray-800">{item.title || '—'}</td>
                                        <td>
                                            <span className="sansad-badge" style={style}>{typeLabel}</span>
                                        </td>
                                        <td className="text-gray-500 text-xs">
                                            {item.created_at ? new Date(item.created_at).toLocaleDateString('en-CA') : '—'}
                                        </td>
                                        <td>
                                            <button onClick={(e) => downloadItem(item, e)}
                                                className="figma-view-link" style={{ color }}>
                                                👁 View
                                            </button>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Modal */}
            {selected && (
                <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4" onClick={() => setSelected(null)}>
                    <div className="bg-white w-full max-w-2xl max-h-[80vh] overflow-y-auto border shadow-xl rounded-lg"
                        style={{ borderColor: '#ddd' }} onClick={e => e.stopPropagation()}>
                        <div className="p-5 text-white rounded-t-lg" style={{ background: color }}>
                            <div className="flex items-center justify-between">
                                <div>
                                    <div className="text-[10px] uppercase opacity-75 font-semibold tracking-wider">{TYPE_LABELS[selected.activity_type] || selected.activity_type}</div>
                                    <div className="text-base font-bold mt-0.5">{selected.title}</div>
                                </div>
                                <button onClick={() => setSelected(null)} className="text-white/80 hover:text-white text-xl">✕</button>
                            </div>
                        </div>
                        <div className="p-5 space-y-4">
                            <div className="text-xs text-gray-400">
                                {selected.created_at ? new Date(selected.created_at).toLocaleString('en-IN', { dateStyle: 'full', timeStyle: 'short' }) : '—'}
                            </div>
                            <div className="bg-gray-50 border p-4 text-sm text-gray-700 whitespace-pre-wrap leading-relaxed rounded" style={{ borderColor: '#eee' }}>
                                {selected.content || 'No content.'}
                            </div>
                            <div className="flex gap-2 justify-end pt-2 border-t" style={{ borderColor: '#eee' }}>
                                <button onClick={(e) => downloadItem(selected, e)}
                                    className="figma-btn-outline" style={{ color }}>
                                    ⬇ Download .txt
                                </button>
                                <button onClick={() => setSelected(null)}
                                    className="px-4 py-1.5 text-sm border rounded text-gray-500" style={{ borderColor: '#ddd' }}>
                                    Close
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
