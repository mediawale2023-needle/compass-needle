'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { apiGet, apiPatch, apiPost } from '@/lib/api';
import ConfirmModal from '@/components/ConfirmModal';
import {
    AdminDataState, AdminMetricStrip, AdminNotice, AdminPageHeader, AdminPanel, AdminTableWrap,
} from '@/components/admin-ui/AdminPrimitives';
import { Modal, SEAT_STATUS, TempPasswordModal, formatDate, formatInr } from './shared';

// ───────────── seats ─────────────
function ActivateSeatModal({ partnerId, seat, onClose, onDone }) {
    const [tenants, setTenants] = useState(null);
    const [loadError, setLoadError] = useState('');
    const [tenantId, setTenantId] = useState('');
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        let cancelled = false;
        apiGet('/api/admin/partners/available-tenants')
            .then((r) => { if (!cancelled) setTenants(r.tenants || []); })
            .catch((e) => { if (!cancelled) setLoadError(e.message || 'Could not load accounts'); });
        return () => { cancelled = true; };
    }, []);

    async function submit(e) {
        e.preventDefault();
        setSaving(true);
        setError('');
        try {
            await apiPost(`/api/admin/partners/${partnerId}/seats/${seat.id}/activate`, { tenant_id: Number(tenantId) });
            onDone(`${seat.client_label} is now live.`);
        } catch (err) {
            setError(err.message || 'Could not activate the seat.');
            setSaving(false);
        }
    }

    return (
        <Modal title={`Activate ${seat.client_label}`} titleId="activate-seat-title" onClose={saving ? () => {} : onClose}>
            <form onSubmit={submit}>
                <p style={{ margin: '0 0 12px', fontSize: '0.85rem' }}>
                    Link this seat to an existing customer account. Requested: {seat.constituency || 'constituency not given'} · {seat.seat_type === 'mla' ? 'MLA' : 'MP'}.
                    {seat.notes ? ` Notes: ${seat.notes}` : ''}
                </p>
                {loadError ? (
                    <div role="alert" className="toast toast-error" style={{ position: 'static' }}>{loadError}</div>
                ) : tenants === null ? (
                    <div className="admin-skeleton-row" aria-busy="true" aria-label="Loading accounts" />
                ) : tenants.length === 0 ? (
                    <AdminNotice tone="warning" title="No unlinked accounts available">
                        Create the customer account first, then come back to link it.
                    </AdminNotice>
                ) : (
                    <div className="form-row">
                        <label className="form-label" htmlFor="activate-tenant">Customer account *</label>
                        <select id="activate-tenant" className="form-input" required value={tenantId} onChange={(e) => setTenantId(e.target.value)}>
                            <option value="">— select account —</option>
                            {tenants.map((t) => (
                                <option key={t.tenant_id} value={t.tenant_id}>
                                    {t.name} · {t.constituency || 'no constituency'} · {t.account_stage || 'account'} #{t.tenant_id}
                                </option>
                            ))}
                        </select>
                    </div>
                )}
                <p style={{ fontSize: '0.78rem', margin: '8px 0 0' }}>
                    Account not created yet? <Link href="/dashboard/accounts/new">Open Onboarding</Link>.
                </p>
                {error && <div role="alert" className="toast toast-error" style={{ position: 'static', margin: '8px 0' }}>{error}</div>}
                <div className="modal-footer">
                    <button type="submit" className="btn-primary" disabled={!tenantId || saving}>{saving ? 'Linking…' : 'Link and activate'}</button>
                    <button type="button" className="btn-secondary" onClick={onClose} disabled={saving}>Cancel</button>
                </div>
            </form>
        </Modal>
    );
}

function SeatsPanel({ partner, seats, error, loading, onRetry, onChanged, notify }) {
    const [activating, setActivating] = useState(null);
    const [confirm, setConfirm] = useState(null); // { seat, action }
    const [busy, setBusy] = useState(false);

    async function runConfirmed() {
        const { seat, action } = confirm;
        setConfirm(null);
        setBusy(true);
        try {
            if (action === 'reject') await apiPost(`/api/admin/partners/${partner.id}/seats/${seat.id}/reject`, {});
            else await apiPost(`/api/admin/partners/${partner.id}/seats/${seat.id}/status`, { status: action === 'pause' ? 'paused' : 'active' });
            notify('success', action === 'reject' ? 'Request declined.' : action === 'pause' ? `${seat.client_label} paused.` : `${seat.client_label} resumed.`);
            onChanged();
        } catch (e) {
            notify('error', e.message || 'Action failed.');
        } finally {
            setBusy(false);
        }
    }

    const CONFIRM_COPY = {
        reject: (s) => ({ title: `Decline ${s.client_label}?`, description: 'The partner will see this request as declined and the seat is freed from their cap.', label: 'Decline', variant: 'danger' }),
        pause: (s) => ({ title: `Pause ${s.client_label}?`, description: 'The partner immediately stops seeing this client’s data. The customer account itself is unaffected.', label: 'Pause', variant: 'warning' }),
        resume: (s) => ({ title: `Resume ${s.client_label}?`, description: 'The partner can see this client’s data again.', label: 'Resume', variant: 'warning' }),
    };
    const copy = confirm ? CONFIRM_COPY[confirm.action](confirm.seat) : null;

    return (
        <AdminPanel title="Client seats" description="Requests from the partner and the customer accounts linked to them.">
            <AdminDataState loading={loading} error={error} onRetry={onRetry} empty={!error && seats.length === 0}
                emptyTitle="No seats yet" emptyDescription="Seat requests from this partner will appear here.">
                <AdminTableWrap label="Partner client seats">
                    <table className="data-table">
                        <thead><tr><th>Client</th><th>Seat</th><th>Status</th><th>Linked account</th><th>Requested</th><th style={{ textAlign: 'right' }}>Actions</th></tr></thead>
                        <tbody>
                            {seats.map((s) => {
                                const st = SEAT_STATUS[s.status] || { label: s.status, badge: 'badge-slate' };
                                return (
                                    <tr key={s.id}>
                                        <td><strong>{s.client_label}</strong><div style={{ fontSize: '0.72rem', opacity: 0.7 }}>{s.constituency || '—'}</div></td>
                                        <td>{s.seat_type === 'mla' ? 'MLA' : 'MP'}</td>
                                        <td><span className={`badge badge-dot ${st.badge}`}>{st.label}</span></td>
                                        <td>{s.tenant_id ? <>{s.tenant_name || 'Account'} <span style={{ opacity: 0.6 }}>#{s.tenant_id}</span></> : '—'}</td>
                                        <td>{formatDate(s.created_at)}</td>
                                        <td style={{ textAlign: 'right' }}>
                                            <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                                                {s.status === 'requested' && <>
                                                    <button type="button" className="btn-primary" disabled={busy} onClick={() => setActivating(s)}>Activate</button>
                                                    <button type="button" className="btn-ghost" disabled={busy} onClick={() => setConfirm({ seat: s, action: 'reject' })}>Decline</button>
                                                </>}
                                                {s.status === 'active' && <button type="button" className="btn-ghost" disabled={busy} onClick={() => setConfirm({ seat: s, action: 'pause' })}>Pause</button>}
                                                {s.status === 'paused' && <button type="button" className="btn-ghost" disabled={busy} onClick={() => setConfirm({ seat: s, action: 'resume' })}>Resume</button>}
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </AdminTableWrap>
            </AdminDataState>

            {activating && (
                <ActivateSeatModal partnerId={partner.id} seat={activating} onClose={() => setActivating(null)}
                    onDone={(msg) => { setActivating(null); notify('success', msg); onChanged(); }} />
            )}
            {confirm && (
                <ConfirmModal title={copy.title} description={copy.description} confirmLabel={copy.label} variant={copy.variant}
                    onConfirm={runConfirmed} onCancel={() => setConfirm(null)} />
            )}
        </AdminPanel>
    );
}

// ───────────── users ─────────────
function AddUserModal({ partnerId, onClose, onCreated }) {
    const [email, setEmail] = useState('');
    const [name, setName] = useState('');
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    async function submit(e) {
        e.preventDefault();
        setSaving(true);
        setError('');
        try {
            const res = await apiPost(`/api/admin/partners/${partnerId}/users`, { email: email.trim(), display_name: name.trim() || null });
            onCreated(res);
        } catch (err) {
            setError(err.message || 'Could not create the login.');
            setSaving(false);
        }
    }

    return (
        <Modal title="Add partner login" titleId="add-user-title" onClose={saving ? () => {} : onClose}>
            <form onSubmit={submit}>
                <div className="form-row">
                    <label className="form-label" htmlFor="u-email">Work email *</label>
                    <input id="u-email" type="email" className="form-input" required value={email} onChange={(e) => setEmail(e.target.value)} />
                </div>
                <div className="form-row">
                    <label className="form-label" htmlFor="u-name">Name</label>
                    <input id="u-name" className="form-input" maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
                </div>
                {error && <div role="alert" className="toast toast-error" style={{ position: 'static', margin: '8px 0' }}>{error}</div>}
                <div className="modal-footer">
                    <button type="submit" className="btn-primary" disabled={saving || !email.trim()}>{saving ? 'Creating…' : 'Create login'}</button>
                    <button type="button" className="btn-secondary" onClick={onClose} disabled={saving}>Cancel</button>
                </div>
            </form>
        </Modal>
    );
}

function UsersPanel({ partner, users, error, loading, onRetry, onChanged, notify }) {
    const [adding, setAdding] = useState(false);
    const [confirm, setConfirm] = useState(null); // { user, action: 'reset' | 'deactivate' | 'reactivate' }
    const [secret, setSecret] = useState(null); // { email, password }
    const [busy, setBusy] = useState(false);

    async function runConfirmed() {
        const { user, action } = confirm;
        setConfirm(null);
        setBusy(true);
        try {
            if (action === 'reset') {
                const res = await apiPost(`/api/admin/partners/${partner.id}/users/${user.id}/reset-password`, {});
                setSecret({ email: res.email, password: res.temporary_password });
            } else {
                await apiPost(`/api/admin/partners/${partner.id}/users/${user.id}/active`, { is_active: action === 'reactivate' });
                notify('success', `${user.email} ${action === 'reactivate' ? 'reactivated' : 'deactivated'}.`);
            }
            onChanged();
        } catch (e) {
            notify('error', e.message || 'Action failed.');
        } finally {
            setBusy(false);
        }
    }

    const COPY = {
        reset: (u) => ({ title: `Reset password for ${u.email}?`, description: 'A new one-time password is issued and their current session ends immediately.', label: 'Reset password', variant: 'warning' }),
        deactivate: (u) => ({ title: `Deactivate ${u.email}?`, description: 'They can no longer sign in, and any open session stops working.', label: 'Deactivate', variant: 'danger' }),
        reactivate: (u) => ({ title: `Reactivate ${u.email}?`, description: 'They can sign in again with their existing password.', label: 'Reactivate', variant: 'warning' }),
    };
    const copy = confirm ? COPY[confirm.action](confirm.user) : null;

    return (
        <AdminPanel title="Partner logins" description="People at the consultancy who can sign in to the partner dashboard."
            actions={<button type="button" className="btn-primary" onClick={() => setAdding(true)}>+ Add login</button>}>
            <AdminDataState loading={loading} error={error} onRetry={onRetry} empty={!error && users.length === 0}
                emptyTitle="No logins yet" emptyDescription="Add a login so the consultancy can sign in.">
                <AdminTableWrap label="Partner logins">
                    <table className="data-table">
                        <thead><tr><th>Person</th><th>Status</th><th>Password</th><th>Added</th><th style={{ textAlign: 'right' }}>Actions</th></tr></thead>
                        <tbody>
                            {users.map((u) => (
                                <tr key={u.id} style={{ opacity: u.is_active ? 1 : 0.55 }}>
                                    <td><strong>{u.display_name || u.email}</strong>{u.display_name && <div style={{ fontSize: '0.72rem', opacity: 0.7 }}>{u.email}</div>}</td>
                                    <td><span className={`badge badge-dot ${u.is_active ? 'badge-green' : 'badge-red'}`}>{u.is_active ? 'Active' : 'Deactivated'}</span></td>
                                    <td>{u.must_change_password ? <span className="badge badge-amber">Temporary, not yet changed</span> : 'Set by user'}</td>
                                    <td>{formatDate(u.created_at)}</td>
                                    <td style={{ textAlign: 'right' }}>
                                        <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                                            <button type="button" className="btn-ghost" disabled={busy} onClick={() => setConfirm({ user: u, action: 'reset' })}>Reset password</button>
                                            <button type="button" className="btn-ghost" disabled={busy} onClick={() => setConfirm({ user: u, action: u.is_active ? 'deactivate' : 'reactivate' })}>
                                                {u.is_active ? 'Deactivate' : 'Reactivate'}
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </AdminTableWrap>
            </AdminDataState>

            {adding && (
                <AddUserModal partnerId={partner.id} onClose={() => setAdding(false)}
                    onCreated={(res) => { setAdding(false); setSecret({ email: res.email, password: res.temporary_password }); onChanged(); }} />
            )}
            {confirm && <ConfirmModal title={copy.title} description={copy.description} confirmLabel={copy.label} variant={copy.variant}
                onConfirm={runConfirmed} onCancel={() => setConfirm(null)} />}
            {secret && <TempPasswordModal email={secret.email} password={secret.password} onClose={() => setSecret(null)} />}
        </AdminPanel>
    );
}

// ───────────── branding & limits ─────────────
function SettingsPanel({ partner, onSaved, notify }) {
    const [form, setForm] = useState(null);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        setForm({
            brand_name: partner.brand_name || '', brand_color: partner.brand_color || '#1F3A5F',
            brand_logo_url: partner.brand_logo_url || '', show_powered_by: !!partner.show_powered_by,
            contact_email: partner.contact_email || '', seat_cap: partner.seat_cap, wholesale_price_inr: partner.wholesale_price_inr,
        });
    }, [partner]);

    if (!form) return null;
    const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }));

    async function save(e) {
        e.preventDefault();
        setSaving(true);
        try {
            await apiPatch(`/api/admin/partners/${partner.id}`, {
                brand_name: form.brand_name.trim(), brand_color: form.brand_color,
                brand_logo_url: form.brand_logo_url.trim(), show_powered_by: form.show_powered_by,
                contact_email: form.contact_email.trim(), seat_cap: Number(form.seat_cap),
                wholesale_price_inr: Number(form.wholesale_price_inr),
            });
            notify('success', 'Partner settings saved.');
            onSaved();
        } catch (err) {
            notify('error', err.message || 'Could not save settings.');
        } finally {
            setSaving(false);
        }
    }

    return (
        <AdminPanel title="Branding & limits" description="What the consultancy's clients see on reports, and how many seats they may hold.">
            <form onSubmit={save}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
                    <div className="form-row"><label className="form-label" htmlFor="s-brand">Brand name</label>
                        <input id="s-brand" className="form-input" value={form.brand_name} onChange={set('brand_name')} /></div>
                    <div className="form-row"><label className="form-label" htmlFor="s-color">Brand colour</label>
                        <input id="s-color" type="color" className="form-input" style={{ height: 40, padding: 4 }} value={form.brand_color} onChange={set('brand_color')} /></div>
                    <div className="form-row"><label className="form-label" htmlFor="s-logo">Logo URL (https)</label>
                        <input id="s-logo" className="form-input" value={form.brand_logo_url} onChange={set('brand_logo_url')} /></div>
                    <div className="form-row"><label className="form-label" htmlFor="s-email">Contact email</label>
                        <input id="s-email" type="email" className="form-input" value={form.contact_email} onChange={set('contact_email')} /></div>
                    <div className="form-row"><label className="form-label" htmlFor="s-cap">Seat cap</label>
                        <input id="s-cap" type="number" min={0} max={500} className="form-input" value={form.seat_cap} onChange={set('seat_cap')} /></div>
                    <div className="form-row"><label className="form-label" htmlFor="s-price">Wholesale ₹ / seat / month</label>
                        <input id="s-price" type="number" min={0} className="form-input" value={form.wholesale_price_inr} onChange={set('wholesale_price_inr')} /></div>
                </div>
                <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: '0.85rem', margin: '4px 0 12px' }}>
                    <input type="checkbox" checked={form.show_powered_by} onChange={set('show_powered_by')} />
                    Show &ldquo;Intelligence by Compass Needle&rdquo; on reports and the dashboard
                </label>
                <button type="submit" className="btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Save settings'}</button>
            </form>
        </AdminPanel>
    );
}

// ───────────── page ─────────────
export default function PartnerDetailPage() {
    const { partnerId } = useParams();
    const [partner, setPartner] = useState(null);
    const [partnerState, setPartnerState] = useState('loading'); // loading | ready | missing | error
    const [partnerError, setPartnerError] = useState('');
    const [seats, setSeats] = useState([]);
    const [seatsError, setSeatsError] = useState('');
    const [seatsLoading, setSeatsLoading] = useState(true);
    const [users, setUsers] = useState([]);
    const [usersError, setUsersError] = useState('');
    const [usersLoading, setUsersLoading] = useState(true);
    const [msg, setMsg] = useState({ type: '', text: '' });
    const [confirmActive, setConfirmActive] = useState(false);

    const notify = useCallback((type, text) => {
        setMsg({ type, text });
        setTimeout(() => setMsg({ type: '', text: '' }), 4000);
    }, []);

    const loadPartner = useCallback(async () => {
        try {
            const res = await apiGet('/api/admin/partners');
            const found = (res.partners || []).find((p) => String(p.id) === String(partnerId));
            if (!found) { setPartnerState('missing'); return; }
            setPartner(found);
            setPartnerState('ready');
        } catch (e) {
            setPartnerError(e.message || 'Failed to load partner');
            setPartnerState('error');
        }
    }, [partnerId]);

    const loadSeats = useCallback(async () => {
        setSeatsLoading(true);
        setSeatsError('');
        try { setSeats((await apiGet(`/api/admin/partners/${partnerId}/seats`)).seats || []); }
        catch (e) { setSeatsError(e.message || 'Failed to load seats'); }
        finally { setSeatsLoading(false); }
    }, [partnerId]);

    const loadUsers = useCallback(async () => {
        setUsersLoading(true);
        setUsersError('');
        try { setUsers((await apiGet(`/api/admin/partners/${partnerId}/users`)).users || []); }
        catch (e) { setUsersError(e.message || 'Failed to load logins'); }
        finally { setUsersLoading(false); }
    }, [partnerId]);

    useEffect(() => { loadPartner(); loadSeats(); loadUsers(); }, [loadPartner, loadSeats, loadUsers]);

    async function setPartnerActive() {
        setConfirmActive(false);
        try {
            await apiPatch(`/api/admin/partners/${partner.id}`, { is_active: !partner.is_active });
            notify('success', partner.is_active ? 'Partner deactivated.' : 'Partner reactivated.');
            loadPartner();
        } catch (e) { notify('error', e.message || 'Action failed.'); }
    }

    if (partnerState === 'missing') {
        return (
            <>
                <AdminPageHeader context="Customers" title="Partner not found" />
                <AdminNotice tone="warning" title="This partner does not exist" action={<Link className="btn-secondary" href="/dashboard/partners">Back to partners</Link>} />
            </>
        );
    }

    return (
        <>
            <AdminPageHeader
                context={<Link href="/dashboard/partners">← Partners</Link>}
                title={partner?.name || 'Partner'}
                description={partner ? `${partner.slug} · ${partner.contact_email || 'no contact email'}` : undefined}
                actions={partner && (
                    <button type="button" className={partner.is_active ? 'btn-danger' : 'btn-primary'} onClick={() => setConfirmActive(true)}>
                        {partner.is_active ? 'Deactivate partner' : 'Reactivate partner'}
                    </button>
                )}
            />
            {msg.text && <div className={`toast ${msg.type === 'error' ? 'toast-error' : 'toast-success'}`} role="status">{msg.text}</div>}
            {confirmActive && partner && (
                <ConfirmModal
                    title={`${partner.is_active ? 'Deactivate' : 'Reactivate'} ${partner.name}?`}
                    description={partner.is_active
                        ? 'All of their logins stop working on the next request. Client seats and customer accounts are not changed.'
                        : 'Their logins work again.'}
                    confirmLabel={partner.is_active ? 'Deactivate' : 'Reactivate'}
                    variant={partner.is_active ? 'danger' : 'warning'}
                    onConfirm={setPartnerActive} onCancel={() => setConfirmActive(false)} />
            )}

            <AdminDataState loading={partnerState === 'loading'} error={partnerState === 'error' ? partnerError : ''} onRetry={loadPartner}>
                {partner && (
                    <>
                        {!partner.is_active && (
                            <AdminNotice tone="warning" title="This partner is inactive">Their logins are blocked until you reactivate them.</AdminNotice>
                        )}
                        <AdminMetricStrip items={[
                            { label: 'Seats used', value: `${partner.seats_used} / ${partner.seat_cap}`, tone: partner.seats_used >= partner.seat_cap ? 'warning' : 'neutral' },
                            { label: 'Live clients', value: partner.seats_active },
                            { label: 'Awaiting activation', value: partner.seats_requested, tone: partner.seats_requested ? 'warning' : 'neutral' },
                            { label: 'Est. monthly wholesale', value: formatInr(partner.seats_active * (partner.wholesale_price_inr || 0)), detail: `${partner.seats_active} live × ${formatInr(partner.wholesale_price_inr)}` },
                        ]} />
                        <SeatsPanel partner={partner} seats={seats} loading={seatsLoading} error={seatsError}
                            onRetry={loadSeats} onChanged={() => { loadSeats(); loadPartner(); }} notify={notify} />
                        <UsersPanel partner={partner} users={users} loading={usersLoading} error={usersError}
                            onRetry={loadUsers} onChanged={() => { loadUsers(); loadPartner(); }} notify={notify} />
                        <SettingsPanel partner={partner} onSaved={loadPartner} notify={notify} />
                    </>
                )}
            </AdminDataState>
        </>
    );
}
