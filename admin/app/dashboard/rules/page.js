'use client';
import { useState, useEffect } from 'react';
import { apiGet, apiPut } from '@/lib/api';

export default function GeographyRulesPage() {
    const [mps, setMps] = useState([]);
    const [selectedTid, setSelectedTid] = useState('');
    const [overrides, setOverrides] = useState({});
    const [rules, setRules] = useState({});
    const [newLoc, setNewLoc] = useState('');
    const [newAC, setNewAC] = useState('');
    const [msg, setMsg] = useState({ type: '', text: '' });

    useEffect(() => {
        apiGet('/api/admin/mps').then(r => setMps((r.mps || []).filter(m => m.role === 'mp'))).catch(() => { });
        apiGet('/api/admin/overrides').then(setOverrides).catch(() => { });
    }, []);

    useEffect(() => {
        if (!selectedTid) { setRules({}); return; }
        const geoOverrides = overrides?.geo_overrides || {};
        setRules(geoOverrides[selectedTid] || {});
    }, [selectedTid, overrides]);

    const addRule = async () => {
        if (!newLoc || !newAC) return;
        const updated = { ...overrides };
        if (!updated.geo_overrides) updated.geo_overrides = {};
        if (!updated.geo_overrides[selectedTid]) updated.geo_overrides[selectedTid] = {};
        updated.geo_overrides[selectedTid][newLoc.trim().toLowerCase()] = newAC;
        try {
            await apiPut('/api/admin/overrides', { data: updated });
            setOverrides(updated);
            setRules(updated.geo_overrides[selectedTid]);
            setNewLoc('');
            setNewAC('');
            setMsg({ type: 'success', text: 'Rule added' });
        } catch (err) { setMsg({ type: 'error', text: err.message }); }
    };

    const deleteRule = async (loc) => {
        const updated = { ...overrides };
        if (updated.geo_overrides?.[selectedTid]) {
            delete updated.geo_overrides[selectedTid][loc];
            try {
                await apiPut('/api/admin/overrides', { data: updated });
                setOverrides(updated);
                setRules({ ...updated.geo_overrides[selectedTid] });
            } catch { }
        }
    };

    const mpList = mps.filter(m => m.role !== 'admin');

    return (
        <>
            <div className="section-title">Geography Override Rules (per MP)</div>

            {mpList.length === 0 ? (
                <div className="glass-panel" style={{ textAlign: 'center', color: '#6b7f76', padding: '2rem' }}>Create an MP first.</div>
            ) : (
                <>
                    <div style={{ marginBottom: '1.5rem' }}>
                        <label className="form-label">Select MP</label>
                        <select className="form-input" value={selectedTid} onChange={e => setSelectedTid(e.target.value)}>
                            <option value="">Choose an MP...</option>
                            {mpList.map(m => (
                                <option key={m.tenant_id} value={m.tenant_id}>
                                    {m.display_name} — {m.parliamentary_constituency} [ID {m.tenant_id}]
                                </option>
                            ))}
                        </select>
                    </div>

                    {selectedTid && (
                        <>
                            {/* Add Rule */}
                            <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                                <h3 style={{ color: '#1a2e28', fontSize: '1rem', fontWeight: 600, marginBottom: 12 }}>Add New Rule</h3>
                                <div style={{ display: 'grid', gridTemplateColumns: '2fr 2fr 1fr', gap: 12, alignItems: 'end' }}>
                                    <div>
                                        <label className="form-label">Location Input</label>
                                        <input className="form-input" placeholder="e.g. tilakwadi" value={newLoc} onChange={e => setNewLoc(e.target.value)} />
                                    </div>
                                    <div>
                                        <label className="form-label">Maps To (Assembly Constituency)</label>
                                        <input className="form-input" placeholder="e.g. Belgaum Dakshin" value={newAC} onChange={e => setNewAC(e.target.value)} />
                                    </div>
                                    <button className="btn-primary" onClick={addRule}>Add Rule</button>
                                </div>
                            </div>

                            {msg.text && (
                                <div style={{
                                    background: msg.type === 'success' ? 'rgba(5,150,105,0.06)' : 'rgba(220,38,38,0.06)',
                                    border: `1px solid ${msg.type === 'success' ? 'rgba(5,150,105,0.15)' : 'rgba(220,38,38,0.15)'}`,
                                    color: msg.type === 'success' ? '#059669' : '#dc2626',
                                    padding: '10px 14px', borderRadius: 10, fontSize: '0.82rem', marginBottom: '1rem',
                                }}>{msg.text}</div>
                            )}

                            {/* Rules Table */}
                            {Object.keys(rules).length > 0 ? (
                                <div className="glass-panel">
                                    <div style={{ marginBottom: 12, color: '#6b7f76', fontSize: '0.82rem', fontWeight: 500 }}>
                                        <strong>{Object.keys(rules).length}</strong> rules for this MP
                                    </div>
                                    <table className="data-table">
                                        <thead>
                                            <tr>
                                                <th>Location</th>
                                                <th>Assembly Constituency</th>
                                                <th style={{ width: 80 }}></th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {Object.entries(rules).map(([loc, ac]) => (
                                                <tr key={loc}>
                                                    <td>{loc}</td>
                                                    <td>{ac}</td>
                                                    <td>
                                                        <button className="btn-danger" style={{ fontSize: '0.72rem', padding: '4px 8px' }} onClick={() => deleteRule(loc)}>Remove</button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            ) : (
                                <div className="glass-panel" style={{ textAlign: 'center', color: '#6b7f76', padding: '1.5rem' }}>
                                    No rules defined for this MP yet.
                                </div>
                            )}
                        </>
                    )}
                </>
            )}
        </>
    );
}
