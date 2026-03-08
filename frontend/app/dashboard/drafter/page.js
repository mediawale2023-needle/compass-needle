'use client';

import { useState } from 'react';
import { useAuth } from '@/lib/auth';
import { apiPost, AI_TIMEOUT } from '@/lib/api';

const RECIPIENT_TYPES = ['Cabinet Minister', 'Minister of State', 'Secretary to GoI', 'Chief Secretary', 'District Collector', 'Other Official'];
const TONES = ['Assertive (Opposition Style)', 'Requesting (Ministerial Courtesy)', 'Formal (Neutral)'];

function Field({ label, value, onChange, placeholder, textarea, rows }) {
    return (
        <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">{label}</label>
            {textarea ? (
                <textarea value={value} onChange={e => onChange(e.target.value)}
                    placeholder={placeholder} rows={rows || 3}
                    className="w-full px-3 py-2.5 border text-sm focus:outline-none resize-none"
                    style={{ borderColor: '#ddd' }} />
            ) : (
                <input type="text" value={value} onChange={e => onChange(e.target.value)}
                    placeholder={placeholder}
                    className="w-full px-3 py-2.5 border text-sm focus:outline-none"
                    style={{ borderColor: '#ddd' }} />
            )}
        </div>
    );
}

export default function DrafterPage() {
    const { user } = useAuth();
    const [mode, setMode] = useState('letter');

    // Letter fields
    const [recipientType, setRecipientType] = useState('Cabinet Minister');
    const [recipientName, setRecipientName] = useState('');
    const [ministry, setMinistry] = useState('');
    const [subject, setSubject] = useState('');
    const [reference, setReference] = useState('');
    const [keyPoints, setKeyPoints] = useState('');
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
        <div className="space-y-5">
            <div className="flex items-center justify-between">
                <h1 className="text-lg font-bold text-gray-800">Smart Drafter</h1>
                <span className="text-xs text-gray-400">
                    Drafting as <strong className="text-gray-600">{user?.display_name}</strong> · {user?.constituency} · {user?.house}
                </span>
            </div>

            {/* Mode tabs — switching does NOT clear fields */}
            <div className="sansad-tabs">
                {[
                    { key: 'letter', label: 'Official Letter' },
                    { key: 'question', label: 'Parliament Question' },
                ].map(t => (
                    <button key={t.key}
                        onClick={() => setMode(t.key)}
                        className={`sansad-tab ${mode === t.key ? 'sansad-tab-active' : ''}`}
                        style={mode === t.key ? { color } : {}}
                    >
                        {t.label}
                    </button>
                ))}
            </div>

            <div className="grid grid-cols-2 gap-5">
                {/* LEFT: Input Form */}
                <div className="space-y-4">
                    {mode === 'letter' ? (
                        <>
                            <div className="sansad-card">
                                <div className="sansad-card-header" style={{ background: color }}>Recipient Details</div>
                                <div className="sansad-card-body space-y-3">
                                    <div>
                                        <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Recipient Type</label>
                                        <select value={recipientType} onChange={e => setRecipientType(e.target.value)}
                                            className="w-full px-3 py-2.5 border text-sm" style={{ borderColor: '#ddd' }}>
                                            {RECIPIENT_TYPES.map(r => <option key={r} value={r}>{r}</option>)}
                                        </select>
                                    </div>
                                    <Field label="Recipient Name & Designation" value={recipientName} onChange={setRecipientName}
                                        placeholder="e.g., Shri Ashwini Vaishnaw, Hon'ble Minister of Railways" />
                                    <Field label="Ministry / Department / Office" value={ministry} onChange={setMinistry}
                                        placeholder="e.g., Ministry of Railways, Rail Bhavan, New Delhi" />
                                </div>
                            </div>

                            <div className="sansad-card">
                                <div className="sansad-card-header" style={{ background: color }}>Letter Content</div>
                                <div className="sansad-card-body space-y-3">
                                    <Field label="Subject" value={subject} onChange={setSubject}
                                        placeholder="e.g., Urgent need for platform extension at Belagavi Railway Station" />
                                    <Field label="Reference (Prior correspondence)" value={reference} onChange={setReference}
                                        placeholder="e.g., Letter dated 15.01.2025 / RTI Reply No. XYZ" />
                                    <Field label="Key Points to Cover" value={keyPoints} onChange={setKeyPoints} textarea rows={5}
                                        placeholder={"• Platform too short for 24-coach trains\n• 3 accidents in last 6 months\n• Request inspection by Railway Board"} />
                                </div>
                            </div>

                            <div className="sansad-card">
                                <div className="sansad-card-header" style={{ background: color }}>Settings</div>
                                <div className="sansad-card-body">
                                    <div className="flex gap-4">
                                        <div className="flex-1">
                                            <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Tone</label>
                                            <select value={tone} onChange={e => setTone(e.target.value)}
                                                className="w-full px-3 py-2.5 border text-sm" style={{ borderColor: '#ddd' }}>
                                                {TONES.map(t => <option key={t} value={t}>{t}</option>)}
                                            </select>
                                        </div>
                                        <div>
                                            <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Language</label>
                                            <select value={language} onChange={e => setLanguage(e.target.value)}
                                                className="px-3 py-2.5 border text-sm" style={{ borderColor: '#ddd' }}>
                                                <option>English</option>
                                                <option>Hindi</option>
                                            </select>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </>
                    ) : (
                        <div className="sansad-card">
                            <div className="sansad-card-header" style={{ background: color }}>Parliament Question</div>
                            <div className="sansad-card-body space-y-3">
                                <Field label="Subject" value={pqSubject} onChange={setPqSubject}
                                    placeholder="e.g., Status of Jal Jeevan Mission in rural Karnataka" />
                                <Field label="Ministry" value={pqMinistry} onChange={setPqMinistry}
                                    placeholder="e.g., Ministry of Jal Shakti" />
                                <Field label="Key Points / Context" value={pqPoints} onChange={setPqPoints} textarea rows={5}
                                    placeholder={"• 40% villages still without piped water\n• Funds allocated but not utilized\n• Request state-wise breakdown"} />
                                <div>
                                    <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Language</label>
                                    <select value={pqLang} onChange={e => setPqLang(e.target.value)}
                                        className="px-3 py-2.5 border text-sm" style={{ borderColor: '#ddd' }}>
                                        <option>English</option>
                                        <option>Hindi</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                    )}

                    <button onClick={generate}
                        disabled={loading || (mode === 'letter' ? !recipientName || !subject : !pqSubject)}
                        className="w-full py-2.5 text-white text-sm font-semibold disabled:opacity-40"
                        style={{ background: color }}>
                        {loading ? 'Generating...' : mode === 'letter' ? 'Generate Letter' : 'Generate Question'}
                    </button>
                </div>

                {/* RIGHT: Output */}
                <div className="sansad-card" style={{ display: 'flex', flexDirection: 'column' }}>
                    <div className="sansad-card-header" style={{ background: '#555' }}>
                        Preview
                    </div>
                    <div className="sansad-card-body flex-1 overflow-y-auto" style={{ minHeight: 400 }}>
                        {draft ? (
                            <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{draft}</div>
                        ) : (
                            <div className="text-sm text-gray-400 text-center py-16">
                                {loading ? 'Generating your draft...' : 'Your draft will appear here'}
                            </div>
                        )}
                    </div>
                    {draft && (
                        <div className="border-t px-5 py-3 flex gap-3 items-center" style={{ borderColor: '#eee' }}>
                            <button onClick={saveDraft} disabled={saved}
                                className="px-4 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                                style={{ background: saved ? '#999' : color }}>
                                {saved ? 'Saved to Archives' : 'Save to Archives'}
                            </button>
                            <button onClick={downloadDraft}
                                className="px-4 py-1.5 text-xs font-semibold border text-gray-600" style={{ borderColor: '#ddd' }}>
                                Download
                            </button>
                            <button onClick={() => navigator.clipboard?.writeText(draft)}
                                className="px-4 py-1.5 text-xs font-semibold border text-gray-600" style={{ borderColor: '#ddd' }}>
                                Copy
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
