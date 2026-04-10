'use client';
import { useState, useEffect, useRef, useMemo } from 'react';
import { apiGet, apiPut, apiDelete, apiUpload } from '@/lib/api';
import ConfirmModal from '@/components/ConfirmModal';

// ─── style constants ───────────────────────────────────────────────────────────
const TH = {
    padding: '8px 12px', textAlign: 'left', fontSize: '0.72rem',
    fontWeight: 700, color: '#4a635a', textTransform: 'uppercase', letterSpacing: '0.05em',
};
const TD = { padding: '8px 12px', color: '#1a2e28', verticalAlign: 'middle' };
const DEL_BTN = {
    background: 'none', border: 'none', cursor: 'pointer',
    color: '#cbd5d0', fontSize: '1.1rem', lineHeight: 1, padding: '2px 6px',
    borderRadius: 4, transition: 'color 0.15s',
};

// Locality may still contain a building/institution name — flag it for review
const FLAG_PAT = /\b(?:School|College|Vidyalaya|Vidhyalaya|Academy|Sadan|Niketan|Kendra|Hall|Office|Karyalay|Mandir|Bhavan|Bhawan|Panchayat)\b/i;

// ─── ReviewTable ───────────────────────────────────────────────────────────────
function ReviewTable({ stations, onChange }) {
    const [search, setSearch]           = useState('');
    const [deduped, setDeduped]         = useState(true);
    const [onlyFlagged, setOnlyFlagged] = useState(false);
    const [editingKey, setEditingKey]   = useState(null); // string (deduped) or number index (raw)
    const [editVal, setEditVal]         = useState('');
    const [showRaw, setShowRaw]         = useState(false);
    const inputRef                      = useRef();

    useEffect(() => {
        if (editingKey !== null && inputRef.current) {
            inputRef.current.focus();
            inputRef.current.select();
        }
    }, [editingKey]);

    // Build deduped map: locality → {count, indices[]}
    const uniqueMap = useMemo(() => {
        const map = new Map();
        stations.forEach((s, idx) => {
            const loc = (s.locality || '').trim();
            if (!map.has(loc)) map.set(loc, { locality: loc, count: 0, indices: [] });
            const e = map.get(loc);
            e.count++;
            e.indices.push(idx);
        });
        return map;
    }, [stations]);

    const lower = search.toLowerCase();

    const dedupedRows = useMemo(() => {
        let rows = [...uniqueMap.values()];
        if (lower) rows = rows.filter(r => r.locality.toLowerCase().includes(lower));
        if (onlyFlagged) rows = rows.filter(r => FLAG_PAT.test(r.locality));
        return rows;
    }, [uniqueMap, lower, onlyFlagged]);

    const rawRows = useMemo(() => {
        let rows = stations.map((s, idx) => ({ ...s, _idx: idx }));
        if (lower) rows = rows.filter(s => (s.locality || '').toLowerCase().includes(lower));
        if (onlyFlagged) rows = rows.filter(s => FLAG_PAT.test(s.locality || ''));
        return rows;
    }, [stations, lower, onlyFlagged]);

    const flagCount = useMemo(
        () => [...uniqueMap.keys()].filter(k => FLAG_PAT.test(k)).length,
        [uniqueMap],
    );

    // ── Edit ──────────────────────────────────────────────────────────────────
    const startEdit = (key, value) => { setEditingKey(key); setEditVal(value); };

    const commitEdit = () => {
        const trimmed = editVal.trim();
        if (!trimmed) { setEditingKey(null); return; }
        if (typeof editingKey === 'string') {
            if (trimmed !== editingKey) {
                onChange(stations.map(s =>
                    (s.locality || '').trim() === editingKey ? { ...s, locality: trimmed } : s
                ));
            }
        } else {
            if (trimmed !== stations[editingKey]?.locality) {
                const updated = [...stations];
                updated[editingKey] = { ...updated[editingKey], locality: trimmed };
                onChange(updated);
            }
        }
        setEditingKey(null);
    };

    // ── Delete ────────────────────────────────────────────────────────────────
    const deleteRow = (key) => {
        if (typeof key === 'string') {
            onChange(stations.filter(s => (s.locality || '').trim() !== key));
        } else {
            onChange(stations.filter((_, i) => i !== key));
        }
        if (editingKey === key) setEditingKey(null);
    };

    // ── Add ───────────────────────────────────────────────────────────────────
    const addRow = () => {
        const newLoc = 'New Locality';
        onChange([...stations, { station_number: '', locality: newLoc, building_name: '' }]);
        setTimeout(() => startEdit(deduped ? newLoc : stations.length, newLoc), 40);
    };

    const displayRows = deduped ? dedupedRows : rawRows;

    return (
        <div>
            {/* Stats bar */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                <span className="badge badge-green">{stations.length} stations</span>
                <span className="badge badge-slate">{uniqueMap.size} unique localities</span>
                {flagCount > 0 && (
                    <span className="badge badge-amber">⚠ {flagCount} to review</span>
                )}
            </div>

            {/* Controls */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                <input
                    className="form-input"
                    style={{ flex: 1, minWidth: 180, marginBottom: 0, padding: '7px 10px' }}
                    placeholder="Search localities…"
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                />
                <button
                    onClick={() => setDeduped(d => !d)}
                    className={deduped ? 'btn-primary' : 'btn-secondary'}
                    style={{ fontSize: '0.77rem', padding: '7px 12px', whiteSpace: 'nowrap' }}
                    title={deduped ? 'Unique mode — click to show all rows' : 'All rows — click to show unique only'}
                >
                    {deduped ? '⊞ Unique' : '≡ All rows'}
                </button>
                {flagCount > 0 && (
                    <button
                        onClick={() => setOnlyFlagged(f => !f)}
                        style={{
                            fontSize: '0.77rem', padding: '7px 12px', whiteSpace: 'nowrap',
                            border: `1px solid ${onlyFlagged ? '#d97706' : '#e2ebe5'}`,
                            borderRadius: 8, cursor: 'pointer', fontWeight: 600,
                            background: onlyFlagged ? '#d97706' : '#fff',
                            color: onlyFlagged ? '#fff' : '#d97706',
                            transition: 'all 0.15s',
                        }}
                        title="Show only entries that may contain building names"
                    >
                        ⚠ Flagged only
                    </button>
                )}
                <button
                    onClick={addRow}
                    className="btn-secondary"
                    style={{ fontSize: '0.77rem', padding: '7px 12px' }}
                >
                    + Add
                </button>
            </div>

            {/* Table */}
            <div style={{ border: '1px solid #e2ebe5', borderRadius: 8, overflow: 'hidden', maxHeight: 440, overflowY: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.83rem' }}>
                    <thead style={{ position: 'sticky', top: 0, background: '#f4f6f5', zIndex: 1 }}>
                        <tr style={{ borderBottom: '1px solid #e2ebe5' }}>
                            {!deduped && <th style={{ ...TH, width: 44, color: '#9ca3af' }}>#</th>}
                            <th style={TH}>Locality</th>
                            {deduped && <th style={{ ...TH, width: 60, textAlign: 'center' }}>Stations</th>}
                            <th style={{ ...TH, width: 36 }}></th>
                        </tr>
                    </thead>
                    <tbody>
                        {displayRows.length === 0 ? (
                            <tr>
                                <td colSpan={3} style={{ padding: '20px', textAlign: 'center', color: '#9ca3af', fontSize: '0.82rem' }}>
                                    {search || onlyFlagged ? 'No matching localities.' : 'No data.'}
                                </td>
                            </tr>
                        ) : displayRows.map((row, i) => {
                            const key = deduped ? row.locality : row._idx;
                            const loc = row.locality;
                            const flagged = FLAG_PAT.test(loc || '');
                            const isEditing = editingKey === key;

                            return (
                                <tr key={String(key) + i} style={{
                                    borderBottom: '1px solid #f0f4f1',
                                    background: flagged ? '#fffdf4' : undefined,
                                }}>
                                    {!deduped && (
                                        <td style={{ ...TD, color: '#c0cbc4', fontSize: '0.74rem' }}>{row.station_number}</td>
                                    )}
                                    <td style={TD}>
                                        {isEditing ? (
                                            <input
                                                ref={inputRef}
                                                className="form-input"
                                                style={{ margin: 0, padding: '4px 8px', fontSize: '0.83rem' }}
                                                value={editVal}
                                                onChange={e => setEditVal(e.target.value)}
                                                onBlur={commitEdit}
                                                onKeyDown={e => {
                                                    if (e.key === 'Enter') commitEdit();
                                                    if (e.key === 'Escape') setEditingKey(null);
                                                }}
                                            />
                                        ) : (
                                            <span
                                                onClick={() => startEdit(key, loc)}
                                                style={{ cursor: 'text', display: 'flex', alignItems: 'center', gap: 5, padding: '2px 0' }}
                                                title="Click to edit"
                                            >
                                                {flagged && (
                                                    <span title="May contain building/institution name" style={{ color: '#d97706', fontSize: '0.72rem', flexShrink: 0 }}>⚠</span>
                                                )}
                                                <span>{loc || <em style={{ color: '#c0cbc4' }}>empty</em>}</span>
                                            </span>
                                        )}
                                    </td>
                                    {deduped && (
                                        <td style={{ ...TD, textAlign: 'center' }}>
                                            <span className="badge badge-slate" style={{ fontSize: '0.7rem', padding: '2px 7px' }}>{row.count}</span>
                                        </td>
                                    )}
                                    <td style={{ ...TD, textAlign: 'center', padding: '4px' }}>
                                        <button
                                            style={DEL_BTN}
                                            onMouseEnter={e => e.currentTarget.style.color = '#ef4444'}
                                            onMouseLeave={e => e.currentTarget.style.color = '#cbd5d0'}
                                            onClick={() => deleteRow(key)}
                                            title={deduped ? 'Remove all stations with this locality' : 'Remove this row'}
                                        >
                                            ×
                                        </button>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            <div style={{ marginTop: 6, fontSize: '0.73rem', color: '#9ca3af' }}>
                Click any locality to edit inline · Enter to confirm · Esc to cancel
            </div>

            {/* Raw JSON accordion */}
            <div style={{ marginTop: 14 }}>
                <button
                    onClick={() => setShowRaw(r => !r)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#6b7f76', fontSize: '0.76rem', padding: 0, display: 'flex', alignItems: 'center', gap: 5 }}
                >
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
                        style={{ transform: showRaw ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }}>
                        <polyline points="9 18 15 12 9 6" />
                    </svg>
                    Advanced: view / edit raw JSON
                </button>
                {showRaw && (
                    <textarea
                        className="form-input"
                        rows={10}
                        style={{ marginTop: 8, fontFamily: 'monospace', fontSize: '0.78rem' }}
                        value={JSON.stringify(stations, null, 2)}
                        onChange={e => {
                            try { onChange(JSON.parse(e.target.value)); } catch { /* ignore parse errors while typing */ }
                        }}
                    />
                )}
            </div>
        </div>
    );
}

// ─── Main page ─────────────────────────────────────────────────────────────────
export default function GeographyUploadPage() {
    const [constituencies, setConstituencies] = useState([]);
    const [pConst, setPConst]                 = useState('');
    const [assemblies, setAssemblies]         = useState([]);
    const [aSelection, setASelection]         = useState('');
    const [newAssembly, setNewAssembly]       = useState('');
    const [stations, setStations]             = useState(null); // null = not yet parsed
    const [savedPCs, setSavedPCs]             = useState([]);
    const [savedData, setSavedData]           = useState({});
    const [msg, setMsg]                       = useState({ type: '', text: '' });
    const [parsing, setParsing]               = useState(false);
    const [ocrProgress, setOcrProgress]       = useState(null);
    const [saving, setSaving]                 = useState(false);
    const [deleteTarget, setDeleteTarget]     = useState(null); // {pc, ac}
    const fileRef = useRef();

    useEffect(() => {
        apiGet('/api/admin/constituencies')
            .then(r => setConstituencies(r.constituencies || []))
            .catch(() => { });
        loadSavedFiles();
    }, []);

    useEffect(() => {
        if (!pConst) { setAssemblies([]); return; }
        apiGet(`/api/admin/geography/${encodeURIComponent(pConst)}/assemblies`)
            .then(r => setAssemblies(r.assemblies || []))
            .catch(() => { });
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

    // ── PDF parse ──────────────────────────────────────────────────────────────
    const handleParsePDF = async () => {
        const file = fileRef.current?.files?.[0];
        if (!file || !pConst || !aConst) return;
        setParsing(true);
        setOcrProgress(null);
        setMsg({});
        setStations(null);
        try {
            const r = await apiUpload('/api/admin/geography/upload-pdf', file);
            if (r.job_id) {
                showMsg('success', 'Hindi PDF detected — processing with AI OCR…');
                const extracted = await pollOcrJob(r.job_id);
                setStations(extracted);
                showMsg('success', `Extracted ${extracted.length} stations`);
            } else {
                const extracted = r.stations || [];
                setStations(extracted);
                showMsg('success', `Extracted ${extracted.length} stations`);
            }
        } catch (err) {
            showMsg('error', err.message);
        } finally {
            setParsing(false);
            setOcrProgress(null);
        }
    };

    const pollOcrJob = async (jobId) => {
        const INTERVAL = 5000;
        const MAX_WAIT = 15 * 60 * 1000;
        const start = Date.now();
        while (Date.now() - start < MAX_WAIT) {
            await new Promise(res => setTimeout(res, INTERVAL));
            try {
                const job = await apiGet(`/api/admin/geography/ocr-job/${jobId}`);
                if (job.progress) setOcrProgress(job.progress);
                if (job.status === 'done') return job.stations || [];
                if (job.status === 'error') throw new Error(job.error || 'OCR failed');
            } catch (err) {
                if (err.message?.includes('OCR failed')) throw err;
            }
        }
        throw new Error('OCR timed out after 15 minutes');
    };

    // ── Save ───────────────────────────────────────────────────────────────────
    const handleSave = async () => {
        if (!stations || stations.length === 0) return;
        setSaving(true);
        try {
            await apiPut(
                `/api/admin/geography/${encodeURIComponent(pConst)}/${encodeURIComponent(aConst)}`,
                { data: stations },
            );
            showMsg('success', 'Geography data saved successfully.');
            setStations(null);
            if (fileRef.current) fileRef.current.value = '';
            loadSavedFiles();
        } catch {
            showMsg('error', 'Save failed — please try again.');
        } finally {
            setSaving(false);
        }
    };

    // ── Delete ─────────────────────────────────────────────────────────────────
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
            {msg.text && (
                <div className={`toast ${msg.type === 'success' ? 'toast-success' : 'toast-error'}`}>
                    {msg.text}
                </div>
            )}

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

            {/* ── Upload form ────────────────────────────────────────────────── */}
            <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                <div className="section-title">Upload Polling Station Data</div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: '1rem' }}>
                    <div className="form-row" style={{ marginBottom: 0 }}>
                        <label className="form-label">Parliamentary Constituency</label>
                        <select
                            className="form-input"
                            value={pConst}
                            onChange={e => { setPConst(e.target.value); setASelection(''); }}
                        >
                            <option value="">Select…</option>
                            {constituencies.map(c => <option key={c} value={c}>{c}</option>)}
                        </select>
                    </div>
                    <div className="form-row" style={{ marginBottom: 0 }}>
                        <label className="form-label">Assembly Constituency</label>
                        {pConst ? (
                            <>
                                <select
                                    className="form-input"
                                    value={aSelection}
                                    onChange={e => setASelection(e.target.value)}
                                >
                                    <option value="">Select…</option>
                                    {assemblies.map(a => <option key={a} value={a}>{a}</option>)}
                                    <option value="__new__">+ Add New Assembly…</option>
                                </select>
                                {aSelection === '__new__' && (
                                    <input
                                        className="form-input"
                                        style={{ marginTop: 8 }}
                                        placeholder="e.g. Ghaziabad"
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
                    {parsing
                        ? (ocrProgress && ocrProgress.total_pages > 0
                            ? `AI OCR: ${ocrProgress.pages_done} / ${ocrProgress.total_pages} pages…`
                            : 'Parsing PDF…')
                        : 'Parse PDF'}
                </button>
            </div>

            {/* ── Review panel ───────────────────────────────────────────────── */}
            {stations !== null && (
                <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                        <div className="section-title" style={{ margin: 0 }}>
                            Review — {pConst} · {aConst}
                        </div>
                    </div>

                    <ReviewTable stations={stations} onChange={setStations} />

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 16 }}>
                        <button
                            className="btn-primary"
                            onClick={handleSave}
                            disabled={saving || stations.length === 0}
                        >
                            {saving ? 'Saving…' : 'Save to Database'}
                        </button>
                        <button
                            className="btn-secondary"
                            onClick={() => { setStations(null); if (fileRef.current) fileRef.current.value = ''; }}
                        >
                            Discard
                        </button>
                    </div>
                </div>
            )}

            <hr className="divider" />

            {/* ── Saved geography list ───────────────────────────────────────── */}
            <div className="section-title" style={{ marginBottom: '1rem' }}>Saved Geography Files</div>

            {savedPCs.length === 0 ? (
                <div className="glass-panel">
                    <div className="empty-state">
                        <div className="empty-state-icon">
                            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M3 6l9-4 9 4v12l-9 4-9-4V6z" /><path d="M12 2v20M3 6l9 4 9-4" />
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
                                        <path d="M3 6l9-4 9 4v12l-9 4-9-4V6z" />
                                    </svg>
                                    <span style={{ fontWeight: 600, fontSize: '0.88rem', color: '#1a2e28' }}>{pc}</span>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                    <span className="badge badge-slate">{(savedData[pc] || []).length} assemblies</span>
                                    <svg
                                        width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6b7f76" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                                        style={{ transform: savedData[`${pc}_open`] ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}
                                    >
                                        <polyline points="6 9 12 15 18 9" />
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
                                            <div style={{ display: 'flex', gap: 8 }}>
                                                <button
                                                    className="btn-secondary"
                                                    style={{ fontSize: '0.72rem', padding: '4px 10px' }}
                                                    onClick={async () => {
                                                        try {
                                                            const r = await apiGet(`/api/admin/geography/${encodeURIComponent(pc)}/${encodeURIComponent(ac)}`);
                                                            setStations(r.data || []);
                                                            setPConst(pc);
                                                            setASelection(ac);
                                                            window.scrollTo({ top: 0, behavior: 'smooth' });
                                                        } catch {
                                                            showMsg('error', 'Could not load geography data.');
                                                        }
                                                    }}
                                                >
                                                    Edit
                                                </button>
                                                <button
                                                    className="btn-danger"
                                                    style={{ fontSize: '0.72rem', padding: '4px 10px' }}
                                                    onClick={() => setDeleteTarget({ pc, ac })}
                                                >
                                                    Delete
                                                </button>
                                            </div>
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
