'use client';

import { useState, useEffect, useRef } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import { apiGet } from '@/lib/api';

// ─── UPLOAD BUTTON ───────────────────────────────────────────────────────────
function UploadButton({ onUpload, color, direction }) {
    const [uploading, setUploading] = useState(false);
    const fileInputRef = useRef(null);

    const handleFile = async (file) => {
        if (!file) return;
        setUploading(true);
        try {
            await onUpload(file);
        } catch (e) {
            alert('Upload failed: ' + e.message);
        } finally {
            setUploading(false);
        }
    };

    return (
        <>
            <input
                type="file"
                ref={fileInputRef}
                onChange={e => handleFile(e.target.files[0])}
                className="hidden"
                accept=".pdf,image/*"
            />
            <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-60 transition-opacity hover:opacity-90"
                style={{ background: color }}
            >
                <span>{uploading ? '⏳' : direction === 'inbox' ? '📥' : '📤'}</span>
                <span>{uploading ? 'Scanning...' : direction === 'inbox' ? 'Scan / Upload Letter' : 'Upload Sent Letter'}</span>
            </button>
        </>
    );
}

// ─── MESSAGE ROW (center pane) ────────────────────────────────────────────────
function MessageRow({ item, isSelected, onClick, color }) {
    const isUnread = item.status === 'Pending-Intake';
    const urgencyColor = item.urgency_level === 'High' ? '#dc2626' : item.urgency_level === 'Low' ? '#9ca3af' : '#d97706';

    return (
        <div
            onClick={onClick}
            className={`px-4 py-3 border-b cursor-pointer transition-colors ${isSelected ? 'bg-blue-50' : isUnread ? 'bg-white hover:bg-gray-50' : 'bg-gray-50 hover:bg-gray-100'}`}
            style={{ borderColor: '#eee', borderLeft: isSelected ? `3px solid ${color}` : '3px solid transparent' }}
        >
            <div className="flex justify-between items-start gap-2">
                <span className={`text-sm truncate ${isUnread ? 'font-bold text-gray-900' : 'font-medium text-gray-600'}`}>
                    {item.citizen_name || 'Unknown Sender'}
                </span>
                <span className="text-[10px] text-gray-400 shrink-0">
                    {item.created_at ? new Date(item.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : ''}
                </span>
            </div>
            <div className="flex items-center justify-between mt-0.5">
                <p className="text-xs text-gray-500 truncate flex-1">
                    {item.issue_summary || 'No summary available'}
                </p>
                {item.urgency_level === 'High' && (
                    <span className="ml-2 px-1.5 py-0.5 text-[9px] font-bold rounded uppercase shrink-0" style={{ background: '#fee2e2', color: urgencyColor }}>
                        {item.urgency_level}
                    </span>
                )}
            </div>
            {item.village && item.village !== '[NOT FOUND]' && (
                <p className="text-[10px] text-gray-400 mt-0.5">📍 {item.village}</p>
            )}
        </div>
    );
}

// ─── DETAIL PANE ─────────────────────────────────────────────────────────────
function DetailPane({ item, color, onDraftResponse, onMarkResolved }) {
    if (!item) {
        return (
            <div className="flex-1 flex items-center justify-center text-gray-400 bg-gray-50">
                <div className="text-center">
                    <div className="text-5xl mb-3">✉️</div>
                    <p className="text-sm font-medium">Select a letter to read</p>
                </div>
            </div>
        );
    }

    const urgencyColor = item.urgency_level === 'High' ? '#dc2626' : item.urgency_level === 'Low' ? '#9ca3af' : '#d97706';
    const urgencyBg = item.urgency_level === 'High' ? '#fee2e2' : item.urgency_level === 'Low' ? '#f3f4f6' : '#fef3c7';

    return (
        <div className="flex-1 flex flex-col overflow-hidden bg-white">
            {/* Header */}
            <div className="px-6 py-4 border-b" style={{ borderColor: '#eee' }}>
                <div className="flex items-start justify-between gap-3">
                    <div>
                        <h2 className="text-base font-bold text-gray-900">
                            {item.issue_summary && item.issue_summary !== '[NOT FOUND]'
                                ? item.issue_summary
                                : 'No Subject'}
                        </h2>
                        <p className="text-xs text-gray-500 mt-1">
                            From: <strong>{item.citizen_name || 'Unknown'}</strong>
                            {item.village && item.village !== '[NOT FOUND]' ? ` · ${item.village}` : ''}
                            {item.phone_number && item.phone_number !== '[NOT FOUND]' ? ` · 📞 ${item.phone_number}` : ''}
                        </p>
                        <p className="text-[10px] text-gray-400 mt-0.5">
                            {item.created_at ? new Date(item.created_at).toLocaleString('en-IN', { dateStyle: 'full', timeStyle: 'short' }) : ''}
                        </p>
                    </div>
                    <span className="px-2 py-1 text-[10px] font-bold uppercase rounded shrink-0"
                        style={{ background: urgencyBg, color: urgencyColor }}>
                        {item.urgency_level || 'Normal'}
                    </span>
                </div>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
                {/* Extracted Data Block */}
                <div className="bg-gray-50 rounded-lg border p-4 text-sm space-y-2" style={{ borderColor: '#e5e7eb' }}>
                    <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">AI Extracted Details</p>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                        <div>
                            <p className="text-[10px] text-gray-400">Citizen Name</p>
                            <p className="font-medium text-gray-800">{item.citizen_name || '—'}</p>
                        </div>
                        <div>
                            <p className="text-[10px] text-gray-400">Phone</p>
                            <p className="font-medium text-gray-800">{item.phone_number || '—'}</p>
                        </div>
                        <div>
                            <p className="text-[10px] text-gray-400">Village / Location</p>
                            <p className="font-medium text-gray-800">{item.village || '—'}</p>
                        </div>
                        <div>
                            <p className="text-[10px] text-gray-400">Status</p>
                            <p className="font-medium text-gray-800">{item.status || '—'}</p>
                        </div>
                    </div>
                </div>

                {/* Raw OCR Text */}
                {item.ocr_raw_text && (
                    <div>
                        <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2">Original Document Text</p>
                        <div className="bg-white border rounded-lg p-4 text-sm text-gray-700 whitespace-pre-wrap font-mono leading-relaxed max-h-64 overflow-y-auto" style={{ borderColor: '#e5e7eb', fontSize: '12px' }}>
                            {item.ocr_raw_text}
                        </div>
                    </div>
                )}
            </div>

            {/* Action Bar */}
            {item.direction === 'inbox' && (
                <div className="px-6 py-4 border-t flex gap-3" style={{ borderColor: '#eee' }}>
                    <button
                        onClick={() => onDraftResponse(item)}
                        className="flex-1 py-2 text-sm font-bold text-white rounded-lg hover:opacity-90 transition-opacity"
                        style={{ background: color }}
                    >
                        ✍️ Draft Response
                    </button>
                    <button
                        onClick={() => onMarkResolved(item)}
                        className="px-4 py-2 text-sm font-semibold border rounded-lg text-gray-600 hover:bg-gray-50"
                        style={{ borderColor: '#ddd' }}
                    >
                        ✅ Mark Resolved
                    </button>
                </div>
            )}
        </div>
    );
}

// ─── MAIN PAGE ────────────────────────────────────────────────────────────────
export default function LetterboxPage() {
    const { user } = useAuth();
    const router = useRouter();
    const color = user?.theme_color || '#006a4d';

    const [folder, setFolder] = useState('inbox');   // 'inbox' | 'outbox'
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selected, setSelected] = useState(null);
    const [search, setSearch] = useState('');

    const loadItems = async (dir) => {
        setLoading(true);
        setSelected(null);
        try {
            const data = await apiGet(`/api/letterbox?direction=${dir}`);
            setItems(data.items || []);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { loadItems(folder); }, [folder]);

    const handleFileUpload = async (file) => {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('direction', folder);
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
        loadItems(folder);
    };

    const draftResponse = (item) => {
        const params = new URLSearchParams({
            subject: `Re: ${item.issue_summary}`,
            recipient: item.citizen_name !== '[NOT FOUND]' ? item.citizen_name : '',
            context: `Grievance received from ${item.citizen_name} (${item.village})\nPhone: ${item.phone_number}\n\nSummary: ${item.issue_summary}`,
        });
        router.push(`/dashboard/drafter?${params.toString()}`);
    };

    const markResolved = async (item) => {
        // TODO: Add PATCH /api/letterbox/:id to update status
        alert('Mark resolved feature coming soon!');
    };

    const filtered = items.filter(i =>
        !search || [i.citizen_name, i.village, i.issue_summary, i.phone_number]
            .some(f => f && f.toLowerCase().includes(search.toLowerCase()))
    );

    const inboxCount = folder === 'inbox' ? items.filter(i => i.status === 'Pending-Intake').length : null;

    return (
        <div className="flex h-[calc(100vh-64px)] overflow-hidden bg-white rounded-xl border shadow-sm" style={{ borderColor: '#e5e7eb' }}>

            {/* ── LEFT SIDEBAR ─────────────────────── */}
            <div className="w-48 shrink-0 flex flex-col border-r" style={{ borderColor: '#eee', background: '#fafafa' }}>
                <div className="p-4">
                    <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">Letterbox</p>
                    <UploadButton onUpload={handleFileUpload} color={color} direction={folder} />
                </div>

                <nav className="flex-1 px-2 space-y-0.5">
                    {[
                        { key: 'inbox', label: 'Inbox', icon: '📥' },
                        { key: 'outbox', label: 'Outbox', icon: '📤' },
                    ].map(f => (
                        <button
                            key={f.key}
                            onClick={() => setFolder(f.key)}
                            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-left transition-colors ${folder === f.key ? 'text-white' : 'text-gray-600 hover:bg-gray-200'}`}
                            style={folder === f.key ? { background: color } : {}}
                        >
                            <span>{f.icon}</span>
                            <span className="flex-1">{f.label}</span>
                            {f.key === 'inbox' && inboxCount > 0 && (
                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full"
                                    style={folder === 'inbox' ? { background: 'rgba(255,255,255,0.3)', color: 'white' } : { background: color, color: 'white' }}>
                                    {inboxCount}
                                </span>
                            )}
                        </button>
                    ))}
                </nav>

                <div className="p-3 text-center">
                    <p className="text-[9px] text-gray-400">{items.length} letters total</p>
                </div>
            </div>

            {/* ── CENTER: MESSAGE LIST ──────────────── */}
            <div className="w-72 shrink-0 flex flex-col border-r overflow-hidden" style={{ borderColor: '#eee' }}>
                {/* Search */}
                <div className="p-3 border-b" style={{ borderColor: '#eee' }}>
                    <input
                        type="text"
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                        placeholder="Search letters..."
                        className="w-full px-3 py-1.5 text-xs border rounded-lg bg-gray-50 focus:outline-none focus:ring-1"
                        style={{ borderColor: '#ddd' }}
                    />
                </div>

                {/* List */}
                <div className="flex-1 overflow-y-auto">
                    {loading ? (
                        <div className="p-6 text-center text-sm text-gray-400">Loading...</div>
                    ) : filtered.length === 0 ? (
                        <div className="p-6 text-center">
                            <div className="text-4xl mb-2">{folder === 'inbox' ? '📭' : '📬'}</div>
                            <p className="text-sm text-gray-400">{folder === 'inbox' ? 'No grievances received' : 'No letters sent'}</p>
                            <p className="text-xs text-gray-300 mt-1">Upload a letter to get started</p>
                        </div>
                    ) : (
                        filtered.map(item => (
                            <MessageRow
                                key={item.id}
                                item={item}
                                isSelected={selected?.id === item.id}
                                onClick={() => setSelected(item)}
                                color={color}
                            />
                        ))
                    )}
                </div>
            </div>

            {/* ── RIGHT: DETAIL PANE ───────────────── */}
            <DetailPane
                item={selected}
                color={color}
                onDraftResponse={draftResponse}
                onMarkResolved={markResolved}
            />
        </div>
    );
}
