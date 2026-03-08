'use client';

import { useState } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
    const { user, login } = useAuth();
    const router = useRouter();
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    if (user) {
        router.push('/dashboard');
        return null;
    }

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            await login(username, password);
            router.push('/dashboard');
        } catch (err) {
            const msg = err.message || 'Invalid credentials';
            setError(msg.includes('Connection timed out') || msg.includes('try again') ? msg : (msg === 'Request failed after retries' ? 'Connection issue. Please try again in a moment.' : msg));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center" style={{ background: '#f4f4f4' }}>
            <div className="w-full max-w-sm">
                {/* Accent bar */}
                <div style={{ height: 4, background: '#006a4d', borderRadius: '4px 4px 0 0' }} />

                {/* Card */}
                <div className="bg-white border p-8" style={{ borderColor: '#ddd', borderTop: 'none' }}>
                    {/* Header — matches sansad.in "Lok Sabha / House of the People" style */}
                    <div className="text-center mb-8">
                        <h1 className="text-2xl font-bold" style={{ color: '#006a4d' }}>Needle</h1>
                        <p className="text-xs text-gray-500 mt-1">Parliamentary Intelligence Platform</p>
                    </div>

                    <form onSubmit={handleSubmit}>
                        <div className="mb-4">
                            <label className="block text-xs font-semibold text-gray-600 mb-1.5 uppercase">Username</label>
                            <input
                                type="text"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                className="w-full px-3 py-2.5 border text-sm focus:outline-none focus:ring-1"
                                style={{ borderColor: '#ddd', '--tw-ring-color': '#006a4d' }}
                                required
                                autoFocus
                            />
                        </div>

                        <div className="mb-5">
                            <label className="block text-xs font-semibold text-gray-600 mb-1.5 uppercase">Password</label>
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full px-3 py-2.5 border text-sm focus:outline-none focus:ring-1"
                                style={{ borderColor: '#ddd', '--tw-ring-color': '#006a4d' }}
                                required
                            />
                        </div>

                        {error && (
                            <div className="text-red-700 text-xs bg-red-50 px-3 py-2 border border-red-200 mb-4">
                                {error}
                            </div>
                        )}

                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full py-2.5 text-white text-sm font-semibold disabled:opacity-50"
                            style={{ background: '#006a4d' }}
                        >
                            {loading ? 'Signing in...' : 'Login'}
                        </button>
                    </form>
                </div>

                <p className="text-center text-[11px] text-gray-400 mt-4">
                    Compass Needle · Digital Parliament
                </p>
            </div>
        </div>
    );
}
