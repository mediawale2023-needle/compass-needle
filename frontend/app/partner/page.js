'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { usePartnerSession } from '@/lib/partnerSession';

function ErrorLine({ message }) {
    if (!message) return null;
    return (
        <div role="alert" className="pd-alert">{message}</div>
    );
}

function SignInForm({ onDone }) {
    const { signIn } = usePartnerSession();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');

    async function submit(e) {
        e.preventDefault();
        setBusy(true);
        setError('');
        try {
            const res = await signIn(email, password);
            onDone(res);
        } catch (err) {
            setError(err.message || 'Could not sign in.');
        } finally {
            setBusy(false);
        }
    }

    return (
        <form onSubmit={submit} style={{ display: 'grid', gap: 16 }}>
            <div>
                <label className="pd-label" htmlFor="partner-email">Work email</label>
                <input className="pd-input" id="partner-email" type="email" autoComplete="username" required value={email}
                    onChange={(e) => setEmail(e.target.value)} placeholder="you@yourfirm.in" />
            </div>
            <div>
                <label className="pd-label" htmlFor="partner-password">Password</label>
                <input className="pd-input" id="partner-password" type="password" autoComplete="current-password" required value={password}
                    onChange={(e) => setPassword(e.target.value)} placeholder="Enter your password" />
            </div>
            <ErrorLine message={error} />
            <button type="submit" className="pd-btn primary" style={{ width: '100%', justifyContent: 'center', height: 40 }} disabled={busy}>
                {busy ? 'Signing in…' : 'Sign in'}
            </button>
        </form>
    );
}

function ChangePasswordForm({ onDone }) {
    const { changePassword } = usePartnerSession();
    const [current, setCurrent] = useState('');
    const [next, setNext] = useState('');
    const [confirm, setConfirm] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');

    async function submit(e) {
        e.preventDefault();
        if (next !== confirm) {
            setError('The new passwords do not match.');
            return;
        }
        setBusy(true);
        setError('');
        try {
            await changePassword(current, next);
            onDone();
        } catch (err) {
            setError(err.message || 'Could not change the password.');
        } finally {
            setBusy(false);
        }
    }

    return (
        <form onSubmit={submit} style={{ display: 'grid', gap: 16 }}>
            <div>
                <label className="pd-label" htmlFor="current-password">Temporary password</label>
                <input className="pd-input" id="current-password" type="password" autoComplete="current-password" required value={current}
                    onChange={(e) => setCurrent(e.target.value)} />
            </div>
            <div>
                <label className="pd-label" htmlFor="new-password">New password</label>
                <input className="pd-input" id="new-password" type="password" autoComplete="new-password" required value={next}
                    onChange={(e) => setNext(e.target.value)} />
                <p className="pd-csub" style={{ marginTop: 6 }}>At least 8 characters, with one capital letter and one number.</p>
            </div>
            <div>
                <label className="pd-label" htmlFor="confirm-password">Confirm new password</label>
                <input className="pd-input" id="confirm-password" type="password" autoComplete="new-password" required value={confirm}
                    onChange={(e) => setConfirm(e.target.value)} />
            </div>
            <ErrorLine message={error} />
            <button type="submit" className="pd-btn primary" style={{ width: '100%', justifyContent: 'center', height: 40 }} disabled={busy}>
                Set password and continue
            </button>
        </form>
    );
}

export default function PartnerLoginPage() {
    const router = useRouter();
    const { ready, token, mustChangePassword } = usePartnerSession();

    useEffect(() => {
        if (ready && token && !mustChangePassword) router.replace('/partner/dashboard');
    }, [ready, token, mustChangePassword, router]);

    if (!ready) return null;
    const needsChange = !!token && mustChangePassword;

    return (
        <div className="pd-auth">
            <div className="pd-authcard">
                <div className="pd-authbrand">
                    <span className="pd-mark" aria-hidden="true">P</span>
                    <div><div className="pd-wm-name">Partner workspace</div><div className="pd-wm-sub">Client portfolio</div></div>
                </div>
                <div className="pd-panel" style={{ padding: 28 }}>
                    <h1 className="pd-title" style={{ fontSize: 28, marginTop: 0 }}>{needsChange ? 'Choose a new password' : 'Partner sign in'}</h1>
                    <p className="pd-lede" style={{ marginBottom: 22, fontSize: 14 }}>
                        {needsChange
                            ? 'Your account was created with a temporary password. Set your own to continue.'
                            : 'See every client constituency in one place.'}
                    </p>
                    {needsChange ? (
                        <ChangePasswordForm onDone={() => router.push('/partner/dashboard')} />
                    ) : (
                        <SignInForm onDone={(res) => { if (!res.must_change_password) router.push('/partner/dashboard'); }} />
                    )}
                </div>
                <p className="pd-note" style={{ textAlign: 'center' }}>Locked out? Contact your organisation&apos;s administrator.</p>
            </div>
        </div>
    );
}
