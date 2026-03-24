'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPatch } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
} from 'lucide-react';

const STATUS_OPTIONS = [
    { value: 'new', label: 'New', color: 'status-new' },
    { value: 'in_progress', label: 'In Progress', color: 'status-in_progress' },
    { value: 'resolved', label: 'Resolved', color: 'status-resolved' },
    { value: 'escalated', label: 'Escalated', color: 'status-escalated' },
    { value: 'closed', label: 'Closed', color: 'status-closed' },
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

function CaseDetail({ caseItem, onStatusChange, updating }) {
    if (!caseItem) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground py-20">
                <MessageSquare className="h-12 w-12 mb-3 opacity-30" />
                <p className="text-sm">Select a message to view details</p>
            </div>
        );
    }

    return (
        <div className="p-5 space-y-5">
            {/* Header */}
            <div className="flex items-start justify-between">
                <div>
                    <h3 className="font-semibold text-foreground">Case #{caseItem.id}</h3>
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

            {/* AI Response */}
            {caseItem.response_to_citizen && (
                <div>
                    <p className="text-[11px] text-muted-foreground mb-1.5">AI Auto-Response Sent</p>
                    <div className="bg-primary/5 border border-primary/20 rounded-lg p-3">
                        <p className="text-sm text-foreground">{caseItem.response_to_citizen}</p>
                    </div>
                </div>
            )}

            {/* Critical Flag */}
            {caseItem.is_critical && (
                <div className="flex items-center gap-2 p-3 bg-destructive/10 border border-destructive/20 rounded-lg">
                    <AlertTriangle className="h-4 w-4 text-destructive" />
                    <span className="text-sm font-medium text-destructive">Flagged as Critical / Emergency</span>
                </div>
            )}
        </div>
    );
}

export default function MessagesPage() {
    const [cases, setCases] = useState([]);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [search, setSearch] = useState('');
    const [statusFilter, setStatusFilter] = useState('all');
    const [selectedCase, setSelectedCase] = useState(null);
    const [updating, setUpdating] = useState(false);

    const fetchCases = useCallback(async () => {
        setLoading(true);
        try {
            let path = `/api/cases?page=${page}&per_page=20`;
            if (statusFilter && statusFilter !== 'all') path += `&status=${statusFilter}`;
            if (search) path += `&search=${encodeURIComponent(search)}`;
            const data = await apiGet(path);
            setCases(data.cases || []);
            setTotalPages(data.pages || 1);
        } catch {
            setCases([]);
        } finally {
            setLoading(false);
        }
    }, [page, statusFilter, search]);

    useEffect(() => { fetchCases(); }, [fetchCases]);

    const handleStatusChange = async (caseId, newStatus) => {
        setUpdating(true);
        try {
            await apiPatch(`/api/cases/${caseId}/status`, { status: newStatus });
            setCases(prev => prev.map(c => c.id === caseId ? { ...c, status: newStatus } : c));
            if (selectedCase?.id === caseId) {
                setSelectedCase(prev => ({ ...prev, status: newStatus }));
            }
        } catch {
            // Fail silently
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
                    {cases.length} shown
                </Badge>
            </div>

            {/* Filters */}
            <div className="flex flex-col sm:flex-row gap-3">
                <form onSubmit={handleSearch} className="flex-1 relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search messages, phone numbers..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="pl-9"
                    />
                </form>
                <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
                    <SelectTrigger className="w-40">
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
                    />
                </div>
            </div>
        </div>
    );
}
