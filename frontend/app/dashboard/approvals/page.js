'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPost } from '@/lib/api';
import { useRouter } from 'next/navigation';
import {
    Loader2, CheckCircle2, XCircle, Send, MessageSquare,
    Clock, AlertTriangle, User
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';

export default function ApprovalsPage() {
    const { user } = useAuth();
    const router = useRouter();
    const color = user?.theme_color || '#006a4d';

    const [items, setItems] = useState([]);
    const [monthlySent, setMonthlySent] = useState(0);
    const [monthlyLimit, setMonthlyLimit] = useState(5000);
    const [loading, setLoading] = useState(true);
    const [actionStates, setActionStates] = useState({}); // {id: 'approving'|'sending'|'rejecting'}
    const [rejectInputs, setRejectInputs] = useState({});   // {id: string}
    const [showRejectFor, setShowRejectFor] = useState(null);
    const [errors, setErrors] = useState({});
    const [successes, setSuccesses] = useState({});

    const role = user?.role || 'user';
    const isMP = role === 'mp' || role === 'admin' || role === 'super_admin';

    const fetchQueue = async () => {
        try {
            const data = await apiGet('/api/resolutions/pending');
            setItems(data.items || []);
            setMonthlySent(data.monthly_sent || 0);
            setMonthlyLimit(data.monthly_limit || 5000);
        } catch (err) {
            console.error('Failed to load approval queue:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (!isMP) {
            router.replace('/dashboard');
            return;
        }
        fetchQueue();
    }, [isMP]);

    const setAction = (id, state) =>
        setActionStates(prev => ({ ...prev, [id]: state }));

    const setError = (id, msg) => {
        setErrors(prev => ({ ...prev, [id]: msg }));
        setTimeout(() => setErrors(prev => { const n = { ...prev }; delete n[id]; return n; }), 5000);
    };

    const setSuccess = (id, msg) => {
        setSuccesses(prev => ({ ...prev, [id]: msg }));
        setTimeout(() => setSuccesses(prev => { const n = { ...prev }; delete n[id]; return n; }), 5000);
    };

    const handleApprove = async (item) => {
        setAction(item.id, 'approving');
        setErrors(prev => { const n = { ...prev }; delete n[item.id]; return n; });
        try {
            await apiPost(`/api/cases/${item.case_id}/resolution/approve`, {});
            setSuccess(item.id, 'Approved. Ready to send.');
            await fetchQueue();
        } catch (err) {
            setError(item.id, err.message || 'Approval failed');
        } finally {
            setAction(item.id, null);
        }
    };

    const handleReject = async (item) => {
        setAction(item.id, 'rejecting');
        try {
            await apiPost(`/api/cases/${item.case_id}/resolution/reject`, {
                reason: rejectInputs[item.id] || '',
            });
            setSuccess(item.id, 'Sent back to staff for revision.');
            setShowRejectFor(null);
            setRejectInputs(prev => { const n = { ...prev }; delete n[item.id]; return n; });
            await fetchQueue();
        } catch (err) {
            setError(item.id, err.message || 'Rejection failed');
        } finally {
            setAction(item.id, null);
        }
    };

    const handleSend = async (item) => {
        setAction(item.id, 'sending');
        setErrors(prev => { const n = { ...prev }; delete n[item.id]; return n; });
        try {
            await apiPost(`/api/cases/${item.case_id}/resolution/send`, {});
            setSuccess(item.id, 'Message sent to constituent.');
            await fetchQueue();
        } catch (err) {
            setError(item.id, err.message || 'Send failed');
        } finally {
            setAction(item.id, null);
        }
    };

    const pendingItems = items.filter(i => i.status === 'pending_approval');
    const approvedItems = items.filter(i => i.status === 'approved');

    if (!isMP) return null;

    return (
        <div className="space-y-6">
            <div className="flex items-start justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-foreground">Resolution Approvals</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Review and approve staff-drafted messages before they reach constituents
                    </p>
                </div>
                <div className="text-right">
                    <div className="text-2xl font-bold text-foreground">{monthlySent.toLocaleString()}</div>
                    <div className="text-xs text-muted-foreground">of {monthlyLimit.toLocaleString()} messages sent this month</div>
                    <div className="mt-1 h-1.5 w-32 bg-secondary rounded-full overflow-hidden">
                        <div
                            className={cn(
                                "h-full rounded-full transition-all",
                                monthlySent / monthlyLimit >= 0.9 ? "bg-red-500" :
                                monthlySent / monthlyLimit >= 0.7 ? "bg-amber-500" : "bg-primary"
                            )}
                            style={{ width: `${Math.min((monthlySent / monthlyLimit) * 100, 100)}%` }}
                        />
                    </div>
                </div>
            </div>

            {loading ? (
                <div className="flex items-center justify-center py-20 gap-3">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">Loading queue…</span>
                </div>
            ) : items.length === 0 ? (
                <Card>
                    <CardContent className="flex flex-col items-center justify-center py-16 text-center gap-3">
                        <CheckCircle2 className="h-12 w-12 text-emerald-400" />
                        <div>
                            <p className="font-semibold text-foreground">All clear</p>
                            <p className="text-sm text-muted-foreground mt-1">No resolution messages are waiting for your review.</p>
                        </div>
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-6">
                    {/* Pending Approval Section */}
                    {pendingItems.length > 0 && (
                        <div className="space-y-3">
                            <div className="flex items-center gap-2">
                                <Clock className="h-4 w-4 text-amber-500" />
                                <h2 className="font-semibold text-foreground">Awaiting Your Approval ({pendingItems.length})</h2>
                            </div>
                            {pendingItems.map(item => (
                                <ResolutionCard
                                    key={item.id}
                                    item={item}
                                    color={color}
                                    actionState={actionStates[item.id]}
                                    error={errors[item.id]}
                                    success={successes[item.id]}
                                    showReject={showRejectFor === item.id}
                                    rejectReason={rejectInputs[item.id] || ''}
                                    onRejectReasonChange={v => setRejectInputs(prev => ({ ...prev, [item.id]: v }))}
                                    onApprove={() => handleApprove(item)}
                                    onShowReject={() => setShowRejectFor(item.id)}
                                    onReject={() => handleReject(item)}
                                    onCancelReject={() => setShowRejectFor(null)}
                                    onSend={null}
                                    monthlySent={monthlySent}
                                    monthlyLimit={monthlyLimit}
                                />
                            ))}
                        </div>
                    )}

                    {/* Approved — Ready to Send */}
                    {approvedItems.length > 0 && (
                        <div className="space-y-3">
                            <div className="flex items-center gap-2">
                                <CheckCircle2 className="h-4 w-4 text-green-600" />
                                <h2 className="font-semibold text-foreground">Approved — Ready to Send ({approvedItems.length})</h2>
                            </div>
                            {approvedItems.map(item => (
                                <ResolutionCard
                                    key={item.id}
                                    item={item}
                                    color={color}
                                    actionState={actionStates[item.id]}
                                    error={errors[item.id]}
                                    success={successes[item.id]}
                                    showReject={false}
                                    rejectReason=""
                                    onRejectReasonChange={() => {}}
                                    onApprove={null}
                                    onShowReject={null}
                                    onReject={null}
                                    onCancelReject={null}
                                    onSend={() => handleSend(item)}
                                    monthlySent={monthlySent}
                                    monthlyLimit={monthlyLimit}
                                />
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

function ResolutionCard({
    item, color,
    actionState, error, success,
    showReject, rejectReason, onRejectReasonChange,
    onApprove, onShowReject, onReject, onCancelReject,
    onSend, monthlySent, monthlyLimit,
}) {
    const isPending = item.status === 'pending_approval';
    const isApproved = item.status === 'approved';
    const atLimit = monthlySent >= monthlyLimit;

    return (
        <Card className={cn(
            "border-l-4",
            isPending && "border-l-amber-400",
            isApproved && "border-l-green-500",
        )}>
            <CardContent className="pt-5 space-y-4">
                {/* Header */}
                <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div>
                        <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs font-mono text-muted-foreground">Case #{item.case_id}</span>
                            <Badge variant="secondary" className="text-xs">{item.category || 'General'}</Badge>
                            {isPending && (
                                <Badge variant="secondary" className="bg-amber-100 text-amber-700 text-xs gap-1">
                                    <Clock className="h-3 w-3" /> Awaiting Approval
                                </Badge>
                            )}
                            {isApproved && (
                                <Badge variant="secondary" className="bg-green-100 text-green-700 text-xs gap-1">
                                    <CheckCircle2 className="h-3 w-3" /> Approved
                                </Badge>
                            )}
                        </div>
                        <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                            <User className="h-3 w-3" />
                            <span>Drafted by <span className="font-medium text-foreground">{item.drafted_by}</span></span>
                            {item.approved_by && (
                                <span>· Approved by <span className="font-medium text-foreground">{item.approved_by}</span></span>
                            )}
                        </div>
                    </div>
                    <div className="text-right text-xs text-muted-foreground">
                        <div className="font-mono">{item.user_phone}</div>
                        {item.created_at && (
                            <div>{new Date(item.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</div>
                        )}
                    </div>
                </div>

                {/* Original complaint */}
                <div className="space-y-1">
                    <div className="text-xs text-muted-foreground uppercase font-medium">Original Grievance</div>
                    <div className="bg-muted/40 rounded-lg p-3 text-sm text-muted-foreground italic leading-relaxed line-clamp-3">
                        {item.raw_message || '—'}
                    </div>
                </div>

                <Separator />

                {/* Resolution message */}
                <div className="space-y-1">
                    <div className="text-xs text-muted-foreground uppercase font-medium flex items-center gap-1.5">
                        <MessageSquare className="h-3.5 w-3.5" />
                        Message to be Sent to Constituent
                    </div>
                    <div className="border-2 border-dashed border-primary/20 rounded-lg p-4 bg-primary/5 text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                        {item.message_body}
                    </div>
                </div>

                {/* Feedback */}
                {error && (
                    <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
                        {error}
                    </div>
                )}
                {success && (
                    <div className="text-xs text-green-700 bg-green-50 border border-green-200 rounded p-2 flex items-center gap-1.5">
                        <CheckCircle2 className="h-3.5 w-3.5" /> {success}
                    </div>
                )}

                {/* Actions */}
                <div className="flex flex-wrap gap-2 items-center">
                    {/* Pending: Approve / Reject */}
                    {isPending && onApprove && (
                        <Button
                            size="sm"
                            onClick={onApprove}
                            disabled={!!actionState}
                            className="gap-1.5 bg-green-600 hover:bg-green-700 text-white"
                        >
                            {actionState === 'approving'
                                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                : <CheckCircle2 className="h-3.5 w-3.5" />}
                            Approve
                        </Button>
                    )}

                    {isPending && !showReject && onShowReject && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={onShowReject}
                            disabled={!!actionState}
                            className="gap-1.5 text-red-600 border-red-200 hover:bg-red-50"
                        >
                            <XCircle className="h-3.5 w-3.5" />
                            Reject
                        </Button>
                    )}

                    {isPending && showReject && (
                        <div className="flex items-center gap-2 w-full flex-wrap">
                            <input
                                className="flex-1 min-w-[180px] text-xs border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring"
                                placeholder="Reason for rejection (optional)"
                                value={rejectReason}
                                onChange={e => onRejectReasonChange(e.target.value)}
                            />
                            <Button
                                size="sm"
                                variant="destructive"
                                onClick={onReject}
                                disabled={actionState === 'rejecting'}
                                className="gap-1"
                            >
                                {actionState === 'rejecting' ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                                Send Back to Staff
                            </Button>
                            <Button size="sm" variant="ghost" onClick={onCancelReject}>Cancel</Button>
                        </div>
                    )}

                    {/* Approved: Send */}
                    {isApproved && onSend && (
                        atLimit ? (
                            <span className="text-xs text-red-600 flex items-center gap-1">
                                <AlertTriangle className="h-3.5 w-3.5" /> Monthly limit reached
                            </span>
                        ) : (
                            <Button
                                size="sm"
                                onClick={onSend}
                                disabled={!!actionState}
                                style={{ background: color }}
                                className="gap-1.5 text-white hover:opacity-90"
                            >
                                {actionState === 'sending'
                                    ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                    : <Send className="h-3.5 w-3.5" />}
                                {actionState === 'sending' ? 'Sending…' : 'Send to Constituent'}
                            </Button>
                        )
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
