'use client';

import { useState, useRef, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiPost } from '@/lib/api';

export default function CopilotPage() {
    const { user } = useAuth();
    const [tab, setTab] = useState('analyse');

    // Document state
    const [docPages, setDocPages] = useState([]);
    const [docFilename, setDocFilename] = useState('');
    const [uploading, setUploading] = useState(false);

    // Analyse state
    const [language, setLanguage] = useState('English');
    const [depth, setDepth] = useState('Quick Scan');
    const [analysis, setAnalysis] = useState('');
    const [analysing, setAnalysing] = useState(false);

    // Chat state
    const [chatLang, setChatLang] = useState('English');
    const [messages, setMessages] = useState([
        { role: 'assistant', content: 'Upload a document and ask me anything about it — or ask general parliamentary queries.' }
    ]);
    const [input, setInput] = useState('');
    const [chatLoading, setChatLoading] = useState(false);
    const endRef = useRef(null);

    const color = user?.theme_color || '#006a4d';
    const docContext = docPages.map(p => `[Page ${p.page}]\n${p.text}`).join('\n\n');

    useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

    // Upload PDF
    const handleUpload = async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        setUploading(true);
        try {
            const token = localStorage.getItem('needle_token') || '';
            const formData = new FormData();
            formData.append('file', file);
            const res = await fetch('/api/copilot/upload', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData,
            });
            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || `Upload failed (${res.status})`);
            }
            const data = await res.json();
            setDocPages(data.content || []);
            setDocFilename(data.filename || file.name);
            setAnalysis('');
            setMessages(prev => [...prev, { role: 'assistant', content: `Document loaded: ${data.filename} (${data.pages} pages). You can now Analyse it or Ask questions about it.` }]);
        } catch (err) {
            alert('Failed to upload: ' + err.message);
        } finally {
            setUploading(false);
        }
    };

    // Run Analysis
    const runAnalysis = async () => {
        if (!docContext) return;
        setAnalysing(true);
        try {
            const data = await apiPost('/api/copilot/analyse', {
                document_text: docContext,
                filename: docFilename,
                language,
                depth,
            });
            setAnalysis(data.analysis || 'No analysis returned.');
        } catch (err) {
            setAnalysis('Error: ' + err.message);
        } finally {
            setAnalysing(false);
        }
    };

    // Chat
    const sendChat = async () => {
        if (!input.trim() || chatLoading) return;
        const msg = input;
        setMessages(prev => [...prev, { role: 'user', content: msg }]);
        setInput('');
        setChatLoading(true);
        try {
            const langNote = chatLang === 'Hindi' ? 'Respond in Hindi (Devanagari script).' : chatLang === 'Bilingual' ? 'Respond in both Hindi and English.' : '';
            const data = await apiPost('/api/copilot/chat', {
                message: langNote ? `${langNote}\n${msg}` : msg,
                history: messages,
                document_context: docContext,
            });
            setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
        } catch {
            setMessages(prev => [...prev, { role: 'assistant', content: 'An error occurred.' }]);
        } finally {
            setChatLoading(false);
        }
    };

    // Change document
    const clearDocument = () => {
        setDocPages([]);
        setDocFilename('');
        setAnalysis('');
        setMessages([{ role: 'assistant', content: 'Document cleared. Upload a new document to begin.' }]);
    };

    // Download helper
    const downloadText = (content, filename) => {
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    };

    // Export full chat history
    const exportChat = () => {
        const text = messages.map(m => `[${m.role === 'user' ? 'You' : 'Co-Pilot'}]\n${m.content}`).join('\n\n---\n\n');
        downloadText(text, `CoPilot_Chat_${docFilename || 'session'}_${new Date().toISOString().slice(0, 10)}.txt`);
    };

    // Chat panel (reused in both doc and no-doc modes)
    const renderChat = (headerText, placeholder) => (
        <div className="sansad-card" style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 340px)' }}>
            <div className="sansad-card-header flex items-center justify-between" style={{ background: color }}>
                <span>{headerText}</span>
                <div className="flex items-center gap-2">
                    <select value={chatLang} onChange={e => setChatLang(e.target.value)}
                        className="px-2 py-1 text-xs border-none rounded text-gray-800 bg-white/90">
                        <option>English</option>
                        <option>Hindi</option>
                        <option>Bilingual</option>
                    </select>
                </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-5 space-y-3" style={{ background: '#fafafa' }}>
                {messages.map((m, i) => (
                    <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className="max-w-[70%] px-4 py-3 text-sm whitespace-pre-wrap"
                            style={m.role === 'user'
                                ? { background: color, color: 'white', borderRadius: '4px 4px 0 4px' }
                                : { background: 'white', border: '1px solid #ddd', borderRadius: '4px 4px 4px 0' }
                            }>
                            {m.content}
                        </div>
                    </div>
                ))}
                {chatLoading && (
                    <div className="flex justify-start">
                        <div className="bg-white border px-4 py-3 text-sm text-gray-400" style={{ borderColor: '#ddd', borderRadius: '4px 4px 4px 0' }}>
                            Thinking...
                        </div>
                    </div>
                )}
                <div ref={endRef} />
            </div>

            {/* Save / Download bar */}
            {messages.length > 1 && (
                <div className="border-t px-4 py-2 flex gap-2 justify-end" style={{ borderColor: '#eee', background: '#fafafa' }}>
                    <button onClick={exportChat}
                        className="px-3 py-1 text-[11px] font-semibold border text-gray-500" style={{ borderColor: '#ddd' }}>
                        Download Chat
                    </button>
                    <button onClick={() => navigator.clipboard?.writeText(messages.map(m => `${m.role === 'user' ? 'You' : 'Co-Pilot'}: ${m.content}`).join('\n\n'))}
                        className="px-3 py-1 text-[11px] font-semibold border text-gray-500" style={{ borderColor: '#ddd' }}>
                        Copy All
                    </button>
                </div>
            )}

            {/* Input */}
            <div className="border-t p-4 flex gap-3" style={{ borderColor: '#ddd' }}>
                <input type="text" value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && sendChat()}
                    placeholder={placeholder}
                    className="flex-1 px-3 py-2.5 border text-sm focus:outline-none"
                    style={{ borderColor: '#ddd' }}
                    disabled={chatLoading}
                />
                <button onClick={sendChat} disabled={chatLoading || !input.trim()}
                    className="px-5 py-2.5 text-white text-sm font-semibold disabled:opacity-40"
                    style={{ background: color }}>
                    Send
                </button>
            </div>
        </div>
    );

    return (
        <div className="space-y-5">
            <div className="flex items-center justify-between">
                <h1 className="text-lg font-bold text-gray-800">Research Desk</h1>
                {docFilename && (
                    <button onClick={clearDocument} className="px-4 py-1.5 text-xs font-semibold border text-gray-500" style={{ borderColor: '#ddd' }}>
                        Upload Another File
                    </button>
                )}
            </div>

            {/* Document Status */}
            {docFilename ? (
                <div className="bg-white border px-4 py-3 flex items-center justify-between" style={{ borderColor: '#ddd', borderLeft: `4px solid ${color}` }}>
                    <div>
                        <span className="text-sm font-semibold text-gray-800">{docFilename}</span>
                        <span className="text-xs text-gray-400 ml-2">{docPages.length} pages extracted</span>
                    </div>
                </div>
            ) : (
                /* Upload Card */
                <div className="sansad-card">
                    <div className="sansad-card-header" style={{ background: color }}>Upload Document</div>
                    <div className="sansad-card-body text-center py-8">
                        <p className="text-sm text-gray-500 mb-4">Upload a PDF — Bills, Acts, Ordinances, Committee Reports, Policy Documents</p>
                        <label className="inline-block cursor-pointer">
                            <input type="file" accept=".pdf" onChange={handleUpload} className="hidden" disabled={uploading} />
                            <span className="px-6 py-2.5 text-white text-sm font-semibold inline-block" style={{ background: color, opacity: uploading ? 0.5 : 1 }}>
                                {uploading ? 'Extracting pages...' : 'Choose PDF File'}
                            </span>
                        </label>
                        <p className="text-xs text-gray-400 mt-3">Supported: PDF files up to 50MB</p>
                    </div>
                </div>
            )}

            {/* Tabs (when document loaded) */}
            {docFilename && (
                <>
                    <div className="sansad-tabs">
                        {[
                            { key: 'analyse', label: 'Analyse' },
                            { key: 'ask', label: 'Ask' },
                        ].map(t => (
                            <button key={t.key}
                                onClick={() => setTab(t.key)}
                                className={`sansad-tab ${tab === t.key ? 'sansad-tab-active' : ''}`}
                                style={tab === t.key ? { color } : {}}
                            >
                                {t.label}
                            </button>
                        ))}
                    </div>

                    {/* ANALYSE TAB */}
                    {tab === 'analyse' && (
                        <div className="space-y-4">
                            <div className="sansad-card">
                                <div className="sansad-card-header" style={{ background: color }}>
                                    Comprehensive Document Analysis
                                </div>
                                <div className="sansad-card-body space-y-4">
                                    <p className="text-xs text-gray-500">One-click analysis covering legal risks, stakeholder impact, and parliamentary talking points.</p>

                                    <div className="flex gap-4">
                                        <div>
                                            <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Language</label>
                                            <select value={language} onChange={e => setLanguage(e.target.value)}
                                                className="px-3 py-2 border text-sm" style={{ borderColor: '#ddd' }}>
                                                <option>English</option>
                                                <option>Hindi</option>
                                                <option>Bilingual</option>
                                            </select>
                                        </div>
                                        <div>
                                            <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Depth</label>
                                            <div className="flex gap-2">
                                                {['Quick Scan', 'Comprehensive'].map(d => (
                                                    <button key={d} onClick={() => setDepth(d)}
                                                        className="px-3 py-2 text-xs font-semibold border"
                                                        style={depth === d ? { background: color, color: 'white', borderColor: color } : { borderColor: '#ddd', color: '#555' }}
                                                    >
                                                        {d}
                                                    </button>
                                                ))}
                                            </div>
                                        </div>
                                    </div>

                                    <button onClick={runAnalysis} disabled={analysing}
                                        className="w-full py-2.5 text-white text-sm font-semibold disabled:opacity-40"
                                        style={{ background: color }}>
                                        {analysing ? 'Analysing document...' : 'Run Analysis'}
                                    </button>
                                </div>
                            </div>

                            {/* Analysis Output */}
                            {analysis && (
                                <div className="sansad-card">
                                    <div className="sansad-card-header" style={{ background: '#555' }}>
                                        Analysis Result
                                    </div>
                                    <div className="sansad-card-body">
                                        <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{analysis}</div>
                                        <div className="flex gap-3 mt-4 pt-3 border-t" style={{ borderColor: '#eee' }}>
                                            <button onClick={() => downloadText(analysis, `Analysis_${docFilename}.txt`)}
                                                className="px-4 py-1.5 text-xs font-semibold border text-gray-600" style={{ borderColor: '#ddd' }}>
                                                Download Analysis
                                            </button>
                                            <button onClick={() => navigator.clipboard?.writeText(analysis)}
                                                className="px-4 py-1.5 text-xs font-semibold border text-gray-600" style={{ borderColor: '#ddd' }}>
                                                Copy to Clipboard
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* ASK TAB */}
                    {tab === 'ask' && renderChat('Ask About This Document', 'Ask about this document...')}
                </>
            )}

            {/* Chat without document — general queries */}
            {!docFilename && renderChat('General Parliamentary Queries', 'Ask anything...')}
        </div>
    );
}
