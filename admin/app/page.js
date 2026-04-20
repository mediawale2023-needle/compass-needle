'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { apiPost } from '@/lib/api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
const PROBE_INTERVAL_MS = 4000;
const PROBE_TIMEOUT_MS = 5000;

function CompassIcon({ className = 'h-7 w-7' }) {
    return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="2" x2="12" y2="22" />
            <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
        </svg>
    );
}

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

export default function AdminLoginPage() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const { user, login } = useAuth();
    const router = useRouter();

    const [serverStatus, setServerStatus] = useState('checking');
    const [retryCount, setRetryCount] = useState(0);
    const probeTimerRef = useRef(null);

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

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            const res = await apiPost('/api/admin/auth/login', { username, password });
            login(res.token, res.user);
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

    const isReady = serverStatus === 'ready';
    const isChecking = serverStatus === 'checking';

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#f4f6f5] via-white to-[#e8efe9] p-4">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(0,106,77,0.08),_transparent_42%),radial-gradient(circle_at_bottom_right,_rgba(0,106,77,0.06),_transparent_34%)]" />

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

                <div className="rounded-3xl border border-[#e2ebe5] bg-white/95 p-8 shadow-xl backdrop-blur-sm">
                    <div className="mb-6 text-center">
                        <div className="mb-4 flex items-center justify-center">
                            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#006a4d] text-white shadow-lg shadow-[0_12px_32px_rgba(0,106,77,0.18)]">
                                <CompassIcon />
                            </div>
                        </div>
                        <h1 className="text-2xl font-bold tracking-tight text-[#1a2e28]">Needle Command Center</h1>
                        <p className="mt-1 text-sm text-[#6b7f76]">Administrative Control Panel</p>
                    </div>

                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="space-y-2">
                            <label htmlFor="username" className="block text-sm font-medium text-[#1a2e28]">
                                Username
                            </label>
                            <input
                                id="username"
                                type="text"
                                className="w-full rounded-xl border border-[#d4e0d9] bg-[#f8faf9] px-4 py-3 text-sm text-[#1a2e28] outline-none transition focus:border-[#006a4d] focus:bg-white focus:ring-4 focus:ring-[#006a4d]/10 disabled:cursor-not-allowed disabled:opacity-60"
                                placeholder="Enter your username"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                required
                                autoFocus
                                autoComplete="username"
                            />
                        </div>

                        <div className="space-y-2">
                            <label htmlFor="password" className="block text-sm font-medium text-[#1a2e28]">
                                Password
                            </label>
                            <div className="relative">
                                <input
                                    id="password"
                                    type={showPassword ? 'text' : 'password'}
                                    className="w-full rounded-xl border border-[#d4e0d9] bg-[#f8faf9] px-4 py-3 pr-12 text-sm text-[#1a2e28] outline-none transition focus:border-[#006a4d] focus:bg-white focus:ring-4 focus:ring-[#006a4d]/10 disabled:cursor-not-allowed disabled:opacity-60"
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
                                    className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-2 text-[#6b7f76] transition hover:bg-black/5 hover:text-[#1a2e28]"
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
                            <p className="text-xs text-[#6b7f76]">
                                Forgot password? Contact your system administrator.
                            </p>
                        </div>

                        {error && (
                            <div className="flex items-start gap-2 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-700">
                                <AlertIcon className="mt-0.5 h-4 w-4 shrink-0" />
                                <span>{error}</span>
                            </div>
                        )}

                        <button
                            type="submit"
                            disabled={loading}
                            className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#006a4d] to-[#00875f] px-4 text-base font-semibold text-white shadow-[0_10px_24px_rgba(0,106,77,0.18)] transition hover:-translate-y-0.5 hover:shadow-[0_14px_30px_rgba(0,106,77,0.22)] disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
                        >
                            {loading ? (
                                <>
                                    <SpinnerIcon className="h-4 w-4" />
                                    Signing in…
                                </>
                            ) : (
                                'Sign in'
                            )}
                        </button>
                    </form>
                </div>

                <p className="mt-6 text-center text-xs text-[#6b7f76]">Compass Needle · Admin Console</p>
            </div>
        </div>
    );
}
