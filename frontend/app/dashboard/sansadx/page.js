'use client';

import { useState, useEffect, Suspense } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPatch } from '@/lib/api';
import { useSearchParams, useRouter } from 'next/navigation';
import { X, Loader2, AlertTriangle, CheckCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
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

function CaseModal({ caseItem, color, onClose, onStatusChange }) {
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

                    {c.response_to_citizen && (
                        <div>
                            <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Response Sent</div>
                            <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                                {c.response_to_citizen}
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
    const [statusFilter, setStatusFilter] = useState('All');
    const [categoryFilter, setCategoryFilter] = useState('');
    const [selected, setSelected] = useState(null);

    useEffect(() => {
        const status = searchParams.get('status') || 'All';
        const cat = searchParams.get('category') || '';
        setStatusFilter(status);
        setCategoryFilter(cat);
    }, [searchParams]);

    useEffect(() => {
        fetchCases();
    }, [statusFilter, categoryFilter]);

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
            setCases(data.cases || []);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    }

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
            <div>
                <h1 className="text-2xl font-bold text-foreground">Briefcase</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Manage constituent grievances and cases
                </p>
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
                                                {c.user_phone || '-'}
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
