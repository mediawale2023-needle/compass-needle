'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2, AlertCircle } from 'lucide-react';
import { usePartnerSession } from '@/lib/partnerSession';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

function ErrorLine({ message }) {
    if (!message) return null;
    return (
        <div role="alert" className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{message}</span>
        </div>
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
        <form onSubmit={submit} className="space-y-4">
            <div className="space-y-2">
                <Label htmlFor="partner-email">Work email</Label>
                <Input id="partner-email" type="email" autoComplete="username" required value={email}
                    onChange={(e) => setEmail(e.target.value)} placeholder="you@yourfirm.in" />
            </div>
            <div className="space-y-2">
                <Label htmlFor="partner-password">Password</Label>
                <Input id="partner-password" type="password" autoComplete="current-password" required value={password}
                    onChange={(e) => setPassword(e.target.value)} placeholder="Enter your password" />
            </div>
            <ErrorLine message={error} />
            <Button type="submit" className="w-full" disabled={busy}>
                {busy ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
                Sign in
            </Button>
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
        <form onSubmit={submit} className="space-y-4">
            <div className="space-y-2">
                <Label htmlFor="current-password">Temporary password</Label>
                <Input id="current-password" type="password" autoComplete="current-password" required value={current}
                    onChange={(e) => setCurrent(e.target.value)} />
            </div>
            <div className="space-y-2">
                <Label htmlFor="new-password">New password</Label>
                <Input id="new-password" type="password" autoComplete="new-password" required value={next}
                    onChange={(e) => setNext(e.target.value)} />
                <p className="text-xs text-muted-foreground">At least 8 characters, with one capital letter and one number.</p>
            </div>
            <div className="space-y-2">
                <Label htmlFor="confirm-password">Confirm new password</Label>
                <Input id="confirm-password" type="password" autoComplete="new-password" required value={confirm}
                    onChange={(e) => setConfirm(e.target.value)} />
            </div>
            <ErrorLine message={error} />
            <Button type="submit" className="w-full" disabled={busy}>
                {busy ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
                Set password and continue
            </Button>
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
        <div className="mx-auto mt-10 w-full max-w-md">
            <Card>
                <CardHeader>
                    <CardTitle className="font-serif text-2xl">{needsChange ? 'Choose a new password' : 'Partner sign in'}</CardTitle>
                    <CardDescription>
                        {needsChange
                            ? 'Your account was created with a temporary password. Set your own to continue.'
                            : 'See every client constituency in one place.'}
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {needsChange ? (
                        <ChangePasswordForm onDone={() => router.push('/partner/dashboard')} />
                    ) : (
                        <SignInForm onDone={(res) => { if (!res.must_change_password) router.push('/partner/dashboard'); }} />
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
