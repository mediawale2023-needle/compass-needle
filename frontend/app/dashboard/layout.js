'use client';

import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import Sidebar from '@/components/Sidebar';
import { apiGet } from '@/lib/api';

const TYPE_LABELS = {
    draft_letter: 'Letter',
    draft_question: 'PQ',
    analysis: 'Analysis',
    copilot_chat: 'Chat',
};

export default function DashboardLayout({ children }) {
    const { user, logout, loading } = useAuth();
    const router = useRouter();
    const [showHistory, setShowHistory] = useState(false);
    const [history, setHistory] = useState([]);
    const [historyLoading, setHistoryLoading] = useState(false);

    useEffect(() => {
        if (!loading && !user) router.push('/');
    }, [user, loading, router]);

    const openHistory = async () => {
        setShowHistory(true);
        setHistoryLoading(true);
        try {
            const data = await apiGet('/api/history?limit=30');
            setHistory(data.items || []);
        } catch { setHistory([]); }
        finally { setHistoryLoading(false); }
    };

    if (loading) return (
        <div className="min-h-screen flex items-center justify-center" style={{ background: '#f4f4f4' }}>
            <p className="text-gray-500 text-sm">Loading...</p>
        </div>
    );
    if (!user) return null;

    const color = user.theme_color || '#006a4d';

    return (
        <div className="min-h-screen" style={{ background: '#f4f4f4' }}>
            <Sidebar user={user} onLogout={() => { logout(); router.push('/'); }} />

            <main className="ml-60 min-h-screen">
                {/* Header bar */}
                <header className="bg-white border-b px-6 py-3 flex items-center justify-between" style={{ borderColor: '#ddd' }}>
                    <div>
                        <span className="text-sm font-semibold text-gray-700">{user.display_name}</span>
                        <span className="text-gray-400 mx-2">|</span>
                        <span className="text-xs text-gray-500">{user.constituency} · {user.house}</span>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="text-[11px] text-gray-400">
                            {new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
                        </div>
                        {/* History icon */}
                        <button onClick={openHistory}
                            className="w-7 h-7 flex items-center justify-center border text-gray-400 hover:text-gray-600 hover:border-gray-400 transition-colors"
                            style={{ borderColor: '#ddd', borderRadius: '4px' }}
                            title="Activity History">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <circle cx="12" cy="12" r="10" />
                                <polyline points="12 6 12 12 16 14" />
                            </svg>
                        </button>
                    </div>
                </header>

                {/* Content */}
                <div className="p-6 animate-fade-in">
                    {children}
                </div>
            </main>

            {/* History Panel (slide-over) */}
            {showHistory && (
                <div className="fixed inset-0 z-50" onClick={() => setShowHistory(false)}>
                    {/* Backdrop */}
                    <div className="absolute inset-0 bg-black/20" />
                    {/* Panel */}
                    <div className="absolute right-0 top-0 h-full w-96 bg-white border-l shadow-lg flex flex-col"
                        style={{ borderColor: '#ddd' }}
                        onClick={e => e.stopPropagation()}>
                        <div className="px-5 py-4 border-b flex items-center justify-between" style={{ borderColor: '#ddd' }}>
                            <div>
                                <div className="text-sm font-bold text-gray-800">Activity History</div>
                                <div className="text-[10px] text-gray-400 uppercase">Last 30 days</div>
                            </div>
                            <button onClick={() => setShowHistory(false)} className="text-gray-400 hover:text-gray-600 text-lg">✕</button>
                        </div>

                        <div className="flex-1 overflow-y-auto">
                            {historyLoading ? (
                                <div className="text-center py-10 text-gray-400 text-sm">Loading...</div>
                            ) : history.length === 0 ? (
                                <div className="text-center py-10 text-gray-400 text-sm">No activity yet.</div>
                            ) : (
                                <div className="divide-y" style={{ borderColor: '#eee' }}>
                                    {history.map(item => (
                                        <div key={item.id} className="px-5 py-3 hover:bg-gray-50 cursor-pointer"
                                            onClick={() => { setShowHistory(false); router.push('/dashboard/archives'); }}>
                                            <div className="flex items-center gap-2">
                                                <span className="inline-block w-2 h-2 rounded-full" style={{ background: color }} />
                                                <span className="text-[10px] font-semibold uppercase" style={{ color }}>
                                                    {TYPE_LABELS[item.activity_type] || item.activity_type}
                                                </span>
                                            </div>
                                            <div className="text-sm font-medium text-gray-700 mt-0.5 truncate">{item.title}</div>
                                            <div className="text-[10px] text-gray-400 mt-0.5">
                                                {item.created_at ? new Date(item.created_at).toLocaleString('en-IN', {
                                                    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
                                                }) : '–'}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        <div className="px-5 py-3 border-t" style={{ borderColor: '#ddd' }}>
                            <button onClick={() => { setShowHistory(false); router.push('/dashboard/archives'); }}
                                className="w-full py-2 text-xs font-semibold text-white" style={{ background: color }}>
                                View All in Archives
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
