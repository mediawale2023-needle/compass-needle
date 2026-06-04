'use client';
import { useState, useEffect, useRef, useMemo } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { apiGet, apiPut, apiDelete, apiUpload, apiPatch } from '@/lib/api';
import ConfirmModal from '@/components/ConfirmModal';

const SEAT_TYPES = [
    { value: 'mp', label: 'MP Seat', pickerLabel: 'Parliamentary Seat' },
    { value: 'mla', label: 'MLA Seat', pickerLabel: 'Assembly Seat' },
];

function getSeatConfig(seatType) {
    return SEAT_TYPES.find((item) => item.value === seatType) || SEAT_TYPES[0];
}

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

// Institution-type keywords — mirrors Python _INST_KW_PAT in admin_api.py
const INST_KW_RE = /\b(?:Inter\s+College|Degree\s+College|Junior\s+High\s+School|Senior\s+Secondary\s+School|Higher\s+Secondary\s+School|High\s+School|Public\s+School|Bal\s+Mandir|Vidya\s+Mandir|Shiksha\s+Sadan|Shiksha\s+Niketan|Composite\s+Vidyalaya|Composite\s+Vidhyalaya|Prathmik\s+Vidyalaya|Primary\s+School|Vidyalaya|Vidhyalaya|School|College|Academy|Sadan|Niketan|Kendra|Banquet\s+Hall|Club\s+House|Club|Sthal|Hall|Office|Karyalay|Foundation|Center|Centre|Mandir|Bhavan|Bhawan|Panchayat\s+Ghar|Panchayat|Gram\s+Sabha)\b/gi;

// Strip "Room No X", Wing, and institution prefixes from a full polling station name
function cleanLocality(name) {
    if (!name) return name;
    let s = name;
    // Strip Room/Wing suffixes
    s = s.replace(/\s*,?\s*(?:(?:North|South|East|West)\s+)?Wing\s+Roo?m\s*(?:No\.?\s*)?\d+\S*/gi, '').trim();
    s = s.replace(/\s*,?\s*Roo?m\s*(?:No\.?\s*)?\d+\S*/gi, '').trim();
    s = s.replace(/\s+(?:North|South|East|West)\s+Wing/gi, '').trim();
    // Find the LAST institution keyword; everything after it is the locality
    let lastIdx = -1, lastLen = 0;
    const re = new RegExp(INST_KW_RE.source, 'gi');
    let m;
    while ((m = re.exec(s)) !== null) { lastIdx = m.index; lastLen = m[0].length; }
    if (lastIdx >= 0) {
        const after = s.slice(lastIdx + lastLen).replace(/^[\s,(\-]+/, '').trim();
        if (after.length > 2) return after;
    }
    return s;
}

function applyClean(stations) {
    return stations.map(s => ({ ...s, locality: cleanLocality(s.locality || '') || s.locality }));
}

// Locality may still contain a building/institution name — flag it for review
const FLAG_PAT = /\b(?:School|College|Vidyalaya|Vidhyalaya|Academy|Sadan|Niketan|Kendra|Hall|Office|Karyalay|Mandir|Bhavan|Bhawan|Panchayat|Room\s*No)\b/i;

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
                    onClick={() => onChange(applyClean(stations))}
                    className="btn-secondary"
                    style={{ fontSize: '0.77rem', padding: '7px 12px', whiteSpace: 'nowrap' }}
                    title="Strip Room No, school/college/vidyalaya prefixes from all localities"
                >
                    ✦ Auto-clean
                </button>
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
    const router = useRouter();
    const searchParams = useSearchParams();
    const tenantId = searchParams.get('tenant_id');
    const [tenantOptions, setTenantOptions]   = useState([]);
    const [tenantPickerId, setTenantPickerId] = useState('');
    const [constituencies, setConstituencies] = useState([]);
    const [seatType, setSeatType]             = useState('mp');
    const [pConst, setPConst]                 = useState('');
    const [assemblies, setAssemblies]         = useState([]);
    const [aSelection, setASelection]         = useState('');
    const [newAssembly, setNewAssembly]       = useState('');
    const [stations, setStations]             = useState(null); // null = not yet parsed
    const [savedSeats, setSavedSeats]         = useState([]);
    const [savedData, setSavedData]           = useState({});
    const [msg, setMsg]                       = useState({ type: '', text: '' });
    const [parsing, setParsing]               = useState(false);
    const [ocrProgress, setOcrProgress]       = useState(null);
    const [saving, setSaving]                 = useState(false);
    const [validationReport, setValidationReport] = useState(null);
    const [deleteTarget, setDeleteTarget]     = useState(null); // {seatType, pc, ac}
    const [geoAliases, setGeoAliases]         = useState([]);
    const [geoAliasLoading, setGeoAliasLoading] = useState(false);
    const [geoAliasQuery, setGeoAliasQuery]   = useState('');
    const [geoAliasDeleteTarget, setGeoAliasDeleteTarget] = useState(null);
    const [overrides, setOverrides]           = useState({});
    const [manualRules, setManualRules]       = useState({});
    const [manualRuleInput, setManualRuleInput] = useState('');
    const [manualRuleAssembly, setManualRuleAssembly] = useState('');
    const [manualRuleBulkInput, setManualRuleBulkInput] = useState('');
    const [manualRuleBulkMode, setManualRuleBulkMode] = useState(false);
    const [manualRulesLoading, setManualRulesLoading] = useState(false);
    const [manualRuleDeleteTarget, setManualRuleDeleteTarget] = useState(null);
    const [manualRuleDeleteAllTarget, setManualRuleDeleteAllTarget] = useState(false);
    const [manualRuleEditingKey, setManualRuleEditingKey] = useState(null);
    const [tenantContext, setTenantContext]   = useState(null);
    const [tenantLoading, setTenantLoading]   = useState(false);
    const [reuseSeatName, setReuseSeatName]   = useState('');
    const [linkingSeat, setLinkingSeat]       = useState(false);
    const fileRef = useRef();
    const seatConfig = getSeatConfig(seatType);
    const assemblyLabel = seatType === 'mla' ? 'Routing Group / Area' : 'Assembly Constituency';

    useEffect(() => {
        apiGet('/api/admin/constituencies')
            .then(r => setConstituencies(r.constituencies || []))
            .catch(() => { });
        apiGet('/api/admin/mps')
            .then((r) => {
                const options = (r.mps || []).map((item) => ({
                    tenantId: String(item.tenant_id),
                    label: item.display_name || item.mp_name || item.username || `Tenant ${item.tenant_id}`,
                    constituency: item.parliamentary_constituency || item.profile?.constituency || '',
                    seatLabel: item.seat_label || '',
                }));
                setTenantOptions(options);
            })
            .catch(() => { });
        apiGet('/api/admin/overrides')
            .then((response) => setOverrides(response || {}))
            .catch(() => { });
        loadSavedFiles();
    }, []);

    useEffect(() => {
        if (!tenantId) {
            setTenantContext(null);
            setGeoAliases([]);
            setManualRules({});
            return;
        }
        setTenantLoading(true);
        apiGet(`/api/admin/mps/${tenantId}/detail`)
            .then((detail) => {
                const profile = detail?.profile || {};
                const nextSeatType = profile.seat_type || detail?.seat_type || 'mp';
                const nextSeatName = profile.constituency || '';
                setTenantPickerId(String(tenantId));
                setTenantContext({
                    tenantId: String(tenantId),
                    displayName: profile.mp_name || 'Account',
                    constituency: nextSeatName,
                    seatType: nextSeatType,
                    seatLabel: profile.seat_label || detail?.seat_label || getSeatConfig(nextSeatType).label,
                });
                setSeatType(nextSeatType);
                setPConst(nextSeatName);
                setASelection('');
                setNewAssembly('');
                setReuseSeatName(nextSeatName);
            })
            .catch(() => {
                setTenantContext(null);
            })
            .finally(() => setTenantLoading(false));
    }, [tenantId]);

    useEffect(() => {
        if (tenantId) return;
        setTenantPickerId('');
    }, [tenantId]);

    useEffect(() => {
        if (!tenantId) return;
        loadGeoAliases(tenantId);
    }, [tenantId]);

    useEffect(() => {
        if (!tenantId) return;
        const geoOverrides = overrides?.geo_overrides || {};
        setManualRules(geoOverrides[String(tenantId)] || {});
    }, [tenantId, overrides]);

    useEffect(() => {
        if (!pConst) { setAssemblies([]); return; }
        apiGet(`/api/admin/geography/${encodeURIComponent(pConst)}/assemblies?seat_type=${seatType}`)
            .then(r => setAssemblies(r.assemblies || []))
            .catch(() => { });
    }, [pConst, seatType]);

    useEffect(() => {
        if (!tenantContext) return;
        if (!reuseSeatName && tenantContext.constituency) {
            setReuseSeatName(tenantContext.constituency);
        }
    }, [tenantContext, reuseSeatName]);

    const loadSavedFiles = async () => {
        try {
            const responses = await Promise.all(
                SEAT_TYPES.map(async ({ value }) => {
                    const r = await apiGet(`/api/admin/geography/parliamentary?seat_type=${value}`);
                    return {
                        seatType: value,
                        seatNames: r.parliamentary_constituencies || [],
                    };
                }),
            );
            const seats = [];
            const data = {};
            for (const response of responses) {
                for (const seatName of response.seatNames) {
                    const key = `${response.seatType}:${seatName}`;
                    const ar = await apiGet(`/api/admin/geography/${encodeURIComponent(seatName)}/assemblies?seat_type=${response.seatType}`);
                    data[key] = ar.assemblies || [];
                    seats.push({ seatType: response.seatType, seatName });
                }
            }
            setSavedSeats(seats);
            setSavedData(data);
        } catch { }
    };

    const handleTenantPickerOpen = () => {
        if (!tenantPickerId) return;
        router.push(`/dashboard/shared-geography/workspace?tenant_id=${encodeURIComponent(tenantPickerId)}`);
    };

    const loadGeoAliases = async (tenant) => {
        if (!tenant) return;
        setGeoAliasLoading(true);
        try {
            const response = await apiGet(`/api/admin/mps/${tenant}/geo-aliases`);
            setGeoAliases(response.items || []);
        } catch {
            setGeoAliases([]);
        } finally {
            setGeoAliasLoading(false);
        }
    };

    const persistManualRules = async (nextRules) => {
        const tenantKey = String(tenantId);
        const updated = { ...(overrides || {}) };
        if (!updated.geo_overrides) updated.geo_overrides = {};
        if (Object.keys(nextRules).length === 0) {
            delete updated.geo_overrides[tenantKey];
        } else {
            updated.geo_overrides[tenantKey] = nextRules;
        }
        setManualRulesLoading(true);
        try {
            await apiPut('/api/admin/overrides', { data: updated });
            setOverrides(updated);
            setManualRules(nextRules);
            return true;
        } catch (err) {
            showMsg('error', err.message || 'Could not save manual geography correction.');
            return false;
        } finally {
            setManualRulesLoading(false);
        }
    };

    const addManualRule = async () => {
        if (!tenantId) return;
        const nextKey = manualRuleInput.trim().toLowerCase();
        const nextAssembly = manualRuleAssembly.trim();
        if (!nextKey || !nextAssembly) return;
        const nextRules = { ...manualRules };
        if (manualRuleEditingKey && manualRuleEditingKey !== nextKey) {
            delete nextRules[manualRuleEditingKey];
        }
        nextRules[nextKey] = nextAssembly;
        const success = await persistManualRules(nextRules);
        if (!success) return;
        setManualRuleInput('');
        setManualRuleAssembly('');
        setManualRuleEditingKey(null);
        showMsg('success', manualRuleEditingKey
            ? `Updated manual correction for "${nextKey}".`
            : `Saved manual correction for "${nextKey}".`);
    };

    const startManualRuleEdit = (loc, ac) => {
        setManualRuleEditingKey(loc);
        setManualRuleInput(loc);
        setManualRuleAssembly(ac);
    };

    const cancelManualRuleEdit = () => {
        setManualRuleEditingKey(null);
        setManualRuleInput('');
        setManualRuleAssembly('');
    };

    const parseBulkManualRules = () => {
        const entries = [];
        const errors = [];
        manualRuleBulkInput
            .split('\n')
            .map((line) => line.trim())
            .filter(Boolean)
            .forEach((line, index) => {
                const parts = line.split(/\s*=>\s*/);
                if (parts.length !== 2 || !parts[0]?.trim() || !parts[1]?.trim()) {
                    errors.push(`Line ${index + 1}`);
                    return;
                }
                entries.push({
                    key: parts[0].trim().toLowerCase(),
                    value: parts[1].trim(),
                });
            });
        return { entries, errors };
    };

    const saveBulkManualRules = async () => {
        if (!tenantId) return;
        const { entries, errors } = parseBulkManualRules();
        if (errors.length) {
            showMsg('error', `Bulk format error on ${errors.join(', ')}. Use "alias => assembly" on each line.`);
            return;
        }
        if (!entries.length) {
            showMsg('error', 'Add at least one correction line before saving.');
            return;
        }
        const nextRules = { ...manualRules };
        entries.forEach(({ key, value }) => {
            nextRules[key] = value;
        });
        const success = await persistManualRules(nextRules);
        if (!success) return;
        setManualRuleBulkInput('');
        setManualRuleBulkMode(false);
        showMsg('success', `Saved ${entries.length} manual correction${entries.length === 1 ? '' : 's'}.`);
    };

    const showMsg = (type, text) => {
        setMsg({ type, text });
        setTimeout(() => setMsg({ type: '', text: '' }), 4000);
    };

    const aConst = aSelection === '__new__' ? newAssembly : aSelection;
    const seatHasSavedGeography = !!(savedData[`${seatType}:${pConst}`] || []).length;
    const savedSeatsForCurrentType = savedSeats.filter(({ seatType: currentSeatType }) => currentSeatType === seatType);
    const selectedReuseBlockCount = (savedData[`${seatType}:${reuseSeatName}`] || []).length;

    const handleReuseExistingSeat = async () => {
        if (!tenantContext?.tenantId) return;
        if (!reuseSeatName) {
            showMsg('error', 'Select a saved seat first.');
            return;
        }
        setLinkingSeat(true);
        try {
            if (reuseSeatName !== tenantContext.constituency) {
                await apiPatch(`/api/admin/mps/${tenantContext.tenantId}/constituency`, { constituency: reuseSeatName });
                setTenantContext((prev) => prev ? { ...prev, constituency: reuseSeatName } : prev);
                setPConst(reuseSeatName);
            }
            setSeatType(tenantContext.seatType);
            showMsg('success', reuseSeatName === tenantContext.constituency
                ? `Using existing shared geography for ${reuseSeatName}. No upload needed.`
                : `Linked this account to existing shared geography for ${reuseSeatName}.`);
        } catch (err) {
            showMsg('error', err.message || 'Could not link existing geography.');
        } finally {
            setLinkingSeat(false);
        }
    };

    // ── PDF parse ──────────────────────────────────────────────────────────────
    const handleParsePDF = async () => {
        const file = fileRef.current?.files?.[0];
        if (!file || !pConst || !aConst) return;
        setParsing(true);
        setOcrProgress(null);
        setMsg({});
        setStations(null);
        setValidationReport(null);
        try {
            const r = await apiUpload('/api/admin/geography/upload-pdf', file);
            if (r.job_id) {
                showMsg('success', 'Hindi PDF detected — processing with AI OCR…');
                const job = await pollOcrJob(r.job_id);
                const extracted = applyClean(job.stations || []);
                setStations(extracted);
                setValidationReport(job.validation || null);
                showMsg('success', `Extracted ${extracted.length} stations`);
            } else {
                const extracted = applyClean(r.stations || []);
                setStations(extracted);
                setValidationReport(r.validation || null);
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
                if (job.status === 'done') return job;
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
            const r = await apiPut(
                `/api/admin/geography/${encodeURIComponent(pConst)}/${encodeURIComponent(aConst)}?seat_type=${seatType}`,
                { data: stations },
            );
            setValidationReport(r.validation || null);
            const ambiguityCount = Object.keys(r.validation?.ambiguous_localities_against_constituency || {}).length;
            const removedCount = r.validation?.meta_rows_removed || 0;
            const suffix = ambiguityCount || removedCount
                ? ` Removed ${removedCount} meta rows; flagged ${ambiguityCount} ambiguous localities.`
                : '';
            showMsg('success', `Geography data saved successfully.${suffix}`);
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
        const { seatType: deleteSeatType, pc, ac } = deleteTarget;
        setDeleteTarget(null);
        try {
            await apiDelete(`/api/admin/geography/${encodeURIComponent(pc)}/${encodeURIComponent(ac)}?seat_type=${deleteSeatType}`);
            loadSavedFiles();
        } catch { }
    };

    const confirmGeoAliasDelete = async () => {
        if (!geoAliasDeleteTarget || !tenantId) return;
        const target = geoAliasDeleteTarget;
        setGeoAliasDeleteTarget(null);
        try {
            await apiDelete(`/api/admin/mps/${tenantId}/geo-aliases/${target.id}`);
            setGeoAliases((current) => current.filter((item) => item.id !== target.id));
            showMsg('success', `Deleted geo alias "${target.key}".`);
        } catch (err) {
            showMsg('error', err.message || 'Could not delete geo alias.');
        }
    };

    const confirmManualRuleDelete = async () => {
        if (!manualRuleDeleteTarget) return;
        const target = manualRuleDeleteTarget;
        setManualRuleDeleteTarget(null);
        const nextRules = { ...manualRules };
        delete nextRules[target];
        const success = await persistManualRules(nextRules);
        if (success) {
            if (manualRuleEditingKey === target) {
                cancelManualRuleEdit();
            }
            showMsg('success', `Removed manual correction for "${target}".`);
        }
    };

    const confirmManualRuleDeleteAll = async () => {
        setManualRuleDeleteAllTarget(false);
        const success = await persistManualRules({});
        if (success) {
            cancelManualRuleEdit();
            setManualRuleBulkInput('');
            setManualRuleBulkMode(false);
            showMsg('success', 'Removed all manual corrections for this tenant.');
        }
    };

    const filteredGeoAliases = geoAliases.filter((item) => {
        const needle = geoAliasQuery.trim().toLowerCase();
        if (!needle) return true;
        return [
            item.key,
            item.display,
            item.assembly,
            item.canonical_locality,
            item.source,
        ].some((value) => (value || '').toLowerCase().includes(needle));
    });
    const manualRuleEntries = Object.entries(manualRules).sort((a, b) => a[0].localeCompare(b[0]));

    return (
        <>
            {msg.text && (
                <div className={`toast ${msg.type === 'success' ? 'toast-success' : 'toast-error'}`}>
                    {msg.text}
                </div>
            )}

            {deleteTarget && (
                <ConfirmModal
                    title={`Delete geography block "${deleteTarget.ac}"?`}
                    description={`This will remove all polling station data for "${deleteTarget.ac}" from the ${getSeatConfig(deleteTarget.seatType).label.toLowerCase()} "${deleteTarget.pc}". This action cannot be undone.`}
                    confirmLabel="Delete"
                    variant="danger"
                    onConfirm={confirmDelete}
                    onCancel={() => setDeleteTarget(null)}
                />
            )}

            {geoAliasDeleteTarget && (
                <ConfirmModal
                    title={`Delete alias "${geoAliasDeleteTarget.key}"?`}
                    description={`This will remove the resolver alias for tenant ${tenantId}. If alias generation runs again later, the row may return unless the underlying geography data or generator rules are also corrected.`}
                    confirmLabel="Delete Alias"
                    variant="danger"
                    onConfirm={confirmGeoAliasDelete}
                    onCancel={() => setGeoAliasDeleteTarget(null)}
                />
            )}

            {manualRuleDeleteTarget && (
                <ConfirmModal
                    title={`Remove manual correction for "${manualRuleDeleteTarget}"?`}
                    description="This tenant-specific correction will be deleted. Matching will fall back to the shared seat geography and generated resolver index."
                    confirmLabel="Remove Correction"
                    variant="danger"
                    onConfirm={confirmManualRuleDelete}
                    onCancel={() => setManualRuleDeleteTarget(null)}
                />
            )}

            {manualRuleDeleteAllTarget && (
                <ConfirmModal
                    title="Remove all manual corrections?"
                    description="This will delete every tenant-specific manual correction for this account. Matching will fall back to shared seat geography and generated resolver aliases."
                    confirmLabel="Delete All"
                    variant="danger"
                    onConfirm={confirmManualRuleDeleteAll}
                    onCancel={() => setManualRuleDeleteAllTarget(false)}
                />
            )}

            {tenantId && (
                <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, marginBottom: 10, flexWrap: 'wrap' }}>
                        <div>
                            <div className="section-title" style={{ marginBottom: 6 }}>Tenant Geography Setup</div>
                            <p style={{ color: '#6b7f76', fontSize: '0.82rem', margin: 0 }}>
                                Choose an existing shared seat geography or upload a new one for this account.
                            </p>
                        </div>
                        <Link
                            href={`/dashboard/mps/${tenantId}/setup`}
                            className="btn-ghost"
                            style={{ textDecoration: 'none', fontSize: '0.74rem', flexShrink: 0 }}
                        >
                            Back to launch readiness
                        </Link>
                    </div>

                    {tenantLoading ? (
                        <div style={{ color: '#6b7f76', fontSize: '0.8rem' }}>Loading tenant seat…</div>
                    ) : tenantContext ? (
                        <>
                            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
                                <span className="badge badge-slate">{tenantContext.displayName}</span>
                                <span className={`badge ${tenantContext.seatType === 'mla' ? 'badge-red' : 'badge-green'}`}>{tenantContext.seatLabel}</span>
                                <span className="badge badge-slate">{tenantContext.constituency || 'No constituency set'}</span>
                                <span className={`badge badge-dot ${seatHasSavedGeography ? 'badge-green' : 'badge-amber'}`}>
                                    {seatHasSavedGeography ? 'Shared geography already present' : 'No shared geography yet'}
                                </span>
                                <span className="badge badge-slate">{manualRuleEntries.length} manual correction{manualRuleEntries.length === 1 ? '' : 's'}</span>
                                <span className="badge badge-amber">{geoAliases.length} generated alias{geoAliases.length === 1 ? '' : 'es'}</span>
                            </div>

                            <div style={{
                                display: 'grid',
                                gridTemplateColumns: 'minmax(240px, 1.15fr) minmax(280px, 1.6fr)',
                                gap: 16,
                                alignItems: 'start',
                            }}>
                                <div style={{
                                    border: '1px solid #e2ebe5',
                                    borderRadius: 12,
                                    padding: '14px 16px',
                                    background: '#f8fbf9',
                                }}>
                                    <div style={{ fontWeight: 700, fontSize: '0.84rem', color: '#1a2e28', marginBottom: 6 }}>
                                        Option 1: Use Existing Shared Geography
                                    </div>
                                    <div style={{ color: '#6b7f76', fontSize: '0.78rem', lineHeight: 1.5, marginBottom: 12 }}>
                                        If this seat already exists because of a rival or another account, just select it here.
                                        Shared geography will apply immediately.
                                    </div>
                                    <label className="form-label">Saved {tenantContext.seatType === 'mla' ? 'MLA' : 'MP'} constituency</label>
                                    <select
                                        className="form-input"
                                        value={reuseSeatName}
                                        onChange={(e) => setReuseSeatName(e.target.value)}
                                    >
                                        <option value="">Select existing seat…</option>
                                        {savedSeatsForCurrentType.map(({ seatName }) => (
                                            <option key={`${tenantContext.seatType}:${seatName}`} value={seatName}>{seatName}</option>
                                        ))}
                                    </select>
                                    <div style={{ color: '#6b7f76', fontSize: '0.75rem', marginTop: 8, minHeight: 18 }}>
                                        {reuseSeatName
                                            ? `${selectedReuseBlockCount} routing block${selectedReuseBlockCount === 1 ? '' : 's'} available for ${reuseSeatName}.`
                                            : 'Choose a saved seat to reuse its shared geography.'}
                                    </div>
                                    <button
                                        className="btn-primary"
                                        style={{ marginTop: 12, width: '100%' }}
                                        disabled={!reuseSeatName || linkingSeat}
                                        onClick={handleReuseExistingSeat}
                                    >
                                        {linkingSeat ? 'Linking…' : reuseSeatName && reuseSeatName !== tenantContext.constituency ? 'Use selected seat geography' : 'Use existing geography'}
                                    </button>
                                </div>

                                <div style={{
                                    border: '1px solid #e2ebe5',
                                    borderRadius: 12,
                                    padding: '14px 16px',
                                    background: '#fff',
                                }}>
                                    <div style={{ fontWeight: 700, fontSize: '0.84rem', color: '#1a2e28', marginBottom: 6 }}>
                                        Option 2: Upload New Shared Geography
                                    </div>
                                    <div style={{ color: '#6b7f76', fontSize: '0.78rem', lineHeight: 1.5 }}>
                                        Use the upload form below if this seat has no saved geography yet, or if you want to replace the shared base dataset with a newer Election Commission PDF.
                                    </div>
                                </div>
                            </div>
                        </>
                    ) : (
                        <div style={{ color: '#9a3412', fontSize: '0.8rem' }}>
                            Could not load tenant details for this geography setup flow.
                        </div>
                    )}
                </div>
            )}

            {tenantId && (
                <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14 }}>
                        <div style={{ border: '1px solid #e2ebe5', borderRadius: 12, padding: '14px 16px', background: '#fff' }}>
                            <div className="section-title" style={{ marginBottom: 6 }}>1. Shared Seat Geography</div>
                            <div style={{ color: '#6b7f76', fontSize: '0.78rem', lineHeight: 1.5 }}>
                                Canonical parent-locality and sub-locality data for this seat. Upload and maintain it once, then reuse it safely across same-seat accounts.
                            </div>
                        </div>
                        <div style={{ border: '1px solid #e2ebe5', borderRadius: 12, padding: '14px 16px', background: '#fff' }}>
                            <div className="section-title" style={{ marginBottom: 6 }}>2. Manual Matching Corrections</div>
                            <div style={{ color: '#6b7f76', fontSize: '0.78rem', lineHeight: 1.5 }}>
                                Use only when citizens repeatedly type a nickname, shorthand, or misspelling that the shared geography cannot resolve cleanly on its own.
                            </div>
                        </div>
                        <div style={{ border: '1px solid #e2ebe5', borderRadius: 12, padding: '14px 16px', background: '#fff' }}>
                            <div className="section-title" style={{ marginBottom: 6 }}>3. Generated Resolver Aliases</div>
                            <div style={{ color: '#6b7f76', fontSize: '0.78rem', lineHeight: 1.5 }}>
                                These are internal helper forms built by the system from geography data. Keep them as a debug tool, not the main place to manage geography.
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {tenantId && (
                <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, marginBottom: 10, flexWrap: 'wrap' }}>
                        <div>
                            <div className="section-title" style={{ marginBottom: 6 }}>Manual Matching Corrections</div>
                            <p style={{ color: '#6b7f76', fontSize: '0.82rem', margin: 0 }}>
                                Keep tenant-specific corrections here when real-world citizen wording needs a manual bridge into the shared parent/sub-locality geography.
                            </p>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                            <span className="badge badge-slate">{manualRuleEntries.length} total</span>
                            <button
                                className={manualRuleBulkMode ? 'btn-primary' : 'btn-secondary'}
                                style={{ fontSize: '0.72rem', padding: '4px 10px' }}
                                disabled={manualRulesLoading}
                                onClick={() => {
                                    setManualRuleBulkMode((current) => !current);
                                    cancelManualRuleEdit();
                                }}
                            >
                                {manualRuleBulkMode ? 'Single Add' : 'Bulk Add'}
                            </button>
                            <button
                                className="btn-danger"
                                style={{ fontSize: '0.72rem', padding: '4px 10px' }}
                                disabled={manualRulesLoading || manualRuleEntries.length === 0}
                                onClick={() => setManualRuleDeleteAllTarget(true)}
                            >
                                Delete All
                            </button>
                        </div>
                    </div>

                    {manualRuleBulkMode ? (
                        <div style={{ marginBottom: 14 }}>
                            <label className="form-label" htmlFor="manual-correction-bulk-input">Bulk corrections</label>
                            <textarea
                                id="manual-correction-bulk-input"
                                className="form-input"
                                rows={8}
                                placeholder={`teacher colony => ${seatType === 'mla' ? 'North Zone' : 'Belgaum South'}\nteachers colony khasbag => ${seatType === 'mla' ? 'North Zone' : 'Belgaum South'}`}
                                value={manualRuleBulkInput}
                                onChange={(e) => setManualRuleBulkInput(e.target.value)}
                                style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}
                            />
                            <div style={{ color: '#6b7f76', fontSize: '0.76rem', marginTop: 8, marginBottom: 12 }}>
                                Add one correction per line using the format <code style={{ fontFamily: 'monospace' }}>alias =&gt; assembly</code>.
                            </div>
                            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                                <button
                                    className="btn-primary"
                                    disabled={!manualRuleBulkInput.trim() || manualRulesLoading}
                                    onClick={saveBulkManualRules}
                                >
                                    {manualRulesLoading ? 'Saving…' : 'Save Bulk Corrections'}
                                </button>
                                <button
                                    className="btn-secondary"
                                    disabled={manualRulesLoading}
                                    onClick={() => setManualRuleBulkInput('')}
                                >
                                    Clear
                                </button>
                            </div>
                        </div>
                    ) : (
                        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(220px, 2fr) minmax(220px, 2fr) auto', gap: 12, alignItems: 'end', marginBottom: 14 }}>
                            <div>
                                <label className="form-label" htmlFor="manual-correction-input">Citizen wording / alias</label>
                                <input
                                    id="manual-correction-input"
                                    className="form-input"
                                    placeholder="e.g. teacher colony"
                                    value={manualRuleInput}
                                    onChange={(e) => setManualRuleInput(e.target.value)}
                                    onKeyDown={(e) => e.key === 'Enter' && addManualRule()}
                                />
                            </div>
                            <div>
                                <label className="form-label" htmlFor="manual-correction-target">Maps to assembly / routing area</label>
                                <input
                                    id="manual-correction-target"
                                    className="form-input"
                                    placeholder={seatType === 'mla' ? 'e.g. North Zone' : 'e.g. Belgaum South'}
                                    value={manualRuleAssembly}
                                    onChange={(e) => setManualRuleAssembly(e.target.value)}
                                    onKeyDown={(e) => e.key === 'Enter' && addManualRule()}
                                />
                            </div>
                            <button
                                className="btn-primary"
                                disabled={!manualRuleInput.trim() || !manualRuleAssembly.trim() || manualRulesLoading}
                                onClick={addManualRule}
                                style={{ whiteSpace: 'nowrap' }}
                            >
                                {manualRulesLoading ? 'Saving…' : manualRuleEditingKey ? 'Update Correction' : 'Save Correction'}
                            </button>
                        </div>
                    )}

                    {manualRuleEditingKey && !manualRuleBulkMode && (
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 14, padding: '10px 12px', border: '1px solid #e2ebe5', borderRadius: 10, background: '#f8fbf9' }}>
                            <div style={{ color: '#6b7f76', fontSize: '0.78rem' }}>
                                Editing manual correction for <code style={{ fontFamily: 'monospace', fontSize: '0.76rem' }}>{manualRuleEditingKey}</code>
                            </div>
                            <button
                                className="btn-secondary"
                                style={{ fontSize: '0.72rem', padding: '4px 10px' }}
                                disabled={manualRulesLoading}
                                onClick={cancelManualRuleEdit}
                            >
                                Cancel
                            </button>
                        </div>
                    )}

                    {manualRuleEntries.length > 0 ? (
                        <div style={{ border: '1px solid #e2ebe5', borderRadius: 12, overflow: 'hidden' }}>
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Citizen wording</th>
                                        <th>Maps to assembly / routing area</th>
                                        <th style={{ width: 180, textAlign: 'right' }}></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {manualRuleEntries.map(([loc, ac]) => (
                                        <tr key={loc}>
                                            <td>
                                                <code style={{ fontFamily: 'monospace', fontSize: '0.82rem', background: '#f0f4f1', padding: '2px 7px', borderRadius: 4 }}>{loc}</code>
                                            </td>
                                            <td style={{ color: '#1a2e28' }}>{ac}</td>
                                            <td style={{ textAlign: 'right' }}>
                                                <button
                                                    className="btn-secondary"
                                                    style={{ fontSize: '0.72rem', padding: '4px 10px', marginRight: 8 }}
                                                    disabled={manualRulesLoading}
                                                    onClick={() => startManualRuleEdit(loc, ac)}
                                                >
                                                    Edit
                                                </button>
                                                <button
                                                    className="btn-danger"
                                                    style={{ fontSize: '0.72rem', padding: '4px 10px' }}
                                                    disabled={manualRulesLoading}
                                                    onClick={() => setManualRuleDeleteTarget(loc)}
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
                        <div style={{ border: '1px solid #e2ebe5', borderRadius: 12, padding: '18px 16px', color: '#6b7f76', fontSize: '0.8rem' }}>
                            No manual corrections yet. Prefer the shared seat geography first; add a correction here only when citizen wording truly needs a tenant-specific bridge.
                        </div>
                    )}
                </div>
            )}

            {!tenantId && (
                <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                    <div className="section-title" style={{ marginBottom: 8 }}>Tenant Alias Cleanup</div>
                    <p style={{ color: '#6b7f76', fontSize: '0.82rem', marginTop: 0, marginBottom: 14 }}>
                        Resolver alias inspection is tenant-scoped. Pick an account here to open the workspace in tenant-aware mode and inspect `geo_alias` rows safely.
                    </p>
                    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(220px, 1.5fr) auto', gap: 12, alignItems: 'end' }}>
                        <div className="form-row" style={{ marginBottom: 0 }}>
                            <label className="form-label" htmlFor="tenant-alias-workspace-picker">Account / Tenant</label>
                            <select
                                id="tenant-alias-workspace-picker"
                                className="form-input"
                                value={tenantPickerId}
                                onChange={(e) => setTenantPickerId(e.target.value)}
                            >
                                <option value="">Select account…</option>
                                {tenantOptions.map((option) => (
                                    <option key={option.tenantId} value={option.tenantId}>
                                        {option.label}{option.constituency ? ` · ${option.constituency}` : ''}{option.seatLabel ? ` · ${option.seatLabel}` : ''}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <button
                            className="btn-primary"
                            style={{ minWidth: 180 }}
                            disabled={!tenantPickerId}
                            onClick={handleTenantPickerOpen}
                        >
                            Open Tenant Workspace
                        </button>
                    </div>
                </div>
            )}

            {tenantId && (
                <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, marginBottom: 10, flexWrap: 'wrap' }}>
                        <div>
                            <div className="section-title" style={{ marginBottom: 6 }}>Resolver Aliases</div>
                            <p style={{ color: '#6b7f76', fontSize: '0.82rem', margin: 0 }}>
                                Inspect and delete tenant-scoped `geo_alias` rows that can short-circuit normal geography matching.
                            </p>
                        </div>
                        <button
                            className="btn-secondary"
                            style={{ fontSize: '0.74rem' }}
                            onClick={() => loadGeoAliases(tenantId)}
                            disabled={geoAliasLoading}
                        >
                            {geoAliasLoading ? 'Refreshing…' : 'Refresh aliases'}
                        </button>
                    </div>

                    <div style={{ color: '#9a3412', fontSize: '0.76rem', lineHeight: 1.5, marginBottom: 12 }}>
                        Deleting an alias takes effect immediately for tenant-scoped resolver lookups, but generated aliases may return after future geography regeneration unless the underlying geography data or alias-generation rules are fixed too.
                    </div>

                    <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12 }}>
                        <input
                            className="form-input"
                            style={{ flex: 1, minWidth: 220, marginBottom: 0 }}
                            placeholder="Search alias key, display, canonical locality, or assembly…"
                            value={geoAliasQuery}
                            onChange={(e) => setGeoAliasQuery(e.target.value)}
                        />
                        <span className="badge badge-slate">{filteredGeoAliases.length} shown</span>
                        <span className="badge badge-amber">{geoAliases.length} total</span>
                    </div>

                    <div style={{ border: '1px solid #e2ebe5', borderRadius: 12, overflow: 'hidden' }}>
                        <div style={{ overflowX: 'auto' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                                <thead style={{ background: '#f4f6f5' }}>
                                    <tr style={{ borderBottom: '1px solid #e2ebe5' }}>
                                        <th style={TH}>Alias Key</th>
                                        <th style={TH}>Display</th>
                                        <th style={TH}>Assembly</th>
                                        <th style={TH}>Canonical Locality</th>
                                        <th style={TH}>Source</th>
                                        <th style={{ ...TH, width: 90 }}>Action</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {geoAliasLoading ? (
                                        <tr>
                                            <td colSpan={6} style={{ ...TD, textAlign: 'center', color: '#6b7f76', padding: '18px 12px' }}>
                                                Loading aliases…
                                            </td>
                                        </tr>
                                    ) : filteredGeoAliases.length === 0 ? (
                                        <tr>
                                            <td colSpan={6} style={{ ...TD, textAlign: 'center', color: '#6b7f76', padding: '18px 12px' }}>
                                                {geoAliases.length === 0 ? 'No tenant geo aliases found.' : 'No aliases match this search.'}
                                            </td>
                                        </tr>
                                    ) : filteredGeoAliases.map((item) => (
                                        <tr key={item.id} style={{ borderBottom: '1px solid #f0f4f1' }}>
                                            <td style={{ ...TD, fontFamily: 'monospace', fontSize: '0.76rem' }}>{item.key}</td>
                                            <td style={TD}>{item.display || <span style={{ color: '#9ca3af' }}>—</span>}</td>
                                            <td style={TD}>{item.assembly || <span style={{ color: '#9ca3af' }}>—</span>}</td>
                                            <td style={TD}>{item.canonical_locality || <span style={{ color: '#9ca3af' }}>—</span>}</td>
                                            <td style={TD}>{item.source || <span style={{ color: '#9ca3af' }}>—</span>}</td>
                                            <td style={{ ...TD, whiteSpace: 'nowrap' }}>
                                                <button
                                                    className="btn-danger"
                                                    style={{ fontSize: '0.72rem', padding: '4px 10px' }}
                                                    onClick={() => setGeoAliasDeleteTarget(item)}
                                                >
                                                    Delete
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            )}

            {/* ── Upload form ────────────────────────────────────────────────── */}
            <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                <div className="section-title">Upload Shared Seat Geography</div>
                <p style={{ color: '#6b7f76', fontSize: '0.8rem', marginTop: -8, marginBottom: '1rem' }}>
                    Upload once per seat. Every tenant on the same seat inherits this base geography automatically.
                </p>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginBottom: '1rem' }}>
                    <div className="form-row" style={{ marginBottom: 0 }}>
                        <label className="form-label">Seat Type</label>
                        <select
                            className="form-input"
                            value={seatType}
                            onChange={e => {
                                setSeatType(e.target.value);
                                setPConst('');
                                setASelection('');
                                setNewAssembly('');
                                setStations(null);
                                setValidationReport(null);
                            }}
                        >
                            {SEAT_TYPES.map(type => <option key={type.value} value={type.value}>{type.label}</option>)}
                        </select>
                    </div>
                    <div className="form-row" style={{ marginBottom: 0 }}>
                        <label className="form-label">{seatConfig.pickerLabel}</label>
                        {seatType === 'mp' ? (
                            <select
                                className="form-input"
                                value={pConst}
                                onChange={e => { setPConst(e.target.value); setASelection(''); }}
                            >
                                <option value="">Select…</option>
                                {constituencies.map(c => <option key={c} value={c}>{c}</option>)}
                            </select>
                        ) : (
                            <input
                                className="form-input"
                                placeholder="e.g. Belagavi North"
                                value={pConst}
                                onChange={e => { setPConst(e.target.value); setASelection(''); }}
                            />
                        )}
                    </div>
                    <div className="form-row" style={{ marginBottom: 0 }}>
                        <label className="form-label">{assemblyLabel}</label>
                        {pConst ? (
                            <>
                                <select
                                    className="form-input"
                                    value={aSelection}
                                    onChange={e => setASelection(e.target.value)}
                                >
                                    <option value="">Select…</option>
                                    {assemblies.map(a => <option key={a} value={a}>{a}</option>)}
                                    <option value="__new__">+ Add New {assemblyLabel}…</option>
                                </select>
                                {aSelection === '__new__' && (
                                    <input
                                        className="form-input"
                                        style={{ marginTop: 8 }}
                                        placeholder={seatType === 'mla' ? 'e.g. North Zone' : 'e.g. Ghaziabad'}
                                        value={newAssembly}
                                        onChange={e => setNewAssembly(e.target.value)}
                                    />
                                )}
                            </>
                        ) : (
                            <select className="form-input" disabled>
                                <option>Select a seat first</option>
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
                {seatType === 'mla' && (
                    <div style={{ marginTop: 10, color: '#6b7f76', fontSize: '0.76rem', lineHeight: 1.45 }}>
                        For MLA seats, you can keep a single routing group named after the seat or create multiple local routing buckets if that helps case routing.
                    </div>
                )}
            </div>

            {/* ── Review panel ───────────────────────────────────────────────── */}
            {stations !== null && (
                <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                        <div className="section-title" style={{ margin: 0 }}>
                            Review — {seatConfig.label} · {pConst} · {aConst}
                        </div>
                    </div>

                    <ReviewTable stations={stations} onChange={setStations} />

                    {validationReport && (
                        <div style={{
                            marginTop: 16,
                            padding: '14px 16px',
                            border: '1px solid #e2ebe5',
                            borderRadius: 10,
                            background: '#f8fbf9',
                        }}>
                            <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#1a2e28', marginBottom: 8 }}>
                                Validation Report
                            </div>
                            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
                                <span className="badge badge-slate">{validationReport.rows_received || 0} received</span>
                                <span className="badge badge-green">{validationReport.rows_saved || 0} saved</span>
                                <span className="badge badge-amber">{validationReport.meta_rows_removed || 0} meta removed</span>
                                <span className="badge badge-slate">
                                    {Object.keys(validationReport.ambiguous_localities_against_constituency || {}).length} ambiguous
                                </span>
                            </div>
                            {validationReport.meta_row_samples?.length > 0 && (
                                <div style={{ fontSize: '0.78rem', color: '#6b7f76', marginBottom: 8 }}>
                                    Removed meta rows: {validationReport.meta_row_samples.join(', ')}
                                </div>
                            )}
                            {Object.keys(validationReport.ambiguous_localities_against_constituency || {}).length > 0 && (
                                <div style={{ fontSize: '0.78rem', color: '#6b7f76', marginBottom: 8 }}>
                                    {Object.entries(validationReport.ambiguous_localities_against_constituency).map(([locality, assemblies]) => (
                                        <div key={locality}>
                                            {locality}: {assemblies.join(', ')}
                                        </div>
                                    ))}
                                </div>
                            )}
                            {validationReport.missing_locality_en_count > 0 && (
                                <div style={{ fontSize: '0.78rem', color: '#6b7f76' }}>
                                    Missing `locality_en` on {validationReport.missing_locality_en_count} rows.
                                </div>
                            )}
                        </div>
                    )}

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
                            onClick={() => { setStations(null); setValidationReport(null); if (fileRef.current) fileRef.current.value = ''; }}
                        >
                            Discard
                        </button>
                    </div>
                </div>
            )}

            <hr className="divider" />

            {/* ── Saved geography list ───────────────────────────────────────── */}
            <div className="section-title" style={{ marginBottom: '1rem' }}>Saved Seat Geography</div>

            {savedSeats.length === 0 ? (
                <div className="glass-panel">
                    <div className="empty-state">
                        <div className="empty-state-icon">
                            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M3 6l9-4 9 4v12l-9 4-9-4V6z" /><path d="M12 2v20M3 6l9 4 9-4" />
                            </svg>
                        </div>
                        <div className="empty-state-title">No seat geography uploaded yet</div>
                        <div className="empty-state-desc">Upload an Election Commission PDF above to get started</div>
                    </div>
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {savedSeats.map(({ seatType: savedSeatType, seatName }) => {
                        const key = `${savedSeatType}:${seatName}`;
                        const openKey = `${key}_open`;
                        return (
                        <div key={key} className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
                            <div
                                style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', cursor: 'pointer' }}
                                onClick={() => setSavedData(prev => ({ ...prev, [openKey]: !prev[openKey] }))}
                            >
                                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#006a4d" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M3 6l9-4 9 4v12l-9 4-9-4V6z" />
                                    </svg>
                                    <span className={`badge ${savedSeatType === 'mla' ? 'badge-red' : 'badge-green'}`}>{getSeatConfig(savedSeatType).label}</span>
                                    <span style={{ fontWeight: 600, fontSize: '0.88rem', color: '#1a2e28' }}>{seatName}</span>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                    <span className="badge badge-slate">{(savedData[key] || []).length} blocks</span>
                                    <svg
                                        width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6b7f76" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                                        style={{ transform: savedData[openKey] ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}
                                    >
                                        <polyline points="6 9 12 15 18 9" />
                                    </svg>
                                </div>
                            </div>

                            {savedData[openKey] && (
                                <div style={{ borderTop: '1px solid #e2ebe5' }}>
                                    {(savedData[key] || []).length === 0 ? (
                                        <div style={{ padding: '12px 16px', color: '#6b7f76', fontSize: '0.82rem' }}>No routing blocks found</div>
                                    ) : (savedData[key] || []).map(ac => (
                                        <div key={ac} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 16px', borderBottom: '1px solid #f0f4f1' }}>
                                            <span style={{ fontSize: '0.85rem', color: '#1a2e28' }}>{ac}</span>
                                            <div style={{ display: 'flex', gap: 8 }}>
                                                <button
                                                    className="btn-secondary"
                                                    style={{ fontSize: '0.72rem', padding: '4px 10px' }}
                                                    onClick={async () => {
                                                        try {
                                                            const r = await apiGet(`/api/admin/geography/${encodeURIComponent(seatName)}/${encodeURIComponent(ac)}?seat_type=${savedSeatType}`);
                                                            setStations(applyClean(r.data || []));
                                                            setSeatType(savedSeatType);
                                                            setPConst(seatName);
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
                                                    onClick={() => setDeleteTarget({ seatType: savedSeatType, pc: seatName, ac })}
                                                >
                                                    Delete
                                                </button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )})}
                </div>
            )}
        </>
    );
}
