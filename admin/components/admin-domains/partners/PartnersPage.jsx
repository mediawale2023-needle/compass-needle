'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { apiGet, apiPost } from '@/lib/api';
import {
    AdminDataState, AdminMetricStrip, AdminNotice, AdminPageHeader, AdminPanel, AdminTableWrap,
} from '@/components/admin-ui/AdminPrimitives';
import { Modal, SEAT_STATUS, formatDate, formatInr } from './shared';

const BLANK = {
    name: '', brand_name: '', brand_color: '#1F3A5F', brand_logo_url: '', show_powered_by: true,
    contact_email: '', wholesale_price_inr: 15000,
};

function CreatePartnerModal({ onClose, onCreated }) {
    const [form, setForm] = useState(BLANK);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }));

    async function submit(e) {
        e.preventDefault();
        setSaving(true);
        setError('');
        try {
            const res = await apiPost('/api/admin/partners', {
                name: form.name.trim(),
                brand_name: form.brand_name.trim() || null,
                brand_color: form.brand_color,
                brand_logo_url: form.brand_logo_url.trim() || null,
                show_powered_by: form.show_powered_by,
                contact_email: form.contact_email.trim() || null,
                wholesale_price_inr: Number(form.wholesale_price_inr),
            });
            onCreated(res.partner);
        } catch (err) {
            setError(err.message || 'Could not create the partner.');
            setSaving(false);
        }
    }

    return (
        <Modal title="New partner" titleId="create-partner-title" onClose={saving ? () => {} : onClose} width={560}>
            <form onSubmit={submit}>
                <div className="form-row">
                    <label className="form-label" htmlFor="p-name">Consultancy name *</label>
                    <input id="p-name" className="form-input" required minLength={2} maxLength={120} value={form.name} onChange={set('name')} />
                </div>
                <div className="form-row">
                    <label className="form-label" htmlFor="p-brand">Brand name on reports <span style={{ fontWeight: 400 }}>(defaults to the name)</span></label>
                    <input id="p-brand" className="form-input" maxLength={120} value={form.brand_name} onChange={set('brand_name')} />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    <div className="form-row">
                        <label className="form-label" htmlFor="p-color">Brand colour</label>
                        <input id="p-color" type="color" className="form-input" style={{ height: 40, padding: 4 }} value={form.brand_color} onChange={set('brand_color')} />
                    </div>
                    <div className="form-row">
                        <label className="form-label" htmlFor="p-email">Contact email</label>
                        <input id="p-email" type="email" className="form-input" value={form.contact_email} onChange={set('contact_email')} />
                    </div>
                </div>
                <div className="form-row">
                    <label className="form-label" htmlFor="p-logo">Logo URL <span style={{ fontWeight: 400 }}>(https only, optional)</span></label>
                    <input id="p-logo" className="form-input" placeholder="https://…" value={form.brand_logo_url} onChange={set('brand_logo_url')} />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    <div className="form-row">
                        <label className="form-label" htmlFor="p-price">Wholesale ₹ / client / month</label>
                        <input id="p-price" type="number" min={0} className="form-input" value={form.wholesale_price_inr} onChange={set('wholesale_price_inr')} />
                    </div>
                </div>
                <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: '0.85rem', margin: '4px 0 8px' }}>
                    <input type="checkbox" checked={form.show_powered_by} onChange={set('show_powered_by')} />
                    Show &ldquo;Intelligence by Compass Needle&rdquo; on their reports
                </label>
                {error && <div role="alert" className="toast toast-error" style={{ position: 'static', margin: '8px 0' }}>{error}</div>}
                <div className="modal-footer">
                    <button type="submit" className="btn-primary" disabled={saving || form.name.trim().length < 2}>{saving ? 'Creating…' : 'Create partner'}</button>
                    <button type="button" className="btn-secondary" onClick={onClose} disabled={saving}>Cancel</button>
                </div>
            </form>
        </Modal>
    );
}

export default function PartnersPage() {
    const router = useRouter();
    const [partners, setPartners] = useState(null);
    const [pending, setPending] = useState(null); // null = unavailable
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [creating, setCreating] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        setError('');
        const [p, r] = await Promise.allSettled([apiGet('/api/admin/partners'), apiGet('/api/admin/partners/requests/pending')]);
        if (p.status === 'fulfilled') setPartners(p.value.partners || []);
        else setError(p.reason?.message || 'Failed to load partners');
        setPending(r.status === 'fulfilled' ? (r.value.requests || []) : null);
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    const totals = partners && {
        partners: partners.length,
        live: partners.reduce((n, p) => n + p.clients_active, 0),
        paused: partners.reduce((n, p) => n + p.clients_paused, 0),
        wholesale: partners.reduce((n, p) => n + p.monthly_wholesale_inr, 0),
    };

    return (
        <>
            <AdminPageHeader
                context="Customers"
                title="Partners"
                description="Political consultancies that bring tenants to Needle. A tenant is attributed to its partner while onboarding it (Onboarding → How did this tenant come to Needle?) and appears in the partner's portfolio immediately."
                actions={<button type="button" className="btn-primary" onClick={() => setCreating(true)}>+ New partner</button>}
            />

            <AdminDataState loading={loading && !partners} error={error} onRetry={load}>
                {partners && (
                    <>
                        <AdminMetricStrip items={[
                            { label: 'Partners', value: totals.partners },
                            { label: 'Active attributed clients', value: totals.live },
                            { label: 'Paused clients', value: totals.paused, detail: 'Attributed, partner access paused' },
                            { label: 'Est. monthly wholesale', value: formatInr(totals.wholesale), detail: 'Active clients × wholesale price' },
                        ]} />

                        {pending === null && (
                            <AdminNotice tone="warning" title="Legacy request list unavailable"
                                action={<button type="button" className="btn-secondary" onClick={load}>Try again</button>}>
                                The list of old partner seat requests could not be loaded. Do not assume there are none.
                            </AdminNotice>
                        )}

                        {pending && pending.length > 0 && (
                        <AdminPanel title="Legacy seat requests" description="Requests made before partner attribution moved into onboarding. New partner tenants never need this step. Link each to an existing account or decline it.">
                            {pending ? (
                                <AdminTableWrap label="Legacy seat requests">
                                    <table className="data-table">
                                        <thead><tr><th>Partner</th><th>Client</th><th>Seat</th><th>Requested</th><th>Notes</th><th /></tr></thead>
                                        <tbody>
                                            {pending.map((r) => (
                                                <tr key={r.id}>
                                                    <td>{r.partner_name}</td>
                                                    <td><strong>{r.client_label}</strong><div style={{ fontSize: '0.72rem', opacity: 0.7 }}>{r.constituency || '—'}</div></td>
                                                    <td>{r.seat_type === 'mla' ? 'MLA' : 'MP'}</td>
                                                    <td>{formatDate(r.created_at)}</td>
                                                    <td style={{ maxWidth: 240 }}>{r.notes || '—'}</td>
                                                    <td style={{ textAlign: 'right' }}>
                                                        <Link className="btn-secondary" href={`/dashboard/partners/${r.partner_id}`}>Review</Link>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </AdminTableWrap>
                            ) : null}
                        </AdminPanel>
                        )}

                        <AdminPanel title="All partners">
                            {partners.length === 0 ? (
                                <div className="admin-empty-state">
                                    <h3>No partners yet</h3>
                                    <p>Create the first consultancy, then pick it when onboarding a tenant it brought to Needle.</p>
                                </div>
                            ) : (
                                <AdminTableWrap label="Partners">
                                    <table className="data-table">
                                        <thead>
                                            <tr><th>Partner</th><th>Status</th><th>Active clients</th><th>Paused</th><th>Legacy requests</th><th>Wholesale / client</th><th>Monthly wholesale</th><th>Logins</th><th>Created</th></tr>
                                        </thead>
                                        <tbody>
                                            {partners.map((p) => (
                                                <tr key={p.id} style={{ opacity: p.is_active ? 1 : 0.55 }}>
                                                    <td>
                                                        <Link href={`/dashboard/partners/${p.id}`} style={{ fontWeight: 600 }}>{p.name}</Link>
                                                        <div style={{ fontSize: '0.72rem', opacity: 0.7 }}>{p.contact_email || p.slug}</div>
                                                    </td>
                                                    <td><span className={`badge badge-dot ${p.is_active ? 'badge-green' : 'badge-red'}`}>{p.is_active ? 'Active' : 'Inactive'}</span></td>
                                                    <td>{p.clients_active}</td>
                                                    <td>{p.clients_paused}</td>
                                                    <td>{p.legacy_requests > 0 ? <span className={`badge ${SEAT_STATUS.requested.badge}`}>{p.legacy_requests}</span> : 0}</td>
                                                    <td>{formatInr(p.wholesale_price_inr)}</td>
                                                    <td>{formatInr(p.monthly_wholesale_inr)}</td>
                                                    <td>{p.users_count}</td>
                                                    <td>{formatDate(p.created_at)}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </AdminTableWrap>
                            )}
                        </AdminPanel>
                    </>
                )}
            </AdminDataState>

            {creating && (
                <CreatePartnerModal
                    onClose={() => setCreating(false)}
                    onCreated={(partner) => { setCreating(false); router.push(`/dashboard/partners/${partner.id}`); }}
                />
            )}
        </>
    );
}
