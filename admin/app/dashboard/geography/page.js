'use client';
import { useState, useEffect, useRef } from 'react';
import { apiGet, apiPut, apiDelete, apiUpload } from '@/lib/api';
import ConfirmModal from '@/components/ConfirmModal';

export default function GeographyUploadPage() {
    const [constituencies, setConstituencies] = useState([]);
    const [pConst, setPConst] = useState('');
    const [assemblies, setAssemblies] = useState([]);
    const [aSelection, setASelection] = useState('');
    const [newAssembly, setNewAssembly] = useState('');
    const [parsedStations, setParsedStations] = useState(null);
    const [jsonText, setJsonText] = useState('');
    const [savedPCs, setSavedPCs] = useState([]);
    const [savedData, setSavedData] = useState({});
    const [msg, setMsg] = useState({ type: '', text: '' });
    const [parsing, setParsing] = useState(false);
    const [showRawJson, setShowRawJson] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState(null); // {pc, ac}
    const fileRef = useRef();

    useEffect(() => {
        apiGet('/api/admin/constituencies').then(r => setConstituencies(r.constituencies || [])).catch(() => { });
        loadSavedFiles();
    }, []);

    useEffect(() => {
        if (!pConst) { setAssemblies([]); return; }
        apiGet(`/api/admin/geography/${encodeURIComponent(pConst)}/assemblies`).then(r => setAssemblies(r.assemblies || [])).catch(() => { });
    }, [pConst]);

    const loadSavedFiles = async () => {
        try {
            const r = await apiGet('/api/admin/geography/parliamentary');
            const pcs = r.parliamentary_constituencies || [];
            setSavedPCs(pcs);
            const data = {};
            for (const pc of pcs) {
                const ar = await apiGet(`/api/admin/geography/${encodeURIComponent(pc)}/assemblies`);
                data[pc] = ar.assemblies || [];
            }
            setSavedData(data);
        } catch { }
    };

    const showMsg = (type, text) => {
        setMsg({ type, text });
        setTimeout(() => setMsg({ type: '', text: '' }), 4000);
    };

    const aConst = aSelection === '__new__' ? newAssembly : aSelection;

    const handleParsePDF = async () => {
        const file = fileRef.current?.files?.[0];
        if (!file || !pConst || !aConst) return;
        setParsing(true);
        setMsg({});
        try {
            const r = await apiUpload('/api/admin/geography/upload-pdf', file);

            // Hindi/Krutidev PDFs are processed async — poll until done
            if (r.job_id) {
                showMsg('success', 'Hindi PDF detected — processing with AI OCR…');
                const stations = await pollOcrJob(r.job_id);
                setParsedStations(stations);
                setJsonText(JSON.stringify(stations, null, 2));
                showMsg('success', `Extracted ${stations.length} stations`);
            } else {
                const stations = r.stations || [];
                setParsedStations(stations);
                setJsonText(JSON.stringify(stations, null, 2));
                showMsg('success', `Extracted ${stations.length} stations`);
            }
        } catch (err) {
            showMsg('error', err.message);
        } finally {
            setParsing(false);
        }
    };

    const pollOcrJob = async (jobId) => {
        const INTERVAL = 4000;
        const MAX_WAIT = 5 * 60 * 1000; // 5 minutes
        const start = Date.now();
        while (Date.now() - start < MAX_WAIT) {
            await new Promise(res => setTimeout(res, INTERVAL));
            const job = await apiGet(`/api/admin/geography/ocr-job/${jobId}`);
            if (job.status === 'done') return job.stations || [];
            if (job.status === 'error') throw new Error(job.error || 'OCR failed');
        }
        throw new Error('OCR timed out after 5 minutes');
    };

    const handleSave = async () => {
        try {
            const data = JSON.parse(jsonText);
            await apiPut(`/api/admin/geography/${encodeURIComponent(pConst)}/${encodeURIComponent(aConst)}`, { data });
            showMsg('success', 'Geography data saved successfully.');
            setParsedStations(null);
            loadSavedFiles();
        } catch {
            showMsg('error', 'Invalid JSON — please check the editor.');
        }
    };

    const handleDeleteGeo = async (pc, ac) => {
        setDeleteTarget({ pc, ac });
    };

    const confirmDelete = async () => {
        if (!deleteTarget) return;
        const { pc, ac } = deleteTarget;
        setDeleteTarget(null);
        try {
            await apiDelete(`/api/admin/geography/${encodeURIComponent(pc)}/${encodeURIComponent(ac)}`);
            loadSavedFiles();
        } catch { }
    };

    return (
        <>
            {msg.text && <div className={`toast ${msg.type === 'success' ? 'toast-success' : 'toast-error'}`}>{msg.text}</div>}

            {/* Confirm Delete Modal */}
            {deleteTarget && (
                <ConfirmModal
                    title={`Delete assembly "${deleteTarget.ac}"?`}
                    description={`This will remove all polling station data for "${deleteTarget.ac}" from ${deleteTarget.pc}. This action cannot be undone.`}
                    confirmLabel="Delete"
                    variant="danger"
                    onConfirm={confirmDelete}
                    onCancel={() => setDeleteTarget(null)}
                />
            )}

            {/* Upload form */}
            <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                <div className="section-title">Upload Polling Station Data</div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: '1rem' }}>
                    <div className="form-row" style={{ marginBottom: 0 }}>
                        <label className="form-label">Parliamentary Constituency</label>
                        <select className="form-input" value={pConst} onChange={e => { setPConst(e.target.value); setASelection(''); }}>
                            <option value="">Select…</option>
                            {constituencies.map(c => <option key={c} value={c}>{c}</option>)}
                        </select>
                    </div>
                    <div className="form-row" style={{ marginBottom: 0 }}>
                        <label className="form-label">Assembly Constituency</label>
                        {pConst ? (
                            <>
                                <select className="form-input" value={aSelection} onChange={e => setASelection(e.target.value)}>
                                    <option value="">Select…</option>
                                    {assemblies.map(a => <option key={a} value={a}>{a}</option>)}
                                    <option value="__new__">+ Add New Assembly…</option>
                                </select>
                                {aSelection === '__new__' && (
                                    <input
                                        className="form-input"
                                        style={{ marginTop: 8 }}
                                        placeholder="e.g. Belgaum Uttar"
                                        value={newAssembly}
                                        onChange={e => setNewAssembly(e.target.value)}
                                    />
                                )}
                            </>
                        ) : (
                            <select className="form-input" disabled>
                                <option>Select a parliamentary constituency first</option>
                            </select>
                        )}
                    </div>
                </div>

                <div className="form-row">
                    <label className="form-label">Election Commission PDF</label>
                    <input type="file" accept=".pdf" ref={fileRef} className="form-input" style={{ padding: 8 }} />
                </div>

                <button
                    className="btn-primary"
                    onClick={handleParsePDF}
                    disabled={!pConst || !aConst || parsing}
                    style={{ width: '100%' }}
                >
                    {parsing ? 'Parsing PDF…' : 'Parse PDF'}
                </button>
            </div>

            {/* JSON editor */}
            {parsedStations && (
                <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                    <div className="section-title">JSON Editor — Review Before Saving</div>
                    <textarea
                        className="form-input"
                        rows={14}
                        value={jsonText}
                        onChange={e => setJsonText(e.target.value)}
                        style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}
                    />
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 12 }}>
                        <button className="btn-primary" onClick={handleSave}>Save to Database</button>
                        <button className="btn-secondary" onClick={() => { setParsedStations(null); setJsonText(''); }}>Discard</button>
                    </div>
                </div>
            )}

            <hr className="divider" />

            {/* Saved geography list */}
            <div className="section-title" style={{ marginBottom: '1rem' }}>Saved Geography Files</div>

            {savedPCs.length === 0 ? (
                <div className="glass-panel">
                    <div className="empty-state">
                        <div className="empty-state-icon">
                            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M3 6l9-4 9 4v12l-9 4-9-4V6z"/><path d="M12 2v20M3 6l9 4 9-4"/>
                            </svg>
                        </div>
                        <div className="empty-state-title">No geography data uploaded yet</div>
                        <div className="empty-state-desc">Upload an Election Commission PDF above to get started</div>
                    </div>
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {savedPCs.map(pc => (
                        <div key={pc} className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
                            <div
                                style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', cursor: 'pointer' }}
                                onClick={() => setSavedData(prev => ({ ...prev, [`${pc}_open`]: !prev[`${pc}_open`] }))}
                            >
                                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#006a4d" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M3 6l9-4 9 4v12l-9 4-9-4V6z"/>
                                    </svg>
                                    <span style={{ fontWeight: 600, fontSize: '0.88rem', color: '#1a2e28' }}>{pc}</span>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                    <span className="badge badge-slate">{(savedData[pc] || []).length} assemblies</span>
                                    <svg
                                        width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6b7f76" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                                        style={{ transform: savedData[`${pc}_open`] ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}
                                    >
                                        <polyline points="6 9 12 15 18 9"/>
                                    </svg>
                                </div>
                            </div>
                            {savedData[`${pc}_open`] && (
                                <div style={{ borderTop: '1px solid #e2ebe5' }}>
                                    {(savedData[pc] || []).length === 0 ? (
                                        <div style={{ padding: '12px 16px', color: '#6b7f76', fontSize: '0.82rem' }}>No assemblies found</div>
                                    ) : (savedData[pc] || []).map(ac => (
                                        <div key={ac} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 16px', borderBottom: '1px solid #f0f4f1' }}>
                                            <span style={{ fontSize: '0.85rem', color: '#1a2e28' }}>{ac}</span>
                                            <button
                                                className="btn-danger"
                                                style={{ fontSize: '0.72rem', padding: '4px 10px' }}
                                                onClick={() => handleDeleteGeo(pc, ac)}
                                            >
                                                Delete
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </>
    );
}
