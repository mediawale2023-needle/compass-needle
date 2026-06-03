'use client';
import { useState, useEffect, useRef } from 'react';
import { apiGet } from '@/lib/api';

export default function NotificationTray() {
    const [alerts, setAlerts] = useState([]);
    const [open, setOpen] = useState(false);
    const [loading, setLoading] = useState(false);
    const trayRef = useRef(null);

    const fetchAlerts = async () => {
        try {
            setLoading(true);
            const data = await apiGet('/api/admin/alerts');
            setAlerts(data.alerts || []);
        } catch (e) {
            console.error('Failed to fetch alerts:', e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchAlerts();
        const interval = setInterval(fetchAlerts, 5 * 60 * 1000); // 5 minutes
        return () => clearInterval(interval);
    }, []);

    // Close on outside click
    useEffect(() => {
        const handler = (e) => {
            if (trayRef.current && !trayRef.current.contains(e.target)) {
                setOpen(false);
            }
        };
        if (open) document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, [open]);

    const severityColor = {
        critical: '#dc2626',
        warning: '#d97706',
        info: '#2563eb',
    };

    const severityBg = {
        critical: '#fff1f2',
        warning: '#fffbeb',
        info: '#eff6ff',
    };

    return (
        <div ref={trayRef} style={{ position: 'relative' }}>
            <button
                onClick={() => { setOpen(!open); if (!open) fetchAlerts(); }}
                style={{
                    background: open ? 'var(--surface)' : 'var(--surface-2)',
                    border: '1px solid var(--line)',
                    borderRadius: 'var(--r-sm)',
                    width: 36,
                    height: 36,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    position: 'relative',
                    transition: 'var(--t-fast)',
                    boxShadow: open ? 'var(--shadow-sm)' : 'none',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'var(--surface)'; }}
                onMouseLeave={e => { if (!open) e.currentTarget.style.background = 'var(--surface-2)'; }}
            >
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="var(--ink-2)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                    <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                </svg>
                {alerts.length > 0 && (
                    <span style={{
                        position: 'absolute', top: 6, right: 7,
                        width: 7, height: 7, borderRadius: '50%',
                        background: 'var(--sansad-maroon)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        border: '1.5px solid var(--surface)',
                    }} />
                )}
            </button>

            {open && (
                <div style={{
                    position: 'absolute',
                    top: 'calc(100% + 8px)',
                    right: 52,
                    width: 320,
                    maxHeight: 440,
                    background: 'var(--surface)',
                    border: '1px solid var(--line)',
                    borderRadius: 'var(--r-lg)',
                    boxShadow: 'var(--shadow-lg)',
                    zIndex: 200,
                    overflow: 'hidden',
                    animation: 'modalIn 0.15s ease',
                }}>
                    <div style={{
                        padding: '11px 14px',
                        borderBottom: '1px solid var(--line)',
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    }}>
                        <span className="cn-eyebrow">
                            Alerts
                        </span>
                        <span style={{
                            fontFamily: 'var(--font-mono)',
                            fontSize: '10px',
                            fontWeight: 600,
                            letterSpacing: '0.08em',
                            textTransform: 'uppercase',
                            color: alerts.length > 0 ? 'var(--sansad-maroon)' : 'var(--ink-3)',
                            background: alerts.length > 0 ? '#f5e6ea' : 'var(--paper-2)',
                            padding: '4px 9px', borderRadius: 999,
                        }}>
                            {alerts.length} active
                        </span>
                    </div>

                    <div style={{ overflowY: 'auto', maxHeight: 370 }}>
                        {loading && alerts.length === 0 && (
                            <div className="cn-meta" style={{ padding: '2rem', textAlign: 'center' }}>
                                Checking...
                            </div>
                        )}
                        {!loading && alerts.length === 0 && (
                            <div style={{ padding: '2rem', textAlign: 'center' }}>
                                <div style={{ fontSize: '1.4rem', marginBottom: 6 }}>✓</div>
                                <div className="cn-meta" style={{ fontWeight: 500 }}>
                                    All systems running smoothly
                                </div>
                            </div>
                        )}
                        {alerts.map((alert, i) => (
                            <div key={i} style={{
                                padding: '11px 14px',
                                borderBottom: i < alerts.length - 1 ? '1px solid var(--line)' : 'none',
                                display: 'flex', gap: 10, alignItems: 'flex-start',
                                transition: 'background 0.1s',
                                cursor: 'default',
                            }}
                                onMouseEnter={e => e.currentTarget.style.background = 'var(--surface-2)'}
                                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                            >
                                <div style={{
                                    width: 8, height: 8, borderRadius: '50%',
                                    background: severityColor[alert.severity] || '#6b7f76',
                                    flexShrink: 0, marginTop: 5,
                                }} />
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{ 
                                        fontSize: '13px', fontWeight: 600, color: 'var(--ink)',
                                        lineHeight: 1.3, marginBottom: 2,
                                    }}>
                                        {alert.title}
                                    </div>
                                    <div className="cn-meta" style={{ fontSize: '12px', lineHeight: 1.4 }}>
                                        {alert.description}
                                    </div>
                                </div>
                                <span className="badge" style={{
                                    background: severityBg[alert.severity] || '#f8fafc',
                                    color: severityColor[alert.severity] || '#64748b',
                                    fontSize: '0.6rem', padding: '3px 7px', flexShrink: 0,
                                }}>
                                    {alert.type?.replace(/_/g, ' ')}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
