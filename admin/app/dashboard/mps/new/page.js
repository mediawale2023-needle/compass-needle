'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { apiGet, apiPost } from '@/lib/api';

export default function CreateMPPage() {
    const router = useRouter();
    const [constituencies, setConstituencies] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    const [form, setForm] = useState({
        name: '', display_name: '', house: 'Lok Sabha',
        username: '', password: '', constituency: '',
        state: '', party: '', whatsapp_number: '',
        languages: 'English, Hindi', key_facts: '', alt_names: '',
    });

    useEffect(() => {
        apiGet('/api/admin/constituencies').then(r => setConstituencies(r.constituencies || [])).catch(() => { });
    }, []);

    const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!form.name || !form.username || !form.password) { setError('Fill all required fields'); return; }
        setLoading(true);
        setError('');
        try {
            await apiPost('/api/admin/mps', {
                name: form.name,
                username: form.username,
                password: form.password,
                constituency: form.constituency || 'India',
                whatsapp_number: form.whatsapp_number,
                house: form.house,
                display_name: form.display_name || form.name,
                state: form.state,
                party: form.party || 'Independent',
                languages: form.languages ? form.languages.split(',').map(s => s.trim()).filter(Boolean) : ['English', 'Hindi'],
                key_facts: form.key_facts ? form.key_facts.split('\n').map(s => s.trim()).filter(Boolean) : [],
                alt_names: form.alt_names ? form.alt_names.split(',').map(s => s.trim()).filter(Boolean) : [],
            });
            setSuccess(`Created ${form.name} — redirecting…`);
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
                            <label className="form-label">MP Full Name *</label>
                            <input className="form-input" placeholder="Hon. Shri/Smt…" value={form.name} onChange={set('name')} required />
                        </div>
                        <div className="form-row">
                            <label className="form-label">Display Name</label>
                            <input className="form-input" placeholder="Dashboard display name" value={form.display_name} onChange={set('display_name')} />
                        </div>
                        <div className="form-row">
                            <label className="form-label">House *</label>
                            <select className="form-input" value={form.house} onChange={set('house')}>
                                <option value="Lok Sabha">Lok Sabha</option>
                                <option value="Rajya Sabha">Rajya Sabha</option>
                            </select>
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

                        {form.house === 'Lok Sabha' ? (
                            <div className="form-row">
                                <label className="form-label">Parliamentary Constituency *</label>
                                <select className="form-input" value={form.constituency} onChange={set('constituency')}>
                                    <option value="">Select…</option>
                                    {constituencies.map(c => <option key={c} value={c}>{c}</option>)}
                                </select>
                            </div>
                        ) : (
                            <div className="form-row">
                                <label className="form-label">State / Nominated</label>
                                <input className="form-input" placeholder="e.g. Maharashtra" value={form.constituency} onChange={set('constituency')} />
                            </div>
                        )}

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
                            <div>
                                <label className="form-label">State *</label>
                                <input className="form-input" placeholder="e.g. Karnataka" value={form.state} onChange={set('state')} />
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
                            <input className="form-input" placeholder="English, Hindi, Kannada" value={form.languages} onChange={set('languages')} />
                        </div>
                        <div className="form-row">
                            <label className="form-label">Key Facts <span style={{ fontWeight: 400, color: '#94a3b8' }}>(one per line)</span></label>
                            <textarea className="form-input" placeholder="Major industrial hub&#10;Border district" rows={5} value={form.key_facts} onChange={set('key_facts')} />
                        </div>
                        <div className="form-row">
                            <label className="form-label">Alt Constituency Names <span style={{ fontWeight: 400, color: '#94a3b8' }}>(comma-separated)</span></label>
                            <input className="form-input" placeholder="Belagavi, Belgaum" value={form.alt_names} onChange={set('alt_names')} />
                        </div>
                    </div>
                </div>

                {error && <div className="toast toast-error">{error}</div>}
                {success && <div className="toast toast-success">{success}</div>}

                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <button type="submit" className="btn-primary" disabled={loading} style={{ padding: '10px 32px', fontSize: '0.88rem' }}>
                        {loading ? 'Creating…' : 'Create MP'}
                    </button>
                </div>
            </form>
        </>
    );
}
