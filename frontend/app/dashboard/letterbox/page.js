'use client';

import { useState, useEffect, useRef } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import { apiGet } from '@/lib/api';

const TABS = ['inbox', 'outbox'];
const TAB_LABELS = { inbox: '📥 Inbox', outbox: '📤 Outbox' };
const URGENCY_STYLES = {
    High: { background: '#fef2f2', color: '#dc2626' },
    Normal: { background: '#f0fdf4', color: '#16a34a' },
    Low: { background: '#f8fafc', color: '#94a3b8' },
};

// ── UPLOAD BUTTON ─────────────────────────────────────────────────────────────
function UploadButton({ onUpload, direction, color }) {
    const [uploading, setUploading] = useState(false);
    const ref = useRef(null);
    const handle = async (file) => {
        if (!file) return;
        setUploading(true);
        try { await onUpload(file); }
        catch (e) { alert('Upload failed: ' + e.message); }
        finally { setUploading(false); }
    };
    return (
        <>
            <input type="file" ref={ref} className="hidden" accept=".pdf,image/*"
                onChange={e => handle(e.target.files[0])} />
            <button
                onClick={() => ref.current?.click()}
                disabled={uploading}
                className="px-4 py-1.5 text-xs font-bold text-white rounded disabled:opacity-60 hover:opacity-90 transition-opacity"
                style={{ background: color }}
            >
                {uploading ? 'Scanning...' : direction === 'inbox' ? '+ Scan Letter' : '+ Upload Letter'}
            </button>
        </>
    );
}

// ── LETTER MODAL ──────────────────────────────────────────────────────────────
function LetterModal({ item, color, onClose, onDraft }) {
    const urgency = URGENCY_STYLES[item.urgency_level] || URGENCY_STYLES.Normal;
    return (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4" onClick={onClose}>
            <div className="bg-white w-full max-w-2xl max-h-[85vh] overflow-y-auto border shadow-xl"
                style={{ borderColor: '#ddd' }}
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="p-5 text-white" style={{ background: color }}>
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <div className="text-[10px] uppercase opacity-80 font-semibold tracking-widest">
                                {item.direction === 'inbox' ? 'Incoming Grievance' : 'Outgoing Letter'} · #{item.id}
                            </div>
                            <div className="text-lg font-bold mt-1 leading-tight">
                                {item.issue_summary && item.issue_summary !== '[NOT FOUND]'
                                    ? item.issue_summary : 'No Subject'}
                            </div>
                        </div>
                        <button onClick={onClose} className="text-white/80 hover:text-white text-xl leading-none">✕</button>
                    </div>
                </div>

                <div className="p-5 space-y-4">
                    {/* Info grid */}
                    <div className="grid grid-cols-3 gap-3">
                        {[
                            ['From / To', item.citizen_name],
                            ['Phone', item.phone_number],
                            ['Village', item.village],
                            ['Urgency', item.urgency_level],
                            ['Status', item.status],
                            ['Date', item.created_at ? new Date(item.created_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : '—'],
                        ].map(([label, value]) => (
                            <div key={label} className="border p-3" style={{ borderColor: '#eee' }}>
                                <div className="text-[10px] text-gray-400 uppercase font-semibold">{label}</div>
                                <div className="text-sm font-medium text-gray-700 mt-0.5">{value || '—'}</div>
                            </div>
                        ))}
                    </div>

                    {/* Full letter content */}
                    <div>
                        <div className="text-[10px] text-gray-400 uppercase font-semibold mb-1.5">Full Letter Content</div>
                        <div className="bg-gray-50 border p-4 text-sm text-gray-700 whitespace-pre-wrap leading-relaxed min-h-[120px]"
                            style={{ borderColor: '#eee', fontFamily: 'mono' }}>
                            {item.ocr_raw_text && !item.ocr_raw_text.startsWith('[Gemini Vision')
                                ? item.ocr_raw_text
                                : item.issue_summary || 'No content available.'}
                        </div>
                    </div>

                    {/* Actions */}
                    {item.direction === 'inbox' && (
                        <div className="flex gap-3 pt-2 border-t" style={{ borderColor: '#eee' }}>
                            <button
                                onClick={() => onDraft(item)}
                                className="flex-1 py-2 text-sm font-bold text-white hover:opacity-90 transition-opacity"
                                style={{ background: color }}
                            >
                                ✍️ Draft Response
                            </button>
                            <button
                                onClick={onClose}
                                className="px-5 py-2 text-sm font-semibold border text-gray-500 hover:bg-gray-50"
                                style={{ borderColor: '#ddd' }}
                            >
                                Close
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

// ── MAIN PAGE ─────────────────────────────────────────────────────────────────
export default function LetterboxPage() {
    const { user } = useAuth();
    const router = useRouter();
    const color = user?.theme_color || '#006a4d';

    const [tab, setTab] = useState('inbox');
    const [items, setItems] = useState([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [selected, setSelected] = useState(null);

    const fetchItems = async (dir) => {
        setLoading(true);
        try {
            const data = await apiGet(`/api/letterbox?direction=${dir}`);
            setItems(data.items || []);
            setTotal(data.total || 0);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchItems(tab); }, [tab]);

    const handleUpload = async (file) => {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('direction', tab);
        const token = localStorage.getItem('needle_token');
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/api/letterbox/upload`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
            throw new Error(err.detail || 'Upload failed');
        }
        fetchItems(tab);
    };

    const draftResponse = (item) => {
        const params = new URLSearchParams({
            subject: `Re: ${item.issue_summary}`,
            recipient: item.citizen_name !== '[NOT FOUND]' ? item.citizen_name : '',
            context: `From: ${item.citizen_name} (${item.village})\nPhone: ${item.phone_number}\n\nGrievance:\n${item.issue_summary}`,
        });
        router.push(`/dashboard/drafter?${params.toString()}`);
    };

    const pendingCount = items.filter(i => i.status === 'Pending-Intake').length;

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-lg font-bold text-gray-800">Letterbox</h1>
                    <p className="text-xs text-gray-400">{total} letters · {pendingCount > 0 ? `${pendingCount} pending` : 'all clear'}</p>
                </div>
                <UploadButton onUpload={handleUpload} direction={tab} color={color} />
            </div>

            {/* Tabs */}
            <div className="sansad-tabs">
                {TABS.map(t => (
                    <button
                        key={t}
                        onClick={() => { setTab(t); }}
                        className={`sansad-tab ${tab === t ? 'sansad-tab-active' : ''}`}
                        style={tab === t ? { color } : {}}
                    >
                        {TAB_LABELS[t]}
                    </button>
                ))}
            </div>

            {/* Table */}
            {loading ? (
                <div className="text-center py-10 text-gray-400 text-sm">Loading letters...</div>
            ) : items.length === 0 ? (
                <div className="text-center py-12 text-gray-400 text-sm bg-white border" style={{ borderColor: '#ddd' }}>
                    <div className="text-4xl mb-2">{tab === 'inbox' ? '📭' : '📬'}</div>
                    <p>No letters in {tab} yet.</p>
                    <p className="text-xs text-gray-300 mt-1">Upload a PDF or image to get started.</p>
                </div>
            ) : (
                <div className="sansad-card">
                    <table className="sansad-table">
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>{tab === 'inbox' ? 'Sender' : 'Recipient'}</th>
                                <th>Village</th>
                                <th>Phone</th>
                                <th>Summary</th>
                                <th>Urgency</th>
                                <th>Status</th>
                                <th>Date</th>
                            </tr>
                        </thead>
                        <tbody>
                            {items.map(item => {
                                const urg = URGENCY_STYLES[item.urgency_level] || URGENCY_STYLES.Normal;
                                const isPending = item.status === 'Pending-Intake';
                                return (
                                    <tr
                                        key={item.id}
                                        onClick={() => setSelected(item)}
                                        className="cursor-pointer"
                                        style={isPending ? { borderLeft: `3px solid ${color}` } : {}}
                                    >
                                        <td className="font-mono text-gray-400">#{item.id}</td>
                                        <td className={`${isPending ? 'font-bold text-gray-900' : 'font-medium text-gray-600'}`}>
                                            {item.citizen_name || '—'}
                                        </td>
                                        <td>{item.village || '—'}</td>
                                        <td className="font-mono text-xs">{item.phone_number || '—'}</td>
                                        <td className="max-w-[220px] truncate text-gray-600">{item.issue_summary || '—'}</td>
                                        <td>
                                            <span className="sansad-badge" style={{ background: urg.background, color: urg.color }}>
                                                {item.urgency_level || 'Normal'}
                                            </span>
                                        </td>
                                        <td>
                                            <span className="sansad-badge" style={{ background: `${color}15`, color }}>
                                                {item.status || '—'}
                                            </span>
                                        </td>
                                        <td className="text-gray-400 text-xs">
                                            {item.created_at ? new Date(item.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : '—'}
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
                <LetterModal
                    item={selected}
                    color={color}
                    onClose={() => setSelected(null)}
                    onDraft={draftResponse}
                />
            )}
        </div>
    );
}
