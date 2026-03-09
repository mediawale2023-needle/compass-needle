'use client';

import { useState, useEffect, useRef } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import { apiGet } from '@/lib/api';

const URGENCY_STYLES = {
    High: { background: '#fef2f2', color: '#dc2626' },
    Normal: { background: '#f0fdf4', color: '#16a34a' },
    Low: { background: '#f8fafc', color: '#94a3b8' },
};

const STATUS_STYLES = {
    'Pending-Intake': { background: '#eff6ff', color: '#2563eb' },
    'Drafted': { background: '#fef3c7', color: '#d97706' },
    'Resolved': { background: '#f0fdf4', color: '#16a34a' },
    'Sent': { background: '#f0fdf4', color: '#16a34a' },
};

function ScanBtn({ onUpload, direction, color }) {
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
            <button onClick={() => ref.current?.click()} disabled={uploading}
                className="flex items-center gap-2 px-4 py-2 text-sm font-bold text-white rounded-lg disabled:opacity-60 transition-opacity hover:opacity-90"
                style={{ background: color }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
                </svg>
                {uploading ? 'Scanning...' : direction === 'inbox' ? 'Scan Letter' : 'Upload Letter'}
            </button>
        </>
    );
}

function LetterModal({ item, color, onClose, onDraft }) {
    return (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4" onClick={onClose}>
            <div className="bg-white w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-xl border shadow-2xl"
                style={{ borderColor: '#e5e7eb' }} onClick={e => e.stopPropagation()}>
                <div className="p-5 text-white rounded-t-xl" style={{ background: color }}>
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
                        <button onClick={onClose} className="text-white/80 hover:text-white text-xl">✕</button>
                    </div>
                </div>
                <div className="p-5 space-y-4">
                    <div className="grid grid-cols-3 gap-3">
                        {[
                            ['From / To', item.citizen_name],
                            ['Phone', item.phone_number],
                            ['Village', item.village],
                            ['Urgency', item.urgency_level],
                            ['Status', item.status],
                            ['Date', item.created_at ? new Date(item.created_at).toLocaleDateString('en-CA') : '—'],
                        ].map(([label, value]) => (
                            <div key={label} className="border rounded-lg p-3" style={{ borderColor: '#e5e7eb' }}>
                                <div className="text-[10px] text-gray-400 uppercase font-semibold">{label}</div>
                                <div className="text-sm font-medium text-gray-700 mt-0.5">{value || '—'}</div>
                            </div>
                        ))}
                    </div>
                    <div>
                        <div className="text-[10px] text-gray-400 uppercase font-semibold mb-1.5">Full Letter Content</div>
                        <div className="bg-gray-50 border rounded-lg p-4 text-sm text-gray-700 whitespace-pre-wrap leading-relaxed min-h-[100px]"
                            style={{ borderColor: '#e5e7eb' }}>
                            {item.ocr_raw_text && !item.ocr_raw_text.startsWith('[Gemini Vision')
                                ? item.ocr_raw_text
                                : item.issue_summary || 'No content available.'}
                        </div>
                    </div>
                    {item.direction === 'inbox' && (
                        <div className="flex gap-3 pt-2 border-t" style={{ borderColor: '#e5e7eb' }}>
                            <button onClick={() => onDraft(item)}
                                className="flex-1 py-2.5 text-sm font-bold text-white rounded-lg hover:opacity-90" style={{ background: color }}>
                                ✍️ Draft Response
                            </button>
                            <button onClick={onClose}
                                className="px-5 py-2.5 text-sm font-medium border rounded-lg text-gray-500 hover:bg-gray-50" style={{ borderColor: '#e5e7eb' }}>
                                Close
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

export default function LetterboxPage() {
    const { user } = useAuth();
    const router = useRouter();
    const color = user?.theme_color || '#006a4d';

    const [tab, setTab] = useState('inbox');
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selected, setSelected] = useState(null);

    const fetchItems = async (dir) => {
        setLoading(true);
        try {
            const data = await apiGet(`/api/letterbox?direction=${dir}`);
            setItems(data.items || []);
        } catch (e) { console.error(e); }
        finally { setLoading(false); }
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

    const TABS = [
        { key: 'inbox', label: 'Inbox', icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" /><polyline points="22,6 12,13 2,6" /></svg> },
        { key: 'outbox', label: 'Outbox', icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg> },
    ];

    return (
        <div className="space-y-4">
            <h1 className="text-lg font-bold text-gray-900">Letterbox</h1>

            {/* Card with tabs + table — exactly as Figma */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                <div className="flex items-center justify-between px-6 pt-4 pb-0">
                    <div className="flex gap-6">
                        {TABS.map(t => (
                            <button key={t.key} onClick={() => setTab(t.key)}
                                className="flex items-center gap-2 pb-3 text-sm font-semibold transition-colors"
                                style={tab === t.key
                                    ? { color, borderBottom: `2px solid ${color}` }
                                    : { color: '#9ca3af', borderBottom: '2px solid transparent' }}>
                                {t.icon} {t.label}
                            </button>
                        ))}
                    </div>
                    <ScanBtn onUpload={handleUpload} direction={tab} color={color} />
                </div>

                {loading ? (
                    <div className="text-center py-10 text-gray-400 text-sm">Loading letters...</div>
                ) : items.length === 0 ? (
                    <div className="text-center py-14 text-gray-400 text-sm">
                        <div className="text-4xl mb-2">{tab === 'inbox' ? '📭' : '📬'}</div>
                        <p>No letters in {tab} yet.</p>
                    </div>
                ) : (
                    <table className="sansad-table mt-2">
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>{tab === 'inbox' ? 'SENDER' : 'RECIPIENT'}</th>
                                <th>VILLAGE</th>
                                <th>PHONE</th>
                                <th>SUMMARY</th>
                                <th>URGENCY</th>
                                <th>STATUS</th>
                            </tr>
                        </thead>
                        <tbody>
                            {items.map((item, idx) => {
                                const urg = URGENCY_STYLES[item.urgency_level] || URGENCY_STYLES.Normal;
                                const st = STATUS_STYLES[item.status] || { background: '#f3f4f6', color: '#6b7280' };
                                return (
                                    <tr key={item.id} onClick={() => setSelected(item)} className="cursor-pointer">
                                        <td className="text-gray-400">{idx + 1}</td>
                                        <td className="font-semibold text-gray-900">{item.citizen_name || '—'}</td>
                                        <td>{item.village || '—'}</td>
                                        <td className="font-mono text-xs">{item.phone_number || '—'}</td>
                                        <td className="max-w-[200px] truncate text-gray-600">{item.issue_summary || '—'}</td>
                                        <td><span className="sansad-badge" style={urg}>{item.urgency_level || 'Normal'}</span></td>
                                        <td><span className="sansad-badge" style={st}>{item.status || '—'}</span></td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                )}
            </div>

            {selected && (
                <LetterModal item={selected} color={color} onClose={() => setSelected(null)} onDraft={draftResponse} />
            )}
        </div>
    );
}
