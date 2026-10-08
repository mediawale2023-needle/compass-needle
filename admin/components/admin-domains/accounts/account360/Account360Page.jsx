'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { ClipboardCheck, Inbox, Landmark, MapPin, MessageCircle, MoreHorizontal, Pencil, Rocket, TriangleAlert, Users } from 'lucide-react';
import {
    accountCondition, accountIdentity, formatRelative, readinessColumns, SEVERITY_LABEL,
} from '@/lib/admin-data';
import {
    Avatar, Badge, Callout, Card, ErrorState, IncidentBanner, LoadingSkeleton, MobileDisclosure, ReadinessRail, useMediaQuery,
} from '@/components/admin-ui';
import { useAccount360Data } from './useAccount360Data';
import {
    ActivityCard, CaseOperationsCard, GeographyCard, IntelligenceCard, NotesPanel, ProfileSettingsPanel, StaffPanel,
    SupportAccessPanel, WhatsAppCard, WhatsAppConfigPanel,
} from './panels';
import '@/app/styles/admin-account360.css';

// Hash ↔ tab. Legacy anchors (#profile from the launch checklist, #whatsapp,
// #staff, #activity, #cases, #overview) keep working.
export const ACCOUNT_TABS = [
    { key: 'overview', label: 'Overview' },
    { key: 'cases', label: 'Cases' },
    { key: 'whatsapp', label: 'Messaging' },
    { key: 'staff', label: 'Staff' },
    { key: 'geography', label: 'Geography' },
    { key: 'intelligence', label: 'Intelligence' },
    { key: 'activity', label: 'Activity' },
    { key: 'settings', label: 'Settings' },
];
const HASH_ALIASES = { profile: 'settings', messaging: 'whatsapp', support: 'settings', notes: 'activity' };

function tabFromHash(hash) {
    const key = String(hash || '').replace(/^#/, '');
    const resolved = HASH_ALIASES[key] || key;
    return ACCOUNT_TABS.some((tab) => tab.key === resolved) ? resolved : 'overview';
}

const RAIL_ICONS = { whatsapp: MessageCircle, onboarding: ClipboardCheck, staff: Users, geography: MapPin, intelligence: Landmark, cases: Inbox };

function useToast() {
    const [toast, setToast] = useState(null);
    const timer = useRef(null);
    const notify = useCallback((text, tone = 'ok') => {
        setToast({ text, tone });
        window.clearTimeout(timer.current);
        timer.current = window.setTimeout(() => setToast(null), tone === 'error' ? 4000 : 3000);
    }, []);
    useEffect(() => () => window.clearTimeout(timer.current), []);
    return { toast, notify };
}

function MoreActions({ onSelect, tenantId }) {
    const [open, setOpen] = useState(false);
    const ref = useRef(null);
    useEffect(() => {
        if (!open) return undefined;
        const close = (event) => { if (ref.current && !ref.current.contains(event.target)) setOpen(false); };
        const key = (event) => { if (event.key === 'Escape') setOpen(false); };
        document.addEventListener('mousedown', close);
        document.addEventListener('keydown', key);
        return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', key); };
    }, [open]);
    const item = (label, action) => (
        <button type="button" role="menuitem" className="nx-menu-item" onClick={() => { setOpen(false); action(); }}>{label}</button>
    );
    return (
        <div className="nx-popover-anchor" ref={ref}>
            <button type="button" className="nx-icon-button" aria-label="More actions" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
                <MoreHorizontal size={18} aria-hidden="true" />
            </button>
            {open && (
                <div className="nx-popover nx-menu" role="menu" aria-label="Account actions">
                    {item('Request support access', () => onSelect('settings', 'support-access'))}
                    {item('Edit WhatsApp routing', () => onSelect('whatsapp', 'edit'))}
                    {item('Add staff', () => onSelect('staff'))}
                    {item('Add admin note', () => onSelect('activity'))}
                    <Link role="menuitem" className="nx-menu-item" href={`/dashboard/mps/${tenantId}/setup`}>Launch setup checklist</Link>
                </div>
            )}
        </div>
    );
}

export default function Account360Page({ tenantId }) {
    const { data, status, reload, setLocal } = useAccount360Data(tenantId);
    const { toast, notify } = useToast();
    const [tab, setTab] = useState('overview');
    const [editWhatsApp, setEditWhatsApp] = useState(false);
    const compact = useMediaQuery('(max-width: 760px)');

    useEffect(() => {
        const sync = () => setTab(tabFromHash(window.location.hash));
        sync();
        window.addEventListener('hashchange', sync);
        return () => window.removeEventListener('hashchange', sync);
    }, []);

    const openTab = useCallback((key, focus) => {
        setTab(key);
        setEditWhatsApp(focus === 'edit');
        if (typeof window !== 'undefined') {
            window.history.replaceState(null, '', `#${key === 'settings' && focus === 'support-access' ? 'support' : key}`);
            window.requestAnimationFrame?.(() => {
                const target = focus === 'support-access' ? document.getElementById('support-access') : document.getElementById('nx-a3-tabs');
                target?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
            });
        }
    }, []);

    const detail = data.detail;
    const identity = useMemo(() => ({ ...accountIdentity(detail, tenantId), lastCase: detail?.cases?.last_case || null }), [detail, tenantId]);
    const condition = useMemo(() => accountCondition({
        tenantId,
        whatsapp: data.health?.whatsapp || null,
        outboundItems: status.outbound === 'ready' ? data.outbound : null,
        alerts: status.alerts === 'ready' ? data.alerts : null,
    }), [tenantId, data.health, data.outbound, data.alerts, status.outbound, status.alerts]);
    const columns = useMemo(() => readinessColumns({
        tenantId,
        detail,
        geography: status.geography === 'ready' ? data.geography : null,
        whatsapp: data.health?.whatsapp || null,
        outboundItems: status.outbound === 'ready' ? data.outbound : null,
        parliament: status.parliament === 'ready' ? data.parliament : null,
        cases: status.cases === 'ready' ? data.cases : null,
    }), [tenantId, detail, data, status]);

    if (status.detail === 'error' && !detail) {
        return <div className="nx-a3"><ErrorState title="Account unavailable" message="The account could not be loaded." onRetry={() => reload('detail')} /></div>;
    }
    if (!detail) {
        return <div className="nx-a3"><LoadingSkeleton rows={8} label="Loading account" /></div>;
    }

    const readyCount = columns.filter((column) => column.tone === 'ok').length;
    const lead = condition.reasons[0] || null;
    const severity = condition.severity;
    const onSavedDetail = (fresh) => setLocal('detail', fresh);
    const accountReasonsReady = condition.sources.whatsapp || condition.sources.alerts || condition.sources.outbound;

    return (
        <div className="nx-a3">
            {toast && <div className={`nx-toast`} data-tone={toast.tone === 'error' ? 'critical' : 'ok'} role="status">{toast.text}</div>}

            <section className="nx-a3-band" aria-label="Account">
                <div className="nx-a3-identity">
                    <Avatar name={identity.name || '?'} size="lg" tint="forest" />
                    <div className="nx-a3-identity-copy">
                        <div className="nx-a3-title-row">
                            <h1>{identity.name || 'Account name unavailable'}</h1>
                            {identity.roleLabel && <Badge tone="neutral" dot={false}>{[identity.roleLabel, identity.stageLabel].filter(Boolean).join(' · ')}</Badge>}
                            {accountReasonsReady
                                ? <Badge tone={severity}>{severity === 'ok' ? 'No account issues' : `Condition: ${SEVERITY_LABEL[severity]}`}</Badge>
                                : <span className="nx-unavailable">Condition unavailable</span>}
                        </div>
                        <p className="nx-a3-meta">
                            <span className="nx-a3-meta-item"><MapPin size={14} aria-hidden="true" />{[identity.constituency || 'No constituency', identity.state].filter(Boolean).join(' · ')}</span>
                            {identity.party && <span className="nx-a3-meta-item">{identity.party}</span>}
                            <span className="nx-a3-meta-item">Tenant #{identity.tenantId}</span>
                            {identity.createdAt && <span className="nx-a3-meta-item">Since {new Date(identity.createdAt).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' })}</span>}
                            <span className="nx-a3-meta-item">Last login {identity.lastLogin ? formatRelative(identity.lastLogin) : 'never'}</span>
                        </p>
                    </div>
                    <div className="nx-a3-actions">
                        <Link className="nx-btn" href={`/dashboard/mps/${tenantId}/setup`}><Rocket size={16} aria-hidden="true" />Launch setup</Link>
                        <Link className="nx-btn" href={`/dashboard/accounts/registry?tenant_id=${tenantId}`}><Pencil size={16} aria-hidden="true" />Edit account</Link>
                        <MoreActions tenantId={tenantId} onSelect={(key, focus) => openTab(key, focus)} />
                    </div>
                </div>
                <nav id="nx-a3-tabs" className="nx-tabs nx-a3-tabs" aria-label="Account sections">
                    {ACCOUNT_TABS.map((item) => (
                        <a
                            key={item.key}
                            href={`#${item.key}`}
                            className="nx-tab"
                            aria-current={tab === item.key ? 'page' : undefined}
                            onClick={(event) => { event.preventDefault(); openTab(item.key); }}
                        >
                            {item.label}
                            {item.key === 'cases' && data.cases ? <span className="nx-count">{data.cases.open_now}</span> : null}
                            {item.key === 'staff' ? <span className="nx-count">{(detail.staff || []).length}</span> : null}
                            {item.key === 'whatsapp' && columns[0].tone === 'warning' ? <span className="nx-dot" data-tone="warning" aria-label="needs attention" /> : null}
                        </a>
                    ))}
                </nav>
            </section>

            {condition.platformIncidents.length > 0 && (
                <Callout tone="info" title="Platform-wide:" action={<Link className="nx-link" href="/dashboard/system/whatsapp">Open Messaging →</Link>}>
                    {condition.platformIncidents.map((incident) => incident.title).join(' · ')}. This affects every account and is not specific to this one.
                </Callout>
            )}

            {tab === 'overview' && (
                <>
                    {lead && (severity === 'critical' || severity === 'warning') && (
                        <IncidentBanner
                            severity={lead.severity}
                            icon={lead.source?.startsWith('whatsapp') ? MessageCircle : TriangleAlert}
                            title={lead.label}
                            meta={condition.reasons.length > 1 ? `${condition.reasons.length} account issues` : 'This account'}
                            detail={lead.detail || null}
                            actions={lead.source?.startsWith('whatsapp')
                                ? <button type="button" className="nx-btn nx-btn-primary nx-btn-sm" onClick={() => openTab('whatsapp', 'edit')}>Fix WhatsApp routing</button>
                                : <Link className="nx-btn nx-btn-primary nx-btn-sm" href={`/dashboard/mps/${tenantId}/setup`}>Open launch setup</Link>}
                        />
                    )}

                    <Card title="Account readiness" description={`${readyCount} of ${columns.length} areas ready`}>
                        <ReadinessRail items={columns.map((column) => ({ label: column.label, tone: column.tone, status: column.status, detail: column.detail, icon: RAIL_ICONS[column.key] }))} />
                    </Card>

                    <div className="nx-split-grid" data-align="stretch">
                        <CaseOperationsCard tenantId={tenantId} cases={data.cases} detail={detail} status={status.cases} onRetry={() => reload('cases')} />
                        <WhatsAppCard identity={identity} condition={condition} health={data.health} outbound={data.outbound} outboundStatus={status.outbound} onEdit={() => openTab('whatsapp', 'edit')} />
                    </div>

                    <MobileDisclosure compact={compact} title="Staff & geography" hint={`${(detail.staff || []).filter((m) => m.is_active).length} active staff · ${columns[3].status.toLowerCase()} geography`}>
                        <div className="nx-split-grid" data-align="stretch">
                            <StaffPanel compact tenantId={tenantId} staff={detail.staff} onSaved={onSavedDetail} notify={notify} onOpenTab={openTab} />
                            <GeographyCard tenantId={tenantId} identity={identity} geography={data.geography} geographyStatus={status.geography} decisions={data.decisions} decisionsStatus={status.decisions} />
                        </div>
                    </MobileDisclosure>

                    <MobileDisclosure compact={compact} title="Intelligence & activity" hint="Parliament sync, AI context and recent activity">
                        <div className="nx-split-grid">
                            <IntelligenceCard tenantId={tenantId} parliament={data.parliament} parliamentStatus={status.parliament} identity={identity} />
                            <ActivityCard activity={detail.activity} limit={5} onOpenTab={openTab} />
                        </div>
                    </MobileDisclosure>
                </>
            )}

            {tab === 'cases' && (
                <CaseOperationsCard expanded tenantId={tenantId} cases={data.cases} detail={detail} status={status.cases} onRetry={() => reload('cases')} />
            )}

            {tab === 'whatsapp' && (
                <div className="nx-a3-stack" id="whatsapp">
                    {condition.failures && (
                        <Callout tone="warning" title={`${condition.failures.failed} failed WhatsApp ${condition.failures.failed === 1 ? 'reply' : 'replies'}.`}>
                            {condition.failures.lastError ? String(condition.failures.lastError).slice(0, 200) : 'See recent outbound messages below.'}
                        </Callout>
                    )}
                    <WhatsAppConfigPanel key={editWhatsApp ? 'edit' : 'view'} startEditing={editWhatsApp} tenantId={tenantId} identity={identity} onSaved={onSavedDetail} notify={notify} outbound={data.outbound} outboundStatus={status.outbound} />
                </div>
            )}

            {tab === 'staff' && (
                <div id="staff"><StaffPanel tenantId={tenantId} staff={detail.staff} onSaved={onSavedDetail} notify={notify} onOpenTab={openTab} /></div>
            )}

            {tab === 'geography' && (
                <GeographyCard expanded tenantId={tenantId} identity={identity} geography={data.geography} geographyStatus={status.geography} decisions={data.decisions} decisionsStatus={status.decisions} />
            )}

            {tab === 'intelligence' && (
                <IntelligenceCard expanded tenantId={tenantId} parliament={data.parliament} parliamentStatus={status.parliament} identity={identity} />
            )}

            {tab === 'activity' && (
                <div className="nx-split-grid" id="activity">
                    <ActivityCard activity={detail.activity} limit={20} />
                    <NotesPanel tenantId={tenantId} notes={data.notes} onSaved={(notes) => setLocal('notes', notes)} notify={notify} />
                </div>
            )}

            {tab === 'settings' && (
                <div className="nx-a3-stack">
                    <ProfileSettingsPanel tenantId={tenantId} identity={identity} detail={detail} />
                    <SupportAccessPanel tenantId={tenantId} requests={data.support} reload={() => reload('support')} notify={notify} />
                </div>
            )}
        </div>
    );
}
