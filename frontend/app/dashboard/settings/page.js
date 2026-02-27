'use client';

import { useState } from 'react';
import { useAuth } from '@/lib/auth';

export default function SettingsPage() {
    const { user } = useAuth();
    const [currentPw, setCurrentPw] = useState('');
    const [newPw, setNewPw] = useState('');
    const [confirmPw, setConfirmPw] = useState('');
    const [message, setMessage] = useState('');
    const color = user?.theme_color || '#006a4d';

    const handleSubmit = (e) => {
        e.preventDefault();
        if (newPw !== confirmPw) { setMessage('Passwords do not match'); return; }
        setMessage('Password update coming soon.');
    };

    return (
        <div className="space-y-5 max-w-lg">
            <h1 className="text-lg font-bold text-gray-800">Settings</h1>

            {/* Profile */}
            <div className="sansad-card">
                <div className="sansad-card-header" style={{ background: color }}>Profile</div>
                <div className="sansad-card-body">
                    <table className="sansad-table">
                        <tbody>
                            {[
                                ['Name', user?.display_name],
                                ['Username', user?.username],
                                ['Constituency', user?.constituency],
                                ['House', user?.house],
                                ['Role', user?.role],
                            ].map(([label, value]) => (
                                <tr key={label}>
                                    <td className="text-gray-500 font-medium" style={{ width: 140 }}>{label}</td>
                                    <td className="font-semibold">{value || '–'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Password */}
            <div className="sansad-card">
                <div className="sansad-card-header" style={{ background: color }}>Change Password</div>
                <div className="sansad-card-body">
                    <form onSubmit={handleSubmit} className="space-y-3">
                        {[
                            [currentPw, setCurrentPw, 'Current password'],
                            [newPw, setNewPw, 'New password'],
                            [confirmPw, setConfirmPw, 'Confirm new password'],
                        ].map(([val, set, placeholder]) => (
                            <input
                                key={placeholder}
                                type="password" value={val} onChange={e => set(e.target.value)}
                                placeholder={placeholder}
                                className="w-full px-3 py-2.5 border text-sm focus:outline-none focus:ring-1"
                                style={{ borderColor: '#ddd', '--tw-ring-color': color }}
                            />
                        ))}
                        {message && <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 px-3 py-2">{message}</p>}
                        <button type="submit" className="px-5 py-2.5 text-white text-sm font-semibold" style={{ background: color }}>
                            Update Password
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
}
