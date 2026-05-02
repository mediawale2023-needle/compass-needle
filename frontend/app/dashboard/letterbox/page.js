'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import { apiGet, apiPost } from '@/lib/api';
import {
    Upload, Send, Loader2, Inbox, Search, X, PenTool,
    ImageIcon, FileText, Download, ChevronLeft, ChevronRight, Trash2, Save,
    AlertCircle, CheckCircle2, Clock, Eye
} from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { cn } from '@/lib/utils';

// ─── Constants ───────────────────────────────────────────────────────────────

const CATEGORIES = [
    'Water & Sanitation', 'Roads & Infrastructure', 'Electricity & Power',
    'Health & Medical', 'Education', 'Pension & Welfare Schemes',
    'Land & Revenue', 'Police & Law & Order', 'Employment & MNREGA',
    'Agriculture & Farmers', 'Housing & PMAY', 'Women & Child Development',
    'Ration & PDS', 'Aadhaar & Documents', 'Caste & Community Certificates',
    'Drainage & Sewage', 'Environment & Pollution', 'Transport & Railways',
    'Banks & Finance', 'Forest & Tribal Affairs', 'Disaster Relief',
    'Sports & Youth', 'Religious & Minority Affairs', 'NRI Affairs',
    'Municipal Services', 'General / Other',
];

const INBOX_STATUS_FLOW = ['new', 'in_progress', 'resolved'];
const OUTBOX_STATUS_FLOW = ['drafted', 'sent'];

const STATUS_META = {
    processing:   { label: 'Processing',    color: 'bg-blue-100 text-blue-700' },
    new:          { label: 'New',           color: 'bg-sky-100 text-sky-700' },
    in_progress:  { label: 'In Progress',   color: 'bg-amber-100 text-amber-700' },
    drafted:      { label: 'Drafted',       color: 'bg-violet-100 text-violet-700' },
    sent:         { label: 'Sent',          color: 'bg-emerald-100 text-emerald-700' },
    resolved:     { label: 'Resolved',      color: 'bg-green-100 text-green-700' },
    needs_review: { label: 'Needs Review',  color: 'bg-red-100 text-red-700' },
    // legacy values
    'Pending-Intake': { label: 'Pending',   color: 'bg-blue-100 text-blue-700' },
    'Sent':           { label: 'Sent',      color: 'bg-green-100 text-green-700' },
    'Drafted':        { label: 'Drafted',   color: 'bg-violet-100 text-violet-700' },
};

const URGENCY_META = {
    High:   'bg-red-100 text-red-700',
    Normal: 'bg-green-100 text-green-700',
    Low:    'bg-slate-100 text-slate-600',
    Medium: 'bg-amber-100 text-amber-700',
};

const SOURCE_META = {
    whatsapp: { label: 'WhatsApp', color: 'bg-emerald-100 text-emerald-700' },
    upload:   { label: 'Uploaded', color: 'bg-slate-100 text-slate-600' },
    drafter:  { label: 'Drafter',  color: 'bg-violet-100 text-violet-700' },
};

function isPdfMime(mime) {
    return typeof mime === 'string' && mime.toLowerCase() === 'application/pdf';
}

// ─── Helper components ────────────────────────────────────────────────────────

function StatusBadge({ status }) {
    const meta = STATUS_META[status] || { label: status || '-', color: 'bg-slate-100 text-slate-600' };
    return <Badge variant="secondary" className={cn('text-xs font-medium', meta.color)}>{meta.label}</Badge>;
}

function UrgencyBadge({ urgency }) {
    return (
        <Badge variant="secondary" className={cn('text-xs font-medium', URGENCY_META[urgency] || 'bg-slate-100 text-slate-600')}>
            {urgency || 'Normal'}
        </Badge>
    );
}

function Thumbnail({ item }) {
    if (isPdfMime(item.image_mime)) {
        return (
            <div className="w-10 h-10 rounded border bg-rose-50 text-rose-700 flex items-center justify-center flex-shrink-0">
                <FileText className="h-4 w-4" />
            </div>
        );
    }
    if (!item.thumbnail) {
        return (
            <div className="w-10 h-10 rounded bg-muted flex items-center justify-center flex-shrink-0">
                <ImageIcon className="h-4 w-4 text-muted-foreground" />
            </div>
        );
    }
    return (
        <img
            src={item.thumbnail}
            alt="Letter"
            className="w-10 h-10 rounded object-cover flex-shrink-0 border"
        />
    );
}

function ScanBtn({ onUpload, direction }) {
    const [uploading, setUploading] = useState(false);
    const ref = useRef(null);

    const handle = async (file) => {
        if (!file) return;
        setUploading(true);
        try { await onUpload(file); }
        catch (e) { alert('Upload failed: ' + e.message); }
        finally { setUploading(false); }
    };

    return (
        <>
            <input type="file" ref={ref} className="hidden" accept=".pdf,image/*"
                onChange={e => handle(e.target.files[0])} />
            <Button onClick={() => ref.current?.click()} disabled={uploading} className="gap-2">
                {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                {uploading ? 'Scanning...' : direction === 'inbox' ? 'Scan Letter' : 'Upload Letter'}
            </Button>
        </>
    );
}

// ─── Status Stepper ───────────────────────────────────────────────────────────

function StatusStepper({ current, direction, onUpdate, saving }) {
    const specialStatuses = ['processing', 'needs_review'];
    if (specialStatuses.includes(current)) {
        return <StatusBadge status={current} />;
    }
    const statusFlow = direction === 'outbox' ? OUTBOX_STATUS_FLOW : INBOX_STATUS_FLOW;
    return (
        <div className="flex items-center gap-1 flex-wrap">
            {statusFlow.map((s, i) => {
                const currentIdx = Math.max(0, statusFlow.indexOf(current));
                const isPast = i < currentIdx;
                const isCurrent = s === current;
                const isNext = i === currentIdx + 1;
                const meta = STATUS_META[s];
                return (
                    <button
                        key={s}
                        disabled={saving || (!isNext && !isCurrent)}
                        onClick={() => isNext && onUpdate(s)}
                        className={cn(
                            'px-2.5 py-1 rounded-full text-xs font-medium transition-all',
                            isCurrent && meta.color + ' ring-2 ring-offset-1 ring-current',
                            isPast && 'bg-green-50 text-green-600 opacity-70',
                            isNext && 'bg-muted text-muted-foreground hover:bg-accent cursor-pointer',
                            !isCurrent && !isPast && !isNext && 'opacity-30'
                        )}
                    >
                        {isPast && <CheckCircle2 className="h-3 w-3 inline mr-1" />}
                        {isCurrent && <Clock className="h-3 w-3 inline mr-1" />}
                        {meta.label}
                    </button>
                );
            })}
        </div>
    );
}

// ─── Letter Modal ─────────────────────────────────────────────────────────────

function LetterModal({ item, onClose, onDraft, onSaved, onDeleted }) {
    const [fields, setFields] = useState({});
    const [saving, setSaving] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [confirmDelete, setConfirmDelete] = useState(false);
    const [currentPage, setCurrentPage] = useState(1);
    const [pageCount, setPageCount] = useState(1);
    const [showOcr, setShowOcr] = useState(false);
    const token = typeof window !== 'undefined' ? localStorage.getItem('needle_token') : null;
    const isPdf = isPdfMime(item?.image_mime);

    const imageUrl = item
        ? (() => {
            const base = process.env.NEXT_PUBLIC_API_URL || '';
            if (isPdf) return `${base}/api/letterbox/${item.id}/image`;
            if (currentPage === 1 && item.thumbnail) return item.thumbnail;
            if (item.image_mime || item.page_count > 1)
                return `${base}/api/letterbox/${item.id}/image?page=${currentPage}`;
            return null;
          })()
        : null;

    useEffect(() => {
        if (!item) return;
        setFields({
            citizen_name:   item.citizen_name || '',
            village:        item.village || '',
            phone_number:   item.phone_number || '',
            issue_summary:  item.issue_summary || '',
            category:       item.category || '',
            urgency_level:  item.urgency_level || 'Normal',
            date_of_letter: item.date_of_letter || '',
            assigned_to:    item.assigned_to || '',
            notes:          item.notes || '',
            document_text:  item.document_text || '',
            status:         item.status || 'new',
        });
        setCurrentPage(1);
        setPageCount(item.page_count || 1);
        setConfirmDelete(false);
        setShowOcr(false);
    }, [item]);

    if (!item) return null;

    const set = (k, v) => setFields(prev => ({ ...prev, [k]: v }));

    const handleSave = async () => {
        setSaving(true);
        try {
            const base = process.env.NEXT_PUBLIC_API_URL || '';
            const res = await fetch(`${base}/api/letterbox/${item.id}`, {
                method: 'PATCH',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify(fields),
            });
            if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Save failed');
            onSaved({ ...item, ...fields });
        } catch (e) { alert('Failed to save: ' + e.message); }
        finally { setSaving(false); }
    };

    const handleStatusUpdate = async (newStatus) => {
        setSaving(true);
        try {
            const base = process.env.NEXT_PUBLIC_API_URL || '';
            const res = await fetch(`${base}/api/letterbox/${item.id}`, {
                method: 'PATCH',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus }),
            });
            if (!res.ok) throw new Error('Update failed');
            set('status', newStatus);
            onSaved({ ...item, ...fields, status: newStatus });
        } catch (e) { alert('Failed to update status: ' + e.message); }
        finally { setSaving(false); }
    };

    const handleDelete = async () => {
        if (!confirmDelete) { setConfirmDelete(true); return; }
        setDeleting(true);
        try {
            const base = process.env.NEXT_PUBLIC_API_URL || '';
            const res = await fetch(`${base}/api/letterbox/${item.id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` },
            });
            if (!res.ok) throw new Error('Delete failed');
            onDeleted(item.id);
            onClose();
        } catch (e) { alert('Failed to delete: ' + e.message); }
        finally { setDeleting(false); }
    };

    const ocr = item.ocr_text || item.ocr_raw_text || '';
    const sourceMeta = SOURCE_META[item.source] || SOURCE_META['upload'];

    return (
        <Dialog open={!!item} onOpenChange={onClose}>
            <DialogContent className="max-w-4xl max-h-[92vh] overflow-y-auto p-0">
                {/* Header */}
                <DialogHeader className="px-6 py-4 border-b bg-primary text-primary-foreground rounded-t-xl">
                    <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                                <DialogDescription className="text-primary-foreground/70 text-xs font-semibold uppercase tracking-widest m-0">
                                    {item.direction === 'inbox' ? 'Incoming Letter' : 'Outgoing Letter'}
                                </DialogDescription>
                                {item.diary_number && (
                                    <span className="text-xs font-mono bg-primary-foreground/20 text-primary-foreground px-2 py-0.5 rounded">
                                        {item.diary_number}
                                    </span>
                                )}
                                <Badge variant="secondary" className={cn('text-xs', sourceMeta.color)}>
                                    {sourceMeta.label}
                                </Badge>
                            </div>
                            <DialogTitle className="text-base font-bold text-primary-foreground leading-snug">
                                {fields.issue_summary && fields.issue_summary !== '[NOT FOUND]'
                                    ? fields.issue_summary : 'No Subject'}
                            </DialogTitle>
                        </div>
                    </div>
                </DialogHeader>

                <div className="p-6 space-y-6">
                    {/* Image + status row */}
                    <div className="flex flex-col lg:flex-row gap-6">
                        {/* Image panel */}
                        <div className="lg:w-1/2">
                            {imageUrl ? (
                                <div className="border rounded-lg overflow-hidden bg-muted">
                                    {isPdf ? (
                                        <div className="bg-white">
                                            <div className="flex items-center justify-between gap-3 px-3 py-2 border-b bg-muted/30">
                                                <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                                                    <FileText className="h-4 w-4 text-rose-600" />
                                                    PDF Document
                                                    {(item.page_count || 1) > 1 && (
                                                        <span className="text-xs text-muted-foreground">
                                                            {item.page_count} pages
                                                        </span>
                                                    )}
                                                </div>
                                                <a
                                                    href={imageUrl}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                                                >
                                                    <Download className="h-3.5 w-3.5" />
                                                    Open / Download
                                                </a>
                                            </div>
                                            <iframe
                                                src={imageUrl}
                                                title="Original PDF document"
                                                className="w-full h-[32rem] bg-white"
                                            />
                                        </div>
                                    ) : (
                                        <img
                                            src={imageUrl}
                                            alt="Original letter"
                                            className="w-full object-contain max-h-80 lg:max-h-96"
                                            {...(imageUrl.startsWith('http') || imageUrl.startsWith('/api') ? {
                                                onError: e => e.target.style.display = 'none'
                                            } : {})}
                                        />
                                    )}
                                </div>
                            ) : (
                                <div className="border rounded-lg bg-muted flex items-center justify-center h-48 text-muted-foreground text-sm">
                                    No image available
                                </div>
                            )}

                            {/* Page navigator */}
                            {!isPdf && pageCount > 1 && (
                                <div className="flex items-center justify-between mt-2 px-1">
                                    <button
                                        onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                                        disabled={currentPage === 1}
                                        className="p-1 rounded hover:bg-muted disabled:opacity-30"
                                    >
                                        <ChevronLeft className="h-4 w-4" />
                                    </button>
                                    <span className="text-xs text-muted-foreground font-medium">
                                        Page {currentPage} of {pageCount}
                                    </span>
                                    <button
                                        onClick={() => setCurrentPage(p => Math.min(pageCount, p + 1))}
                                        disabled={currentPage === pageCount}
                                        className="p-1 rounded hover:bg-muted disabled:opacity-30"
                                    >
                                        <ChevronRight className="h-4 w-4" />
                                    </button>
                                </div>
                            )}

                        {/* OCR text toggle */}
                            {ocr && (
                                <div className="mt-3">
                                    <button
                                        onClick={() => setShowOcr(v => !v)}
                                        className="text-xs text-muted-foreground underline underline-offset-2 flex items-center gap-1"
                                    >
                                        <Eye className="h-3 w-3" />
                                        {showOcr ? 'Hide' : 'Show'} extracted text
                                    </button>
                                    {showOcr && (
                                        <div className="mt-2 bg-muted/50 border rounded-lg p-3 text-xs text-foreground whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto font-mono">
                                            {ocr}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>

                        {/* Fields panel */}
                        <div className="lg:w-1/2 space-y-4">
                            {/* Status stepper */}
                            <div>
                                <Label className="text-xs text-muted-foreground uppercase font-medium mb-2 block">Status</Label>
                                <StatusStepper current={fields.status} direction={item.direction} onUpdate={handleStatusUpdate} saving={saving} />
                            </div>

                            <div className="grid grid-cols-2 gap-3">
                                <div className="space-y-1">
                                    <Label className="text-xs">Sender / Recipient</Label>
                                    <Input value={fields.citizen_name} onChange={e => set('citizen_name', e.target.value)}
                                        placeholder="Name" className="h-8 text-sm" />
                                </div>
                                <div className="space-y-1">
                                    <Label className="text-xs">Phone</Label>
                                    <Input value={fields.phone_number} onChange={e => set('phone_number', e.target.value)}
                                        placeholder="Phone number" className="h-8 text-sm font-mono" />
                                </div>
                                <div className="space-y-1">
                                    <Label className="text-xs">Village / City</Label>
                                    <Input value={fields.village} onChange={e => set('village', e.target.value)}
                                        placeholder="Location" className="h-8 text-sm" />
                                </div>
                                <div className="space-y-1">
                                    <Label className="text-xs">Date of Letter</Label>
                                    <Input type="date" value={fields.date_of_letter || ''}
                                        onChange={e => set('date_of_letter', e.target.value)}
                                        className="h-8 text-sm" />
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-3">
                                <div className="space-y-1">
                                    <Label className="text-xs">Category</Label>
                                    <Select value={fields.category || ''} onValueChange={v => set('category', v)}>
                                        <SelectTrigger className="h-8 text-sm">
                                            <SelectValue placeholder="Select category" />
                                        </SelectTrigger>
                                        <SelectContent className="max-h-60">
                                            {CATEGORIES.map(c => (
                                                <SelectItem key={c} value={c} className="text-sm">{c}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-1">
                                    <Label className="text-xs">Priority</Label>
                                    <Select value={fields.urgency_level || 'Normal'} onValueChange={v => set('urgency_level', v)}>
                                        <SelectTrigger className="h-8 text-sm">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="High">High</SelectItem>
                                            <SelectItem value="Normal">Normal</SelectItem>
                                            <SelectItem value="Low">Low</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>

                            <div className="space-y-1">
                                <Label className="text-xs">Assigned To</Label>
                                <Input value={fields.assigned_to} onChange={e => set('assigned_to', e.target.value)}
                                    placeholder="Staff member name" className="h-8 text-sm" />
                            </div>
                        </div>
                    </div>

                    {/* Subject / Summary */}
                    <div className="space-y-1">
                        <Label className="text-xs">Subject / Issue Summary</Label>
                        <Textarea value={fields.issue_summary} onChange={e => set('issue_summary', e.target.value)}
                            placeholder="Summary of the issue or request" rows={3} className="text-sm resize-none" />
                    </div>

                    {/* Internal notes */}
                    <div className="space-y-1">
                        <Label className="text-xs">Internal Notes</Label>
                        <Textarea value={fields.notes} onChange={e => set('notes', e.target.value)}
                            placeholder="Staff notes (not visible to citizens)" rows={2} className="text-sm resize-none" />
                    </div>

                    {item.direction === 'outbox' && (
                        <div className="space-y-1">
                            <Label className="text-xs">Letter Text / Draft Content</Label>
                            <Textarea
                                value={fields.document_text}
                                onChange={e => set('document_text', e.target.value)}
                                placeholder="Final or working letter text"
                                rows={8}
                                className="text-sm resize-y font-serif"
                            />
                        </div>
                    )}
                </div>

                {/* Footer actions */}
                <DialogFooter className="px-6 py-4 border-t flex flex-col sm:flex-row justify-between gap-3">
                    <div className="flex gap-2">
                        {confirmDelete ? (
                            <>
                                <span className="text-xs text-red-600 flex items-center gap-1">
                                    <AlertCircle className="h-3 w-3" /> Confirm delete?
                                </span>
                                <Button variant="destructive" size="sm" onClick={handleDelete} disabled={deleting}>
                                    {deleting ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Yes, delete'}
                                </Button>
                                <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(false)}>Cancel</Button>
                            </>
                        ) : (
                            <Button variant="ghost" size="sm" onClick={handleDelete}
                                className="text-red-500 hover:text-red-700 hover:bg-red-50 gap-1">
                                <Trash2 className="h-3.5 w-3.5" /> Delete
                            </Button>
                        )}
                    </div>
                    <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={onClose}>Close</Button>
                        <Button variant="outline" size="sm" onClick={handleSave} disabled={saving} className="gap-1">
                            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                            Save Changes
                        </Button>
                        {item.direction === 'inbox' && (
                            <Button size="sm" onClick={() => onDraft(item)} className="gap-1">
                                <PenTool className="h-3.5 w-3.5" />
                                Draft Response
                            </Button>
                        )}
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function LetterboxPage() {
    const { user } = useAuth();
    const router = useRouter();

    const [tab, setTab] = useState('inbox');
    const [items, setItems] = useState([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [selected, setSelected] = useState(null);
    const [search, setSearch] = useState('');
    const [filterCategory, setFilterCategory] = useState('');
    const [filterStatus, setFilterStatus] = useState('');
    const [page, setPage] = useState(0);
    const LIMIT = 20;

    const fetchItems = useCallback(async (dir, q, cat, stat, pg) => {
        setLoading(true);
        try {
            const params = new URLSearchParams({
                direction: dir,
                limit: LIMIT,
                offset: pg * LIMIT,
                thumbnail: 'true',
            });
            if (q) params.set('search', q);
            if (cat) params.set('category', cat);
            if (stat) params.set('status', stat);
            const data = await apiGet(`/api/letterbox?${params}`);
            setItems(data.items || []);
            setTotal(data.total || 0);
        } catch (e) { console.error(e); }
        finally { setLoading(false); }
    }, []);

    useEffect(() => {
        setPage(0);
    }, [tab, search, filterCategory, filterStatus]);

    useEffect(() => {
        fetchItems(tab, search, filterCategory, filterStatus, page);
    }, [tab, search, filterCategory, filterStatus, page, fetchItems]);

    const handleUpload = async (file) => {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('direction', tab);
        const token = localStorage.getItem('needle_token');
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/api/letterbox/upload`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
            throw new Error(err.detail || 'Upload failed');
        }
        fetchItems(tab, search, filterCategory, filterStatus, page);
    };

    const draftResponse = (item) => {
        const params = new URLSearchParams({
            letterbox_id: item.id,
            subject: `Re: ${item.issue_summary || ''}`,
            recipient: item.citizen_name !== '[NOT FOUND]' ? (item.citizen_name || '') : '',
            context: [
                `Diary No: ${item.diary_number || ''}`,
                `From: ${item.citizen_name} (${item.village})`,
                `Phone: ${item.phone_number}`,
                `Category: ${item.category || ''}`,
                ``,
                `Issue:`,
                item.issue_summary,
            ].join('\n'),
        });
        router.push(`/dashboard/drafter?${params.toString()}`);
    };

    const handleSaved = (updated) => {
        setItems(prev => prev.map(i => i.id === updated.id ? { ...i, ...updated } : i));
        setSelected(prev => prev ? { ...prev, ...updated } : prev);
    };

    const handleDeleted = (id) => {
        setItems(prev => prev.filter(i => i.id !== id));
        setTotal(prev => Math.max(0, prev - 1));
    };

    const totalPages = Math.ceil(total / LIMIT);

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-foreground">Letterbox</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Digital dispatch register — incoming and outgoing constituency correspondence
                    </p>
                </div>
            </div>

            <Card>
                <CardHeader className="pb-0">
                    <div className="flex flex-col gap-4">
                        {/* Tabs + Upload */}
                        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                            <Tabs value={tab} onValueChange={v => { setTab(v); setPage(0); }} className="w-full sm:w-auto">
                                <TabsList>
                                    <TabsTrigger value="inbox" className="gap-2">
                                        <Inbox className="h-4 w-4" /> Inbox
                                    </TabsTrigger>
                                    <TabsTrigger value="outbox" className="gap-2">
                                        <Send className="h-4 w-4" /> Outbox
                                    </TabsTrigger>
                                </TabsList>
                            </Tabs>
                            <ScanBtn onUpload={handleUpload} direction={tab} />
                        </div>

                        {/* Search + Filters */}
                        <div className="flex flex-col sm:flex-row gap-3">
                            <div className="relative flex-1">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                                <Input
                                    value={search}
                                    onChange={e => setSearch(e.target.value)}
                                    placeholder="Search by name, phone, village, diary no..."
                                    className="pl-9 h-9"
                                />
                                {search && (
                                    <button onClick={() => setSearch('')}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                                        <X className="h-4 w-4" />
                                    </button>
                                )}
                            </div>
                            <Select value={filterCategory || 'all'} onValueChange={v => setFilterCategory(v === 'all' ? '' : v)}>
                                <SelectTrigger className="w-full sm:w-52 h-9">
                                    <SelectValue placeholder="All categories" />
                                </SelectTrigger>
                                <SelectContent className="max-h-60">
                                    <SelectItem value="all">All categories</SelectItem>
                                    {CATEGORIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                                </SelectContent>
                            </Select>
                            <Select value={filterStatus || 'all'} onValueChange={v => setFilterStatus(v === 'all' ? '' : v)}>
                                <SelectTrigger className="w-full sm:w-40 h-9">
                                    <SelectValue placeholder="All statuses" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">All statuses</SelectItem>
                                    <SelectItem value="new">New</SelectItem>
                                    <SelectItem value="in_progress">In Progress</SelectItem>
                                    <SelectItem value="drafted">Drafted</SelectItem>
                                    <SelectItem value="sent">Sent</SelectItem>
                                    <SelectItem value="resolved">Resolved</SelectItem>
                                    <SelectItem value="needs_review">Needs Review</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                </CardHeader>

                <CardContent className="pt-4">
                    {loading ? (
                        <div className="space-y-3 pt-2">
                            {[1,2,3,4,5].map(i => (
                                <div key={i} className="flex items-center gap-4">
                                    <Skeleton className="h-10 w-10 rounded" />
                                    <Skeleton className="h-4 w-28" />
                                    <Skeleton className="h-4 w-20" />
                                    <Skeleton className="h-4 w-16" />
                                    <Skeleton className="h-4 flex-1" />
                                    <Skeleton className="h-6 w-16" />
                                    <Skeleton className="h-6 w-20" />
                                </div>
                            ))}
                        </div>
                    ) : items.length === 0 ? (
                        <div className="text-center py-16">
                            <div className="mx-auto w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
                                {tab === 'inbox' ? <Inbox className="h-8 w-8 text-muted-foreground" /> : <Send className="h-8 w-8 text-muted-foreground" />}
                            </div>
                            <p className="text-muted-foreground">
                                {search || filterCategory || filterStatus ? 'No letters match your filters.' : `No letters in ${tab} yet.`}
                            </p>
                            {!(search || filterCategory || filterStatus) && (
                                <p className="text-sm text-muted-foreground mt-1">
                                    {tab === 'inbox'
                                        ? 'PA can send a photo via WhatsApp, or upload a scan here.'
                                        : 'Upload a copy of an outgoing letter to keep records.'}
                                </p>
                            )}
                        </div>
                    ) : (
                        <>
                            <div className="overflow-x-auto -mx-6">
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead className="w-12 pl-6"></TableHead>
                                            <TableHead className="w-28">Diary No.</TableHead>
                                            <TableHead>{tab === 'inbox' ? 'Sender' : 'Recipient'}</TableHead>
                                            <TableHead>Village</TableHead>
                                            <TableHead>Category</TableHead>
                                            <TableHead className="max-w-[200px]">Subject</TableHead>
                                            <TableHead>Priority</TableHead>
                                            <TableHead>Status</TableHead>
                                            <TableHead>Date</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {items.map((item) => (
                                            <TableRow key={item.id} onClick={() => setSelected(item)} className="cursor-pointer">
                                                <TableCell className="pl-6">
                                                    <div className="relative inline-block">
                                                        <Thumbnail item={item} />
                                                        {(item.page_count || 1) > 1 && (
                                                            <span className="absolute -top-1 -right-1 bg-primary text-primary-foreground text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center leading-none">
                                                                {item.page_count}
                                                            </span>
                                                        )}
                                                    </div>
                                                </TableCell>
                                                <TableCell className="font-mono text-xs text-muted-foreground">
                                                    {item.diary_number || `#${item.id}`}
                                                </TableCell>
                                                <TableCell className="font-semibold">
                                                    {item.citizen_name && item.citizen_name !== '[NOT FOUND]'
                                                        ? item.citizen_name : <span className="text-muted-foreground italic">Unknown</span>}
                                                </TableCell>
                                                <TableCell className="text-sm text-muted-foreground">
                                                    {item.village && item.village !== '[NOT FOUND]' ? item.village : '-'}
                                                </TableCell>
                                                <TableCell>
                                                    {item.category
                                                        ? <Badge variant="outline" className="text-xs whitespace-nowrap">{item.category}</Badge>
                                                        : <span className="text-muted-foreground text-xs">-</span>}
                                                </TableCell>
                                                <TableCell className="max-w-[200px]">
                                                    <p className="truncate text-sm text-muted-foreground">
                                                        {item.issue_summary && item.issue_summary !== '[NOT FOUND]'
                                                            ? item.issue_summary : '-'}
                                                    </p>
                                                </TableCell>
                                                <TableCell><UrgencyBadge urgency={item.urgency_level} /></TableCell>
                                                <TableCell><StatusBadge status={item.status} /></TableCell>
                                                <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                                                    {item.created_at ? new Date(item.created_at).toLocaleDateString('en-IN') : '-'}
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>

                            {/* Pagination */}
                            {totalPages > 1 && (
                                <div className="flex items-center justify-between mt-4 pt-4 border-t">
                                    <p className="text-xs text-muted-foreground">
                                        Showing {page * LIMIT + 1}–{Math.min((page + 1) * LIMIT, total)} of {total} letters
                                    </p>
                                    <div className="flex gap-2">
                                        <Button variant="outline" size="sm" onClick={() => setPage(p => p - 1)}
                                            disabled={page === 0} className="gap-1">
                                            <ChevronLeft className="h-4 w-4" /> Prev
                                        </Button>
                                        <Button variant="outline" size="sm" onClick={() => setPage(p => p + 1)}
                                            disabled={page >= totalPages - 1} className="gap-1">
                                            Next <ChevronRight className="h-4 w-4" />
                                        </Button>
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </CardContent>
            </Card>

            <LetterModal
                item={selected}
                onClose={() => setSelected(null)}
                onDraft={draftResponse}
                onSaved={handleSaved}
                onDeleted={handleDeleted}
            />
        </div>
    );
}
