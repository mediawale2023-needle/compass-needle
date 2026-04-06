'use client';
import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { apiPost } from '@/lib/api';

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

export default function AdminLoginPage() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError]       = useState('');
    const [loading, setLoading]   = useState(false);
    const { user, login }         = useAuth();
    const router                  = useRouter();

    // 'checking' | 'connecting' | 'ready'
    const [serverStatus, setServerStatus] = useState('checking');
    const [retryCount, setRetryCount]     = useState(0);
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

    const isReady    = serverStatus === 'ready';
    const isChecking = serverStatus === 'checking';

    /* ── status banner text & colour ── */
    const bannerStyle = {
        display: 'flex',
        alignItems: 'flex-start',
        gap: 10,
        padding: '10px 14px',
        borderRadius: 10,
        fontSize: '0.82rem',
        marginBottom: 16,
        border: '1px solid',
        ...(isChecking
            ? { background: 'rgba(0,0,0,0.04)', borderColor: '#d1d5db', color: '#6b7280' }
            : { background: 'rgba(245,158,11,0.08)', borderColor: 'rgba(245,158,11,0.25)', color: '#92400e' }
        ),
    };

    return (
        <div style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'linear-gradient(135deg, #f8faf9 0%, #e8efe9 100%)',
        }}>
            <div style={{ width: 400 }}>

                {/* ── Server status banner (hidden once ready) ── */}
                {!isReady && (
                    <div style={bannerStyle}>
                        <span style={{ fontSize: '1rem', lineHeight: 1 }}>
                            {isChecking ? '⏳' : '🔄'}
                        </span>
                        <div>
                            <div style={{ fontWeight: 600 }}>
                                {isChecking ? 'Connecting to server…' : 'Server is starting up — please wait.'}
                            </div>
                            {!isChecking && (
                                <div style={{ marginTop: 2, opacity: 0.75 }}>
                                    This takes about 30 seconds on first load. Retrying automatically…
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {isReady && retryCount > 0 && (
                    <div style={{
                        display: 'flex', alignItems: 'center', gap: 8,
                        padding: '8px 14px', borderRadius: 10, fontSize: '0.82rem',
                        marginBottom: 12,
                        background: 'rgba(22,163,74,0.08)',
                        border: '1px solid rgba(22,163,74,0.2)',
                        color: '#166534',
                    }}>
                        <span>✅</span>
                        <span style={{ fontWeight: 600 }}>Server is ready.</span>
                    </div>
                )}

                {/* ── Login card ── */}
                <div style={{
                    background: '#ffffff',
                    border: '1px solid #e2ebe5',
                    borderRadius: 20,
                    padding: '2.5rem',
                    boxShadow: '0 4px 24px rgba(0,0,0,0.06)',
                    opacity: isReady ? 1 : 0.7,
                    transition: 'opacity 0.3s ease',
                }}>
                    <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
                        <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#006a4d', marginBottom: 4 }}>
                            Needle Command Center
                        </div>
                        <div style={{ fontSize: '0.82rem', color: '#6b7f76' }}>
                            Administrative Control Panel
                        </div>
                    </div>

                    <form onSubmit={handleSubmit}>
                        <div style={{ marginBottom: '1rem' }}>
                            <label className="form-label">Username</label>
                            <input
                                type="text"
                                className="form-input"
                                placeholder={isReady ? 'admin username' : 'Waiting for server…'}
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                disabled={!isReady}
                                required
                            />
                        </div>

                        <div style={{ marginBottom: '1.5rem' }}>
                            <label className="form-label">Password</label>
                            <input
                                type="password"
                                className="form-input"
                                placeholder={isReady ? 'password' : 'Waiting for server…'}
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                disabled={!isReady}
                                required
                            />
                        </div>

                        {error && (
                            <div style={{
                                background: 'rgba(220,38,38,0.06)',
                                border: '1px solid rgba(220,38,38,0.15)',
                                color: '#dc2626',
                                padding: '10px 14px',
                                borderRadius: 10,
                                fontSize: '0.82rem',
                                marginBottom: '1rem',
                            }}>
                                {error}
                            </div>
                        )}

                        <button
                            type="submit"
                            className="btn-primary"
                            disabled={loading || !isReady}
                            style={{
                                width: '100%',
                                padding: '12px',
                                fontSize: '0.9rem',
                                opacity: (loading || !isReady) ? 0.6 : 1,
                                cursor: (loading || !isReady) ? 'not-allowed' : 'pointer',
                            }}
                        >
                            {loading
                                ? 'Signing in…'
                                : !isReady
                                    ? (isChecking ? 'Connecting…' : 'Starting server…')
                                    : 'Sign In'
                            }
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
}
