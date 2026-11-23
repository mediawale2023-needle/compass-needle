'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { partnerClients } from '@/lib/partnerApi';
import { SEAT_LABEL, clientHealth } from '@/lib/partnerFormat';
import { Icon } from './ui';

const DOT = { attention: 'crit', watch: 'warn', ok: 'go', paused: 'neutral' };

/** Jump between clients without going back to the table. Loads the list only when opened. */
export default function ClientSwitcher({ currentId }) {
    const [open, setOpen] = useState(false);
    const [q, setQ] = useState('');
    const [clients, setClients] = useState(null);
    const [failed, setFailed] = useState(false);
    const ref = useRef(null);

    useEffect(() => {
        if (!open || clients) return;
        partnerClients(30).then((d) => setClients(d.clients || [])).catch(() => setFailed(true));
    }, [open, clients]);

    useEffect(() => {
        if (!open) return undefined;
        const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
        const esc = (e) => { if (e.key === 'Escape') setOpen(false); };
        document.addEventListener('mousedown', close);
        document.addEventListener('keydown', esc);
        return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc); };
    }, [open]);

    const needle = q.trim().toLowerCase();
    const list = (clients || []).filter((c) => !needle || `${c.client_label} ${c.constituency || ''}`.toLowerCase().includes(needle));

    return (
        <div className="pd-dd" ref={ref}>
            <button type="button" className="pd-btn" onClick={() => { setOpen((o) => !o); setQ(''); }} aria-haspopup="dialog" aria-expanded={open}>
                <Icon name="swap" size={16} /> Switch client <Icon name="down" size={14} />
            </button>
            {open ? (
                <div className="pd-pop pd-switcher" role="dialog" aria-label="Switch client">
                    {/* eslint-disable-next-line jsx-a11y/no-autofocus */}
                    <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find a client…" aria-label="Find a client" />
                    <div className="list">
                        {failed ? <div className="pd-empty" style={{ padding: 20 }}>The client list could not be loaded.</div> : null}
                        {!failed && !clients ? <div className="pd-empty" style={{ padding: 20 }}>Loading…</div> : null}
                        {clients && list.length === 0 ? <div className="pd-empty" style={{ padding: 20 }}>No match</div> : null}
                        {list.map((c) => {
                            const live = c.status === 'active';
                            const body = (
                                <>
                                    <span className={`pd-dot ${DOT[clientHealth(c).level]}`} aria-hidden="true" />
                                    <span style={{ flex: 1, minWidth: 0 }}>
                                        <b style={{ fontWeight: 600 }}>{c.client_label}</b>
                                        <small>{[c.constituency, SEAT_LABEL[c.seat_type] || 'MP', live ? null : 'Paused'].filter(Boolean).join(' · ')}</small>
                                    </span>
                                    {String(c.id) === String(currentId) ? <span className="muted" style={{ fontSize: 12 }}>Current</span> : null}
                                </>
                            );
                            return live ? (
                                <Link key={c.id} className={`item ${String(c.id) === String(currentId) ? 'active' : ''}`} href={`/partner/dashboard/clients/${c.id}`} onClick={() => setOpen(false)}>{body}</Link>
                            ) : <div key={c.id} className="item" style={{ cursor: 'default', opacity: 0.6 }}>{body}</div>;
                        })}
                    </div>
                </div>
            ) : null}
        </div>
    );
}
