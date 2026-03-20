'use client';

import { useState, useEffect, use } from 'react';
import { useRouter } from 'next/navigation';
import { apiGet, apiPatch, apiPost, AI_TIMEOUT } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';
import { Sheet, SheetContent, SheetFooter, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import {
    ArrowLeft,
    Building2,
    MapPin,
    TrendingUp,
    TrendingDown,
    Minus,
    AlertTriangle,
    CheckCircle2,
    Edit2,
    Save,
    X,
    Download,
    Loader2,
    Plus,
    BarChart3,
    FileText,
    Users,
    Printer,
    Calendar,
    MessageSquare,
} from 'lucide-react';

const STAGE_LABELS = {
    identified: 'Identified',
    contacted: 'Contacted',
    proposal_sent: 'Proposal Sent',
    negotiating: 'Negotiating',
    approved: 'Approved',
    funded: 'Funded',
};

const STAGE_COLORS = {
    identified: 'text-muted-foreground border-border',
    contacted: 'text-blue-700 border-blue-300',
    proposal_sent: 'text-amber-700 border-amber-400',
    negotiating: 'text-purple-700 border-purple-400',
    approved: 'text-emerald-700 border-emerald-400',
    funded: 'text-emerald-800 border-emerald-600',
};

function FYPill({ window: w, label }) {
    if (!w) return null;
    return (
        <span className={cn(
            'inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide border',
            w === 'prime'   && 'bg-emerald-50 border-emerald-300 text-emerald-700',
            w === 'late'    && 'bg-amber-50 border-amber-300 text-amber-700',
            w === 'next_fy' && 'bg-muted border-border text-muted-foreground',
        )}>
            <Calendar className="h-2.5 w-2.5 mr-1" />
            {label}
        </span>
    );
}

function SpendBar({ label, amount, maxAmount }) {
    const pct = maxAmount > 0 ? Math.round((amount / maxAmount) * 100) : 0;
    return (
        <div className="space-y-1">
            <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">{label}</span>
                <span className="font-mono font-semibold text-foreground">
                    {amount != null ? `₹${amount}L` : '—'}
                </span>
            </div>
            <div className="h-2 bg-secondary rounded-full overflow-hidden">
                <div
                    className="h-full bg-primary rounded-full transition-all"
                    style={{ width: `${pct}%` }}
                />
            </div>
        </div>
    );
}

function SpendTrendIcon({ y1, y2, y3 }) {
    const vals = [y1, y2, y3].filter(v => v != null);
    if (vals.length < 2) return <Minus className="h-4 w-4 text-muted-foreground" />;
    const last = vals[vals.length - 1];
    const prev = vals[vals.length - 2];
    if (last > prev) return <TrendingUp className="h-4 w-4 text-emerald-500" />;
    if (last < prev) return <TrendingDown className="h-4 w-4 text-destructive" />;
    return <Minus className="h-4 w-4 text-muted-foreground" />;
}

export default function CompanyProfilePage({ params }) {
    const { slug } = use(params);
    const router = useRouter();

    const [company, setCompany] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Contact editing
    const [editing, setEditing] = useState(false);
    const [editContact, setEditContact] = useState({ contact_person: '', contact_email: '', notes: '', unspent_obligation_lakhs: '' });
    const [saving, setSaving] = useState(false);

    // Letter / DPR sheet
    const [openSheet, setOpenSheet] = useState(null);
    const [genLoading, setGenLoading] = useState(null); // 'letter' | 'dpr'

    // Pipeline quick-add
    const [addingPipeline, setAddingPipeline] = useState(false);
    const [pipelineStage, setPipelineStage] = useState('identified');
    const [pipelineNotes, setPipelineNotes] = useState('');
    const [pipelineLoading, setPipelineLoading] = useState(false);

    // Pre-meeting briefing
    const [briefing, setBriefing] = useState(null);
    const [briefingLoading, setBriefingLoading] = useState(false);

    // Post-meeting interaction notes (keyed by entry id)
    const [interactionNotes, setInteractionNotes] = useState({});
    const [editingNote, setEditingNote] = useState(null); // entry id being edited
    const [savingNote, setSavingNote] = useState(null);   // entry id being saved

    const fetchProfile = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await apiGet(`/api/csr/companies/by-slug/${slug}`);
            setCompany(data);
            setEditContact({
                contact_person: data.contact_person || '',
                contact_email: data.contact_email || '',
                notes: data.notes || '',
                unspent_obligation_lakhs: data.unspent_obligation_lakhs != null
                    ? String(data.unspent_obligation_lakhs) : '',
            });
            // Seed interaction notes from loaded pipeline entries
            const notes = {};
            (data.pipeline_entries || []).forEach(e => {
                notes[e.id] = e.last_interaction_note || '';
            });
            setInteractionNotes(notes);
        } catch {
            setError('Company not found or failed to load.');
        } finally {
            setLoading(false);
        }
    };

    const fetchBriefing = async () => {
        setBriefingLoading(true);
        try {
            const data = await apiGet(`/api/csr/companies/by-slug/${slug}/briefing`);
            setBriefing(data);
        } catch {
            // non-fatal — briefing section simply stays empty
        } finally {
            setBriefingLoading(false);
        }
    };

    useEffect(() => {
        fetchProfile();
        fetchBriefing();
    }, [slug]);

    const saveInteractionNote = async (entryId) => {
        setSavingNote(entryId);
        try {
            await apiPatch(`/api/csr/pipeline/${entryId}/note`, {
                note: interactionNotes[entryId] || '',
            });
            setEditingNote(null);
            // refresh pipeline entries so datestamp shows
            await fetchProfile();
        } catch {
            // keep editing open on error
        } finally {
            setSavingNote(null);
        }
    };

    const saveContact = async () => {
        setSaving(true);
        try {
            const payload = {
                contact_person: editContact.contact_person || null,
                contact_email: editContact.contact_email || null,
                notes: editContact.notes || null,
                unspent_obligation_lakhs: editContact.unspent_obligation_lakhs
                    ? parseFloat(editContact.unspent_obligation_lakhs) : null,
            };
            await apiPatch(`/api/csr/companies/${company.id}/profile`, payload);
            await fetchProfile();
            setEditing(false);
        } catch {
            // keep form open on error
        } finally {
            setSaving(false);
        }
    };

    const generateLetter = async () => {
        setGenLoading('letter');
        try {
            const data = await apiPost('/api/csr/draft-letter', {
                company: company.name,
                district: company.district || '',
                sector: company.sector || '',
                total_3y: company.total_3y_lakhs ? `₹${company.total_3y_lakhs}L` : '',
                spend_history: {
                    '2022-23': company.spend_2022_23 ? `₹${company.spend_2022_23}L` : 'N/A',
                    '2023-24': company.spend_2023_24 ? `₹${company.spend_2023_24}L` : 'N/A',
                    '2024-25': company.spend_2024_25 ? `₹${company.spend_2024_25}L` : 'N/A',
                },
                letter_type: 'upscale',
            }, { timeout: AI_TIMEOUT, noRetry: true });
            setOpenSheet({
                title: `Partnership Letter — ${company.name}`,
                type: 'letter',
                content: data.content,
            });
        } catch {
            setOpenSheet({ title: `Letter — ${company.name}`, type: 'letter', content: 'Error generating letter. Please try again.' });
        } finally {
            setGenLoading(null);
        }
    };

    const addToPipeline = async () => {
        setPipelineLoading(true);
        try {
            await apiPost('/api/csr/pipeline', {
                company_name: company.name,
                sector: company.sector || '',
                stage: pipelineStage,
                notes: pipelineNotes,
            });
            setAddingPipeline(false);
            setPipelineNotes('');
            await fetchProfile();
        } catch {
            // keep open
        } finally {
            setPipelineLoading(false);
        }
    };

    const downloadText = (text, filename) => {
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = filename; a.click();
        URL.revokeObjectURL(url);
    };

    if (loading) return (
        <div className="space-y-6">
            <Skeleton className="h-8 w-48" />
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-28" />)}
            </div>
            <Skeleton className="h-48" />
        </div>
    );

    if (error || !company) return (
        <div className="space-y-4">
            <Button variant="ghost" size="sm" onClick={() => router.back()} className="gap-2">
                <ArrowLeft className="h-4 w-4" /> Back
            </Button>
            <Card className="border-destructive/30 bg-destructive/5">
                <CardContent className="py-12 text-center">
                    <AlertTriangle className="h-8 w-8 text-destructive mx-auto mb-3" />
                    <p className="text-sm text-destructive">{error || 'Company not found.'}</p>
                </CardContent>
            </Card>
        </div>
    );

    const maxSpend = Math.max(
        company.spend_2022_23 || 0,
        company.spend_2023_24 || 0,
        company.spend_2024_25 || 0,
        1
    );

    const isZeroSpend = company.status === 'zero_spend';
    const hasSpendData = company.total_3y_lakhs != null && company.total_3y_lakhs > 0;
    const pipelineEntries = company.pipeline_entries || [];

    return (
        <div className="space-y-6">
            {/* ─── Back + Header ─── */}
            <div>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => router.push('/dashboard/csr')}
                    className="gap-2 mb-4 -ml-2"
                >
                    <ArrowLeft className="h-4 w-4" />
                    CSR Intelligence
                </Button>

                <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                        <div className="flex flex-wrap items-center gap-2 mb-1">
                            <h1 className="text-2xl font-bold text-foreground">{company.name}</h1>
                            <Badge
                                variant="outline"
                                className={cn(
                                    "capitalize",
                                    company.company_type === 'local'
                                        ? "border-primary/50 text-primary bg-primary/5"
                                        : "border-border text-muted-foreground"
                                )}
                            >
                                <Building2 className="h-3 w-3 mr-1" />
                                {company.company_type === 'local' ? 'Local Operations' : 'Remote Spender'}
                            </Badge>
                            {isZeroSpend ? (
                                <Badge variant="destructive" className="gap-1">
                                    <AlertTriangle className="h-3 w-3" />
                                    Zero Spend
                                </Badge>
                            ) : (
                                <Badge variant="outline" className="border-emerald-400 text-emerald-700 bg-emerald-50 gap-1">
                                    <CheckCircle2 className="h-3 w-3" />
                                    Active
                                </Badge>
                            )}
                            {briefing?.fy_window && (
                                <FYPill window={briefing.fy_window.window} label={briefing.fy_window.label} />
                            )}
                        </div>
                        <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                            <MapPin className="h-3.5 w-3.5" />
                            {company.district}{company.state ? ` · ${company.state}` : ''}
                        </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => window.print()}
                            className="gap-2 print:hidden"
                        >
                            <Printer className="h-3.5 w-3.5" />
                            Print Briefing
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={generateLetter}
                            disabled={genLoading === 'letter'}
                            className="gap-2 print:hidden"
                        >
                            {genLoading === 'letter'
                                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                : <FileText className="h-3.5 w-3.5" />}
                            Draft Letter
                        </Button>
                        <Button
                            variant="default"
                            size="sm"
                            onClick={() => setAddingPipeline(true)}
                            className="gap-2 print:hidden"
                        >
                            <Plus className="h-3.5 w-3.5" />
                            Add to Pipeline
                        </Button>
                    </div>
                </div>
            </div>

            {/* ─── Compliance Help Card ─── */}
            {(isZeroSpend || company.unspent_obligation_lakhs) && (
                <Card className="border-amber-200 bg-amber-50/50 print:border print:border-amber-200">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-semibold text-amber-800 flex items-center gap-2">
                            <AlertTriangle className="h-4 w-4 shrink-0" />
                            Compliance Situation — Conversation Starter
                        </CardTitle>
                        <CardDescription className="text-amber-700/80 text-xs">
                            This company may have an unspent CSR obligation. The goal is to help them deploy it well — not to issue notices.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
                            <div className="bg-white/70 rounded-lg border border-amber-200 px-3 py-2">
                                <p className="text-[10px] font-semibold text-amber-700 uppercase tracking-wide">Unspent Obligation</p>
                                <p className="font-mono font-bold text-foreground mt-0.5">
                                    {company.unspent_obligation_lakhs != null
                                        ? `₹${company.unspent_obligation_lakhs}L`
                                        : <span className="text-muted-foreground font-normal text-xs italic">MCA data needed</span>}
                                </p>
                                <p className="text-[10px] text-muted-foreground mt-0.5">Per MCA annual disclosure</p>
                            </div>
                            <div className="bg-white/70 rounded-lg border border-amber-200 px-3 py-2">
                                <p className="text-[10px] font-semibold text-amber-700 uppercase tracking-wide">Transfer Deadline</p>
                                <p className="font-semibold text-foreground mt-0.5">30 Sept</p>
                                <p className="text-[10px] text-muted-foreground mt-0.5">
                                    6 months after FY end (March 31) — company must transfer to a Schedule VII fund if unspent
                                </p>
                            </div>
                            <div className="bg-white/70 rounded-lg border border-amber-200 px-3 py-2">
                                <p className="text-[10px] font-semibold text-amber-700 uppercase tracking-wide">Enforcement Authority</p>
                                <p className="font-semibold text-foreground mt-0.5">MCA / RoC</p>
                                <p className="text-[10px] text-muted-foreground mt-0.5">
                                    Registrar of Companies. This office can facilitate introductions — not issue directions.
                                </p>
                            </div>
                        </div>
                        {briefing?.sector_gaps?.length > 0 && (
                            <div>
                                <p className="text-[10px] font-semibold text-amber-700 uppercase tracking-wide mb-1">
                                    Schedule VII sectors they haven't spent on
                                </p>
                                <div className="flex flex-wrap gap-1">
                                    {briefing.sector_gaps.map((s, i) => (
                                        <Badge key={i} variant="outline" className="text-[10px] border-amber-300 text-amber-800 bg-white/50">
                                            {s}
                                        </Badge>
                                    ))}
                                </div>
                            </div>
                        )}
                        {briefing?.open_pipeline_entry && (
                            <div className="text-xs text-amber-800 bg-white/60 rounded border border-amber-200 px-3 py-2">
                                <span className="font-semibold">Open opportunity:</span>{' '}
                                {briefing.open_pipeline_entry.sector}
                                {briefing.open_pipeline_entry.estimated_amount
                                    ? ` · ${briefing.open_pipeline_entry.estimated_amount}` : ''}
                                {' '}— stage: {STAGE_LABELS[briefing.open_pipeline_entry.stage] || briefing.open_pipeline_entry.stage}
                            </div>
                        )}
                        <p className="text-[10px] text-muted-foreground/80 leading-relaxed">
                            Under the 2021 Amendment Rules, unspent amounts not deployed via an ongoing project must be transferred
                            within 6 months of FY end to a PM National Relief Fund or other Schedule VII fund. This office cannot
                            redirect these funds — but can help the company identify verified local projects before the deadline.
                        </p>
                    </CardContent>
                </Card>
            )}

            {/* ─── Key Metrics ─── */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <Card className={cn("border-l-4", hasSpendData ? "border-l-primary" : "border-l-border")}>
                    <CardContent className="p-5">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Total 3Y Spend</p>
                        <p className={cn("text-3xl font-bold mt-1", hasSpendData ? "text-primary" : "text-muted-foreground")}>
                            {company.total_3y_lakhs != null ? `₹${company.total_3y_lakhs}L` : isZeroSpend ? '₹0' : '—'}
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">FY 2022–25 cumulative</p>
                    </CardContent>
                </Card>

                <Card className="border-l-4 border-l-amber-500">
                    <CardContent className="p-5">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Avg Annual Ticket</p>
                        <div className="flex items-center gap-2 mt-1">
                            <p className="text-3xl font-bold text-amber-600">
                                {company.avg_ticket_size_lakhs != null ? `₹${company.avg_ticket_size_lakhs}L` : '—'}
                            </p>
                            <SpendTrendIcon
                                y1={company.spend_2022_23}
                                y2={company.spend_2023_24}
                                y3={company.spend_2024_25}
                            />
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">Per financial year</p>
                    </CardContent>
                </Card>

                <Card className="border-l-4 border-l-border">
                    <CardContent className="p-5">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Primary Sector</p>
                        <p className="text-lg font-bold text-foreground mt-1 leading-snug">{company.sector || '—'}</p>
                        {company.sector_priorities?.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-2">
                                {company.sector_priorities.map((s, i) => (
                                    <Badge key={i} variant="secondary" className="text-[10px]">{s}</Badge>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>

                <Card className="border-l-4 border-l-emerald-500">
                    <CardContent className="p-5">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Pipeline Entries</p>
                        <p className="text-3xl font-bold text-emerald-600 mt-1">{pipelineEntries.length}</p>
                        <p className="text-xs text-muted-foreground mt-1">
                            {pipelineEntries.length > 0
                                ? `Latest: ${STAGE_LABELS[pipelineEntries[0]?.stage] || pipelineEntries[0]?.stage}`
                                : 'Not yet in pipeline'}
                        </p>
                    </CardContent>
                </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* ─── Spend History ─── */}
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base flex items-center gap-2">
                            <BarChart3 className="h-4 w-4 text-muted-foreground" />
                            Spend History
                        </CardTitle>
                        <CardDescription>Annual CSR expenditure in ₹ Lakhs</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {(company.spend_2022_23 == null && company.spend_2023_24 == null && company.spend_2024_25 == null) ? (
                            <p className="text-sm text-muted-foreground italic">No spend data available.</p>
                        ) : (
                            <>
                                <SpendBar label="2022–23" amount={company.spend_2022_23} maxAmount={maxSpend} />
                                <SpendBar label="2023–24" amount={company.spend_2023_24} maxAmount={maxSpend} />
                                <SpendBar label="2024–25" amount={company.spend_2024_25} maxAmount={maxSpend} />
                            </>
                        )}
                        {company.gap_analysis && (
                            <>
                                <Separator />
                                <div>
                                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">Gap Analysis</p>
                                    <p className="text-sm text-foreground">{company.gap_analysis}</p>
                                </div>
                            </>
                        )}
                    </CardContent>
                </Card>

                {/* ─── Contact / Relationship ─── */}
                <Card>
                    <CardHeader className="pb-3">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-base flex items-center gap-2">
                                <Users className="h-4 w-4 text-muted-foreground" />
                                Contact & Relationship
                            </CardTitle>
                            {!editing ? (
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7"
                                    onClick={() => setEditing(true)}
                                    aria-label="Edit contact info"
                                >
                                    <Edit2 className="h-3.5 w-3.5" />
                                </Button>
                            ) : (
                                <div className="flex gap-1">
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-7 w-7 text-muted-foreground"
                                        onClick={() => setEditing(false)}
                                    >
                                        <X className="h-3.5 w-3.5" />
                                    </Button>
                                    <Button
                                        variant="default"
                                        size="sm"
                                        className="h-7 text-xs gap-1"
                                        onClick={saveContact}
                                        disabled={saving}
                                    >
                                        {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
                                        Save
                                    </Button>
                                </div>
                            )}
                        </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        {!editing ? (
                            <>
                                <div>
                                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Contact Person</p>
                                    <p className="text-sm text-foreground mt-0.5">
                                        {company.contact_person || <span className="italic text-muted-foreground">Not set</span>}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Email</p>
                                    <p className="text-sm text-foreground mt-0.5">
                                        {company.contact_email || <span className="italic text-muted-foreground">Not set</span>}
                                    </p>
                                </div>
                                {isZeroSpend && (
                                    <div>
                                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Unspent Obligation (₹L, MCA-reported)</p>
                                        <p className="text-sm text-foreground mt-0.5 font-mono">
                                            {company.unspent_obligation_lakhs != null
                                                ? `₹${company.unspent_obligation_lakhs}L`
                                                : <span className="italic text-muted-foreground">Requires MCA data</span>}
                                        </p>
                                        <p className="text-[10px] text-muted-foreground/70 mt-0.5 leading-tight">
                                            Must be transferred by company to a Schedule VII fund within 6 months of FY end (2021 Rules). Not redirectable by MP.
                                        </p>
                                    </div>
                                )}
                                <div>
                                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Notes</p>
                                    <p className="text-sm text-foreground mt-0.5 whitespace-pre-line">
                                        {company.notes || <span className="italic text-muted-foreground">No notes</span>}
                                    </p>
                                </div>
                            </>
                        ) : (
                            <>
                                <div className="space-y-1">
                                    <label className="text-xs font-medium text-muted-foreground">Contact Person</label>
                                    <Input
                                        value={editContact.contact_person}
                                        onChange={e => setEditContact(p => ({ ...p, contact_person: e.target.value }))}
                                        placeholder="CSR Head / Director name"
                                        className="h-8 text-sm"
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs font-medium text-muted-foreground">Email</label>
                                    <Input
                                        type="email"
                                        value={editContact.contact_email}
                                        onChange={e => setEditContact(p => ({ ...p, contact_email: e.target.value }))}
                                        placeholder="csr@company.com"
                                        className="h-8 text-sm"
                                    />
                                </div>
                                {isZeroSpend && (
                                    <div className="space-y-1">
                                        <label className="text-xs font-medium text-muted-foreground">Unspent Obligation — MCA Disclosed (₹ Lakhs)</label>
                                        <Input
                                            type="number"
                                            value={editContact.unspent_obligation_lakhs}
                                            onChange={e => setEditContact(p => ({ ...p, unspent_obligation_lakhs: e.target.value }))}
                                            placeholder="e.g. 45 — from MCA annual return"
                                            className="h-8 text-sm"
                                        />
                                        <p className="text-[10px] text-muted-foreground/70 leading-tight">
                                            Record the figure from MCA disclosures only. This obligation is owed to MCA, not to the MP's office.
                                        </p>
                                    </div>
                                )}
                                <div className="space-y-1">
                                    <label className="text-xs font-medium text-muted-foreground">Notes</label>
                                    <Textarea
                                        value={editContact.notes}
                                        onChange={e => setEditContact(p => ({ ...p, notes: e.target.value }))}
                                        placeholder="Meeting notes, follow-up dates, commitments…"
                                        className="text-sm resize-none"
                                        rows={3}
                                    />
                                </div>
                            </>
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* ─── Pipeline Entries ─── */}
            <Card>
                <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle className="text-base">Funding Pipeline</CardTitle>
                            <CardDescription>All pipeline entries for this company</CardDescription>
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setAddingPipeline(!addingPipeline)}
                            className="gap-2"
                        >
                            <Plus className="h-3.5 w-3.5" />
                            Add Entry
                        </Button>
                    </div>
                </CardHeader>
                <CardContent>
                    {addingPipeline && (
                        <div className="border border-dashed border-border rounded-lg p-4 mb-4 space-y-3 bg-muted/20">
                            <p className="text-sm font-medium text-foreground">New Pipeline Entry</p>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                <div className="space-y-1">
                                    <label className="text-xs font-medium text-muted-foreground">Stage</label>
                                    <select
                                        value={pipelineStage}
                                        onChange={e => setPipelineStage(e.target.value)}
                                        className="w-full h-8 rounded-md border border-input bg-background px-3 text-sm"
                                    >
                                        {Object.entries(STAGE_LABELS).map(([k, v]) => (
                                            <option key={k} value={k}>{v}</option>
                                        ))}
                                    </select>
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs font-medium text-muted-foreground">Notes (optional)</label>
                                    <Input
                                        value={pipelineNotes}
                                        onChange={e => setPipelineNotes(e.target.value)}
                                        placeholder="Context or next step"
                                        className="h-8 text-sm"
                                    />
                                </div>
                            </div>
                            <div className="flex gap-2">
                                <Button
                                    size="sm"
                                    disabled={pipelineLoading}
                                    onClick={addToPipeline}
                                    className="gap-1.5"
                                >
                                    {pipelineLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                                    Add
                                </Button>
                                <Button variant="ghost" size="sm" onClick={() => setAddingPipeline(false)}>
                                    Cancel
                                </Button>
                            </div>
                        </div>
                    )}

                    {pipelineEntries.length === 0 && !addingPipeline ? (
                        <p className="text-sm text-muted-foreground italic text-center py-6">
                            No pipeline entries yet. Add this company to your funding pipeline.
                        </p>
                    ) : (
                        <div className="space-y-3">
                            {pipelineEntries.map(entry => (
                                <div key={entry.id} className="rounded-lg border border-border bg-card">
                                    <div className="flex items-start gap-3 p-3">
                                        <Badge
                                            variant="outline"
                                            className={cn("text-xs shrink-0 mt-0.5", STAGE_COLORS[entry.stage] || 'text-muted-foreground border-border')}
                                        >
                                            {STAGE_LABELS[entry.stage] || entry.stage}
                                        </Badge>
                                        <div className="flex-1 min-w-0">
                                            {entry.estimated_amount && (
                                                <p className="text-sm font-mono font-semibold text-foreground">{entry.estimated_amount}</p>
                                            )}
                                            {entry.notes && (
                                                <p className="text-xs text-muted-foreground mt-0.5">{entry.notes}</p>
                                            )}
                                            <p className="text-xs text-muted-foreground/60 mt-1">
                                                Added {entry.created_at ? new Date(entry.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'}
                                            </p>
                                        </div>
                                    </div>
                                    {/* Post-meeting interaction note */}
                                    <div className="border-t border-border/60 px-3 py-2 bg-muted/20">
                                        <div className="flex items-center justify-between mb-1.5">
                                            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1">
                                                <MessageSquare className="h-3 w-3" />
                                                Last Interaction Note
                                            </p>
                                            {editingNote !== entry.id ? (
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-5 w-5 print:hidden"
                                                    onClick={() => setEditingNote(entry.id)}
                                                    aria-label="Edit interaction note"
                                                >
                                                    <Edit2 className="h-3 w-3" />
                                                </Button>
                                            ) : (
                                                <div className="flex gap-1 print:hidden">
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-5 w-5 text-muted-foreground"
                                                        onClick={() => setEditingNote(null)}
                                                    >
                                                        <X className="h-3 w-3" />
                                                    </Button>
                                                    <Button
                                                        variant="default"
                                                        size="sm"
                                                        className="h-5 text-[10px] px-2 gap-1"
                                                        disabled={savingNote === entry.id}
                                                        onClick={() => saveInteractionNote(entry.id)}
                                                    >
                                                        {savingNote === entry.id
                                                            ? <Loader2 className="h-2.5 w-2.5 animate-spin" />
                                                            : <Save className="h-2.5 w-2.5" />}
                                                        Save
                                                    </Button>
                                                </div>
                                            )}
                                        </div>
                                        {editingNote === entry.id ? (
                                            <Textarea
                                                value={interactionNotes[entry.id] || ''}
                                                onChange={e => setInteractionNotes(p => ({ ...p, [entry.id]: e.target.value }))}
                                                placeholder="Brief note after the meeting — what was discussed, next step, commitment made…"
                                                className="text-xs resize-none min-h-[60px]"
                                                rows={3}
                                            />
                                        ) : (
                                            entry.last_interaction_note ? (
                                                <div>
                                                    <p className="text-xs text-foreground whitespace-pre-line">{entry.last_interaction_note}</p>
                                                    {entry.last_interaction_at && (
                                                        <p className="text-[10px] text-muted-foreground/60 mt-1">
                                                            {new Date(entry.last_interaction_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                                                        </p>
                                                    )}
                                                </div>
                                            ) : (
                                                <p className="text-xs text-muted-foreground italic">
                                                    No note yet — add one after your next meeting.
                                                </p>
                                            )
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* ─── Print-only Briefing Page ─── */}
            <style jsx global>{`
                @media print {
                    .print\\:hidden { display: none !important; }
                    body { background: white !important; }
                }
            `}</style>
            <div className="hidden print:block mt-8 border-t pt-6 text-sm font-sans">
                <p className="text-xs text-muted-foreground mb-4">PRE-MEETING BRIEFING — {new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}</p>
                <h2 className="text-xl font-bold mb-1">{company.name}</h2>
                <p className="text-sm text-muted-foreground mb-4">
                    {company.district}{company.state ? ` · ${company.state}` : ''} &nbsp;|&nbsp;
                    {company.company_type === 'local' ? 'Local Operations' : 'Remote Spender'} &nbsp;|&nbsp;
                    {briefing?.fy_window?.label || ''}
                </p>

                <div className="grid grid-cols-3 gap-4 mb-4">
                    <div>
                        <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">3Y CSR Spend</p>
                        <p className="font-mono font-bold text-lg">{company.total_3y_lakhs != null ? `₹${company.total_3y_lakhs}L` : '—'}</p>
                        <p className="text-xs text-muted-foreground">FY 2022–25 · Avg ₹{company.avg_ticket_size_lakhs || '—'}L/yr</p>
                    </div>
                    <div>
                        <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">Primary Sector</p>
                        <p className="font-semibold">{company.sector || '—'}</p>
                        {company.sector_priorities?.length > 0 && (
                            <p className="text-xs text-muted-foreground">{company.sector_priorities.join(', ')}</p>
                        )}
                    </div>
                    <div>
                        <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">FY Window</p>
                        <p className="font-semibold">{briefing?.fy_window?.label || '—'}</p>
                        <p className="text-xs text-muted-foreground">{briefing?.fy_window?.description || ''}</p>
                    </div>
                </div>

                {briefing?.sector_gaps?.length > 0 && (
                    <div className="mb-4">
                        <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground mb-1">Schedule VII Gaps (not yet funded)</p>
                        <p className="text-sm">{briefing.sector_gaps.join(' · ')}</p>
                    </div>
                )}

                {briefing?.open_pipeline_entry && (
                    <div className="mb-4 border border-gray-300 rounded px-3 py-2">
                        <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground mb-1">Open Pipeline Entry</p>
                        <p className="text-sm font-semibold">
                            {briefing.open_pipeline_entry.sector}
                            {briefing.open_pipeline_entry.estimated_amount ? ` — ${briefing.open_pipeline_entry.estimated_amount}` : ''}
                        </p>
                        <p className="text-xs text-muted-foreground">
                            Stage: {STAGE_LABELS[briefing.open_pipeline_entry.stage] || briefing.open_pipeline_entry.stage}
                            {briefing.open_pipeline_entry.notes ? ` · ${briefing.open_pipeline_entry.notes}` : ''}
                        </p>
                    </div>
                )}

                {briefing?.best_ngo_partner && (
                    <div className="mb-4">
                        <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground mb-1">Suggested NGO Implementer</p>
                        <p className="text-sm font-semibold">{briefing.best_ngo_partner.name}</p>
                        <p className="text-xs text-muted-foreground">
                            {[briefing.best_ngo_partner.darpan_id && `Darpan: ${briefing.best_ngo_partner.darpan_id}`,
                              briefing.best_ngo_partner.csr1_number && `CSR-1: ${briefing.best_ngo_partner.csr1_number}`,
                              briefing.best_ngo_partner.sector].filter(Boolean).join(' · ')}
                        </p>
                    </div>
                )}

                {company.contact_person && (
                    <div className="mb-4">
                        <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground mb-1">Contact</p>
                        <p className="text-sm">{company.contact_person}{company.contact_email ? ` — ${company.contact_email}` : ''}</p>
                    </div>
                )}

                <p className="text-[9px] text-muted-foreground mt-6 border-t pt-2">
                    Internal briefing document. MPs are not in the statutory CSR approval chain (CSR Committee → Board → Implementation).
                    Enforcement authority rests with MCA / Registrar of Companies.
                </p>
            </div>

            {/* ─── Sheet: Letter output ─── */}
            <Sheet open={!!openSheet} onOpenChange={open => !open && setOpenSheet(null)}>
                <SheetContent side="right" className="w-full sm:max-w-xl p-0 flex flex-col gap-0">
                    <SheetHeader className="px-6 py-4 border-b border-border shrink-0 text-left">
                        <SheetTitle className="text-base leading-snug pr-6">{openSheet?.title}</SheetTitle>
                        <SheetDescription>Review carefully before sending.</SheetDescription>
                    </SheetHeader>
                    <ScrollArea className="flex-1 px-6 py-4">
                        {openSheet?.content ? (
                            <pre className="text-sm text-foreground bg-muted/50 rounded-lg border border-border p-4 whitespace-pre-wrap font-mono leading-relaxed">
                                {openSheet.content}
                            </pre>
                        ) : (
                            <div className="flex items-center gap-2 text-muted-foreground py-4">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                <span className="text-sm">Generating…</span>
                            </div>
                        )}
                    </ScrollArea>
                    {openSheet?.content && (
                        <SheetFooter className="px-6 py-4 border-t border-border shrink-0">
                            <Button variant="outline" onClick={() => setOpenSheet(null)}>Close</Button>
                            <Button
                                onClick={() => downloadText(
                                    openSheet.content,
                                    `${openSheet.type === 'letter' ? 'Letter' : 'DPR'}_${company.name.replace(/\s+/g, '_')}.txt`
                                )}
                                className="gap-2"
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
