'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { apiGet, apiPost } from '@/lib/api';
import { gen2, gen2Fonts } from '@/lib/briefcase-tokens';

// Staff Overview: Government Tracking. Three compact rows, each opening on click.
// Portals don't push updates, so "Check status" is how the office keeps this true.
export const CHECK_BUTTONS = [
    { outcome: 'still_pending', label: 'Still pending', tone: '' },
    { outcome: 'resolved', label: 'Resolved', tone: 'ok' },
    { outcome: 'closed_without_fix', label: 'Closed without fix', tone: 'bad' },
    { outcome: 'more_info', label: 'More info asked', tone: '' },
];
const SHOWN = 4;

const days = (n) => (n === null || n === undefined ? '—' : `${n} day${n === 1 ? '' : 's'}`);

function Row({ id, title, summary, value, warn, open, onToggle, children }) {
    return (
        <div className={`gt-row${open ? ' open' : ''}`}>
            <button type="button" className="gt-head" aria-expanded={open} aria-controls={`gt-${id}`} onClick={onToggle}>
                <span><span className="gt-title">{title}</span><span className="gt-sum">{summary}</span></span>
                <span className={`gt-val${warn ? ' warn' : ''}`}>{value}</span>
                <span className="gt-car" aria-hidden="true">›</span>
            </button>
            {open ? <div className="gt-body" id={`gt-${id}`}>{children}</div> : null}
        </div>
    );
}

export default function GovtTrackingCard({ syncIssues = 0, issues = [], onOpenCase }) {
    const [data, setData] = useState(null);
    const [status, setStatus] = useState('loading');
    const [open, setOpen] = useState(() => new Set());
    const [showAllDue, setShowAllDue] = useState(false);
    const [saving, setSaving] = useState(null);
    const [note, setNote] = useState('');

    const load = useCallback(() => {
        apiGet('/api/dashboard/overview/govt-tracking')
            .then((res) => {
                // Never render from a partial payload: a malformed response must not take the page down.
                if (res && res.check && res.departments && res.resolved) { setData(res); setStatus('ready'); }
                else setStatus('error');
            })
            .catch(() => setStatus('error'));
    }, []);
    useEffect(() => { load(); }, [load]);

    const toggle = (key) => setOpen((prev) => {
        const next = new Set(prev);
        if (next.has(key)) next.delete(key); else next.add(key);
        return next;
    });

    async function record(item, btn) {
        setSaving(item.id);
        setNote('');
        try {
            await apiPost(`/api/cases/${item.id}/govt/check`, { outcome: btn.outcome });
            setNote(`${item.case_ref}: recorded “${btn.label}”.`);
            load();
        } catch {
            setNote(`${item.case_ref}: could not save. Try again.`);
        } finally {
            setSaving(null);
        }
    }

    const chk = data?.check;
    const dep = data?.departments;
    const res = data?.resolved;
    const portal = data?.portal;
    const dueItems = chk ? (showAllDue ? chk.items : chk.items.slice(0, SHOWN)) : [];
    const resChange = res && res.previous !== null && res.previous !== undefined ? res.count - res.previous : null;

    return (
        <section className="op-panel gt" aria-label="Government Tracking">
            <div className="op-section-head">
                <h2>Government Tracking</h2>
                <Link href="/dashboard/sansadx">Open government cases -&gt;</Link>
            </div>
            {syncIssues > 0 ? (
                <div className="gt-alert" role="alert">
                    <strong>{syncIssues} {syncIssues === 1 ? 'filing' : 'filings'} failed to sync with the portal.</strong> Check before the next portal run.
                    {issues.length ? <ul>{issues.map((i) => <li key={i}>{i}</li>)}</ul> : null}
                </div>
            ) : null}
            {status === 'loading' ? <p className="gt-empty">Loading…</p> : null}
            {status === 'error' ? <p className="gt-empty" role="alert">Government tracking could not be loaded.</p> : null}
            {data ? (
                <>
                    <Row id="check" title="Check status of filed complaints"
                        summary={chk.due ? `${chk.due} not checked in ${data.check_every_days} days · oldest filed ${days(chk.oldest_filed_days)} ago`
                            : chk.open_filed ? `All checked in the last ${data.check_every_days} days` : 'No filed complaints waiting on government'}
                        value={chk.due} warn={chk.due > 0} open={open.has('check')} onToggle={() => toggle('check')}>
                        {chk.checked_recently_pct !== null ? (
                            <div className="gt-fresh">
                                <span>{chk.checked_recently_pct}% of filings checked in the last {data.check_every_days} days</span>
                                <span className="gt-bar" aria-hidden="true"><b style={{ width: `${chk.checked_recently_pct}%` }} /></span>
                            </div>
                        ) : null}
                        {note ? <p className="gt-note" role="status">{note}</p> : null}
                        {dueItems.map((item) => (
                            <div className="gt-chk" key={item.id}>
                                <div className="gt-chk-top">
                                    <div>
                                        <button type="button" className="gt-ref" onClick={() => onOpenCase?.(item.id)}>{item.case_ref}</button>
                                        <span className="gt-meta"> · {item.department}</span>
                                        <div className="gt-chk-title">{item.title || '—'}</div>
                                        <div className="gt-meta">
                                            Filed {days(item.filed_days)} ago · {item.last_checked_days === null ? 'never checked' : `last checked ${days(item.last_checked_days)} ago`}
                                            {item.reference ? ` · Ref ${item.reference}` : ''}
                                        </div>
                                    </div>
                                    {portal?.url ? <a className="gt-portal" href={portal.url} target="_blank" rel="noopener noreferrer">{portal.name} ↗</a> : null}
                                </div>
                                <div className="gt-btns">
                                    {CHECK_BUTTONS.map((btn) => (
                                        <button key={btn.outcome} type="button" className={btn.tone} disabled={saving === item.id}
                                            onClick={() => record(item, btn)}>{btn.label}</button>
                                    ))}
                                </div>
                            </div>
                        ))}
                        {chk.items.length > SHOWN ? (
                            <button type="button" className="gt-more" onClick={() => setShowAllDue(!showAllDue)}>
                                {showAllDue ? 'Show fewer' : `See all ${chk.due} due for a check →`}
                            </button>
                        ) : null}
                    </Row>

                    <Row id="dept" title="Filed complaints, department-wise"
                        summary={dep.filed ? `${dep.waiting} waiting across ${dep.rows.length} ${dep.rows.length === 1 ? 'department' : 'departments'}${dep.slowest ? ` · slowest: ${dep.slowest}` : ''}` : 'Nothing filed with government yet'}
                        value={dep.filed} open={open.has('dept')} onToggle={() => toggle('dept')}>
                        <table className="gt-table">
                            <thead><tr><th>Department</th><th className="r">Filed</th><th className="r">Waiting</th><th className="r">Resolved</th><th className="r">Oldest wait</th></tr></thead>
                            <tbody>
                                {dep.rows.map((d) => (
                                    <tr key={d.name}>
                                        <td><b>{d.name}</b></td><td className="r">{d.filed}</td><td className="r">{d.waiting}</td>
                                        <td className={`r${d.resolved ? ' grn' : ''}`}>{d.resolved}</td>
                                        <td className={`r${(d.oldest_wait_days || 0) > 30 ? ' red' : ''}`}>{d.oldest_wait_days === null ? '—' : `${d.oldest_wait_days}d`}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </Row>

                    <Row id="res" title="Resolved by Government"
                        summary={`Last ${res.window_days} days${resChange !== null ? ` · ${resChange === 0 ? 'same as' : `${resChange > 0 ? '↑' : '↓'} ${Math.abs(resChange)} vs`} previous ${res.window_days} days` : ''}${res.not_told ? ` · ${res.not_told} citizen${res.not_told === 1 ? '' : 's'} not yet told` : ''}`}
                        value={res.count} open={open.has('res')} onToggle={() => toggle('res')}>
                        <div className="gt-stats">
                            <div><strong>{res.avg_days === null ? '—' : res.avg_days}</strong><span>average days, filing to resolution</span></div>
                            <div><strong className={res.not_told ? 'amber' : ''}>{res.not_told}</strong><span>citizens not yet told</span></div>
                        </div>
                        {res.items.length ? res.items.slice(0, 6).map((r) => (
                            <button type="button" className="gt-res" key={r.id} onClick={() => onOpenCase?.(r.id)}>
                                <span className="gt-refm">{r.case_ref}</span>
                                <span><span className="gt-chk-title">{r.title || '—'}</span><span className="gt-meta">{r.department} · {days(r.days_to_resolve)}</span></span>
                                <span className={`gt-chip ${r.citizen_told ? 'told' : 'tell'}`}>{r.citizen_told ? 'Citizen told' : 'Tell citizen'}</span>
                            </button>
                        )) : <p className="gt-empty">Nothing resolved by government in the last {res.window_days} days.</p>}
                    </Row>
                </>
            ) : null}
            <style>{`
                .gt-alert { margin: 10px 13px; background: ${gen2.errSoft || '#F5E1D9'}; border: 1px solid #E8C2B5; padding: 9px 12px; font-size: 12.5px; color: #6E2A17; }
                .gt-alert ul { margin: 6px 0 0 16px; padding: 0; }
                .gt-empty { padding: 12px 16px; margin: 0; color: ${gen2.muted}; font-size: 12.5px; }
                .gt-row { border-top: 1px solid ${gen2.hair}; }
                .gt-head { width: 100%; display: grid; grid-template-columns: 1fr auto 14px; gap: 12px; align-items: center; padding: 12px 16px; border: 0; background: none; text-align: left; cursor: pointer; font: inherit; color: inherit; }
                .gt-head:hover { background: ${gen2.rowHover}; }
                .gt-head:focus-visible { outline: 2px solid ${gen2.green}; outline-offset: -2px; }
                .gt-title { display: block; font-weight: 600; font-size: 13.5px; color: ${gen2.ink}; }
                .gt-sum { display: block; font-size: 12px; color: ${gen2.muted}; margin-top: 1px; }
                .gt-val { font-family: ${gen2Fonts.serif}; font-size: 24px; font-weight: 600; color: ${gen2.ink}; font-variant-numeric: tabular-nums; }
                .gt-val.warn { color: ${gen2.err}; }
                .gt-car { color: ${gen2.muted}; transition: transform .15s; }
                .gt-row.open .gt-car { transform: rotate(90deg); }
                .gt-body { border-top: 1px solid ${gen2.hair}; background: ${gen2.surface}; }
                .gt-fresh { display: flex; align-items: center; gap: 10px; padding: 10px 16px; font-size: 12px; color: ${gen2.muted}; }
                .gt-bar { flex: 1; height: 6px; background: ${gen2.hair}; overflow: hidden; border-radius: 3px; }
                .gt-bar b { display: block; height: 100%; background: #B98118; }
                .gt-note { margin: 0; padding: 0 16px 8px; font-size: 12px; color: ${gen2.green}; }
                .gt-chk { padding: 10px 16px; border-top: 1px solid ${gen2.hair}; }
                .gt-chk-top { display: flex; justify-content: space-between; gap: 10px; }
                .gt-ref, .gt-refm { font-family: ${gen2Fonts.mono}; font-size: 12px; color: ${gen2.muted}; }
                .gt-ref { border: 0; background: none; padding: 0; cursor: pointer; text-decoration: underline; }
                .gt-meta { font-size: 12px; color: ${gen2.muted}; display: inline; }
                .gt-chk .gt-meta:last-child { display: block; }
                .gt-chk-title { display: block; font-weight: 600; font-size: 13px; color: ${gen2.ink}; margin-top: 1px; }
                .gt-portal { font-family: ${gen2Fonts.mono}; font-size: 11.5px; color: ${gen2.green}; text-decoration: none; white-space: nowrap; }
                .gt-btns { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
                .gt-btns button { border: 1px solid ${gen2.hairStrong}; background: ${gen2.surface}; padding: 4px 9px; font: 600 12px ${gen2Fonts.sans}; cursor: pointer; color: ${gen2.ink}; }
                .gt-btns button:hover:not(:disabled) { background: ${gen2.rowHover}; }
                .gt-btns button:disabled { opacity: .5; cursor: default; }
                .gt-btns .ok { color: ${gen2.green}; border-color: #A9CBB6; }
                .gt-btns .bad { color: ${gen2.err}; border-color: #E4B9AC; }
                .gt-more { display: block; width: 100%; text-align: left; border: 0; border-top: 1px solid ${gen2.hair}; background: none; padding: 10px 16px; font: 600 12.5px ${gen2Fonts.sans}; color: ${gen2.green}; cursor: pointer; }
                .gt-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
                .gt-table th { font-family: ${gen2Fonts.mono}; font-size: 9.5px; letter-spacing: .1em; text-transform: uppercase; color: ${gen2.muted}; font-weight: 500; text-align: left; padding: 8px 10px; border-bottom: 1px solid ${gen2.hair}; }
                .gt-table td { padding: 8px 10px; border-bottom: 1px solid ${gen2.hair}; color: ${gen2.ink}; }
                .gt-table th:first-child, .gt-table td:first-child { padding-left: 16px; }
                .gt-table th:last-child, .gt-table td:last-child { padding-right: 16px; }
                .gt-table tr:last-child td { border-bottom: 0; }
                .gt-table .r { text-align: right; font-variant-numeric: tabular-nums; }
                .gt-table .grn { color: ${gen2.green}; font-weight: 600; }
                .gt-table .red { color: ${gen2.err}; font-weight: 600; }
                .gt-stats { display: flex; gap: 24px; padding: 10px 16px; flex-wrap: wrap; }
                .gt-stats strong { display: block; font-family: ${gen2Fonts.serif}; font-size: 24px; color: ${gen2.ink}; }
                .gt-stats strong.amber { color: #8A5D12; }
                .gt-stats span { font-size: 12px; color: ${gen2.muted}; }
                .gt-res { width: 100%; display: grid; grid-template-columns: 64px 1fr auto; gap: 10px; align-items: center; padding: 9px 16px; border: 0; border-top: 1px solid ${gen2.hair}; background: none; text-align: left; cursor: pointer; font: inherit; color: inherit; }
                .gt-res:hover { background: ${gen2.rowHover}; }
                .gt-res .gt-meta { display: block; }
                .gt-chip { font-family: ${gen2Fonts.mono}; font-size: 9.5px; letter-spacing: .05em; text-transform: uppercase; padding: 2px 6px; white-space: nowrap; }
                .gt-chip.told { background: #E1ECE4; color: ${gen2.green}; }
                .gt-chip.tell { background: #F4E7C9; color: #8A5D12; }
                @media (max-width: 640px) { .gt-table th:nth-child(5), .gt-table td:nth-child(5) { display: none; } }
            `}</style>
        </section>
    );
}
