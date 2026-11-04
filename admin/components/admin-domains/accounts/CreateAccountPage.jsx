'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowLeft, ArrowRight, Pencil } from 'lucide-react';
import { apiGet, apiPost } from '@/lib/api';
import {
    applyRole, buildCreatePayload, constituencyMode, formReadiness, INITIAL_ACCOUNT_FORM, ONBOARDING_STEPS,
    ROLE_OPTIONS, roleValue, validateForCreate, validateStep,
} from '@/lib/admin-data';
import {
    Callout, Card, Field, PageHeader, RadioCards, ReadinessIcon, ReadinessList, SegmentedControl, Select, Stepper, TextInput,
} from '@/components/admin-ui';
import '@/app/styles/admin-onboarding.css';

const STAGE_COPY = {
    1: { title: 'Identity', description: 'Who this account represents. Staff see this name in the MP dashboard and citizens see it in WhatsApp replies.' },
    2: { title: 'Seat & Access', description: 'Assign the seat and create the primary login. The account holder sets a new password on first login.' },
    3: { title: 'Configure', description: 'Optional settings that improve messaging and intelligence. All of them can be completed later from Account 360.' },
    4: { title: 'Review & Create', description: 'Check everything below. Nothing is created until you confirm.' },
};

const NEXT_HINT = {
    1: 'Next: assign the seat and primary login',
    2: 'Next: messaging and AI context (optional)',
    3: 'Next: review everything before creating',
};

const UPCOMING = {
    2: 'Assign the seat and create the primary login',
    3: 'WhatsApp number, reply languages, key facts and alternate names',
    4: 'Review, resolve anything missing, then confirm Create account',
};

function Fieldset({ legend, children }) {
    return (
        <fieldset className="nx-ob-fieldset">
            <legend>{legend}</legend>
            {children}
        </fieldset>
    );
}

function ReviewGroup({ title, step, onEdit, rows }) {
    return (
        <section className="nx-ob-review-group" aria-label={title}>
            <div className="nx-ob-review-head">
                <h3>{title}</h3>
                <button type="button" className="nx-btn nx-btn-ghost nx-btn-sm" onClick={() => onEdit(step)}>
                    <Pencil size={14} aria-hidden="true" />Edit<span className="nx-sr-only"> {title}</span>
                </button>
            </div>
            <dl>
                {rows.map(([label, value, muted]) => (
                    <div key={label}>
                        <dt>{label}</dt>
                        <dd data-muted={muted ? 'true' : undefined}>{value}</dd>
                    </div>
                ))}
            </dl>
        </section>
    );
}

export default function CreateAccountPage() {
    const router = useRouter();
    const [constituencies, setConstituencies] = useState([]);
    const [constituencyState, setConstituencyState] = useState('loading');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [step, setStep] = useState(1);
    const [form, setForm] = useState(INITIAL_ACCOUNT_FORM);

    useEffect(() => {
        apiGet('/api/admin/constituencies')
            .then((r) => { setConstituencies(r.constituencies || []); setConstituencyState('ready'); })
            .catch(() => setConstituencyState('error'));
    }, []);

    const set = (key) => (event) => {
        const value = event?.target ? event.target.value : event;
        setForm((prev) => ({ ...prev, [key]: value }));
    };

    const goTo = (target) => {
        setError('');
        setStep(target);
        if (typeof window !== 'undefined') window.scrollTo?.({ top: 0, behavior: 'smooth' });
    };

    const nextStep = () => {
        const problem = validateStep(form, step);
        if (problem) { setError(problem); return; }
        goTo(Math.min(4, step + 1));
    };

    const handleSubmit = async (event) => {
        event.preventDefault();
        // Creation is an explicit final action: only the Create button on the
        // review step submits. Enter in a field (or any other submit) advances.
        const submitter = event.nativeEvent?.submitter;
        if (step < 4 || (submitter && submitter.dataset?.action !== 'create')) { if (step < 4) nextStep(); return; }
        const problem = validateForCreate(form);
        if (problem) { setError(problem); return; }
        setLoading(true);
        setError('');
        try {
            const result = await apiPost('/api/admin/mps', buildCreatePayload(form));
            setSuccess(`Created ${form.name}. The account must set a new password on first login — redirecting to setup checklist…`);
            const tid = result?.tenant_id;
            setTimeout(() => router.push(tid ? `/dashboard/mps/${tid}/setup` : '/dashboard'), 1500);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const readiness = useMemo(() => formReadiness(form), [form]);
    const requiredItems = readiness.filter((item) => item.key === 'identity' || item.key === 'access');
    const requiredDone = requiredItems.filter((item) => item.state === 'complete').length;
    const createProblem = validateForCreate(form);
    const mode = constituencyMode(form);
    const role = ROLE_OPTIONS.find((option) => option.value === roleValue(form));
    const steps = ONBOARDING_STEPS.map((item, index) => ({
        label: item.label,
        detail: item.detail,
        state: index + 1 < step ? 'done' : index + 1 === step ? 'current' : 'todo',
    }));
    const copy = STAGE_COPY[step];

    return (
        <div className="nx-ob">
            <PageHeader
                title="New account"
                description="Set up a political account and its tenant"
                actions={<Link href="/dashboard/accounts" className="nx-btn nx-btn-ghost">Cancel</Link>}
            />

            <Card className="nx-ob-stepper">
                <Stepper label="Onboarding steps" steps={steps} onSelect={(index) => goTo(index + 1)} />
            </Card>

            <div className="nx-ob-layout">
                <div className="nx-ob-main">
                    <form className="nx-card nx-ob-form" onSubmit={handleSubmit} aria-labelledby="nx-ob-stage-title" noValidate>
                        <div className="nx-ob-form-head">
                            <div className="nx-eyebrow">Step {step} of 4</div>
                            <h2 id="nx-ob-stage-title">{copy.title}</h2>
                            <p>{copy.description}</p>
                        </div>

                        <div aria-live="polite">
                            {step === 1 && (
                                <>
                                    <Fieldset legend="Person">
                                        <div className="nx-ob-grid">
                                            <Field label={form.account_stage === 'aspirant' ? 'Candidate / leader name' : `${form.seat_type === 'mla' ? 'MLA' : 'MP'} full name`} required>
                                                {(props) => <TextInput {...props} placeholder="Hon. Shri/Smt…" value={form.name} onChange={set('name')} autoComplete="off" />}
                                            </Field>
                                            <Field label="Display name" optional help="Shown in the MP dashboard. Defaults to the full name.">
                                                {(props) => <TextInput {...props} placeholder="Dashboard display name" value={form.display_name} onChange={set('display_name')} />}
                                            </Field>
                                        </div>
                                    </Fieldset>
                                    <Fieldset legend="Role">
                                        <div className="nx-field">
                                            <span className="nx-label">Elected role <span className="nx-req" aria-hidden="true">*</span></span>
                                            <RadioCards name="role" label="Elected role" columns={3} value={roleValue(form)} onChange={(value) => setForm((prev) => applyRole(prev, value))}
                                                options={ROLE_OPTIONS.map((option) => ({ value: option.value, label: option.label, detail: option.detail }))} />
                                        </div>
                                        <div className="nx-ob-grid">
                                            <div className="nx-field">
                                                <span className="nx-label" id="nx-ob-stage-label">Account stage <span className="nx-req" aria-hidden="true">*</span></span>
                                                <SegmentedControl mode="radio" fill label="Account stage" value={form.account_stage} onChange={set('account_stage')}
                                                    options={[{ value: 'elected', label: 'Elected' }, { value: 'aspirant', label: 'Aspirant' }]} />
                                            </div>
                                            <Field label="Party or affiliation" optional help="Defaults to Independent.">
                                                {(props) => <TextInput {...props} placeholder="e.g. BJP, INC" value={form.party} onChange={set('party')} />}
                                            </Field>
                                        </div>
                                    </Fieldset>
                                    <Fieldset legend="Location">
                                        <div className="nx-ob-grid">
                                            <Field label="State" required>
                                                {(props) => <TextInput {...props} placeholder="e.g. Karnataka" value={form.state} onChange={set('state')} />}
                                            </Field>
                                        </div>
                                    </Fieldset>
                                </>
                            )}

                            {step === 2 && (
                                <>
                                    <Fieldset legend="Seat">
                                        <div className="nx-ob-grid">
                                            <div className="nx-field">
                                                <span className="nx-label">House</span>
                                                <div className="nx-ob-static">
                                                    <span>{role ? `${role.label} · ${role.detail}` : form.house}</span>
                                                    <button type="button" className="nx-link nx-ob-static-link" onClick={() => goTo(1)}>Change role</button>
                                                </div>
                                            </div>
                                            <Field
                                                label={mode.label}
                                                optional
                                                help={constituencyState === 'error' && mode.kind === 'select' ? 'Constituency list could not be loaded — try again later.' : 'If left blank the account is created for India.'}
                                            >
                                                {(props) => (mode.kind === 'select'
                                                    ? <Select {...props} value={form.constituency} onChange={set('constituency')} placeholder={constituencyState === 'loading' ? 'Loading constituencies…' : 'Select…'} options={constituencies} />
                                                    : <TextInput {...props} value={form.constituency} onChange={set('constituency')} />)}
                                            </Field>
                                        </div>
                                    </Fieldset>
                                    <Fieldset legend="Primary login">
                                        <div className="nx-ob-grid">
                                            <Field label="Username" required>
                                                {(props) => <TextInput {...props} value={form.username} onChange={set('username')} autoComplete="off" />}
                                            </Field>
                                            <Field label="Temporary password" required help="The account must set a new password on first login.">
                                                {(props) => <TextInput {...props} type="password" value={form.password} onChange={set('password')} autoComplete="new-password" />}
                                            </Field>
                                        </div>
                                    </Fieldset>
                                </>
                            )}

                            {step === 3 && (
                                <>
                                    <Fieldset legend="Messaging">
                                        <div className="nx-ob-grid">
                                            <Field label="WhatsApp number" optional help="The Meta phone number ID is added after creation in WhatsApp settings.">
                                                {(props) => <TextInput {...props} placeholder="+91…" value={form.whatsapp_number} onChange={set('whatsapp_number')} inputMode="tel" />}
                                            </Field>
                                            <Field label="Reply languages" optional help="Comma-separated.">
                                                {(props) => <TextInput {...props} placeholder="English, Hindi, Kannada" value={form.languages} onChange={set('languages')} />}
                                            </Field>
                                        </div>
                                    </Fieldset>
                                    <Fieldset legend="AI context">
                                        <Field label="Key facts" optional help="One per line. Used by drafting, Copilot and constituency intelligence.">
                                            {(props) => <textarea {...props} className="nx-input nx-textarea" rows={5} value={form.key_facts} onChange={set('key_facts')} />}
                                        </Field>
                                        <div className="nx-ob-gap" />
                                        <Field label="Alternate constituency names" optional help="Comma-separated spellings citizens use.">
                                            {(props) => <TextInput {...props} placeholder="Belagavi, Belgaum" value={form.alt_names} onChange={set('alt_names')} />}
                                        </Field>
                                    </Fieldset>
                                </>
                            )}

                            {step === 4 && (
                                <div className="nx-ob-review">
                                    {createProblem && (
                                        <Callout tone="warning" title="Resolve before creating.">{createProblem}.</Callout>
                                    )}
                                    <ReviewGroup title="Identity" step={1} onEdit={goTo} rows={[
                                        ['Account', form.display_name || form.name || '—', !form.name],
                                        ['Role', role ? `${role.label} · ${role.detail}` : form.house],
                                        ['Stage', form.account_stage === 'aspirant' ? 'Aspirant' : 'Elected'],
                                        ['State / Party', `${form.state || '—'} · ${form.party || 'Independent'}`, !form.state],
                                    ]} />
                                    <ReviewGroup title="Seat & Access" step={2} onEdit={goTo} rows={[
                                        ['Constituency', form.constituency || 'India', !form.constituency],
                                        ['Username', form.username || '—', !form.username],
                                        ['Temporary password', form.password ? 'Set · changed on first login' : '—', !form.password],
                                    ]} />
                                    <ReviewGroup title="Configure" step={3} onEdit={goTo} rows={[
                                        ['WhatsApp', form.whatsapp_number || 'Configure later', !form.whatsapp_number],
                                        ['Languages', form.languages || 'English, Hindi'],
                                        ['Key facts', form.key_facts.trim() ? `${form.key_facts.split('\n').filter((line) => line.trim()).length} added` : 'None yet', !form.key_facts.trim()],
                                    ]} />
                                    <section className="nx-ob-creates" aria-label="What happens next">
                                        <h3>When you create this account</h3>
                                        <ul>
                                            <li>A tenant and its profile are created for this seat.</li>
                                            <li>The primary login is created with the temporary password.</li>
                                            <li>Needle opens the launch setup checklist: geography, staff, WhatsApp routing and a live smoke test. Production traffic stays off until those checks pass.</li>
                                        </ul>
                                    </section>
                                </div>
                            )}
                        </div>

                        {error && <div className="nx-ob-message"><Callout tone="critical">{error}</Callout></div>}
                        {success && <div className="nx-ob-message"><Callout tone="ok">{success}</Callout></div>}

                        <div className="nx-ob-foot">
                            <span className="nx-ob-hint">{step < 4 ? NEXT_HINT[step] : createProblem ? 'Complete the required fields to create the account' : 'Ready to create'}</span>
                            <div className="nx-ob-actions">
                                {step > 1 && (
                                    <button type="button" className="nx-btn" disabled={loading} onClick={() => goTo(step - 1)}>
                                        <ArrowLeft size={16} aria-hidden="true" />Back
                                    </button>
                                )}
                                {step < 4 ? (
                                    <button key="continue" type="button" className="nx-btn nx-btn-primary" onClick={nextStep}>
                                        {`Continue to ${ONBOARDING_STEPS[step].label}`}<ArrowRight size={16} aria-hidden="true" />
                                    </button>
                                ) : (
                                    <button key="create" type="submit" data-action="create" className="nx-btn nx-btn-primary" disabled={loading || Boolean(createProblem) || Boolean(success)}>
                                        {loading ? 'Creating…' : 'Create account and continue setup'}
                                    </button>
                                )}
                            </div>
                        </div>
                    </form>

                    {step < 4 && (
                        <section aria-label="Still to come" className="nx-ob-upcoming">
                            <h2 className="nx-ob-section-title">Still to come</h2>
                            <div className="nx-card">
                                {ONBOARDING_STEPS.slice(step).map((item, offset) => (
                                    <div className="nx-ob-upcoming-row" key={item.key}>
                                        <span className="nx-step-n nx-ob-step-n">{step + offset + 1}</span>
                                        <div>
                                            <strong>{item.label}</strong>
                                            <small>{UPCOMING[step + offset + 1]}</small>
                                        </div>
                                    </div>
                                ))}
                                <div className="nx-ob-upcoming-row">
                                    <span className="nx-ob-after" aria-hidden="true">→</span>
                                    <div>
                                        <strong>Launch setup (after creation)</strong>
                                        <small>Geography, staff, WhatsApp routing and a live smoke test before production traffic</small>
                                    </div>
                                </div>
                            </div>
                        </section>
                    )}
                </div>

                <aside className="nx-card nx-ob-readiness" aria-label="Setup readiness">
                    <div className="nx-card-head">
                        <div>
                            <h2 className="nx-card-title">Setup readiness</h2>
                            <p className="nx-card-description">{requiredDone} of {requiredItems.length} required items complete</p>
                        </div>
                    </div>
                    <div className="nx-ob-readiness-bar" aria-hidden="true">
                        {readiness.slice(0, 5).map((item) => <span key={item.key} data-state={item.state} />)}
                    </div>
                    <ReadinessList items={readiness.map((item) => ({
                        label: item.label,
                        state: item.state,
                        detail: item.detail,
                        aside: item.step ? `Step ${item.step}` : 'After creation',
                    }))} />
                    <div className="nx-ob-legend">
                        {[['complete', 'Complete'], ['progress', 'In progress'], ['todo', 'To do'], ['optional', 'Optional or later']].map(([state, text]) => (
                            <span key={state}><ReadinessIcon state={state} size="sm" />{text}</span>
                        ))}
                    </div>
                </aside>
            </div>
        </div>
    );
}
