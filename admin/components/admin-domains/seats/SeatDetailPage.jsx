'use client';
import { useState, useEffect, useMemo, useCallback } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { apiGet, apiPut, apiPatch } from '@/lib/api';
import ConfirmModal from '@/components/ConfirmModal';

function decodeSeatKey(raw) {
    const value = Array.isArray(raw) ? raw[0] : raw;
    if (!value) return '';
    try {
        return decodeURIComponent(value);
    } catch {
        return value;
    }
}

function DecisionBadge({ item }) {
    if (item.resolved) {
        return <span className="badge badge-green badge-dot">Resolved</span>;
    }
    if (item.needs_review || item.review_reason) {
        return <span className="badge badge-amber badge-dot">Needs review</span>;
    }
    return <span className="badge badge-red badge-dot">Unresolved</span>;
}

export default function SeatDetailPage() {
    const params = useParams();
    const seatKey = decodeSeatKey(params?.seatKey);
    const [seatType, , seatName] = useMemo(() => {
        const idx = seatKey.indexOf(':');
        if (idx === -1) return ['mp', ':', seatKey];
        return [seatKey.slice(0, idx) || 'mp', ':', seatKey.slice(idx + 1)];
    }, [seatKey]);

    const [seat, setSeat] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [message, setMessage] = useState(null);

    const [assemblies, setAssemblies] = useState([]);
    const [expandedAssembly, setExpandedAssembly] = useState('');
    const [stations, setStations] = useState({});
    const [stationsLoading, setStationsLoading] = useState('');
    const [editingLocality, setEditingLocality] = useState(''); // locality being edited, scoped to expandedAssembly
    const [editParent, setEditParent] = useState('');
    const [editSub, setEditSub] = useState('');
    const [hierarchySaving, setHierarchySaving] = useState('');
    const [stationSearch, setStationSearch] = useState('');

    const [overrides, setOverrides] = useState(null);
    const [rules, setRules] = useState({});
    const [rulesLoading, setRulesLoading] = useState(false);
    const [ruleInput, setRuleInput] = useState('');
    const [ruleAssembly, setRuleAssembly] = useState('');
    const [ruleEditingKey, setRuleEditingKey] = useState(null);
    const [ruleDeleteTarget, setRuleDeleteTarget] = useState(null);

    const [decisions, setDecisions] = useState([]);
    const [decisionsLoading, setDecisionsLoading] = useState(true);
    const [expandedDecision, setExpandedDecision] = useState(null);

    const showMsg = (type, text) => {
        setMessage({ type, text });
        setTimeout(() => setMessage(null), 4500);
    };

    useEffect(() => {
        if (!seatKey) return;
        apiGet('/api/admin/seats')
            .then((d) => {
                const match = (d.items || []).find(
                    (s) => (s.seat_key || '').toLowerCase() === seatKey.toLowerCase(),
                );
                setSeat(match || null);
                if (!match) setError(`No seat found for "${seatKey}".`);
            })
            .catch((e) => setError(e.message || 'Failed to load seat'))
            .finally(() => setLoading(false));
    }, [seatKey]);

    useEffect(() => {
        if (!seatName) return;
        apiGet(`/api/admin/geography/${encodeURIComponent(seatName)}/assemblies?seat_type=${seatType}`)
            .then((r) => setAssemblies(r.assemblies || []))
            .catch(() => {});
    }, [seatName, seatType]);

    useEffect(() => {
        apiGet('/api/admin/overrides')
            .then((response) => {
                setOverrides(response || {});
                const seatRules = (response?.seat_geo_overrides || {})[seatKey] || {};
                setRules(seatRules);
            })
            .catch(() => {});
    }, [seatKey]);

    const loadDecisions = useCallback(() => {
        if (!seatKey) return;
        setDecisionsLoading(true);
        apiGet(`/api/admin/seats/geography-decisions?seat_key=${encodeURIComponent(seatKey)}&limit=30`)
            .then((d) => setDecisions(d.items || []))
            .catch(() => setDecisions([]))
            .finally(() => setDecisionsLoading(false));
    }, [seatKey]);

    useEffect(() => { loadDecisions(); }, [loadDecisions]);

    const loadAssemblyStations = async (assembly) => {
        setStationsLoading(assembly);
        try {
            const r = await apiGet(
                `/api/admin/geography/${encodeURIComponent(seatName)}/${encodeURIComponent(assembly)}?seat_type=${seatType}`,
            );
            setStations((prev) => ({ ...prev, [assembly]: r.data || [] }));
        } catch {
            setStations((prev) => ({ ...prev, [assembly]: [] }));
        } finally {
            setStationsLoading((current) => (current === assembly ? '' : current));
        }
    };

    const toggleAssembly = (assembly) => {
        if (expandedAssembly === assembly) {
            setExpandedAssembly('');
            return;
        }
        setExpandedAssembly(assembly);
        if (!stations[assembly]) loadAssemblyStations(assembly);
    };

    const isSearching = stationSearch.trim().length > 0;

    // Searching spans every assembly, not just the one currently expanded, so
    // fetch any assembly whose stations haven't been loaded yet as soon as the
    // operator starts typing.
    useEffect(() => {
        if (!isSearching) return;
        assemblies.forEach((assembly) => {
            if (!stations[assembly] && stationsLoading !== assembly) loadAssemblyStations(assembly);
        });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isSearching, assemblies]);

    const stationMatchesSearch = (station, term) => {
        const needle = term.toLowerCase();
        return (
            (station.locality || '').toLowerCase().includes(needle) ||
            (station.sub_locality || '').toLowerCase().includes(needle) ||
            (station.parent_locality || '').toLowerCase().includes(needle)
        );
    };

    const startHierarchyEdit = (station) => {
        setEditingLocality(station.locality);
        setEditParent(station.parent_locality || '');
        setEditSub(station.sub_locality || '');
    };

    const cancelHierarchyEdit = () => {
        setEditingLocality('');
        setEditParent('');
        setEditSub('');
    };

    const applyHierarchyPatch = async (assembly, locality, body, successText) => {
        setHierarchySaving(locality);
        try {
            const r = await apiPatch(
                `/api/admin/geography/${encodeURIComponent(seatName)}/${encodeURIComponent(assembly)}/hierarchy?seat_type=${seatType}`,
                body,
            );
            const updated = r.station;
            setStations((prev) => ({
                ...prev,
                [assembly]: (prev[assembly] || []).map((s) =>
                    s.locality === locality ? { ...s, ...updated } : s,
                ),
            }));
            showMsg('success', successText);
            cancelHierarchyEdit();
            return true;
        } catch (err) {
            showMsg('error', err.message || 'Could not update parent/sub-locality.');
            return false;
        } finally {
            setHierarchySaving('');
        }
    };

    const saveHierarchyEdit = (assembly) => {
        const parent = editParent.trim();
        const sub = editSub.trim();
        if (!parent || !sub) {
            showMsg('error', 'Both parent and sub-locality are required.');
            return;
        }
        applyHierarchyPatch(
            assembly,
            editingLocality,
            { locality: editingLocality, mode: 'set', parent_locality: parent, sub_locality: sub },
            `Set "${editingLocality}" → ${sub} → ${parent}.`,
        );
    };

    const clearHierarchyToFlat = (assembly, locality) => {
        applyHierarchyPatch(
            assembly,
            locality,
            { locality, mode: 'clear_to_flat' },
            `"${locality}" locked as a flat locality.`,
        );
    };

    const resetHierarchyToAuto = (assembly, locality) => {
        applyHierarchyPatch(
            assembly,
            locality,
            { locality, mode: 'reset_to_auto' },
            `"${locality}" reset to automatic matching.`,
        );
    };

    const persistRules = async (nextRules, successText) => {
        const updated = { ...(overrides || {}) };
        if (!updated.seat_geo_overrides) updated.seat_geo_overrides = {};
        if (Object.keys(nextRules).length === 0) {
            delete updated.seat_geo_overrides[seatKey];
        } else {
            updated.seat_geo_overrides[seatKey] = nextRules;
        }
        setRulesLoading(true);
        try {
            await apiPut('/api/admin/overrides', { data: updated });
            setOverrides(updated);
            setRules(nextRules);
            if (successText) showMsg('success', successText);
            return true;
        } catch (err) {
            showMsg('error', err.message || 'Could not save manual correction.');
            return false;
        } finally {
            setRulesLoading(false);
        }
    };

    const addRule = async () => {
        const nextKey = ruleInput.trim().toLowerCase();
        const nextAssembly = ruleAssembly.trim();
        if (!nextKey || !nextAssembly) return;
        const nextRules = { ...rules };
        if (ruleEditingKey && ruleEditingKey !== nextKey) delete nextRules[ruleEditingKey];
        nextRules[nextKey] = nextAssembly;
        const ok = await persistRules(
            nextRules,
            ruleEditingKey ? `Updated correction for "${nextKey}".` : `Saved correction for "${nextKey}".`,
        );
        if (!ok) return;
        setRuleInput('');
        setRuleAssembly('');
        setRuleEditingKey(null);
    };

    const confirmRuleDelete = async () => {
        const target = ruleDeleteTarget;
        setRuleDeleteTarget(null);
        if (!target) return;
        const nextRules = { ...rules };
        delete nextRules[target];
        await persistRules(nextRules, `Removed correction "${target}".`);
    };

    const ruleEntries = Object.entries(rules).sort(([a], [b]) => a.localeCompare(b));
    const seatBadgeClass = seatType === 'mla' ? 'badge badge-red' : 'badge badge-green';

    if (!seatKey) {
        return <div className="toast toast-error">Missing seat key.</div>;
    }

    return (
        <>
            {message && (
                <div className={`toast toast-${message.type}`} style={{ marginBottom: '1rem' }}>{message.text}</div>
            )}
            {error && <div className="toast toast-error" style={{ marginBottom: '1rem' }}>{error}</div>}

            {ruleDeleteTarget && (
                <ConfirmModal
                    title="Remove manual correction?"
                    description={`Citizen mentions of "${ruleDeleteTarget}" will fall back to shared seat geography matching.`}
                    confirmLabel="Remove"
                    variant="danger"
                    onConfirm={confirmRuleDelete}
                    onCancel={() => setRuleDeleteTarget(null)}
                />
            )}

            {/* Header */}
            <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
                    <div>
                        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                            <h2 style={{ margin: 0, fontSize: '1.35rem', color: '#1a2e28' }}>{seatName || seatKey}</h2>
                            <span className={seatBadgeClass}>{seatType.toUpperCase()}</span>
                            {seat?.state ? <span className="badge badge-slate">{seat.state}</span> : null}
                        </div>
                        <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
                            <span className={`badge badge-dot ${seat?.geography_ready ? 'badge-green' : 'badge-red'}`}>
                                {seat?.geography_ready ? `Geography: ${seat.locality_count} localities` : 'No shared geography'}
                            </span>
                            <span className={`badge badge-dot ${seat?.map_ready ? 'badge-green' : 'badge-amber'}`}>
                                {seat?.map_ready ? `Map: ${seat.map_status || 'draft'}` : 'No map yet'}
                            </span>
                            <span className={`badge badge-dot ${seat?.boundary_ready ? 'badge-green' : 'badge-slate'}`}>
                                {seat?.boundary_ready ? 'Real boundary' : 'No boundary asset'}
                            </span>
                        </div>
                    </div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        <Link href="/dashboard/seats" className="btn-ghost" style={{ textDecoration: 'none', fontSize: '0.74rem' }}>
                            ← All seats
                        </Link>
                        <Link href="/dashboard/shared-geography/workspace" className="btn-secondary" style={{ textDecoration: 'none', fontSize: '0.74rem' }}>
                            Upload / replace geography
                        </Link>
                        <Link href="/dashboard/seat-maps" className="btn-secondary" style={{ textDecoration: 'none', fontSize: '0.74rem' }}>
                            Seat maps
                        </Link>
                    </div>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 1.3fr) minmax(300px, 1fr)', gap: 16, alignItems: 'start' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    {/* Core geography */}
                    <div className="glass-panel">
                        <div className="section-title" style={{ marginBottom: 6 }}>Core Geography</div>
                        <p style={{ color: '#6b7f76', fontSize: '0.8rem', marginTop: 0 }}>
                            Canonical locality data shared by every account on this seat.
                        </p>
                        {assemblies.length > 0 && (
                            <input
                                className="form-input"
                                style={{ marginBottom: 10, fontSize: '0.8rem' }}
                                placeholder="Search locality, parent, or sub-locality across all assemblies…"
                                value={stationSearch}
                                onChange={(e) => setStationSearch(e.target.value)}
                            />
                        )}
                        {loading ? (
                            <div className="skeleton" style={{ height: 40, borderRadius: 8 }} />
                        ) : assemblies.length === 0 ? (
                            <div className="empty-state">
                                <div className="empty-state-title">No geography uploaded</div>
                                <div className="empty-state-desc">Upload an Election Commission dataset from the geography workspace to activate matching for this seat.</div>
                            </div>
                        ) : (() => {
                            const term = stationSearch.trim();
                            const visibleAssemblies = assemblies.filter((assembly) => {
                                if (!isSearching) return true;
                                const loaded = stations[assembly];
                                // Keep showing an assembly while its rows are still loading for
                                // the search pass, so it doesn't flicker out and back in.
                                if (!loaded) return true;
                                return loaded.some((st) => stationMatchesSearch(st, term));
                            });
                            if (isSearching && visibleAssemblies.length === 0) {
                                return (
                                    <div className="empty-state">
                                        <div className="empty-state-title">No matches</div>
                                        <div className="empty-state-desc">No locality, parent, or sub-locality matches "{term}" in this seat's core geography.</div>
                                    </div>
                                );
                            }
                            return visibleAssemblies.map((assembly) => {
                                const allRows = stations[assembly] || [];
                                const rows = isSearching ? allRows.filter((st) => stationMatchesSearch(st, term)) : allRows;
                                const isExpanded = isSearching || expandedAssembly === assembly;
                                return (
                            <div key={assembly} style={{ border: '1px solid #e2ebe5', borderRadius: 10, marginBottom: 8, overflow: 'hidden' }}>
                                <button
                                    onClick={() => !isSearching && toggleAssembly(assembly)}
                                    style={{
                                        display: 'flex', width: '100%', justifyContent: 'space-between', alignItems: 'center',
                                        padding: '10px 14px', background: '#f8fbf9', border: 'none',
                                        cursor: isSearching ? 'default' : 'pointer',
                                        fontSize: '0.84rem', fontWeight: 600, color: '#1a2e28',
                                    }}
                                >
                                    <span>{assembly}</span>
                                    <span style={{ color: '#94a3a0', fontSize: '0.72rem' }}>
                                        {isSearching
                                            ? (stations[assembly] ? `${rows.length} match${rows.length === 1 ? '' : 'es'}` : 'searching…')
                                            : (stations[assembly] ? `${stations[assembly].length} rows` : '')}
                                        {!isSearching && ` ${expandedAssembly === assembly ? '▾' : '▸'}`}
                                    </span>
                                </button>
                                {isExpanded && (
                                    <div style={{ maxHeight: 320, overflowY: 'auto' }}>
                                        {!stations[assembly] ? (
                                            <div className="skeleton" style={{ height: 60, margin: 10, borderRadius: 8 }} />
                                        ) : (
                                            <table className="data-table" style={{ fontSize: '0.78rem' }}>
                                                <thead>
                                                    <tr><th>#</th><th>Locality</th><th>Parent / Sub</th><th style={{ textAlign: 'right' }}>Edit</th></tr>
                                                </thead>
                                                <tbody>
                                                    {rows.map((st, i) => {
                                                        const isEditing = editingLocality === st.locality;
                                                        const isManual = st.hierarchy_source === 'manual';
                                                        const isSaving = hierarchySaving === st.locality;
                                                        return (
                                                            <tr key={i}>
                                                                <td style={{ color: '#94a3a0' }}>{st.station_number || i + 1}</td>
                                                                <td>{st.locality}</td>
                                                                {isEditing ? (
                                                                    <td colSpan={2}>
                                                                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                                                                            <input
                                                                                className="form-input"
                                                                                style={{ width: 130, fontSize: '0.76rem', padding: '3px 6px' }}
                                                                                placeholder="Sub-locality"
                                                                                value={editSub}
                                                                                onChange={(e) => setEditSub(e.target.value)}
                                                                            />
                                                                            <span style={{ color: '#94a3a0' }}>→</span>
                                                                            <input
                                                                                className="form-input"
                                                                                style={{ width: 130, fontSize: '0.76rem', padding: '3px 6px' }}
                                                                                placeholder="Parent locality"
                                                                                value={editParent}
                                                                                onChange={(e) => setEditParent(e.target.value)}
                                                                            />
                                                                            <button
                                                                                className="btn-primary"
                                                                                style={{ fontSize: '0.7rem', padding: '3px 8px' }}
                                                                                disabled={isSaving}
                                                                                onClick={() => saveHierarchyEdit(assembly)}
                                                                            >
                                                                                {isSaving ? 'Saving…' : 'Save'}
                                                                            </button>
                                                                            <button
                                                                                className="btn-ghost"
                                                                                style={{ fontSize: '0.7rem', padding: '3px 8px' }}
                                                                                disabled={isSaving}
                                                                                onClick={cancelHierarchyEdit}
                                                                            >
                                                                                Cancel
                                                                            </button>
                                                                        </div>
                                                                    </td>
                                                                ) : (
                                                                    <>
                                                                        <td style={{ color: '#6b7f76' }}>
                                                                            {st.sub_locality && st.parent_locality
                                                                                ? `${st.sub_locality} → ${st.parent_locality}`
                                                                                : '—'}
                                                                            {isManual && (
                                                                                <span
                                                                                    className="badge badge-slate"
                                                                                    style={{ marginLeft: 6, fontSize: '0.6rem', padding: '1px 5px' }}
                                                                                    title="Operator-set — will not be auto-recomputed"
                                                                                >
                                                                                    manual
                                                                                </span>
                                                                            )}
                                                                        </td>
                                                                        <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                                                                            <button
                                                                                className="btn-ghost"
                                                                                style={{ fontSize: '0.7rem', padding: '2px 6px' }}
                                                                                disabled={isSaving}
                                                                                onClick={() => startHierarchyEdit(st)}
                                                                            >
                                                                                Edit
                                                                            </button>
                                                                            {isManual ? (
                                                                                <button
                                                                                    className="btn-ghost"
                                                                                    style={{ fontSize: '0.7rem', padding: '2px 6px' }}
                                                                                    disabled={isSaving}
                                                                                    onClick={() => resetHierarchyToAuto(assembly, st.locality)}
                                                                                >
                                                                                    Reset to auto
                                                                                </button>
                                                                            ) : (
                                                                                (st.sub_locality || st.parent_locality) && (
                                                                                    <button
                                                                                        className="btn-ghost"
                                                                                        style={{ fontSize: '0.7rem', padding: '2px 6px', color: '#b91c1c' }}
                                                                                        disabled={isSaving}
                                                                                        onClick={() => clearHierarchyToFlat(assembly, st.locality)}
                                                                                    >
                                                                                        Lock flat
                                                                                    </button>
                                                                                )
                                                                            )}
                                                                        </td>
                                                                    </>
                                                                )}
                                                            </tr>
                                                        );
                                                    })}
                                                </tbody>
                                            </table>
                                        )}
                                    </div>
                                )}
                            </div>
                                );
                            });
                        })()}
                    </div>

                    {/* Recent geography decisions */}
                    <div className="glass-panel">
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                            <div className="section-title" style={{ margin: 0 }}>Recent Geography Decisions</div>
                            <button className="btn-secondary" style={{ fontSize: '0.72rem', padding: '4px 10px' }} onClick={loadDecisions}>
                                Refresh
                            </button>
                        </div>
                        <p style={{ color: '#6b7f76', fontSize: '0.8rem', marginTop: 0 }}>
                            What the resolver actually did for the latest citizen messages on this seat.
                        </p>
                        {decisionsLoading ? (
                            <div className="skeleton" style={{ height: 60, borderRadius: 8 }} />
                        ) : decisions.length === 0 ? (
                            <div className="empty-state">
                                <div className="empty-state-title">No recent cases</div>
                                <div className="empty-state-desc">Resolution outcomes appear here as citizen messages arrive.</div>
                            </div>
                        ) : (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                {decisions.map((d) => (
                                    <div key={d.case_id} style={{ border: '1px solid #e2ebe5', borderRadius: 10, padding: '10px 14px' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                                            <div style={{ minWidth: 0 }}>
                                                <div style={{ fontSize: '0.82rem', color: '#1a2e28', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                                    {d.message_excerpt || '(no text)'}
                                                </div>
                                                <div style={{ fontSize: '0.7rem', color: '#94a3a0', marginTop: 3 }}>
                                                    {d.case_ref || `#${d.case_id}`} · tenant {d.tenant_id}
                                                    {d.created_at ? ` · ${new Date(d.created_at).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}` : ''}
                                                </div>
                                            </div>
                                            <div style={{ textAlign: 'right', flexShrink: 0 }}>
                                                <DecisionBadge item={d} />
                                                <div style={{ fontSize: '0.72rem', color: '#6b7f76', marginTop: 4 }}>
                                                    {d.resolved
                                                        ? `${d.location || d.matched_value}${d.assembly ? ` · ${d.assembly}` : ''}`
                                                        : (d.review_reason || 'no match')}
                                                </div>
                                            </div>
                                        </div>
                                        {d.has_diagnostics && (
                                            <button
                                                className="btn-ghost"
                                                style={{ fontSize: '0.7rem', padding: '2px 0', marginTop: 4 }}
                                                onClick={() => setExpandedDecision(expandedDecision === d.case_id ? null : d.case_id)}
                                            >
                                                {expandedDecision === d.case_id ? 'Hide attempts' : `Show attempts (${(d.attempts || []).length})`}
                                            </button>
                                        )}
                                        {expandedDecision === d.case_id && (
                                            <div style={{ marginTop: 6, background: '#f8fbf9', borderRadius: 8, padding: '8px 12px' }}>
                                                {(d.attempts || []).map((a, i) => (
                                                    <div key={i} style={{ fontSize: '0.72rem', color: '#6b7f76', padding: '3px 0' }}>
                                                        <strong style={{ color: '#1a2e28' }}>{a.source || 'attempt'}</strong>
                                                        {' — '}
                                                        {a.location_resolved
                                                            ? `matched "${a.matched_value}" → ${a.assembly_constituency || '?'} (${a.match_type || a.confidence_level || 'match'})`
                                                            : `no match${a.reason ? ` (${a.reason})` : ''}`}
                                                    </div>
                                                ))}
                                                {(d.attempts || []).length === 0 && (
                                                    <div style={{ fontSize: '0.72rem', color: '#94a3a0' }}>No attempt details recorded.</div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    {/* Manual corrections */}
                    <div className="glass-panel">
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                            <div className="section-title" style={{ margin: 0 }}>Manual Matching Corrections</div>
                            <span className="badge badge-slate">{ruleEntries.length} total</span>
                        </div>
                        <p style={{ color: '#6b7f76', fontSize: '0.8rem', marginTop: 0 }}>
                            Seat-scoped bridges for nicknames and misspellings shared geography cannot resolve. Applies to every account on this seat.
                        </p>

                        <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
                            <input
                                className="form-input"
                                style={{ flex: '1 1 140px' }}
                                placeholder="Citizen wording (e.g. teachers colony)"
                                value={ruleInput}
                                onChange={(e) => setRuleInput(e.target.value)}
                            />
                            <select
                                className="form-input"
                                style={{ flex: '1 1 120px' }}
                                value={ruleAssembly}
                                onChange={(e) => setRuleAssembly(e.target.value)}
                            >
                                <option value="">Assembly…</option>
                                {assemblies.map((a) => <option key={a} value={a}>{a}</option>)}
                            </select>
                            <button
                                className="btn-primary"
                                style={{ fontSize: '0.74rem' }}
                                disabled={rulesLoading || !ruleInput.trim() || !ruleAssembly.trim()}
                                onClick={addRule}
                            >
                                {ruleEditingKey ? 'Update' : 'Add'}
                            </button>
                            {ruleEditingKey && (
                                <button
                                    className="btn-ghost"
                                    style={{ fontSize: '0.74rem' }}
                                    onClick={() => { setRuleEditingKey(null); setRuleInput(''); setRuleAssembly(''); }}
                                >
                                    Cancel
                                </button>
                            )}
                        </div>

                        {ruleEntries.length === 0 ? (
                            <div style={{ color: '#94a3a0', fontSize: '0.78rem' }}>No manual corrections for this seat.</div>
                        ) : (
                            <div style={{ maxHeight: 340, overflowY: 'auto' }}>
                                {ruleEntries.map(([loc, ac]) => (
                                    <div
                                        key={loc}
                                        style={{
                                            display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8,
                                            padding: '7px 10px', borderBottom: '1px solid #eef4f0', fontSize: '0.8rem',
                                        }}
                                    >
                                        <div style={{ minWidth: 0 }}>
                                            <span style={{ color: '#1a2e28', fontWeight: 600 }}>{loc}</span>
                                            <span style={{ color: '#94a3a0' }}> → {ac}</span>
                                        </div>
                                        <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                                            <button
                                                className="btn-ghost"
                                                style={{ fontSize: '0.7rem', padding: '2px 8px' }}
                                                onClick={() => { setRuleEditingKey(loc); setRuleInput(loc); setRuleAssembly(ac); }}
                                            >
                                                Edit
                                            </button>
                                            <button
                                                className="btn-ghost"
                                                style={{ fontSize: '0.7rem', padding: '2px 8px', color: '#b91c1c' }}
                                                onClick={() => setRuleDeleteTarget(loc)}
                                            >
                                                Remove
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                        <div style={{ marginTop: 10 }}>
                            <Link
                                href="/dashboard/shared-geography/workspace"
                                style={{ fontSize: '0.72rem', color: '#6b7f76' }}
                            >
                                Need bulk paste? Use the geography workspace →
                            </Link>
                        </div>
                    </div>

                    {/* Linked accounts */}
                    <div className="glass-panel">
                        <div className="section-title" style={{ marginBottom: 6 }}>Accounts On This Seat</div>
                        {loading ? (
                            <div className="skeleton" style={{ height: 40, borderRadius: 8 }} />
                        ) : (seat?.tenants || []).length === 0 ? (
                            <div style={{ color: '#94a3a0', fontSize: '0.78rem' }}>No accounts use this seat yet.</div>
                        ) : (
                            (seat.tenants || []).map((t) => (
                                <div
                                    key={t.tenant_id}
                                    style={{
                                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                        padding: '8px 10px', borderBottom: '1px solid #eef4f0', fontSize: '0.82rem',
                                    }}
                                >
                                    <div>
                                        <Link href={`/dashboard/mps/${t.tenant_id}`} style={{ color: '#1a2e28', fontWeight: 600, textDecoration: 'none' }}>
                                            {t.name || `Tenant #${t.tenant_id}`}
                                        </Link>
                                        <div style={{ fontSize: '0.7rem', color: '#94a3a0' }}>Tenant #{t.tenant_id}</div>
                                    </div>
                                    <span className={`badge ${t.account_stage === 'aspirant' ? 'badge-slate' : 'badge-green'}`}>
                                        {t.account_stage || 'elected'}
                                    </span>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>
        </>
    );
}
