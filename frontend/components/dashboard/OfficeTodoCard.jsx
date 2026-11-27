'use client';

import { useEffect, useState } from 'react';
import { apiGet } from '@/lib/api';
import { gen2, gen2Fonts } from '@/lib/briefcase-tokens';

// Staff Overview: Office To-do. Four counts, each with how long the oldest has waited,
// each opening the place where the work is done.
export const TODO = {
    unassigned: {
        label: 'Complaints with no owner', go: 'Assign owners', href: '/dashboard/sansadx?assigned_to=unassigned',
        sub: (d) => `oldest waiting ${d} day${d === 1 ? '' : 's'}`, warnAfter: 7,
    },
    letters: {
        label: 'Letters to review', go: 'Open Letterbox', href: '/dashboard/letterbox',
        sub: (d) => (d === 0 ? 'oldest received today' : `oldest received ${d} day${d === 1 ? '' : 's'} ago`), warnAfter: 7,
    },
    drafts: {
        label: 'Drafts awaiting approval', go: 'Review drafts', href: '/dashboard/letterbox?direction=outbox&status=drafted',
        sub: (d) => (d === 0 ? 'oldest drafted today' : `oldest drafted ${d} day${d === 1 ? '' : 's'} ago`), warnAfter: 7,
    },
    citizens_to_update: {
        label: 'Citizens to update', go: 'Send updates', href: '/dashboard/sansadx?status=resolved',
        sub: () => 'resolved by government, not yet told', warnAfter: 0,
    },
};

export default function OfficeTodoCard({ onNavigate }) {
    const [items, setItems] = useState(null);
    const [status, setStatus] = useState('loading');

    useEffect(() => {
        let cancelled = false;
        apiGet('/api/dashboard/overview/office-todo')
            .then((res) => {
                if (cancelled) return;
                const list = res && Array.isArray(res.items) ? res.items.filter((i) => i && TODO[i.key]) : null;
                if (list && list.length) { setItems(list); setStatus('ready'); } else setStatus('error');
            })
            .catch(() => { if (!cancelled) setStatus('error'); });
        return () => { cancelled = true; };
    }, []);

    const go = (href) => (typeof onNavigate === 'function' ? onNavigate(href) : undefined);

    return (
        <section className="op-panel ot" aria-label="Office To-do">
            <div className="op-section-head"><h2>Office To-do</h2></div>
            {status === 'loading' ? <p className="ot-empty">Loading…</p> : null}
            {status === 'error' ? <p className="ot-empty" role="alert">Office To-do could not be loaded.</p> : null}
            {items ? (
                <div className="ot-grid">
                    {items.map((item) => {
                        const def = TODO[item.key];
                        const n = Number(item.count) || 0;
                        const warn = n > 0 && item.oldest_days !== null && item.oldest_days !== undefined && item.oldest_days > def.warnAfter;
                        return (
                            <button type="button" key={item.key} className="ot-tile" onClick={() => go(def.href)}>
                                <span className={`ot-v${warn ? ' red' : ''}`}>{n}</span>
                                <span className="ot-l">{def.label}</span>
                                <span className={`ot-s${warn ? ' red' : ''}`}>
                                    {n ? def.sub(item.oldest_days ?? 0) : 'nothing waiting'}
                                </span>
                                <span className="ot-go">{def.go} →</span>
                            </button>
                        );
                    })}
                </div>
            ) : null}
            <style>{`
                .ot-empty { padding: 12px 16px; margin: 0; color: ${gen2.muted}; font-size: 12.5px; }
                .ot-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); }
                .ot-tile { display: flex; flex-direction: column; gap: 3px; padding: 14px 16px; border: 0; border-left: 1px solid ${gen2.hair};
                    background: none; text-align: left; cursor: pointer; font: inherit; color: inherit; }
                .ot-tile:first-child { border-left: 0; }
                .ot-tile:hover { background: ${gen2.surfaceWarm}; }
                .ot-tile:focus-visible { outline: 2px solid ${gen2.green}; outline-offset: -2px; }
                .ot-v { font-family: ${gen2Fonts.serif}; font-size: 30px; line-height: 1; font-weight: 650; color: ${gen2.ink}; font-variant-numeric: tabular-nums; }
                .ot-v.red, .ot-s.red { color: ${gen2.err}; }
                .ot-l { font-weight: 600; font-size: 13px; color: ${gen2.ink}; }
                .ot-s { font-size: 12px; color: ${gen2.muted}; }
                .ot-s.red { font-weight: 600; }
                .ot-go { font-size: 12px; color: ${gen2.green}; font-weight: 600; margin-top: 4px; }
                @media (max-width: 1100px) {
                    .ot-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                    .ot-tile:nth-child(3) { border-left: 0; }
                    .ot-tile:nth-child(n+3) { border-top: 1px solid ${gen2.hair}; }
                }
            `}</style>
        </section>
    );
}
