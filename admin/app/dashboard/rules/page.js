'use client';
import { useState, useEffect } from 'react';
import { apiGet, apiPut } from '@/lib/api';
import ConfirmModal from '@/components/ConfirmModal';

export default function GeographyRulesPage() {
    const [mps, setMps] = useState([]);
    const [selectedTid, setSelectedTid] = useState('');
    const [overrides, setOverrides] = useState({});
    const [rules, setRules] = useState({});
    const [newLoc, setNewLoc] = useState('');
    const [newAC, setNewAC] = useState('');
    const [msg, setMsg] = useState({ type: '', text: '' });
    const [deleteRuleTarget, setDeleteRuleTarget] = useState(null);

    useEffect(() => {
        apiGet('/api/admin/mps').then(r => setMps(r.mps || [])).catch(() => { });
        apiGet('/api/admin/overrides').then(setOverrides).catch(() => { });
    }, []);

    useEffect(() => {
        if (!selectedTid) { setRules({}); return; }
        const geoOverrides = overrides?.geo_overrides || {};
        setRules(geoOverrides[selectedTid] || {});
    }, [selectedTid, overrides]);

    const showMsg = (type, text) => {
        setMsg({ type, text });
        setTimeout(() => setMsg({ type: '', text: '' }), 4000);
    };

    const addRule = async () => {
        if (!newLoc || !newAC) return;
        const updated = { ...overrides };
        if (!updated.geo_overrides) updated.geo_overrides = {};
        if (!updated.geo_overrides[selectedTid]) updated.geo_overrides[selectedTid] = {};
        updated.geo_overrides[selectedTid][newLoc.trim().toLowerCase()] = newAC;
        try {
            await apiPut('/api/admin/overrides', { data: updated });
            setOverrides(updated);
            setRules({ ...updated.geo_overrides[selectedTid] });
            setNewLoc('');
            setNewAC('');
            showMsg('success', 'Rule added successfully.');
        } catch (err) { showMsg('error', err.message); }
    };

    const deleteRule = async (loc) => {
        setDeleteRuleTarget(loc);
    };

    const confirmDeleteRule = async () => {
        if (!deleteRuleTarget) return;
        const loc = deleteRuleTarget;
        setDeleteRuleTarget(null);
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
    const ruleEntries = Object.entries(rules);

    return (
        <>
            {msg.text && <div className={`toast ${msg.type === 'success' ? 'toast-success' : 'toast-error'}`}>{msg.text}</div>}

            {/* Delete Rule Modal */}
            {deleteRuleTarget && (
                <ConfirmModal
                    title={`Remove rule for "${deleteRuleTarget}"?`}
                    description="This location-to-assembly mapping will be deleted. Citizens mentioning this location will fall back to AI matching."
                    confirmLabel="Remove Rule"
                    variant="danger"
                    onConfirm={confirmDeleteRule}
                    onCancel={() => setDeleteRuleTarget(null)}
                />
            )}

            {mpList.length === 0 ? (
                <div className="glass-panel">
                    <div className="empty-state">
                        <div className="empty-state-icon">
                            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2V9M9 21H5a2 2 0 0 1-2-2V9m0 0h18"/>
                            </svg>
                        </div>
                        <div className="empty-state-title">No accounts registered</div>
                        <div className="empty-state-desc">Create an account first before configuring geography rules</div>
                    </div>
                </div>
            ) : (
                <>
                    <div className="form-row">
                        <label className="form-label">Select Account</label>
                        <select className="form-input" value={selectedTid} onChange={e => setSelectedTid(e.target.value)} style={{ maxWidth: 480 }}>
                            <option value="">Choose an account…</option>
                            {mpList.map(m => (
                                <option key={m.tenant_id} value={m.tenant_id}>
                                    {m.display_name} — {m.parliamentary_constituency}
                                </option>
                            ))}
                        </select>
                    </div>

                    {selectedTid && (
                        <>
                            {/* Add rule panel */}
                            <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                                <div className="section-title">Add Geography Override Rule</div>
                                <p style={{ color: '#6b7f76', fontSize: '0.8rem', marginTop: -8, marginBottom: '1rem' }}>
                                    Map a location string (as citizens type it) to the correct routing assembly or area for this account.
                                </p>
                                <div style={{ display: 'grid', gridTemplateColumns: '2fr 2fr auto', gap: 12, alignItems: 'flex-end' }}>
                                    <div>
                                        <label className="form-label">Location Input</label>
                                        <input
                                            className="form-input"
                                            placeholder="e.g. tilakwadi"
                                            value={newLoc}
                                            onChange={e => setNewLoc(e.target.value)}
                                            onKeyDown={e => e.key === 'Enter' && addRule()}
                                        />
                                    </div>
                                    <div>
                                        <label className="form-label">Maps to Assembly / Routing Area</label>
                                        <input
                                            className="form-input"
                                            placeholder="e.g. Belgaum Dakshin"
                                            value={newAC}
                                            onChange={e => setNewAC(e.target.value)}
                                            onKeyDown={e => e.key === 'Enter' && addRule()}
                                        />
                                    </div>
                                    <button
                                        className="btn-primary"
                                        onClick={addRule}
                                        disabled={!newLoc.trim() || !newAC.trim()}
                                        style={{ whiteSpace: 'nowrap' }}
                                    >
                                        Add Rule
                                    </button>
                                </div>
                            </div>

                            {/* Rules table */}
                            {ruleEntries.length > 0 ? (
                                <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
                                    <div style={{ padding: '12px 16px', borderBottom: '1px solid #e2ebe5', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                        <span style={{ fontSize: '0.82rem', color: '#6b7f76' }}>
                                            <strong style={{ color: '#1a2e28' }}>{ruleEntries.length}</strong> rule{ruleEntries.length !== 1 ? 's' : ''} configured
                                        </span>
                                    </div>
                                    <table className="data-table">
                                        <thead>
                                            <tr>
                                                <th>Location Input</th>
                                                <th>Assembly Constituency</th>
                                                <th style={{ width: 90, textAlign: 'right' }}></th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {ruleEntries.map(([loc, ac]) => (
                                                <tr key={loc}>
                                                    <td>
                                                        <code style={{ fontFamily: 'monospace', fontSize: '0.82rem', background: '#f0f4f1', padding: '2px 7px', borderRadius: 4 }}>{loc}</code>
                                                    </td>
                                                    <td style={{ color: '#1a2e28' }}>{ac}</td>
                                                    <td style={{ textAlign: 'right' }}>
                                                        <button
                                                            className="btn-danger"
                                                            style={{ fontSize: '0.72rem', padding: '4px 10px' }}
                                                            onClick={() => deleteRule(loc)}
                                                        >
                                                            Remove
                                                        </button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            ) : (
                                <div className="glass-panel">
                                    <div className="empty-state" style={{ padding: '1.5rem 0' }}>
                                        <div className="empty-state-title">No rules defined</div>
                                        <div className="empty-state-desc">Add a rule above to override location-to-assembly mapping for this account</div>
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </>
            )}
        </>
    );
}
