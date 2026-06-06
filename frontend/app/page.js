'use client';

import { useState, useEffect, useRef } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2, Compass, AlertCircle, CheckCircle2, Eye, EyeOff } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
const PROBE_INTERVAL_MS = 4000;
const PROBE_TIMEOUT_MS  = 5000;

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

function isConnError(msg) {
    return (
        msg.includes('Connection timed out') ||
        msg.includes('try again') ||
        msg.includes('Connection issue') ||
        msg === 'Request failed after retries'
    );
}

export default function LoginPage() {
    const { user, login } = useAuth();
    const router = useRouter();
    const [username, setUsername]   = useState('');
    const [password, setPassword]   = useState('');
    const [rememberMe, setRememberMe] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError]         = useState('');
    const [notice, setNotice]       = useState('');
    const [loading, setLoading]     = useState(false);
    const [retryingLogin, setRetryingLogin] = useState(false);

    const [serverStatus, setServerStatus] = useState('checking');
    const [retryCount, setRetryCount]     = useState(0);
    const probeTimerRef    = useRef(null);
    const loginRetryTimerRef = useRef(null);
    const handleSubmitRef  = useRef(null);

    useEffect(() => {
        if (!user) return;
        if (user.must_change_password) router.push('/force-password-reset');
        else router.push('/dashboard');
    }, [user, router]);

    useEffect(() => {
        if (typeof window === 'undefined') return;
        const storedNotice = sessionStorage.getItem('needle_auth_notice');
        if (storedNotice) {
            setNotice(storedNotice);
            sessionStorage.removeItem('needle_auth_notice');
        }
    }, []);

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

    // When server becomes ready while we're waiting to retry login, fire immediately
    useEffect(() => {
        if (serverStatus === 'ready' && retryingLogin) {
            clearTimeout(loginRetryTimerRef.current);
            handleSubmitRef.current?.();
        }
    }, [serverStatus, retryingLogin]);

    useEffect(() => () => clearTimeout(loginRetryTimerRef.current), []);

    const handleSubmit = async (e) => {
        e?.preventDefault();
        clearTimeout(loginRetryTimerRef.current);
        setRetryingLogin(false);
        setError('');
        setNotice('');
        setLoading(true);
        try {
            const nextUser = await login(username, password, rememberMe);
            if (nextUser?.must_change_password) router.push('/force-password-reset');
            else router.push('/dashboard');
        } catch (err) {
            const msg = err.message || 'Invalid credentials';
            if (isConnError(msg) && serverStatus !== 'ready') {
                // Server still cold-starting — queue a retry instead of showing error
                setRetryingLogin(true);
                loginRetryTimerRef.current = setTimeout(() => handleSubmitRef.current?.(), 6000);
            } else {
                setError(isConnError(msg) ? 'Connection issue. Please try again in a moment.' : msg);
            }
        } finally {
            setLoading(false);
        }
    };

    handleSubmitRef.current = handleSubmit;

    const isServerReady    = serverStatus === 'ready';
    const isServerChecking = serverStatus === 'checking';

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-background to-accent/30 p-4">
            <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiMwMDAiIGZpbGwtb3BhY2l0eT0iMC4wMiI+PGNpcmNsZSBjeD0iMzAiIGN5PSIzMCIgcj0iMiIvPjwvZz48L2c+PC9zdmc+')] opacity-50" />

            <div className="w-full max-w-md relative animate-fade-in">

                {/* Server status banner */}
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
                                    <p>Server is starting up — this may take a moment.</p>
                                    <p className="text-xs font-normal opacity-75 mt-0.5">
                                        You can sign in now — the request will wait for the server automatically.
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

                {notice && (
                    <div className="mb-3 flex items-start gap-2 px-4 py-3 rounded-xl text-sm font-medium bg-green-500/10 text-green-700 dark:text-green-400 border border-green-500/20">
                        <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" />
                        <span>{notice}</span>
                    </div>
                )}

                <Card className="border-0 shadow-xl bg-card/95 backdrop-blur-sm">
                    <CardHeader className="space-y-1 pb-4 pt-8 px-8">
                        <div className="flex items-center justify-center mb-4">
                            <div className="h-14 w-14 rounded-2xl flex items-center justify-center shadow-lg bg-primary shadow-primary/20">
                                <Compass className="h-7 w-7 text-primary-foreground" />
                            </div>
                        </div>
                        <CardTitle className="text-2xl font-bold text-center text-foreground">
                            Compass Needle
                        </CardTitle>
                        <CardDescription className="text-center text-muted-foreground">
                            Grievance Management Platform
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
                                    placeholder="Enter your username"
                                    className="h-11 bg-secondary/50 border-input focus-visible:ring-primary"
                                    required
                                    autoFocus
                                    autoComplete="username"
                                />
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="password" className="text-sm font-medium text-foreground">
                                    Password
                                </Label>
                                <div className="relative">
                                    <Input
                                        id="password"
                                        type={showPassword ? 'text' : 'password'}
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        placeholder="Enter your password"
                                        className="h-11 bg-secondary/50 border-input focus-visible:ring-primary pr-12"
                                        required
                                        autoComplete="current-password"
                                    />
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon"
                                        className="absolute right-1 top-1/2 -translate-y-1/2 h-9 w-9 text-muted-foreground hover:text-foreground"
                                        onClick={() => setShowPassword(v => !v)}
                                        aria-label={showPassword ? 'Hide password' : 'Show password'}
                                    >
                                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                    </Button>
                                </div>
                                <p className="text-xs text-muted-foreground">
                                    Forgot password? Contact your administrator.
                                </p>
                            </div>

                            <label className="flex items-center gap-2 text-sm text-muted-foreground">
                                <input
                                    type="checkbox"
                                    checked={rememberMe}
                                    onChange={(e) => setRememberMe(e.target.checked)}
                                    className="h-4 w-4 rounded border-input"
                                />
                                <span>Remember me on this device</span>
                            </label>

                            {retryingLogin && !loading && (
                                <div className="flex items-center gap-2 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-400 text-sm">
                                    <Loader2 className="h-4 w-4 animate-spin shrink-0" />
                                    <span>Waiting for server to start — will sign in automatically.</span>
                                </div>
                            )}

                            {error && (
                                <div className="flex items-start gap-2 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
                                    <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                                    <span>{error}</span>
                                </div>
                            )}

                            <Button
                                type="submit"
                                disabled={loading || retryingLogin}
                                className="w-full h-11 text-base font-semibold shadow-md shadow-primary/20 hover:shadow-lg hover:shadow-primary/30 transition-all"
                            >
                                {loading ? (
                                    <>
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                        Signing in…
                                    </>
                                ) : retryingLogin ? (
                                    <>
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                        Retrying…
                                    </>
                                ) : (
                                    'Sign in'
                                )}
                            </Button>
                        </form>
                    </CardContent>
                </Card>

                <p className="text-center text-xs text-muted-foreground mt-6">
                    Compass Needle · Constituency Operations
                </p>
            </div>
        </div>
    );
}
