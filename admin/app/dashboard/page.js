'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { apiGet } from '@/lib/api';
import { AdminDataState } from '@/components/admin-ui/AdminPrimitives';

function timeAgo(value) {
    if (!value) return 'No recent observation';
    const seconds = Math.max(0, (Date.now() - new Date(value).getTime()) / 1000);
    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)} hr ago`;
    return `${Math.floor(seconds / 86400)} d ago`;
}
function destination(alert) {
    if (alert.type === 'setup_incomplete') return `/dashboard/mps/${alert.tenant_id}/setup`;
    if (alert.type === 'low_completeness') return `/dashboard/accounts?tenant_id=${alert.tenant_id}`;
    if (alert.type === 'tenant_inactive') return `/dashboard/system/health?tenant_id=${alert.tenant_id}`;
    if (alert.type?.startsWith('whatsapp_inbound')) return '/dashboard/system/whatsapp-inbound';
    if (alert.type === 'whatsapp_health') return '/dashboard/system/whatsapp';
    if (alert.type?.startsWith('job_')) return '/dashboard/system/jobs';
    return alert.tenant_id ? `/dashboard/mps/${alert.tenant_id}` : '/dashboard/system/health';
}
function tone(severity) {
    return severity === 'critical' || severity === 'error' ? 'critical' : severity === 'warning' ? 'warning' : 'review';
}

export default function DashboardOverview() {
    const [stats, setStats] = useState(null);
    const [accounts, setAccounts] = useState([]);
    const [alerts, setAlerts] = useState([]);
    const [health, setHealth] = useState(null);
    const [state, setState] = useState({ stats:'loading', accounts:'loading', alerts:'loading', health:'loading' });
    const [errors, setErrors] = useState({});
    const load = useCallback(async (key, path, apply) => {
        setState(s => ({...s,[key]:'loading'})); setErrors(e => ({...e,[key]:''}));
        try { const result = await apiGet(path); apply(result); setState(s => ({...s,[key]:'ready'})); }
        catch (error) { setErrors(e => ({...e,[key]:error.message || 'Data unavailable'})); setState(s => ({...s,[key]:'error'})); }
    }, []);
    const loaders = useMemo(() => ({
        stats:()=>load('stats','/api/admin/stats',setStats),
        accounts:()=>load('accounts','/api/admin/mps',r=>setAccounts(r.mps||[])),
        alerts:()=>load('alerts','/api/admin/alerts',r=>setAlerts(r.alerts||[])),
        health:()=>load('health','/api/admin/system-health',setHealth),
    }),[load]);
    useEffect(()=>{ Object.values(loaders).forEach(fn=>fn()); },[loaders]);

    const sortedAlerts = useMemo(()=>[...alerts].sort((a,b)=>({critical:0,error:0,warning:1,info:2}[a.severity]??3)-({critical:0,error:0,warning:1,info:2}[b.severity]??3)),[alerts]);
    const blocked = alerts.filter(a=>a.type==='setup_incomplete').length;
    const stale = alerts.filter(a=>a.type==='tenant_inactive').length;
    const missingWhatsApp = accounts.filter(a=>!a.whatsapp_number || String(a.whatsapp_number).startsWith('temp_')).length;
    const attentionAccounts = new Set(alerts.filter(a=>a.tenant_id).map(a=>a.tenant_id)).size;
    const services = health ? [
        ['WhatsApp',health.whatsapp?.status,health.whatsapp?.reason || (health.whatsapp?.last_webhook ? `Last activity ${timeAgo(health.whatsapp.last_webhook)}` : 'No recent webhook'),'/dashboard/system/whatsapp'],
        ['OpenAI',health.openai?.status,health.openai?.configured?'Configured':'Not configured','/dashboard/cases-intelligence/engine'],
        ['Gemini',health.gemini?.status,health.gemini?.configured?'Configured':'Not configured','/dashboard/cases-intelligence/engine'],
    ] : [];

    return <div className="command-centre-v2">
        <section className="cc-hero">
            <div>
                <span className="cc-kicker">Platform command</span>
                <h2>Command Centre</h2>
                <p>See what needs intervention, confirm platform readiness, and move directly into the affected operation.</p>
            </div>
            <div className="cc-hero-actions">
                <Link className="btn-secondary" href="/dashboard/staff-access/audit">Audit log</Link>
                <button className="btn-primary" type="button" onClick={()=>Object.values(loaders).forEach(fn=>fn())}>Refresh data</button>
            </div>
        </section>

        <section className="cc-kpi-grid" aria-label="Operational overview">
            <Link href="/dashboard/accounts" className="cc-kpi"><span>Customer accounts</span><strong>{state.stats==='error'?'—':(stats?.total_accounts ?? stats?.total_mps ?? accounts.length)}</strong><small>Open account workspace →</small></Link>
            <div className="cc-kpi" data-tone={alerts.length?'danger':'success'}><span>Needs attention</span><strong>{state.alerts==='error'?'—':alerts.length}</strong><small>{state.alerts==='error'?'Alert data unavailable':`${attentionAccounts} affected accounts`}</small></div>
            <div className="cc-kpi" data-tone={blocked?'warning':'success'}><span>Launch blockers</span><strong>{state.alerts==='error'?'—':blocked}</strong><small>{blocked?'Setup intervention required':'No blocked launches'}</small></div>
            <Link href="/dashboard/system/whatsapp" className="cc-kpi" data-tone={missingWhatsApp?'warning':'success'}><span>Messaging readiness</span><strong>{state.accounts==='error'?'—':missingWhatsApp}</strong><small>{missingWhatsApp?'accounts missing WhatsApp':'All accounts configured'} →</small></Link>
            <Link href="/dashboard/cases-intelligence/explorer" className="cc-kpi"><span>Total cases</span><strong>{state.stats==='error'?'—':(stats?.total_cases ?? '—')}</strong><small>Open case intelligence →</small></Link>
        </section>

        <div className="cc-primary-grid">
            <section className="cc-panel cc-attention">
                <header className="cc-panel-head"><div><span className="cc-kicker">Priority queue</span><h3>Needs attention</h3><p>Highest-severity exceptions only. Resolve the issue in context.</p></div><span className="cc-count">{alerts.length || 0} open</span></header>
                <AdminDataState loading={state.alerts==='loading'} error={errors.alerts} empty={!errors.alerts && state.alerts!=='loading' && sortedAlerts.length===0} emptyTitle="No active operational alerts" emptyDescription="Current checks returned no issues." onRetry={loaders.alerts}>
                    <div className="cc-alert-list">{sortedAlerts.slice(0,5).map((alert,index)=><Link href={destination(alert)} className="cc-alert" data-tone={tone(alert.severity)} key={`${alert.type}-${alert.tenant_id||'platform'}-${index}`}>
                        <span className="cc-alert-marker" /><span className="cc-alert-copy"><strong>{alert.title}</strong><small>{alert.description}</small></span><span className="cc-alert-scope">{alert.tenant_id?`Account #${alert.tenant_id}`:'Platform'}</span><span className="cc-arrow">→</span>
                    </Link>)}</div>
                    {sortedAlerts.length>5 && <div className="cc-panel-foot"><Link href="/dashboard/system/health">View all {sortedAlerts.length} operational alerts →</Link></div>}
                </AdminDataState>
            </section>

            <section className="cc-panel">
                <header className="cc-panel-head"><div><span className="cc-kicker">Live services</span><h3>Platform health</h3><p>{health?.last_checked?`Checked ${timeAgo(health.last_checked)}`:'Service readiness and configuration'}</p></div><Link href="/dashboard/system/health">Details →</Link></header>
                <AdminDataState loading={state.health==='loading'} error={errors.health} onRetry={loaders.health}>
                    <div className="cc-service-list">{services.map(([name,status,detail,href])=><Link href={href} className="cc-service" key={name}><span className="cc-service-dot" data-status={status||'red'} /><span><strong>{name}</strong><small>{detail}</small></span><span>→</span></Link>)}</div>
                </AdminDataState>
                <div className="cc-health-links"><Link href="/dashboard/system/jobs">Background jobs →</Link><Link href="/dashboard/system/parliament-sync">Parliament sync →</Link></div>
            </section>
        </div>

        <div className="cc-secondary-grid">
            <section className="cc-panel">
                <header className="cc-panel-head"><div><span className="cc-kicker">Customer readiness</span><h3>Accounts requiring intervention</h3><p>Go to Accounts for the complete registry.</p></div><Link className="btn-secondary" href="/dashboard/accounts">Open Accounts</Link></header>
                <AdminDataState loading={state.accounts==='loading'} error={errors.accounts} onRetry={loaders.accounts}>
                    <div className="cc-readiness-row"><div><strong>{stale}</strong><span>Stale accounts</span></div><div><strong>{missingWhatsApp}</strong><span>Missing WhatsApp</span></div><div><strong>{accounts.filter(a=>(a.completeness||0)<70).length}</strong><span>Incomplete profiles</span></div><div><strong>{blocked}</strong><span>Blocked launches</span></div></div>
                </AdminDataState>
            </section>
            <section className="cc-panel cc-quick">
                <header className="cc-panel-head"><div><span className="cc-kicker">Shortcuts</span><h3>Common operations</h3></div></header>
                <div className="cc-quick-links"><Link href="/dashboard/accounts/new">Create account <span>→</span></Link><Link href="/dashboard/system/whatsapp">WhatsApp operations <span>→</span></Link><Link href="/dashboard/seats">Seats & geography <span>→</span></Link><Link href="/dashboard/cases-intelligence/explorer">Case intelligence <span>→</span></Link></div>
            </section>
        </div>
    </div>;
}
