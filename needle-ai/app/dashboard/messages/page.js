'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { apiGet, apiPost, apiPatch, apiDelete } from '@/lib/api';
import { useToast } from '@/components/ui/toast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import {
    Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { cn } from '@/lib/utils';
import {
    Search, CheckCircle2, Loader2, Send, Mail, Shield, Trash2,
    Clock, X, ChevronDown, ChevronRight, AlertTriangle,
} from 'lucide-react';

// ── Constants ──────────────────────────────────────────────────────────────

const STATUS_CFG = {
    new:         { label: 'New',         dot: 'bg-blue-500',   border: 'border-l-blue-500',   badge: 'bg-blue-100 text-blue-700',    row: 'bg-blue-50/30' },
    in_progress: { label: 'In Progress', dot: 'bg-amber-500',  border: 'border-l-amber-500',  badge: 'bg-amber-100 text-amber-700',  row: '' },
    escalated:   { label: 'Escalated',   dot: 'bg-red-500',    border: 'border-l-red-500',    badge: 'bg-red-100 text-red-700',      row: 'bg-red-50/30' },
    resolved:    { label: 'Resolved',    dot: 'bg-green-500',  border: 'border-l-green-500',  badge: 'bg-green-100 text-green-700',  row: '' },
    closed:      { label: 'Closed',      dot: 'bg-slate-400',  border: 'border-l-slate-200',  badge: 'bg-slate-100 text-slate-500',  row: 'opacity-60' },
    spam:        { label: 'Spam',        dot: 'bg-orange-400', border: 'border-l-orange-400', badge: 'bg-orange-100 text-orange-700', row: 'opacity-50' },
};

const SIDEBAR_STATUSES = ['new', 'in_progress', 'escalated', 'resolved', 'closed', 'spam'];

const QUICK_STATUS_ACTIONS = ['new', 'in_progress', 'resolved', 'escalated', 'closed', 'spam'];

const CATEGORY_OPTIONS = [
    'External Affairs', 'Railways', 'Infrastructure', 'Telecom',
    'Postal Services', 'Education (Central)', 'Banking & Finance',
    'Labor & Employment', 'Law & Order', 'Energy',
    'Infrastructure (State)', 'Food Supply', 'Transport',
    'Revenue & Land', 'Sanitation', 'Water', 'Civic Amenities',
    'Public Health', 'Civic Admin', 'Private/Legal',
];

function timeAgo(dateStr) {
    if (!dateStr) return '';
    const diff = Date.now() - new Date(dateStr).getTime();
    const m = Math.floor(diff / 60000);
    if (m < 1) return 'just now';
    if (m < 60) return `${m}m`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h`;
    return `${Math.floor(h / 24)}d`;
}

// ── Detail Panel ───────────────────────────────────────────────────────────

function DetailPanel({ caseItem, onClose, onStatusChange, onDeleted, toast }) {
    const [notes, setNotes] = useState('');
    const [response, setResponse] = useState('');
    const [savingNotes, setSavingNotes] = useState(false);
    const [notifying, setNotifying] = useState(false);
    const [updating, setUpdating] = useState(null);
    const [activities, setActivities] = useState([]);
    const [loadingActivity, setLoadingActivity] = useState(false);
    const [showActivity, setShowActivity] = useState(false);

    const [showEscalation, setShowEscalation] = useState(false);
    const [officers, setOfficers] = useState([]);
    const [selectedOfficer, setSelectedOfficer] = useState('');
    const [letterContent, setLetterContent] = useState('');
    const [escalations, setEscalations] = useState([]);
    const [submitting, setSubmitting] = useState(false);
    const [sendingEmail, setSendingEmail] = useState(null);
    const [expandedLetter, setExpandedLetter] = useState(null);

    useEffect(() => {
        if (!caseItem) return;
        setNotes(caseItem.notes_for_staff || '');
        setResponse(caseItem.response_to_citizen || '');
        setShowEscalation(false);
        setShowActivity(false);
        setActivities([]);
        setExpandedLetter(null);
    }, [caseItem?.id]);

    const loadEscalationData = useCallback(async () => {
        if (!caseItem) return;
        const [oData, eData] = await Promise.all([
            apiGet('/api/officers').catch(() => ({ officers: [] })),
            apiGet(`/api/escalations?case_id=${caseItem.id}`).catch(() => ({ escalations: [] })),
        ]);
        setOfficers(oData.officers || []);
        setEscalations(eData.escalations || []);
    }, [caseItem?.id]);

    useEffect(() => {
        if (showEscalation) loadEscalationData();
    }, [showEscalation, loadEscalationData]);

    useEffect(() => {
        if (!showActivity || !caseItem) return;
        setLoadingActivity(true);
        apiGet(`/api/cases/${caseItem.id}/activity`)
            .then(d => setActivities(d.activities || []))
            .catch(() => setActivities([]))
            .finally(() => setLoadingActivity(false));
    }, [showActivity, caseItem?.id]);

    if (!caseItem) return null;

    const c = caseItem;
    const meta = c.case_metadata || {};
    const currentStatus = (c.status || 'new').toLowerCase();
    const cfg = STATUS_CFG[currentStatus] || {};
    const createdAt = c.created_at ? new Date(c.created_at) : null;

    const handleStatusChange = async (newStatus) => {
        setUpdating(newStatus);
        try {
            await apiPatch(`/api/cases/${c.id}/status`, { status: newStatus });
            onStatusChange(c.id, newStatus);
            toast.success(`Marked ${newStatus}`);
        } catch {
            toast.error('Failed to update status');
        } finally {
            setUpdating(null);
        }
    };

    const saveNotes = async () => {
        setSavingNotes(true);
        try {
            await apiPatch(`/api/cases/${c.id}`, {
                notes_for_staff: notes || null,
                response_to_citizen: response || null,
            });
            toast.success('Saved');
        } catch {
            toast.error('Failed to save');
        } finally {
            setSavingNotes(false);
        }
    };

    const handleNotify = async () => {
        setNotifying(true);
        try {
            await apiPost(`/api/cases/${c.id}/notify`);
            toast.success('WhatsApp update sent');
        } catch {
            toast.error('Failed to send');
        } finally {
            setNotifying(false);
        }
    };

    const handleDelete = async () => {
        if (!window.confirm('Delete this case?')) return;
        try {
            await apiDelete(`/api/cases/${c.id}`);
            toast.success('Case deleted');
            onDeleted(c.id);
        } catch {
            toast.error('Failed to delete');
        }
    };

    const handleEscalate = async () => {
        if (!selectedOfficer) { toast.error('Select an officer'); return; }
        setSubmitting(true);
        try {
            const cat = c.category || 'this matter';
            const ref = c.case_ref || `#${c.id}`;
            const loc = c.location || '';
            const msg = c.raw_message || '';
            const letter = letterContent ||
                `Subject: Escalation of Citizen Grievance ${ref}\n\nRespected Sir/Madam,\n\nCitizen grievance (Ref: ${ref}) related to ${cat}${loc ? ` in ${loc}` : ''}.\n\nComplaint: "${msg.slice(0, 300)}"\n\nKindly take necessary action.\n\nRegards,\nOffice of the Representative`;
            await apiPost('/api/escalations', {
                case_id: c.id,
                officer_id: parseInt(selectedOfficer),
                letter_content: letter,
                deadline: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0],
            });
            toast.success('Case escalated');
            await loadEscalationData();
            setSelectedOfficer('');
            setLetterContent('');
        } catch (err) {
            toast.error('Failed: ' + (err.message || 'Unknown'));
        } finally {
            setSubmitting(false);
        }
    };

    const handleSendEmail = async (escalationId) => {
        setSendingEmail(escalationId);
        try {
            await apiPost(`/api/escalations/${escalationId}/send`);
            toast.success('Email sent');
            await loadEscalationData();
        } catch {
            toast.error('Failed to send email');
        } finally {
            setSendingEmail(null);
        }
    };

    return (
        <div className="h-full flex flex-col">
            {/* Header */}
            <div className={cn('px-5 py-4 border-b shrink-0', cfg.row)}>
                <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                            <span className="text-[11px] font-mono text-muted-foreground">#{c.id}</span>
                            <span className={cn('text-[11px] font-semibold px-2 py-0.5 rounded-full', cfg.badge || 'bg-slate-100 text-slate-600')}>
                                {cfg.label || currentStatus}
                            </span>
                            {c.is_critical && (
                                <span className="text-[10px] bg-red-600 text-white px-1.5 py-0.5 rounded font-bold tracking-wide">CRITICAL</span>
                            )}
                        </div>
                        <h2 className="font-bold text-foreground text-base leading-tight truncate">{c.category || 'General'}</h2>
                        <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1.5 text-xs text-muted-foreground">
                            {c.user_phone && <span>{c.user_phone}</span>}
                            {(c.location || meta.matched_value) && <span>{c.location || meta.matched_value}</span>}
                            {createdAt && <span>{createdAt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</span>}
                        </div>
                    </div>
                    <button onClick={onClose} className="text-muted-foreground hover:text-foreground shrink-0 mt-0.5">
                        <X className="h-4 w-4" />
                    </button>
                </div>
            </div>

            {/* Scrollable body */}
            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5 min-h-0">

                {/* Message */}
                <div>
                    <p className="text-[10px] uppercase font-semibold text-muted-foreground tracking-widest mb-2">Message</p>
                    <div className="bg-muted/40 border rounded-lg p-3 text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                        {c.raw_message || 'No content.'}
                    </div>
                </div>

                <Separator />

                {/* Status actions */}
                <div>
                    <p className="text-[10px] uppercase font-semibold text-muted-foreground tracking-widest mb-2">Change Status</p>
                    <div className="flex flex-wrap gap-1.5">
                        {QUICK_STATUS_ACTIONS.filter(s => s !== currentStatus).map(s => {
                            const sc = STATUS_CFG[s];
                            return (
                                <button
                                    key={s}
                                    onClick={() => handleStatusChange(s)}
                                    disabled={!!updating}
                                    className={cn(
                                        'text-xs px-3 py-1.5 rounded-full font-medium transition-opacity border-0 outline-none',
                                        sc?.badge || 'bg-slate-100 text-slate-600',
                                        updating === s ? 'opacity-50 cursor-not-allowed' : 'hover:opacity-75 cursor-pointer'
                                    )}
                                >
                                    {updating === s && <Loader2 className="h-3 w-3 animate-spin inline mr-1" />}
                                    {sc?.label || s}
                                </button>
                            );
                        })}
                    </div>
                </div>

                <Separator />

                {/* Notes + Response */}
                <div className="space-y-3">
                    <div>
                        <p className="text-[10px] uppercase font-semibold text-muted-foreground tracking-widest mb-1.5">Staff Notes</p>
                        <Textarea
                            value={notes}
                            onChange={e => setNotes(e.target.value)}
                            placeholder="Internal notes..."
                            className="min-h-[56px] text-sm"
                        />
                    </div>
                    <div>
                        <p className="text-[10px] uppercase font-semibold text-muted-foreground tracking-widest mb-1.5">Response to Citizen</p>
                        <Textarea
                            value={response}
                            onChange={e => setResponse(e.target.value)}
                            placeholder="What to tell the citizen..."
                            className="min-h-[56px] text-sm"
                        />
                    </div>
                    <div className="flex gap-2 flex-wrap">
                        <Button size="sm" onClick={saveNotes} disabled={savingNotes} className="text-xs h-8">
                            {savingNotes && <Loader2 className="h-3 w-3 animate-spin mr-1" />}
                            Save Notes
                        </Button>
                        <Button
                            size="sm" variant="outline"
                            className="text-xs h-8 border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                            disabled={notifying || !c.user_phone}
                            onClick={handleNotify}
                        >
                            {notifying ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Send className="h-3 w-3 mr-1" />}
                            Send via WhatsApp
                        </Button>
                    </div>
                </div>

                <Separator />

                {/* Escalation */}
                <div>
                    <button
                        onClick={() => setShowEscalation(v => !v)}
                        className="flex items-center gap-1.5 text-[10px] uppercase font-semibold text-amber-700 tracking-widest mb-2 hover:opacity-80 w-full"
                    >
                        <Shield className="h-3 w-3" />
                        Escalate to Officer
                        {showEscalation ? <ChevronDown className="h-3 w-3 ml-auto" /> : <ChevronRight className="h-3 w-3 ml-auto" />}
                    </button>

                    {showEscalation && (
                        <div className="border border-amber-200 rounded-lg p-3 bg-amber-50/40 space-y-3">
                            {officers.length === 0 ? (
                                <p className="text-xs text-muted-foreground">
                                    No officers configured.{' '}
                                    <a href="/dashboard/officers" className="text-primary underline">Add officers</a> first.
                                </p>
                            ) : (
                                <>
                                    <select
                                        value={selectedOfficer}
                                        onChange={e => setSelectedOfficer(e.target.value)}
                                        className="w-full border rounded-md p-2 text-xs bg-white"
                                    >
                                        <option value="">— Select Officer —</option>
                                        {officers.map(o => (
                                            <option key={o.id} value={o.id}>
                                                {o.name} · {o.designation}{o.department ? `, ${o.department}` : ''}
                                            </option>
                                        ))}
                                    </select>
                                    <Textarea
                                        value={letterContent}
                                        onChange={e => setLetterContent(e.target.value)}
                                        placeholder="Escalation letter (auto-generated if empty)..."
                                        className="min-h-[70px] text-xs bg-white"
                                    />
                                    <Button
                                        size="sm"
                                        onClick={handleEscalate}
                                        disabled={submitting || !selectedOfficer}
                                        className="text-xs bg-amber-600 hover:bg-amber-700 text-white h-8"
                                    >
                                        {submitting ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Shield className="h-3 w-3 mr-1" />}
                                        Escalate
                                    </Button>
                                </>
                            )}

                            {escalations.length > 0 && (
                                <div className="space-y-2 pt-2 border-t border-amber-200">
                                    <p className="text-[10px] uppercase font-semibold text-amber-800 tracking-widest">History</p>
                                    {escalations.map(esc => (
                                        <React.Fragment key={esc.id}>
                                            <div className="bg-white border rounded-md p-2.5 space-y-2">
                                                <div className="flex items-center justify-between gap-2">
                                                    <span className="text-xs font-medium truncate">{esc.officer_name || 'Officer'}</span>
                                                    <span className={cn(
                                                        'text-[10px] font-semibold px-1.5 py-0.5 rounded-full shrink-0',
                                                        esc.email_sent ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'
                                                    )}>
                                                        {esc.email_sent ? '✓ Sent' : 'Not Sent'}
                                                    </span>
                                                </div>
                                                <div className="flex gap-2">
                                                    {!esc.email_sent && (
                                                        <Button
                                                            size="sm" variant="outline"
                                                            className="text-[11px] h-6 border-blue-200 text-blue-700"
                                                            disabled={sendingEmail === esc.id}
                                                            onClick={() => handleSendEmail(esc.id)}
                                                        >
                                                            {sendingEmail === esc.id ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Mail className="h-3 w-3 mr-1" />}
                                                            Send Email
                                                        </Button>
                                                    )}
                                                    {esc.letter_content && (
                                                        <Button
                                                            size="sm" variant="ghost"
                                                            className="text-[11px] h-6 text-muted-foreground"
                                                            onClick={() => setExpandedLetter(expandedLetter === esc.id ? null : esc.id)}
                                                        >
                                                            {expandedLetter === esc.id ? 'Hide Letter' : 'View Letter'}
                                                        </Button>
                                                    )}
                                                </div>
                                                {expandedLetter === esc.id && (
                                                    <pre className="text-[11px] whitespace-pre-wrap font-mono bg-slate-50 border rounded p-2 max-h-48 overflow-y-auto leading-relaxed">
                                                        {esc.letter_content}
                                                    </pre>
                                                )}
                                            </div>
                                        </React.Fragment>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>

                <Separator />

                {/* Activity Log (collapsed) */}
                <div>
                    <button
                        onClick={() => setShowActivity(v => !v)}
                        className="flex items-center gap-1.5 w-full text-[10px] uppercase font-semibold text-muted-foreground tracking-widest hover:text-foreground"
                    >
                        Activity Log
                        {showActivity ? <ChevronDown className="h-3 w-3 ml-auto" /> : <ChevronRight className="h-3 w-3 ml-auto" />}
                    </button>
                    {showActivity && (
                        <div className="mt-2">
                            {loadingActivity ? (
                                <div className="flex justify-center py-3">
                                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                                </div>
                            ) : activities.length === 0 ? (
                                <p className="text-xs text-muted-foreground">No activity yet</p>
                            ) : (
                                <div className="space-y-2 max-h-40 overflow-y-auto">
                                    {activities.map(a => (
                                        <div key={a.id} className="flex items-start gap-2 text-xs">
                                            <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                                            <div>
                                                <span className="font-medium">{a.username}</span>{' '}
                                                {a.action.replace(/_/g, ' ')}
                                                {a.new_value && <span className="text-muted-foreground"> → {a.new_value}</span>}
                                                <div className="text-muted-foreground">
                                                    {a.created_at ? new Date(a.created_at).toLocaleString('en-IN') : ''}
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* Delete */}
                <div className="pt-1 pb-2">
                    <button
                        onClick={handleDelete}
                        className="text-xs text-red-400 hover:text-red-600 flex items-center gap-1.5 transition-colors"
                    >
                        <Trash2 className="h-3 w-3" /> Delete case
                    </button>
                </div>
            </div>
        </div>
    );
}

// ── Case Row ────────────────────────────────────────────────────────────────

function CaseRow({ c, isSelected, onClick, onQuickStatus }) {
    const [hovered, setHovered] = useState(false);
    const cfg = STATUS_CFG[(c.status || 'new').toLowerCase()] || {};

    return (
        <div
            className={cn(
                'relative flex items-center gap-3 px-4 py-2.5 border-b border-border/50 cursor-pointer border-l-[3px] select-none',
                cfg.border,
                isSelected
                    ? 'bg-primary/8 border-l-primary'
                    : cn(cfg.row, 'hover:bg-muted/50'),
            )}
            onClick={onClick}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
        >
            {/* Status dot */}
            <div className={cn('w-2 h-2 rounded-full shrink-0', cfg.dot || 'bg-slate-300')} />

            {/* ID */}
            <span className="text-[11px] font-mono text-muted-foreground w-10 shrink-0">#{c.id}</span>

            {/* Phone */}
            <span className="text-xs text-muted-foreground w-28 shrink-0 truncate font-mono">{c.user_phone || '—'}</span>

            {/* Category badge */}
            <span className={cn(
                'text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0 hidden sm:block',
                cfg.badge || 'bg-slate-100 text-slate-600'
            )} style={{ maxWidth: 130 }}>
                <span className="block truncate" style={{ maxWidth: 120 }}>{c.category || 'General'}</span>
            </span>

            {/* Location */}
            <span className="text-xs text-muted-foreground w-24 shrink-0 truncate hidden lg:block">{c.location || '—'}</span>

            {/* Message preview */}
            <span className="text-xs text-foreground/80 flex-1 truncate min-w-0">
                {c.raw_message || '—'}
            </span>

            {/* Time */}
            <span className="text-[11px] text-muted-foreground shrink-0 w-9 text-right tabular-nums">
                {timeAgo(c.created_at)}
            </span>

            {/* Hover inline actions */}
            {hovered && !isSelected && (
                <div className="flex items-center gap-1 shrink-0 ml-1" onClick={e => e.stopPropagation()}>
                    {c.status !== 'resolved' && (
                        <button
                            className="text-[11px] px-2 py-1 bg-green-100 text-green-700 rounded hover:bg-green-200 font-semibold transition-colors"
                            onClick={() => onQuickStatus(c.id, 'resolved')}
                        >
                            Resolve
                        </button>
                    )}
                    {c.status !== 'spam' && (
                        <button
                            className="text-[11px] px-2 py-1 bg-orange-100 text-orange-700 rounded hover:bg-orange-200 font-semibold transition-colors"
                            onClick={() => onQuickStatus(c.id, 'spam')}
                        >
                            Spam
                        </button>
                    )}
                </div>
            )}

            {/* Critical marker */}
            {c.is_critical && (
                <span className="absolute right-1.5 top-1 text-[9px] bg-red-600 text-white px-1 rounded font-bold leading-tight">!</span>
            )}
        </div>
    );
}

// ── Escalations View ────────────────────────────────────────────────────────

function EscalationsView({ toast }) {
    const [escalations, setEscalations] = useState([]);
    const [loading, setLoading] = useState(true);
    const [sendingEmail, setSendingEmail] = useState(null);
    const [expandedLetter, setExpandedLetter] = useState(null);

    const load = useCallback(() => {
        setLoading(true);
        apiGet('/api/escalations')
            .then(d => setEscalations(d.escalations || []))
            .catch(() => toast.error('Failed to load escalations'))
            .finally(() => setLoading(false));
    }, []);

    useEffect(() => { load(); }, [load]);

    const handleSendEmail = async (id) => {
        setSendingEmail(id);
        try {
            await apiPost(`/api/escalations/${id}/send`);
            toast.success('Email sent');
            load();
        } catch {
            toast.error('Failed to send email');
        } finally {
            setSendingEmail(null);
        }
    };

    if (loading) return (
        <div className="flex items-center justify-center py-20">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
    );

    if (escalations.length === 0) return (
        <div className="flex flex-col items-center justify-center py-20 text-center">
            <Mail className="h-10 w-10 text-muted-foreground/30 mb-3" />
            <p className="text-sm text-muted-foreground">No escalations yet</p>
            <p className="text-xs text-muted-foreground mt-1">Escalate cases to officers from any case detail</p>
        </div>
    );

    return (
        <div className="overflow-x-auto">
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead className="pl-5 w-16">Case</TableHead>
                        <TableHead>Officer</TableHead>
                        <TableHead>Designation</TableHead>
                        <TableHead>Email</TableHead>
                        <TableHead>Deadline</TableHead>
                        <TableHead>By</TableHead>
                        <TableHead>Date</TableHead>
                        <TableHead>Action</TableHead>
                        <TableHead>Letter</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {escalations.map(esc => (
                        <React.Fragment key={esc.id}>
                            <TableRow className={esc.email_sent ? '' : 'border-l-4 border-l-amber-400 bg-amber-50/30'}>
                                <TableCell className="pl-5 font-mono text-xs text-muted-foreground">#{esc.case_id}</TableCell>
                                <TableCell className="font-medium text-sm">{esc.officer_name || '-'}</TableCell>
                                <TableCell className="text-xs text-muted-foreground">{esc.designation || '-'}</TableCell>
                                <TableCell>
                                    {esc.email_sent ? (
                                        <span className="text-[11px] bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-semibold">✓ Sent</span>
                                    ) : (
                                        <span className="text-[11px] bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-semibold flex items-center gap-1 w-fit">
                                            <Clock className="h-2.5 w-2.5" /> Pending
                                        </span>
                                    )}
                                </TableCell>
                                <TableCell className="text-xs text-muted-foreground">
                                    {esc.deadline ? new Date(esc.deadline).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : '-'}
                                </TableCell>
                                <TableCell className="text-xs text-muted-foreground">{esc.created_by || '-'}</TableCell>
                                <TableCell className="text-xs text-muted-foreground">
                                    {esc.created_at ? new Date(esc.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : '-'}
                                </TableCell>
                                <TableCell>
                                    {!esc.email_sent && (
                                        <Button
                                            size="sm" variant="outline"
                                            className="h-7 text-xs border-blue-200 text-blue-700 hover:bg-blue-50"
                                            disabled={sendingEmail === esc.id}
                                            onClick={() => handleSendEmail(esc.id)}
                                        >
                                            {sendingEmail === esc.id
                                                ? <Loader2 className="h-3 w-3 animate-spin" />
                                                : <Mail className="h-3 w-3" />}
                                        </Button>
                                    )}
                                    {esc.email_sent && esc.email_sent_at && (
                                        <span className="text-[10px] text-green-600">
                                            {new Date(esc.email_sent_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}
                                        </span>
                                    )}
                                </TableCell>
                                <TableCell>
                                    {esc.letter_content && (
                                        <Button
                                            size="sm" variant="ghost"
                                            className="h-7 text-xs text-muted-foreground"
                                            onClick={() => setExpandedLetter(expandedLetter === esc.id ? null : esc.id)}
                                        >
                                            {expandedLetter === esc.id ? 'Hide' : 'View'}
                                        </Button>
                                    )}
                                </TableCell>
                            </TableRow>
                            {expandedLetter === esc.id && (
                                <TableRow>
                                    <TableCell colSpan={9} className="px-5 pb-4 pt-1 bg-slate-50">
                                        <p className="text-[10px] uppercase font-semibold text-muted-foreground mb-2 flex items-center gap-1.5">
                                            <Mail className="h-3 w-3" /> Email sent to officer
                                        </p>
                                        <pre className="text-xs whitespace-pre-wrap font-mono bg-white border rounded-lg p-3 max-h-64 overflow-y-auto leading-relaxed">
                                            {esc.letter_content}
                                        </pre>
                                    </TableCell>
                                </TableRow>
                            )}
                        </React.Fragment>
                    ))}
                </TableBody>
            </Table>
            <div className="px-5 py-3 border-t text-xs text-muted-foreground">
                {escalations.length} total · {escalations.filter(e => e.email_sent).length} sent · {escalations.filter(e => !e.email_sent).length} pending
            </div>
        </div>
    );
}

// ── Main Page ───────────────────────────────────────────────────────────────

export default function MessagesPage() {
    const toast = useToast();

    const [cases, setCases] = useState([]);
    const [loading, setLoading] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);
    const [page, setPage] = useState(1);
    const [hasMore, setHasMore] = useState(false);
    const [totalCases, setTotalCases] = useState(0);

    const [selectedStatuses, setSelectedStatuses] = useState(new Set());
    const [selectedCategories, setSelectedCategories] = useState(new Set());
    const [search, setSearch] = useState('');
    const [debouncedSearch, setDebouncedSearch] = useState('');

    const [selectedCase, setSelectedCase] = useState(null);
    const [activeView, setActiveView] = useState('cases');

    const [stats, setStats] = useState(null);

    // Debounce search
    const searchTimer = useRef(null);
    const handleSearchChange = (val) => {
        setSearch(val);
        if (searchTimer.current) clearTimeout(searchTimer.current);
        searchTimer.current = setTimeout(() => setDebouncedSearch(val), 350);
    };

    const fetchStats = useCallback(() => {
        apiGet('/api/dashboard/summary').then(d => setStats(d)).catch(() => {});
    }, []);

    const fetchCases = useCallback(async (reset = false) => {
        if (activeView !== 'cases') return;
        if (reset) setLoading(true);
        else setLoadingMore(true);
        const currentPage = reset ? 1 : page;
        try {
            const params = new URLSearchParams({ page: String(currentPage), limit: '80' });
            if (selectedStatuses.size === 1) params.set('status', [...selectedStatuses][0]);
            if (selectedCategories.size === 1) params.set('category', [...selectedCategories][0]);
            if (debouncedSearch) params.set('search', debouncedSearch);
            const data = await apiGet(`/api/cases?${params}`);
            let newCases = data.cases || [];
            // client-side filter when multiple statuses selected
            if (selectedStatuses.size > 1) {
                newCases = newCases.filter(c => selectedStatuses.has((c.status || '').toLowerCase()));
            }
            if (reset) { setCases(newCases); setPage(2); }
            else { setCases(prev => [...prev, ...newCases]); setPage(p => p + 1); }
            setTotalCases(data.total || 0);
            setHasMore(data.page < data.pages);
        } catch {
            toast.error('Failed to load cases');
        } finally {
            setLoading(false);
            setLoadingMore(false);
        }
    }, [activeView, page, selectedStatuses, selectedCategories, debouncedSearch]);

    useEffect(() => { fetchStats(); }, []);

    useEffect(() => {
        if (activeView === 'cases') fetchCases(true);
    }, [selectedStatuses, selectedCategories, debouncedSearch, activeView]);

    const handleStatusChange = (caseId, newStatus) => {
        setCases(prev => prev.map(c => c.id === caseId ? { ...c, status: newStatus } : c));
        setSelectedCase(prev => prev?.id === caseId ? { ...prev, status: newStatus } : prev);
        fetchStats();
    };

    const handleCaseDeleted = (caseId) => {
        setCases(prev => prev.filter(c => c.id !== caseId));
        setSelectedCase(null);
        fetchStats();
    };

    const handleQuickStatus = async (caseId, newStatus) => {
        try {
            await apiPatch(`/api/cases/${caseId}/status`, { status: newStatus });
            handleStatusChange(caseId, newStatus);
            toast.success(`Marked ${newStatus}`);
        } catch {
            toast.error('Failed');
        }
    };

    const toggleStatus = (s) => {
        setSelectedStatuses(prev => {
            const next = new Set(prev);
            if (next.has(s)) next.delete(s);
            else next.add(s);
            return next;
        });
    };

    const sb = stats?.status_breakdown || {};

    const statPills = [
        { key: 'new',         label: 'New',         count: sb.new || 0,              cls: 'bg-blue-100 text-blue-700 border border-blue-200' },
        { key: 'escalated',   label: 'Escalated',   count: sb.escalated || 0,        cls: 'bg-red-100 text-red-700 border border-red-200' },
        { key: null,          label: 'Critical',    count: stats?.critical_count || 0, cls: 'bg-red-600 text-white border border-red-600' },
        { key: 'in_progress', label: 'In Progress', count: sb.in_progress || 0,      cls: 'bg-amber-100 text-amber-700 border border-amber-200' },
        { key: 'resolved',    label: 'Resolved',    count: sb.resolved || 0,         cls: 'bg-green-100 text-green-700 border border-green-200' },
    ];

    return (
        <div className="-mx-4 md:-mx-6 -mt-4 md:-mt-6 flex flex-col overflow-hidden" style={{ height: 'calc(100vh - 56px)' }}>

            {/* ── Top Stats Bar ────────────────────────────────────────────── */}
            <div className="flex items-center justify-between gap-3 px-5 py-2.5 border-b bg-card shrink-0">
                <div className="flex items-center gap-2 flex-wrap">
                    {statPills.map(({ key, label, count, cls }) => (
                        <button
                            key={label}
                            onClick={() => {
                                if (!key) return;
                                setActiveView('cases');
                                setSelectedStatuses(new Set([key]));
                                setSelectedCase(null);
                            }}
                            className={cn(
                                'flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold transition-opacity',
                                cls,
                                key ? 'hover:opacity-75 cursor-pointer' : 'cursor-default'
                            )}
                        >
                            <span className="font-bold text-sm tabular-nums">{count}</span>
                            <span>{label}</span>
                        </button>
                    ))}
                </div>

                <div className="flex items-center gap-2 shrink-0">
                    <div className="relative">
                        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                        <Input
                            placeholder="Search phone or message..."
                            value={search}
                            onChange={e => handleSearchChange(e.target.value)}
                            className="pl-8 h-8 w-56 text-sm"
                        />
                    </div>
                    {search && (
                        <button onClick={() => { handleSearchChange(''); }} className="text-muted-foreground hover:text-foreground">
                            <X className="h-4 w-4" />
                        </button>
                    )}
                </div>
            </div>

            {/* ── Body ─────────────────────────────────────────────────────── */}
            <div className="flex flex-1 min-h-0 overflow-hidden">

                {/* Sidebar */}
                <div className="w-44 border-r bg-muted/20 overflow-y-auto shrink-0 px-3 py-4 space-y-4">

                    {/* Status filters */}
                    <div>
                        <div className="flex items-center justify-between mb-1.5">
                            <p className="text-[10px] uppercase font-bold text-muted-foreground tracking-widest">Status</p>
                            {selectedStatuses.size > 0 && (
                                <button
                                    onClick={() => setSelectedStatuses(new Set())}
                                    className="text-[10px] text-primary hover:underline"
                                >
                                    Clear
                                </button>
                            )}
                        </div>
                        <div className="space-y-px">
                            {SIDEBAR_STATUSES.map(s => {
                                const cfg = STATUS_CFG[s];
                                const count = sb[s] || 0;
                                const active = activeView === 'cases' && selectedStatuses.has(s);
                                return (
                                    <button
                                        key={s}
                                        onClick={() => { setActiveView('cases'); toggleStatus(s); setSelectedCase(null); }}
                                        className={cn(
                                            'w-full flex items-center justify-between gap-2 px-2 py-1.5 rounded text-xs transition-colors text-left',
                                            active
                                                ? 'bg-primary/10 text-primary font-semibold'
                                                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                                        )}
                                    >
                                        <div className="flex items-center gap-1.5">
                                            <div className={cn('w-2 h-2 rounded-full shrink-0', cfg.dot)} />
                                            {cfg.label}
                                        </div>
                                        {count > 0 && (
                                            <span className="text-[10px] font-medium tabular-nums opacity-60">{count}</span>
                                        )}
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    <Separator />

                    {/* Officer dispatches link */}
                    <div>
                        <button
                            onClick={() => { setActiveView(v => v === 'escalations' ? 'cases' : 'escalations'); setSelectedCase(null); }}
                            className={cn(
                                'w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs transition-colors text-left',
                                activeView === 'escalations'
                                    ? 'bg-primary/10 text-primary font-semibold'
                                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                            )}
                        >
                            <Mail className="h-3 w-3 shrink-0" />
                            Officer Dispatches
                        </button>
                    </div>

                    <Separator />

                    {/* Category filters */}
                    <div>
                        <div className="flex items-center justify-between mb-1.5">
                            <p className="text-[10px] uppercase font-bold text-muted-foreground tracking-widest">Category</p>
                            {selectedCategories.size > 0 && (
                                <button
                                    onClick={() => setSelectedCategories(new Set())}
                                    className="text-[10px] text-primary hover:underline"
                                >
                                    Clear
                                </button>
                            )}
                        </div>
                        <div className="space-y-px max-h-56 overflow-y-auto">
                            {CATEGORY_OPTIONS.map(cat => {
                                const active = selectedCategories.has(cat);
                                return (
                                    <button
                                        key={cat}
                                        onClick={() => {
                                            setSelectedCategories(prev => {
                                                const next = new Set(prev);
                                                if (next.has(cat)) next.delete(cat);
                                                else next.add(cat);
                                                return next;
                                            });
                                        }}
                                        className={cn(
                                            'w-full flex items-center gap-1.5 px-2 py-1 rounded text-[11px] transition-colors text-left',
                                            active
                                                ? 'bg-primary/10 text-primary font-medium'
                                                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                                        )}
                                    >
                                        <div className={cn('w-1.5 h-1.5 rounded-full shrink-0 transition-colors', active ? 'bg-primary' : 'bg-slate-300')} />
                                        <span className="truncate">{cat}</span>
                                    </button>
                                );
                            })}
                        </div>
                    </div>
                </div>

                {/* Case Feed */}
                <div className={cn(
                    'flex-1 overflow-y-auto flex flex-col min-w-0',
                    selectedCase ? 'hidden md:flex' : 'flex'
                )}>
                    {activeView === 'escalations' ? (
                        <EscalationsView toast={toast} />
                    ) : (
                        <>
                            {/* Feed sub-header */}
                            <div className="px-4 py-2 border-b bg-card flex items-center justify-between sticky top-0 z-10 shrink-0">
                                <span className="text-xs text-muted-foreground">
                                    {loading ? '...' : `${totalCases} case${totalCases !== 1 ? 's' : ''}`}
                                    {selectedStatuses.size > 0 && (
                                        <span className="ml-1 opacity-60">
                                            · {[...selectedStatuses].map(s => STATUS_CFG[s]?.label || s).join(', ')}
                                        </span>
                                    )}
                                    {selectedCategories.size > 0 && (
                                        <span className="ml-1 opacity-60">· {[...selectedCategories].join(', ')}</span>
                                    )}
                                </span>
                                {totalCases > 100 && (
                                    <span className="text-[11px] bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium flex items-center gap-1">
                                        <AlertTriangle className="h-3 w-3" /> {totalCases} cases
                                    </span>
                                )}
                            </div>

                            {loading ? (
                                <div className="divide-y">
                                    {[...Array(10)].map((_, i) => (
                                        <div key={i} className="flex items-center gap-3 px-4 py-3">
                                            <Skeleton className="h-2 w-2 rounded-full shrink-0" />
                                            <Skeleton className="h-3 w-8" />
                                            <Skeleton className="h-3 w-24" />
                                            <Skeleton className="h-5 w-20 rounded-full" />
                                            <Skeleton className="h-3 w-20 hidden lg:block" />
                                            <Skeleton className="h-3 flex-1" />
                                            <Skeleton className="h-3 w-8" />
                                        </div>
                                    ))}
                                </div>
                            ) : cases.length === 0 ? (
                                <div className="flex-1 flex flex-col items-center justify-center py-20 text-center">
                                    <CheckCircle2 className="h-10 w-10 text-muted-foreground/25 mb-3" />
                                    <p className="text-sm text-muted-foreground font-medium">No cases found</p>
                                    <p className="text-xs text-muted-foreground mt-1">
                                        {debouncedSearch
                                            ? `No results for "${debouncedSearch}"`
                                            : selectedStatuses.size > 0 || selectedCategories.size > 0
                                                ? 'Try adjusting your filters'
                                                : 'No cases yet'}
                                    </p>
                                </div>
                            ) : (
                                <>
                                    {cases.map(c => (
                                        <CaseRow
                                            key={c.id}
                                            c={c}
                                            isSelected={selectedCase?.id === c.id}
                                            onClick={() => setSelectedCase(c)}
                                            onQuickStatus={handleQuickStatus}
                                        />
                                    ))}
                                    {hasMore && (
                                        <div className="p-4 flex justify-center shrink-0">
                                            <Button
                                                variant="outline" size="sm"
                                                onClick={() => fetchCases(false)}
                                                disabled={loadingMore}
                                                className="text-xs"
                                            >
                                                {loadingMore && <Loader2 className="h-3 w-3 animate-spin mr-1" />}
                                                Load more
                                            </Button>
                                        </div>
                                    )}
                                </>
                            )}
                        </>
                    )}
                </div>

                {/* Detail Panel */}
                {selectedCase && (
                    <div className="w-[380px] border-l bg-card shrink-0 overflow-hidden flex flex-col">
                        <DetailPanel
                            caseItem={selectedCase}
                            onClose={() => setSelectedCase(null)}
                            onStatusChange={handleStatusChange}
                            onDeleted={handleCaseDeleted}
                            toast={toast}
                        />
                    </div>
                )}
            </div>
        </div>
    );
}
