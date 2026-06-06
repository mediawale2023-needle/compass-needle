'use client';

import { useState, useEffect, useRef } from 'react';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { apiPost } from '@/lib/api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
const PROBE_INTERVAL_MS = 4000;
const PROBE_TIMEOUT_MS = 5000;

function SpinnerIcon({ className = 'h-4 w-4' }) {
    return (
        <svg className={`${className} animate-spin`} viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.2" strokeWidth="3" />
            <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
        </svg>
    );
}

function CheckIcon({ className = 'h-4 w-4' }) {
    return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 6 9 17l-5-5" />
        </svg>
    );
}

function AlertIcon({ className = 'h-4 w-4' }) {
    return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 9v4" />
            <path d="M12 17h.01" />
            <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.72 3h16.92a2 2 0 0 0 1.72-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
        </svg>
    );
}

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

export default function AdminLoginPage() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const [retryingLogin, setRetryingLogin] = useState(false);
    const { user, login } = useAuth();
    const router = useRouter();

    const [serverStatus, setServerStatus] = useState('checking');
    const [retryCount, setRetryCount] = useState(0);
    const probeTimerRef = useRef(null);
    const loginRetryTimerRef = useRef(null);
    const handleSubmitRef = useRef(null);

    useEffect(() => {
        if (user) router.push('/dashboard');
    }, [user, router]);

    useEffect(() => {
        let cancelled = false;

        async function runProbe() {
            const ok = await probeBackend();
            if (cancelled) return;
            if (ok) {
                setServerStatus('ready');
            } else {
                setServerStatus('connecting');
                setRetryCount((n) => n + 1);
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
        setLoading(true);
        try {
            const res = await apiPost('/api/admin/auth/login', { username, password });
            login(res.token, res.user);
            router.push('/dashboard');
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

    const isReady = serverStatus === 'ready';
    const isChecking = serverStatus === 'checking';

    return (
        <div className="min-h-screen flex items-center justify-center bg-[var(--paper)] p-6">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(11,110,79,0.06),_transparent_38%),radial-gradient(circle_at_bottom_right,_rgba(158,43,69,0.05),_transparent_32%)]" />

            <div className="relative w-full max-w-md animate-fade-in">
                {!isReady && (
                    <div
                        className={`mb-3 flex items-start gap-3 rounded-xl border px-4 py-3 text-sm font-medium ${
                            isChecking
                                ? 'border-[#e2ebe5] bg-white/80 text-[#6b7f76]'
                                : 'border-amber-500/20 bg-amber-500/10 text-amber-700'
                        }`}
                    >
                        <SpinnerIcon className="mt-0.5 h-4 w-4 shrink-0" />
                        <div>
                            <p>{isChecking ? 'Connecting to server…' : 'Server is starting up — this may take a moment.'}</p>
                            {!isChecking && (
                                <p className="mt-0.5 text-xs font-normal opacity-80">
                                    You can sign in now — the request will wait for the server automatically.
                                </p>
                            )}
                        </div>
                    </div>
                )}

                {isReady && retryCount > 0 && (
                    <div className="mb-3 flex items-center gap-2 rounded-xl border border-green-500/20 bg-green-500/10 px-4 py-2.5 text-sm font-medium text-green-700">
                        <CheckIcon className="h-4 w-4 shrink-0" />
                        <span>Server is ready.</span>
                    </div>
                )}

                <div className="rounded-[10px] border border-[var(--line)] bg-[var(--surface)] p-8 shadow-[var(--shadow-md)] backdrop-blur-sm">
                    <div className="mb-6 text-center">
                        <div className="mb-5 flex items-center justify-center">
                            <Image
                                src="/needle-logo.svg"
                                alt="Compass Needle"
                                width={72}
                                height={44}
                                className="h-11 w-auto"
                                priority
                            />
                        </div>
                        <h1 className="cn-display" style={{ fontSize: '26px' }}>Compass Needle</h1>
                        <p className="mt-2 font-[var(--font-mono)] text-[11px] uppercase tracking-[0.14em] text-[var(--ink-3)]">Administrative Control Panel</p>
                    </div>

                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="space-y-2">
                            <label htmlFor="username" className="form-label">
                                Username
                            </label>
                            <input
                                id="username"
                                type="text"
                                className="form-input px-4 py-3"
                                placeholder="Enter your username"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                required
                                autoFocus
                                autoComplete="username"
                            />
                        </div>

                        <div className="space-y-2">
                            <label htmlFor="password" className="form-label">
                                Password
                            </label>
                            <div className="relative">
                                <input
                                    id="password"
                                    type={showPassword ? 'text' : 'password'}
                                    className="form-input px-4 py-3 pr-12"
                                    placeholder="Enter your password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    required
                                    autoComplete="current-password"
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPassword(v => !v)}
                                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                                    className="absolute right-2 top-1/2 -translate-y-1/2 rounded-[5px] p-2 text-[var(--ink-3)] transition hover:bg-[var(--paper-2)] hover:text-[var(--ink)]"
                                >
                                    {showPassword ? (
                                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                            <path d="m1 1 22 22" />
                                            <path d="M17.94 17.94A10.94 10.94 0 0 1 12 20C7 20 2.73 16.11 1 12c.56-1.34 1.49-2.83 2.7-4.21" />
                                            <path d="M9.9 4.24A10.94 10.94 0 0 1 12 4c5 0 9.27 3.89 11 8-1.01 2.41-2.84 4.6-5.06 6.06" />
                                            <path d="M14.12 14.12a3 3 0 0 1-4.24-4.24" />
                                            <path d="M9.88 9.88A3 3 0 0 1 14.12 14.12" />
                                        </svg>
                                    ) : (
                                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                            <path d="M2.06 12C3.8 7.64 7.68 5 12 5c4.33 0 8.2 2.64 9.94 7-1.74 4.36-5.61 7-9.94 7-4.32 0-8.2-2.64-9.94-7Z" />
                                            <circle cx="12" cy="12" r="3" />
                                        </svg>
                                    )}
                                </button>
                            </div>
                            <p className="cn-meta text-xs">
                                Forgot password? Contact your system administrator.
                            </p>
                        </div>

                        {retryingLogin && !loading && (
                            <div className="flex items-start gap-2 rounded-[7px] border border-[rgba(194,117,42,0.18)] bg-[rgba(194,117,42,0.1)] p-3 text-sm text-[var(--saffron)]">
                                <SpinnerIcon className="mt-0.5 h-4 w-4 shrink-0" />
                                <span>Waiting for server to start — will sign in automatically.</span>
                            </div>
                        )}

                        {error && (
                            <div className="flex items-start gap-2 rounded-[7px] border border-[rgba(158,43,69,0.18)] bg-[rgba(158,43,69,0.1)] p-3 text-sm text-[var(--sansad-maroon)]">
                                <AlertIcon className="mt-0.5 h-4 w-4 shrink-0" />
                                <span>{error}</span>
                            </div>
                        )}

                        <button
                            type="submit"
                            disabled={loading || retryingLogin}
                            className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-[5px] bg-gradient-to-r from-[var(--sansad-green)] to-[var(--sansad-green-light)] px-4 text-base font-semibold text-white shadow-[var(--shadow-md)] transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-lg)] disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
                        >
                            {loading ? (
                                <>
                                    <SpinnerIcon className="h-4 w-4" />
                                    Signing in…
                                </>
                            ) : retryingLogin ? (
                                <>
                                    <SpinnerIcon className="h-4 w-4" />
                                    Retrying…
                                </>
                            ) : (
                                'Sign in'
                            )}
                        </button>
                    </form>
                </div>

                <p className="mt-6 text-center font-[var(--font-mono)] text-[10.5px] uppercase tracking-[0.08em] text-[var(--ink-4)]">Compass Needle · Admin Console</p>
            </div>
        </div>
    );
}
