'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { apiPost } from '@/lib/api';

export default function AdminLoginPage() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const { user, login } = useAuth();
    const router = useRouter();

    // If already logged in, redirect
    if (user) {
        router.push('/dashboard');
        return null;
    }

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
            setError(msg.includes('Connection timed out') || msg.includes('try again') ? msg : (msg === 'Request failed after retries' ? 'Connection issue. Please try again in a moment.' : msg));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'linear-gradient(135deg, #f8faf9 0%, #e8efe9 100%)',
        }}>
            <div style={{
                width: 400,
                background: '#ffffff',
                border: '1px solid #e2ebe5',
                borderRadius: 20,
                padding: '2.5rem',
                boxShadow: '0 4px 24px rgba(0,0,0,0.06)',
            }}>
                {/* Title */}
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
                            placeholder="admin username"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            required
                        />
                    </div>

                    <div style={{ marginBottom: '1.5rem' }}>
                        <label className="form-label">Password</label>
                        <input
                            type="password"
                            className="form-input"
                            placeholder="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                        />
                    </div>

                    {error && (
                        <div style={{
                            background: 'rgba(220, 38, 38, 0.06)',
                            border: '1px solid rgba(220, 38, 38, 0.15)',
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
                        disabled={loading}
                        style={{ width: '100%', padding: '12px', fontSize: '0.9rem' }}
                    >
                        {loading ? 'Signing in...' : 'Sign In'}
                    </button>
                </form>
            </div>
        </div>
    );
}
