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
        if (!form.name || !form.username || !form.password) {
            setError('Fill all required fields');
            return;
        }
        setLoading(true);
        setError('');
        try {
            const payload = {
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
            };
            await apiPost('/api/admin/prs', payload);
            setSuccess(`Created PR: ${form.name}`);
            setTimeout(() => router.push('/dashboard'), 1500);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: '1.5rem' }}>
                <button className="btn-secondary" onClick={() => router.push('/dashboard')}>← Back</button>
                <div className="section-title" style={{ margin: 0, border: 'none', paddingBottom: 0 }}>Create PR (Needle AI Login)</div>
            </div>

            <form onSubmit={handleSubmit}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
                    {/* Left Column */}
                    <div className="glass-panel">
                        <h3 style={{ color: '#1a2e28', fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>Identity & Login</h3>

                        <div style={{ marginBottom: 12 }}>
                            <label className="form-label">Full Name *</label>
                            <input className="form-input" placeholder="Name of PR/Aspirant" value={form.name} onChange={set('name')} required />
                        </div>
                        <div style={{ marginBottom: 12 }}>
                            <label className="form-label">Display Name</label>
                            <input className="form-input" placeholder="Dashboard display name" value={form.display_name} onChange={set('display_name')} />
                        </div>
                        
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                            <div>
                                <label className="form-label">Username *</label>
                                <input className="form-input" placeholder="username" value={form.username} onChange={set('username')} required />
                            </div>
                            <div>
                                <label className="form-label">Password *</label>
                                <input className="form-input" type="password" value={form.password} onChange={set('password')} required />
                            </div>
                        </div>

                        <div style={{ marginBottom: 12 }}>
                            <label className="form-label">Area / Constituency</label>
                            <input className="form-input" placeholder="e.g. Pune City" value={form.constituency} onChange={set('constituency')} />
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                            <div>
                                <label className="form-label">State</label>
                                <input className="form-input" placeholder="e.g. Maharashtra" value={form.state} onChange={set('state')} />
                            </div>
                            <div>
                                <label className="form-label">Party</label>
                                <input className="form-input" placeholder="e.g. BJP, INC" value={form.party} onChange={set('party')} />
                            </div>
                        </div>
                        <div style={{ marginBottom: 12 }}>
                            <label className="form-label">WhatsApp</label>
                            <input className="form-input" placeholder="+91..." value={form.whatsapp_number} onChange={set('whatsapp_number')} />
                        </div>
                    </div>

                    {/* Right Column */}
                    <div className="glass-panel">
                        <h3 style={{ color: '#1a2e28', fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>Profile Data</h3>

                        <div style={{ marginBottom: 12 }}>
                            <label className="form-label">Languages (comma-separated)</label>
                            <input className="form-input" placeholder="English, Hindi, Marathi" value={form.languages} onChange={set('languages')} />
                        </div>
                        <div style={{ marginBottom: 12 }}>
                            <label className="form-label">Key Facts (one per line)</label>
                            <textarea className="form-input" placeholder="Focuses on youth employment\nBased in urban center" rows={4} value={form.key_facts} onChange={set('key_facts')} />
                        </div>
                        <div style={{ marginBottom: 12 }}>
                            <label className="form-label">Alt Names/Locations (comma-separated)</label>
                            <input className="form-input" placeholder="Camp, Deccan" value={form.alt_names} onChange={set('alt_names')} />
                        </div>
                    </div>
                </div>

                {error && <div style={{ background: 'rgba(220,38,38,0.06)', border: '1px solid rgba(220,38,38,0.15)', color: '#dc2626', padding: '10px 14px', borderRadius: 10, fontSize: '0.82rem', marginTop: '1rem' }}>{error}</div>}
                {success && <div style={{ background: 'rgba(5,150,105,0.06)', border: '1px solid rgba(5,150,105,0.15)', color: '#059669', padding: '10px 14px', borderRadius: 10, fontSize: '0.82rem', marginTop: '1rem' }}>{success}</div>}

                <div style={{ marginTop: '1.5rem', textAlign: 'right' }}>
                    <button type="submit" className="btn-primary" disabled={loading} style={{ padding: '12px 32px', fontSize: '0.9rem' }}>
                        {loading ? 'Creating...' : 'Create PR Profile'}
                    </button>
                </div>
            </form>
        </>
    );
}
