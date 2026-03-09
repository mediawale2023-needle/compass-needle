'use client';

import { useState, useEffect, useRef } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import { apiGet } from '@/lib/api';

function Dropzone({ onUpload, color, label }) {
    const [dragging, setDragging] = useState(false);
    const [uploading, setUploading] = useState(false);
    const fileInputRef = useRef(null);

    const handleUpload = async (file) => {
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
        <div
            className={`border-2 border-dashed p-8 text-center rounded-lg transition-colors cursor-pointer 
                ${dragging ? 'bg-gray-50' : 'bg-white hover:bg-gray-50'}`}
            style={{ borderColor: dragging ? color : '#ccc' }}
            onDragOver={e => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={e => {
                e.preventDefault();
                setDragging(false);
                const file = e.dataTransfer.files[0];
                handleUpload(file);
            }}
            onClick={() => fileInputRef.current?.click()}
        >
            <input
                type="file"
                ref={fileInputRef}
                onChange={e => handleUpload(e.target.files[0])}
                className="hidden"
                accept=".pdf,image/*"
            />
            <div className="text-3xl mb-3 text-gray-400">📄</div>
            {uploading ? (
                <p className="text-sm font-semibold text-gray-600">Extracting details with AI...</p>
            ) : (
                <>
                    <p className="text-sm font-semibold text-gray-700">{label}</p>
                    <p className="text-xs text-gray-500 mt-1">Drag & drop or click to upload</p>
                </>
            )}
        </div>
    );
}

export default function LetterboxPage() {
    const { user } = useAuth();
    const router = useRouter();
    const [tab, setTab] = useState('inbox');
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);

    const color = user?.theme_color || '#006a4d';

    const loadItems = async (direction) => {
        setLoading(true);
        try {
            const data = await apiGet(`/api/letterbox?direction=${direction}`);
            setItems(data.items || []);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadItems(tab);
    }, [tab]);

    const handleFileUpload = async (file) => {
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
            let errorText = "Upload failed";
            try {
                const errJson = await res.json();
                errorText = errJson.detail || errorText;
            } catch (e) {
                // If not JSON, try text
                const text = await res.text();
                errorText = text || errorText;
            }
            throw new Error(errorText);
        }

        // Reload list
        loadItems(tab);
    };

    const draftResponse = (item) => {
        const params = new URLSearchParams({
            subject: `Regarding: ${item.issue_summary}`,
            recipient: item.citizen_name !== '[NOT FOUND]' ? item.citizen_name : '',
            context: `Original Grievance:\nCitizen: ${item.citizen_name}\nVillage: ${item.village}\nPhone: ${item.phone_number}\n\nSummary: ${item.issue_summary}`
        });
        router.push(`/dashboard/drafter?${params.toString()}`);
    };

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-gray-800">Letterbox</h1>
                <p className="text-sm text-gray-500">The physical-to-digital loop.</p>
            </div>

            {/* Tabs */}
            <div className="flex border-b" style={{ borderColor: '#ddd' }}>
                {['inbox', 'outbox'].map((t) => (
                    <button
                        key={t}
                        onClick={() => setTab(t)}
                        className="px-6 py-2.5 text-sm font-semibold transition-colors uppercase"
                        style={{
                            color: tab === t ? color : '#777',
                            borderBottom: tab === t ? `3px solid ${color}` : '3px solid transparent',
                        }}
                    >
                        {t === 'inbox' ? '📥 Inbox (Grievances)' : '📤 Outbox (Sent)'}
                    </button>
                ))}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

                {/* Left: Dropzone */}
                <div className="md:col-span-1">
                    <div className="bg-white p-5 rounded-lg shadow-sm border border-gray-100">
                        <Dropzone
                            onUpload={handleFileUpload}
                            color={color}
                            label={tab === 'inbox' ? 'Scan Letter / Grievance' : 'Upload External Letter'}
                        />
                        <div className="mt-4 text-xs text-gray-500 space-y-2">
                            <p><strong>Step 1:</strong> Place document on scanner.</p>
                            <p><strong>Step 2:</strong> Upload PDF/Image here.</p>
                            <p><strong>Step 3:</strong> AI will instantly read and extract the details.</p>
                        </div>
                    </div>
                </div>

                {/* Right: Items List */}
                <div className="md:col-span-2 space-y-4">
                    {loading ? (
                        <div className="text-sm text-gray-500 text-center py-10 bg-white rounded-lg border">Loading...</div>
                    ) : items.length === 0 ? (
                        <div className="text-sm text-gray-500 text-center py-10 bg-white rounded-lg border">
                            No items in the {tab}.
                        </div>
                    ) : (
                        items.map((item) => (
                            <div key={item.id} className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm flex flex-col gap-3">
                                <div className="flex justify-between items-start">
                                    <div>
                                        <div className="text-xs font-bold text-gray-400 uppercase tracking-wide">
                                            {item.created_at ? new Date(item.created_at).toLocaleDateString() : ''}
                                        </div>
                                        <h3 className="text-lg font-bold text-gray-800 mt-1">
                                            {item.citizen_name}
                                        </h3>
                                        <p className="text-xs text-gray-500 mt-0.5">
                                            {item.village} • {item.phone_number}
                                        </p>
                                    </div>
                                    <span className="px-2 py-1 text-[10px] font-bold uppercase rounded"
                                        style={{
                                            background: item.urgency_level === 'High' ? '#fee2e2' : '#f3f4f6',
                                            color: item.urgency_level === 'High' ? '#dc2626' : '#4b5563'
                                        }}>
                                        {item.urgency_level}
                                    </span>
                                </div>

                                <div className="bg-gray-50 p-3 rounded text-sm text-gray-700 italic border-l-4" style={{ borderColor: color }}>
                                    "{item.issue_summary}"
                                </div>

                                {tab === 'inbox' && (
                                    <div className="flex justify-end pt-2 border-t border-gray-100">
                                        <button
                                            onClick={() => draftResponse(item)}
                                            className="px-4 py-1.5 text-xs font-bold text-white rounded shadow-sm hover:opacity-90"
                                            style={{ background: color }}
                                        >
                                            Draft Response →
                                        </button>
                                    </div>
                                )}
                            </div>
                        ))
                    )}
                </div>

            </div>
        </div>
    );
}
