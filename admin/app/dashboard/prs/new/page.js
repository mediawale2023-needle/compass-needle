'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiPost } from '@/lib/api';

export default function CreatePRPage() {
    const router = useRouter();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    const [form, setForm] = useState({
        name: '', display_name: '', username: '', password: '',
        constituency: '', state: '', party: '', whatsapp_number: '',
        languages: 'English, Hindi', key_facts: '', alt_names: '',
    });

    const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!form.name || !form.username || !form.password) { setError('Fill all required fields'); return; }
        setLoading(true);
        setError('');
        try {
            await apiPost('/api/admin/prs', {
                name: form.name,
                username: form.username,
                password: form.password,
                constituency: form.constituency || 'General',
                whatsapp_number: form.whatsapp_number,
                display_name: form.display_name || form.name,
                state: form.state,
                party: form.party || 'Independent',
                languages: form.languages ? form.languages.split(',').map(s => s.trim()).filter(Boolean) : ['English', 'Hindi'],
                key_facts: form.key_facts ? form.key_facts.split('\n').map(s => s.trim()).filter(Boolean) : [],
                alt_names: form.alt_names ? form.alt_names.split(',').map(s => s.trim()).filter(Boolean) : [],
            });
            setSuccess(`Created Ambassador: ${form.name} — redirecting…`);
            setTimeout(() => router.push('/dashboard'), 1500);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            <div style={{ marginBottom: '1.5rem' }}>
                <button className="btn-secondary" onClick={() => router.push('/dashboard')} style={{ fontSize: '0.8rem', padding: '6px 14px' }}>
                    ← Back to Overview
                </button>
            </div>

            <form onSubmit={handleSubmit}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: '1.25rem' }}>
                    {/* Left Column */}
                    <div className="glass-panel">
                        <div className="section-title">Identity & Login</div>

                        <div className="form-row">
                            <label className="form-label">Full Name *</label>
                            <input className="form-input" placeholder="Name of PR/Aspirant" value={form.name} onChange={set('name')} required />
                        </div>
                        <div className="form-row">
                            <label className="form-label">Display Name</label>
                            <input className="form-input" placeholder="Dashboard display name" value={form.display_name} onChange={set('display_name')} />
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
                            <div>
                                <label className="form-label">Username *</label>
                                <input className="form-input" placeholder="username" value={form.username} onChange={set('username')} required />
                            </div>
                            <div>
                                <label className="form-label">Password *</label>
                                <input className="form-input" type="password" value={form.password} onChange={set('password')} required />
                            </div>
                        </div>
                        <div className="form-row">
                            <label className="form-label">Area / Constituency</label>
                            <input className="form-input" placeholder="e.g. Pune City" value={form.constituency} onChange={set('constituency')} />
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
                            <div>
                                <label className="form-label">State</label>
                                <input className="form-input" placeholder="e.g. Maharashtra" value={form.state} onChange={set('state')} />
                            </div>
                            <div>
                                <label className="form-label">Party</label>
                                <input className="form-input" placeholder="e.g. BJP, INC" value={form.party} onChange={set('party')} />
                            </div>
                        </div>
                        <div className="form-row">
                            <label className="form-label">WhatsApp Number</label>
                            <input className="form-input" placeholder="+91…" value={form.whatsapp_number} onChange={set('whatsapp_number')} />
                        </div>
                    </div>

                    {/* Right Column */}
                    <div className="glass-panel">
                        <div className="section-title">Profile Data</div>

                        <div className="form-row">
                            <label className="form-label">Languages <span style={{ fontWeight: 400, color: '#94a3b8' }}>(comma-separated)</span></label>
                            <input className="form-input" placeholder="English, Hindi, Marathi" value={form.languages} onChange={set('languages')} />
                        </div>
                        <div className="form-row">
                            <label className="form-label">Key Facts <span style={{ fontWeight: 400, color: '#94a3b8' }}>(one per line)</span></label>
                            <textarea className="form-input" placeholder="Focuses on youth employment&#10;Based in urban center" rows={5} value={form.key_facts} onChange={set('key_facts')} />
                        </div>
                        <div className="form-row">
                            <label className="form-label">Alt Names / Locations <span style={{ fontWeight: 400, color: '#94a3b8' }}>(comma-separated)</span></label>
                            <input className="form-input" placeholder="Camp, Deccan" value={form.alt_names} onChange={set('alt_names')} />
                        </div>
                    </div>
                </div>

                {error && <div className="toast toast-error">{error}</div>}
                {success && <div className="toast toast-success">{success}</div>}

                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <button type="submit" className="btn-primary" disabled={loading} style={{ padding: '10px 32px', fontSize: '0.88rem' }}>
                        {loading ? 'Creating…' : 'Create Ambassador'}
                    </button>
                </div>
            </form>
        </>
    );
}
