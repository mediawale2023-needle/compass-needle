'use client';
import { useState, useEffect } from 'react';
import { apiGet, apiPost, apiPatch, apiDelete } from '@/lib/api';

export default function AnnouncementsPage() {
    const [announcements, setAnnouncements] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [actionMsg, setActionMsg] = useState('');
    const [form, setForm] = useState({ title: '', body: '' });
    const [submitting, setSubmitting] = useState(false);

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
        setTimeout(() => setActionMsg(''), 3000);
    };

    const handleCreate = async (e) => {
        e.preventDefault();
        if (!form.title.trim()) return;
        setSubmitting(true);
        try {
            const created = await apiPost('/api/admin/announcements', form);
            setAnnouncements(prev => [created, ...prev]);
            setForm({ title: '', body: '' });
            showMsg('Announcement created and published.');
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
        if (!confirm('Delete this announcement? This cannot be undone.')) return;
        try {
            await apiDelete(`/api/admin/announcements/${id}`);
            setAnnouncements(prev => prev.filter(a => a.id !== id));
            showMsg('Announcement deleted.');
        } catch (err) {
            showMsg(`Error: ${err.message}`);
        }
    };

    return (
        <>
            <div className="section-title">Announcements</div>
            <p style={{ color: '#6b7f76', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
                Compose banners that appear on all MP dashboards. Active announcements are shown immediately.
            </p>

            {actionMsg && (
                <div style={{ padding: '10px 16px', background: '#ecfdf5', border: '1px solid #a7f3d0', borderRadius: 8, color: '#065f46', marginBottom: '1rem', fontSize: '0.85rem' }}>
                    {actionMsg}
                </div>
            )}

            {error && (
                <div style={{ padding: '10px 16px', background: '#fff1f2', border: '1px solid #fecdd3', borderRadius: 8, color: '#be123c', marginBottom: '1rem', fontSize: '0.85rem' }}>
                    {error}
                </div>
            )}

            {/* Composer */}
            <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                <h3 style={{ fontWeight: 700, color: '#1a2e28', marginBottom: '1rem', fontSize: '0.95rem' }}>
                    📢 New Announcement
                </h3>
                <form onSubmit={handleCreate}>
                    <div style={{ marginBottom: '0.75rem' }}>
                        <label style={{ fontSize: '0.8rem', color: '#6b7f76', fontWeight: 600, display: 'block', marginBottom: 4 }}>
                            Title <span style={{ color: '#e11d48' }}>*</span>
                        </label>
                        <input
                            className="form-input"
                            value={form.title}
                            onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                            placeholder="e.g. Scheduled maintenance on Saturday"
                            required
                            style={{ width: '100%' }}
                        />
                    </div>
                    <div style={{ marginBottom: '1rem' }}>
                        <label style={{ fontSize: '0.8rem', color: '#6b7f76', fontWeight: 600, display: 'block', marginBottom: 4 }}>
                            Body <span style={{ fontSize: '0.75rem', fontWeight: 400 }}>(optional)</span>
                        </label>
                        <textarea
                            className="form-input"
                            value={form.body}
                            onChange={e => setForm(f => ({ ...f, body: e.target.value }))}
                            placeholder="Additional details shown below the title…"
                            rows={2}
                            style={{ width: '100%', resize: 'vertical' }}
                        />
                    </div>
                    <button className="btn-primary" type="submit" disabled={submitting || !form.title.trim()}>
                        {submitting ? 'Publishing…' : 'Publish Announcement'}
                    </button>
                </form>
            </div>

            {/* List */}
            {loading ? (
                <div style={{ textAlign: 'center', padding: '2rem', color: '#6b7f76' }}>Loading…</div>
            ) : announcements.length === 0 ? (
                <div className="glass-panel" style={{ textAlign: 'center', color: '#6b7f76', padding: '2rem' }}>
                    No announcements yet. Create one above.
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {announcements.map(a => (
                        <div
                            key={a.id}
                            className="glass-panel"
                            style={{
                                display: 'flex', alignItems: 'flex-start', gap: '1rem',
                                opacity: a.is_active ? 1 : 0.6,
                                borderLeft: `4px solid ${a.is_active ? '#006a4d' : '#94a3b8'}`,
                                padding: '1rem 1.2rem',
                            }}
                        >
                            <div style={{ flex: 1 }}>
                                <div style={{ fontWeight: 700, color: '#1a2e28', marginBottom: a.body ? 4 : 0 }}>
                                    {a.title}
                                </div>
                                {a.body && (
                                    <div style={{ fontSize: '0.83rem', color: '#6b7f76' }}>{a.body}</div>
                                )}
                                <div style={{ fontSize: '0.73rem', color: '#94a3b8', marginTop: 6 }}>
                                    Created {a.created_at ? new Date(a.created_at).toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
                                </div>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                                <span style={{
                                    padding: '3px 10px', borderRadius: 20,
                                    background: a.is_active ? '#ecfdf5' : '#f8fafc',
                                    color: a.is_active ? '#065f46' : '#64748b',
                                    fontSize: '0.73rem', fontWeight: 600,
                                }}>
                                    {a.is_active ? '● Live' : '○ Inactive'}
                                </span>
                                <button
                                    onClick={() => handleToggle(a)}
                                    style={{ padding: '4px 10px', borderRadius: 6, border: '1px solid #e2ebe5', background: '#fff', color: '#1a2e28', fontSize: '0.75rem', cursor: 'pointer', fontFamily: 'inherit' }}
                                >
                                    {a.is_active ? 'Deactivate' : 'Activate'}
                                </button>
                                <button
                                    onClick={() => handleDelete(a.id)}
                                    style={{ padding: '4px 10px', borderRadius: 6, border: 'none', background: '#fff1f2', color: '#be123c', fontSize: '0.75rem', cursor: 'pointer', fontFamily: 'inherit', fontWeight: 600 }}
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
