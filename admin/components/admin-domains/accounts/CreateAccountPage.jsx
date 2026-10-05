'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { apiGet, apiPost } from '@/lib/api';

export default function CreateAccountPage() {
    const router = useRouter();
    const [constituencies, setConstituencies] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [step, setStep] = useState(1);

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

    const stepValid = () => {
        if (step === 1) return Boolean(form.name && form.state);
        if (step === 2) return Boolean(form.username && form.password);
        return true;
    };

    const nextStep = () => {
        if (!stepValid()) {
            setError(step === 1 ? 'Name and State are required before continuing' : 'Username and Password are required before continuing');
            return;
        }
        setError('');
        setStep((current) => Math.min(4, current + 1));
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
            setSuccess(`Created ${form.name}. The account must set a new password on first login — redirecting to setup checklist…`);
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
                <button className="btn-secondary" onClick={() => router.push('/dashboard/accounts')} style={{ fontSize: '0.8rem', padding: '6px 14px' }}>
                    ← Back to Accounts
                </button>
            </div>

            <form onSubmit={handleSubmit} className="onboarding-flow">
                <div className="onboarding-progress" aria-label="Account onboarding progress">
                    {[
                        ['Identity', 'Who this account represents'],
                        ['Access', 'Login and seat assignment'],
                        ['Configure', 'Messaging and intelligence profile'],
                        ['Review', 'Validate before creation'],
                    ].map(([label, detail], index) => {
                        const number = index + 1;
                        return (
                            <button key={label} type="button" className={step === number ? 'active' : step > number ? 'complete' : ''}
                                onClick={() => number < step && setStep(number)}>
                                <span>{step > number ? '✓' : number}</span><b>{label}</b><small>{detail}</small>
                            </button>
                        );
                    })}
                </div>

                <div className="glass-panel onboarding-stage">
                    {step === 1 && <>
                        <div className="section-title">1. Account identity</div>
                        <p className="onboarding-help">Start with the minimum information needed to identify the customer and political seat.</p>
                        <div className="onboarding-form-grid">
                            <div className="form-row"><label className="form-label">Account Stage *</label>
                                <select className="form-input" value={form.account_stage} onChange={set('account_stage')}><option value="elected">Elected</option><option value="aspirant">Aspirant</option></select>
                            </div>
                            <div className="form-row"><label className="form-label">Seat Type *</label>
                                <select className="form-input" value={form.seat_type} onChange={set('seat_type')}><option value="mp">MP Seat</option><option value="mla">MLA Seat</option></select>
                            </div>
                            <div className="form-row onboarding-span-2"><label className="form-label">{form.account_stage === 'aspirant' ? 'Candidate / Leader Name *' : `${form.seat_type === 'mla' ? 'MLA' : 'MP'} Full Name *`}</label>
                                <input className="form-input" placeholder="Hon. Shri/Smt…" value={form.name} onChange={set('name')} required />
                            </div>
                            <div className="form-row"><label className="form-label">Display Name</label><input className="form-input" placeholder="Dashboard display name" value={form.display_name} onChange={set('display_name')} /></div>
                            <div className="form-row"><label className="form-label">State *</label><input className="form-input" placeholder="e.g. Karnataka" value={form.state} onChange={set('state')} required /></div>
                            <div className="form-row onboarding-span-2"><label className="form-label">Party</label><input className="form-input" placeholder="e.g. BJP, INC" value={form.party} onChange={set('party')} /></div>
                        </div>
                    </>}

                    {step === 2 && <>
                        <div className="section-title">2. Seat & access</div>
                        <p className="onboarding-help">Assign the constituency and create the primary login. The user will change the temporary password on first login.</p>
                        <div className="onboarding-form-grid">
                            <div className="form-row"><label className="form-label">House *</label>
                                {form.seat_type === 'mla' ? <input className="form-input" value="Vidhan Sabha" disabled /> :
                                <select className="form-input" value={form.house} onChange={set('house')}><option value="Lok Sabha">Lok Sabha</option><option value="Rajya Sabha">Rajya Sabha</option></select>}
                            </div>
                            <div className="form-row">
                                <label className="form-label">{form.seat_type === 'mp' && form.house === 'Lok Sabha' ? 'Parliamentary Constituency *' : form.seat_type === 'mla' ? 'Assembly Seat Name' : 'State / Nominated'}</label>
                                {form.seat_type === 'mp' && form.house === 'Lok Sabha' ?
                                <select className="form-input" value={form.constituency} onChange={set('constituency')}><option value="">Select…</option>{constituencies.map(c => <option key={c} value={c}>{c}</option>)}</select> :
                                <input className="form-input" value={form.constituency} onChange={set('constituency')} />}
                            </div>
                            <div className="form-row"><label className="form-label">Username *</label><input className="form-input" value={form.username} onChange={set('username')} required /></div>
                            <div className="form-row"><label className="form-label">Temporary Password *</label><input className="form-input" type="password" value={form.password} onChange={set('password')} required /></div>
                        </div>
                    </>}

                    {step === 3 && <>
                        <div className="section-title">3. Configure account</div>
                        <p className="onboarding-help">These settings improve messaging and intelligence, but can be completed later from Account 360.</p>
                        <div className="onboarding-form-grid">
                            <div className="form-row onboarding-span-2"><label className="form-label">WhatsApp Number</label><input className="form-input" placeholder="+91…" value={form.whatsapp_number} onChange={set('whatsapp_number')} /></div>
                            <div className="form-row onboarding-span-2"><label className="form-label">Languages</label><input className="form-input" placeholder="English, Hindi, Kannada" value={form.languages} onChange={set('languages')} /></div>
                            <div className="form-row onboarding-span-2"><label className="form-label">Key Facts</label><textarea className="form-input" rows={5} value={form.key_facts} onChange={set('key_facts')} /></div>
                            <div className="form-row onboarding-span-2"><label className="form-label">Alternate Constituency Names</label><input className="form-input" placeholder="Belagavi, Belgaum" value={form.alt_names} onChange={set('alt_names')} /></div>
                        </div>
                    </>}

                    {step === 4 && <>
                        <div className="section-title">4. Review & create</div>
                        <p className="onboarding-help">Creating the account does not bypass the existing setup checklist. Launch validation still happens after creation.</p>
                        <div className="onboarding-review">
                            <ReviewRow label="Account" value={form.display_name || form.name || '—'} />
                            <ReviewRow label="Stage" value={form.account_stage} />
                            <ReviewRow label="Seat" value={`${form.seat_type.toUpperCase()} · ${form.house}`} />
                            <ReviewRow label="Constituency" value={form.constituency || 'India'} />
                            <ReviewRow label="State / Party" value={`${form.state || '—'} · ${form.party || 'Independent'}`} />
                            <ReviewRow label="Username" value={form.username || '—'} />
                            <ReviewRow label="WhatsApp" value={form.whatsapp_number || 'Configure later'} />
                            <ReviewRow label="Languages" value={form.languages || 'English, Hindi'} />
                        </div>
                        <div className="onboarding-next-note"><strong>After creation</strong><span>Needle opens the account setup checklist to validate routing, staff, geography and production readiness before launch.</span></div>
                    </>}
                </div>

                {error && <div className="toast toast-error">{error}</div>}
                {success && <div className="toast toast-success">{success}</div>}

                <div className="onboarding-actions">
                    <button type="button" className="btn-secondary" disabled={step === 1 || loading} onClick={() => { setError(''); setStep((current) => Math.max(1, current - 1)); }}>Back</button>
                    {step < 4 ? <button type="button" className="btn-primary" onClick={nextStep}>Continue</button> :
                    <button type="submit" className="btn-primary" disabled={loading}>{loading ? 'Creating…' : 'Create Account & Continue Setup'}</button>}
                </div>
            </form>
        </>
    );
}


function ReviewRow({ label, value }) { return <div><span>{label}</span><strong>{value}</strong></div>; }
