'use client';
import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { apiGet, apiPatch } from '@/lib/api';

const REQUIRED_KEYS = ['profile', 'key_facts', 'geography', 'staff', 'whatsapp', 'test_sent'];

function buildChecklist(tenantId, detail, onboarding, geography) {
    const p = detail?.profile || {};
    const assemblies = Object.keys(geography?.assemblies || {});
    const localityCount = assemblies.reduce((sum, assembly) => sum + (geography.assemblies[assembly]?.length || 0), 0);
    const hasWhatsAppNumber = !!p.whatsapp_number;
    const hasPhoneId = !!p.phone_number_id;

    return [
        {
            key: 'profile',
            label: 'Profile Data',
            desc: 'Name, constituency, state, house, and party are present.',
            action: 'Edit profile',
            link: `/dashboard/profiles?tenant_id=${tenantId}`,
            done: !!(p.mp_name && p.constituency && p.state && p.house),
            source: 'Verified from profile',
        },
        {
            key: 'key_facts',
            label: 'AI Context Added',
            desc: 'Key facts help Copilot, Drafter, and constituency intelligence avoid generic output.',
            action: 'Add key facts',
            link: `/dashboard/profiles?tenant_id=${tenantId}`,
            done: !!(p.key_facts && p.key_facts.length > 0),
            source: 'Verified from profile',
        },
        {
            key: 'geography',
            label: 'Geography Uploaded',
            desc: assemblies.length
                ? `${assemblies.length} assemblies and ${localityCount} localities available for routing.`
                : 'Upload or add assembly-locality data before live grievance routing.',
            action: 'Configure geography',
            link: `/dashboard/profiles?tenant_id=${tenantId}#geography`,
            done: assemblies.length > 0 && localityCount > 0,
            source: 'Verified from saved geography',
        },
        {
            key: 'rules',
            label: 'Geography Rules Reviewed',
            desc: 'Optional override rules are not required, but should be reviewed for ambiguous locality names.',
            action: 'Review rules',
            link: '/dashboard/rules',
            done: true,
            optional: true,
            source: 'Optional review step',
        },
        {
            key: 'staff',
            label: 'Staff Assigned',
            desc: 'At least one active non-admin staff account is assigned to this MP tenant.',
            action: 'Add staff',
            link: `/dashboard/mps/${tenantId}`,
            done: (detail?.staff || []).some(s => s.is_active),
            source: 'Verified from staff roster',
        },
        {
            key: 'whatsapp',
            label: 'WhatsApp Routing Ready',
            desc: hasWhatsAppNumber && hasPhoneId
                ? 'WhatsApp number and Meta phone number ID are mapped.'
                : 'Both WhatsApp number and Meta phone number ID are required for reliable routing.',
            action: 'Configure WhatsApp',
            link: `/dashboard/mps/${tenantId}`,
            done: hasWhatsAppNumber && hasPhoneId,
            source: hasWhatsAppNumber && !hasPhoneId ? 'Missing Meta phone number ID' : 'Verified from tenant config',
        },
        {
            key: 'test_sent',
            label: 'Live Smoke Test Completed',
            desc: 'Manually verify MP login, webhook intake, and one citizen reply before enabling production traffic.',
            action: null,
            link: null,
            done: !!onboarding.test_sent,
            manual: true,
            source: 'Manual operator verification',
        },
    ];
}

export default function SetupChecklistPage() {
    const params = useParams();
    const tenantId = params.tenant_id;
    const [detail, setDetail] = useState(null);
    const [geography, setGeography] = useState({ assemblies: {} });
    const [onboarding, setOnboarding] = useState({});
    const [toast, setToast] = useState({ type: '', text: '' });
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [savingKey, setSavingKey] = useState('');

    const showToast = (type, text) => {
        setToast({ type, text });
        setTimeout(() => setToast({ type: '', text: '' }), 3000);
    };

    const loadSetup = async () => {
        setLoading(true);
        setError('');
        try {
            const [detailData, geographyData] = await Promise.all([
                apiGet(`/api/admin/mps/${tenantId}/detail`),
                apiGet(`/api/admin/mps/${tenantId}/geography`),
            ]);
            setDetail(detailData);
            setOnboarding(detailData.onboarding_state || {});
            setGeography(geographyData || { assemblies: {} });
        } catch (e) {
            setError(e.message || 'Failed to load setup readiness');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadSetup();
    }, [tenantId]);

    const toggleManualStep = async (key, newValue) => {
        setSavingKey(key);
        try {
            const body = {};
            body[key] = newValue;
            const updated = await apiPatch(`/api/admin/mps/${tenantId}/onboarding`, body);
            setOnboarding(updated.onboarding_state || { ...onboarding, [key]: newValue });
            showToast('success', `${key === 'test_sent' ? 'Smoke test' : key} ${newValue ? 'verified' : 'unmarked'}.`);
        } catch (e) {
            showToast('error', e.message || 'Failed to update setup state');
        } finally {
            setSavingKey('');
        }
    };

    const checklist = buildChecklist(tenantId, detail, onboarding, geography);
    const requiredItems = checklist.filter(item => REQUIRED_KEYS.includes(item.key));
    const completed = requiredItems.filter(item => item.done).length;
    const pct = Math.round((completed / requiredItems.length) * 100);
    const canGoLive = requiredItems.every(item => item.done);
    const isLive = !!onboarding.live;
    const blockers = requiredItems.filter(item => !item.done);

    if (loading) {
        return (
            <div style={{ display: 'grid', gap: 12 }}>
                {[...Array(4)].map((_, i) => <div key={i} className="glass-panel skeleton" style={{ height: 82 }} />)}
            </div>
        );
    }

    return (
        <>
            {toast.text && <div className={`toast ${toast.type === 'success' ? 'toast-success' : 'toast-error'}`}>{toast.text}</div>}
            {error && (
                <div className="toast toast-error" style={{ position: 'relative', marginBottom: 16 }}>
                    {error}
                    <button className="btn-ghost" onClick={loadSetup} style={{ marginLeft: 12 }}>Retry</button>
                </div>
            )}

            <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', color: '#6b7f76' }}>
                <Link href="/dashboard" style={{ color: '#006a4d', textDecoration: 'none' }}>Overview</Link>
                <span>›</span>
                <Link href={`/dashboard/mps/${tenantId}`} style={{ color: '#006a4d', textDecoration: 'none' }}>
                    {detail?.profile?.mp_name || 'MP'}
                </Link>
                <span>›</span>
                <span>Launch Readiness</span>
            </div>

            <div className="glass-panel" style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, marginBottom: 12 }}>
                    <div>
                        <h2 style={{ margin: 0, fontSize: '1rem', fontWeight: 800, color: '#1a2e28' }}>
                            Tenant Launch Readiness
                        </h2>
                        <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: '#6b7f76' }}>
                            Production traffic should stay off until all required checks are verified from real tenant data.
                        </p>
                    </div>
                    <span className={`badge badge-dot ${isLive ? 'badge-green' : canGoLive ? 'badge-amber' : 'badge-red'}`}>
                        {isLive ? 'Live' : canGoLive ? 'Ready to enable' : `${blockers.length} blockers`}
                    </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div className="completeness-bar" style={{ height: 9, flex: 1 }}>
                        <div className={`completeness-fill ${pct >= 80 ? 'fill-good' : pct >= 50 ? 'fill-mid' : 'fill-low'}`}
                            style={{ width: `${pct}%` }} />
                    </div>
                    <span style={{ fontSize: '0.82rem', fontWeight: 800, color: canGoLive ? '#059669' : '#d97706' }}>
                        {completed}/{requiredItems.length}
                    </span>
                </div>
            </div>

            {blockers.length > 0 && (
                <div style={{
                    marginBottom: 16,
                    padding: '12px 14px',
                    border: '1px solid #fed7aa',
                    background: '#fff7ed',
                    borderRadius: 12,
                    color: '#9a3412',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                }}>
                    Blocked: {blockers.map(item => item.label).join(', ')}
                </div>
            )}

            <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
                {checklist.map((item, i) => (
                    <div key={item.key} style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 14,
                        padding: '15px 20px',
                        borderBottom: i < checklist.length - 1 ? '1px solid #f0f4f1' : 'none',
                        background: item.done ? '#f8fdf9' : item.optional ? '#fbfcfb' : '#fff',
                    }}>
                        <div style={{
                            width: 24,
                            height: 24,
                            borderRadius: 8,
                            border: item.done ? 'none' : `2px solid ${item.optional ? '#cbd5d0' : '#f59e0b'}`,
                            background: item.done ? 'linear-gradient(135deg, #006a4d, #059669)' : '#fff',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0,
                        }}>
                            {item.done ? (
                                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                                    <polyline points="20 6 9 17 4 12" />
                                </svg>
                            ) : (
                                <span style={{ width: 7, height: 7, borderRadius: 999, background: item.optional ? '#94a3a0' : '#f59e0b' }} />
                            )}
                        </div>

                        <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                                <span style={{ fontSize: '0.86rem', fontWeight: 700, color: '#1a2e28' }}>
                                    {item.label}
                                </span>
                                {item.optional && <span className="badge badge-slate" style={{ fontSize: '0.64rem' }}>Optional</span>}
                                {item.manual && <span className="badge badge-amber" style={{ fontSize: '0.64rem' }}>Manual</span>}
                            </div>
                            <div style={{ marginTop: 3, fontSize: '0.75rem', color: '#6b7f76' }}>{item.desc}</div>
                            <div style={{ marginTop: 4, fontSize: '0.68rem', color: item.done ? '#059669' : '#94a3a0' }}>
                                {item.source}
                            </div>
                        </div>

                        {item.manual ? (
                            <button
                                className={item.done ? 'btn-secondary' : 'btn-primary'}
                                disabled={savingKey === item.key}
                                onClick={() => toggleManualStep(item.key, !item.done)}
                                style={{ fontSize: '0.72rem', padding: '6px 12px', flexShrink: 0 }}
                            >
                                {savingKey === item.key ? 'Saving…' : item.done ? 'Unmark' : 'Mark verified'}
                            </button>
                        ) : item.link && !item.done ? (
                            <Link href={item.link} className="btn-ghost" style={{ textDecoration: 'none', fontSize: '0.72rem', flexShrink: 0 }}>
                                {item.action} →
                            </Link>
                        ) : (
                            <span className={`badge badge-dot ${item.done ? 'badge-green' : 'badge-slate'}`} style={{ fontSize: '0.66rem', flexShrink: 0 }}>
                                {item.done ? 'Verified' : 'Pending'}
                            </span>
                        )}
                    </div>
                ))}
            </div>

            <div className="glass-panel" style={{ marginTop: 16, textAlign: 'center', borderColor: canGoLive ? '#bbf7d0' : '#fed7aa' }}>
                <p style={{ margin: '0 0 10px', fontSize: '0.82rem', color: '#6b7f76' }}>
                    {canGoLive
                        ? 'All required checks are complete. Enabling live status records operator approval; it does not replace a real WhatsApp smoke test.'
                        : 'Complete all required checks before enabling this tenant for production grievance traffic.'}
                </p>
                <button
                    className="btn-primary"
                    disabled={!canGoLive || savingKey === 'live'}
                    onClick={() => toggleManualStep('live', true)}
                    style={{ opacity: canGoLive ? 1 : 0.55, cursor: canGoLive ? 'pointer' : 'not-allowed' }}
                >
                    {isLive ? 'Live Enabled' : savingKey === 'live' ? 'Enabling…' : 'Enable Production Traffic'}
                </button>
            </div>
        </>
    );
}
