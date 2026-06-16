'use client';
import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { apiGet, apiPost, apiPatch } from '@/lib/api';

function timeAgo(isoStr) {
    if (!isoStr || isoStr === 'Never') return isoStr || '—';
    const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
    return `${Math.floor(diff / 86400)} days ago`;
}

function formatDate(isoStr) {
    if (!isoStr || isoStr === 'Never') return isoStr || '—';
    try {
        return new Date(isoStr).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
    } catch { return isoStr; }
}

export default function MpDetailPage() {
    const params = useParams();
    const tenantId = params.tenant_id;
    const [data, setData] = useState(null);
    const [notes, setNotes] = useState([]);
    const [newNote, setNewNote] = useState('');
    const [saving, setSaving] = useState(false);
    const [toast, setToast] = useState('');
    const [supportAccess, setSupportAccess] = useState([]);
    const [supportReason, setSupportReason] = useState('Investigating an operator issue in the tenant workspace.');
    const [supportDuration, setSupportDuration] = useState(30);
    const [supportLoading, setSupportLoading] = useState(false);
    const [launchingKey, setLaunchingKey] = useState('');

    // WhatsApp config edit state
    const [waEditing, setWaEditing] = useState(false);
    const [waNumber, setWaNumber] = useState('');
    const [waPhoneId, setWaPhoneId] = useState('');
    const [waSaving, setWaSaving] = useState(false);

    // Add staff state
    const [addingStaff, setAddingStaff] = useState(false);
    const [staffForm, setStaffForm] = useState({ username: '', password: '', display_name: '', role: 'staff', phone: '' });
    const [staffSaving, setStaffSaving] = useState(false);

    const loadSupportAccess = async () => {
        try {
            const result = await apiGet(`/api/admin/mps/${tenantId}/support-access`);
            setSupportAccess(result.requests || []);
        } catch {}
    };

    useEffect(() => {
        apiGet(`/api/admin/mps/${tenantId}/detail`).then(d => {
            setData(d);
            setWaNumber(d?.profile?.whatsapp_number || '');
            setWaPhoneId(d?.profile?.phone_number_id || '');
        }).catch(() => {});
        apiGet(`/api/admin/mps/${tenantId}/notes`).then(r => setNotes(r.notes || [])).catch(() => {});
        loadSupportAccess();
    }, [tenantId]);

    useEffect(() => {
        const intervalId = window.setInterval(() => {
            loadSupportAccess();
        }, 15000);
        return () => window.clearInterval(intervalId);
    }, [tenantId]);

    const saveWhatsApp = async () => {
        if (!waNumber.trim()) { setToast('WhatsApp number is required'); setTimeout(() => setToast(''), 3000); return; }
        if (!waNumber.startsWith('+')) { setToast('Number must start with + (e.g. +919876543210)'); setTimeout(() => setToast(''), 3000); return; }
        setWaSaving(true);
        try {
            await apiPatch(`/api/admin/mps/${tenantId}/whatsapp`, {
                whatsapp_number: waNumber.trim(),
                phone_number_id: waPhoneId.trim(),
            });
            // Refresh data to confirm saved values
            const fresh = await apiGet(`/api/admin/mps/${tenantId}/detail`);
            setData(fresh);
            setWaNumber(fresh?.profile?.whatsapp_number || '');
            setWaPhoneId(fresh?.profile?.phone_number_id || '');
            setWaEditing(false);
            setToast('WhatsApp settings saved');
            setTimeout(() => setToast(''), 3000);
        } catch (e) {
            setToast(e.message || 'Failed to save WhatsApp settings');
            setTimeout(() => setToast(''), 4000);
        }
        setWaSaving(false);
    };

    const addStaff = async () => {
        if (!staffForm.username.trim()) { setToast('Username is required'); setTimeout(() => setToast(''), 3000); return; }
        if (!staffForm.password) { setToast('Password is required'); setTimeout(() => setToast(''), 3000); return; }
        setStaffSaving(true);
        try {
            await apiPost('/api/admin/staff', {
                tenant_id: parseInt(tenantId),
                username: staffForm.username.trim(),
                password: staffForm.password,
                display_name: staffForm.display_name.trim(),
                role: staffForm.role,
                phone: staffForm.phone.trim(),
            });
            // Refresh detail to update staff roster
            const fresh = await apiGet(`/api/admin/mps/${tenantId}/detail`);
            setData(fresh);
            setAddingStaff(false);
            setStaffForm({ username: '', password: '', display_name: '', role: 'staff', phone: '' });
            setToast(`@${staffForm.username} added to team`);
            setTimeout(() => setToast(''), 3000);
        } catch (e) {
            setToast(e.message || 'Failed to create staff');
            setTimeout(() => setToast(''), 4000);
        }
        setStaffSaving(false);
    };

    const addNote = async () => {
        if (!newNote.trim()) return;
        setSaving(true);
        try {
            await apiPost(`/api/admin/mps/${tenantId}/notes`, { body: newNote.trim() });
            setNewNote('');
            const r = await apiGet(`/api/admin/mps/${tenantId}/notes`);
            setNotes(r.notes || []);
            setToast('Note added');
            setTimeout(() => setToast(''), 3000);
        } catch (e) {
            setToast('Failed to add note');
            setTimeout(() => setToast(''), 3000);
        }
        setSaving(false);
    };

    const createSupportRequest = async () => {
        const reason = supportReason.trim();
        if (!reason) {
            setToast('Support reason is required');
            setTimeout(() => setToast(''), 3000);
            return;
        }
        setSupportLoading(true);
        try {
            await apiPost(`/api/admin/mps/${tenantId}/support-access/request`, {
                reason,
                duration_minutes: supportDuration,
            });
            await loadSupportAccess();
            setToast('Support request sent to tenant for approval');
            setTimeout(() => setToast(''), 3000);
        } catch (e) {
            setToast(e.message || 'Failed to send support request');
            setTimeout(() => setToast(''), 4000);
        }
        setSupportLoading(false);
    };

    const launchSupportSession = async (requestKey) => {
        setLaunchingKey(requestKey);
        try {
            const launch = await apiPost(`/api/admin/support-access/${requestKey}/launch`, {});
            const mpBase = process.env.NEXT_PUBLIC_MP_DASHBOARD_URL || 'http://localhost:3000';
            const url = `${mpBase}/support-access?request=${encodeURIComponent(launch.request_key)}&launch_token=${encodeURIComponent(launch.launch_token)}`;
            window.open(url, '_blank', 'noopener,noreferrer');
            setToast('Support session opened in a new tab');
            setTimeout(() => setToast(''), 3000);
            await loadSupportAccess();
        } catch (e) {
            setToast(e.message || 'Failed to open support session');
            setTimeout(() => setToast(''), 4000);
        }
        setLaunchingKey('');
    };

    const cancelSupportRequest = async (requestKey) => {
        setLaunchingKey(requestKey);
        try {
            await apiPost(`/api/admin/support-access/${requestKey}/cancel`, {});
            setToast('Support request cancelled');
            setTimeout(() => setToast(''), 3000);
            await loadSupportAccess();
        } catch (e) {
            setToast(e.message || 'Failed to cancel support request');
            setTimeout(() => setToast(''), 4000);
        }
        setLaunchingKey('');
    };

    if (!data) {
        return (
            <div style={{ display: 'grid', gap: 16 }}>
                {[...Array(3)].map((_, i) => (
                    <div key={i} className="glass-panel skeleton" style={{ height: 120 }} />
                ))}
            </div>
        );
    }

    const p = data.profile || {};
    const isLS = p.house === 'Lok Sabha';
    const accountBadge = data?.account_stage === 'aspirant'
        ? `Aspirant ${data?.seat_label || ''}`.trim()
        : (data?.seat_label || p.house || 'MP');

    return (
        <>
            {toast && <div className={`toast ${toast.includes('Failed') ? 'toast-error' : 'toast-success'}`}>{toast}</div>}

            {/* Breadcrumb */}
            <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', color: '#6b7f76' }}>
                <Link href="/dashboard" style={{ color: '#006a4d', textDecoration: 'none' }}>Overview</Link>
                <span>›</span>
                <span>{p.mp_name || 'MP Detail'}</span>
            </div>

            {/* Profile Summary */}
            <div id="profile" className="glass-panel" style={{ marginBottom: 16, scrollMarginTop: 96 }}>
                <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
                    <div style={{
                        width: 56, height: 56, borderRadius: 14,
                        background: isLS ? 'linear-gradient(135deg, #006a4d, #00875f)' : 'linear-gradient(135deg, #8d153a, #b91c50)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        color: 'white', fontWeight: 700, fontSize: '1.2rem', flexShrink: 0,
                    }}>
                        {(p.mp_name || '?').split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase()}
                    </div>
                    <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                            <h2 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700, color: '#1a2e28' }}>
                                {p.mp_name || '—'}
                            </h2>
                            <span className={`badge ${isLS ? 'badge-green' : 'badge-red'}`}>{accountBadge}</span>
                        </div>
                        <div style={{ display: 'flex', gap: 20, fontSize: '0.78rem', color: '#6b7f76', flexWrap: 'wrap', alignItems: 'center' }}>
                            <span><strong>Constituency:</strong> {p.constituency || '—'}</span>
                            <span><strong>State:</strong> {p.state || '—'}</span>
                            <span><strong>Party:</strong> {p.party || '—'}</span>
                            <span><strong>Stage:</strong> {data?.account_stage || 'elected'}</span>
                            <span style={{
                                fontFamily: 'monospace', fontSize: '0.72rem', fontWeight: 700,
                                background: '#f0f4f1', color: '#006a4d',
                                borderRadius: 5, padding: '2px 8px', border: '1px solid #d1e8df',
                            }}>
                                Tenant #{data?.tenant_id ?? tenantId}
                            </span>
                        </div>
                        {p.key_facts && p.key_facts.length > 0 && (
                            <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                                {p.key_facts.slice(0, 5).map((f, i) => (
                                    <span key={i} className="badge badge-slate" style={{ fontSize: '0.68rem' }}>{f}</span>
                                ))}
                            </div>
                        )}
                    </div>
                    <Link href={`/dashboard/mps/${tenantId}/setup`}
                        className="btn-secondary"
                        style={{ textDecoration: 'none', fontSize: '0.78rem', padding: '6px 14px', flexShrink: 0 }}>
                        Setup Checklist
                    </Link>
                </div>
            </div>

            <div className="glass-panel" style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, marginBottom: 14 }}>
                    <div>
                        <h3 className="section-title" style={{ margin: 0, border: 'none', padding: 0 }}>
                            Tenant Operations
                        </h3>
                        <p style={{ margin: '5px 0 0', color: '#6b7f76', fontSize: '0.8rem' }}>
                            Manage this tenant from one place. Seat-wide data stays in Shared Geography; tenant-specific routing and staff stay here.
                        </p>
                    </div>
                    <span style={{
                        fontFamily: 'monospace', fontSize: '0.72rem', fontWeight: 700,
                        background: '#f0f4f1', color: '#006a4d',
                        borderRadius: 5, padding: '3px 8px', border: '1px solid #d1e8df',
                        whiteSpace: 'nowrap',
                    }}>
                        Tenant #{tenantId}
                    </span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 10 }}>
                    <OperationLink
                        href={`/dashboard/accounts/registry?tenant_id=${tenantId}`}
                        title="Profile & credentials"
                        detail="Identity, key facts, password reset"
                    />
                    <OperationLink
                        href="#whatsapp"
                        title="WhatsApp routing"
                        detail={p.whatsapp_number && p.phone_number_id ? 'Number and Meta ID configured' : 'Configure number and Meta ID'}
                    />
                    <OperationLink
                        href="#staff"
                        title="Tenant staff"
                        detail={(data.staff || []).length ? `${data.staff.length} staff account${data.staff.length === 1 ? '' : 's'}` : 'Create the first staff account'}
                    />
                    <OperationLink
                        href={`/dashboard/shared-geography/workspace?tenant_id=${tenantId}`}
                        title="Geography corrections"
                        detail="Tenant corrections plus shared seat geography"
                    />
                    <OperationLink
                        href={`/dashboard/mps/${tenantId}/setup`}
                        title="Launch readiness"
                        detail={data.onboarding_state?.live ? 'Production traffic enabled' : 'Review blockers and smoke test'}
                    />
                </div>
            </div>

            <div className="glass-panel" style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, marginBottom: 14 }}>
                    <div>
                        <h3 className="section-title" style={{ margin: 0, border: 'none', padding: 0 }}>
                            Support Access
                        </h3>
                        <p style={{ margin: '5px 0 0', color: '#6b7f76', fontSize: '0.8rem' }}>
                            Request tenant-approved admin viewing access instead of opening the MP dashboard directly.
                        </p>
                    </div>
                    <span className="badge badge-slate">Tenant-approved</span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '2fr 140px auto', gap: 10, alignItems: 'end', marginBottom: 14 }}>
                    <div>
                        <label style={{ display: 'block', fontSize: '0.65rem', color: '#94a3a0', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 4 }}>
                            Reason shown to tenant
                        </label>
                        <textarea
                            className="form-input"
                            rows={2}
                            value={supportReason}
                            onChange={(e) => setSupportReason(e.target.value)}
                            placeholder="Explain why admin needs temporary workspace access"
                            style={{ minHeight: 58 }}
                        />
                    </div>
                    <div>
                        <label style={{ display: 'block', fontSize: '0.65rem', color: '#94a3a0', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 4 }}>
                            Duration
                        </label>
                        <select
                            className="form-input"
                            value={supportDuration}
                            onChange={(e) => setSupportDuration(Number(e.target.value))}
                        >
                            <option value={15}>15 min</option>
                            <option value={30}>30 min</option>
                            <option value={60}>60 min</option>
                        </select>
                    </div>
                    <button
                        className="btn-primary"
                        style={{ fontSize: '0.78rem', padding: '7px 14px' }}
                        disabled={supportLoading}
                        onClick={createSupportRequest}
                    >
                        {supportLoading ? 'Sending…' : 'Request access'}
                    </button>
                </div>

                <div style={{ display: 'grid', gap: 10 }}>
                    {supportAccess.length === 0 ? (
                        <div style={{ fontSize: '0.78rem', color: '#6b7f76' }}>
                            No recent support-access requests for this tenant.
                        </div>
                    ) : supportAccess.map((request) => {
                        const canLaunch = request.status === 'approved';
                        const canCancel = request.status === 'pending' || request.status === 'approved';
                        return (
                            <div
                                key={request.request_key}
                                style={{
                                    border: '1px solid #e2e8e5',
                                    borderRadius: 10,
                                    padding: '12px 14px',
                                    background: canLaunch ? '#f6fbf7' : '#fbfcfc',
                                }}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
                                    <div>
                                        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 5, flexWrap: 'wrap' }}>
                                            <span className={`badge ${request.status === 'approved' ? 'badge-green' : request.status === 'active' ? 'badge-slate' : request.status === 'rejected' || request.status === 'revoked' || request.status === 'cancelled' || request.status === 'expired' ? 'badge-red' : 'badge-slate'}`}>
                                                {request.status}
                                            </span>
                                            <span style={{ fontSize: '0.72rem', color: '#6b7f76' }}>
                                                {request.duration_minutes || 30} min
                                            </span>
                                            <span style={{ fontSize: '0.72rem', color: '#6b7f76' }}>
                                                Requested {formatDate(request.requested_at)}
                                            </span>
                                        </div>
                                        <div style={{ fontSize: '0.82rem', color: '#1a2e28', lineHeight: 1.5 }}>
                                            {request.reason || 'No reason provided.'}
                                        </div>
                                        <div style={{ fontSize: '0.68rem', color: '#94a3a0', marginTop: 6 }}>
                                            Target account: @{request.target_username}
                                            {request.approved_by_username ? ` · Tenant response by ${request.approved_by_username}` : ''}
                                        </div>
                                    </div>
                                    <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                                        {canCancel && (
                                            <button
                                                className="btn-secondary"
                                                style={{ fontSize: '0.74rem', padding: '6px 12px' }}
                                                disabled={launchingKey === request.request_key}
                                                onClick={() => cancelSupportRequest(request.request_key)}
                                            >
                                                Cancel
                                            </button>
                                        )}
                                        {canLaunch && (
                                            <button
                                                className="btn-primary"
                                                style={{ fontSize: '0.74rem', padding: '6px 12px' }}
                                                disabled={launchingKey === request.request_key}
                                                onClick={() => launchSupportSession(request.request_key)}
                                            >
                                                {launchingKey === request.request_key ? 'Opening…' : 'Open tenant view'}
                                            </button>
                                        )}
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Quick Stats Row */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10, marginBottom: 16 }}>
                <QuickStat label="Last Login" value={timeAgo(data.last_login)} />
                <QuickStat label="Total Cases" value={data.cases?.total || 0} />
                <QuickStat label="Open Cases" value={data.cases?.open || 0} accent={data.cases?.open > 0 ? '#d97706' : null} />
                <QuickStat label="Resolved" value={data.cases?.resolved || 0} accent="#059669" />
                <QuickStat label="Last WhatsApp" value={timeAgo(data.last_whatsapp)} />
            </div>

            {/* WhatsApp Configuration Panel */}
            <div id="whatsapp" className="glass-panel" style={{ marginBottom: 16, scrollMarginTop: 96 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: waEditing ? 14 : 0 }}>
                    <h3 className="section-title" style={{ margin: 0, border: 'none', padding: 0 }}>
                        WhatsApp Configuration
                    </h3>
                    {!waEditing && (
                        <button
                            className="btn-secondary"
                            style={{ fontSize: '0.78rem', padding: '5px 14px' }}
                            onClick={() => setWaEditing(true)}
                        >
                            Edit
                        </button>
                    )}
                </div>

                {!waEditing ? (
                    <div style={{ display: 'flex', gap: 32, marginTop: 12, fontSize: '0.82rem', color: '#1a2e28', flexWrap: 'wrap' }}>
                        <div>
                            <div style={{ fontSize: '0.65rem', color: '#94a3a0', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 4 }}>
                                WhatsApp Number
                            </div>
                            <div style={{ fontWeight: 600, fontFamily: 'monospace' }}>
                                {p.whatsapp_number || <span style={{ color: '#94a3a0', fontStyle: 'italic', fontFamily: 'inherit' }}>Not set</span>}
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: '0.65rem', color: '#94a3a0', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 4 }}>
                                Meta Phone Number ID
                            </div>
                            <div style={{ fontWeight: 600, fontFamily: 'monospace' }}>
                                {p.phone_number_id || <span style={{ color: '#94a3a0', fontStyle: 'italic', fontFamily: 'inherit' }}>Not set</span>}
                            </div>
                        </div>
                    </div>
                ) : (
                    <div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                            <div>
                                <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 600, color: '#4a5f58', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                    WhatsApp Number *
                                </label>
                                <input
                                    className="form-input"
                                    type="tel"
                                    placeholder="+919876543210"
                                    value={waNumber}
                                    onChange={e => setWaNumber(e.target.value)}
                                    style={{ fontFamily: 'monospace' }}
                                />
                                <div style={{ fontSize: '0.67rem', color: '#94a3a0', marginTop: 4 }}>
                                    Must start with + country code. Unique across all MPs.
                                </div>
                            </div>
                            <div>
                                <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 600, color: '#4a5f58', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                    Meta Phone Number ID
                                </label>
                                <input
                                    className="form-input"
                                    type="text"
                                    placeholder="e.g. 089911394213487"
                                    value={waPhoneId}
                                    onChange={e => setWaPhoneId(e.target.value)}
                                    style={{ fontFamily: 'monospace' }}
                                />
                                <div style={{ fontSize: '0.67rem', color: '#94a3a0', marginTop: 4 }}>
                                    From Meta Business Suite → WhatsApp → Phone Numbers.
                                </div>
                            </div>
                        </div>
                        <div style={{ display: 'flex', gap: 8 }}>
                            <button
                                className="btn-primary"
                                style={{ fontSize: '0.78rem', padding: '6px 18px' }}
                                disabled={waSaving}
                                onClick={saveWhatsApp}
                            >
                                {waSaving ? 'Saving…' : 'Save'}
                            </button>
                            <button
                                className="btn-secondary"
                                style={{ fontSize: '0.78rem', padding: '6px 14px' }}
                                disabled={waSaving}
                                onClick={() => {
                                    setWaNumber(p.whatsapp_number || '');
                                    setWaPhoneId(p.phone_number_id || '');
                                    setWaEditing(false);
                                }}
                            >
                                Cancel
                            </button>
                        </div>
                    </div>
                )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                {/* Left: Activity Timeline */}
                <div className="glass-panel">
                    <h3 className="section-title">Recent Activity</h3>
                    {(!data.activity || data.activity.length === 0) ? (
                        <div className="empty-state" style={{ padding: '1.5rem' }}>
                            <div className="empty-state-desc">No activity recorded yet</div>
                        </div>
                    ) : (
                        <div style={{ maxHeight: 360, overflowY: 'auto' }}>
                            {data.activity.map((a, i) => (
                                <div key={i} style={{
                                    display: 'flex', gap: 10, padding: '8px 0',
                                    borderBottom: i < data.activity.length - 1 ? '1px solid #f0f4f1' : 'none',
                                }}>
                                    <div style={{
                                        width: 8, height: 8, borderRadius: '50%',
                                        background: '#006a4d', flexShrink: 0, marginTop: 5,
                                    }} />
                                    <div style={{ flex: 1 }}>
                                        <div style={{ fontSize: '0.78rem', fontWeight: 500, color: '#1a2e28' }}>
                                            {a.title || a.activity_type}
                                        </div>
                                        <div style={{ fontSize: '0.68rem', color: '#94a3a0' }}>
                                            {timeAgo(a.created_at)} · {a.activity_type?.replace(/_/g, ' ')}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Right: Staff & Notes */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    {/* Staff Roster */}
                    <div id="staff" className="glass-panel" style={{ scrollMarginTop: 96 }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                            <h3 className="section-title" style={{ margin: 0, border: 'none', padding: 0 }}>
                                Staff Roster
                                {data.staff && data.staff.length > 0 && (
                                    <span style={{ marginLeft: 8, fontSize: '0.72rem', fontWeight: 600, color: '#006a4d', background: '#f0fdf4', borderRadius: 20, padding: '2px 8px' }}>
                                        {data.staff.length}
                                    </span>
                                )}
                            </h3>
                            <button className="btn-secondary" style={{ fontSize: '0.72rem', padding: '4px 12px' }}
                                onClick={() => setAddingStaff(v => !v)}>
                                {addingStaff ? 'Cancel' : '+ Add'}
                            </button>
                        </div>

                        {addingStaff && (
                            <div style={{ marginBottom: 14, padding: '12px', background: '#f8fdf9', borderRadius: 8, border: '1px solid #d1e8df' }}>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
                                    <div>
                                        <label style={{ display: 'block', fontSize: '0.65rem', fontWeight: 600, color: '#4a5f58', marginBottom: 3, textTransform: 'uppercase' }}>Username *</label>
                                        <input className="form-input" placeholder="pa_ravi" value={staffForm.username}
                                            onChange={e => setStaffForm(f => ({ ...f, username: e.target.value }))}
                                            style={{ fontSize: '0.8rem', padding: '5px 8px' }} />
                                    </div>
                                    <div>
                                        <label style={{ display: 'block', fontSize: '0.65rem', fontWeight: 600, color: '#4a5f58', marginBottom: 3, textTransform: 'uppercase' }}>Display Name</label>
                                        <input className="form-input" placeholder="Full name" value={staffForm.display_name}
                                            onChange={e => setStaffForm(f => ({ ...f, display_name: e.target.value }))}
                                            style={{ fontSize: '0.8rem', padding: '5px 8px' }} />
                                    </div>
                                    <div>
                                        <label style={{ display: 'block', fontSize: '0.65rem', fontWeight: 600, color: '#4a5f58', marginBottom: 3, textTransform: 'uppercase' }}>Password *</label>
                                        <input className="form-input" type="password" placeholder="Min 8 chars" value={staffForm.password}
                                            onChange={e => setStaffForm(f => ({ ...f, password: e.target.value }))}
                                            style={{ fontSize: '0.8rem', padding: '5px 8px' }} />
                                    </div>
                                    <div>
                                        <label style={{ display: 'block', fontSize: '0.65rem', fontWeight: 600, color: '#4a5f58', marginBottom: 3, textTransform: 'uppercase' }}>Role</label>
                                        <select className="form-input" value={staffForm.role}
                                            onChange={e => setStaffForm(f => ({ ...f, role: e.target.value }))}
                                            style={{ fontSize: '0.8rem', padding: '5px 8px' }}>
                                            <option value="staff">staff</option>
                                            <option value="manager">manager</option>
                                            <option value="user">user</option>
                                        </select>
                                    </div>
                                </div>
                                <div style={{ marginBottom: 8 }}>
                                    <label style={{ display: 'block', fontSize: '0.65rem', fontWeight: 600, color: '#4a5f58', marginBottom: 3, textTransform: 'uppercase' }}>
                                        WhatsApp Number <span style={{ fontWeight: 400, color: '#94a3a0', textTransform: 'none' }}>(optional — enables PA case queries)</span>
                                    </label>
                                    <input className="form-input" type="tel" placeholder="+919876543210" value={staffForm.phone}
                                        onChange={e => setStaffForm(f => ({ ...f, phone: e.target.value }))}
                                        style={{ fontSize: '0.8rem', padding: '5px 8px', fontFamily: 'monospace' }} />
                                </div>
                                <button className="btn-primary" style={{ fontSize: '0.78rem', padding: '5px 16px' }}
                                    disabled={staffSaving} onClick={addStaff}>
                                    {staffSaving ? 'Creating…' : 'Create Staff Account'}
                                </button>
                            </div>
                        )}

                        {(!data.staff || data.staff.length === 0) ? (
                            <div style={{ fontSize: '0.78rem', color: '#6b7f76' }}>
                                No staff assigned. Click "+ Add" to create one.
                            </div>
                        ) : (
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Name</th><th>Role</th><th>WhatsApp</th><th>Status</th><th>Last Login</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.staff.map(s => (
                                        <tr key={s.id}>
                                            <td>
                                                <div style={{ fontWeight: 500 }}>{s.display_name || s.username}</div>
                                                <div style={{ fontSize: '0.7rem', color: '#94a3a0' }}>@{s.username}</div>
                                            </td>
                                            <td><span className="badge badge-slate">{s.role}</span></td>
                                            <td style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: s.phone ? '#1a2e28' : '#94a3a0' }}>
                                                {s.phone || '—'}
                                            </td>
                                            <td><span className={`badge badge-dot ${s.is_active ? 'badge-green' : 'badge-red'}`}>{s.is_active ? 'Active' : 'Suspended'}</span></td>
                                            <td style={{ fontSize: '0.72rem', color: '#94a3a0' }}>{timeAgo(s.last_login)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>

                    {/* Admin Notes */}
                    <div className="glass-panel" style={{ flex: 1 }}>
                        <h3 className="section-title">Admin Notes</h3>
                        {/* Add note */}
                        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                            <textarea
                                className="form-input"
                                rows={2}
                                placeholder="Add a note about this account..."
                                value={newNote}
                                onChange={e => setNewNote(e.target.value)}
                                style={{ flex: 1, minHeight: 50 }}
                            />
                            <button className="btn-primary" disabled={saving || !newNote.trim()} onClick={addNote}
                                style={{ alignSelf: 'flex-end', padding: '7px 16px', fontSize: '0.78rem' }}>
                                {saving ? '...' : 'Add'}
                            </button>
                        </div>
                        {/* Notes list */}
                        <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                            {notes.length === 0 && (
                                <div style={{ fontSize: '0.78rem', color: '#94a3a0' }}>No notes yet</div>
                            )}
                            {notes.map(n => (
                                <div key={n.id} style={{
                                    padding: '8px 0',
                                    borderBottom: '1px solid #f0f4f1',
                                }}>
                                    <div style={{ fontSize: '0.78rem', color: '#1a2e28', lineHeight: 1.5 }}>{n.body}</div>
                                    <div style={{ fontSize: '0.65rem', color: '#94a3a0', marginTop: 3 }}>
                                        {n.admin_username} · {formatDate(n.created_at)}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
}

function QuickStat({ label, value, accent }) {
    return (
        <div className="stat-card" style={{ padding: '0.9rem 1rem' }}>
            <div style={{ fontSize: '0.65rem', color: '#94a3a0', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 4 }}>
                {label}
            </div>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: accent || '#1a2e28' }}>
                {value ?? '—'}
            </div>
        </div>
    );
}

function OperationLink({ href, title, detail }) {
    return (
        <Link
            href={href}
            className="btn-secondary"
            style={{
                display: 'block',
                textAlign: 'left',
                textDecoration: 'none',
                padding: '11px 12px',
                borderRadius: 8,
                minHeight: 74,
            }}
        >
            <span style={{ display: 'block', color: '#1a2e28', fontSize: '0.82rem', fontWeight: 800, marginBottom: 4 }}>
                {title}
            </span>
            <span style={{ display: 'block', color: '#6b7f76', fontSize: '0.72rem', lineHeight: 1.45, fontWeight: 500 }}>
                {detail}
            </span>
        </Link>
    );
}
