'use client';

import { useState, useEffect, Suspense } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPost, apiPatch, apiBlob } from '@/lib/api';
import { useSearchParams, useRouter } from 'next/navigation';
import { X, Loader2, AlertTriangle, CheckCircle, Download, User, Tag, FileText, Send, Clock, CheckCircle2, XCircle, MessageSquare } from 'lucide-react';
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
    { key: 'in_progress', label: 'In Progress' },
    { key: 'resolved', label: 'Resolved' },
    { key: 'escalated', label: 'Escalated' },
    { key: 'closed', label: 'Closed' },
    { key: 'other', label: 'Other' },
];

const STATUS_OPTIONS = [
    { value: 'new', label: 'New', className: 'bg-blue-100 text-blue-700' },
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

const RESOLUTION_STATUS_LABELS = {
    draft: { label: 'Draft', color: 'bg-slate-100 text-slate-600', icon: FileText },
    pending_approval: { label: 'Awaiting Approval', color: 'bg-amber-100 text-amber-700', icon: Clock },
    approved: { label: 'Approved', color: 'bg-green-100 text-green-700', icon: CheckCircle2 },
    rejected: { label: 'Rejected', color: 'bg-red-100 text-red-700', icon: XCircle },
    sent: { label: 'Sent', color: 'bg-blue-100 text-blue-700', icon: Send },
    failed: { label: 'Send Failed', color: 'bg-red-100 text-red-700', icon: XCircle },
};

function ResolutionPanel({ caseItem, color, user, onResolutionSent }) {
    const [resolution, setResolution] = useState(null);
    const [monthlySent, setMonthlySent] = useState(0);
    const [monthlyLimit] = useState(5000);
    const [loading, setLoading] = useState(true);
    const [showDraftModal, setShowDraftModal] = useState(false);
    const [draftText, setDraftText] = useState('');
    const [isDirty, setIsDirty] = useState(false); // must edit before enabling submit
    const [saving, setSaving] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [approving, setApproving] = useState(false);
    const [rejecting, setRejecting] = useState(false);
    const [sending, setSending] = useState(false);
    const [rejectReason, setRejectReason] = useState('');
    const [showRejectInput, setShowRejectInput] = useState(false);
    const [actionError, setActionError] = useState('');
    const [actionSuccess, setActionSuccess] = useState('');

    const role = user?.role || 'user';
    const isMP = role === 'mp' || role === 'admin' || role === 'super_admin';

    const fetchResolution = async () => {
        try {
            const data = await apiGet(`/api/cases/${caseItem.id}/resolution`);
            setResolution(data.resolution);
            setMonthlySent(data.monthly_sent || 0);
            if (data.resolution) {
                setDraftText(data.resolution.message_body || '');
            }
        } catch (err) {
            console.error('Resolution fetch failed:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchResolution();
    }, [caseItem.id]);

    const handleOpenDraft = () => {
        setIsDirty(false);
        setActionError('');
        setActionSuccess('');
        setShowDraftModal(true);
    };

    const handleSaveDraft = async () => {
        setSaving(true);
        setActionError('');
        try {
            await apiPost(`/api/cases/${caseItem.id}/resolution`, { message_body: draftText });
            await fetchResolution();
            setIsDirty(false);
            setActionSuccess('Draft saved.');
            setTimeout(() => setActionSuccess(''), 3000);
        } catch (err) {
            setActionError(err.message || 'Failed to save draft');
        } finally {
            setSaving(false);
        }
    };

    const handleSubmitForApproval = async () => {
        setSubmitting(true);
        setActionError('');
        try {
            // Save current text first
            await apiPost(`/api/cases/${caseItem.id}/resolution`, { message_body: draftText });
            await apiPost(`/api/cases/${caseItem.id}/resolution/submit`, {});
            await fetchResolution();
            setShowDraftModal(false);
            setActionSuccess('Submitted for MP approval.');
            setTimeout(() => setActionSuccess(''), 4000);
        } catch (err) {
            setActionError(err.message || 'Failed to submit');
        } finally {
            setSubmitting(false);
        }
    };

    const handleApprove = async () => {
        setApproving(true);
        setActionError('');
        try {
            await apiPost(`/api/cases/${caseItem.id}/resolution/approve`, {});
            await fetchResolution();
            setActionSuccess('Approved. You can now send the message.');
            setTimeout(() => setActionSuccess(''), 4000);
        } catch (err) {
            setActionError(err.message || 'Failed to approve');
        } finally {
            setApproving(false);
        }
    };

    const handleReject = async () => {
        setRejecting(true);
        setActionError('');
        try {
            await apiPost(`/api/cases/${caseItem.id}/resolution/reject`, { reason: rejectReason });
            await fetchResolution();
            setShowRejectInput(false);
            setRejectReason('');
            setActionSuccess('Sent back to staff for revision.');
            setTimeout(() => setActionSuccess(''), 4000);
        } catch (err) {
            setActionError(err.message || 'Failed to reject');
        } finally {
            setRejecting(false);
        }
    };

    const handleSend = async () => {
        setSending(true);
        setActionError('');
        try {
            await apiPost(`/api/cases/${caseItem.id}/resolution/send`, {});
            await fetchResolution();
            setActionSuccess('Message sent to constituent successfully.');
            setTimeout(() => setActionSuccess(''), 5000);
            if (onResolutionSent) onResolutionSent(caseItem.id);
        } catch (err) {
            setActionError(err.message || 'Failed to send message');
        } finally {
            setSending(false);
        }
    };

    const rs = resolution?.status;
    const StatusInfo = rs ? RESOLUTION_STATUS_LABELS[rs] : null;

    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between">
                <div className="text-xs text-muted-foreground uppercase font-medium flex items-center gap-1.5">
                    <MessageSquare className="h-3.5 w-3.5" />
                    Resolution Message
                </div>
                <span className="text-xs text-muted-foreground">
                    {monthlySent} / {monthlyLimit.toLocaleString()} msgs this month
                </span>
            </div>

            {loading ? (
                <div className="flex items-center gap-2 py-2">
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                    <span className="text-xs text-muted-foreground">Loading…</span>
                </div>
            ) : (
                <>
                    {resolution && StatusInfo && (
                        <div className="border rounded-lg p-3 space-y-2">
                            <div className="flex items-center gap-2">
                                <Badge variant="secondary" className={cn(StatusInfo.color, 'gap-1 text-xs')}>
                                    <StatusInfo.icon className="h-3 w-3" />
                                    {StatusInfo.label}
                                </Badge>
                                <span className="text-xs text-muted-foreground">
                                    by {resolution.drafted_by}
                                    {resolution.approved_by && ` · approved by ${resolution.approved_by}`}
                                </span>
                            </div>
                            <div className="bg-muted/40 rounded p-3 text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                                {resolution.message_body}
                            </div>
                            {resolution.rejection_reason && (
                                <div className="text-xs text-red-600 bg-red-50 rounded p-2">
                                    Rejection note: {resolution.rejection_reason}
                                </div>
                            )}
                        </div>
                    )}

                    {actionSuccess && (
                        <div className="text-xs text-green-700 bg-green-50 border border-green-200 rounded p-2 flex items-center gap-1.5">
                            <CheckCircle2 className="h-3.5 w-3.5" /> {actionSuccess}
                        </div>
                    )}
                    {actionError && (
                        <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
                            {actionError}
                        </div>
                    )}

                    {/* Action buttons based on current state */}
                    <div className="flex flex-wrap gap-2">
                        {/* Draft / Edit */}
                        {(!rs || rs === 'draft' || rs === 'rejected' || rs === 'failed') && (
                            <Button variant="outline" size="sm" onClick={handleOpenDraft} className="gap-1.5">
                                <FileText className="h-3.5 w-3.5" />
                                {resolution ? 'Edit Draft' : 'Draft Resolution'}
                            </Button>
                        )}

                        {/* MP: Approve pending */}
                        {isMP && rs === 'pending_approval' && (
                            <>
                                <Button
                                    size="sm"
                                    onClick={handleApprove}
                                    disabled={approving}
                                    className="gap-1.5 bg-green-600 hover:bg-green-700 text-white"
                                >
                                    {approving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                                    Approve
                                </Button>
                                {!showRejectInput ? (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => setShowRejectInput(true)}
                                        className="gap-1.5 text-red-600 border-red-200 hover:bg-red-50"
                                    >
                                        <XCircle className="h-3.5 w-3.5" />
                                        Reject
                                    </Button>
                                ) : (
                                    <div className="flex items-center gap-2 w-full">
                                        <input
                                            className="flex-1 text-xs border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring"
                                            placeholder="Reason (optional)"
                                            value={rejectReason}
                                            onChange={e => setRejectReason(e.target.value)}
                                        />
                                        <Button
                                            size="sm"
                                            variant="destructive"
                                            onClick={handleReject}
                                            disabled={rejecting}
                                        >
                                            {rejecting ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Send Back'}
                                        </Button>
                                        <Button size="sm" variant="ghost" onClick={() => setShowRejectInput(false)}>
                                            Cancel
                                        </Button>
                                    </div>
                                )}
                            </>
                        )}

                        {/* MP: Send approved message */}
                        {isMP && rs === 'approved' && monthlySent < monthlyLimit && (
                            <Button
                                size="sm"
                                onClick={handleSend}
                                disabled={sending}
                                style={{ background: color }}
                                className="gap-1.5 text-white hover:opacity-90"
                            >
                                {sending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                                {sending ? 'Sending…' : 'Send to Constituent'}
                            </Button>
                        )}

                        {isMP && rs === 'approved' && monthlySent >= monthlyLimit && (
                            <span className="text-xs text-red-600">Monthly limit reached</span>
                        )}
                    </div>
                </>
            )}

            {/* Draft / Edit Modal */}
            <Dialog open={showDraftModal} onOpenChange={setShowDraftModal}>
                <DialogContent className="max-w-xl">
                    <DialogHeader>
                        <DialogTitle>Draft Resolution Message</DialogTitle>
                        <DialogDescription>
                            This message will be sent to the constituent via WhatsApp.
                            You must edit the text before submitting for approval.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-2">
                        {/* Constituent info */}
                        <div className="bg-muted/50 rounded-lg p-3 text-xs text-muted-foreground space-y-1">
                            <div><span className="font-medium text-foreground">To:</span> {caseItem.user_phone}</div>
                            <div><span className="font-medium text-foreground">Re:</span> {caseItem.category} — Case #{caseItem.id}</div>
                        </div>

                        {/* Message textarea */}
                        <div className="space-y-1.5">
                            <Label className="text-xs text-muted-foreground uppercase font-medium">
                                Message to Constituent
                                {!isDirty && (
                                    <span className="ml-2 text-amber-600 normal-case font-normal">
                                        (edit the message to enable submission)
                                    </span>
                                )}
                            </Label>
                            <Textarea
                                value={draftText}
                                onChange={e => { setDraftText(e.target.value); setIsDirty(true); }}
                                placeholder="Write the resolution message that will be sent to the constituent…"
                                className="min-h-[140px] text-sm"
                            />
                            <div className="flex justify-between text-xs text-muted-foreground">
                                <span>{draftText.length} characters</span>
                                <span>{monthlySent} / {monthlyLimit.toLocaleString()} messages used this month</span>
                            </div>
                        </div>

                        {/* Preview box */}
                        {draftText.trim() && (
                            <div className="space-y-1.5">
                                <div className="text-xs text-muted-foreground uppercase font-medium">Preview — What the constituent will receive</div>
                                <div className="border-2 border-dashed border-primary/20 rounded-lg p-4 bg-primary/5 text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                                    {draftText}
                                </div>
                            </div>
                        )}

                        {actionError && (
                            <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
                                {actionError}
                            </div>
                        )}
                    </div>

                    <DialogFooter className="gap-2 flex-wrap">
                        <Button variant="outline" size="sm" onClick={() => setShowDraftModal(false)}>
                            Cancel
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleSaveDraft}
                            disabled={saving || !draftText.trim()}
                        >
                            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : null}
                            Save Draft
                        </Button>
                        {/* Staff submits for approval; MP can directly approve-on-submit */}
                        {isMP ? (
                            <Button
                                size="sm"
                                onClick={handleSubmitForApproval}
                                disabled={submitting || !isDirty || !draftText.trim()}
                                style={{ background: isDirty && draftText.trim() ? color : undefined }}
                                className="gap-1.5 text-white hover:opacity-90"
                            >
                                {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                                Submit & Approve
                            </Button>
                        ) : (
                            <Button
                                size="sm"
                                onClick={handleSubmitForApproval}
                                disabled={submitting || !isDirty || !draftText.trim()}
                                className="gap-1.5"
                            >
                                {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                                Submit for Approval
                            </Button>
                        )}
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}

function CaseModal({ caseItem, color, onClose, onStatusChange }) {
    const { user } = useAuth();
    const [updating, setUpdating] = useState(null);

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
        } catch (err) {
            console.error('Status update failed:', err);
        } finally {
            setUpdating(null);
        }
    };

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

                    {c.notes_for_staff && (
                        <div>
                            <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Staff Notes</div>
                            <div className="bg-amber-50 border border-amber-100 rounded-lg p-4 text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                                {c.notes_for_staff}
                            </div>
                        </div>
                    )}

                    <Separator />

                    {/* Resolution Message Panel */}
                    <ResolutionPanel
                        caseItem={c}
                        color={color}
                        user={user}
                        onResolutionSent={(caseId) => onStatusChange(caseId, 'resolved')}
                    />

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
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={onClose}>Close</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

function BriefcaseInner() {
    const { user } = useAuth();
    const router = useRouter();
    const searchParams = useSearchParams();

    const color = user?.theme_color || '#006a4d';

    const [cases, setCases] = useState([]);
    const [loading, setLoading] = useState(true);
    // Initialise directly from URL so the very first fetch uses the correct filter,
    // avoiding a race where the all-cases response overwrites the filtered one.
    const [statusFilter, setStatusFilter] = useState(() => searchParams.get('status') || 'All');
    const [categoryFilter, setCategoryFilter] = useState(() => searchParams.get('category') || '');
    const [selected, setSelected] = useState(null);
    const [downloading, setDownloading] = useState(false);
    const [contactPhone, setContactPhone] = useState(null);

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
        } catch (err) {
            console.error('Report download failed:', err);
        } finally {
            setDownloading(false);
        }
    }

    // Sync filters when the URL changes (e.g. browser back/forward, or navigating
    // from another page with different params while this page is already mounted).
    useEffect(() => {
        const status = searchParams.get('status') || 'All';
        const cat = searchParams.get('category') || '';
        setStatusFilter(status);
        setCategoryFilter(cat);
    }, [searchParams]);

    // Fetch cases whenever the active filter changes.
    // The cancel flag ensures a slow in-flight response for a previous filter
    // can never overwrite results for the current one.
    useEffect(() => {
        let cancelled = false;

        async function fetchCases() {
            setLoading(true);
            try {
                const params = new URLSearchParams({ page: '1', limit: '100' });

                if (statusFilter === 'other') {
                    params.set('categories', OTHER_CATEGORIES.join(','));
                } else if (statusFilter !== 'All') {
                    params.set('status', statusFilter);
                }

                if (categoryFilter) {
                    params.set('category', categoryFilter);
                }

                const data = await apiGet(`/api/cases?${params}`);
                if (!cancelled) setCases(data.cases || []);
            } catch (err) {
                if (!cancelled) console.error(err);
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        fetchCases();
        return () => { cancelled = true; };
    }, [statusFilter, categoryFilter]);

    // Auto-open a specific case when case_id is present in the URL (e.g. deep-linked from dashboard)
    useEffect(() => {
        const caseId = searchParams.get('case_id');
        if (!caseId || cases.length === 0) return;
        const match = cases.find(c => String(c.id) === caseId);
        if (match) setSelected(match);
    }, [cases, searchParams]);

    function switchTab(key) {
        setStatusFilter(key);
        const url = new URL(window.location.href);
        if (key === 'All') url.searchParams.delete('status');
        else url.searchParams.set('status', key);
        window.history.replaceState({}, '', url.toString());
    }

    function clearCategoryFilter() {
        setCategoryFilter('');
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

                <CardContent className="pt-0">
                    {loading ? (
                        <div className="space-y-3 py-6">
                            {[1, 2, 3, 4, 5].map(i => (
                                <div key={i} className="flex items-center gap-4">
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
                                {statusFilter !== 'All' ? ` with status "${statusFilter}"` : ''}.
                            </p>
                        </div>
                    ) : (
                        <div className="overflow-x-auto -mx-6">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="w-16 pl-6">#</TableHead>
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
                                            <TableCell className="pl-6 font-mono text-xs text-muted-foreground">
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
            </Card>

            <CaseModal
                caseItem={selected}
                color={color}
                onClose={() => setSelected(null)}
                onStatusChange={handleStatusChange}
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
