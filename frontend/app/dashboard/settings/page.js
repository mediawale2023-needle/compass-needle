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

    const inputClass = "w-full px-3 py-2.5 border text-sm rounded-lg focus:outline-none focus:ring-2 transition-shadow";

    return (
        <div className="space-y-5 max-w-xl">
            <h1 className="text-lg font-bold text-gray-800">Settings</h1>

            {/* Profile */}
            <div className="figma-card">
                <h2 className="text-base font-bold text-gray-800 mb-4 pb-3 border-b" style={{ borderColor: color }}>
                    Profile
                </h2>
                <div className="space-y-3">
                    {[
                        ['Name', user?.display_name],
                        ['Username', user?.username],
                        ['Constituency', user?.constituency],
                        ['House', user?.house],
                        ['Role', user?.role],
                    ].map(([label, value]) => (
                        <div key={label} className="flex items-center gap-3">
                            <span className="text-xs text-gray-400 uppercase font-semibold w-28">{label}</span>
                            <span className="text-sm font-medium text-gray-800">{value || '—'}</span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Security Settings */}
            <div className="figma-card">
                <h2 className="text-base font-bold text-gray-800 mb-4 pb-3 border-b" style={{ borderColor: color }}>
                    Security Settings
                </h2>
                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Current Password</label>
                        <input
                            type="password" value={currentPw} onChange={e => setCurrentPw(e.target.value)}
                            placeholder="Enter current password"
                            className={inputClass}
                            style={{ borderColor: '#e5e7eb' }}
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">New Password</label>
                        <input
                            type="password" value={newPw} onChange={e => setNewPw(e.target.value)}
                            placeholder="Enter new password"
                            className={inputClass}
                            style={{ borderColor: '#e5e7eb' }}
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Confirm New Password</label>
                        <input
                            type="password" value={confirmPw} onChange={e => setConfirmPw(e.target.value)}
                            placeholder="Confirm new password"
                            className={inputClass}
                            style={{ borderColor: '#e5e7eb' }}
                        />
                    </div>
                    {message && (
                        <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 px-3 py-2 rounded">
                            {message}
                        </p>
                    )}
                    <button
                        type="submit"
                        className="px-6 py-2.5 text-white text-sm font-bold rounded-lg hover:opacity-90 transition-opacity"
                        style={{ background: color }}
                    >
                        Change Password
                    </button>
                </form>
            </div>

            {/* System Info */}
            <div className="figma-card">
                <h2 className="text-base font-bold text-gray-800 mb-4 pb-3 border-b" style={{ borderColor: '#e5e7eb' }}>
                    System Information
                </h2>
                <div className="space-y-2">
                    {[
                        ['Version', 'Compass Needle v1.0.0'],
                        ['Last Updated', 'March 9, 2026'],
                        ['Environment', 'Production'],
                    ].map(([k, v]) => (
                        <div key={k} className="flex items-center justify-between text-sm">
                            <span className="text-gray-500">{k}:</span>
                            <span className="font-semibold text-gray-800">{v}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
