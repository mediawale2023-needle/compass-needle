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
            {/* Bell Button */}
            <button
                onClick={() => { setOpen(!open); if (!open) fetchAlerts(); }}
                style={{
                    background: open ? '#f0f4f2' : 'transparent',
                    border: '1px solid transparent',
                    borderRadius: 8,
                    padding: '6px 8px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    position: 'relative',
                    transition: 'all 0.12s ease',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = '#f0f4f2'; }}
                onMouseLeave={e => { if (!open) e.currentTarget.style.background = 'transparent'; }}
            >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6b7f76" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                    <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                </svg>
                {/* Badge */}
                {alerts.length > 0 && (
                    <span style={{
                        position: 'absolute', top: 2, right: 2,
                        width: 16, height: 16, borderRadius: '50%',
                        background: '#dc2626', color: 'white',
                        fontSize: '0.6rem', fontWeight: 700,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        border: '2px solid white',
                    }}>
                        {alerts.length > 9 ? '9+' : alerts.length}
                    </span>
                )}
            </button>

            {/* Dropdown */}
            {open && (
                <div style={{
                    position: 'absolute',
                    top: 'calc(100% + 8px)',
                    right: 0,
                    width: 380,
                    maxHeight: 440,
                    background: '#ffffff',
                    border: '1px solid #e2ebe5',
                    borderRadius: 14,
                    boxShadow: '0 12px 32px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06)',
                    zIndex: 200,
                    overflow: 'hidden',
                    animation: 'modalIn 0.15s ease',
                }}>
                    {/* Header */}
                    <div style={{
                        padding: '12px 16px',
                        borderBottom: '1px solid #e2ebe5',
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    }}>
                        <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#1a2e28' }}>
                            Alerts
                        </span>
                        <span style={{
                            fontSize: '0.68rem', fontWeight: 600,
                            color: alerts.length > 0 ? '#dc2626' : '#6b7f76',
                            background: alerts.length > 0 ? '#fff1f2' : '#f0f4f2',
                            padding: '2px 8px', borderRadius: 12,
                        }}>
                            {alerts.length} active
                        </span>
                    </div>

                    {/* Alert List */}
                    <div style={{ overflowY: 'auto', maxHeight: 370 }}>
                        {loading && alerts.length === 0 && (
                            <div style={{ padding: '2rem', textAlign: 'center', color: '#6b7f76', fontSize: '0.82rem' }}>
                                Checking...
                            </div>
                        )}
                        {!loading && alerts.length === 0 && (
                            <div style={{ padding: '2rem', textAlign: 'center' }}>
                                <div style={{ fontSize: '1.4rem', marginBottom: 6 }}>✓</div>
                                <div style={{ fontSize: '0.82rem', color: '#6b7f76', fontWeight: 500 }}>
                                    All systems running smoothly
                                </div>
                            </div>
                        )}
                        {alerts.map((alert, i) => (
                            <div key={i} style={{
                                padding: '10px 16px',
                                borderBottom: i < alerts.length - 1 ? '1px solid #f0f4f1' : 'none',
                                display: 'flex', gap: 10, alignItems: 'flex-start',
                                transition: 'background 0.1s',
                                cursor: 'default',
                            }}
                                onMouseEnter={e => e.currentTarget.style.background = '#f8faf9'}
                                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                            >
                                <div style={{
                                    width: 8, height: 8, borderRadius: '50%',
                                    background: severityColor[alert.severity] || '#6b7f76',
                                    flexShrink: 0, marginTop: 5,
                                }} />
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{ 
                                        fontSize: '0.78rem', fontWeight: 600, color: '#1a2e28',
                                        lineHeight: 1.3, marginBottom: 2,
                                    }}>
                                        {alert.title}
                                    </div>
                                    <div style={{ fontSize: '0.72rem', color: '#6b7f76', lineHeight: 1.4 }}>
                                        {alert.description}
                                    </div>
                                </div>
                                <span className="badge" style={{
                                    background: severityBg[alert.severity] || '#f8fafc',
                                    color: severityColor[alert.severity] || '#64748b',
                                    fontSize: '0.62rem', padding: '2px 6px', flexShrink: 0,
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
