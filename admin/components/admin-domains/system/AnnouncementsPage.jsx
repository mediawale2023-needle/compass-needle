'use client';
import { useState, useEffect } from 'react';
import { apiGet, apiPost, apiPatch, apiDelete } from '@/lib/api';
import ConfirmModal from '@/components/ConfirmModal';

export default function AnnouncementsPage() {
    const [announcements, setAnnouncements] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [actionMsg, setActionMsg] = useState('');
    const [form, setForm] = useState({ title: '', body: '' });
    const [submitting, setSubmitting] = useState(false);
    const [deleteAnnouncementId, setDeleteAnnouncementId] = useState(null);

    useEffect(() => {
        loadAnnouncements();
    }, []);

    const loadAnnouncements = () => {
        setLoading(true);
        apiGet('/api/admin/announcements')
            .then(d => setAnnouncements(d.announcements || []))
            .catch(e => setError(e.message || 'Failed to load'))
            .finally(() => setLoading(false));
    };

    const showMsg = (msg) => {
        setActionMsg(msg);
        setTimeout(() => setActionMsg(''), 3500);
    };

    const handleCreate = async (e) => {
        e.preventDefault();
        if (!form.title.trim()) return;
        setSubmitting(true);
        try {
            const created = await apiPost('/api/admin/announcements', form);
            setAnnouncements(prev => [created, ...prev]);
            setForm({ title: '', body: '' });
            showMsg('Announcement published to all MP dashboards.');
        } catch (err) {
            showMsg(`Error: ${err.message}`);
        } finally {
            setSubmitting(false);
        }
    };

    const handleToggle = async (a) => {
        try {
            await apiPatch(`/api/admin/announcements/${a.id}`, { is_active: !a.is_active });
            setAnnouncements(prev => prev.map(x => x.id === a.id ? { ...x, is_active: !x.is_active } : x));
            showMsg(`Announcement ${!a.is_active ? 'activated' : 'deactivated'}.`);
        } catch (err) {
            showMsg(`Error: ${err.message}`);
        }
    };

    const handleDelete = async (id) => {
        setDeleteAnnouncementId(id);
    };

    const confirmDeleteAnnouncement = async () => {
        if (!deleteAnnouncementId) return;
        const id = deleteAnnouncementId;
        setDeleteAnnouncementId(null);
        try {
            await apiDelete(`/api/admin/announcements/${id}`);
            setAnnouncements(prev => prev.filter(a => a.id !== id));
            showMsg('Announcement deleted.');
        } catch (err) {
            showMsg(`Error: ${err.message}`);
        }
    };

    const formatDate = (ts) => ts
        ? new Date(ts).toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
        : '—';

    return (
        <>
            {actionMsg && <div className="toast toast-success">{actionMsg}</div>}
            {error && <div className="toast toast-error">{error}</div>}

            {/* Delete Announcement Modal */}
            {deleteAnnouncementId && (
                <ConfirmModal
                    title="Delete this announcement?"
                    description="This announcement will be permanently removed from all MP dashboards. This action cannot be undone."
                    confirmLabel="Delete"
                    variant="danger"
                    onConfirm={confirmDeleteAnnouncement}
                    onCancel={() => setDeleteAnnouncementId(null)}
                />
            )}

            {/* Composer */}
            <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                <div className="section-title">New Announcement</div>
                <p style={{ color: '#6b7f76', fontSize: '0.8rem', marginTop: -8, marginBottom: '1rem' }}>
                    Active announcements appear as banners on all MP dashboards immediately.
                </p>
                <form onSubmit={handleCreate}>
                    <div className="form-row">
                        <label className="form-label">
                            Title <span style={{ color: '#e11d48' }}>*</span>
                        </label>
                        <input
                            className="form-input"
                            value={form.title}
                            onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                            placeholder="e.g. Scheduled maintenance on Saturday"
                            required
                        />
                    </div>
                    <div className="form-row">
                        <label className="form-label">
                            Body <span style={{ fontWeight: 400, color: '#94a3b8' }}>(optional)</span>
                        </label>
                        <textarea
                            className="form-input"
                            value={form.body}
                            onChange={e => setForm(f => ({ ...f, body: e.target.value }))}
                            placeholder="Additional details shown below the title…"
                            rows={2}
                            style={{ resize: 'vertical' }}
                        />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                        <button className="btn-primary" type="submit" disabled={submitting || !form.title.trim()} style={{ padding: '9px 28px' }}>
                            {submitting ? 'Publishing…' : 'Publish Announcement'}
                        </button>
                    </div>
                </form>
            </div>

            {/* List */}
            {loading ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {[...Array(3)].map((_, i) => <div key={i} className="skeleton" style={{ height: 76, borderRadius: 10 }} />)}
                </div>
            ) : announcements.length === 0 ? (
                <div className="glass-panel">
                    <div className="empty-state">
                        <div className="empty-state-icon">
                            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M22 10.5V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v12c0 1.1.9 2 2 2h12.5"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>
                                <path d="M18 15.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z"/><path d="M20.27 17.27 22 19"/>
                            </svg>
                        </div>
                        <div className="empty-state-title">No announcements yet</div>
                        <div className="empty-state-desc">Create one above — it will appear on all MP dashboards immediately</div>
                    </div>
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {announcements.map(a => (
                        <div
                            key={a.id}
                            className="glass-panel"
                            style={{
                                display: 'flex', alignItems: 'flex-start', gap: '1rem',
                                opacity: a.is_active ? 1 : 0.65,
                                borderLeft: `3px solid ${a.is_active ? '#006a4d' : '#cbd5e1'}`,
                                padding: '14px 18px',
                                transition: 'opacity 0.2s',
                            }}
                        >
                            <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ fontWeight: 600, color: '#1a2e28', marginBottom: a.body ? 4 : 0, fontSize: '0.9rem' }}>
                                    {a.title}
                                </div>
                                {a.body && (
                                    <div style={{ fontSize: '0.82rem', color: '#6b7f76', marginBottom: 6 }}>{a.body}</div>
                                )}
                                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
                                    Published {formatDate(a.created_at)}
                                </div>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                                <span className={`badge badge-dot ${a.is_active ? 'badge-green' : 'badge-slate'}`}>
                                    {a.is_active ? 'Live' : 'Inactive'}
                                </span>
                                <button className="btn-ghost" onClick={() => handleToggle(a)}>
                                    {a.is_active ? 'Deactivate' : 'Activate'}
                                </button>
                                <button
                                    onClick={() => handleDelete(a.id)}
                                    style={{
                                        padding: '5px 10px', borderRadius: 6, border: 'none', cursor: 'pointer',
                                        fontFamily: 'inherit', background: '#fff1f2', color: '#be123c',
                                        fontSize: '0.76rem', fontWeight: 600,
                                    }}
                                >
                                    Delete
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </>
    );
}
