'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost, apiPatch, apiDelete } from '@/lib/api';
import { useToast } from '@/components/ui/toast';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import {
    Search,
    MessageSquare,
    MapPin,
    Phone,
    Clock,
    ChevronLeft,
    ChevronRight,
    AlertTriangle,
    CheckCircle2,
    X,
    Filter,
    Loader2,
    Send,
    Mail,
    Shield,
    Trash2,
} from 'lucide-react';

const STATUS_OPTIONS = [
    { value: 'new', label: 'New', color: 'status-new' },
    { value: 'in_progress', label: 'In Progress', color: 'status-in_progress' },
    { value: 'resolved', label: 'Resolved', color: 'status-resolved' },
    { value: 'escalated', label: 'Escalated', color: 'status-escalated' },
    { value: 'closed', label: 'Closed', color: 'status-closed' },
];

const CATEGORY_OPTIONS = [
    'External Affairs', 'Railways', 'Infrastructure', 'Telecom',
    'Postal Services', 'Education (Central)', 'Banking & Finance',
    'Labor & Employment', 'Law & Order', 'Energy',
    'Infrastructure (State)', 'Food Supply', 'Transport',
    'Revenue & Land', 'Sanitation', 'Water', 'Civic Amenities',
    'Public Health', 'Civic Admin', 'Private/Legal',
];

function CaseCard({ caseItem, onSelect, selected }) {
    const statusObj = STATUS_OPTIONS.find(s => s.value === caseItem.status) || STATUS_OPTIONS[0];
    const timeAgo = (dateStr) => {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        const now = new Date();
        const diffH = Math.floor((now - d) / 3600000);
        if (diffH < 1) return 'just now';
        if (diffH < 24) return `${diffH}h ago`;
        const diffD = Math.floor(diffH / 24);
        if (diffD < 30) return `${diffD}d ago`;
        return d.toLocaleDateString();
    };

    return (
        <div
            className={`p-4 border-b border-border cursor-pointer transition-colors hover:bg-accent/50 ${
                selected ? 'bg-primary/5 border-l-2 border-l-primary' : ''
            }`}
            onClick={() => onSelect(caseItem)}
        >
            <div className="flex items-start justify-between gap-2 mb-2">
                <div className="flex items-center gap-2 min-w-0">
                    <Phone className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <span className="text-sm font-medium text-foreground truncate">{caseItem.user_phone || 'Unknown'}</span>
                </div>
                <Badge variant="outline" className={`shrink-0 text-[10px] ${statusObj.color}`}>
                    {statusObj.label}
                </Badge>
            </div>
            <p className="text-sm text-foreground line-clamp-2 mb-2">{caseItem.raw_message}</p>
            <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                <Badge variant="outline" className="text-[10px] px-1.5 py-0">{caseItem.category || 'General'}</Badge>
                {caseItem.location && (
                    <span className="flex items-center gap-1">
                        <MapPin className="h-3 w-3" />{caseItem.location}
                    </span>
                )}
                <span className="flex items-center gap-1 ml-auto">
                    <Clock className="h-3 w-3" />{timeAgo(caseItem.created_at)}
                </span>
            </div>
        </div>
    );
}

function CaseDetail({ caseItem, onStatusChange, updating, onRefresh }) {
    const toast = useToast();
    const [notes, setNotes] = useState('');
    const [response, setResponse] = useState('');
    const [savingNotes, setSavingNotes] = useState(false);
    const [notifying, setNotifying] = useState(false);
    const [activities, setActivities] = useState([]);
    const [loadingActivity, setLoadingActivity] = useState(false);

    // Escalation state
    const [showEscalation, setShowEscalation] = useState(false);
    const [officers, setOfficers] = useState([]);
    const [selectedOfficer, setSelectedOfficer] = useState('');
    const [letterContent, setLetterContent] = useState('');
    const [escalations, setEscalations] = useState([]);
    const [submitting, setSubmitting] = useState(false);
    const [sendingEmail, setSendingEmail] = useState(null);

    useEffect(() => {
        if (!caseItem) return;
        setNotes(caseItem.notes_for_staff || '');
        setResponse(caseItem.response_to_citizen || '');
        setShowEscalation(false);

        setLoadingActivity(true);
        apiGet(`/api/cases/${caseItem.id}/activity`)
            .then(d => setActivities(d.activities || []))
            .catch(() => setActivities([]))
            .finally(() => setLoadingActivity(false));
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

    if (!caseItem) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground py-20">
                <MessageSquare className="h-12 w-12 mb-3 opacity-30" />
                <p className="text-sm">Select a message to view details</p>
            </div>
        );
    }

    const saveNotes = async () => {
        setSavingNotes(true);
        try {
            await apiPatch(`/api/cases/${caseItem.id}`, {
                notes_for_staff: notes || null,
                response_to_citizen: response || null,
            });
            toast.success('Notes saved successfully');
        } catch (err) {
            toast.error('Failed to save notes');
        } finally {
            setSavingNotes(false);
        }
    };

    const handleNotify = async () => {
        setNotifying(true);
        try {
            await apiPost(`/api/cases/${caseItem.id}/notify`);
            toast.success('WhatsApp update sent to citizen');
        } catch (err) {
            toast.error('Failed to send WhatsApp notification');
        } finally {
            setNotifying(false);
        }
    };

    const handleDelete = async () => {
        if (!window.confirm('Are you sure you want to delete this case?')) return;
        try {
            await apiDelete(`/api/cases/${caseItem.id}`);
            toast.success('Case deleted');
            if (onRefresh) onRefresh();
        } catch (err) {
            toast.error('Failed to delete case');
        }
    };

    const handleEscalate = async () => {
        if (!selectedOfficer) {
            toast.error('Please select an officer');
            return;
        }
        setSubmitting(true);
        try {
            const cat = caseItem.category || 'this matter';
            const ref = caseItem.case_ref || `#${caseItem.id}`;
            const loc = caseItem.location || '';
            const msg = caseItem.raw_message || '';
            const letter = letterContent || `Subject: Escalation of Citizen Grievance ${ref}\n\nRespected Sir/Madam,\n\nI am writing about a citizen grievance (Ref: ${ref}) related to ${cat}${loc ? ` in ${loc}` : ''}.\n\nCitizen's complaint:\n"${msg.slice(0, 300)}"\n\nKindly take necessary action at the earliest.\n\nRegards,\nOffice of the Representative`;

            await apiPost('/api/escalations', {
                case_id: caseItem.id,
                officer_id: parseInt(selectedOfficer),
                letter_content: letter,
                deadline: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0],
            });
            toast.success('Case escalated to officer');
            await loadEscalationData();
            setSelectedOfficer('');
            setLetterContent('');
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
            await loadEscalationData();
        } catch (err) {
            toast.error('Failed to send email');
        } finally {
            setSendingEmail(null);
        }
    };

    return (
        <div className="p-5 space-y-5 overflow-y-auto">
            {/* Header */}
            <div className="flex items-start justify-between">
                <div>
                    <h3 className="font-semibold text-foreground">
                        Case {caseItem.case_ref || `#${caseItem.id}`}
                    </h3>
                    <p className="text-sm text-muted-foreground mt-0.5">{caseItem.user_phone}</p>
                </div>
                <Select
                    value={caseItem.status}
                    onValueChange={(val) => onStatusChange(caseItem.id, val)}
                    disabled={updating}
                >
                    <SelectTrigger className="w-36 h-8 text-xs">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        {STATUS_OPTIONS.map(s => (
                            <SelectItem key={s.value} value={s.value} className="text-xs">{s.label}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {/* Message */}
            <div className="bg-secondary/50 rounded-lg p-4">
                <p className="text-sm text-foreground whitespace-pre-wrap">{caseItem.raw_message}</p>
            </div>

            {/* Meta Grid */}
            <div className="grid grid-cols-2 gap-3">
                <div className="bg-secondary/30 rounded-lg p-3">
                    <p className="text-[11px] text-muted-foreground mb-1">Category</p>
                    <p className="text-sm font-medium">{caseItem.category || 'General'}</p>
                </div>
                <div className="bg-secondary/30 rounded-lg p-3">
                    <p className="text-[11px] text-muted-foreground mb-1">Location</p>
                    <p className="text-sm font-medium">{caseItem.location || 'Not specified'}</p>
                </div>
                <div className="bg-secondary/30 rounded-lg p-3">
                    <p className="text-[11px] text-muted-foreground mb-1">Ward / Area</p>
                    <p className="text-sm font-medium">{caseItem.ward || caseItem.assembly || '—'}</p>
                </div>
                <div className="bg-secondary/30 rounded-lg p-3">
                    <p className="text-[11px] text-muted-foreground mb-1">Received</p>
                    <p className="text-sm font-medium">
                        {caseItem.created_at ? new Date(caseItem.created_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : '—'}
                    </p>
                </div>
            </div>

            {/* Critical Flag */}
            {caseItem.is_critical && (
                <div className="flex items-center gap-2 p-3 bg-destructive/10 border border-destructive/20 rounded-lg">
                    <AlertTriangle className="h-4 w-4 text-destructive" />
                    <span className="text-sm font-medium text-destructive">Flagged as Critical / Emergency</span>
                </div>
            )}

            <Separator />

            {/* Notes & Response */}
            <div className="space-y-3">
                <div>
                    <p className="text-[11px] text-muted-foreground uppercase font-medium mb-1.5">Notes for Staff</p>
                    <Textarea
                        value={notes}
                        onChange={e => setNotes(e.target.value)}
                        placeholder="Internal notes..."
                        className="min-h-[60px] text-sm"
                    />
                </div>
                <div>
                    <p className="text-[11px] text-muted-foreground uppercase font-medium mb-1.5">Response to Citizen</p>
                    <Textarea
                        value={response}
                        onChange={e => setResponse(e.target.value)}
                        placeholder="Response message..."
                        className="min-h-[60px] text-sm"
                    />
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                    <Button size="sm" onClick={saveNotes} disabled={savingNotes}>
                        {savingNotes ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : null}
                        Save Notes
                    </Button>
                    <Button
                        size="sm"
                        variant="outline"
                        className="border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                        disabled={notifying || !caseItem.user_phone}
                        onClick={handleNotify}
                    >
                        {notifying ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Send className="h-3 w-3 mr-1" />}
                        Send Update via WhatsApp
                    </Button>
                </div>
            </div>

            <Separator />

            {/* Action Buttons */}
            <div className="flex items-center gap-2 flex-wrap">
                <Button
                    size="sm"
                    variant="outline"
                    className="border-amber-200 text-amber-700 hover:bg-amber-50"
                    onClick={() => setShowEscalation(!showEscalation)}
                >
                    <Shield className="h-3 w-3 mr-1" />
                    {showEscalation ? 'Hide Escalation' : 'Escalate to Officer'}
                </Button>
                <Button
                    size="sm"
                    variant="outline"
                    className="border-red-200 text-red-600 hover:bg-red-50 ml-auto"
                    onClick={handleDelete}
                >
                    <Trash2 className="h-3 w-3 mr-1" />
                    Delete
                </Button>
            </div>

            {/* Escalation Panel */}
            {showEscalation && (
                <div className="border border-amber-200 rounded-lg p-4 bg-amber-50/50 space-y-4">
                    <p className="text-xs text-amber-800 uppercase font-semibold">Escalation</p>

                    {officers.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No officers configured. Add officers via the API or admin panel.</p>
                    ) : (
                        <>
                            <select
                                value={selectedOfficer}
                                onChange={e => setSelectedOfficer(e.target.value)}
                                className="w-full border rounded-lg p-2 text-sm bg-white"
                            >
                                <option value="">— Select Officer —</option>
                                {officers.map(o => (
                                    <option key={o.id} value={o.id}>
                                        {o.name} — {o.designation}{o.department ? `, ${o.department}` : ''}
                                    </option>
                                ))}
                            </select>

                            <Textarea
                                value={letterContent}
                                onChange={e => setLetterContent(e.target.value)}
                                placeholder="Escalation letter content (auto-generated on submit if empty)..."
                                className="min-h-[100px] text-sm bg-white"
                            />

                            <Button
                                size="sm"
                                onClick={handleEscalate}
                                disabled={submitting || !selectedOfficer}
                                className="bg-amber-600 hover:bg-amber-700 text-white"
                            >
                                {submitting ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Shield className="h-3 w-3 mr-1" />}
                                Escalate Case
                            </Button>
                        </>
                    )}

                    {/* Escalation history */}
                    {escalations.length > 0 && (
                        <div className="space-y-2 pt-2 border-t border-amber-200">
                            <p className="text-xs text-amber-800 font-medium">Escalation History</p>
                            {escalations.map(esc => (
                                <div key={esc.id} className="bg-white border rounded-lg p-3 space-y-2">
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm font-medium">{esc.officer_name || 'Officer'}</span>
                                        <Badge variant={esc.email_sent ? 'default' : 'outline'} className="text-[10px]">
                                            {esc.email_sent ? '✓ Sent' : 'Not Sent'}
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
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            <Separator />

            {/* Activity Log */}
            <div>
                <p className="text-[11px] text-muted-foreground uppercase font-medium mb-2">Activity Log</p>
                {loadingActivity ? (
                    <div className="flex items-center justify-center py-4">
                        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                    </div>
                ) : activities.length === 0 ? (
                    <p className="text-xs text-muted-foreground">No activity yet</p>
                ) : (
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                        {activities.map(a => (
                            <div key={a.id} className="flex items-start gap-2 text-xs">
                                <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                                <div>
                                    <span className="font-medium">{a.username}</span> {a.action.replace(/_/g, ' ')}
                                    {a.new_value && <span className="text-muted-foreground"> → {a.new_value}</span>}
                                    <div className="text-muted-foreground">{a.created_at ? new Date(a.created_at).toLocaleString('en-IN') : ''}</div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

export default function MessagesPage() {
    const toast = useToast();
    const [cases, setCases] = useState([]);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [totalCases, setTotalCases] = useState(0);
    const [search, setSearch] = useState('');
    const [statusFilter, setStatusFilter] = useState('all');
    const [categoryFilter, setCategoryFilter] = useState('all');
    const [selectedCase, setSelectedCase] = useState(null);
    const [updating, setUpdating] = useState(false);

    const fetchCases = useCallback(async () => {
        setLoading(true);
        try {
            let path = `/api/cases?page=${page}&per_page=20`;
            if (statusFilter && statusFilter !== 'all') path += `&status=${statusFilter}`;
            if (categoryFilter && categoryFilter !== 'all') path += `&category=${encodeURIComponent(categoryFilter)}`;
            if (search) path += `&search=${encodeURIComponent(search)}`;
            const data = await apiGet(path);
            setCases(data.cases || []);
            setTotalPages(data.pages || 1);
            setTotalCases(data.total || 0);
        } catch {
            setCases([]);
            toast.error('Failed to load messages');
        } finally {
            setLoading(false);
        }
    }, [page, statusFilter, categoryFilter, search]);

    useEffect(() => { fetchCases(); }, [fetchCases]);

    const handleStatusChange = async (caseId, newStatus) => {
        setUpdating(true);
        try {
            await apiPatch(`/api/cases/${caseId}/status`, { status: newStatus });
            setCases(prev => prev.map(c => c.id === caseId ? { ...c, status: newStatus } : c));
            if (selectedCase?.id === caseId) {
                setSelectedCase(prev => ({ ...prev, status: newStatus }));
            }
            toast.success(`Status updated to ${newStatus}`);
        } catch {
            toast.error('Failed to update status');
        } finally {
            setUpdating(false);
        }
    };

    const handleSearch = (e) => {
        e.preventDefault();
        setPage(1);
        fetchCases();
    };

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h1 className="text-xl font-bold text-foreground">Messages</h1>
                <Badge variant="outline" className="text-xs">
                    Page {page} of {totalPages} ({totalCases} total)
                </Badge>
            </div>

            {/* Filters */}
            <div className="flex flex-col sm:flex-row gap-3">
                <form onSubmit={handleSearch} className="flex-1 relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search phone, message, location..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="pl-9"
                    />
                </form>
                <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
                    <SelectTrigger className="w-36">
                        <Filter className="h-4 w-4 mr-2" />
                        <SelectValue placeholder="All Status" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Status</SelectItem>
                        {STATUS_OPTIONS.map(s => (
                            <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <Select value={categoryFilter} onValueChange={(v) => { setCategoryFilter(v); setPage(1); }}>
                    <SelectTrigger className="w-44">
                        <SelectValue placeholder="All Categories" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Categories</SelectItem>
                        {CATEGORY_OPTIONS.map(c => (
                            <SelectItem key={c} value={c}>{c}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {/* Split View */}
            <div className="grid lg:grid-cols-5 gap-0 border border-border rounded-lg overflow-hidden bg-card min-h-[600px]">
                {/* List Panel */}
                <div className="lg:col-span-2 border-r border-border overflow-y-auto max-h-[700px]">
                    {loading ? (
                        <div className="p-4 space-y-3">
                            {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-20 w-full" />)}
                        </div>
                    ) : cases.length > 0 ? (
                        <>
                            {cases.map(c => (
                                <CaseCard
                                    key={c.id}
                                    caseItem={c}
                                    onSelect={setSelectedCase}
                                    selected={selectedCase?.id === c.id}
                                />
                            ))}
                            {/* Pagination */}
                            <div className="flex items-center justify-between p-3 border-t border-border">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    disabled={page <= 1}
                                    onClick={() => setPage(p => p - 1)}
                                >
                                    <ChevronLeft className="h-4 w-4" />
                                </Button>
                                <span className="text-xs text-muted-foreground">
                                    Page {page} of {totalPages}
                                </span>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    disabled={page >= totalPages}
                                    onClick={() => setPage(p => p + 1)}
                                >
                                    <ChevronRight className="h-4 w-4" />
                                </Button>
                            </div>
                        </>
                    ) : (
                        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
                            <MessageSquare className="h-10 w-10 mb-2 opacity-30" />
                            <p className="text-sm">No messages found</p>
                        </div>
                    )}
                </div>

                {/* Detail Panel */}
                <div className="lg:col-span-3 overflow-y-auto max-h-[700px]">
                    <CaseDetail
                        caseItem={selectedCase}
                        onStatusChange={handleStatusChange}
                        updating={updating}
                        onRefresh={() => { setSelectedCase(null); fetchCases(); }}
                    />
                </div>
            </div>
        </div>
    );
}
