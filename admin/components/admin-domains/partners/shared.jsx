'use client';

import { useState } from 'react';

export const SEAT_STATUS = {
    active: { label: 'Live', badge: 'badge-green' },
    requested: { label: 'Awaiting activation', badge: 'badge-amber' },
    paused: { label: 'Paused', badge: 'badge-slate' },
    rejected: { label: 'Declined', badge: 'badge-red' },
};

const inr = new Intl.NumberFormat('en-IN');
export const formatInr = (value) => `₹${inr.format(value || 0)}`;

export function formatDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

/** Modal shell using the admin's existing modal classes, with dialog semantics. */
export function Modal({ title, titleId, children, onClose, width = 520 }) {
    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-card" role="dialog" aria-modal="true" aria-labelledby={titleId}
                style={{ maxWidth: width, width: '100%' }} onClick={(e) => e.stopPropagation()}>
                <h3 id={titleId} style={{ margin: '0 0 16px', fontSize: '1rem', fontWeight: 700 }}>{title}</h3>
                {children}
            </div>
        </div>
    );
}

/**
 * Shows a one-time temporary password. The server never returns it again, so the
 * operator must copy it before closing.
 */
export function TempPasswordModal({ email, password, onClose }) {
    const [copied, setCopied] = useState(false);

    async function copy() {
        try {
            await navigator.clipboard.writeText(password);
            setCopied(true);
        } catch {
            setCopied(false);
        }
    }

    return (
        <Modal title="Temporary password" titleId="temp-password-title" onClose={() => {}}>
            <p style={{ margin: '0 0 12px', fontSize: '0.85rem' }}>
                Share this with <strong>{email}</strong> over a secure channel. They must change it on first sign-in.
                It is shown only once.
            </p>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <code data-testid="temp-password" style={{ flex: 1, padding: '10px 12px', background: 'var(--surface-warm, #f7f0dc)', border: '1px solid var(--line, #d4c9af)', borderRadius: 6, fontSize: '1rem', letterSpacing: '0.04em', userSelect: 'all' }}>
                    {password}
                </code>
                <button type="button" className="btn-secondary" onClick={copy}>{copied ? 'Copied' : 'Copy'}</button>
            </div>
            <div className="modal-footer">
                <button type="button" className="btn-primary" onClick={onClose}>I have saved it</button>
            </div>
        </Modal>
    );
}
