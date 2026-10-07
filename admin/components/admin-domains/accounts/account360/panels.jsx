'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Bot, MapPin, Landmark, Plus } from 'lucide-react';
import { apiGet, apiPatch, apiPost } from '@/lib/api';
import {
    caseTrend, decisionSummary, formatCount, formatDuration, formatRelative, openOverDays, parliamentForAccount,
} from '@/lib/admin-data';
import {
    AccountIdentity, Badge, BarList, Card, ChartLegend, DataState, EmptyState, Field, KeyValueList, LineChart, Metric,
    MetricGroup, SeverityTile, StatusText, TextInput, Timeline, Unavailable,
} from '@/components/admin-ui';

const AGE_TONES = ['forest', 'forest-2', 'forest-3', 'warning', 'critical'];

function formatDate(value) {
    if (!value || value === 'Never') return null;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

// ─── Cases ────────────────────────────────────────────────────────────────

export function CaseOperationsCard({ tenantId, cases, detail, status, onRetry, expanded = false }) {
    const trend = cases ? caseTrend(cases) : null;
    const over14 = cases ? openOverDays(cases, 14) : null;
    const median = cases ? formatDuration(cases.resolution?.median_hours) : null;
    const categories = (cases?.open_by_category || []).slice(0, expanded ? 10 : 6);
    const maxCategory = Math.max(1, ...categories.map((c) => c.count));
    return (
        <Card
            title="Case operations"
            description="This account · last 12 weeks"
            actions={<Link className="nx-link" href={`/dashboard/cases-intelligence/explorer?tenant_id=${tenantId}`}>Open cases →</Link>}
        >
            <div className="nx-a3-pad">
                <DataState loading={status === 'loading' && !cases} error={status === 'error' ? 'Case aggregates could not be loaded.' : null} onRetry={onRetry} rows={4}>
                    {cases && (
                        <>
                            <MetricGroup columns={4}>
                                <Metric label="Open cases" value={formatCount(cases.open_now)} detail={trend?.openChange !== null && trend?.openChange !== undefined ? `${trend.openChange > 0 ? '+' : ''}${trend.openChange} since last week` : null} />
                                <Metric label="Older than 14 days" value={formatCount(over14)} tone={over14 ? 'warning' : undefined} detail={cases.open_now ? `${Math.round((over14 / cases.open_now) * 100)}% of open` : null} />
                                <Metric label="Median time to resolve" value={median} unavailable={!median} detail={median ? `${formatCount(cases.resolution.resolved_in_window)} resolved` : null} />
                                <Metric label="All-time cases" value={formatCount(detail?.cases?.total)} detail={detail?.cases?.last_case ? `Last ${formatRelative(detail.cases.last_case)}` : null} />
                            </MetricGroup>
                            <div className="nx-a3-cases-body">
                                <div className="nx-a3-chart">
                                    <ChartLegend items={[{ label: 'New', tone: 'forest' }, { label: 'Resolved', tone: 'mint' }]} />
                                    {trend && trend.labels.length >= 2
                                        ? <LineChart ariaLabel="Weekly new and resolved cases for this account" labels={trend.labels} height={200} viewWidth={440} series={[{ label: 'New', values: trend.newCases, tone: 'forest' }, { label: 'Resolved', values: trend.resolved, tone: 'mint' }]} />
                                        : <p className="nx-a3-note">Weekly trend appears after two completed weeks.</p>}
                                </div>
                                <div className="nx-a3-categories">
                                    <div className="nx-a3-subtitle">Open cases by category</div>
                                    {categories.length
                                        ? <BarList max={maxCategory} items={categories.map((c, index) => ({ label: c.category, value: c.count, tone: index === 0 ? 'forest' : index === 1 ? 'forest-2' : 'forest-3' }))} />
                                        : <p className="nx-a3-note">No open cases.</p>}
                                </div>
                            </div>
                            {expanded && (
                                <div className="nx-a3-ageing">
                                    <div className="nx-a3-subtitle">Open cases by age</div>
                                    <BarList items={(cases.ageing || []).map((band, index) => ({ label: band.label, value: band.count, tone: AGE_TONES[index] }))} />
                                    <p className="nx-a3-note">Age since the case was created. Needle defines no resolution deadline.</p>
                                </div>
                            )}
                        </>
                    )}
                </DataState>
            </div>
        </Card>
    );
}

// ─── WhatsApp ─────────────────────────────────────────────────────────────

export function WhatsAppCard({ identity, condition, health, outbound, outboundStatus, onEdit }) {
    const routingIssue = (health?.whatsapp?.routing?.tenant_issues || []).find((issue) => String(issue.tenant_id) === String(identity.tenantId));
    const configured = Boolean(identity.whatsappNumber && identity.phoneNumberId);
    const tone = routingIssue || !configured ? 'warning' : condition?.failures ? 'warning' : 'ok';
    const state = routingIssue ? 'Routing incomplete' : !configured ? 'Not configured' : condition?.failures ? 'Delivery failures' : 'Configured';
    const counts = outbound ? outbound.reduce((acc, row) => { const key = String(row.status || '').toLowerCase(); acc[key] = (acc[key] || 0) + 1; return acc; }, {}) : null;
    const token = health?.whatsapp?.meta_token;
    return (
        <Card
            title="WhatsApp"
            description={identity.name ? `Office of ${identity.name}` : 'Account messaging'}
            actions={<Badge tone={tone}>{state}</Badge>}
            footer={(
                <>
                    <button type="button" className="nx-btn nx-btn-sm" onClick={onEdit}>{routingIssue || !configured ? 'Fix WhatsApp routing' : 'Edit routing'}</button>
                    <Link className="nx-link" href="/dashboard/system/whatsapp">Messaging →</Link>
                </>
            )}
        >
            <KeyValueList items={[
                { label: 'Number', value: identity.whatsappNumber || <span className="nx-unavailable">Not set</span> },
                { label: 'Meta phone number ID', value: identity.phoneNumberId ? `•••• ${String(identity.phoneNumberId).slice(-4)}` : <span className="nx-unavailable">Not set</span>, tone: identity.phoneNumberId ? undefined : 'warning' },
                { label: 'Routing', value: routingIssue ? routingIssue.issue : configured ? 'Mapped to this account' : 'Incomplete', tone: routingIssue || !configured ? 'warning' : undefined },
                { label: 'Outbound (latest 100)', value: counts ? `${counts.sent || 0} sent · ${counts.pending || 0} pending · ${counts.failed || 0} failed` : outboundStatus === 'error' ? <Unavailable /> : '…', tone: counts?.failed ? 'warning' : undefined },
                { label: 'Last case received', value: identity.lastCase ? formatRelative(identity.lastCase) : '—' },
                { label: 'Meta token (platform)', value: token ? ({ green: 'Valid', amber: 'Not verified', red: 'Invalid — all accounts' }[token.status] || 'Unknown') : <Unavailable />, tone: token?.status === 'red' ? 'critical' : undefined },
            ]} />
        </Card>
    );
}

export function WhatsAppConfigPanel({ tenantId, identity, onSaved, notify, outbound, outboundStatus, startEditing = false }) {
    const [editing, setEditing] = useState(startEditing);
    const [number, setNumber] = useState(identity.whatsappNumber || '');
    const [phoneId, setPhoneId] = useState(identity.phoneNumberId || '');
    const [saving, setSaving] = useState(false);

    const save = async () => {
        if (!number.trim()) { notify('WhatsApp number is required', 'error'); return; }
        if (!number.startsWith('+')) { notify('Number must start with + (e.g. +919876543210)', 'error'); return; }
        setSaving(true);
        try {
            await apiPatch(`/api/admin/mps/${tenantId}/whatsapp`, { whatsapp_number: number.trim(), phone_number_id: phoneId.trim() });
            const fresh = await apiGet(`/api/admin/mps/${tenantId}/detail`);
            onSaved(fresh);
            setNumber(fresh?.profile?.whatsapp_number || '');
            setPhoneId(fresh?.profile?.phone_number_id || '');
            setEditing(false);
            notify('WhatsApp settings saved');
        } catch (error) {
            notify(error.message || 'Failed to save WhatsApp settings', 'error');
        }
        setSaving(false);
    };

    const recent = (outbound || []).slice(0, 8);
    return (
        <>
            <Card
                title="WhatsApp configuration"
                description="Tenant routing: the number citizens message and its Meta phone number ID."
                actions={!editing ? <button type="button" className="nx-btn nx-btn-sm" onClick={() => setEditing(true)}>Edit</button> : null}
            >
                {!editing ? (
                    <KeyValueList items={[
                        { label: 'WhatsApp number', value: identity.whatsappNumber || <span className="nx-unavailable">Not set</span> },
                        { label: 'Meta phone number ID', value: identity.phoneNumberId || <span className="nx-unavailable">Not set</span> },
                    ]} />
                ) : (
                    <div className="nx-a3-form">
                        <div className="nx-a3-grid">
                            <Field label="WhatsApp number" required help="Must start with + country code. Unique across all MPs.">
                                {(props) => <TextInput {...props} type="tel" placeholder="+919876543210" value={number} onChange={(e) => setNumber(e.target.value)} />}
                            </Field>
                            <Field label="Meta phone number ID" help="From Meta Business Suite → WhatsApp → Phone Numbers.">
                                {(props) => <TextInput {...props} placeholder="e.g. 089911394213487" value={phoneId} onChange={(e) => setPhoneId(e.target.value)} />}
                            </Field>
                        </div>
                        <div className="nx-a3-form-actions">
                            <button type="button" className="nx-btn nx-btn-primary nx-btn-sm" disabled={saving} onClick={save}>{saving ? 'Saving…' : 'Save'}</button>
                            <button type="button" className="nx-btn nx-btn-sm" disabled={saving} onClick={() => { setNumber(identity.whatsappNumber || ''); setPhoneId(identity.phoneNumberId || ''); setEditing(false); }}>Cancel</button>
                        </div>
                    </div>
                )}
            </Card>
            <Card title="Recent outbound messages" description="Latest replies Needle sent or attempted for this account" actions={<Link className="nx-link" href="/dashboard/system/whatsapp#outbound">All outbound →</Link>}>
                <DataState loading={outboundStatus === 'loading' && !outbound} error={outboundStatus === 'error' ? 'Outbound messages could not be loaded.' : null} empty={Boolean(outbound) && recent.length === 0} emptyTitle="No outbound messages yet" rows={3}>
                    <ul className="nx-a3-list">
                        {recent.map((row) => (
                            <li key={row.id}>
                                <StatusText tone={row.status === 'failed' ? 'critical' : row.status === 'sent' ? 'ok' : 'warning'}>{row.status}</StatusText>
                                <span className="nx-a3-list-main">{(row.message_body || '').slice(0, 90) || '—'}{row.status === 'failed' && row.last_error ? <small>{String(row.last_error).slice(0, 140)}</small> : null}</span>
                                <span className="nx-muted nx-a3-list-time">{formatRelative(row.last_attempt_at || row.created_at) || '—'}</span>
                            </li>
                        ))}
                    </ul>
                </DataState>
            </Card>
        </>
    );
}

// ─── Staff ────────────────────────────────────────────────────────────────

const EMPTY_STAFF = { username: '', password: '', display_name: '', role: 'staff', phone: '' };

export function StaffPanel({ tenantId, staff, onSaved, notify, compact = false, onOpenTab }) {
    const [adding, setAdding] = useState(false);
    const [form, setForm] = useState(EMPTY_STAFF);
    const [saving, setSaving] = useState(false);
    const list = staff || [];
    const active = list.filter((member) => member.is_active).length;

    const add = async () => {
        if (!form.username.trim()) { notify('Username is required', 'error'); return; }
        if (!form.password) { notify('Password is required', 'error'); return; }
        setSaving(true);
        try {
            await apiPost('/api/admin/staff', {
                tenant_id: parseInt(tenantId, 10),
                username: form.username.trim(),
                password: form.password,
                display_name: form.display_name.trim(),
                role: form.role,
                phone: form.phone.trim(),
            });
            const fresh = await apiGet(`/api/admin/mps/${tenantId}/detail`);
            onSaved(fresh);
            setAdding(false);
            setForm(EMPTY_STAFF);
            notify(`@${form.username} added to team`);
        } catch (error) {
            notify(error.message || 'Failed to create staff', 'error');
        }
        setSaving(false);
    };

    const rows = compact ? list.slice(0, 5) : list;
    return (
        <Card
            id={compact ? undefined : 'staff-panel'}
            title="Staff & access"
            description={list.length ? `${active} active${list.length > active ? ` · ${list.length - active} suspended` : ''} · tenant staff accounts` : 'No staff accounts yet'}
            actions={compact
                ? <button type="button" className="nx-btn nx-btn-sm" onClick={() => onOpenTab('staff')}>Manage staff</button>
                : <button type="button" className="nx-btn nx-btn-sm" onClick={() => setAdding((value) => !value)}>{adding ? 'Cancel' : <><Plus size={14} aria-hidden="true" />Add staff</>}</button>}
            footer={compact && list.length > rows.length ? <><span>Showing {rows.length} of {list.length}</span><button type="button" className="nx-link nx-a3-linkbtn" onClick={() => onOpenTab('staff')}>All staff →</button></> : null}
        >
            {adding && !compact && (
                <div className="nx-a3-form nx-a3-form-tinted">
                    <div className="nx-a3-grid">
                        <Field label="Username" required>{(props) => <TextInput {...props} placeholder="pa_ravi" value={form.username} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} />}</Field>
                        <Field label="Display name" optional>{(props) => <TextInput {...props} placeholder="Full name" value={form.display_name} onChange={(e) => setForm((f) => ({ ...f, display_name: e.target.value }))} />}</Field>
                        <Field label="Password" required>{(props) => <TextInput {...props} type="password" placeholder="Min 8 chars" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} />}</Field>
                        <Field label="Role">
                            {(props) => (
                                <span className="nx-select">
                                    <select {...props} className="nx-input" value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}>
                                        <option value="staff">staff</option><option value="manager">manager</option><option value="user">user</option>
                                    </select>
                                </span>
                            )}
                        </Field>
                    </div>
                    <Field label="WhatsApp number" optional help="Enables PA case queries over WhatsApp.">
                        {(props) => <TextInput {...props} type="tel" placeholder="+919876543210" value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} />}
                    </Field>
                    <div className="nx-a3-form-actions">
                        <button type="button" className="nx-btn nx-btn-primary nx-btn-sm" disabled={saving} onClick={add}>{saving ? 'Creating…' : 'Create staff account'}</button>
                    </div>
                </div>
            )}
            {list.length === 0 ? (
                <EmptyState title="No staff assigned" description={compact ? 'Add the first staff account from the Staff tab.' : 'Use “Add staff” to create the first account.'} />
            ) : (
                <div className="nx-table-region" role="region" aria-label="Staff roster" tabIndex={0}>
                    <table className="nx-table" data-stack="true">
                        <thead><tr><th>Person</th><th>Role</th><th data-hide-below="sm">WhatsApp</th><th>Status</th><th style={{ textAlign: 'right' }}>Last login</th></tr></thead>
                        <tbody>
                            {rows.map((member) => (
                                <tr key={member.id}>
                                    <td data-label="Person"><AccountIdentity size="sm" name={member.display_name || member.username} detail={`@${member.username}`} /></td>
                                    <td data-label="Role"><Badge tone="neutral" dot={false}>{member.role}</Badge></td>
                                    <td data-label="WhatsApp" data-hide-below="sm" className="nx-muted">{member.phone || '—'}</td>
                                    <td data-label="Status"><StatusText tone={member.is_active ? 'ok' : 'critical'}>{member.is_active ? 'Active' : 'Suspended'}</StatusText></td>
                                    <td data-label="Last login" style={{ textAlign: 'right' }} className="nx-muted">{member.last_login ? formatRelative(member.last_login) || '—' : 'Never'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
            {!compact && (
                <p className="nx-a3-note nx-a3-pad-x">Suspend, reassign or edit staff in <Link className="nx-link" href="/dashboard/staff-access/users">People &amp; Access</Link>.</p>
            )}
        </Card>
    );
}

// ─── Geography ────────────────────────────────────────────────────────────

const DECISION_TONE = (item) => (item.needs_review ? 'warning' : item.resolved ? 'ok' : 'critical');

export function GeographyCard({ tenantId, geography, geographyStatus, decisions, decisionsStatus, identity, expanded = false }) {
    const assemblies = Object.entries(geography?.assemblies || {});
    const localities = assemblies.reduce((sum, [, list]) => sum + (list?.length || 0), 0);
    const summary = decisionSummary(decisions);
    const workspace = `/dashboard/shared-geography/workspace?tenant_id=${tenantId}`;
    return (
        <Card
            title="Geography"
            description={[identity.constituency, identity.state].filter(Boolean).join(' · ') || 'Seat geography'}
            actions={<Badge tone={localities ? 'ok' : 'warning'}>{localities ? 'Configured' : 'Not configured'}</Badge>}
            footer={(
                <>
                    <span>{summary ? (summary.review ? `${summary.review} location${summary.review === 1 ? '' : 's'} need review` : 'No locations awaiting review') : 'Location decisions unavailable'}</span>
                    <Link className="nx-link" href={workspace}>Geography workspace →</Link>
                </>
            )}
        >
            <div className="nx-a3-pad">
                {geographyStatus === 'error' ? <Unavailable>Saved geography unavailable</Unavailable> : (
                    <div className="nx-a3-geo-stats">
                        <div><strong>{formatCount(assemblies.length)}</strong><span>assemblies</span></div>
                        <div><strong>{formatCount(localities)}</strong><span>localities</span></div>
                        <div><strong>{summary ? formatCount(summary.total) : '—'}</strong><span>recent location decisions</span></div>
                    </div>
                )}
                {summary && summary.total > 0 && (
                    <div className="nx-a3-decisions">
                        <div className="nx-a3-subtitle">Latest case locations · one square per case</div>
                        <div className="nx-a3-squares" role="img" aria-label={`${summary.resolved} matched, ${summary.review} need review, ${summary.unresolved} unresolved`}>
                            {decisions.map((item) => <span key={item.case_id} data-tone={DECISION_TONE(item)} title={`${item.case_ref || `Case ${item.case_id}`}: ${item.matched_value || item.location || 'no location'}${item.needs_review ? ' — needs review' : ''}`} />)}
                        </div>
                        <div className="nx-legend">
                            <span><i data-tone="ok" aria-hidden="true" />{summary.resolved} matched</span>
                            <span><i data-tone="warning" aria-hidden="true" />{summary.review} need review</span>
                            <span><i data-tone="critical" aria-hidden="true" />{summary.unresolved} unresolved</span>
                        </div>
                    </div>
                )}
                {decisionsStatus === 'error' && <Unavailable>Location decisions unavailable</Unavailable>}
                {expanded && (
                    <>
                        {summary?.reviewItems?.length > 0 && (
                            <div className="nx-a3-review-list">
                                <div className="nx-a3-subtitle">Locations needing review</div>
                                <ul className="nx-a3-list">
                                    {summary.reviewItems.slice(0, 8).map((item) => (
                                        <li key={item.case_id}>
                                            <SeverityTile tone="warning" icon={MapPin} size="sm" />
                                            <span className="nx-a3-list-main">“{item.location || item.matched_value || 'Unknown'}”<small>{item.review_reason || 'Needs geography review'} · {item.case_ref || `Case ${item.case_id}`}</small></span>
                                            <span className="nx-muted nx-a3-list-time">{formatRelative(item.created_at) || ''}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                        <div className="nx-a3-subtitle">Assemblies</div>
                        {assemblies.length ? (
                            <ul className="nx-a3-assemblies">
                                {assemblies.map(([name, list]) => <li key={name}><span>{name}</span><span className="nx-muted">{formatCount(list?.length || 0)} localities</span></li>)}
                            </ul>
                        ) : <p className="nx-a3-note">No assembly localities saved yet.</p>}
                        <div className="nx-a3-form-actions">
                            <Link className="nx-btn nx-btn-sm" href={workspace}>Open geography workspace</Link>
                            <Link className="nx-btn nx-btn-sm" href="/dashboard/shared-geography/rules">Geography rules</Link>
                        </div>
                    </>
                )}
            </div>
        </Card>
    );
}

// ─── Intelligence ─────────────────────────────────────────────────────────

export function IntelligenceCard({ tenantId, parliament, parliamentStatus, identity, expanded = false }) {
    const record = parliament ? parliamentForAccount(parliament, tenantId) : null;
    const syncTone = !record ? 'neutral' : record.parliament_sync_status === 'needs_review' ? 'review' : record.parliament_last_synced ? 'ok' : 'neutral';
    return (
        <Card title="Intelligence" description="Sources Needle tracks for this account" actions={<Link className="nx-link" href="/dashboard/system/parliament-sync">Parliament Sync →</Link>}>
            <ul className="nx-a3-services">
                <li>
                    <SeverityTile tone={syncTone === 'ok' ? 'neutral' : syncTone} icon={Landmark} size="sm" />
                    <span className="nx-a3-service-copy">
                        <strong>Parliament questions &amp; answers</strong>
                        <small>
                            {parliamentStatus === 'error' ? 'Sync status unavailable'
                                : !record ? 'No sync record for this account'
                                : record.parliament_last_synced ? `Last synced ${formatRelative(record.parliament_last_synced)}${record.parliament_member_id ? ` · member ${record.parliament_member_id}` : ''}`
                                : `Status: ${record.parliament_sync_status || 'pending'}`}
                        </small>
                    </span>
                    {parliamentStatus === 'error' ? <Unavailable /> : <StatusText tone={syncTone}>{!record ? 'Not tracked' : record.parliament_sync_status === 'needs_review' ? 'Needs review' : record.parliament_last_synced ? 'Synced' : 'Not synced'}</StatusText>}
                </li>
                <li>
                    <SeverityTile tone="neutral" icon={Bot} size="sm" />
                    <span className="nx-a3-service-copy">
                        <strong>AI context (key facts)</strong>
                        <small>{identity.keyFacts.length ? `${identity.keyFacts.length} key facts used by drafting and Copilot` : 'No key facts yet'}</small>
                    </span>
                    <StatusText tone={identity.keyFacts.length ? 'ok' : 'warning'}>{identity.keyFacts.length ? 'Present' : 'Missing'}</StatusText>
                </li>
            </ul>
            {expanded && identity.keyFacts.length > 0 && (
                <div className="nx-a3-pad">
                    <div className="nx-a3-subtitle">Key facts</div>
                    <ul className="nx-a3-facts">{identity.keyFacts.map((fact, index) => <li key={index}>{fact}</li>)}</ul>
                </div>
            )}
            <p className="nx-a3-note nx-a3-pad-x">News, scheme and CSR matching are not reported per account by the Admin API, so they are not shown here.</p>
        </Card>
    );
}

// ─── Activity & notes ─────────────────────────────────────────────────────

function humanize(value) {
    const text = String(value || '').replace(/_/g, ' ').trim();
    return text ? text.charAt(0).toUpperCase() + text.slice(1) : '';
}

export function ActivityCard({ activity, limit = 6, onOpenTab }) {
    const items = (activity || []).slice(0, limit);
    return (
        <Card
            title="Recent activity"
            description="Account activity history"
            actions={onOpenTab ? <button type="button" className="nx-link nx-a3-linkbtn" onClick={() => onOpenTab('activity')}>All →</button> : null}
        >
            <div className="nx-a3-pad">
                {items.length ? (
                    <Timeline items={items.map((entry) => ({ title: entry.title || humanize(entry.activity_type), meta: `${formatRelative(entry.created_at) || '—'} · ${humanize(entry.activity_type)}` }))} />
                ) : <EmptyState title="No activity recorded yet" />}
            </div>
        </Card>
    );
}

export function NotesPanel({ tenantId, notes, onSaved, notify }) {
    const [text, setText] = useState('');
    const [saving, setSaving] = useState(false);
    const add = async () => {
        if (!text.trim()) return;
        setSaving(true);
        try {
            await apiPost(`/api/admin/mps/${tenantId}/notes`, { body: text.trim() });
            setText('');
            const result = await apiGet(`/api/admin/mps/${tenantId}/notes`);
            onSaved(result.notes || []);
            notify('Note added');
        } catch {
            notify('Failed to add note', 'error');
        }
        setSaving(false);
    };
    return (
        <Card title="Admin notes" description="Visible to Needle administrators only">
            <div className="nx-a3-pad">
                <div className="nx-a3-note-form">
                    <label htmlFor="nx-a3-note" className="nx-sr-only">Add a note about this account</label>
                    <textarea id="nx-a3-note" className="nx-input nx-textarea" rows={2} placeholder="Add a note about this account..." value={text} onChange={(e) => setText(e.target.value)} />
                    <button type="button" className="nx-btn nx-btn-primary nx-btn-sm" disabled={saving || !text.trim()} onClick={add}>{saving ? 'Adding…' : 'Add note'}</button>
                </div>
                {(notes || []).length === 0 ? <p className="nx-a3-note">No notes yet</p> : (
                    <ul className="nx-a3-notes">
                        {notes.map((note) => (
                            <li key={note.id}>
                                <p>{note.body}</p>
                                <small>{note.admin_username} · {formatDate(note.created_at) || '—'}</small>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </Card>
    );
}

// ─── Settings: profile + support access ───────────────────────────────────

export function ProfileSettingsPanel({ tenantId, identity, detail }) {
    const registry = `/dashboard/accounts/registry?tenant_id=${tenantId}`;
    return (
        <Card
            id="profile"
            title="Profile & credentials"
            description="Identity, constituency, key facts and the primary login"
            actions={<Link className="nx-btn nx-btn-sm" href={registry}>Edit profile, constituency &amp; password</Link>}
        >
            <KeyValueList items={[
                { label: 'Name', value: identity.name || '—' },
                { label: 'Role', value: identity.roleLabel || '—' },
                { label: 'Stage', value: identity.stageLabel || '—' },
                { label: 'Constituency', value: identity.constituency || 'Not assigned' },
                { label: 'State', value: identity.state || '—' },
                { label: 'Party', value: identity.party || '—' },
                { label: 'Languages', value: identity.languages.length ? identity.languages.join(', ') : '—' },
                { label: 'Tenant', value: `#${identity.tenantId}` },
                { label: 'Created', value: formatDate(identity.createdAt) || '—' },
                { label: 'Last login', value: identity.lastLogin ? formatRelative(identity.lastLogin) : 'Never' },
            ]} />
            <div className="nx-a3-pad nx-a3-form-actions">
                <Link className="nx-btn nx-btn-sm" href={`/dashboard/mps/${tenantId}/setup`}>Launch setup checklist</Link>
                <span className="nx-muted nx-a3-inline-note">{detail?.onboarding_state?.live ? 'Production traffic is enabled.' : 'Production traffic is not enabled yet.'}</span>
            </div>
        </Card>
    );
}

const SUPPORT_TONE = { approved: 'ok', active: 'review', pending: 'warning', rejected: 'critical', revoked: 'critical', cancelled: 'critical', expired: 'critical' };

export function SupportAccessPanel({ tenantId, requests, reload, notify }) {
    const [reason, setReason] = useState('Investigating an operator issue in the tenant workspace.');
    const [duration, setDuration] = useState(30);
    const [loading, setLoading] = useState(false);
    const [busyKey, setBusyKey] = useState('');

    const request = async () => {
        const text = reason.trim();
        if (!text) { notify('Support reason is required', 'error'); return; }
        setLoading(true);
        try {
            await apiPost(`/api/admin/mps/${tenantId}/support-access/request`, { reason: text, duration_minutes: duration });
            await reload();
            notify('Support request sent to tenant for approval');
        } catch (error) {
            notify(error.message || 'Failed to send support request', 'error');
        }
        setLoading(false);
    };

    const launch = async (key) => {
        setBusyKey(key);
        try {
            const result = await apiPost(`/api/admin/support-access/${key}/launch`, {});
            const mpBase = process.env.NEXT_PUBLIC_MP_DASHBOARD_URL || 'https://dashboard.theneedle.in';
            const url = `${mpBase}/support-access?request=${encodeURIComponent(result.request_key)}&launch_token=${encodeURIComponent(result.launch_token)}`;
            window.open(url, '_blank', 'noopener,noreferrer');
            notify('Support session opened in a new tab');
            await reload();
        } catch (error) {
            notify(error.message || 'Failed to open support session', 'error');
        }
        setBusyKey('');
    };

    const cancel = async (key) => {
        setBusyKey(key);
        try {
            await apiPost(`/api/admin/support-access/${key}/cancel`, {});
            notify('Support request cancelled');
            await reload();
        } catch (error) {
            notify(error.message || 'Failed to cancel support request', 'error');
        }
        setBusyKey('');
    };

    return (
        <Card id="support-access" title="Support access" description="Request tenant-approved admin viewing access instead of opening the MP dashboard directly." actions={<Badge tone="neutral" dot={false}>Tenant-approved</Badge>}>
            <div className="nx-a3-pad">
                <div className="nx-a3-support-form">
                    <Field label="Reason shown to tenant" required>
                        {(props) => <textarea {...props} className="nx-input nx-textarea" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Explain why admin needs temporary workspace access" />}
                    </Field>
                    <Field label="Duration">
                        {(props) => (
                            <span className="nx-select">
                                <select {...props} className="nx-input" value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
                                    <option value={15}>15 min</option><option value={30}>30 min</option><option value={60}>60 min</option>
                                </select>
                            </span>
                        )}
                    </Field>
                    <button type="button" className="nx-btn nx-btn-primary" disabled={loading} onClick={request}>{loading ? 'Sending…' : 'Request access'}</button>
                </div>
                {(requests || []).length === 0 ? (
                    <p className="nx-a3-note">No recent support-access requests for this tenant.</p>
                ) : (
                    <ul className="nx-a3-support-list">
                        {requests.map((item) => {
                            const canLaunch = item.status === 'approved';
                            const canCancel = item.status === 'pending' || item.status === 'approved';
                            return (
                                <li key={item.request_key} data-tone={canLaunch ? 'ok' : undefined}>
                                    <div className="nx-a3-support-copy">
                                        <div className="nx-a3-support-meta">
                                            <Badge tone={SUPPORT_TONE[item.status] || 'neutral'}>{item.status}</Badge>
                                            <span className="nx-muted">{item.duration_minutes || 30} min · requested {formatDate(item.requested_at) || '—'}</span>
                                        </div>
                                        <p>{item.reason || 'No reason provided.'}</p>
                                        <small>Target account: @{item.target_username}{item.approved_by_username ? ` · Tenant response by ${item.approved_by_username}` : ''}</small>
                                    </div>
                                    <div className="nx-a3-support-actions">
                                        {canCancel && <button type="button" className="nx-btn nx-btn-sm" disabled={busyKey === item.request_key} onClick={() => cancel(item.request_key)}>Cancel</button>}
                                        {canLaunch && <button type="button" className="nx-btn nx-btn-primary nx-btn-sm" disabled={busyKey === item.request_key} onClick={() => launch(item.request_key)}>{busyKey === item.request_key ? 'Opening…' : 'Open tenant view'}</button>}
                                    </div>
                                </li>
                            );
                        })}
                    </ul>
                )}
            </div>
        </Card>
    );
}
