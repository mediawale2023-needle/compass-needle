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
        account_stage: 'elected',
        seat_type: 'mp',
        name: '', display_name: '', house: 'Lok Sabha',
        username: '', password: '', constituency: '',
        state: '', party: '', whatsapp_number: '',
        languages: 'English, Hindi', key_facts: '', alt_names: '',
    });

    useEffect(() => {
        apiGet('/api/admin/constituencies').then(r => setConstituencies(r.constituencies || [])).catch(() => { });
    }, []);

    const set = (k) => (e) => {
        const value = e.target.value;
        setForm((prev) => {
            const next = { ...prev, [k]: value };
            if (k === 'seat_type' && value === 'mla') next.house = 'Vidhan Sabha';
            if (k === 'seat_type' && value === 'mp' && prev.house === 'Vidhan Sabha') next.house = 'Lok Sabha';
            return next;
        });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!form.name || !form.username || !form.password || !form.state) { setError('Name, Username, Password and State are required'); return; }
        setLoading(true);
        setError('');
        try {
            const result = await apiPost('/api/admin/mps', {
                name: form.name,
                username: form.username,
                password: form.password,
                tenant_type: form.account_stage === 'aspirant' ? 'aspirant' : form.seat_type,
                account_stage: form.account_stage,
                seat_type: form.seat_type,
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
            setSuccess(`Created ${form.name} — redirecting to setup checklist…`);
            const tid = result?.tenant_id;
            setTimeout(() => router.push(tid ? `/dashboard/mps/${tid}/setup` : '/dashboard'), 1500);
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
                            <label className="form-label">Account Stage *</label>
                            <select className="form-input" value={form.account_stage} onChange={set('account_stage')}>
                                <option value="elected">Elected</option>
                                <option value="aspirant">Aspirant</option>
                            </select>
                        </div>
                        <div className="form-row">
                            <label className="form-label">Seat Type *</label>
                            <select className="form-input" value={form.seat_type} onChange={set('seat_type')}>
                                <option value="mp">MP Seat</option>
                                <option value="mla">MLA Seat</option>
                            </select>
                        </div>
                        <div className="form-row">
                            <label className="form-label">{form.account_stage === 'aspirant' ? 'Candidate / Leader Name *' : `${form.seat_type === 'mla' ? 'MLA' : 'MP'} Full Name *`}</label>
                            <input className="form-input" placeholder="Hon. Shri/Smt…" value={form.name} onChange={set('name')} required />
                        </div>
                        <div className="form-row">
                            <label className="form-label">Display Name</label>
                            <input className="form-input" placeholder="Dashboard display name" value={form.display_name} onChange={set('display_name')} />
                        </div>
                        <div className="form-row">
                            <label className="form-label">House *</label>
                            {form.seat_type === 'mla' ? (
                                <input className="form-input" value="Vidhan Sabha" disabled />
                            ) : (
                                <select className="form-input" value={form.house} onChange={set('house')}>
                                    <option value="Lok Sabha">Lok Sabha</option>
                                    <option value="Rajya Sabha">Rajya Sabha</option>
                                </select>
                            )}
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

                        {form.seat_type === 'mp' && form.house === 'Lok Sabha' ? (
                            <div className="form-row">
                                <label className="form-label">Parliamentary Constituency *</label>
                                <select className="form-input" value={form.constituency} onChange={set('constituency')}>
                                    <option value="">Select…</option>
                                    {constituencies.map(c => <option key={c} value={c}>{c}</option>)}
                                </select>
                            </div>
                        ) : (
                            <div className="form-row">
                                <label className="form-label">{form.seat_type === 'mla' ? 'Assembly Seat Name' : 'State / Nominated'}</label>
                                <input className="form-input" placeholder="e.g. Maharashtra" value={form.constituency} onChange={set('constituency')} />
                            </div>
                        )}

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
                            <div>
                                <label className="form-label">State *</label>
                                <input className="form-input" placeholder="e.g. Karnataka" value={form.state} onChange={set('state')} required />
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
                        {loading ? 'Creating…' : 'Create Account'}
                    </button>
                </div>
            </form>
        </>
    );
}
