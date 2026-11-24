'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { SEAT_LABEL, clientHealth, fmtCount, fmtDays, fmtPct, periodPhrase } from '@/lib/partnerFormat';
import { Badge, Icon } from './ui';

export function HealthBadge({ client }) {
    const { level } = clientHealth(client);
    if (level === 'paused') return <Badge tone="neutral">Paused</Badge>;
    if (level === 'attention') return <Badge tone="crit">Needs attention</Badge>;
    if (level === 'watch') return <Badge tone="warn">Watch</Badge>;
    return <Badge tone="go">On track</Badge>;
}

const FILTERS = [
    ['all', 'All', () => true],
    ['attention', 'Needs attention', (c) => clientHealth(c).level === 'attention'],
    ['live', 'Live', (c) => c.status === 'active'],
    ['paused', 'Paused', (c) => c.status !== 'active'],
    ['mp', 'MP', (c) => c.seat_type !== 'mla'],
    ['mla', 'MLA', (c) => c.seat_type === 'mla'],
];

const SORTS = {
    priority: (c) => clientHealth(c).rank,
    name: (c) => (c.client_label || '').toLowerCase(),
    open: (c) => c.summary?.open ?? -1,
    resolved: (c) => c.summary?.resolved ?? -1,
    rate: (c) => c.summary?.resolution_rate ?? -1,
    critical: (c) => c.summary?.critical ?? -1,
    avg: (c) => c.summary?.avg_resolution_days ?? -1,
};

function SortHead({ k, label, sort, setSort, right }) {
    const on = sort.key === k;
    return (
        <th className={`${right ? 'r' : ''} ${on ? 'sorted' : ''}`} aria-sort={on ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
            <button type="button" onClick={() => setSort(on ? { key: k, dir: sort.dir === 'asc' ? 'desc' : 'asc' } : { key: k, dir: k === 'name' ? 'asc' : 'desc' })}>
                {label}<span className="arr" aria-hidden="true">{on ? (sort.dir === 'asc' ? '▲' : '▼') : '↕'}</span>
            </button>
        </th>
    );
}

function place(c) {
    return [c.constituency, SEAT_LABEL[c.seat_type] || 'MP'].filter(Boolean).join(' · ');
}

export default function ClientTable({ clients, period, title = 'Clients', compact = false, onSeeAll }) {
    const router = useRouter();
    const [q, setQ] = useState('');
    const [filter, setFilter] = useState('all');
    const [sort, setSort] = useState({ key: 'priority', dir: 'desc' });

    const counts = useMemo(() => Object.fromEntries(FILTERS.map(([k, , fn]) => [k, clients.filter(fn).length])), [clients]);
    const rows = useMemo(() => {
        const needle = q.trim().toLowerCase();
        const fn = FILTERS.find(([k]) => k === filter)[2];
        const list = clients.filter(fn).filter((c) => !needle || `${c.client_label} ${c.constituency || ''}`.toLowerCase().includes(needle));
        const val = SORTS[sort.key];
        const dir = sort.dir === 'asc' ? 1 : -1;
        return [...list].sort((a, b) => {
            const A = val(a);
            const B = val(b);
            return (A > B ? 1 : A < B ? -1 : 0) * dir;
        });
    }, [clients, q, filter, sort]);

    const href = (c) => `/partner/dashboard/clients/${c.id}`;
    const live = (c) => c.status === 'active';

    return (
        <section className="pd-panel" aria-labelledby="pd-ct-h">
            <div className="pd-sechead" style={{ padding: '18px 16px 0', margin: 0 }}>
                <div>
                    <h2 className="pd-sec" id="pd-ct-h">{title}</h2>
                    <div className="pd-secsub">Grievances received in {periodPhrase(period)}. Select a live client to open it.</div>
                </div>
                {compact && onSeeAll ? <Link className="pd-link" href={onSeeAll}>View all clients →</Link> : null}
            </div>
            <div className="pd-toolbar">
                <label className="pd-search">
                    <Icon name="search" size={16} /><span className="sr">Search clients</span>
                    <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search client or constituency" autoComplete="off" />
                </label>
                <div className="pd-chips" role="group" aria-label="Filter clients">
                    {FILTERS.map(([k, label]) => (
                        <button key={k} type="button" className="pd-chip" aria-pressed={filter === k} onClick={() => setFilter(k)}>
                            {label}<span className="c">{counts[k]}</span>
                        </button>
                    ))}
                </div>
            </div>

            <div className="pd-tablewrap cards">
                <table className="pd-table">
                    <thead>
                        <tr>
                            <SortHead k="name" label="Client" sort={sort} setSort={setSort} />
                            <SortHead k="open" label="Still open" sort={sort} setSort={setSort} right />
                            <SortHead k="resolved" label="Resolved" sort={sort} setSort={setSort} right />
                            <SortHead k="rate" label="Resolution rate" sort={sort} setSort={setSort} right />
                            <SortHead k="critical" label="Critical" sort={sort} setSort={setSort} right />
                            <SortHead k="avg" label="Avg. to resolve" sort={sort} setSort={setSort} right />
                            <th>Status</th>
                            <th className="r"><span className="sr">Open client</span></th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((c) => {
                            const s = c.summary;
                            return (
                                <tr key={c.id} className={live(c) ? 'go' : ''} onClick={live(c) ? (e) => { if (!e.target.closest('a')) router.push(href(c)); } : undefined}>
                                    <td><div className="pd-cname">{c.client_label}</div><div className="pd-csub">{place(c)}</div></td>
                                    <td className="r num">{fmtCount(s?.open)}</td>
                                    <td className="r num">{fmtCount(s?.resolved)}</td>
                                    <td className="r">
                                        <div className="pd-rate"><span className="num">{fmtPct(s?.resolution_rate)}</span>
                                            <span className="track" aria-hidden="true"><span className="fill" style={{ width: `${Math.round((s?.resolution_rate || 0) * 100)}%` }} /></span></div>
                                    </td>
                                    <td className="r num" style={(s?.critical || 0) >= 5 ? { color: 'var(--crit)', fontWeight: 600 } : undefined}>{fmtCount(s?.critical)}</td>
                                    <td className="r num muted">{fmtDays(s?.avg_resolution_days)}</td>
                                    <td><HealthBadge client={c} /></td>
                                    <td className="r">
                                        {live(c) ? <Link className="pd-link" href={href(c)} aria-label={`Open ${c.client_label}`}>View</Link>
                                            : <span className="pd-csub" title="Paused by Needle. Contact your account manager.">—<span className="sr">Paused by Needle; contact your account manager</span></span>}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
                {rows.length === 0 ? (
                    <div className="pd-empty">No clients match these filters.{' '}
                        <button type="button" className="pd-link" onClick={() => { setQ(''); setFilter('all'); }}>Clear filters</button>
                    </div>
                ) : null}
            </div>

            <ul className="pd-clist">
                {rows.map((c) => {
                    const s = c.summary;
                    const inner = (
                        <>
                            <div className="r1"><div><div className="pd-cname">{c.client_label}</div><div className="pd-csub">{place(c)}</div></div><HealthBadge client={c} /></div>
                            <div className="r2">
                                <div><b>{fmtCount(s?.open)}</b>Still open</div>
                                <div><b>{fmtPct(s?.resolution_rate)}</b>Resolved</div>
                                <div><b style={(s?.critical || 0) >= 5 ? { color: 'var(--crit)' } : undefined}>{fmtCount(s?.critical)}</b>Critical</div>
                            </div>
                        </>
                    );
                    return <li key={c.id}>{live(c) ? <Link href={href(c)}>{inner}</Link> : <div style={{ padding: '14px 16px' }}>{inner}</div>}</li>;
                })}
            </ul>

            <div className="pd-tfoot"><span>Showing {rows.length} of {clients.length} clients</span></div>
        </section>
    );
}
