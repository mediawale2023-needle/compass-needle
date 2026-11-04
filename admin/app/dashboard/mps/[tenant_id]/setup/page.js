'use client';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { apiGet, apiPatch } from '@/lib/api';
import { buildLaunchChecklist, launchSummary, ONBOARDING_STEPS } from '@/lib/admin-data';
import { Badge, Callout, Card, ErrorState, LoadingSkeleton, PageHeader, ProgressBar, ReadinessIcon, Stepper } from '@/components/admin-ui';
import '@/app/styles/admin-onboarding.css';

// Launch setup is the continuation of onboarding after the account exists.
// Every check reads real tenant data (profile, staff, saved geography,
// tenant config, onboarding_state); only the smoke test is operator-marked.
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
    }, [tenantId]); // eslint-disable-line react-hooks/exhaustive-deps

    const toggleManualStep = async (key, newValue) => {
        setSavingKey(key);
        try {
            const updated = await apiPatch(`/api/admin/mps/${tenantId}/onboarding`, { [key]: newValue });
            setOnboarding(updated.onboarding_state || { ...onboarding, [key]: newValue });
            showToast('success', `${key === 'test_sent' ? 'Smoke test' : key} ${newValue ? 'verified' : 'unmarked'}.`);
        } catch (e) {
            showToast('error', e.message || 'Failed to update setup state');
        } finally {
            setSavingKey('');
        }
    };

    const checklist = buildLaunchChecklist(tenantId, detail, onboarding, geography);
    const summary = launchSummary(checklist, onboarding);
    const name = detail?.profile?.mp_name || 'Account';

    if (loading) {
        return <div className="nx-ls"><LoadingSkeleton rows={6} label="Loading launch readiness" /></div>;
    }

    return (
        <div className="nx-ls">
            <PageHeader
                eyebrow={<><Link className="nx-link" href={`/dashboard/mps/${tenantId}`}>{name}</Link> · Onboarding</>}
                title="Launch setup"
                description="The account exists. Production traffic stays off until every required check is verified from real tenant data."
                actions={<Link className="nx-btn" href={`/dashboard/mps/${tenantId}`}>Open Account 360</Link>}
            />

            <Card className="nx-ob-stepper">
                <Stepper label="Onboarding steps" steps={[...ONBOARDING_STEPS.map((step) => ({ label: step.label, detail: step.detail, state: 'done' })), { label: 'Launch setup', detail: 'Verify, then go live', state: 'current' }]} />
            </Card>

            {toast.text && <Callout tone={toast.type === 'success' ? 'ok' : 'critical'}>{toast.text}</Callout>}
            {error && <ErrorState message={error} onRetry={loadSetup} />}

            <Card
                title="Tenant Launch Readiness"
                description={`${summary.completed} of ${summary.required} required checks verified`}
                actions={<Badge tone={summary.isLive ? 'ok' : summary.canGoLive ? 'warning' : 'critical'}>{summary.isLive ? 'Live' : summary.canGoLive ? 'Ready to enable' : `${summary.blockers.length} blockers`}</Badge>}
            >
                <div className="nx-ls-progress">
                    <ProgressBar value={summary.completed} max={summary.required} tone={summary.canGoLive ? 'ok' : 'warning'} label="Required checks verified" />
                    <strong>{summary.completed}/{summary.required}</strong>
                </div>
                {summary.blockers.length > 0 && (
                    <div className="nx-ls-blockers">
                        <Callout tone="warning">{`Blocked: ${summary.blockers.map((item) => item.label).join(', ')}`}</Callout>
                    </div>
                )}
                <div>
                    {checklist.map((item) => (
                        <div key={item.key} className="nx-ls-row" data-done={item.done ? 'true' : undefined}>
                            <ReadinessIcon state={item.done ? 'complete' : item.optional ? 'optional' : 'todo'} />
                            <div className="nx-ls-copy">
                                <strong>
                                    {item.label}
                                    {item.optional && <span className="nx-tag">Optional</span>}
                                    {item.manual && <Badge tone="warning" dot={false}>Manual</Badge>}
                                </strong>
                                <p>{item.desc}</p>
                                <small>{item.source}</small>
                            </div>
                            {item.manual ? (
                                <button
                                    type="button"
                                    className={item.done ? 'nx-btn nx-btn-sm' : 'nx-btn nx-btn-primary nx-btn-sm'}
                                    disabled={savingKey === item.key}
                                    onClick={() => toggleManualStep(item.key, !item.done)}
                                >
                                    {savingKey === item.key ? 'Saving…' : item.done ? 'Unmark' : 'Mark verified'}
                                </button>
                            ) : item.link && !item.done ? (
                                <Link href={item.link} className="nx-btn nx-btn-sm">{item.action} →</Link>
                            ) : (
                                <Badge tone={item.done ? 'ok' : 'neutral'}>{item.done ? 'Verified' : 'Pending'}</Badge>
                            )}
                        </div>
                    ))}
                </div>
            </Card>

            <Card tone={summary.canGoLive ? 'ok' : undefined}>
                <div className="nx-ls-live">
                    <p>
                        {summary.canGoLive
                            ? 'All required checks are complete. Enabling live status records operator approval; it does not replace a real WhatsApp smoke test.'
                            : 'Complete all required checks before enabling this tenant for production grievance traffic.'}
                    </p>
                    <button
                        type="button"
                        className="nx-btn nx-btn-primary"
                        disabled={!summary.canGoLive || savingKey === 'live' || summary.isLive}
                        onClick={() => toggleManualStep('live', true)}
                    >
                        {summary.isLive ? 'Live Enabled' : savingKey === 'live' ? 'Enabling…' : 'Enable Production Traffic'}
                    </button>
                </div>
            </Card>
        </div>
    );
}
