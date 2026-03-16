'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPost, apiPatch, AI_TIMEOUT } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription, SheetFooter } from '@/components/ui/sheet';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import {
    ArrowLeft,
    Plus,
    FileText,
    Download,
    Loader2,
    CheckCircle2,
    TrendingUp,
    Users,
    IndianRupee,
    AlertTriangle,
    RefreshCw,
    BarChart3,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const STATUS_META = {
    active:    { label: 'Active',    color: 'text-blue-700 border-blue-300 bg-blue-50' },
    completed: { label: 'Completed', color: 'text-emerald-700 border-emerald-300 bg-emerald-50' },
    stalled:   { label: 'Stalled',   color: 'text-amber-700 border-amber-300 bg-amber-50' },
    audited:   { label: 'Audited',   color: 'text-purple-700 border-purple-300 bg-purple-50' },
};

function ProgressBar({ pct }) {
    const p = Math.max(0, Math.min(100, pct || 0));
    return (
        <div className="w-full bg-muted rounded-full h-2">
            <div
                className={cn(
                    "h-2 rounded-full transition-all",
                    p >= 100 ? "bg-emerald-500" : p >= 60 ? "bg-primary" : "bg-amber-500"
                )}
                style={{ width: `${p}%` }}
            />
        </div>
    );
}

export default function CSRImpactPage() {
    const { user } = useAuth();
    const router = useRouter();

    const [reports, setReports] = useState([]);
    const [summary, setSummary] = useState({});
    const [loading, setLoading] = useState(true);

    const [showAddForm, setShowAddForm] = useState(false);
    const [addForm, setAddForm] = useState({
        company_name: '',
        project_title: '',
        sector: '',
        location: '',
        sanctioned_amount_lakhs: '',
        utilised_amount_lakhs: '',
        beneficiary_count: '',
        beneficiary_type: 'households',
        completion_percentage: '0',
        narrative_summary: '',
    });
    const [addLoading, setAddLoading] = useState(false);

    const [editId, setEditId] = useState(null);
    const [editPct, setEditPct] = useState('');
    const [editUtilised, setEditUtilised] = useState('');
    const [editStatus, setEditStatus] = useState('');
    const [editLoading, setEditLoading] = useState(false);

    const [certSheet, setCertSheet] = useState(null); // { id, content }
    const [certLoading, setCertLoading] = useState(null);

    const fetchReports = async () => {
        setLoading(true);
        try {
            const data = await apiGet('/api/csr/impact');
            setReports(data.reports || []);
            setSummary(data.summary || {});
        } catch {
            // silent
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchReports(); }, []);

    const handleAdd = async () => {
        if (!addForm.company_name.trim() || !addForm.project_title.trim()) return;
        setAddLoading(true);
        try {
            await apiPost('/api/csr/impact', {
                ...addForm,
                sanctioned_amount_lakhs: addForm.sanctioned_amount_lakhs ? parseFloat(addForm.sanctioned_amount_lakhs) : null,
                utilised_amount_lakhs: addForm.utilised_amount_lakhs ? parseFloat(addForm.utilised_amount_lakhs) : null,
                beneficiary_count: addForm.beneficiary_count ? parseInt(addForm.beneficiary_count) : null,
                completion_percentage: parseInt(addForm.completion_percentage) || 0,
            });
            setShowAddForm(false);
            setAddForm({
                company_name: '', project_title: '', sector: '', location: '',
                sanctioned_amount_lakhs: '', utilised_amount_lakhs: '',
                beneficiary_count: '', beneficiary_type: 'households',
                completion_percentage: '0', narrative_summary: '',
            });
            await fetchReports();
        } catch {
            // keep form open
        } finally {
            setAddLoading(false);
        }
    };

    const handleUpdate = async (id) => {
        setEditLoading(true);
        try {
            const body = {};
            if (editPct !== '') body.completion_percentage = parseInt(editPct);
            if (editUtilised !== '') body.utilised_amount_lakhs = parseFloat(editUtilised);
            if (editStatus) body.status = editStatus;
            await apiPatch(`/api/csr/impact/${id}`, body);
            setEditId(null);
            await fetchReports();
        } catch {
            // silent
        } finally {
            setEditLoading(false);
        }
    };

    const generateCert = async (id) => {
        setCertLoading(id);
        try {
            const data = await apiPost(`/api/csr/impact/${id}/certificate`, {}, { timeout: AI_TIMEOUT });
            setCertSheet({ id, content: data.content });
        } catch {
            setCertSheet({ id, content: 'Failed to generate certificate. Please try again.' });
        } finally {
            setCertLoading(null);
        }
    };

    const downloadText = (text, filename) => {
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = filename; a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-start gap-3">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => router.push('/dashboard/csr')}
                    className="gap-1.5 text-muted-foreground hover:text-foreground -ml-1"
                >
                    <ArrowLeft className="h-4 w-4" />
                    Back
                </Button>
            </div>

            <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                    <h1 className="text-2xl font-bold text-foreground">Impact Reporting</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Track funded CSR projects, monitor progress, and generate utilisation certificates.
                    </p>
                </div>
                <Button onClick={() => setShowAddForm(true)} className="gap-2">
                    <Plus className="h-4 w-4" />
                    New Impact Report
                </Button>
            </div>

            {/* Summary KPIs */}
            {!loading && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Card className="border-l-4 border-l-primary">
                        <CardContent className="p-4">
                            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Total Projects</p>
                            <p className="text-2xl font-bold text-foreground mt-1">{summary.total_projects || 0}</p>
                        </CardContent>
                    </Card>
                    <Card className="border-l-4 border-l-emerald-500">
                        <CardContent className="p-4">
                            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Total Utilised</p>
                            <p className="text-2xl font-bold text-emerald-600 mt-1">
                                {summary.total_utilised_lakhs
                                    ? `₹${parseFloat(summary.total_utilised_lakhs).toFixed(1)}L`
                                    : '—'}
                            </p>
                        </CardContent>
                    </Card>
                    <Card className="border-l-4 border-l-blue-500">
                        <CardContent className="p-4">
                            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Beneficiaries</p>
                            <p className="text-2xl font-bold text-blue-600 mt-1">
                                {(summary.total_beneficiaries || 0).toLocaleString()}
                            </p>
                        </CardContent>
                    </Card>
                    <Card className="border-l-4 border-l-amber-500">
                        <CardContent className="p-4">
                            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Active / Completed</p>
                            <p className="text-2xl font-bold text-amber-600 mt-1">
                                {summary.active || 0} / {summary.completed || 0}
                            </p>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* Add Form */}
            {showAddForm && (
                <Card className="border-primary/30">
                    <CardHeader>
                        <CardTitle className="text-base">New Impact Report</CardTitle>
                        <CardDescription className="text-xs">Track a CSR project from funding to completion.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <Input
                                placeholder="Company name *"
                                value={addForm.company_name}
                                onChange={e => setAddForm(f => ({ ...f, company_name: e.target.value }))}
                            />
                            <Input
                                placeholder="Project title *"
                                value={addForm.project_title}
                                onChange={e => setAddForm(f => ({ ...f, project_title: e.target.value }))}
                            />
                            <Input
                                placeholder="Sector (e.g. Water & Sanitation)"
                                value={addForm.sector}
                                onChange={e => setAddForm(f => ({ ...f, sector: e.target.value }))}
                            />
                            <Input
                                placeholder="Location / village"
                                value={addForm.location}
                                onChange={e => setAddForm(f => ({ ...f, location: e.target.value }))}
                            />
                            <Input
                                placeholder="Sanctioned amount (₹ Lakhs)"
                                type="number"
                                value={addForm.sanctioned_amount_lakhs}
                                onChange={e => setAddForm(f => ({ ...f, sanctioned_amount_lakhs: e.target.value }))}
                            />
                            <Input
                                placeholder="Utilised amount (₹ Lakhs)"
                                type="number"
                                value={addForm.utilised_amount_lakhs}
                                onChange={e => setAddForm(f => ({ ...f, utilised_amount_lakhs: e.target.value }))}
                            />
                            <Input
                                placeholder="Beneficiary count"
                                type="number"
                                value={addForm.beneficiary_count}
                                onChange={e => setAddForm(f => ({ ...f, beneficiary_count: e.target.value }))}
                            />
                            <Input
                                placeholder="Beneficiary type (households / students / patients)"
                                value={addForm.beneficiary_type}
                                onChange={e => setAddForm(f => ({ ...f, beneficiary_type: e.target.value }))}
                            />
                            <div className="sm:col-span-2">
                                <label className="text-xs text-muted-foreground mb-1 block">
                                    Completion: {addForm.completion_percentage}%
                                </label>
                                <input
                                    type="range"
                                    min="0" max="100"
                                    value={addForm.completion_percentage}
                                    onChange={e => setAddForm(f => ({ ...f, completion_percentage: e.target.value }))}
                                    className="w-full accent-primary"
                                />
                            </div>
                            <div className="sm:col-span-2">
                                <Textarea
                                    placeholder="Project narrative / summary (optional)"
                                    value={addForm.narrative_summary}
                                    onChange={e => setAddForm(f => ({ ...f, narrative_summary: e.target.value }))}
                                    className="resize-none text-sm"
                                    rows={3}
                                />
                            </div>
                        </div>
                        <div className="flex gap-2 mt-4">
                            <Button onClick={handleAdd} disabled={addLoading} className="gap-2">
                                {addLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                                {addLoading ? 'Saving…' : 'Save Report'}
                            </Button>
                            <Button variant="outline" onClick={() => setShowAddForm(false)}>Cancel</Button>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Report Cards */}
            {loading ? (
                <div className="space-y-3">
                    {[1,2,3].map(i => <Skeleton key={i} className="h-40 rounded-lg" />)}
                </div>
            ) : reports.length === 0 ? (
                <Card>
                    <CardContent className="py-16 text-center">
                        <BarChart3 className="h-10 w-10 text-muted-foreground/40 mx-auto mb-3" />
                        <p className="text-sm font-medium text-muted-foreground">No impact reports yet.</p>
                        <p className="text-xs text-muted-foreground/70 mt-1">
                            Create a report once a CSR project is funded and underway.
                        </p>
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-4">
                    {reports.map(report => {
                        const meta = STATUS_META[report.status] || STATUS_META.active;
                        const costPerBen = report.cost_per_beneficiary
                            ? `₹${Math.round(report.cost_per_beneficiary).toLocaleString()}`
                            : null;
                        const isEditing = editId === report.id;

                        return (
                            <Card key={report.id} className="overflow-hidden">
                                <CardContent className="p-5">
                                    <div className="flex items-start justify-between gap-3 flex-wrap">
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2 flex-wrap">
                                                <h3 className="text-base font-semibold text-foreground">
                                                    {report.project_title}
                                                </h3>
                                                <Badge
                                                    variant="outline"
                                                    className={cn("text-[10px] uppercase shrink-0", meta.color)}
                                                >
                                                    {meta.label}
                                                </Badge>
                                            </div>
                                            <p className="text-sm text-muted-foreground mt-0.5">
                                                {report.company_name}
                                                {report.location && ` · ${report.location}`}
                                                {report.sector && ` · ${report.sector}`}
                                            </p>
                                        </div>
                                        <div className="flex gap-2 shrink-0">
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => {
                                                    if (isEditing) { setEditId(null); }
                                                    else {
                                                        setEditId(report.id);
                                                        setEditPct(String(report.completion_percentage || 0));
                                                        setEditUtilised(String(report.utilised_amount_lakhs || ''));
                                                        setEditStatus(report.status || 'active');
                                                    }
                                                }}
                                            >
                                                {isEditing ? 'Cancel' : 'Update'}
                                            </Button>
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                className="gap-1.5"
                                                disabled={certLoading === report.id}
                                                onClick={() => generateCert(report.id)}
                                            >
                                                {certLoading === report.id
                                                    ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                    : <FileText className="h-3.5 w-3.5" />
                                                }
                                                {certLoading === report.id ? 'Generating…' : 'Utilisation Cert'}
                                            </Button>
                                        </div>
                                    </div>

                                    {/* Progress Bar */}
                                    <div className="mt-4 space-y-1">
                                        <div className="flex justify-between text-xs text-muted-foreground">
                                            <span>Completion</span>
                                            <span className="font-mono">{report.completion_percentage || 0}%</span>
                                        </div>
                                        <ProgressBar pct={report.completion_percentage} />
                                    </div>

                                    {/* Metrics Row */}
                                    <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
                                        <div>
                                            <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Sanctioned</p>
                                            <p className="text-sm font-semibold text-foreground">
                                                {report.sanctioned_amount_lakhs != null
                                                    ? `₹${report.sanctioned_amount_lakhs}L`
                                                    : '—'}
                                            </p>
                                        </div>
                                        <div>
                                            <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Utilised</p>
                                            <p className="text-sm font-semibold text-emerald-600">
                                                {report.utilised_amount_lakhs != null
                                                    ? `₹${report.utilised_amount_lakhs}L`
                                                    : '—'}
                                            </p>
                                        </div>
                                        <div>
                                            <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Beneficiaries</p>
                                            <p className="text-sm font-semibold text-foreground">
                                                {report.beneficiary_count != null
                                                    ? `${report.beneficiary_count.toLocaleString()} ${report.beneficiary_type || ''}`
                                                    : '—'}
                                            </p>
                                        </div>
                                        <div>
                                            <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Cost/Beneficiary</p>
                                            <p className="text-sm font-semibold text-foreground">{costPerBen || '—'}</p>
                                        </div>
                                    </div>

                                    {/* Narrative */}
                                    {report.narrative_summary && (
                                        <p className="mt-3 text-xs text-muted-foreground line-clamp-2">
                                            {report.narrative_summary}
                                        </p>
                                    )}

                                    {/* Inline Update Form */}
                                    {isEditing && (
                                        <div className="mt-4 pt-4 border-t border-border space-y-3">
                                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                                <div>
                                                    <label className="text-xs text-muted-foreground mb-1 block">
                                                        Completion: {editPct}%
                                                    </label>
                                                    <input
                                                        type="range" min="0" max="100"
                                                        value={editPct}
                                                        onChange={e => setEditPct(e.target.value)}
                                                        className="w-full accent-primary"
                                                    />
                                                </div>
                                                <div>
                                                    <label className="text-xs text-muted-foreground mb-1 block">Utilised (₹ Lakhs)</label>
                                                    <Input
                                                        type="number"
                                                        value={editUtilised}
                                                        onChange={e => setEditUtilised(e.target.value)}
                                                        className="h-8 text-sm"
                                                    />
                                                </div>
                                                <div>
                                                    <label className="text-xs text-muted-foreground mb-1 block">Status</label>
                                                    <select
                                                        className="w-full text-sm border border-border rounded-md px-2 py-1.5 bg-background text-foreground h-8"
                                                        value={editStatus}
                                                        onChange={e => setEditStatus(e.target.value)}
                                                    >
                                                        <option value="active">Active</option>
                                                        <option value="completed">Completed</option>
                                                        <option value="stalled">Stalled</option>
                                                        <option value="audited">Audited</option>
                                                    </select>
                                                </div>
                                            </div>
                                            <Button
                                                size="sm"
                                                onClick={() => handleUpdate(report.id)}
                                                disabled={editLoading}
                                                className="gap-2"
                                            >
                                                {editLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                                                Save Changes
                                            </Button>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            )}

            {/* Certificate Sheet */}
            <Sheet open={!!certSheet} onOpenChange={open => !open && setCertSheet(null)}>
                <SheetContent side="right" className="w-full sm:max-w-xl p-0 flex flex-col gap-0">
                    <SheetHeader className="px-6 py-4 border-b border-border shrink-0 text-left">
                        <SheetTitle className="text-base">Utilisation Certificate</SheetTitle>
                        <SheetDescription className="text-xs">
                            AI-drafted UC — review and have it signed before submission.
                        </SheetDescription>
                    </SheetHeader>
                    <ScrollArea className="flex-1 px-6 py-4">
                        <pre className="text-sm text-foreground bg-muted/50 rounded-lg border border-border p-4 whitespace-pre-wrap font-mono leading-relaxed">
                            {certSheet?.content}
                        </pre>
                    </ScrollArea>
                    {certSheet?.content && (
                        <SheetFooter className="px-6 py-4 border-t border-border shrink-0">
                            <Button variant="outline" onClick={() => setCertSheet(null)}>Close</Button>
                            <Button
                                className="gap-2"
                                onClick={() => downloadText(
                                    certSheet.content,
                                    `Utilisation_Certificate_${certSheet.id}.txt`
                                )}
                            >
                                <Download className="h-4 w-4" />
                                Download
                            </Button>
                        </SheetFooter>
                    )}
                </SheetContent>
            </Sheet>
        </div>
    );
}
