'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertCircle, CheckCircle2, Compass, Loader2, Lock } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

function getResetMessage(reason) {
    if (reason === 'admin_reset') {
        return 'Your password was reset by an administrator. Please set a new password to continue.';
    }
    if (reason === 'first_time_setup') {
        return 'Please set a new password before accessing your workspace for the first time.';
    }
    return 'Please set a new password to continue.';
}

export default function ForcePasswordResetPage() {
    const router = useRouter();
    const { user, loading, completeForcedPasswordReset } = useAuth();
    const [currentPassword, setCurrentPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState({ type: '', text: '' });

    const allowFallback = useMemo(() => {
        if (typeof window === 'undefined') return false;
        return sessionStorage.getItem('needle_force_reset_required') === '1';
    }, []);

    useEffect(() => {
        if (loading) return;
        if (!user && !allowFallback) router.replace('/');
        if (user && !user.must_change_password) router.replace('/dashboard');
    }, [allowFallback, loading, router, user]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setMessage({ type: '', text: '' });
        if (newPassword !== confirmPassword) {
            setMessage({ type: 'error', text: 'New passwords do not match.' });
            return;
        }
        if (newPassword.length < 8) {
            setMessage({ type: 'error', text: 'Password must be at least 8 characters.' });
            return;
        }
        setSaving(true);
        try {
            await completeForcedPasswordReset(currentPassword, newPassword);
            setMessage({ type: 'success', text: 'Password updated. Redirecting to your dashboard…' });
            setTimeout(() => router.replace('/dashboard'), 700);
        } catch (err) {
            setMessage({ type: 'error', text: err.message || 'Could not update password.' });
        } finally {
            setSaving(false);
        }
    };

    if (loading || (!user && !allowFallback)) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-background to-accent/30">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
        );
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-background to-accent/30 p-4">
            <Card className="w-full max-w-md border-0 shadow-xl bg-card/95 backdrop-blur-sm">
                <CardHeader className="space-y-1 pb-4 pt-8 px-8">
                    <div className="flex items-center justify-center mb-4">
                        <div className="h-14 w-14 rounded-2xl flex items-center justify-center shadow-lg bg-primary shadow-primary/20">
                            <Compass className="h-7 w-7 text-primary-foreground" />
                        </div>
                    </div>
                    <CardTitle className="text-2xl font-bold text-center text-foreground">
                        Set a new password
                    </CardTitle>
                    <CardDescription className="text-center text-muted-foreground">
                        {getResetMessage(user?.force_password_reason)}
                    </CardDescription>
                </CardHeader>

                <CardContent className="px-8 pb-8">
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="current-password">Current or temporary password</Label>
                            <Input
                                id="current-password"
                                type="password"
                                value={currentPassword}
                                onChange={(e) => setCurrentPassword(e.target.value)}
                                placeholder="Enter the password you used to sign in"
                                required
                                autoComplete="current-password"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="new-password">New password</Label>
                            <Input
                                id="new-password"
                                type="password"
                                value={newPassword}
                                onChange={(e) => setNewPassword(e.target.value)}
                                placeholder="Minimum 8 characters"
                                required
                                autoComplete="new-password"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="confirm-password">Confirm new password</Label>
                            <Input
                                id="confirm-password"
                                type="password"
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                placeholder="Re-enter new password"
                                required
                                autoComplete="new-password"
                            />
                        </div>

                        {message.text && (
                            <div className={`flex items-start gap-2 p-3 rounded-lg border text-sm ${
                                message.type === 'error'
                                    ? 'bg-destructive/10 border-destructive/20 text-destructive'
                                    : 'bg-green-500/10 border-green-500/20 text-green-700 dark:text-green-400'
                            }`}>
                                {message.type === 'error'
                                    ? <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                                    : <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" />
                                }
                                <span>{message.text}</span>
                            </div>
                        )}

                        <Button type="submit" disabled={saving} className="w-full h-11 text-base font-semibold">
                            {saving
                                ? <><Loader2 className="h-4 w-4 animate-spin" /> Updating…</>
                                : <><Lock className="h-4 w-4" /> Set new password</>
                            }
                        </Button>
                    </form>
                </CardContent>
            </Card>
        </div>
    );
}
