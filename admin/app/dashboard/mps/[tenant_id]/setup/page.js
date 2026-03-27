'use client';
import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { apiGet, apiPatch } from '@/lib/api';

const CHECKLIST_ITEMS = [
    { key: 'profile', label: 'Profile Data', desc: 'Name, constituency, state, party', link: '/dashboard/profiles' },
    { key: 'key_facts', label: 'Key Facts Added', desc: 'Important points about the MP for AI context', link: '/dashboard/profiles' },
    { key: 'geography', label: 'Geography Uploaded', desc: 'Polling station PDF for constituency', link: '/dashboard/geography' },
    { key: 'rules', label: 'Geography Rules Set', desc: 'Location override rules configured', link: '/dashboard/rules' },
    { key: 'staff', label: 'Staff Assigned', desc: 'At least one staff account created', link: '/dashboard/staff' },
    { key: 'whatsapp', label: 'WhatsApp Mapped', desc: 'Phone number connected to tenant', link: '/dashboard/settings' },
    { key: 'test_sent', label: 'Test Message Sent', desc: 'Verified end-to-end message flow', link: null },
];

export default function SetupChecklistPage() {
    const params = useParams();
    const tenantId = params.tenant_id;
    const [detail, setDetail] = useState(null);
    const [onboarding, setOnboarding] = useState({});
    const [toast, setToast] = useState('');

    useEffect(() => {
        apiGet(`/api/admin/mps/${tenantId}/detail`).then(d => {
            setDetail(d);
            setOnboarding(d.onboarding_state || {});
        }).catch(() => {});
    }, [tenantId]);

    const computeStatus = (key) => {
        if (!detail) return false;
        const p = detail.profile || {};
        const ob = onboarding;
        switch (key) {
            case 'profile': return !!(p.mp_name && p.constituency && p.state);
            case 'key_facts': return !!(p.key_facts && p.key_facts.length > 0);
            case 'geography': return !!ob.geography;
            case 'rules': return true; // Optional, default to done
            case 'staff': return detail.staff && detail.staff.length > 0;
            case 'whatsapp': return !!p.whatsapp_number;
            case 'test_sent': return !!ob.test_sent;
            default: return false;
        }
    };

    const toggleStep = async (key, newValue) => {
        try {
            const body = {};
            body[key] = newValue;
            await apiPatch(`/api/admin/mps/${tenantId}/onboarding`, body);
            setOnboarding(prev => ({ ...prev, [key]: newValue }));
            setToast(`${key} ${newValue ? 'marked complete' : 'unmarked'}`);
            setTimeout(() => setToast(''), 2000);
        } catch (e) {
            setToast('Failed to update');
            setTimeout(() => setToast(''), 2000);
        }
    };

    const completed = CHECKLIST_ITEMS.filter(i => computeStatus(i.key)).length;
    const pct = Math.round((completed / CHECKLIST_ITEMS.length) * 100);

    return (
        <>
            {toast && <div className="toast toast-success">{toast}</div>}

            {/* Breadcrumb */}
            <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', color: '#6b7f76' }}>
                <Link href="/dashboard" style={{ color: '#006a4d', textDecoration: 'none' }}>Overview</Link>
                <span>›</span>
                <Link href={`/dashboard/mps/${tenantId}`} style={{ color: '#006a4d', textDecoration: 'none' }}>
                    {detail?.profile?.mp_name || 'MP'}
                </Link>
                <span>›</span>
                <span>Setup Checklist</span>
            </div>

            {/* Progress */}
            <div className="glass-panel" style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                    <h2 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: '#1a2e28' }}>
                        Setup Progress
                    </h2>
                    <span style={{
                        fontSize: '0.82rem', fontWeight: 700,
                        color: pct === 100 ? '#059669' : pct >= 50 ? '#d97706' : '#dc2626',
                    }}>
                        {completed}/{CHECKLIST_ITEMS.length} complete
                    </span>
                </div>
                <div className="completeness-bar" style={{ height: 8 }}>
                    <div className={`completeness-fill ${pct >= 70 ? 'fill-good' : pct >= 40 ? 'fill-mid' : 'fill-low'}`}
                        style={{ width: `${pct}%` }} />
                </div>
            </div>

            {/* Checklist */}
            <div className="glass-panel" style={{ padding: 0 }}>
                {CHECKLIST_ITEMS.map((item, i) => {
                    const done = computeStatus(item.key);
                    return (
                        <div key={item.key} style={{
                            display: 'flex', alignItems: 'center', gap: 12,
                            padding: '14px 20px',
                            borderBottom: i < CHECKLIST_ITEMS.length - 1 ? '1px solid #f0f4f1' : 'none',
                            background: done ? '#f8fdf9' : 'transparent',
                            transition: 'background 0.1s',
                        }}>
                            {/* Checkbox */}
                            <div
                                onClick={() => {
                                    if (['geography', 'staff', 'test_sent'].includes(item.key)) {
                                        toggleStep(item.key, !done);
                                    }
                                }}
                                style={{
                                    width: 22, height: 22, borderRadius: 6,
                                    border: done ? 'none' : '2px solid #d4e0d9',
                                    background: done ? 'linear-gradient(135deg, #006a4d, #059669)' : 'transparent',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    cursor: ['geography', 'staff', 'test_sent'].includes(item.key) ? 'pointer' : 'default',
                                    flexShrink: 0,
                                    transition: 'all 0.15s ease',
                                }}
                            >
                                {done && (
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                                        <polyline points="20 6 9 17 4 12"/>
                                    </svg>
                                )}
                            </div>

                            {/* Label */}
                            <div style={{ flex: 1 }}>
                                <div style={{
                                    fontSize: '0.84rem', fontWeight: 600,
                                    color: done ? '#059669' : '#1a2e28',
                                    textDecoration: done ? 'line-through' : 'none',
                                    opacity: done ? 0.7 : 1,
                                }}>
                                    {item.label}
                                </div>
                                <div style={{ fontSize: '0.72rem', color: '#94a3a0' }}>{item.desc}</div>
                            </div>

                            {/* Action link */}
                            {item.link && !done && (
                                <Link href={item.link} className="btn-ghost" style={{ textDecoration: 'none', fontSize: '0.72rem' }}>
                                    Configure →
                                </Link>
                            )}
                            {done && (
                                <span className="badge badge-green badge-dot" style={{ fontSize: '0.66rem' }}>Done</span>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Go Live */}
            <div style={{ marginTop: 16, textAlign: 'center' }}>
                {pct === 100 ? (
                    <button className="btn-primary" onClick={() => toggleStep('live', true)}>
                        Mark as Live ✓
                    </button>
                ) : (
                    <p style={{ fontSize: '0.78rem', color: '#94a3a0' }}>
                        Complete all steps above before going live
                    </p>
                )}
            </div>
        </>
    );
}
