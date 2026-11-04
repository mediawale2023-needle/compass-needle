'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, ChevronDown, ChevronUp, Sparkles, X } from 'lucide-react';
import { apiGet } from '@/lib/api';
import {
    analysisFacts,
    analysisFlags,
    caseAge,
    caseMessages,
    caseNotes,
    casePriorityMeta,
    caseStatusMeta,
    caseTabs,
    formatCaseTime,
    governmentStatusMeta,
    hasAnalysis,
    hasGovernmentRecord,
    humanize,
    recordedCategory,
    timelineItems,
} from '@/lib/admin-data';
import { Badge, ErrorState, KeyValueList, LoadingSkeleton, StatusText, Unavailable } from '@/components/admin-ui';

function placeValue(value) {
    const text = String(value ?? '').trim();
    return text && text !== '-' ? text : null;
}

function Fact({ label, value, detail }) {
    return (
        <div className="nx-cx-fact">
            <div className="nx-cx-fact-k">{label}</div>
            <div className="nx-cx-fact-v">{value ?? '—'}</div>
            {detail && <div className="nx-cx-fact-s">{detail}</div>}
        </div>
    );
}

function Section({ title, aside, children }) {
    return (
        <section className="nx-cx-section">
            <div className="nx-cx-section-head"><h3>{title}</h3>{aside}</div>
            {children}
        </section>
    );
}

function CaseTimeline({ items }) {
    return (
        <ol className="nx-timeline nx-cx-timeline">
            {items.map((item, index) => (
                <li key={`${item.meta}-${index}`}>
                    <span className="nx-timeline-dot" data-tone={item.tone} aria-hidden="true" />
                    <div className="nx-timeline-title">{item.actor && <strong>{item.actor} </strong>}{item.actor ? item.title.charAt(0).toLowerCase() + item.title.slice(1) : item.title}</div>
                    {item.meta && <div className="nx-timeline-meta">{item.meta}</div>}
                </li>
            ))}
        </ol>
    );
}

function NeedleAnalysis({ analysis, recorded }) {
    const facts = analysisFacts(analysis);
    const flags = analysisFlags(analysis);
    return (
        <section className="nx-cx-ai" aria-label="Needle analysis">
            <div className="nx-cx-ai-head">
                <span className="nx-tile" data-tone="ok" data-size="sm" aria-hidden="true"><Sparkles size={14} strokeWidth={1.9} /></span>
                <h3>Needle analysis</h3>
                <span className="nx-cx-ai-label">AI-derived · not a staff decision</span>
            </div>
            {analysis.summary && <p className="nx-cx-ai-summary">{analysis.summary}</p>}
            {flags.length > 0 && (
                <ul className="nx-cx-ai-flags">
                    {flags.map((flag) => <li key={flag}><StatusText tone="review">{flag}</StatusText></li>)}
                </ul>
            )}
            {facts.length > 0 && <KeyValueList items={facts} />}
            <p className="nx-cx-ai-note">
                Recorded category: <strong>{recorded || 'not set by staff'}</strong>. Suggestions are accepted or changed by MP staff in their workspace.
            </p>
        </section>
    );
}

function GovernmentPanel({ government, compact = false }) {
    const status = governmentStatusMeta(government.status);
    const items = [
        { label: 'Portal status', value: <StatusText tone={status.tone}>{status.label}</StatusText> },
        government.portal && { label: 'Portal', value: [government.portal.name, government.portal.state].filter(Boolean).join(' · ') },
        government.department && { label: 'Department', value: government.department },
        government.reference_number && { label: 'Reference', value: <span className="nx-mono">{government.reference_number}</span> },
        !compact && government.status_updated_at && { label: 'Status updated', value: formatCaseTime(government.status_updated_at) },
        !compact && government.last_forwarded_to_citizen_at && { label: 'Last update sent to citizen', value: formatCaseTime(government.last_forwarded_to_citizen_at) },
    ].filter(Boolean);
    return <KeyValueList items={items} />;
}

function MessagesPanel({ detail }) {
    const messages = caseMessages(detail);
    const inboundUnavailable = detail.messages?.inbound === null;
    const outboundUnavailable = detail.messages?.outbound === null;
    return (
        <>
            {(inboundUnavailable || outboundUnavailable) && (
                <p className="nx-cx-muted"><Unavailable>{inboundUnavailable ? 'Inbound ledger unavailable' : 'Outbound ledger unavailable'}</Unavailable></p>
            )}
            <ol className="nx-cx-messages">
                {messages.map((message) => (
                    <li key={`${message.direction}-${message.id}`} data-direction={message.direction}>
                        <div className="nx-cx-message-head">
                            <strong>{message.direction === 'inbound' ? 'Citizen → Needle' : 'Needle → citizen'}</strong>
                            <span>{formatCaseTime(message.created_at)}</span>
                        </div>
                        {message.direction === 'outbound' ? (
                            <p className="nx-cx-message-body">{message.body || 'No message body recorded'}</p>
                        ) : (
                            <p className="nx-cx-muted">{humanize(message.message_type) || 'Message'} message received from the citizen</p>
                        )}
                        <div className="nx-cx-message-meta">
                            <StatusText tone={['sent', 'processed', 'delivered', 'read'].includes(String(message.status).toLowerCase()) ? 'ok' : String(message.status).toLowerCase() === 'failed' ? 'critical' : 'neutral'}>{humanize(message.status) || 'Unknown'}</StatusText>
                            {message.template_key && <span>Template · {message.template_key}</span>}
                        </div>
                        {message.last_error && <p className="nx-cx-message-error">{message.last_error}</p>}
                    </li>
                ))}
            </ol>
        </>
    );
}

export default function CaseInvestigation({ caseId, row, now, onClose, onPrevious, onNext }) {
    const [detail, setDetail] = useState(null);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(true);
    const [tab, setTab] = useState('overview');

    const load = useCallback(() => {
        let cancelled = false;
        setLoading(true);
        setError('');
        apiGet(`/api/admin/cases/${caseId}`)
            .then((result) => { if (!cancelled) setDetail(result); })
            .catch((e) => { if (!cancelled) setError(e.message || 'Failed to load this case'); })
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, [caseId]);

    useEffect(() => load(), [load]);

    const tabs = caseTabs(detail);
    const activeTab = tabs.some((item) => item.value === tab) ? tab : 'overview';

    const header = (
        <div className="nx-cx-detail-bar">
            <button type="button" className="nx-btn nx-btn-sm nx-cx-back" onClick={onClose}><ArrowLeft size={15} aria-hidden="true" />Back to cases</button>
            <span className="nx-cx-detail-eyebrow">Case #{caseId}{detail?.case_ref ? ` · ${detail.case_ref}` : ''}</span>
            <div className="nx-cx-detail-nav">
                <button type="button" className="nx-icon-button" aria-label="Previous case" disabled={!onPrevious} onClick={onPrevious || undefined}><ChevronUp size={16} /></button>
                <button type="button" className="nx-icon-button" aria-label="Next case" disabled={!onNext} onClick={onNext || undefined}><ChevronDown size={16} /></button>
                <button type="button" className="nx-icon-button nx-cx-close" aria-label="Close investigation" onClick={onClose}><X size={16} /></button>
            </div>
        </div>
    );

    if (loading && !detail) {
        return <div className="nx-card nx-cx-detail">{header}<div className="nx-cx-pad"><LoadingSkeleton rows={7} label="Loading case" /></div></div>;
    }
    if (error && !detail) {
        return <div className="nx-card nx-cx-detail">{header}<div className="nx-cx-pad"><ErrorState title="Case unavailable" message={error} onRetry={load} /></div></div>;
    }
    if (!detail) return null;

    const status = caseStatusMeta(detail.status);
    const priority = casePriorityMeta(detail.priority, detail.critical);
    const created = detail.timestamps?.created_at || row?.created_at;
    const age = caseAge(created, detail.status, now);
    const recorded = recordedCategory(detail);
    const location = placeValue(detail.location);
    const assembly = placeValue(detail.assembly);
    const analysis = detail.analysis;
    const government = detail.government;
    const notes = caseNotes(detail);
    const activity = Array.isArray(detail.activity) ? detail.activity : null;
    const recent = activity ? timelineItems(activity, { limit: 4 }) : [];
    const workspaceHref = `/dashboard/mps/${detail.tenant_id}#support`;

    return (
        <article className="nx-card nx-cx-detail" aria-labelledby="nx-cx-title">
            <div className="nx-cx-detail-head">
                {header}
                <h2 id="nx-cx-title">{recorded || 'Uncategorised grievance'}</h2>
                <div className="nx-cx-badges">
                    {priority.key !== 'standard' && <Badge tone={priority.tone}>{priority.label} priority</Badge>}
                    <Badge tone={status.tone}>{status.label}</Badge>
                    {detail.is_deleted && <Badge tone="neutral" dot={false}>Deleted</Badge>}
                    <span className="nx-cx-muted">{age.days === null ? 'Age unknown' : `${age.label} old`}</span>
                </div>
                <div className="nx-cx-actions">
                    {detail.tenant_id && <Link className="nx-btn nx-btn-sm" href={workspaceHref}>Open in MP workspace →</Link>}
                    {detail.tenant_id && <Link className="nx-link" href={`/dashboard/mps/${detail.tenant_id}`}>Account 360</Link>}
                    <span className="nx-cx-readonly">Read-only in Admin · changes are made by MP staff</span>
                </div>
                <div className="nx-cx-tabs" role="tablist" aria-label="Case sections">
                    {tabs.map((item) => (
                        <button
                            key={item.value}
                            type="button"
                            role="tab"
                            id={`nx-cx-tab-${item.value}`}
                            aria-selected={activeTab === item.value}
                            aria-controls="nx-cx-tabpanel"
                            className="nx-tab"
                            onClick={() => setTab(item.value)}
                        >
                            {item.label}
                            {item.count ? <span className="nx-count">{item.count}</span> : null}
                        </button>
                    ))}
                </div>
            </div>

            <div id="nx-cx-tabpanel" role="tabpanel" aria-labelledby={`nx-cx-tab-${activeTab}`}>
                {activeTab === 'overview' && (
                    <>
                        <div className="nx-cx-facts">
                            <Fact label="Account" value={detail.mp_name} detail={placeValue(detail.mp_constituency)} />
                            <Fact label="Location" value={location || assembly || <Unavailable>Not resolved</Unavailable>} detail={location && assembly && location !== assembly ? assembly : null} />
                            <Fact label="Assigned to" value={detail.assigned_to || 'Unassigned'} detail={detail.assigned_to ? 'Recorded by staff' : null} />
                            <Fact label="Created" value={formatCaseTime(created) || '—'} detail={detail.timestamps?.status_changed_at ? `Status changed ${formatCaseTime(detail.timestamps.status_changed_at)}` : null} />
                        </div>
                        <div className="nx-cx-body">
                            <Section title="Citizen & issue">
                                <div className="nx-cx-citizen">
                                    <span className="nx-cx-muted">Citizen</span>
                                    <strong>{placeValue(detail.phone) || '—'}</strong>
                                </div>
                                <blockquote className="nx-cx-quote">
                                    <p lang={analysis?.language && /hindi/i.test(analysis.language) ? 'hi' : undefined}>{placeValue(detail.raw_message) || 'No message text recorded'}</p>
                                    {analysis?.english_translation && (
                                        <footer><span className="nx-cx-ai-tag">Machine translation</span> {analysis.english_translation}</footer>
                                    )}
                                </blockquote>
                            </Section>

                            {hasAnalysis(analysis) && <NeedleAnalysis analysis={analysis} recorded={recorded} />}

                            {hasGovernmentRecord(government) && (
                                <Section title="Government interaction" aside={tabs.some((t) => t.value === 'government') && <button type="button" className="nx-link-button" onClick={() => setTab('government')}>Details →</button>}>
                                    <GovernmentPanel government={government} compact />
                                </Section>
                            )}

                            <Section
                                title="Recent activity"
                                aside={activity && activity.length > recent.length && <button type="button" className="nx-link-button" onClick={() => setTab('timeline')}>All {activity.length} events →</button>}
                            >
                                {activity === null && <p className="nx-cx-muted"><Unavailable>Activity log unavailable</Unavailable></p>}
                                {activity && activity.length === 0 && <p className="nx-cx-muted">No staff or system activity has been logged for this case.</p>}
                                {recent.length > 0 && <CaseTimeline items={recent} />}
                            </Section>
                        </div>
                    </>
                )}

                {activeTab === 'timeline' && (
                    <div className="nx-cx-body">
                        <Section title="Activity log" aside={<span className="nx-cx-muted">Recorded activity · newest first</span>}>
                            <CaseTimeline items={timelineItems(activity || [])} />
                        </Section>
                    </div>
                )}

                {activeTab === 'government' && (
                    <div className="nx-cx-body">
                        <Section title="Government interaction">
                            <GovernmentPanel government={government} />
                        </Section>
                    </div>
                )}

                {activeTab === 'notes' && (
                    <div className="nx-cx-body">
                        {notes.map((note) => (
                            <Section key={note.key} title={note.label}>
                                <p className="nx-cx-note">{note.body}</p>
                            </Section>
                        ))}
                        <p className="nx-cx-muted">Notes are read-only here. MP staff edit them in their workspace.</p>
                    </div>
                )}

                {activeTab === 'messages' && (
                    <div className="nx-cx-body">
                        <Section title="WhatsApp messages" aside={<span className="nx-cx-muted">Linked to this case</span>}>
                            <MessagesPanel detail={detail} />
                        </Section>
                    </div>
                )}
            </div>
        </article>
    );
}
