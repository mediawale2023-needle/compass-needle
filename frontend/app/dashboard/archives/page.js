'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet } from '@/lib/api';

const TYPE_LABELS = {
    draft_letter: 'Letter',
    draft_question: 'Parliament Question',
    analysis: 'Document Analysis',
    copilot_chat: 'Co-Pilot Chat',
};

export default function ArchivesPage() {
    const { user } = useAuth();
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('all');
    const [expanded, setExpanded] = useState(null);
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

    const deleteItem = async (id) => {
        if (!confirm('Delete this item?')) return;
        try {
            const token = localStorage.getItem('needle_token') || '';
            await fetch(`/api/history/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` },
            });
            setItems(prev => prev.filter(i => i.id !== id));
        } catch { alert('Failed to delete'); }
    };

    const downloadItem = (item) => {
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
            <div className="flex items-center justify-between">
                <h1 className="text-lg font-bold text-gray-800">Archives</h1>
                <span className="text-xs text-gray-500">{items.length} saved items</span>
            </div>

            {/* Filter tabs */}
            <div className="sansad-tabs">
                {[
                    { key: 'all', label: 'All' },
                    { key: 'draft_letter', label: 'Letters' },
                    { key: 'draft_question', label: 'Questions' },
                    { key: 'analysis', label: 'Analyses' },
                ].map(t => (
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
                    <div className="sansad-card-body text-center py-12 text-sm text-gray-400">
                        No saved items yet. Use the Drafter or Co-Pilot to create and save documents.
                    </div>
                </div>
            ) : (
                <div className="space-y-3">
                    {items.map(item => (
                        <div key={item.id} className="sansad-card">
                            <div className="sansad-card-body">
                                <div className="flex items-start justify-between">
                                    <div className="flex-1 cursor-pointer" onClick={() => setExpanded(expanded === item.id ? null : item.id)}>
                                        <div className="flex items-center gap-2">
                                            <span className="sansad-badge" style={{ background: `${color}15`, color }}>
                                                {TYPE_LABELS[item.activity_type] || item.activity_type}
                                            </span>
                                            <span className="text-sm font-semibold text-gray-800">{item.title}</span>
                                        </div>
                                        <div className="text-xs text-gray-400 mt-1">
                                            {item.created_at ? new Date(item.created_at).toLocaleString('en-IN', {
                                                day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
                                            }) : '–'}
                                            {item.metadata?.recipient && <span className="ml-2">To: {item.metadata.recipient}</span>}
                                            {item.metadata?.ministry && <span className="ml-2">Ministry: {item.metadata.ministry}</span>}
                                        </div>
                                    </div>
                                    <div className="flex gap-2 ml-3">
                                        <button onClick={() => downloadItem(item)}
                                            className="px-3 py-1 text-[11px] font-semibold border text-gray-500" style={{ borderColor: '#ddd' }}>
                                            Download
                                        </button>
                                        <button onClick={() => deleteItem(item.id)}
                                            className="px-3 py-1 text-[11px] font-semibold border text-red-400" style={{ borderColor: '#ddd' }}>
                                            Delete
                                        </button>
                                    </div>
                                </div>

                                {expanded === item.id && (
                                    <div className="mt-3 pt-3 border-t" style={{ borderColor: '#eee' }}>
                                        <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed bg-gray-50 p-4 border" style={{ borderColor: '#eee' }}>
                                            {item.content}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
