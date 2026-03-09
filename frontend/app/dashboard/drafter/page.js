'use client';

import { useState } from 'react';
import { useAuth } from '@/lib/auth';
import { apiPost, AI_TIMEOUT } from '@/lib/api';
import { useSearchParams } from 'next/navigation';

const RECIPIENT_TYPES = ['Cabinet Minister', 'Minister of State', 'Secretary to GoI', 'Chief Secretary', 'District Collector', 'Other Official'];
const TONES = ['Assertive (Opposition Style)', 'Requesting (Ministerial Courtesy)', 'Formal (Neutral)'];

export default function DrafterPage() {
    const { user } = useAuth();
    const searchParams = useSearchParams();

    const [mode, setMode] = useState('letter');

    // Letter fields
    const [recipientType, setRecipientType] = useState('Cabinet Minister');
    const [recipientName, setRecipientName] = useState(searchParams.get('recipient') || '');
    const [ministry, setMinistry] = useState('');
    const [subject, setSubject] = useState(searchParams.get('subject') || '');
    const [reference, setReference] = useState('');
    const [keyPoints, setKeyPoints] = useState(searchParams.get('context') || '');
    const [tone, setTone] = useState('Assertive (Opposition Style)');
    const [language, setLanguage] = useState('English');

    // PQ fields
    const [pqSubject, setPqSubject] = useState('');
    const [pqMinistry, setPqMinistry] = useState('');
    const [pqPoints, setPqPoints] = useState('');
    const [pqLang, setPqLang] = useState('English');

    const [draft, setDraft] = useState('');
    const [loading, setLoading] = useState(false);
    const [saved, setSaved] = useState(false);
    const color = user?.theme_color || '#006a4d';

    const generate = async () => {
        setLoading(true);
        setDraft('');
        setSaved(false);
        try {
            const body = mode === 'letter'
                ? { mode, subject, recipient_name: recipientName, recipient_type: recipientType, ministry, reference, key_points: keyPoints, tone, language }
                : { mode: 'question', subject: pqSubject, ministry: pqMinistry, key_points: pqPoints, language: pqLang };
            const data = await apiPost('/api/drafter/generate', body, { timeout: AI_TIMEOUT, noRetry: true });
            setDraft(data.content || 'No content generated.');
        } catch (err) {
            setDraft('Error: ' + err.message);
        } finally {
            setLoading(false);
        }
    };

    const downloadDraft = () => {
        const blob = new Blob([draft], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const title = mode === 'letter' ? (subject || 'letter') : (pqSubject || 'question');
        a.download = `${mode === 'letter' ? 'Letter' : 'PQ'}_${title.replace(/[^a-zA-Z0-9]/g, '_').slice(0, 30)}.txt`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const saveDraft = async () => {
        const title = mode === 'letter' ? (subject || 'Untitled Letter') : (pqSubject || 'Untitled Question');
        try {
            await apiPost('/api/history/save', {
                activity_type: mode === 'letter' ? 'draft_letter' : 'draft_question',
                title,
                content: draft,
                metadata: mode === 'letter'
                    ? { recipient: recipientName, ministry, tone, language }
                    : { ministry: pqMinistry, language: pqLang },
            });
            setSaved(true);
        } catch (err) {
            alert('Failed to save: ' + err.message);
        }
    };

    return (
        <div className="space-y-4 max-w-4xl mx-auto">
            <h1 className="text-lg font-bold text-gray-900">Drafter</h1>

            <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
                {/* Tabs */}
                <div className="px-6 border-b border-gray-100 flex gap-6 pt-4">
                    {[
                        { id: 'letter', label: 'Write Letter', icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" /></svg> },
                        { id: 'question', label: 'Parliamentary Question', icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><circle cx="12" cy="14" r="1" /><path d="M12 11.5a1.5 1.5 0 0 1 1-1.5 1.5 1.5 0 0 0-1.5-2.5" /></svg> }
                    ].map(t => (
                        <button key={t.id} onClick={() => { setMode(t.id); setDraft(''); setSaved(false); }}
                            className="flex items-center gap-2 pb-3 text-sm font-semibold transition-colors"
                            style={mode === t.id
                                ? { color, borderBottom: `2px solid ${color}` }
                                : { color: '#6b7280', borderBottom: '2px solid transparent' }}>
                            {t.icon} {t.label}
                        </button>
                    ))}
                </div>

                {/* Form Body */}
                <div className="p-6 space-y-6">
                    {mode === 'letter' ? (
                        <>
                            <div className="grid grid-cols-2 gap-6">
                                <div>
                                    <label className="block text-sm font-semibold text-gray-700 mb-1.5">Recipient Type</label>
                                    <select value={recipientType} onChange={e => setRecipientType(e.target.value)}
                                        className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-800 focus:outline-none focus:ring-1" style={{ outlineColor: color }}>
                                        {RECIPIENT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-sm font-semibold text-gray-700 mb-1.5">Recipient Name</label>
                                    <input type="text" value={recipientName} onChange={e => setRecipientName(e.target.value)}
                                        placeholder="e.g., Secretary, Ministry Name"
                                        className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-800 focus:outline-none focus:ring-1" style={{ outlineColor: color }} />
                                </div>
                            </div>

                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1.5">Ministry/Department</label>
                                <input type="text" value={ministry} onChange={e => setMinistry(e.target.value)}
                                    placeholder="e.g., Ministry of Road Transport and Highways"
                                    className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-800 focus:outline-none focus:ring-1" style={{ outlineColor: color }} />
                            </div>

                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1.5">Subject</label>
                                <input type="text" value={subject} onChange={e => setSubject(e.target.value)}
                                    placeholder="Brief subject line"
                                    className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-800 focus:outline-none focus:ring-1" style={{ outlineColor: color }} />
                            </div>

                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1.5">Reference No. (Optional)</label>
                                <input type="text" value={reference} onChange={e => setReference(e.target.value)}
                                    placeholder="e.g., MP/2026/123"
                                    className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-800 focus:outline-none focus:ring-1" style={{ outlineColor: color }} />
                            </div>

                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1.5">Key Points (one per line)</label>
                                <textarea value={keyPoints} onChange={e => setKeyPoints(e.target.value)}
                                    placeholder="Enter key points, one per line" rows={4}
                                    className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-800 resize-none focus:outline-none focus:ring-1" style={{ outlineColor: color }} />
                            </div>

                            <div className="grid grid-cols-2 gap-6 pb-2">
                                <div>
                                    <label className="block text-sm font-semibold text-gray-700 mb-1.5">Language</label>
                                    <select value={language} onChange={e => setLanguage(e.target.value)}
                                        className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-800 focus:outline-none focus:ring-1" style={{ outlineColor: color }}>
                                        {['English', 'Hindi', 'Kannada', 'Marathi', 'Tamil', 'Telugu', 'Bengali'].map(l => <option key={l} value={l}>{l}</option>)}
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-sm font-semibold text-gray-700 mb-1.5">Tone</label>
                                    <select value={tone} onChange={e => setTone(e.target.value)}
                                        className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-800 focus:outline-none focus:ring-1" style={{ outlineColor: color }}>
                                        {TONES.map(t => <option key={t} value={t}>{t}</option>)}
                                    </select>
                                </div>
                            </div>
                        </>
                    ) : (
                        <div className="space-y-6">
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1.5">Target Ministry</label>
                                <input type="text" value={pqMinistry} onChange={e => setPqMinistry(e.target.value)}
                                    placeholder="Target Ministry"
                                    className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-800 focus:outline-none focus:ring-1" style={{ outlineColor: color }} />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1.5">Question Subject</label>
                                <input type="text" value={pqSubject} onChange={e => setPqSubject(e.target.value)}
                                    placeholder="Issue to raise"
                                    className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-800 focus:outline-none focus:ring-1" style={{ outlineColor: color }} />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1.5">Specific Data Points Needed</label>
                                <textarea value={pqPoints} onChange={e => setPqPoints(e.target.value)}
                                    placeholder="e.g. state-wise breakdown, funds allocated vs used" rows={4}
                                    className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-800 resize-none focus:outline-none focus:ring-1" style={{ outlineColor: color }} />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1.5">Language</label>
                                <select value={pqLang} onChange={e => setPqLang(e.target.value)}
                                    className="w-full px-4 py-2.5 w-1/2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-800 focus:outline-none focus:ring-1" style={{ outlineColor: color }}>
                                    {['English', 'Hindi'].map(l => <option key={l} value={l}>{l}</option>)}
                                </select>
                            </div>
                        </div>
                    )}

                    <div className="pt-4 border-t border-gray-100 flex items-center justify-between">
                        <p className="text-xs text-gray-400">Uses AI to generate a structured, formal draft.</p>
                        <button onClick={generate} disabled={loading}
                            className="px-6 py-2.5 text-white font-bold rounded-lg shadow-sm disabled:opacity-50"
                            style={{ background: color }}>
                            {loading ? 'Generating...' : `Generate ${mode === 'letter' ? 'Letter' : 'Question'}`}
                        </button>
                    </div>
                </div>
            </div>

            {/* Results Output */}
            {draft && (
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden animate-fade-in">
                    <div className="px-6 py-4 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
                        <div className="font-bold text-gray-900">Generated {mode === 'letter' ? 'Letter Draft' : 'Parliamentary Question'}</div>
                        <div className="flex gap-3">
                            {saved ? (
                                <span className="px-4 py-2 text-sm font-semibold text-green-700 bg-green-50 border border-transparent rounded-lg">Saved to Archives</span>
                            ) : (
                                <button onClick={saveDraft} className="px-4 py-2 text-sm font-semibold border border-gray-200 bg-white text-gray-700 rounded-lg hover:bg-gray-50 transition-colors">
                                    Save to Archives
                                </button>
                            )}
                            <button onClick={downloadDraft} className="px-4 py-2 text-sm font-bold text-white rounded-lg transition-opacity hover:opacity-90" style={{ background: color }}>
                                Download Text
                            </button>
                        </div>
                    </div>
                    <div>
                        <textarea
                            value={draft}
                            onChange={(e) => setDraft(e.target.value)}
                            className="w-full h-96 p-6 bg-white text-sm text-gray-800 font-serif leading-relaxed resize-y focus:outline-none"
                        />
                    </div>
                </div>
            )}
        </div>
    );
}
