'use client';

import { useState, useEffect, Suspense } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPost, apiPatch, apiDelete, apiBlob } from '@/lib/api';
import { useSearchParams, useRouter } from 'next/navigation';
import { useToast } from '@/components/ui/toast';
import { X, Loader2, AlertTriangle, CheckCircle, Download, User, Tag, FileText, Send, Mail, Shield } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';

const TABS = [
    { key: 'All', label: 'All Cases' },
    { key: 'new', label: 'New' },
    { key: 'awaiting_location', label: 'Needs Location' },
    { key: 'in_progress', label: 'In Progress' },
    { key: 'resolved', label: 'Resolved' },
    { key: 'escalated', label: 'Escalated' },
    { key: 'other', label: 'Other' },
    { key: 'clusters', label: 'Related Clusters' },
    { key: 'deleted', label: 'Deleted' },
];

const STATUS_OPTIONS = [
    { value: 'new', label: 'New', className: 'bg-blue-100 text-blue-700' },
    { value: 'awaiting_location', label: 'Needs Location', className: 'bg-orange-100 text-orange-700' },
    { value: 'in_progress', label: 'In Progress', className: 'bg-amber-100 text-amber-700' },
    { value: 'resolved', label: 'Resolved', className: 'bg-green-100 text-green-700' },
    { value: 'escalated', label: 'Escalated', className: 'bg-red-100 text-red-700' },
    { value: 'closed', label: 'Closed', className: 'bg-slate-100 text-slate-600' },
    { value: 'irrelevant', label: 'Irrelevant', className: 'bg-slate-100 text-slate-500' },
];

const OTHER_CATEGORIES = ['Request', 'Greetings', 'Spam', 'Spam (Offensive)'];

function getStatusBadge(status) {
    const opt = STATUS_OPTIONS.find(o => o.value === (status || '').toLowerCase());
    if (opt) {
        return <Badge variant="secondary" className={opt.className}>{opt.label}</Badge>;
    }
    return <Badge variant="secondary">{status}</Badge>;
}

function ContactPanel({ phone, color, onClose }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [form, setForm] = useState({ display_name: '', tags: '', notes: '' });
    const [saved, setSaved] = useState(false);

    useEffect(() => {
        if (!phone) return;
        setLoading(true);
        apiGet(`/api/contacts/${encodeURIComponent(phone)}`)
            .then(d => {
                setData(d);
                setForm({
                    display_name: d.contact?.display_name || '',
                    tags: Array.isArray(d.contact?.tags) ? d.contact.tags.join(', ') : (d.contact?.tags || ''),
                    notes: d.contact?.notes || '',
                });
            })
            .catch(() => setData(null))
            .finally(() => setLoading(false));
    }, [phone]);

    const handleSave = async () => {
        setSaving(true);
        setSaved(false);
        try {
            const tagsArr = form.tags
                ? form.tags.split(',').map(t => t.trim()).filter(Boolean)
                : [];
            await apiPatch(`/api/contacts/${encodeURIComponent(phone)}`, {
                display_name: form.display_name || null,
                tags: tagsArr,
                notes: form.notes || null,
            });
            setSaved(true);
            setTimeout(() => setSaved(false), 2000);
        } catch (err) {
            console.error('Contact save failed:', err);
        } finally {
            setSaving(false);
        }
    };

    return (
        <Dialog open={!!phone} onOpenChange={onClose}>
            <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
                <DialogHeader className="p-0 -m-6 mb-0">
                    <div className="p-6 text-white rounded-t-xl" style={{ background: color }}>
                        <DialogDescription className="text-white/80 text-xs uppercase tracking-widest font-semibold mb-1">
                            Constituent Profile
                        </DialogDescription>
                        <DialogTitle className="text-lg font-bold text-white font-mono">
                            {phone}
                        </DialogTitle>
                    </div>
                </DialogHeader>

                {loading ? (
                    <div className="py-12 flex items-center justify-center">
                        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                ) : (
                    <div className="space-y-5 pt-6">
                        {/* Editable fields */}
                        <div className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="contact-name" className="flex items-center gap-1.5">
                                    <User className="h-3.5 w-3.5" /> Display Name
                                </Label>
                                <Input
                                    id="contact-name"
                                    value={form.display_name}
                                    onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))}
                                    placeholder="Enter constituent's name"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="contact-tags" className="flex items-center gap-1.5">
                                    <Tag className="h-3.5 w-3.5" /> Tags
                                    <span className="text-xs text-muted-foreground font-normal">(comma-separated)</span>
                                </Label>
                                <Input
                                    id="contact-tags"
                                    value={form.tags}
                                    onChange={e => setForm(f => ({ ...f, tags: e.target.value }))}
                                    placeholder="e.g. Ward Councillor, Farmer, Repeat Caller"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="contact-notes" className="flex items-center gap-1.5">
                                    <FileText className="h-3.5 w-3.5" /> Notes
                                </Label>
                                <Textarea
                                    id="contact-notes"
                                    value={form.notes}
                                    onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                                    placeholder="Internal staff notes about this constituent"
                                    className="min-h-[80px]"
                                />
                            </div>
                        </div>

                        <Button
                            onClick={handleSave}
                            disabled={saving}
                            style={{ background: color }}
                            className="w-full"
                        >
                            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                            {saved ? 'Saved!' : saving ? 'Saving…' : 'Save Contact'}
                        </Button>

                        <Separator />

                        {/* Case history */}
                        <div>
                            <p className="text-xs text-muted-foreground uppercase font-medium mb-3">
                                Case History ({data?.cases?.length || 0})
                            </p>
                            {(!data?.cases || data.cases.length === 0) ? (
                                <p className="text-sm text-muted-foreground text-center py-6">No cases found for this number.</p>
                            ) : (
                                <div className="divide-y divide-border border rounded-lg overflow-hidden">
                                    {data.cases.map(c => (
                                        <div key={c.id} className="px-4 py-3 flex items-start justify-between gap-3 hover:bg-accent/30 transition-colors">
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 mb-0.5">
                                                    <span className="text-xs font-mono text-muted-foreground">#{c.id}</span>
                                                    <span className="text-xs font-medium text-foreground">{c.category || 'General'}</span>
                                                </div>
                                                <p className="text-xs text-muted-foreground truncate">{c.raw_message || '—'}</p>
                                            </div>
                                            <div className="shrink-0 text-right">
                                                {getStatusBadge(c.status)}
                                                <p className="text-xs text-muted-foreground mt-1">
                                                    {c.created_at ? new Date(c.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
                                                </p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                )}

                <DialogFooter>
                    <Button variant="outline" onClick={onClose}>Close</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

function EscalationModal({ caseItem, color, open, onClose, toast }) {
    const [officers, setOfficers] = useState([]);
    const [selectedOfficer, setSelectedOfficer] = useState('');
    const [letterContent, setLetterContent] = useState('');
    const [escalations, setEscalations] = useState([]);
    const [submitting, setSubmitting] = useState(false);
    const [sendingEmail, setSendingEmail] = useState(null);
    const [loadingOfficers, setLoadingOfficers] = useState(false);

    useEffect(() => {
        if (!open) return;
        setLoadingOfficers(true);
        Promise.all([
            apiGet('/api/officers').catch(() => ({ officers: [] })),
            apiGet(`/api/escalations?case_id=${caseItem.id}`).catch(() => ({ escalations: [] })),
        ]).then(([oData, eData]) => {
            setOfficers(oData.officers || []);
            setEscalations(eData.escalations || []);
        }).finally(() => setLoadingOfficers(false));
    }, [open, caseItem?.id]);

    useEffect(() => {
        if (open) {
            const cat = caseItem?.category || 'this matter';
            const ref = caseItem?.case_ref || `#${caseItem?.id}`;
            const loc = caseItem?.location || '';
            const msg = caseItem?.raw_message || '';
            setLetterContent(
`Subject: Escalation of Citizen Grievance ${ref}

Respected Sir/Madam,

I am writing to bring to your urgent attention a citizen grievance (Ref: ${ref}) related to ${cat}${loc ? ` in ${loc}` : ''}.

Citizen's complaint:
"${msg.slice(0, 300)}${msg.length > 300 ? '...' : ''}"

This issue requires immediate attention and resolution. Kindly look into this matter and take necessary action at the earliest.

Thank you for your cooperation.

Regards,
MP Office`);
        }
    }, [open, caseItem]);

    const handleEscalate = async () => {
        if (!selectedOfficer) {
            toast.error('Please select an officer');
            return;
        }
        setSubmitting(true);
        try {
            await apiPost('/api/escalations', {
                case_id: caseItem.id,
                officer_id: parseInt(selectedOfficer),
                letter_content: letterContent,
                deadline: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0],
            });
            toast.success('Case escalated to officer');
            const eData = await apiGet(`/api/escalations?case_id=${caseItem.id}`).catch(() => ({ escalations: [] }));
            setEscalations(eData.escalations || []);
            setSelectedOfficer('');
        } catch (err) {
            toast.error('Failed to escalate: ' + (err.message || 'Unknown error'));
        } finally {
            setSubmitting(false);
        }
    };

    const handleSendEmail = async (escalationId) => {
        setSendingEmail(escalationId);
        try {
            await apiPost(`/api/escalations/${escalationId}/send`);
            toast.success('Email sent to officer');
            const eData = await apiGet(`/api/escalations?case_id=${caseItem.id}`).catch(() => ({ escalations: [] }));
            setEscalations(eData.escalations || []);
        } catch (err) {
            toast.error('Failed to send email: ' + (err.message || 'Unknown error'));
        } finally {
            setSendingEmail(null);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onClose}>
            <DialogContent className="max-w-xl max-h-[80vh] overflow-y-auto">
                <DialogHeader className="p-0 -m-6 mb-0">
                    <div className="p-5 text-white rounded-t-xl" style={{ background: color || '#b45309' }}>
                        <DialogDescription className="text-white/80 text-xs uppercase tracking-widest font-semibold mb-1">
                            Escalation · Case #{caseItem?.id}
                        </DialogDescription>
                        <DialogTitle className="text-lg font-bold text-white">Escalate to Officer</DialogTitle>
                    </div>
                </DialogHeader>

                <div className="space-y-5 pt-6">
                    {/* Officer picker */}
                    <div>
                        <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Select Officer</div>
                        {loadingOfficers ? (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading officers...</div>
                        ) : officers.length === 0 ? (
                            <p className="text-sm text-muted-foreground">No officers configured. Add officers in Settings first.</p>
                        ) : (
                            <select
                                value={selectedOfficer}
                                onChange={e => setSelectedOfficer(e.target.value)}
                                className="w-full border rounded-lg p-2 text-sm"
                            >
                                <option value="">— Select Officer —</option>
                                {officers.map(o => (
                                    <option key={o.id} value={o.id}>
                                        {o.name} — {o.designation}{o.department ? `, ${o.department}` : ''}
                                    </option>
                                ))}
                            </select>
                        )}
                    </div>

                    {/* Letter content */}
                    <div>
                        <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Escalation Letter</div>
                        <Textarea
                            value={letterContent}
                            onChange={e => setLetterContent(e.target.value)}
                            className="min-h-[180px] text-sm font-mono"
                        />
                    </div>

                    <Button
                        onClick={handleEscalate}
                        disabled={submitting || !selectedOfficer}
                        className="w-full bg-amber-600 hover:bg-amber-700 text-white"
                    >
                        {submitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Shield className="h-4 w-4 mr-2" />}
                        Escalate Case
                    </Button>

                    {/* Escalation history */}
                    {escalations.length > 0 && (
                        <>
                            <Separator />
                            <div>
                                <div className="text-xs text-muted-foreground uppercase font-medium mb-3">Escalation History</div>
                                <div className="space-y-3">
                                    {escalations.map(esc => (
                                        <div key={esc.id} className="border rounded-lg p-3 space-y-2">
                                            <div className="flex items-center justify-between">
                                                <div>
                                                    <span className="text-sm font-medium">{esc.officer_name || 'Officer'}</span>
                                                    {esc.designation && <span className="text-xs text-muted-foreground ml-2">{esc.designation}</span>}
                                                </div>
                                                <Badge variant={esc.email_sent ? 'default' : 'outline'} className="text-[10px]">
                                                    {esc.email_sent ? '✓ Email Sent' : 'Not Sent'}
                                                </Badge>
                                            </div>
                                            {esc.deadline && (
                                                <p className="text-xs text-muted-foreground">Deadline: {new Date(esc.deadline).toLocaleDateString('en-IN')}</p>
                                            )}
                                            {!esc.email_sent && (
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    className="border-blue-200 text-blue-700 hover:bg-blue-50"
                                                    disabled={sendingEmail === esc.id}
                                                    onClick={() => handleSendEmail(esc.id)}
                                                >
                                                    {sendingEmail === esc.id ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Mail className="h-3 w-3 mr-1" />}
                                                    Send Email to Officer
                                                </Button>
                                            )}
                                            {esc.email_sent && esc.email_sent_at && (
                                                <p className="text-xs text-emerald-600">Sent on {new Date(esc.email_sent_at).toLocaleString('en-IN')}</p>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </>
                    )}
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={onClose}>Close</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

function CaseModal({ caseItem, color, onClose, onStatusChange, staff, user }) {
    const toast = useToast();
    const [updating, setUpdating] = useState(null);
    const [notes, setNotes] = useState('');
    const [response, setResponse] = useState('');
    const [savingNotes, setSavingNotes] = useState(false);
    const [assignee, setAssignee] = useState('');
    const [activities, setActivities] = useState([]);
    const [loadingActivity, setLoadingActivity] = useState(false);
    const [showEscalation, setShowEscalation] = useState(false);
    const [draftSaved, setDraftSaved] = useState(false);
    const [similarCases, setSimilarCases] = useState([]);
    const [notifyOpen, setNotifyOpen] = useState(false);
    const [notifyInput, setNotifyInput] = useState('');
    const [notifySending, setNotifySending] = useState(false);

    // Load from localStorage or server values when case opens
    useEffect(() => {
        if (!caseItem) return;
        const savedNotes = localStorage.getItem(`draft_notes_${caseItem.id}`);
        const savedResponse = localStorage.getItem(`draft_response_${caseItem.id}`);
        setNotes(savedNotes !== null ? savedNotes : (caseItem.notes_for_staff || ''));
        setResponse(savedResponse !== null ? savedResponse : (caseItem.response_to_citizen || ''));
        setAssignee(caseItem.assigned_to || '');
        setDraftSaved(savedNotes !== null || savedResponse !== null);

        setLoadingActivity(true);
        apiGet(`/api/cases/${caseItem.id}/activity`)
            .then(d => setActivities(d.activities || []))
            .catch(() => setActivities([]))
            .finally(() => setLoadingActivity(false));

        apiGet(`/api/cases/${caseItem.id}/similar`)
            .then(d => setSimilarCases(d.cases || []))
            .catch(() => setSimilarCases([]));
    }, [caseItem?.id]);

    // Autosave draft to localStorage on every keystroke
    useEffect(() => {
        if (!caseItem) return;
        localStorage.setItem(`draft_notes_${caseItem.id}`, notes);
        localStorage.setItem(`draft_response_${caseItem.id}`, response);
    }, [notes, response, caseItem?.id]);

    if (!caseItem) return null;

    const c = caseItem;
    const meta = c.case_metadata || {};
    const createdAt = c.created_at ? new Date(c.created_at) : null;
    const updatedAt = c.updated_at ? new Date(c.updated_at) : null;
    const currentStatus = (c.status || 'new').toLowerCase();

    const handleStatusChange = async (newStatus) => {
        setUpdating(newStatus);
        try {
            await apiPatch(`/api/cases/${c.id}/status`, { status: newStatus });
            onStatusChange(c.id, newStatus);
            toast.success(`Case marked as ${newStatus}`);
        } catch (err) {
            console.error('Status update failed:', err);
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
            localStorage.removeItem(`draft_notes_${c.id}`);
            localStorage.removeItem(`draft_response_${c.id}`);
            setDraftSaved(false);
            toast.success('Notes saved successfully');
        } catch (err) {
            console.error('Failed to save notes:', err);
            toast.error('Failed to save notes');
        } finally {
            setSavingNotes(false);
        }
    };

    const isMp = user?.role === 'mp';
    const caseRef = c.case_ref || `#${c.id}`;

    const sendNotification = async () => {
        setNotifySending(true);
        try {
            await apiPost(`/api/cases/${c.id}/notify/send`, {});
            setNotifyOpen(false);
            setNotifyInput('');
            toast.success('WhatsApp update sent — case moved to Resolved');
            onStatusChange(c.id, 'resolved');
            onClose();
        } catch (err) {
            toast.error(err.message || 'Failed to send notification');
        } finally {
            setNotifySending(false);
        }
    };

    const handleAssign = async (username) => {
        try {
            await apiPatch(`/api/cases/${c.id}`, { assigned_to: username || null });
            setAssignee(username);
            onStatusChange(c.id, currentStatus);
            toast.success(`Case assigned to ${username || 'unassigned'}`);
        } catch (err) {
            console.error('Failed to assign:', err);
            toast.error('Failed to assign case');
        }
    };

    const handleDelete = async () => {
        if (!window.confirm('Are you sure you want to delete this case? This cannot be undone.')) {
            return;
        }
        try {
            await apiDelete(`/api/cases/${c.id}`);
            onClose();
            toast.success('Case deleted successfully');
        } catch (err) {
            console.error('Failed to delete case:', err);
            toast.error('Failed to delete case');
        }
    };

    // ── Resolved: stripped-down read-only view ──────────────────────────────
    if (currentStatus === 'resolved') {
        const notifyActivity = [...activities].reverse().find(a => a.action === 'citizen_notified');
        const notifiedAt = notifyActivity ? new Date(notifyActivity.created_at) : null;
        return (
            <Dialog open={!!caseItem} onOpenChange={onClose}>
                <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
                    <DialogHeader className="p-0 -m-6 mb-0">
                        <div className="p-6 text-white rounded-t-xl" style={{ background: color }}>
                            <DialogDescription className="text-white/80 text-xs uppercase tracking-widest font-semibold mb-1">
                                Resolved · {caseRef}
                            </DialogDescription>
                            <DialogTitle className="text-lg font-bold text-white">{c.category || 'General'}</DialogTitle>
                        </div>
                    </DialogHeader>
                    <div className="space-y-4 pt-6">
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                            {[
                                ['Case Number', caseRef],
                                ['Contact', c.user_phone || '-'],
                                ['Category', c.category || 'General'],
                                ['Location', meta.matched_value || c.location || '-'],
                                ['Assembly', meta.assembly_constituency || c.assembly || '-'],
                                ['Date Filed', createdAt ? createdAt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '-'],
                                ['Time Filed', createdAt ? createdAt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '-'],
                                ['Date Resolved', notifiedAt ? notifiedAt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '-'],
                                ['Time Resolved', notifiedAt ? notifiedAt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '-'],
                            ].map(([label, value]) => (
                                <div key={label} className="border rounded-lg p-3">
                                    <div className="text-xs text-muted-foreground uppercase font-medium">{label}</div>
                                    <div className="text-sm font-medium text-foreground mt-0.5">{value}</div>
                                </div>
                            ))}
                        </div>
                        <div>
                            <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Complaint Message</div>
                            <div className="bg-muted/50 border rounded-lg p-4 text-sm text-foreground whitespace-pre-wrap leading-relaxed min-h-[60px]">
                                {c.raw_message || 'No content available.'}
                            </div>
                        </div>
                        <div>
                            <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Resolution Message Sent to Citizen</div>
                            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 text-sm text-foreground whitespace-pre-wrap leading-relaxed min-h-[60px]">
                                {c.response_to_citizen || <span className="text-muted-foreground italic">Standard status message was sent</span>}
                            </div>
                        </div>
                        <Separator />
                        <div>
                            <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Activity Log</div>
                            {loadingActivity ? (
                                <div className="flex items-center justify-center py-4"><Loader2 className="h-4 w-4 animate-spin text-muted-foreground" /></div>
                            ) : (
                                <div className="space-y-2 max-h-48 overflow-y-auto">
                                    {activities.length === 0 ? (
                                        <p className="text-xs text-muted-foreground">No activity yet</p>
                                    ) : (
                                        activities.map(a => (
                                            <div key={a.id} className="flex items-start gap-2 text-xs">
                                                <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                                                <div>
                                                    <span className="font-medium">{a.username}</span> {a.action.replace(/_/g, ' ')}
                                                    {a.new_value && <span className="text-muted-foreground"> → {a.new_value}</span>}
                                                    <div className="text-muted-foreground">{a.created_at ? new Date(a.created_at).toLocaleString('en-IN') : ''}</div>
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={onClose}>Close</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        );
    }

    return (
        <Dialog open={!!caseItem} onOpenChange={onClose}>
            <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
                <DialogHeader className="p-0 -m-6 mb-0">
                    <div className="p-6 text-white rounded-t-xl" style={{ background: color }}>
                        <DialogDescription className="text-white/80 text-xs uppercase tracking-widest font-semibold mb-1">
                            Grievance · #{c.id}
                        </DialogDescription>
                        <DialogTitle className="text-lg font-bold text-white">
                            {c.category || 'General'}
                        </DialogTitle>
                    </div>
                </DialogHeader>

                <div className="space-y-4 pt-6">
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                        {[
                            ['Contact', c.user_phone || '-'],
                            ['Category', c.category || 'General'],
                            ['Status', currentStatus],
                            ['Location', meta.matched_value || c.location || '-'],
                            ['Assembly', meta.assembly_constituency || c.assembly || '-'],
                            ['Date', createdAt ? createdAt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '-'],
                            ['Time', createdAt ? createdAt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '-'],
                            ['Critical', c.is_critical ? 'Yes' : 'No'],
                            ['Last Updated', updatedAt ? updatedAt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '-'],
                        ].map(([label, value]) => (
                            <div key={label} className="border rounded-lg p-3">
                                <div className="text-xs text-muted-foreground uppercase font-medium">{label}</div>
                                <div className="text-sm font-medium text-foreground mt-0.5">{value}</div>
                            </div>
                        ))}
                    </div>

                    <div>
                        <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Full Message</div>
                        <div className="bg-muted/50 border rounded-lg p-4 text-sm text-foreground whitespace-pre-wrap leading-relaxed min-h-[80px]">
                            {c.raw_message || 'No content available.'}
                        </div>
                    </div>

                    {meta.summary && (
                        <div>
                            <div className="text-xs text-muted-foreground uppercase font-medium mb-2">AI Summary</div>
                            <div className="bg-muted/50 border rounded-lg p-4 text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                                {meta.summary}
                            </div>
                        </div>
                    )}

                    <Separator />

                    <div>
                        <div className="text-xs text-muted-foreground uppercase font-medium mb-3">Update Status</div>
                        <div className="flex flex-wrap gap-2">
                            {STATUS_OPTIONS.filter(o => o.value !== currentStatus).map(opt => (
                                <Button
                                    key={opt.value}
                                    variant="outline"
                                    size="sm"
                                    onClick={() => handleStatusChange(opt.value)}
                                    disabled={updating === opt.value}
                                    className={cn("border", opt.className)}
                                >
                                    {updating === opt.value && <Loader2 className="h-3 w-3 animate-spin" />}
                                    Mark {opt.label}
                                </Button>
                            ))}
                        </div>
                    </div>

                    <Separator />

                    <div className="space-y-4">
                        <div>
                            <div className="flex items-center justify-between mb-2">
                                <div className="text-xs text-muted-foreground uppercase font-medium">Notes for Staff</div>
                                {draftSaved && <span className="text-xs text-amber-600 font-medium">● Draft saved locally</span>}
                            </div>
                            <Textarea
                                value={notes}
                                onChange={e => setNotes(e.target.value)}
                                placeholder="Internal notes..."
                                className="min-h-[60px]"
                            />
                        </div>
                        <div>
                            <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Response to Citizen</div>
                            <Textarea
                                value={response}
                                onChange={e => setResponse(e.target.value)}
                                placeholder="Response message..."
                                className="min-h-[60px]"
                            />
                        </div>
                        <div className="flex items-center gap-2 flex-wrap">
                            <Button onClick={saveNotes} disabled={savingNotes}>
                                {savingNotes ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
                                Save Notes
                            </Button>
                            <Button
                                variant="outline"
                                className="border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                                disabled={!c.user_phone || !isMp}
                                title={!isMp ? 'Only the MP can send citizen notifications' : !c.user_phone ? 'No phone number on file' : ''}
                                onClick={() => { setNotifyInput(''); setNotifyOpen(true); }}
                            >
                                <Send className="h-4 w-4 mr-1" />
                                Send Update via WhatsApp
                                {!isMp && <span className="ml-1 text-xs opacity-60">(MP only)</span>}
                            </Button>
                        </div>
                    </div>

                    {/* Similar / related cases */}
                    {similarCases.length > 0 && (
                        <>
                            <Separator />
                            <div>
                                <div className="text-xs text-muted-foreground uppercase font-medium mb-2">
                                    Related Cases ({similarCases.length})
                                </div>
                                <div className="space-y-1 max-h-36 overflow-y-auto">
                                    {similarCases.map(s => (
                                        <div key={s.id} className="flex items-center gap-2 text-xs py-1 border-b last:border-0">
                                            <span className="font-mono text-muted-foreground shrink-0">#{s.id}</span>
                                            {getStatusBadge(s.status)}
                                            <span className="truncate text-muted-foreground">{s.message_preview}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </>
                    )}

                    <Separator />

                    <div>
                        <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Assign To</div>
                        <select
                            value={assignee}
                            onChange={e => handleAssign(e.target.value)}
                            className="w-full border rounded-lg p-2 text-sm"
                        >
                            <option value="">Unassigned</option>
                            {staff.map(s => (
                                <option key={s.username} value={s.username}>
                                    {s.display_name || s.username}
                                </option>
                            ))}
                        </select>
                    </div>

                    <Separator />

                    <div>
                        <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Activity Log</div>
                        {loadingActivity ? (
                            <div className="flex items-center justify-center py-4">
                                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                            </div>
                        ) : (
                            <div className="space-y-2 max-h-48 overflow-y-auto">
                                {activities.length === 0 ? (
                                    <p className="text-xs text-muted-foreground">No activity yet</p>
                                ) : (
                                    activities.map(a => (
                                        <div key={a.id} className="flex items-start gap-2 text-xs">
                                            <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                                            <div>
                                                <span className="font-medium">{a.username}</span> {a.action.replace('_', ' ')}
                                                {a.new_value && <span className="text-muted-foreground"> → {a.new_value}</span>}
                                                <div className="text-muted-foreground">{a.created_at ? new Date(a.created_at).toLocaleString('en-IN') : ''}</div>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        )}
                    </div>

                    <Separator />

                    <div className="flex gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setShowEscalation(true)}
                            className="border-amber-300 text-amber-700 hover:bg-amber-50"
                        >
                            Escalate to Officer
                        </Button>
                        {(user?.role === 'mp' || user?.role === 'pr') && (
                            <Button
                                variant="destructive"
                                size="sm"
                                onClick={handleDelete}
                            >
                                Delete Case
                            </Button>
                        )}
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={onClose}>Close</Button>
                </DialogFooter>
            </DialogContent>

            {showEscalation && (
                <EscalationModal
                    caseItem={c}
                    color="#b45309"
                    open={showEscalation}
                    onClose={() => setShowEscalation(false)}
                    toast={toast}
                />
            )}

            {/* Notify confirmation dialog */}
            <Dialog open={notifyOpen} onOpenChange={open => { setNotifyOpen(open); if (!open) setNotifyInput(''); }}>
                <DialogContent className="max-w-sm">
                    <DialogHeader>
                        <DialogTitle>Send WhatsApp Update</DialogTitle>
                        <DialogDescription>
                            This will message the citizen about the current status of their case. Type the case reference <strong>{caseRef}</strong> to confirm.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="py-2 space-y-3">
                        <div className="rounded-lg bg-muted/50 border p-3 text-sm text-muted-foreground">
                            {(() => {
                                if (response && response.trim()) return response.trim();
                                const statusMessages = {
                                    new: `Your grievance (${caseRef}) has been received and is being reviewed.`,
                                    in_progress: `Update on your grievance (${caseRef}): We are actively working on this.`,
                                    escalated: `Update on your grievance (${caseRef}): This has been escalated to the relevant authority.`,
                                    resolved: `Good news! Your grievance (${caseRef}) has been resolved. If unsatisfied, reply 'NO' to reopen.`,
                                    completed: `Good news! Your grievance (${caseRef}) has been resolved. If unsatisfied, reply 'NO' to reopen.`,
                                    closed: `Your grievance (${caseRef}) has been closed. Thank you for reaching out.`,
                                };
                                return statusMessages[c.status] || `Update on your grievance (${caseRef}): Status is now '${c.status}'.`;
                            })()}
                        </div>
                        {response && response.trim() && (
                            <p className="text-xs text-emerald-600 font-medium">✓ Using your custom response message</p>
                        )}
                        <Input
                            placeholder={`Type ${caseRef} to confirm`}
                            value={notifyInput}
                            onChange={e => setNotifyInput(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && notifyInput === caseRef && sendNotification()}
                            autoFocus
                        />
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => { setNotifyOpen(false); setNotifyInput(''); }}>Cancel</Button>
                        <Button
                            onClick={sendNotification}
                            disabled={notifyInput !== caseRef || notifySending}
                            className="bg-emerald-600 hover:bg-emerald-700 text-white"
                        >
                            {notifySending ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Send className="h-4 w-4 mr-1" />}
                            Confirm & Send
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </Dialog>
    );
}

function BriefcaseInner() {
    const { user } = useAuth();
    const toast = useToast();
    const router = useRouter();
    const searchParams = useSearchParams();

    const color = user?.theme_color || '#006a4d';

    const [cases, setCases] = useState([]);
    const [loading, setLoading] = useState(true);
    const [statusFilter, setStatusFilter] = useState(() => searchParams.get('status') || 'All');
    const [categoryFilter, setCategoryFilter] = useState(() => searchParams.get('category') || '');
    const [selected, setSelected] = useState(null);
    const [downloading, setDownloading] = useState(false);
    const [contactPhone, setContactPhone] = useState(null);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [totalCases, setTotalCases] = useState(0);
    const [selectedIds, setSelectedIds] = useState(new Set());
    const [staff, setStaff] = useState([]);
    const [searchInput, setSearchInput] = useState('');
    const [search, setSearch] = useState('');
    const [pageSize, setPageSize] = useState(50);
    const [hasNewCases, setHasNewCases] = useState(false);
    const [clusters, setClusters] = useState([]);
    const [loadingClusters, setLoadingClusters] = useState(false);
    const [deletedCases, setDeletedCases] = useState([]);
    const [loadingDeleted, setLoadingDeleted] = useState(false);

    async function downloadReport() {
        setDownloading(true);
        try {
            const params = new URLSearchParams();
            if (statusFilter !== 'All') params.set('status', statusFilter);
            if (categoryFilter) params.set('category', categoryFilter);
            const qs = params.toString() ? `?${params}` : '';
            const blob = await apiBlob(`/api/reports/grievance${qs}`);
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `grievance_report_${new Date().toISOString().slice(0, 10)}.pdf`;
            a.click();
            URL.revokeObjectURL(url);
            toast.success('Report downloaded successfully');
        } catch (err) {
            console.error('Report download failed:', err);
            toast.error('Failed to download report');
        } finally {
            setDownloading(false);
        }
    }

    // Sync filters when the URL changes
    useEffect(() => {
        const status = searchParams.get('status') || 'All';
        const cat = searchParams.get('category') || '';
        setStatusFilter(status);
        setCategoryFilter(cat);
        setPage(1);
    }, [searchParams]);

    // Debounce search input → search param
    useEffect(() => {
        const t = setTimeout(() => { setSearch(searchInput); setPage(1); }, 400);
        return () => clearTimeout(t);
    }, [searchInput]);

    // Fetch staff on mount
    useEffect(() => {
        apiGet('/api/staff')
            .then(d => setStaff(d.staff || []))
            .catch(() => { console.error('Failed to fetch staff'); });
    }, []);

    // Fetch clusters when that tab is active
    const fetchClusters = async () => {
        setLoadingClusters(true);
        try {
            const d = await apiGet('/api/clusters');
            setClusters(d.clusters || []);
        } catch { setClusters([]); }
        finally { setLoadingClusters(false); }
    };

    // Fetch deleted cases when that tab is active
    const fetchDeleted = async () => {
        setLoadingDeleted(true);
        try {
            const d = await apiGet('/api/cases/deleted');
            setDeletedCases(d.cases || []);
        } catch { setDeletedCases([]); }
        finally { setLoadingDeleted(false); }
    };

    // Fetch cases whenever the active filter, page, search, or page size changes
    useEffect(() => {
        if (statusFilter === 'clusters') { fetchClusters(); return; }
        if (statusFilter === 'deleted') { fetchDeleted(); return; }

        let cancelled = false;

        async function fetchCases() {
            setLoading(true);
            try {
                const params = new URLSearchParams({
                    page: String(page),
                    limit: String(pageSize),
                });

                if (statusFilter === 'All') {
                    params.set('exclude_status', 'resolved,closed');
                } else if (statusFilter === 'other') {
                    params.set('categories', OTHER_CATEGORIES.join(','));
                } else {
                    params.set('status', statusFilter);
                }

                if (categoryFilter) params.set('category', categoryFilter);
                if (search) params.set('search', search);

                const data = await apiGet(`/api/cases?${params}`);
                if (!cancelled) {
                    setCases(data.cases || []);
                    setTotalPages(data.pages || 1);
                    setTotalCases(data.total || 0);
                    setSelectedIds(new Set());
                    setHasNewCases(false);
                }
            } catch (err) {
                if (!cancelled) {
                    console.error(err);
                    toast.error('Failed to load cases');
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        fetchCases();
        return () => { cancelled = true; };
    }, [statusFilter, categoryFilter, page, user?.username, search, pageSize]);

    // Poll every 30s for new cases (only on visible tabs with live data)
    useEffect(() => {
        if (statusFilter === 'clusters' || statusFilter === 'deleted') return;
        const interval = setInterval(async () => {
            if (document.visibilityState !== 'visible') return;
            try {
                const params = new URLSearchParams({ page: '1', limit: '1' });
                if (statusFilter === 'All') params.set('exclude_status', 'resolved,closed');
                else if (statusFilter === 'other') params.set('categories', OTHER_CATEGORIES.join(','));
                else params.set('status', statusFilter);
                if (search) params.set('search', search);
                const data = await apiGet(`/api/cases?${params}`);
                if ((data.total || 0) > totalCases) setHasNewCases(true);
            } catch { /* silent */ }
        }, 30000);
        return () => clearInterval(interval);
    }, [statusFilter, totalCases, user?.username, search]);

    // Auto-open a specific case when case_id is present in the URL
    useEffect(() => {
        const caseId = searchParams.get('case_id');
        if (!caseId || cases.length === 0) return;
        const match = cases.find(c => String(c.id) === caseId);
        if (match) setSelected(match);
    }, [cases, searchParams]);

    function switchTab(key) {
        setStatusFilter(key);
        setPage(1);
        setSearch('');
        setSearchInput('');
        const url = new URL(window.location.href);
        if (key === 'All') url.searchParams.delete('status');
        else url.searchParams.set('status', key);
        window.history.replaceState({}, '', url.toString());
    }

    const handleRestore = async (caseId) => {
        try {
            await apiPatch(`/api/cases/${caseId}/restore`, {});
            setDeletedCases(prev => prev.filter(c => c.id !== caseId));
            toast.success('Case restored successfully');
        } catch (err) {
            toast.error(err.message || 'Failed to restore case');
        }
    };

    function clearCategoryFilter() {
        setCategoryFilter('');
        setPage(1);
        const url = new URL(window.location.href);
        url.searchParams.delete('category');
        window.history.replaceState({}, '', url.toString());
    }

    const handleStatusChange = (caseId, newStatus) => {
        setCases(prev => prev.map(c => c.id === caseId ? { ...c, status: newStatus } : c));
        setSelected(prev => prev && prev.id === caseId ? { ...prev, status: newStatus } : prev);
    };

    const getRowHighlight = (status, category) => {
        const s = (status || '').toLowerCase();
        const c = (category || '').toLowerCase();
        if (s === 'new' || s === 'escalated' || c === 'emergency') {
            return 'border-l-4 border-l-red-500 bg-red-50/50';
        }
        if (s === 'resolved' || s === 'in_progress') {
            return 'border-l-4 border-l-green-500 bg-green-50/30';
        }
        return '';
    };

    async function bulkStatusChange(newStatus) {
        const ids = [...selectedIds];
        if (ids.length === 0) return;
        try {
            await Promise.all(ids.map(id => apiPatch(`/api/cases/${id}/status`, { status: newStatus })));
            setCases(prev => prev.map(c => ids.includes(c.id) ? { ...c, status: newStatus } : c));
            setSelectedIds(new Set());
            toast.success(`Updated ${ids.length} case${ids.length !== 1 ? 's' : ''} to ${newStatus}`);
        } catch (err) {
            console.error(err);
            toast.error('Bulk update failed');
        }
    }

    async function bulkAssign(username) {
        const ids = [...selectedIds];
        if (ids.length === 0) return;
        try {
            await Promise.all(ids.map(id => apiPatch(`/api/cases/${id}`, { assigned_to: username || null })));
            setCases(prev => prev.map(c => ids.includes(c.id) ? { ...c, assigned_to: username } : c));
            setSelectedIds(new Set());
            toast.success(`Assigned ${ids.length} case${ids.length !== 1 ? 's' : ''} to ${username || 'unassigned'}`);
        } catch (err) {
            console.error(err);
            toast.error('Bulk assign failed');
        }
    }

    return (
        <div className="space-y-6">
            <div className="flex items-start justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-foreground">Briefcase</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Manage constituent grievances and cases
                    </p>
                </div>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={downloadReport}
                    disabled={downloading}
                    className="shrink-0 gap-2"
                >
                    {downloading
                        ? <Loader2 className="h-4 w-4 animate-spin" />
                        : <Download className="h-4 w-4" />}
                    {downloading ? 'Generating…' : 'Download Report'}
                </Button>
            </div>

            {hasNewCases && (
                <div
                    className="flex items-center justify-between gap-3 px-4 py-2 rounded-lg text-sm font-medium mb-2"
                    style={{ background: '#ecfdf5', border: '1px solid #a7f3d0', color: '#065f46' }}
                >
                    <span>New cases arrived since last refresh.</span>
                    <button
                        className="text-xs underline"
                        onClick={() => { setHasNewCases(false); setPage(1); }}
                    >
                        Refresh now
                    </button>
                </div>
            )}

            <Card>
                <CardHeader className="pb-0">
                    <div className="overflow-x-auto -mx-6 px-6">
                        <Tabs value={statusFilter} onValueChange={switchTab}>
                            <TabsList className="h-auto p-0 bg-transparent gap-6">
                                {TABS.map(t => (
                                    <TabsTrigger
                                        key={t.key}
                                        value={t.key}
                                        className={cn(
                                            "px-0 pb-3 rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none",
                                            "text-sm font-medium text-muted-foreground data-[state=active]:text-foreground"
                                        )}
                                        style={statusFilter === t.key ? { borderColor: color, color } : {}}
                                    >
                                        {t.label}
                                    </TabsTrigger>
                                ))}
                            </TabsList>
                        </Tabs>
                    </div>

                    {statusFilter !== 'clusters' && statusFilter !== 'deleted' && (
                        <div className="flex items-center gap-2 mt-3">
                            <div className="relative flex-1 max-w-sm">
                                <svg className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                                </svg>
                                <Input
                                    className="pl-8 h-8 text-sm"
                                    placeholder="Search by phone, message, ref, location…"
                                    value={searchInput}
                                    onChange={e => setSearchInput(e.target.value)}
                                />
                            </div>
                            <select
                                className="text-sm border rounded px-2 py-1 h-8"
                                value={pageSize}
                                onChange={e => { setPageSize(Number(e.target.value)); setPage(1); }}
                            >
                                {[25, 50, 100].map(n => (
                                    <option key={n} value={n}>{n} / page</option>
                                ))}
                            </select>
                        </div>
                    )}
                </CardHeader>

                {categoryFilter && (
                    <div className="px-6 py-3 border-b flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">Filtered by category:</span>
                        <Badge variant="default" className="gap-1" style={{ background: color }}>
                            {categoryFilter}
                            <button onClick={clearCategoryFilter} className="ml-1 hover:opacity-80">
                                <X className="h-3 w-3" />
                            </button>
                        </Badge>
                        <span className="text-xs text-muted-foreground ml-1">
                            {loading ? '...' : `${cases.length} case${cases.length !== 1 ? 's' : ''}`}
                        </span>
                    </div>
                )}

                {selectedIds.size > 0 && (
                    <div className="px-6 py-3 border-b bg-primary/5 flex items-center gap-4">
                        <span className="text-sm font-medium">{selectedIds.size} selected</span>
                        <select
                            className="text-sm border rounded px-2 py-1"
                            value=""
                            onChange={(e) => {
                                if (e.target.value) {
                                    bulkStatusChange(e.target.value);
                                    e.target.value = '';
                                }
                            }}
                        >
                            <option value="">Bulk Status...</option>
                            {STATUS_OPTIONS.map(s => (
                                <option key={s.value} value={s.value}>{s.label}</option>
                            ))}
                        </select>
                        <select
                            className="text-sm border rounded px-2 py-1"
                            value=""
                            onChange={(e) => {
                                if (e.target.value) {
                                    bulkAssign(e.target.value);
                                    e.target.value = '';
                                }
                            }}
                        >
                            <option value="">Bulk Assign...</option>
                            {staff.map(s => (
                                <option key={s.username} value={s.username}>{s.display_name || s.username}</option>
                            ))}
                        </select>
                        <Button variant="ghost" size="sm" onClick={() => setSelectedIds(new Set())}>Clear</Button>
                    </div>
                )}

                <CardContent className="pt-0">
                    {/* ── Clusters tab ── */}
                    {statusFilter === 'clusters' ? (
                        loadingClusters ? (
                            <div className="space-y-3 py-6">{[1,2,3].map(i => <Skeleton key={i} className="h-16 w-full rounded-lg" />)}</div>
                        ) : clusters.length === 0 ? (
                            <div className="text-center py-16 text-muted-foreground">No clusters found in the last 30 days.</div>
                        ) : (
                            <div className="divide-y">
                                {clusters.map((cl, i) => (
                                    <div key={i} className="py-4">
                                        <div className="flex items-center justify-between mb-2">
                                            <div>
                                                <span className="font-semibold text-sm">{cl.category}</span>
                                                {cl.location && cl.location !== 'Unknown' && (
                                                    <span className="text-muted-foreground text-sm ml-2">· {cl.location}</span>
                                                )}
                                            </div>
                                            <Badge variant="secondary">{cl.count} cases</Badge>
                                        </div>
                                        <div className="space-y-1">
                                            {(cl.cases || []).slice(0, 5).map(c => (
                                                <div
                                                    key={c.id}
                                                    className="text-xs text-muted-foreground flex items-center gap-2 cursor-pointer hover:text-foreground"
                                                    onClick={() => setSelected({ id: c.id, ...c })}
                                                >
                                                    <span className="shrink-0">{getStatusBadge(c.status)}</span>
                                                    <span className="truncate">{c.message_preview}</span>
                                                </div>
                                            ))}
                                            {cl.count > 5 && (
                                                <p className="text-xs text-muted-foreground">+{cl.count - 5} more cases in this cluster</p>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )
                    ) : statusFilter === 'deleted' ? (
                        /* ── Deleted tab ── */
                        loadingDeleted ? (
                            <div className="space-y-3 py-6">{[1,2,3].map(i => <Skeleton key={i} className="h-12 w-full rounded-lg" />)}</div>
                        ) : deletedCases.length === 0 ? (
                            <div className="text-center py-16 text-muted-foreground">No deleted cases in the last 7 days.</div>
                        ) : (
                            <div className="overflow-x-auto -mx-6">
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead className="pl-6">#</TableHead>
                                            <TableHead>Contact</TableHead>
                                            <TableHead>Category</TableHead>
                                            <TableHead>Deleted At</TableHead>
                                            <TableHead>Deleted By</TableHead>
                                            <TableHead className="text-right pr-6">Action</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {deletedCases.map(c => (
                                            <TableRow key={c.id} className="opacity-60">
                                                <TableCell className="pl-6 font-mono text-xs text-muted-foreground">{c.id}</TableCell>
                                                <TableCell className="font-mono text-xs">{c.user_phone || '-'}</TableCell>
                                                <TableCell>{c.category || 'General'}</TableCell>
                                                <TableCell className="text-xs text-muted-foreground">
                                                    {c.deleted_at ? new Date(c.deleted_at).toLocaleString('en-IN') : '-'}
                                                </TableCell>
                                                <TableCell className="text-xs">{c.deleted_by || '-'}</TableCell>
                                                <TableCell className="text-right pr-6">
                                                    <Button size="sm" variant="outline" onClick={() => handleRestore(c.id)}>
                                                        Restore
                                                    </Button>
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        )
                    ) : loading ? (
                        <div className="space-y-3 py-6">
                            {[1, 2, 3, 4, 5].map(i => (
                                <div key={i} className="flex items-center gap-4">
                                    <Skeleton className="h-4 w-4" />
                                    <Skeleton className="h-4 w-12" />
                                    <Skeleton className="h-4 w-24" />
                                    <Skeleton className="h-4 w-32" />
                                    <Skeleton className="h-4 w-24" />
                                    <Skeleton className="h-4 w-20" />
                                    <Skeleton className="h-6 w-20" />
                                    <Skeleton className="h-4 flex-1" />
                                </div>
                            ))}
                        </div>
                    ) : cases.length === 0 ? (
                        <div className="text-center py-16">
                            <CheckCircle className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
                            <p className="text-muted-foreground">
                                No cases found{categoryFilter ? ` in "${categoryFilter}"` : ''}
                                {statusFilter !== 'All' ? ` with status "${statusFilter}"` : ''}
                                {search ? ` matching "${search}"` : ''}.
                            </p>
                        </div>
                    ) : (
                        <div className="overflow-x-auto -mx-6">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="w-10 pl-6">
                                            <input
                                                type="checkbox"
                                                checked={selectedIds.size === cases.length && cases.length > 0}
                                                onChange={(e) => {
                                                    if (e.target.checked) setSelectedIds(new Set(cases.map(c => c.id)));
                                                    else setSelectedIds(new Set());
                                                }}
                                                className="rounded border-border"
                                            />
                                        </TableHead>
                                        <TableHead className="w-16">#</TableHead>
                                        <TableHead>Contact</TableHead>
                                        <TableHead>Category</TableHead>
                                        <TableHead>Location</TableHead>
                                        <TableHead>Assembly</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead className="max-w-[200px]">Message</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {cases.map((c) => (
                                        <TableRow
                                            key={c.id}
                                            className={cn("cursor-pointer", getRowHighlight(c.status, c.category))}
                                            onClick={() => setSelected(c)}
                                        >
                                            <TableCell className="pl-6">
                                                <input
                                                    type="checkbox"
                                                    checked={selectedIds.has(c.id)}
                                                    onChange={(e) => {
                                                        e.stopPropagation();
                                                        setSelectedIds(prev => {
                                                            const next = new Set(prev);
                                                            if (e.target.checked) next.add(c.id);
                                                            else next.delete(c.id);
                                                            return next;
                                                        });
                                                    }}
                                                    onClick={e => e.stopPropagation()}
                                                    className="rounded border-border"
                                                />
                                            </TableCell>
                                            <TableCell className="font-mono text-xs text-muted-foreground">
                                                {c.id}
                                            </TableCell>
                                            <TableCell className="font-mono text-xs">
                                                {c.user_phone ? (
                                                    <button
                                                        className="hover:underline text-primary font-mono text-xs"
                                                        onClick={e => { e.stopPropagation(); setContactPhone(c.user_phone); }}
                                                    >
                                                        {c.user_phone}
                                                    </button>
                                                ) : '-'}
                                            </TableCell>
                                            <TableCell className="font-medium">
                                                {c.category || 'General'}
                                            </TableCell>
                                            <TableCell className="text-muted-foreground">
                                                {c.location || '-'}
                                            </TableCell>
                                            <TableCell className="text-muted-foreground">
                                                {c.assembly || '-'}
                                            </TableCell>
                                            <TableCell>{getStatusBadge(c.status)}</TableCell>
                                            <TableCell className="max-w-[200px]">
                                                <span className="truncate block text-muted-foreground" title={c.raw_message}>
                                                    {c.raw_message || '-'}
                                                </span>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    )}
                </CardContent>

                {statusFilter !== 'clusters' && statusFilter !== 'deleted' && (
                    <div className="px-6 py-3 border-t flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">
                            Page {page} of {totalPages} · <strong>{totalCases}</strong> total cases
                            {search && <span> · filtered by "{search}"</span>}
                        </span>
                        <div className="flex gap-2">
                            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}>
                                Previous
                            </Button>
                            {totalPages > 2 && (
                                <span className="flex items-center px-2 text-sm text-muted-foreground">
                                    {page} / {totalPages}
                                </span>
                            )}
                            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
                                Next
                            </Button>
                        </div>
                    </div>
                )}
            </Card>

            <CaseModal
                caseItem={selected}
                color={color}
                onClose={() => setSelected(null)}
                onStatusChange={handleStatusChange}
                staff={staff}
                user={user}
            />

            <ContactPanel
                phone={contactPhone}
                color={color}
                onClose={() => setContactPhone(null)}
            />
        </div>
    );
}

export default function BriefcasePage() {
    return (
        <Suspense fallback={
            <div className="flex items-center justify-center py-20">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        }>
            <BriefcaseInner />
        </Suspense>
    );
}
