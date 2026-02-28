'use client';
import { useState, useEffect, useRef } from 'react';
import { apiGet, apiPut, apiDelete, apiUpload } from '@/lib/api';

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

    const aConst = aSelection === '__new__' ? newAssembly : aSelection;

    const handleParsePDF = async () => {
        const file = fileRef.current?.files?.[0];
        if (!file || !pConst || !aConst) return;
        setParsing(true);
        setMsg({});
        try {
            const r = await apiUpload('/api/admin/geography/upload-pdf', file);
            const stations = r.stations || [];
            setParsedStations(stations);
            setJsonText(JSON.stringify(stations, null, 2));
            setMsg({ type: 'success', text: `Extracted ${stations.length} stations` });
        } catch (err) {
            setMsg({ type: 'error', text: err.message });
        } finally {
            setParsing(false);
        }
    };

    const handleSave = async () => {
        try {
            const data = JSON.parse(jsonText);
            await apiPut(`/api/admin/geography/${encodeURIComponent(pConst)}/${encodeURIComponent(aConst)}`, { data });
            setMsg({ type: 'success', text: 'Saved!' });
            setParsedStations(null);
            loadSavedFiles();
        } catch {
            setMsg({ type: 'error', text: 'Invalid JSON' });
        }
    };

    const handleDeleteGeo = async (pc, ac) => {
        try {
            await apiDelete(`/api/admin/geography/${encodeURIComponent(pc)}/${encodeURIComponent(ac)}`);
            loadSavedFiles();
        } catch { }
    };

    return (
        <>
            <div className="section-title">Upload Polling Station Data</div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: '1rem' }}>
                <div>
                    <label className="form-label">Parliamentary Constituency</label>
                    <select className="form-input" value={pConst} onChange={e => { setPConst(e.target.value); setASelection(''); }}>
                        <option value="">Select...</option>
                        {constituencies.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                </div>
                <div>
                    <label className="form-label">Assembly Constituency</label>
                    {pConst ? (
                        <>
                            <select className="form-input" value={aSelection} onChange={e => setASelection(e.target.value)}>
                                {assemblies.map(a => <option key={a} value={a}>{a}</option>)}
                                <option value="__new__">+ Add New Assembly...</option>
                            </select>
                            {aSelection === '__new__' && (
                                <input className="form-input" style={{ marginTop: 8 }} placeholder="e.g. Belgaum Uttar" value={newAssembly} onChange={e => setNewAssembly(e.target.value)} />
                            )}
                        </>
                    ) : (
                        <select className="form-input" disabled><option>Select a Parliamentary Constituency first</option></select>
                    )}
                </div>
            </div>

            <div style={{ marginBottom: '1rem' }}>
                <label className="form-label">Upload Election Commission PDF</label>
                <input type="file" accept=".pdf" ref={fileRef} className="form-input" style={{ padding: 8 }} />
            </div>

            {pConst && aConst && (
                <button className="btn-primary" onClick={handleParsePDF} disabled={parsing} style={{ width: '100%', marginBottom: '1rem' }}>
                    {parsing ? 'Parsing...' : 'Parse PDF'}
                </button>
            )}

            {msg.text && (
                <div style={{
                    background: msg.type === 'success' ? 'rgba(5,150,105,0.06)' : 'rgba(220,38,38,0.06)',
                    border: `1px solid ${msg.type === 'success' ? 'rgba(5,150,105,0.15)' : 'rgba(220,38,38,0.15)'}`,
                    color: msg.type === 'success' ? '#059669' : '#dc2626',
                    padding: '10px 14px', borderRadius: 10, fontSize: '0.82rem', marginBottom: '1rem',
                }}>{msg.text}</div>
            )}

            {parsedStations && (
                <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                    <h3 style={{ color: '#1a2e28', fontSize: '1rem', fontWeight: 600, marginBottom: 12 }}>JSON Editor</h3>
                    <textarea
                        className="form-input"
                        rows={14}
                        value={jsonText}
                        onChange={e => setJsonText(e.target.value)}
                        style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}
                    />
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 12 }}>
                        <button className="btn-primary" onClick={handleSave}>Save</button>
                        <button className="btn-secondary" onClick={() => setParsedStations(null)}>Discard</button>
                    </div>
                </div>
            )}

            <hr style={{ border: 'none', borderTop: '1px solid #e2ebe5', margin: '1.5rem 0' }} />

            <div className="section-title">Saved Geography Files</div>
            {savedPCs.length === 0 ? (
                <div className="glass-panel" style={{ textAlign: 'center', color: '#6b7f76', padding: '2rem' }}>No geography data uploaded yet.</div>
            ) : (
                savedPCs.map(pc => (
                    <div key={pc} className="glass-panel" style={{ marginBottom: 12 }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
                            onClick={() => setSavedData(prev => ({ ...prev, [`${pc}_open`]: !prev[`${pc}_open`] }))}>
                            <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>🏛️ {pc}</span>
                            <span style={{ color: '#6b7f76', fontSize: '0.75rem' }}>{(savedData[pc] || []).length} assemblies</span>
                        </div>
                        {savedData[`${pc}_open`] && (savedData[pc] || []).map(ac => (
                            <div key={ac} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderTop: '1px solid #f0f4f1', marginTop: 8 }}>
                                <span style={{ fontSize: '0.85rem' }}><strong>{ac}</strong></span>
                                <button className="btn-danger" style={{ fontSize: '0.72rem', padding: '4px 10px' }} onClick={() => handleDeleteGeo(pc, ac)}>Delete</button>
                            </div>
                        ))}
                    </div>
                ))
            )}
        </>
    );
}
