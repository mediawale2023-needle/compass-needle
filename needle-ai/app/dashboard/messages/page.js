'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost, apiPatch, apiDelete } from '@/lib/api';
import { useToast } from '@/components/ui/toast';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import {
    Search,
    MessageSquare,
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
    Download,
    Clock,
    ExternalLink,
} from 'lucide-react';

// ─── Constants ────────────────────────────────────────────────────

const TABS = [
    { key: 'All', label: 'All Cases' },
    { key: 'new', label: 'New' },
    { key: 'in_progress', label: 'In Progress' },
    { key: 'escalated', label: '📧 Escalated' },
    { key: 'resolved', label: 'Resolved' },
    { key: 'closed', label: 'Closed' },
    { key: 'spam', label: '🚫 Spam' },
];

const STATUS_OPTIONS = [
    { value: 'new', label: 'New', className: 'bg-blue-100 text-blue-700' },
    { value: 'in_progress', label: 'In Progress', className: 'bg-amber-100 text-amber-700' },
    { value: 'resolved', label: 'Resolved', className: 'bg-green-100 text-green-700' },
    { value: 'escalated', label: 'Escalated', className: 'bg-red-100 text-red-700' },
    { value: 'closed', label: 'Closed', className: 'bg-slate-100 text-slate-600' },
    { value: 'spam', label: 'Spam', className: 'bg-orange-100 text-orange-700' },
];

const CATEGORY_OPTIONS = [
    'External Affairs', 'Railways', 'Infrastructure', 'Telecom',
    'Postal Services', 'Education (Central)', 'Banking & Finance',
    'Labor & Employment', 'Law & Order', 'Energy',
    'Infrastructure (State)', 'Food Supply', 'Transport',
    'Revenue & Land', 'Sanitation', 'Water', 'Civic Amenities',
    'Public Health', 'Civic Admin', 'Private/Legal',
];

function getStatusBadge(status) {
    const opt = STATUS_OPTIONS.find(o => o.value === (status || '').toLowerCase());
    if (opt) return <Badge variant="secondary" className={opt.className}>{opt.label}</Badge>;
    return <Badge variant="secondary">{status}</Badge>;
}

function getRowHighlight(status) {
    const s = (status || '').toLowerCase();
    if (s === 'new' || s === 'escalated') return 'border-l-4 border-l-red-500 bg-red-50/50';
    if (s === 'resolved' || s === 'in_progress') return 'border-l-4 border-l-green-500 bg-green-50/30';
    if (s === 'spam') return 'border-l-4 border-l-orange-400 bg-orange-50/30 opacity-70';
    return '';
}

// ─── Case Modal ───────────────────────────────────────────────────

function CaseModal({ caseItem, onClose, onStatusChange, toast }) {
    const [notes, setNotes] = useState('');
    const [response, setResponse] = useState('');
    const [savingNotes, setSavingNotes] = useState(false);
    const [notifying, setNotifying] = useState(false);
    const [updating, setUpdating] = useState(null);
    const [activities, setActivities] = useState([]);
    const [loadingActivity, setLoadingActivity] = useState(false);

    // Escalation
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

    if (!caseItem) return null;

    const c = caseItem;
    const meta = c.case_metadata || {};
    const createdAt = c.created_at ? new Date(c.created_at) : null;
    const currentStatus = (c.status || 'new').toLowerCase();

    const handleStatusChange = async (newStatus) => {
        setUpdating(newStatus);
        try {
            await apiPatch(`/api/cases/${c.id}/status`, { status: newStatus });
            onStatusChange(c.id, newStatus);
            toast.success(`Case marked as ${newStatus}`);
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
            toast.success('Notes saved');
        } catch {
            toast.error('Failed to save notes');
        } finally {
            setSavingNotes(false);
        }
    };

    const handleNotify = async () => {
        setNotifying(true);
        try {
            await apiPost(`/api/cases/${c.id}/notify`);
            toast.success('WhatsApp update sent to citizen');
        } catch {
            toast.error('Failed to send WhatsApp notification');
        } finally {
            setNotifying(false);
        }
    };

    const handleDelete = async () => {
        if (!window.confirm('Delete this case?')) return;
        try {
            await apiDelete(`/api/cases/${c.id}`);
            toast.success('Case deleted');
            onClose();
        } catch {
            toast.error('Failed to delete case');
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
            const letter = letterContent || `Subject: Escalation of Citizen Grievance ${ref}\n\nRespected Sir/Madam,\n\nCitizen grievance (Ref: ${ref}) related to ${cat}${loc ? ` in ${loc}` : ''}.\n\nComplaint: "${msg.slice(0, 300)}"\n\nKindly take necessary action.\n\nRegards,\nOffice of the Representative`;
            await apiPost('/api/escalations', {
                case_id: c.id, officer_id: parseInt(selectedOfficer),
                letter_content: letter,
                deadline: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0],
            });
            toast.success('Case escalated');
            await loadEscalationData();
            setSelectedOfficer('');
            setLetterContent('');
        } catch (err) {
            toast.error('Failed to escalate: ' + (err.message || 'Unknown'));
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
        } catch {
            toast.error('Failed to send email');
        } finally {
            setSendingEmail(null);
        }
    };

    return (
        <Dialog open={!!caseItem} onOpenChange={onClose}>
            <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
                <DialogHeader className="p-0 -m-6 mb-0">
                    <div className="p-6 text-white rounded-t-xl bg-primary">
                        <DialogDescription className="text-white/80 text-xs uppercase tracking-widest font-semibold mb-1">
                            Grievance · #{c.id}
                        </DialogDescription>
                        <DialogTitle className="text-lg font-bold text-white">
                            {c.category || 'General'}
                        </DialogTitle>
                    </div>
                </DialogHeader>

                <div className="space-y-4 pt-6">
                    {/* Meta Grid */}
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                        {[
                            ['Contact', c.user_phone || '-'],
                            ['Category', c.category || 'General'],
                            ['Status', currentStatus],
                            ['Location', c.location || meta.matched_value || '-'],
                            ['Assembly', c.assembly || meta.assembly_constituency || '-'],
                            ['Date', createdAt ? createdAt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '-'],
                            ['Critical', c.is_critical ? 'Yes' : 'No'],
                        ].map(([label, value]) => (
                            <div key={label} className="border rounded-lg p-3">
                                <div className="text-xs text-muted-foreground uppercase font-medium">{label}</div>
                                <div className="text-sm font-medium text-foreground mt-0.5">{value}</div>
                            </div>
                        ))}
                    </div>

                    {/* Full Message */}
                    <div>
                        <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Full Message</div>
                        <div className="bg-muted/50 border rounded-lg p-4 text-sm text-foreground whitespace-pre-wrap leading-relaxed min-h-[80px]">
                            {c.raw_message || 'No content available.'}
                        </div>
                    </div>

                    <Separator />

                    {/* Status Update */}
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
                                    {updating === opt.value && <Loader2 className="h-3 w-3 animate-spin mr-1" />}
                                    Mark {opt.label}
                                </Button>
                            ))}
                        </div>
                    </div>

                    <Separator />

                    {/* Notes & Response */}
                    <div className="space-y-3">
                        <div>
                            <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Notes for Staff</div>
                            <Textarea value={notes} onChange={e => setNotes(e.target.value)} placeholder="Internal notes..." className="min-h-[60px]" />
                        </div>
                        <div>
                            <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Response to Citizen</div>
                            <Textarea value={response} onChange={e => setResponse(e.target.value)} placeholder="Response message..." className="min-h-[60px]" />
                        </div>
                        <div className="flex items-center gap-2 flex-wrap">
                            <Button size="sm" onClick={saveNotes} disabled={savingNotes}>
                                {savingNotes ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : null}
                                Save Notes
                            </Button>
                            <Button size="sm" variant="outline" className="border-emerald-200 text-emerald-700 hover:bg-emerald-50" disabled={notifying || !c.user_phone} onClick={handleNotify}>
                                {notifying ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Send className="h-3 w-3 mr-1" />}
                                Send Update via WhatsApp
                            </Button>
                        </div>
                    </div>

                    <Separator />

                    {/* Escalation */}
                    <div className="flex gap-2 flex-wrap">
                        <Button size="sm" variant="outline" className="border-amber-300 text-amber-700 hover:bg-amber-50" onClick={() => setShowEscalation(!showEscalation)}>
                            <Shield className="h-3 w-3 mr-1" />
                            {showEscalation ? 'Hide Escalation' : 'Escalate to Officer'}
                        </Button>
                        <Button size="sm" variant="outline" className="border-red-200 text-red-600 hover:bg-red-50 ml-auto" onClick={handleDelete}>
                            <Trash2 className="h-3 w-3 mr-1" /> Delete
                        </Button>
                    </div>

                    {showEscalation && (
                        <div className="border border-amber-200 rounded-lg p-4 bg-amber-50/50 space-y-3">
                            <p className="text-xs text-amber-800 uppercase font-semibold">Escalation</p>
                            {officers.length === 0 ? (
                                <p className="text-sm text-muted-foreground">No officers configured. <a href="/dashboard/officers" className="text-primary underline">Add officers</a> first.</p>
                            ) : (
                                <>
                                    <select value={selectedOfficer} onChange={e => setSelectedOfficer(e.target.value)} className="w-full border rounded-lg p-2 text-sm bg-white">
                                        <option value="">— Select Officer —</option>
                                        {officers.map(o => (
                                            <option key={o.id} value={o.id}>{o.name} — {o.designation}{o.department ? `, ${o.department}` : ''}</option>
                                        ))}
                                    </select>
                                    <Textarea value={letterContent} onChange={e => setLetterContent(e.target.value)} placeholder="Escalation letter (auto-generated if empty)..." className="min-h-[80px] text-sm bg-white" />
                                    <Button size="sm" onClick={handleEscalate} disabled={submitting || !selectedOfficer} className="bg-amber-600 hover:bg-amber-700 text-white">
                                        {submitting ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Shield className="h-3 w-3 mr-1" />}
                                        Escalate Case
                                    </Button>
                                </>
                            )}

                            {escalations.length > 0 && (
                                <div className="space-y-2 pt-2 border-t border-amber-200">
                                    <p className="text-xs text-amber-800 font-medium">History</p>
                                    {escalations.map(esc => (
                                        <div key={esc.id} className="bg-white border rounded-lg p-3 space-y-2">
                                            <div className="flex items-center justify-between">
                                                <span className="text-sm font-medium">{esc.officer_name || 'Officer'}</span>
                                                <Badge variant={esc.email_sent ? 'default' : 'outline'} className="text-[10px]">
                                                    {esc.email_sent ? '✓ Sent' : 'Not Sent'}
                                                </Badge>
                                            </div>
                                            {!esc.email_sent && (
                                                <Button size="sm" variant="outline" className="border-blue-200 text-blue-700 hover:bg-blue-50" disabled={sendingEmail === esc.id} onClick={() => handleSendEmail(esc.id)}>
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
                        <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Activity Log</div>
                        {loadingActivity ? (
                            <div className="flex items-center justify-center py-4"><Loader2 className="h-4 w-4 animate-spin text-muted-foreground" /></div>
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

                <DialogFooter>
                    <Button variant="outline" onClick={onClose}>Close</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

// ─── Main Page ────────────────────────────────────────────────────

export default function MessagesPage() {
    const toast = useToast();
    const [cases, setCases] = useState([]);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [totalCases, setTotalCases] = useState(0);
    const [search, setSearch] = useState('');
    const [statusFilter, setStatusFilter] = useState('All');
    const [categoryFilter, setCategoryFilter] = useState('');
    const [selected, setSelected] = useState(null);
    const [selectedIds, setSelectedIds] = useState(new Set());

    // Escalation tab state
    const [escalations, setEscalations] = useState([]);
    const [loadingEscalations, setLoadingEscalations] = useState(false);
    const [sendingEmail, setSendingEmail] = useState(null);
    const [expandedLetter, setExpandedLetter] = useState(null);
    const isEscalationTab = statusFilter === 'escalated';

    const fetchCases = useCallback(async () => {
        if (statusFilter === 'escalated') return; // handled separately by escalation view
        setLoading(true);
        try {
            const params = new URLSearchParams({ page: String(page), limit: '50' });
            if (statusFilter !== 'All') params.set('status', statusFilter);
            if (categoryFilter) params.set('category', categoryFilter);
            if (search) params.set('search', search);
            const data = await apiGet(`/api/cases?${params}`);
            setCases(data.cases || []);
            setTotalPages(data.pages || 1);
            setTotalCases(data.total || 0);
            setSelectedIds(new Set());
        } catch {
            setCases([]);
            toast.error('Failed to load cases');
        } finally {
            setLoading(false);
        }
    }, [page, statusFilter, categoryFilter, search]);

    const fetchEscalations = useCallback(async () => {
        setLoadingEscalations(true);
        try {
            const data = await apiGet('/api/escalations');
            setEscalations(data.escalations || []);
        } catch {
            setEscalations([]);
            toast.error('Failed to load escalations');
        } finally {
            setLoadingEscalations(false);
        }
    }, []);

    const handleSendEmail = async (escalationId) => {
        setSendingEmail(escalationId);
        try {
            await apiPost(`/api/escalations/${escalationId}/send`);
            toast.success('Email sent to officer');
            await fetchEscalations();
        } catch (err) {
            toast.error('Email failed: ' + (err.message || 'Unknown error'));
        } finally {
            setSendingEmail(null);
        }
    };

    useEffect(() => { fetchCases(); }, [fetchCases]);
    useEffect(() => { if (isEscalationTab) fetchEscalations(); }, [isEscalationTab, fetchEscalations]);

    const switchTab = (key) => {
        setStatusFilter(key);
        setPage(1);
    };

    const handleStatusChange = (caseId, newStatus) => {
        setCases(prev => prev.map(c => c.id === caseId ? { ...c, status: newStatus } : c));
        setSelected(prev => prev && prev.id === caseId ? { ...prev, status: newStatus } : prev);
    };

    const handleSearch = (e) => {
        e.preventDefault();
        setPage(1);
        fetchCases();
    };

    const clearCategoryFilter = () => {
        setCategoryFilter('');
        setPage(1);
    };

    async function bulkStatusChange(newStatus) {
        const ids = [...selectedIds];
        if (ids.length === 0) return;
        try {
            await Promise.all(ids.map(id => apiPatch(`/api/cases/${id}/status`, { status: newStatus })));
            setCases(prev => prev.map(c => ids.includes(c.id) ? { ...c, status: newStatus } : c));
            setSelectedIds(new Set());
            toast.success(`Updated ${ids.length} case(s) to ${newStatus}`);
        } catch {
            toast.error('Bulk update failed');
        }
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-foreground">Grievance Dashboard</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Manage citizen grievances and cases
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <form onSubmit={handleSearch} className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <Input
                            placeholder="Search phone, message..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            className="pl-9 w-56"
                        />
                    </form>
                    <Select value={categoryFilter || '__all__'} onValueChange={(v) => { setCategoryFilter(v === '__all__' ? '' : v); setPage(1); }}>
                        <SelectTrigger className="w-44">
                            <Filter className="h-4 w-4 mr-2" />
                            <SelectValue placeholder="All Categories" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="__all__">All Categories</SelectItem>
                            {CATEGORY_OPTIONS.map(c => (
                                <SelectItem key={c} value={c}>{c}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
            </div>

            {/* Main Card */}
            <Card>
                {/* Tabs */}
                <div className="px-6 pt-4 overflow-x-auto border-b">
                    <Tabs value={statusFilter} onValueChange={switchTab}>
                        <TabsList className="h-auto p-0 bg-transparent gap-6">
                            {TABS.map(t => (
                                <TabsTrigger
                                    key={t.key}
                                    value={t.key}
                                    className={cn(
                                        "px-0 pb-3 rounded-none border-b-2 border-transparent",
                                        "data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none",
                                        "text-sm font-medium text-muted-foreground data-[state=active]:text-foreground"
                                    )}
                                >
                                    {t.label}
                                </TabsTrigger>
                            ))}
                        </TabsList>
                    </Tabs>
                </div>

                {/* Category filter banner */}
                {categoryFilter && (
                    <div className="px-6 py-3 border-b flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">Filtered by category:</span>
                        <Badge variant="default" className="gap-1">
                            {categoryFilter}
                            <button onClick={clearCategoryFilter} className="ml-1 hover:opacity-80"><X className="h-3 w-3" /></button>
                        </Badge>
                        <span className="text-xs text-muted-foreground ml-1">
                            {loading ? '...' : `${cases.length} case${cases.length !== 1 ? 's' : ''}`}
                        </span>
                    </div>
                )}

                {/* Bulk operations */}
                {selectedIds.size > 0 && (
                    <div className="px-6 py-3 border-b bg-primary/5 flex items-center gap-4">
                        <span className="text-sm font-medium">{selectedIds.size} selected</span>
                        <select
                            className="text-sm border rounded px-2 py-1"
                            value=""
                            onChange={(e) => { if (e.target.value) { bulkStatusChange(e.target.value); e.target.value = ''; } }}
                        >
                            <option value="">Bulk Status...</option>
                            {STATUS_OPTIONS.map(s => (
                                <option key={s.value} value={s.value}>{s.label}</option>
                            ))}
                        </select>
                        <Button variant="ghost" size="sm" onClick={() => setSelectedIds(new Set())}>Clear</Button>
                    </div>
                )}

                {/* Table */}
                <CardContent className="pt-0">
                    {isEscalationTab ? (
                        /* ─── Escalation Table ─── */
                        loadingEscalations ? (
                            <div className="space-y-3 py-6">
                                {[1, 2, 3, 4].map(i => (
                                    <div key={i} className="flex items-center gap-4">
                                        <Skeleton className="h-4 w-12" />
                                        <Skeleton className="h-4 w-32" />
                                        <Skeleton className="h-4 w-24" />
                                        <Skeleton className="h-6 w-20" />
                                        <Skeleton className="h-4 w-24" />
                                    </div>
                                ))}
                            </div>
                        ) : escalations.length === 0 ? (
                            <div className="text-center py-16">
                                <Mail className="h-12 w-12 mx-auto text-muted-foreground/30 mb-4" />
                                <p className="text-muted-foreground">No escalations yet</p>
                                <p className="text-xs text-muted-foreground mt-1">Escalate cases to officers from the case detail modal</p>
                            </div>
                        ) : (
                            <div className="overflow-x-auto -mx-6">
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead className="pl-6 w-16">Case #</TableHead>
                                            <TableHead>Officer</TableHead>
                                            <TableHead>Designation</TableHead>
                                            <TableHead>Email Status</TableHead>
                                            <TableHead>Deadline</TableHead>
                                            <TableHead>Escalated By</TableHead>
                                            <TableHead>Date</TableHead>
                                            <TableHead className="w-28">Action</TableHead>
                                            <TableHead className="w-24">Letter</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {escalations.map(esc => (
                                            <React.Fragment key={esc.id}>
                                            <TableRow className={esc.email_sent ? '' : 'border-l-4 border-l-amber-400 bg-amber-50/30'}>
                                                <TableCell className="pl-6 font-mono text-xs text-muted-foreground">#{esc.case_id}</TableCell>
                                                <TableCell className="font-medium">{esc.officer_name || '-'}</TableCell>
                                                <TableCell className="text-sm text-muted-foreground">{esc.designation || '-'}</TableCell>
                                                <TableCell>
                                                    {esc.email_sent ? (
                                                        <Badge variant="default" className="bg-green-100 text-green-700 gap-1">
                                                            <CheckCircle2 className="h-3 w-3" /> Sent
                                                        </Badge>
                                                    ) : (
                                                        <Badge variant="outline" className="border-amber-300 text-amber-700 gap-1">
                                                            <Clock className="h-3 w-3" /> Not Sent
                                                        </Badge>
                                                    )}
                                                </TableCell>
                                                <TableCell className="text-sm text-muted-foreground">
                                                    {esc.deadline ? new Date(esc.deadline).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '-'}
                                                </TableCell>
                                                <TableCell className="text-sm text-muted-foreground">{esc.created_by || '-'}</TableCell>
                                                <TableCell className="text-xs text-muted-foreground">
                                                    {esc.created_at ? new Date(esc.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : '-'}
                                                </TableCell>
                                                <TableCell>
                                                    {!esc.email_sent && (
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            className="border-blue-200 text-blue-700 hover:bg-blue-50 text-xs h-7"
                                                            disabled={sendingEmail === esc.id}
                                                            onClick={() => handleSendEmail(esc.id)}
                                                        >
                                                            {sendingEmail === esc.id ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Mail className="h-3 w-3 mr-1" />}
                                                            Send
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
                                                            size="sm"
                                                            variant="ghost"
                                                            className="text-xs h-7 text-muted-foreground hover:text-foreground"
                                                            onClick={() => setExpandedLetter(expandedLetter === esc.id ? null : esc.id)}
                                                        >
                                                            {expandedLetter === esc.id ? 'Hide' : 'View'}
                                                        </Button>
                                                    )}
                                                </TableCell>
                                            </TableRow>
                                            {expandedLetter === esc.id && (
                                                <TableRow key={`letter-${esc.id}`} className="bg-slate-50">
                                                    <TableCell colSpan={9} className="px-6 pb-4 pt-2">
                                                        <div className="text-xs text-muted-foreground uppercase font-semibold mb-2 flex items-center gap-1">
                                                            <Mail className="h-3 w-3" /> Email sent to officer
                                                        </div>
                                                        <pre className="text-sm text-foreground whitespace-pre-wrap font-mono bg-white border rounded-lg p-4 leading-relaxed max-h-72 overflow-y-auto">
                                                            {esc.letter_content}
                                                        </pre>
                                                    </TableCell>
                                                </TableRow>
                                            )}
                                            </React.Fragment>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        )
                    ) : (
                        /* ─── Cases Table ─── */
                        loading ? (
                            <div className="space-y-3 py-6">
                                {[1, 2, 3, 4, 5].map(i => (
                                    <div key={i} className="flex items-center gap-4">
                                        <Skeleton className="h-4 w-4" />
                                        <Skeleton className="h-4 w-12" />
                                        <Skeleton className="h-4 w-24" />
                                        <Skeleton className="h-4 w-32" />
                                        <Skeleton className="h-4 w-24" />
                                        <Skeleton className="h-6 w-20" />
                                        <Skeleton className="h-4 flex-1" />
                                    </div>
                                ))}
                            </div>
                        ) : cases.length === 0 ? (
                            <div className="text-center py-16">
                                <CheckCircle2 className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
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
                                            <TableHead>Status</TableHead>
                                            <TableHead className="max-w-[250px]">Message</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {cases.map(c => (
                                            <TableRow
                                                key={c.id}
                                                className={cn("cursor-pointer", getRowHighlight(c.status))}
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
                                                <TableCell className="font-mono text-xs text-muted-foreground">{c.id}</TableCell>
                                                <TableCell className="font-mono text-xs">{c.user_phone || '-'}</TableCell>
                                                <TableCell className="font-medium">{c.category || 'General'}</TableCell>
                                                <TableCell className="text-muted-foreground">{c.location || '-'}</TableCell>
                                                <TableCell>{getStatusBadge(c.status)}</TableCell>
                                                <TableCell className="max-w-[250px]">
                                                    <span className="truncate block text-muted-foreground" title={c.raw_message}>
                                                        {c.raw_message || '-'}
                                                    </span>
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        )
                    )}
                </CardContent>

                {/* Pagination (hide on escalation tab) */}
                {!isEscalationTab && (
                    <div className="px-6 py-3 border-t flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">
                            Page {page} of {totalPages} ({totalCases} total cases)
                        </span>
                        <div className="flex gap-2">
                            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
                                Previous
                            </Button>
                            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
                                Next
                            </Button>
                        </div>
                    </div>
                )}
                {isEscalationTab && escalations.length > 0 && (
                    <div className="px-6 py-3 border-t">
                        <span className="text-sm text-muted-foreground">
                            {escalations.length} escalation{escalations.length !== 1 ? 's' : ''} total
                            {' · '}
                            {escalations.filter(e => e.email_sent).length} emails sent
                            {' · '}
                            {escalations.filter(e => !e.email_sent).length} pending
                        </span>
                    </div>
                )}
            </Card>

            {/* Case Modal */}
            <CaseModal
                caseItem={selected}
                onClose={() => { setSelected(null); fetchCases(); }}
                onStatusChange={handleStatusChange}
                toast={toast}
            />
        </div>
    );
}
