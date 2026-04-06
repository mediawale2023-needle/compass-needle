'use client';

import { useState, useEffect, useRef } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2, Compass, AlertCircle, Wifi, WifiOff, CheckCircle2 } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
const PROBE_INTERVAL_MS = 4000;   // re-ping every 4s while server is unreachable
const PROBE_TIMEOUT_MS  = 5000;   // give each ping 5s before counting as failed

/**
 * Pings /health and resolves true (ok) or false (unreachable).
 * Never throws — a failed probe is a normal state during cold start.
 */
async function probeBackend() {
    try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS);
        const res = await fetch(`${API_BASE}/health`, {
            signal: controller.signal,
            cache: 'no-store',
        });
        clearTimeout(timer);
        return res.ok;
    } catch {
        return false;
    }
}

export default function LoginPage() {
    const { user, login } = useAuth();
    const router = useRouter();
    const [username, setUsername]   = useState('');
    const [password, setPassword]   = useState('');
    const [error, setError]         = useState('');
    const [loading, setLoading]     = useState(false);

    // --- Server connection state ---
    // 'checking'   → first probe in progress
    // 'connecting' → server unreachable, retrying
    // 'ready'      → /health returned 200
    const [serverStatus, setServerStatus] = useState('checking');
    const [retryCount, setRetryCount]     = useState(0);
    const probeTimerRef = useRef(null);

    // Redirect if already authenticated
    useEffect(() => {
        if (user) router.push('/dashboard');
    }, [user, router]);

    // Backend wake-up probe — runs on mount and retries until server is ready
    useEffect(() => {
        let cancelled = false;

        async function runProbe() {
            const ok = await probeBackend();
            if (cancelled) return;
            if (ok) {
                setServerStatus('ready');
            } else {
                setServerStatus('connecting');
                setRetryCount(n => n + 1);
                probeTimerRef.current = setTimeout(runProbe, PROBE_INTERVAL_MS);
            }
        }

        runProbe();

        return () => {
            cancelled = true;
            if (probeTimerRef.current) clearTimeout(probeTimerRef.current);
        };
    }, []);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            await login(username, password);
            router.push('/dashboard');
        } catch (err) {
            const msg = err.message || 'Invalid credentials';
            setError(
                msg.includes('Connection timed out') || msg.includes('try again')
                    ? msg
                    : msg === 'Request failed after retries'
                        ? 'Connection issue. Please try again in a moment.'
                        : msg
            );
        } finally {
            setLoading(false);
        }
    };

    const isServerReady   = serverStatus === 'ready';
    const isServerChecking = serverStatus === 'checking';

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-background to-accent/30 p-4">
            {/* Subtle background pattern */}
            <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiMwMDAiIGZpbGwtb3BhY2l0eT0iMC4wMiI+PGNpcmNsZSBjeD0iMzAiIGN5PSIzMCIgcj0iMiIvPjwvZz48L2c+PC9zdmc+')] opacity-50" />

            <div className="w-full max-w-md relative animate-fade-in">

                {/* ── Server status banner ── */}
                {!isServerReady && (
                    <div className={`mb-3 flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium
                        ${isServerChecking
                            ? 'bg-muted/80 text-muted-foreground border border-border'
                            : 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20'
                        }`}
                    >
                        {isServerChecking ? (
                            <>
                                <Loader2 className="h-4 w-4 animate-spin shrink-0" />
                                <span>Connecting to server…</span>
                            </>
                        ) : (
                            <>
                                <Loader2 className="h-4 w-4 animate-spin shrink-0" />
                                <div>
                                    <p>Server is starting up — please wait.</p>
                                    <p className="text-xs font-normal opacity-75 mt-0.5">
                                        This takes about 30 seconds on first load. Retrying…
                                    </p>
                                </div>
                            </>
                        )}
                    </div>
                )}

                {isServerReady && retryCount > 0 && (
                    <div className="mb-3 flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium bg-green-500/10 text-green-700 dark:text-green-400 border border-green-500/20">
                        <CheckCircle2 className="h-4 w-4 shrink-0" />
                        <span>Server is ready.</span>
                    </div>
                )}

                <Card className="border-0 shadow-xl bg-card/95 backdrop-blur-sm">
                    <CardHeader className="space-y-1 pb-4 pt-8 px-8">
                        <div className="flex items-center justify-center mb-4">
                            <div className={`h-14 w-14 rounded-2xl flex items-center justify-center shadow-lg transition-colors duration-500
                                ${isServerReady
                                    ? 'bg-primary shadow-primary/20'
                                    : 'bg-muted'
                                }`}
                            >
                                {isServerReady
                                    ? <Compass className="h-7 w-7 text-primary-foreground" />
                                    : <Loader2 className="h-7 w-7 text-muted-foreground animate-spin" />
                                }
                            </div>
                        </div>
                        <CardTitle className="text-2xl font-bold text-center text-foreground">
                            Compass Needle
                        </CardTitle>
                        <CardDescription className="text-center text-muted-foreground">
                            Parliamentary Intelligence Platform
                        </CardDescription>
                    </CardHeader>

                    <CardContent className="px-8 pb-8">
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="username" className="text-sm font-medium text-foreground">
                                    Username
                                </Label>
                                <Input
                                    id="username"
                                    type="text"
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    placeholder={isServerReady ? 'Enter your username' : 'Waiting for server…'}
                                    className="h-11 bg-secondary/50 border-input focus-visible:ring-primary"
                                    required
                                    autoFocus
                                    autoComplete="username"
                                    disabled={!isServerReady}
                                />
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="password" className="text-sm font-medium text-foreground">
                                    Password
                                </Label>
                                <Input
                                    id="password"
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder={isServerReady ? 'Enter your password' : 'Waiting for server…'}
                                    className="h-11 bg-secondary/50 border-input focus-visible:ring-primary"
                                    required
                                    autoComplete="current-password"
                                    disabled={!isServerReady}
                                />
                            </div>

                            {error && (
                                <div className="flex items-start gap-2 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
                                    <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                                    <span>{error}</span>
                                </div>
                            )}

                            <Button
                                type="submit"
                                disabled={loading || !isServerReady}
                                className="w-full h-11 text-base font-semibold shadow-md shadow-primary/20 hover:shadow-lg hover:shadow-primary/30 transition-all"
                            >
                                {loading ? (
                                    <>
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                        Signing in…
                                    </>
                                ) : !isServerReady ? (
                                    <>
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                        {isServerChecking ? 'Connecting…' : 'Starting server…'}
                                    </>
                                ) : (
                                    'Sign in'
                                )}
                            </Button>
                        </form>
                    </CardContent>
                </Card>

                <p className="text-center text-xs text-muted-foreground mt-6">
                    Compass Needle · Digital Parliament
                </p>
            </div>
        </div>
    );
}
