'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPost, apiPatch, apiDelete, AI_TIMEOUT } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Sheet, SheetContent, SheetFooter, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import {
    Loader2,
    Search,
    AlertTriangle,
    Lock,
    Download,
    RefreshCw,
    Activity,
    Building2,
    ChevronRight,
    ChevronDown,
    CheckCircle2,
    MapPin,
    Target,
    Paperclip,
} from 'lucide-react';

const CSR_PILLS = ['All', 'Steel & Mining', 'Information Technology', 'Banking & Finance', 'Healthcare', 'Energy', 'Automobile'];

// ─── Skeleton for stat cards ───
function StatSkeleton() {
    return (
        <Card className="border-l-4 border-l-border">
            <CardContent className="p-5 space-y-2">
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-8 w-12" />
                <Skeleton className="h-3 w-36" />
            </CardContent>
        </Card>
    );
}

// ─── Skeleton for project cards ───
function ProjectCardSkeleton() {
    return (
        <Card className="border-l-4 border-l-border">
            <CardContent className="p-4 space-y-3">
                <div className="flex justify-between">
                    <div className="space-y-1.5">
                        <Skeleton className="h-4 w-32" />
                        <Skeleton className="h-3 w-24" />
                    </div>
                    <Skeleton className="h-5 w-20 rounded-full" />
                </div>
                <Skeleton className="h-2 w-full rounded-full" />
                <Skeleton className="h-3 w-28" />
            </CardContent>
        </Card>
    );
}

// ─── FY Window pill — reused on both opportunity and company cards ───
function FYPill({ window: w, label }) {
    if (!w) return null;
    return (
        <span className={cn(
            'inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide border',
            w === 'prime'   && 'bg-emerald-50 border-emerald-300 text-emerald-700',
            w === 'late'    && 'bg-amber-50 border-amber-300 text-amber-700',
            w === 'next_fy' && 'bg-muted border-border text-muted-foreground',
        )}>{label}</span>
    );
}

// ─── Opportunity Card with embedded company recommendations ───
function OpportunityCard({ opp, statusColor, dprLoading, onGenerateDPR, evidence, onEvidenceChange, fyWindow }) {
    const plan = opp.convergence_plan || {};
    const governmentRoute = opp.government_route || {};
    const schemes = governmentRoute.schemes || plan.schemes || [];
    const primaryScheme = schemes[0];
    const schemeIntel = primaryScheme?.intelligence || {};
    const isFundingAllowed = plan.csr_suitability === 'csr_complement_allowed';
    const suitabilityLabel = plan.csr_suitability === 'government_only'
        ? 'Government-only'
        : plan.csr_suitability === 'facilitation_only'
            ? 'Facilitation only'
            : 'CSR complement';

    return (
        <Card className={cn('border-l-4', statusColor)}>
            <CardContent className="p-4">
                {/* Header */}
                <div className="flex justify-between items-start">
                    <div>
                        <p className="font-semibold text-foreground">{opp.category}</p>
                        <p className="text-sm text-muted-foreground mt-0.5 flex items-center gap-1">
                            <MapPin className="h-3 w-3 shrink-0" />
                            {opp.constituency || opp.area || 'Constituency'}
                        </p>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                        <Badge variant="outline" className={cn(
                            'shrink-0',
                            opp.status === 'verify'
                                ? 'border-primary text-primary bg-primary/5'
                                : 'border-amber-500 text-amber-600 bg-amber-50',
                        )}>
                            {opp.volume} reports
                        </Badge>
                        {fyWindow && <FYPill window={fyWindow.window} label={fyWindow.label} />}
                    </div>
                </div>

                {/* Affected areas dropdown */}
                {opp.affected_areas?.length > 0 && (
                    <details className="mt-2 group">
                        <summary className="text-xs text-muted-foreground cursor-pointer flex items-center gap-1 list-none select-none w-fit">
                            <ChevronDown className="h-3 w-3 transition-transform group-open:rotate-180" />
                            {opp.affected_areas.length} area{opp.affected_areas.length !== 1 ? 's' : ''} affected
                        </summary>
                        <ul className="mt-1.5 space-y-0.5 pl-4">
                            {opp.affected_areas.map((a, i) => (
                                <li key={i} className="text-xs text-muted-foreground flex items-center justify-between gap-4">
                                    <span className="flex items-center gap-1">
                                        <span className="h-1.5 w-1.5 rounded-full bg-destructive/60 shrink-0" />
                                        {a.area}
                                    </span>
                                    <span className="font-mono text-muted-foreground/70">{a.volume} complaints</span>
                                </li>
                            ))}
                        </ul>
                    </details>
                )}

                {/* Progress bar */}
                <div className="mt-3 flex items-center gap-3">
                    <div className="flex-1 h-1.5 bg-secondary rounded-full overflow-hidden">
                        <div
                            className={cn('h-full rounded-full transition-all',
                                opp.status === 'verify' ? 'bg-primary' : 'bg-amber-500')}
                            style={{ width: `${Math.min(100, opp.progress_pct || 0)}%` }}
                        />
                    </div>
                    <span className="text-xs font-mono text-muted-foreground">{opp.progress_pct || 0}%</span>
                </div>

                <div className="mt-2">
                    <p className="text-xs text-muted-foreground">
                        Sector: <span className="font-semibold text-foreground">{opp.csr_sector}</span>
                    </p>
                </div>

                {/* True convergence plan: citizen demand → government route → CSR complement */}
                <div className="mt-4 grid grid-cols-1 lg:grid-cols-3 gap-3">
                    <div className="rounded-lg border border-border bg-muted/20 p-3">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                            Citizen Demand
                        </p>
                        <p className="text-sm font-semibold text-foreground">{opp.category}</p>
                        <p className="text-xs text-muted-foreground mt-1">
                            {opp.volume} reports across {opp.affected_areas?.length || 0} affected area{(opp.affected_areas?.length || 0) === 1 ? '' : 's'}
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">
                            Context: {plan.settlement_context || 'unknown'}{plan.state ? ` · ${plan.state}` : ''}
                        </p>
                    </div>

                    <div className="rounded-lg border border-blue-200 bg-blue-50/70 p-3">
                        <p className="text-xs font-semibold text-blue-700 uppercase tracking-wide mb-1">
                            Best Government Route
                        </p>
                        <p className="text-sm font-semibold text-foreground">
                            {primaryScheme?.name || 'Relevant scheme to verify'}
                        </p>
                        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                            {governmentRoute.department || plan.department || 'Relevant line department'}
                        </p>
                        {governmentRoute.gap_type && (
                            <Badge variant="outline" className="mt-2 text-[10px] bg-white/70 border-blue-200 text-blue-700">
                                {governmentRoute.gap_type.replaceAll('_', ' ')}
                            </Badge>
                        )}
                    </div>

                    <div className="rounded-lg border border-emerald-200 bg-emerald-50/70 p-3">
                        <p className="text-xs font-semibold text-emerald-700 uppercase tracking-wide mb-1">
                            CSR Complement
                        </p>
                        <div className="flex items-center gap-2">
                            <p className="text-sm font-semibold text-foreground">
                                {plan.pathway_label || 'Government + CSR'}
                            </p>
                            <Badge variant="outline" className={cn(
                                'text-[10px] bg-white/70',
                                isFundingAllowed
                                    ? 'border-emerald-200 text-emerald-700'
                                    : 'border-amber-300 text-amber-700',
                            )}>
                                {suitabilityLabel}
                            </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1 line-clamp-3">
                            {plan.csr_complement || 'Complementary CSR support after government route is verified.'}
                        </p>
                    </div>
                </div>

                <div className="mt-3 grid grid-cols-1 lg:grid-cols-2 gap-3">
                    <div className="rounded-lg border border-border bg-card p-3">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                            Why This Scheme Matched
                        </p>
                        <p className="text-sm text-foreground">
                            {primaryScheme?.fit || 'No ranked prs_schemes match yet. Verify the government route manually.'}
                        </p>
                        {primaryScheme?.matched_terms?.length > 0 && (
                            <div className="mt-2 flex flex-wrap gap-1">
                                {primaryScheme.matched_terms.slice(0, 6).map(term => (
                                    <Badge key={term} variant="outline" className="text-[10px] bg-muted/30">
                                        {term}
                                    </Badge>
                                ))}
                            </div>
                        )}
                        {(schemeIntel.state_specific_fact || schemeIntel.implementation_gap || schemeIntel.fund_signal) && (
                            <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                                {schemeIntel.state_specific_fact && <p><span className="font-semibold text-foreground">State fact:</span> {schemeIntel.state_specific_fact}</p>}
                                {schemeIntel.implementation_gap && <p><span className="font-semibold text-foreground">Gap:</span> {schemeIntel.implementation_gap}</p>}
                                {schemeIntel.fund_signal && <p><span className="font-semibold text-foreground">Fund signal:</span> {schemeIntel.fund_signal}</p>}
                            </div>
                        )}
                    </div>

                    <div className="rounded-lg border border-border bg-card p-3">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                            Required Evidence
                        </p>
                        <ul className="space-y-1">
                            {(plan.evidence_needed || []).slice(0, 4).map(item => (
                                <li key={item} className="text-sm text-foreground flex items-start gap-2">
                                    <CheckCircle2 className="h-3.5 w-3.5 text-primary mt-0.5 shrink-0" />
                                    <span>{item}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                </div>

                {!isFundingAllowed && (
                    <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
                        <p className="text-xs font-semibold text-amber-800 uppercase tracking-wide mb-0.5">
                            Do not pitch as CSR funding
                        </p>
                        <p className="text-sm text-amber-900">
                            This should remain a government-led entitlement, administrative, or safety route. CSR can only support lawful facilitation after department verification.
                        </p>
                    </div>
                )}

                {plan.next_action && (
                    <div className="mt-3 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2">
                        <p className="text-xs font-semibold text-primary uppercase tracking-wide mb-0.5">Recommended Next Action</p>
                        <p className="text-sm text-foreground">{plan.next_action}</p>
                    </div>
                )}

                {/* ─── Supporting Evidence attachment ─── */}
                <div className="mt-3 space-y-1.5">
                    <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1.5 cursor-pointer w-fit">
                        <Paperclip className="h-3 w-3" />
                        Supporting Evidence
                        <input
                            type="file"
                            accept=".txt,.pdf,.doc,.docx"
                            className="sr-only"
                            onChange={e => onEvidenceChange && onEvidenceChange(opp.category, e.target.files[0])}
                        />
                    </label>
                    {evidence?.name ? (
                        <div className="flex items-center gap-1.5 text-xs text-primary bg-primary/5 border border-primary/20 rounded px-2 py-1 w-fit">
                            <Paperclip className="h-3 w-3 shrink-0" />
                            <span className="truncate max-w-[180px]">{evidence.name}</span>
                            <button
                                onClick={() => onEvidenceChange && onEvidenceChange(opp.category, null)}
                                className="ml-1 text-muted-foreground hover:text-destructive shrink-0"
                                aria-label="Remove evidence"
                            >×</button>
                        </div>
                    ) : (
                        <div className="flex items-start gap-1.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1.5">
                            <AlertTriangle className="h-3 w-3 shrink-0 mt-0.5" />
                            <span>This convergence note relies only on grievance data. Attach a government document, scheme status note, district survey, or department verification to strengthen credibility.</span>
                        </div>
                    )}
                </div>

                {/* Company Recommendations */}
                {opp.top_companies && opp.top_companies.length > 0 && (
                    <div className="mt-4 space-y-2">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1.5">
                            <Target className="h-3 w-3" />Who to Approach
                        </p>
                        {opp.top_companies.map((co, ci) => {
                            const dprKey = `${opp.category}-${co.name}`;
                            return (
                                <div key={ci} className="rounded-md border border-border bg-muted/20 p-3 space-y-2">
                                    <div className="flex items-start justify-between gap-2">
                                        <div className="min-w-0">
                                            <p className="text-sm font-semibold text-foreground truncate">{co.name}</p>
                                            <p className="text-xs text-muted-foreground">
                                                {co.sector}{co.district ? ` · ${co.district}` : ''}
                                                {co.recommended_ask_amount ? ` · Suggested ask: ₹${co.recommended_ask_amount}L` : ''}
                                            </p>
                                        </div>
                                        <Badge variant="outline" className={cn(
                                            'shrink-0 font-mono text-xs',
                                            co.match_score >= 70 && 'border-emerald-500 text-emerald-700 bg-emerald-50',
                                            co.match_score >= 40 && co.match_score < 70 && 'border-amber-500 text-amber-700 bg-amber-50',
                                            co.match_score < 40 && 'border-muted-foreground/30 text-muted-foreground',
                                        )}>
                                            {co.match_score}% fit
                                        </Badge>
                                    </div>

                                    {co.reason && (
                                        <p className="text-xs text-muted-foreground leading-relaxed">{co.reason}</p>
                                    )}

                                    {co.has_funded_similar && co.similar_projects?.length > 0 && (
                                        <p className="text-xs text-primary flex items-center gap-1">
                                            <CheckCircle2 className="h-3 w-3 shrink-0" />
                                            Previously funded: {co.similar_projects[0].title}
                                            {co.similar_projects[0].location ? ` in ${co.similar_projects[0].location}` : ''}
                                        </p>
                                    )}

                                    <div className="flex flex-wrap items-start gap-2 pt-0.5">
                                        {co.suggested_next_action === 'dpr' && isFundingAllowed && (
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                className="h-7 text-xs gap-1.5"
                                                disabled={dprLoading === dprKey}
                                                onClick={() => onGenerateDPR(opp, co, evidence)}
                                            >
                                                {dprLoading === dprKey
                                                    ? <><Loader2 className="h-3 w-3 animate-spin" />Generating...</>
                                                    : 'Generate Convergence Note'
                                                }
                                            </Button>
                                        )}
                                        {co.suggested_approach && (
                                            <p className="text-xs text-muted-foreground leading-relaxed flex-1 min-w-0">
                                                {co.suggested_approach}
                                            </p>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

// ─── Error card ───
function ErrorCard({ message, onRetry }) {
    return (
        <Card className="border-destructive/30 bg-destructive/5">
            <CardContent className="py-6 flex flex-col items-center gap-3 text-center">
                <AlertTriangle className="h-8 w-8 text-destructive" />
                <p className="text-sm font-medium text-destructive">{message}</p>
                {onRetry && (
                    <Button variant="outline" size="sm" onClick={onRetry} className="gap-2">
                        <RefreshCw className="h-3.5 w-3.5" />
                        Retry
                    </Button>
                )}
            </CardContent>
        </Card>
    );
}

function LockedModule({ name }) {
    return (
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-center px-6">
            <div className="h-16 w-16 rounded-full bg-muted flex items-center justify-center">
                <Lock className="h-7 w-7 text-muted-foreground" />
            </div>
            <div>
                <h2 className="text-lg font-semibold text-foreground">{name} is restricted</h2>
                <p className="text-sm text-muted-foreground mt-1">
                    This module is available to the MP only. Contact your MP for access.
                </p>
            </div>
        </div>
    );
}

export default function CSRPage() {
    const { user } = useAuth();
    const router = useRouter();

    if (user && user.role !== 'mp' && user.role !== 'admin') {
        return <LockedModule name="Convergence" />;
    }

    // ─── Live Data State ───
    const [opportunities, setOpportunities] = useState([]);
    const [opportunitiesLoading, setOpportunitiesLoading] = useState(true);
    const [opportunitiesError, setOpportunitiesError] = useState(null);
    const [fyWindow, setFyWindow] = useState(null); // { window, label, description }

    // ─── Company Database State ───
    const [companies, setCompanies] = useState([]);
    const [search, setSearch] = useState('');
    const [selectedSector, setSelectedSector] = useState('All');
    const [companiesLoading, setCompaniesLoading] = useState(true);
    const [companiesError, setCompaniesError] = useState(null);

    // ─── Draft / DPR State ───
    const [draftLoading, setDraftLoading] = useState(null);
    const [dprLoading, setDprLoading] = useState(null);

    // ─── Evidence files — keyed by opp.category ───
    const [evidenceFiles, setEvidenceFiles] = useState({}); // { [category]: File | null }

    const handleEvidenceChange = (category, file) => {
        setEvidenceFiles(prev => ({ ...prev, [category]: file || null }));
    };

    // ─── Sheet State ───
    const [openSheet, setOpenSheet] = useState(null); // { type: 'dpr'|'draft', key, title, content }

    // ─── Tab State ───
    const [activeTab, setActiveTab] = useState('live');

    // ─── Fetch convergence opportunities with scheme route + company recommendations ───
    const fetchOpportunities = async () => {
        setOpportunitiesLoading(true);
        setOpportunitiesError(null);
        try {
            const data = await apiGet('/api/convergence/opportunities');
            setOpportunities(data.opportunities || []);
            if (data.fy_window) setFyWindow(data.fy_window);
        } catch (err) {
            console.error('Opportunities fetch failed:', err);
            setOpportunitiesError('Failed to load opportunities.');
        } finally {
            setOpportunitiesLoading(false);
        }
    };

    useEffect(() => { fetchOpportunities(); }, []);

    // ─── Fetch CSR company database ───
    const fetchCompanies = async () => {
        setCompaniesLoading(true);
        setCompaniesError(null);
        try {
            const params = new URLSearchParams();
            if (search) params.set('search', search);
            if (selectedSector !== 'All') params.set('sector', selectedSector);
            const data = await apiGet(`/api/csr/companies?${params}`);
            setCompanies(data.companies || []);
        } catch (err) {
            console.error(err);
            setCompaniesError('Failed to load company database.');
        } finally {
            setCompaniesLoading(false);
        }
    };
    useEffect(() => { fetchCompanies(); }, [search, selectedSector]);

    // ─── Draft letter from company database ───
    const draftLetter = async (company) => {
        setDraftLoading(company.Company);
        try {
            const data = await apiPost('/api/csr/draft-letter', {
                company: company.Company,
                district: company.District || user?.constituency || '',
                sector: company.Sector || '',
                total_3y: company.Total_3Y || '',
                spend_history: company.Spend_History || company.History || {},
                letter_type: 'upscale',
            }, { timeout: AI_TIMEOUT, noRetry: true });
            const content = data.content;
            setOpenSheet({
                type: 'draft',
                key: company.Company,
                title: `Draft Letter — ${company.Company}`,
                content,
            });
        } catch (err) {
            setOpenSheet({
                type: 'draft',
                key: company.Company,
                title: `Draft — ${company.Company}`,
                content: 'Error generating draft.',
            });
        } finally {
            setDraftLoading(null);
        }
    };

    // ─── Generate Concept Note from opportunity-first recommendation ───
    const generateDPRFromOpportunity = async (opp, company, evidenceFile) => {
        const key = `${opp.category}-${company.name}`;
        setDprLoading(key);
        try {
            // Read evidence file text if provided
            let evidence_text = '';
            let evidence_filename = '';
            if (evidenceFile) {
                evidence_filename = evidenceFile.name;
                try {
                    evidence_text = await evidenceFile.text();
                } catch {
                    evidence_text = '';
                }
            }
            const data = await apiPost('/api/csr/generate-dpr', {
                category: opp.category,
                area: opp.area,
                volume: opp.volume,
                company: company.name,
                sector: company.sector || opp.csr_sector || '',
                government_scheme: opp.convergence_plan?.schemes?.[0]?.name || '',
                government_department: opp.convergence_plan?.department || '',
                gap_type: opp.convergence_plan?.gap_type || '',
                csr_complement: opp.convergence_plan?.csr_complement || '',
                recommended_pathway: opp.convergence_plan?.recommended_pathway || '',
                government_scheme_fit: opp.convergence_plan?.schemes?.[0]?.fit || '',
                scheme_state_fact: opp.convergence_plan?.schemes?.[0]?.intelligence?.state_specific_fact || '',
                scheme_implementation_gap: opp.convergence_plan?.schemes?.[0]?.intelligence?.implementation_gap || '',
                scheme_fund_signal: opp.convergence_plan?.schemes?.[0]?.intelligence?.fund_signal || '',
                evidence_text,
                evidence_filename,
            }, { timeout: AI_TIMEOUT, noRetry: true });
            const fyNote = fyWindow?.window === 'next_fy'
                ? '\n\n---\nNote: Current FY budget is likely locked (January–March). Save this document for April outreach when fresh CSR budgets are allocated.'
                : fyWindow?.window === 'late'
                ? '\n\n---\nNote: Budgets are mostly committed (November–December). This note may be better timed for next FY — follow up in April.'
                : '';
            setOpenSheet({
                type: 'dpr',
                key,
                title: `Concept Note — ${opp.category} × ${company.name}`,
                content: data.content + fyNote,
            });
        } catch {
            setOpenSheet({
                type: 'dpr',
                key,
                title: `Concept Note — ${company.name}`,
                content: 'Error generating concept note. Please try again.',
            });
        } finally {
            setDprLoading(null);
        }
    };

    const downloadText = (text, filename) => {
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = filename; a.click();
        URL.revokeObjectURL(url);
    };

    const opportunitiesReady = opportunities.filter(o => o.status === 'verify').length;
    const opportunitiesMonitoring = opportunities.filter(o => o.status === 'watch').length;

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-foreground">Convergence</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Connect grievance demand with government schemes and CSR partners
                </p>
            </div>

            {/* ─── FY Calendar Banner ─── */}
            {fyWindow && (
                <div className={cn(
                    'flex items-start gap-3 rounded-lg border px-4 py-3 text-sm',
                    fyWindow.window === 'prime' && 'bg-emerald-50 border-emerald-200 text-emerald-800',
                    fyWindow.window === 'late'  && 'bg-amber-50 border-amber-200 text-amber-800',
                    fyWindow.window === 'next_fy' && 'bg-muted border-border text-muted-foreground',
                )}>
                    <span className="font-semibold shrink-0">{fyWindow.label}:</span>
                    <span>{fyWindow.description}</span>
                </div>
            )}

            {/* ─── Summary Stats ─── */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {opportunitiesLoading ? (
                    <>
                        <StatSkeleton />
                        <StatSkeleton />
                    </>
                ) : (
                    <>
                        <Card className="border-l-4 border-l-primary">
                            <CardContent className="p-5">
                                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                                    Field Verification Needed
                                </p>
                                <p className="text-3xl font-bold text-primary mt-1">{opportunitiesReady}</p>
                                <p className="text-xs text-muted-foreground mt-1">Internal trigger — confirm need on ground first</p>
                            </CardContent>
                        </Card>
                        <Card className="border-l-4 border-l-amber-500">
                            <CardContent className="p-5">
                                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                                    Tracking
                                </p>
                                <p className="text-3xl font-bold text-amber-600 mt-1">{opportunitiesMonitoring}</p>
                                <p className="text-xs text-muted-foreground mt-1">Internal trigger — watch for further growth</p>
                            </CardContent>
                        </Card>
                    </>
                )}
            </div>

            {/* ─── Tab Navigation ─── */}
            <Tabs value={activeTab} onValueChange={setActiveTab}>
                <div className="overflow-x-auto">
                    <TabsList className="w-max min-w-full sm:w-auto">
                        <TabsTrigger value="live">
                            <Activity className="h-3.5 w-3.5 mr-1.5" />
                            Opportunities ({opportunities.length})
                        </TabsTrigger>
                        <TabsTrigger value="database">
                            <Building2 className="h-3.5 w-3.5 mr-1.5" />
                            Company Database
                        </TabsTrigger>
                    </TabsList>
                </div>

                {/* ═══════════════════════════════════════════
                    TAB 1: Opportunities → Who to Approach
                   ═══════════════════════════════════════════ */}
                <TabsContent value="live" className="mt-6">
                    <div className="space-y-6">
                        {opportunitiesLoading ? (
                            <div className="space-y-4">
                                {[...Array(3)].map((_, i) => <ProjectCardSkeleton key={i} />)}
                            </div>
                        ) : opportunitiesError ? (
                            <ErrorCard message={opportunitiesError} onRetry={fetchOpportunities} />
                        ) : opportunities.length === 0 ? (
                            <Card>
                                <CardContent className="py-12 text-center">
                                    <p className="text-sm text-muted-foreground">No grievance clusters have reached the threshold yet.</p>
                                    <p className="text-xs text-muted-foreground/60 mt-2">
                                        Clusters appear here when enough complaints accumulate for the same issue and location.
                                    </p>
                                </CardContent>
                            </Card>
                        ) : (
                            <>
                                {/* Needs Field Verification (200+) */}
                                {opportunitiesReady > 0 && (
                                    <div className="space-y-3">
                                        <div className="flex items-center gap-2">
                                            <Badge variant="outline" className="border-primary text-primary bg-primary/5">Field Verification Needed</Badge>
                                            <span className="text-xs text-muted-foreground">Internal trigger only — verify the need before any company outreach</span>
                                        </div>
                                        <div className="space-y-4">
                                            {opportunities.filter(o => o.status === 'verify').map((opp, i) => (
                                                <OpportunityCard
                                                    key={i}
                                                    opp={opp}
                                                    statusColor="border-l-primary"
                                                    dprLoading={dprLoading}
                                                    onGenerateDPR={generateDPRFromOpportunity}
                                                    evidence={evidenceFiles[opp.category] || null}
                                                    onEvidenceChange={handleEvidenceChange}
                                                    fyWindow={fyWindow}
                                                />
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Tracking (100–199) */}
                                {opportunitiesMonitoring > 0 && (
                                    <div className="space-y-3">
                                        <div className="flex items-center gap-2">
                                            <Badge variant="outline" className="border-amber-500 text-amber-600 bg-amber-50">
                                                Tracking
                                            </Badge>
                                            <span className="text-xs text-muted-foreground">Growing cluster — watch for further increase</span>
                                        </div>
                                        <div className="space-y-4">
                                            {opportunities.filter(o => o.status === 'watch').map((opp, i) => (
                                                <OpportunityCard
                                                    key={i}
                                                    opp={opp}
                                                    statusColor="border-l-amber-500"
                                                    dprLoading={dprLoading}
                                                    onGenerateDPR={generateDPRFromOpportunity}
                                                    evidence={evidenceFiles[opp.category] || null}
                                                    onEvidenceChange={handleEvidenceChange}
                                                    fyWindow={fyWindow}
                                                />
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                </TabsContent>

                {/* ═══════════════════════════════════════════
                    TAB 2: Company Database
                   ═══════════════════════════════════════════ */}
                <TabsContent value="database" className="mt-6">
                    <div className="space-y-4">
                        {/* Search Bar */}
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                            <Input
                                type="text"
                                aria-label="Search companies"
                                placeholder="Search by company or focus area…"
                                value={search}
                                onChange={e => setSearch(e.target.value)}
                                className="pl-9"
                            />
                        </div>

                        {/* Sector Pill Filters */}
                        <div className="flex flex-wrap gap-2">
                            {CSR_PILLS.map(p => (
                                <Button
                                    key={p}
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setSelectedSector(p)}
                                    className={cn(
                                        "rounded-full h-7 text-xs",
                                        selectedSector === p && "bg-primary text-primary-foreground border-primary hover:bg-primary/90 hover:text-primary-foreground"
                                    )}
                                >
                                    {p}
                                </Button>
                            ))}
                        </div>

                        {/* Company Table */}
                        <Card>
                            {companiesLoading ? (
                                <CardContent className="py-6 space-y-2">
                                    {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
                                </CardContent>
                            ) : companiesError ? (
                                <CardContent className="py-4">
                                    <ErrorCard message={companiesError} onRetry={fetchCompanies} />
                                </CardContent>
                            ) : companies.length === 0 ? (
                                <CardContent className="py-14 text-center">
                                    <p className="text-sm text-muted-foreground">No companies found matching criteria.</p>
                                </CardContent>
                            ) : (
                                <div className="overflow-x-auto">
                                    <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead className="w-10 pl-6">#</TableHead>
                                                <TableHead>Company</TableHead>
                                                <TableHead>Sector</TableHead>
                                                <TableHead>Focus Area</TableHead>
                                                <TableHead>Budget</TableHead>
                                                <TableHead>Project Type</TableHead>
                                                <TableHead className="text-right">Action</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {companies.map((c, i) => (
                                                <TableRow key={i} className="group">
                                                    <TableCell className="pl-6 text-muted-foreground font-mono text-xs">{i + 1}</TableCell>
                                                    <TableCell>
                                                        {c.slug ? (
                                                            <button
                                                                onClick={() => router.push(`/dashboard/csr/company/${c.slug}`)}
                                                                className="font-semibold text-foreground hover:text-primary hover:underline text-left transition-colors"
                                                            >
                                                                {c.Company}
                                                            </button>
                                                        ) : (
                                                            <span className="font-semibold text-foreground">{c.Company}</span>
                                                        )}
                                                    </TableCell>
                                                    <TableCell className="text-muted-foreground">{c.Sector || 'N/A'}</TableCell>
                                                    <TableCell
                                                        className="text-muted-foreground max-w-[150px] truncate"
                                                        title={c.Gap_Analysis || 'Community Development'}
                                                    >
                                                        {c.Gap_Analysis || 'Community Development'}
                                                    </TableCell>
                                                    <TableCell className="font-mono text-xs text-foreground">
                                                        {c.total_3y_lakhs != null
                                                            ? `₹${c.total_3y_lakhs}L`
                                                            : c.Total_3Y || 'Undisclosed'}
                                                    </TableCell>
                                                    <TableCell>
                                                        <Badge
                                                            variant={c.status === 'zero_spend' ? 'destructive' : 'secondary'}
                                                            className="text-[10px] uppercase"
                                                        >
                                                            {c.status === 'zero_spend' ? 'Zero Spend' : (c.company_type === 'local' ? 'Local' : 'Remote')}
                                                        </Badge>
                                                        {fyWindow && <FYPill window={fyWindow.window} label={fyWindow.label} />}
                                                    </TableCell>
                                                    <TableCell className="text-right">
                                                        <div className="flex items-center justify-end gap-1.5">
                                                            {c.slug && (
                                                                <Button
                                                                    variant="ghost"
                                                                    size="sm"
                                                                    onClick={() => router.push(`/dashboard/csr/company/${c.slug}`)}
                                                                    className="text-xs h-7 px-2 opacity-0 group-hover:opacity-100 transition-opacity"
                                                                >
                                                                    View Profile
                                                                </Button>
                                                            )}
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                disabled={draftLoading === c.Company}
                                                                onClick={() => draftLetter(c)}
                                                                className="gap-1.5 whitespace-nowrap"
                                                            >
                                                                {draftLoading === c.Company
                                                                    ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Drafting…</>
                                                                    : 'Draft Letter'
                                                                }
                                                            </Button>
                                                        </div>
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </div>
                            )}
                        </Card>
                    </div>
                </TabsContent>

            </Tabs>

            {/* ═══════════════════════════════════════════
                Sheet — DPR / Draft Letter output
               ═══════════════════════════════════════════ */}
            <Sheet open={!!openSheet} onOpenChange={open => !open && setOpenSheet(null)}>
                {/* gap-0 overrides the base sheetVariants gap-4 which activates when we add flex flex-col */}
                <SheetContent side="right" className="w-full sm:max-w-xl p-0 flex flex-col gap-0">
                    {/* text-left overrides SheetHeader's default text-center sm:text-left */}
                    <SheetHeader className="px-6 py-4 border-b border-border shrink-0 text-left">
                        <SheetTitle className="text-base leading-snug pr-6">
                            {openSheet?.title}
                        </SheetTitle>
                        <SheetDescription>
                            {openSheet?.type === 'dpr'
                                ? 'Concept Note — pre-meeting document, review before sharing'
                                : 'AI-drafted letter — review and edit before sending'}
                        </SheetDescription>
                    </SheetHeader>

                    <ScrollArea className="flex-1 px-6 py-4">
                        {openSheet?.content ? (
                            <pre className="text-sm text-foreground bg-muted/50 rounded-lg border border-border p-4 whitespace-pre-wrap font-mono leading-relaxed">
                                {openSheet.content}
                            </pre>
                        ) : (
                            <div className="flex items-center gap-2 text-muted-foreground py-4">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                <span className="text-sm">Generating...</span>
                            </div>
                        )}
                    </ScrollArea>

                    {openSheet?.content && (
                        <SheetFooter className="px-6 py-4 border-t border-border shrink-0">
                            <Button variant="outline" onClick={() => setOpenSheet(null)}>
                                Close
                            </Button>
                            <Button
                                onClick={() => downloadText(
                                    openSheet.content,
                                    openSheet.type === 'dpr'
                                        ? `ConceptNote_${openSheet.key}.txt`
                                        : `CSR_Letter_${openSheet.key}.txt`
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
