'use client';

import { useState, useRef, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiPost } from '@/lib/api';

export default function CopilotPage() {
    const { user } = useAuth();

    // Document state
    const [docPages, setDocPages] = useState([]);
    const [docFilename, setDocFilename] = useState('');
    const [uploading, setUploading] = useState(false);
    const fileRef = useRef(null);

    // Chat state
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [chatLoading, setChatLoading] = useState(false);
    const endRef = useRef(null);

    const color = user?.theme_color || '#006a4d';
    const docContext = docPages.map(p => `[Page ${p.page}]\n${p.text}`).join('\n\n');

    useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

    const handleUpload = async (file) => {
        if (!file) return;
        setUploading(true);
        try {
            const token = localStorage.getItem('needle_token') || '';
            const formData = new FormData();
            formData.append('file', file);
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/api/copilot/upload`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData,
            });
            if (!res.ok) throw new Error('Upload failed');
            const data = await res.json();
            setDocPages(data.content || []);
            setDocFilename(data.filename || file.name);
            setMessages([{ role: 'assistant', content: `Document loaded: **${data.filename || file.name}** (${data.pages} pages). You can now ask me questions about it.` }]);
        } catch (err) {
            alert('Failed to upload: ' + err.message);
        } finally {
            setUploading(false);
        }
    };

    const askChat = async () => {
        if (!input.trim() || chatLoading) return;
        const q = input.trim();
        setInput('');
        const newMsgs = [...messages, { role: 'user', content: q }];
        setMessages(newMsgs);
        setChatLoading(true);
        try {
            const data = await apiPost('/api/copilot/chat', { document_context: docContext, message: q, language: 'English' });
            setMessages([...newMsgs, { role: 'assistant', content: data.reply }]);
        } catch (err) {
            setMessages([...newMsgs, { role: 'assistant', content: 'Error: ' + err.message }]);
        } finally {
            setChatLoading(false);
        }
    };

    return (
        <div className="space-y-4 h-full flex flex-col">
            <h1 className="text-lg font-bold text-gray-900">Research Desk</h1>

            {!docFilename ? (
                // Initial Upload State — Matches Figma "AI Co-Pilot" card exactly
                <div className="flex-1 flex items-center justify-center p-6">
                    <div className="bg-white rounded-xl shadow-sm w-full max-w-2xl text-center overflow-hidden" style={{ borderTop: `4px solid ${color}` }}>
                        <div className="px-6 py-4 border-b border-gray-100 text-left">
                            <h2 className="text-lg font-bold text-gray-900">AI Co-Pilot</h2>
                        </div>
                        <div className="p-16 flex flex-col items-center">
                            <svg className="text-gray-400 mb-6" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                                <polyline points="14 2 14 8 20 8" />
                                <line x1="9" y1="15" x2="15" y2="15" />
                                <line x1="9" y1="11" x2="15" y2="11" />
                            </svg>
                            <h3 className="text-xl font-bold text-gray-900 mb-2">Upload a PDF Document</h3>
                            <p className="text-gray-500 mb-8">Bills, Acts, Ordinances, Policy Documents</p>

                            <input type="file" ref={fileRef} className="hidden" accept=".pdf" onChange={e => handleUpload(e.target.files[0])} />

                            <button onClick={() => fileRef.current?.click()} disabled={uploading}
                                className="flex items-center gap-2 px-6 py-3 font-bold rounded-lg transition-colors"
                                style={{ color, border: `1.5px solid ${color}`, background: 'transparent' }}>
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>
                                {uploading ? 'Scanning...' : 'Choose PDF File'}
                            </button>
                        </div>
                    </div>
                </div>
            ) : (
                // Chat Interface State (matches Figma styling approach for cards)
                <div className="bg-white rounded-xl shadow-sm flex-1 flex flex-col overflow-hidden border border-gray-100" style={{ minHeight: 600 }}>
                    <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between" style={{ background: '#fafafa' }}>
                        <div>
                            <div className="font-bold text-gray-800 text-sm">AI Co-Pilot</div>
                            <div className="text-xs text-gray-500">Analyzing: {docFilename}</div>
                        </div>
                        <button onClick={() => { setDocFilename(''); setDocPages([]); setMessages([]); }}
                            className="text-xs text-red-500 hover:underline">
                            Clear Session
                        </button>
                    </div>

                    <div className="flex-1 p-5 overflow-y-auto space-y-4 bg-gray-50">
                        {messages.map((m, i) => (
                            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <div className={`max-w-[80%] px-4 py-3 rounded-xl text-sm leading-relaxed ${m.role === 'user' ? 'text-white' : 'bg-white border shadow-sm text-gray-800'}`}
                                    style={m.role === 'user' ? { background: color } : { borderColor: '#eee' }}>
                                    {m.content}
                                </div>
                            </div>
                        ))}
                        {chatLoading && (
                            <div className="flex justify-start">
                                <div className="bg-white border px-4 py-3 rounded-xl text-sm text-gray-400" style={{ borderColor: '#eee' }}>
                                    Thinking...
                                </div>
                            </div>
                        )}
                        <div ref={endRef} />
                    </div>

                    <div className="p-4 bg-white border-t border-gray-100 flex gap-3">
                        <input type="text" value={input} onChange={e => setInput(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && askChat()}
                            placeholder="Ask any question about the document..."
                            className="flex-1 px-4 py-3 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-gray-400" />
                        <button onClick={askChat} disabled={chatLoading || !input.trim()}
                            className="px-6 py-3 text-white font-bold rounded-lg disabled:opacity-50"
                            style={{ background: color }}>
                            Ask
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
