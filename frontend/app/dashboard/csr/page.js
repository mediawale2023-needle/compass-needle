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
    Download,
    RefreshCw,
    TrendingUp,
    Activity,
    Building2,
    Kanban,
    Plus,
    ChevronRight,
    Trash2,
} from 'lucide-react';

const CSR_PILLS = ['All', 'Steel & Mining', 'Information Technology', 'Banking & Finance', 'Healthcare', 'Energy', 'Automobile'];

const PIPELINE_STAGES = [
    { key: 'identified', label: 'Identified', color: 'text-muted-foreground border-border' },
    { key: 'contacted', label: 'Contacted', color: 'text-blue-700 border-blue-300' },
    { key: 'proposal_sent', label: 'Proposal Sent', color: 'text-amber-700 border-amber-400' },
    { key: 'negotiating', label: 'Negotiating', color: 'text-purple-700 border-purple-400' },
    { key: 'approved', label: 'Approved', color: 'text-emerald-700 border-emerald-400' },
    { key: 'funded', label: 'Funded', color: 'text-emerald-800 border-emerald-600' },
];

const STAGE_NEXT = {
    identified: 'contacted',
    contacted: 'proposal_sent',
    proposal_sent: 'negotiating',
    negotiating: 'approved',
    approved: 'funded',
    funded: null,
};

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

export default function CSRPage() {
    const { user } = useAuth();
    const router = useRouter();

    // ─── Live Data State ───
    const [proposals, setProposals] = useState({ candidates: [], monitoring: [] });
    const [strategicMatches, setStrategicMatches] = useState([]);
    const [proposalsLoading, setProposalsLoading] = useState(true);
    const [matchesLoading, setMatchesLoading] = useState(true);
    const [proposalsError, setProposalsError] = useState(null);
    const [matchesError, setMatchesError] = useState(null);

    // ─── Company Database State ───
    const [companies, setCompanies] = useState([]);
    const [search, setSearch] = useState('');
    const [selectedSector, setSelectedSector] = useState('All');
    const [companiesLoading, setCompaniesLoading] = useState(true);
    const [companiesError, setCompaniesError] = useState(null);

    // ─── Draft / DPR State ───
    const [draftLoading, setDraftLoading] = useState(null);
    const [dprLoading, setDprLoading] = useState(null);

    // ─── Sheet State ───
    const [openSheet, setOpenSheet] = useState(null); // { type: 'dpr'|'draft', key, title, content }

    // ─── Tab State ───
    const [activeTab, setActiveTab] = useState('live');

    // ─── Pipeline State ───
    const [pipelineByStage, setPipelineByStage] = useState({});
    const [pipelineLoading, setPipelineLoading] = useState(false);
    const [pipelineError, setPipelineError] = useState(null);
    const [addingToStage, setAddingToStage] = useState(null); // stage key when add form is open
    const [newCompanyName, setNewCompanyName] = useState('');
    const [newCompanySector, setNewCompanySector] = useState('');
    const [addLoading, setAddLoading] = useState(false);
    const [movingId, setMovingId] = useState(null);

    // ─── Fetch live proposals from grievance data ───
    const fetchProposals = async () => {
        setProposalsLoading(true);
        setProposalsError(null);
        try {
            const data = await apiGet('/api/csr/proposals');
            setProposals({
                candidates: data.candidates || [],
                monitoring: data.monitoring || [],
            });
        } catch (err) {
            console.error('Proposals fetch failed:', err);
            setProposalsError('Failed to load live grievance data.');
        } finally {
            setProposalsLoading(false);
        }
    };

    // ─── Fetch strategic matches (live gaps ↔ CSR companies) ───
    const fetchMatches = async () => {
        setMatchesLoading(true);
        setMatchesError(null);
        try {
            const data = await apiPost('/api/csr/strategic-matches', {});
            setStrategicMatches(data.matches || []);
        } catch (err) {
            console.error('Strategic matches fetch failed:', err);
            setMatchesError('Failed to load strategic matches.');
        } finally {
            setMatchesLoading(false);
        }
    };

    useEffect(() => { fetchProposals(); }, []);
    useEffect(() => { fetchMatches(); }, []);

    // ─── Pipeline helpers ───
    const fetchPipeline = async () => {
        setPipelineLoading(true);
        setPipelineError(null);
        try {
            const data = await apiGet('/api/csr/pipeline');
            setPipelineByStage(data.by_stage || {});
        } catch {
            setPipelineError('Failed to load pipeline.');
        } finally {
            setPipelineLoading(false);
        }
    };
    useEffect(() => { fetchPipeline(); }, []);

    const addToPipeline = async (stage) => {
        if (!newCompanyName.trim()) return;
        setAddLoading(true);
        try {
            await apiPost('/api/csr/pipeline', {
                company_name: newCompanyName.trim(),
                sector: newCompanySector.trim(),
                stage,
            });
            setNewCompanyName('');
            setNewCompanySector('');
            setAddingToStage(null);
            await fetchPipeline();
        } catch {
            // keep form open on failure
        } finally {
            setAddLoading(false);
        }
    };

    const moveToNextStage = async (entry) => {
        const next = STAGE_NEXT[entry.stage];
        if (!next) return;
        setMovingId(entry.id);
        try {
            await apiPatch(`/api/csr/pipeline/${entry.id}`, { stage: next });
            await fetchPipeline();
        } catch {
            // silently fail, user can retry
        } finally {
            setMovingId(null);
        }
    };

    const deleteEntry = async (id) => {
        try {
            await apiDelete(`/api/csr/pipeline/${id}`);
            await fetchPipeline();
        } catch {
            // silently fail
        }
    };

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

    // ─── Generate DPR from live data ───
    const generateDPR = async (match, company) => {
        const key = `${match.category}-${company.Company}`;
        setDprLoading(key);
        try {
            const data = await apiPost('/api/csr/generate-dpr', {
                category: match.category,
                area: match.area,
                volume: match.volume,
                company: company.Company,
                sector: company.Sector || '',
            }, { timeout: AI_TIMEOUT, noRetry: true });
            const content = data.content;
            setOpenSheet({
                type: 'dpr',
                key,
                title: `DPR — ${match.category} × ${company.Company}`,
                content,
            });
        } catch (err) {
            setOpenSheet({
                type: 'dpr',
                key,
                title: `DPR — ${company.Company}`,
                content: 'Error generating DPR. Please try again.',
            });
        } finally {
            setDprLoading(null);
        }
    };

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

    const downloadText = (text, filename) => {
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = filename; a.click();
        URL.revokeObjectURL(url);
    };

    const totalCandidates = proposals.candidates.length;
    const totalMonitoring = proposals.monitoring.length;
    const totalMatches = strategicMatches.length;
    const totalPipeline = Object.values(pipelineByStage).reduce((sum, arr) => sum + arr.length, 0);
    const fundedCount = (pipelineByStage['funded'] || []).length;

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-foreground">CSR Intelligence</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Match constituency needs to corporate social responsibility opportunities
                </p>
            </div>

            {/* ─── Summary Stats ─── */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {proposalsLoading ? (
                    <>
                        <StatSkeleton />
                        <StatSkeleton />
                    </>
                ) : (
                    <>
                        <Card className="border-l-4 border-l-destructive">
                            <CardContent className="p-5">
                                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                                    CSR-Ready Projects
                                </p>
                                <p className="text-3xl font-bold text-destructive mt-1">{totalCandidates}</p>
                                <p className="text-xs text-muted-foreground mt-1">200+ verified complaints</p>
                            </CardContent>
                        </Card>
                        <Card className="border-l-4 border-l-amber-500">
                            <CardContent className="p-5">
                                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                                    Monitoring
                                </p>
                                <p className="text-3xl font-bold text-amber-600 mt-1">{totalMonitoring}</p>
                                <p className="text-xs text-muted-foreground mt-1">100–199 complaints, approaching threshold</p>
                            </CardContent>
                        </Card>
                    </>
                )}
                {matchesLoading ? (
                    <StatSkeleton />
                ) : (
                    <Card className="border-l-4 border-l-primary">
                        <CardContent className="p-5">
                            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                                Strategic Matches
                            </p>
                            <p className="text-3xl font-bold text-primary mt-1">{totalMatches}</p>
                            <p className="text-xs text-muted-foreground mt-1">Live gaps matched to CSR companies</p>
                        </CardContent>
                    </Card>
                )}
                {pipelineLoading ? (
                    <StatSkeleton />
                ) : (
                    <Card className="border-l-4 border-l-emerald-500">
                        <CardContent className="p-5">
                            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                                Pipeline
                            </p>
                            <p className="text-3xl font-bold text-emerald-600 mt-1">{totalPipeline}</p>
                            <p className="text-xs text-muted-foreground mt-1">
                                {fundedCount > 0 ? `${fundedCount} funded` : 'Companies being tracked'}
                            </p>
                        </CardContent>
                    </Card>
                )}
            </div>

            {/* ─── Tab Navigation ─── */}
            <Tabs value={activeTab} onValueChange={setActiveTab}>
                <div className="overflow-x-auto">
                    <TabsList className="w-max min-w-full sm:w-auto">
                        <TabsTrigger value="live">
                            <Activity className="h-3.5 w-3.5 mr-1.5" />
                            Live Projects ({totalCandidates + totalMonitoring})
                        </TabsTrigger>
                        <TabsTrigger value="matches">
                            <TrendingUp className="h-3.5 w-3.5 mr-1.5" />
                            Strategic Matches ({totalMatches})
                        </TabsTrigger>
                        <TabsTrigger value="database">
                            <Building2 className="h-3.5 w-3.5 mr-1.5" />
                            Company Database
                        </TabsTrigger>
                        <TabsTrigger value="pipeline">
                            <Kanban className="h-3.5 w-3.5 mr-1.5" />
                            Pipeline
                        </TabsTrigger>
                    </TabsList>
                </div>

                {/* ═══════════════════════════════════════════
                    TAB 1: Live Grievance Clusters → CSR Projects
                   ═══════════════════════════════════════════ */}
                <TabsContent value="live" className="mt-6">
                    <div className="space-y-6">
                        {proposalsLoading ? (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {[...Array(4)].map((_, i) => <ProjectCardSkeleton key={i} />)}
                            </div>
                        ) : proposalsError ? (
                            <ErrorCard message={proposalsError} onRetry={fetchProposals} />
                        ) : totalCandidates === 0 && totalMonitoring === 0 ? (
                            <Card>
                                <CardContent className="py-12 text-center">
                                    <p className="text-sm text-muted-foreground">No grievance clusters have reached the threshold yet.</p>
                                    <p className="text-xs text-muted-foreground/60 mt-2">
                                        Clusters appear here when 100+ complaints accumulate for the same issue and location.
                                    </p>
                                </CardContent>
                            </Card>
                        ) : (
                            <>
                                {/* CSR-Ready (200+) */}
                                {totalCandidates > 0 && (
                                    <div className="space-y-3">
                                        <div className="flex items-center gap-2">
                                            <Badge variant="destructive">CSR-Ready</Badge>
                                            <span className="text-xs text-muted-foreground">200+ verified complaints</span>
                                        </div>
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                            {proposals.candidates.map((c, i) => (
                                                <Card key={i} className="border-l-4 border-l-destructive">
                                                    <CardContent className="p-4">
                                                        <div className="flex justify-between items-start">
                                                            <div>
                                                                <p className="font-semibold text-foreground">{c.category}</p>
                                                                <p className="text-sm text-muted-foreground mt-0.5">{c.area}</p>
                                                            </div>
                                                            <Badge variant="outline" className="border-destructive text-destructive bg-destructive/5 shrink-0">
                                                                {c.volume} complaints
                                                            </Badge>
                                                        </div>
                                                        <div className="mt-3 flex items-center gap-3">
                                                            <div className="flex-1 h-2 bg-secondary rounded-full overflow-hidden">
                                                                <div
                                                                    className="h-full rounded-full bg-destructive transition-all"
                                                                    style={{ width: `${Math.min(100, c.progress_pct)}%` }}
                                                                />
                                                            </div>
                                                            <span className="text-xs font-mono text-muted-foreground">{c.progress_pct}%</span>
                                                        </div>
                                                        <div className="mt-2 flex items-center justify-between">
                                                            <p className="text-xs text-muted-foreground">
                                                                Sector: <span className="font-semibold text-foreground">{c.csr_sector}</span>
                                                            </p>
                                                            {c.opportunity_score != null && (
                                                                <span className="text-xs font-mono text-primary">
                                                                    Score {c.opportunity_score}
                                                                </span>
                                                            )}
                                                        </div>
                                                        {c.velocity_7d > 0 && (
                                                            <p className="mt-1 text-xs text-amber-600">
                                                                +{c.velocity_7d} in last 7 days
                                                            </p>
                                                        )}
                                                    </CardContent>
                                                </Card>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Monitoring (100–199) */}
                                {totalMonitoring > 0 && (
                                    <div className="space-y-3">
                                        <div className="flex items-center gap-2">
                                            <Badge variant="outline" className="border-amber-500 text-amber-600 bg-amber-50">
                                                Monitoring
                                            </Badge>
                                            <span className="text-xs text-muted-foreground">Approaching threshold</span>
                                        </div>
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                            {proposals.monitoring.map((c, i) => (
                                                <Card key={i} className="border-l-4 border-l-amber-500">
                                                    <CardContent className="p-4">
                                                        <div className="flex justify-between items-start">
                                                            <div>
                                                                <p className="font-semibold text-foreground">{c.category}</p>
                                                                <p className="text-sm text-muted-foreground mt-0.5">{c.area}</p>
                                                            </div>
                                                            <Badge variant="outline" className="border-amber-500 text-amber-600 bg-amber-50 shrink-0">
                                                                {c.volume} complaints
                                                            </Badge>
                                                        </div>
                                                        <div className="mt-3 flex items-center gap-3">
                                                            <div className="flex-1 h-2 bg-secondary rounded-full overflow-hidden">
                                                                <div
                                                                    className="h-full rounded-full bg-amber-500 transition-all"
                                                                    style={{ width: `${Math.min(100, c.progress_pct)}%` }}
                                                                />
                                                            </div>
                                                            <span className="text-xs font-mono text-muted-foreground">{c.progress_pct}%</span>
                                                        </div>
                                                        <div className="mt-2 flex items-center justify-between">
                                                            <p className="text-xs text-muted-foreground">
                                                                Sector: <span className="font-semibold text-foreground">{c.csr_sector}</span>
                                                            </p>
                                                            {c.opportunity_score != null && (
                                                                <span className="text-xs font-mono text-amber-600">
                                                                    Score {c.opportunity_score}
                                                                </span>
                                                            )}
                                                        </div>
                                                        {c.velocity_7d > 0 && (
                                                            <p className="mt-1 text-xs text-amber-600">
                                                                +{c.velocity_7d} in last 7 days
                                                            </p>
                                                        )}
                                                    </CardContent>
                                                </Card>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                </TabsContent>

                {/* ═══════════════════════════════════════════
                    TAB 2: Strategic Matches (Live Gaps ↔ Companies)
                   ═══════════════════════════════════════════ */}
                <TabsContent value="matches" className="mt-6">
                    <div className="space-y-4">
                        {matchesLoading ? (
                            <div className="space-y-4">
                                {[...Array(2)].map((_, i) => (
                                    <Card key={i}>
                                        <CardHeader className="pb-3">
                                            <div className="flex items-center gap-2">
                                                <Skeleton className="h-5 w-32" />
                                                <Skeleton className="h-5 w-16 rounded-full" />
                                            </div>
                                            <Skeleton className="h-3 w-48 mt-1" />
                                        </CardHeader>
                                        <CardContent>
                                            <div className="space-y-2">
                                                {[...Array(3)].map((_, j) => <Skeleton key={j} className="h-10 w-full" />)}
                                            </div>
                                        </CardContent>
                                    </Card>
                                ))}
                            </div>
                        ) : matchesError ? (
                            <ErrorCard message={matchesError} onRetry={fetchMatches} />
                        ) : strategicMatches.length === 0 ? (
                            <Card>
                                <CardContent className="py-12 text-center">
                                    <p className="text-sm text-muted-foreground">No strategic matches found yet.</p>
                                    <p className="text-xs text-muted-foreground/60 mt-2">
                                        Matches appear when grievance clusters (100+ complaints) can be mapped to CSR-eligible companies.
                                    </p>
                                </CardContent>
                            </Card>
                        ) : (
                            strategicMatches.map((match, mi) => {
                                const isCritical = match.badge === 'CRITICAL';
                                const isMajor = match.badge === 'MAJOR';
                                return (
                                    <Card key={mi}>
                                        <CardHeader className="pb-3">
                                            <div className="flex flex-wrap items-center justify-between gap-2">
                                                <div>
                                                    <div className="flex items-center gap-2">
                                                        <CardTitle className="text-base">{match.category}</CardTitle>
                                                        <Badge variant={isCritical ? 'destructive' : 'outline'} className={cn(
                                                            !isCritical && isMajor && "border-amber-500 text-amber-600 bg-amber-50",
                                                            !isCritical && !isMajor && "border-blue-400 text-blue-700 bg-blue-50",
                                                        )}>
                                                            {match.badge}
                                                        </Badge>
                                                    </div>
                                                    <CardDescription className="mt-1">
                                                        {match.area} · <span className="font-semibold">{match.volume}</span> verified complaints
                                                    </CardDescription>
                                                </div>
                                                <p className="text-xs text-muted-foreground">
                                                    Matched sectors: {match.matched_sectors?.join(', ')}
                                                </p>
                                            </div>
                                        </CardHeader>
                                        <CardContent className="pt-0">
                                            {match.matched_companies?.length > 0 ? (
                                                <div className="overflow-x-auto rounded-md border border-border">
                                                    <Table>
                                                        <TableHeader>
                                                            <TableRow>
                                                                <TableHead>Company</TableHead>
                                                                <TableHead>Sector</TableHead>
                                                                <TableHead>3Y Spend</TableHead>
                                                                <TableHead>District</TableHead>
                                                                <TableHead className="text-right">Action</TableHead>
                                                            </TableRow>
                                                        </TableHeader>
                                                        <TableBody>
                                                            {match.matched_companies.map((comp, ci) => {
                                                                const dprKey = `${match.category}-${comp.Company}`;
                                                                return (
                                                                    <TableRow key={ci}>
                                                                        <TableCell className="font-semibold text-foreground">{comp.Company}</TableCell>
                                                                        <TableCell className="text-muted-foreground">{comp.Sector || 'N/A'}</TableCell>
                                                                        <TableCell className="font-mono text-xs text-foreground">{comp.Total_3Y || 'N/A'}</TableCell>
                                                                        <TableCell className="text-muted-foreground">{comp.District || '—'}</TableCell>
                                                                        <TableCell className="text-right">
                                                                            <Button
                                                                                variant="outline"
                                                                                size="sm"
                                                                                disabled={dprLoading === dprKey}
                                                                                onClick={() => generateDPR(match, comp)}
                                                                                className="gap-1.5 whitespace-nowrap"
                                                                            >
                                                                                {dprLoading === dprKey
                                                                                    ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Generating…</>
                                                                                    : 'Generate DPR'
                                                                                }
                                                                            </Button>
                                                                        </TableCell>
                                                                    </TableRow>
                                                                );
                                                            })}
                                                        </TableBody>
                                                    </Table>
                                                </div>
                                            ) : (
                                                <p className="text-xs text-muted-foreground italic">
                                                    No matching companies found in the database for this sector.
                                                </p>
                                            )}
                                        </CardContent>
                                    </Card>
                                );
                            })
                        )}
                    </div>
                </TabsContent>

                {/* ═══════════════════════════════════════════
                    TAB 3: Company Database (existing static data)
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

                {/* ═══════════════════════════════════════════
                    TAB 4: Funding Pipeline Board
                   ═══════════════════════════════════════════ */}
                <TabsContent value="pipeline" className="mt-6">
                    <div className="space-y-4">
                        <div>
                            <p className="text-sm text-muted-foreground">
                                Track companies through your CSR funding relationship pipeline.
                            </p>
                        </div>

                        {pipelineLoading ? (
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                                {[...Array(3)].map((_, i) => (
                                    <Card key={i}>
                                        <CardHeader className="pb-2">
                                            <Skeleton className="h-4 w-24" />
                                        </CardHeader>
                                        <CardContent className="space-y-2">
                                            {[...Array(2)].map((_, j) => <Skeleton key={j} className="h-16 w-full rounded-lg" />)}
                                        </CardContent>
                                    </Card>
                                ))}
                            </div>
                        ) : pipelineError ? (
                            <ErrorCard message={pipelineError} onRetry={fetchPipeline} />
                        ) : (
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                                {PIPELINE_STAGES.map(stage => {
                                    const entries = pipelineByStage[stage.key] || [];
                                    const isAdding = addingToStage === stage.key;
                                    return (
                                        <Card key={stage.key} className="flex flex-col">
                                            <CardHeader className="pb-3 shrink-0">
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-2">
                                                        <Badge variant="outline" className={cn("text-xs", stage.color)}>
                                                            {stage.label}
                                                        </Badge>
                                                        <span className="text-xs text-muted-foreground font-mono">
                                                            {entries.length}
                                                        </span>
                                                    </div>
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-6 w-6"
                                                        onClick={() => setAddingToStage(isAdding ? null : stage.key)}
                                                        aria-label={`Add to ${stage.label}`}
                                                    >
                                                        <Plus className="h-3.5 w-3.5" />
                                                    </Button>
                                                </div>
                                            </CardHeader>
                                            <CardContent className="flex-1 space-y-2 pt-0">
                                                {/* Add form */}
                                                {isAdding && (
                                                    <div className="border border-dashed border-border rounded-lg p-3 space-y-2 bg-muted/30">
                                                        <Input
                                                            placeholder="Company name"
                                                            value={newCompanyName}
                                                            onChange={e => setNewCompanyName(e.target.value)}
                                                            className="h-7 text-sm"
                                                            autoFocus
                                                        />
                                                        <Input
                                                            placeholder="Sector (optional)"
                                                            value={newCompanySector}
                                                            onChange={e => setNewCompanySector(e.target.value)}
                                                            className="h-7 text-sm"
                                                        />
                                                        <div className="flex gap-2">
                                                            <Button
                                                                size="sm"
                                                                className="h-7 text-xs flex-1"
                                                                disabled={addLoading || !newCompanyName.trim()}
                                                                onClick={() => addToPipeline(stage.key)}
                                                            >
                                                                {addLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Add'}
                                                            </Button>
                                                            <Button
                                                                variant="ghost"
                                                                size="sm"
                                                                className="h-7 text-xs"
                                                                onClick={() => { setAddingToStage(null); setNewCompanyName(''); setNewCompanySector(''); }}
                                                            >
                                                                Cancel
                                                            </Button>
                                                        </div>
                                                    </div>
                                                )}

                                                {/* Entry cards */}
                                                {entries.length === 0 && !isAdding ? (
                                                    <p className="text-xs text-muted-foreground/60 text-center py-4 italic">
                                                        No companies here yet
                                                    </p>
                                                ) : (
                                                    entries.map(entry => {
                                                        const nextStage = STAGE_NEXT[entry.stage];
                                                        const nextLabel = nextStage
                                                            ? PIPELINE_STAGES.find(s => s.key === nextStage)?.label
                                                            : null;
                                                        return (
                                                            <div
                                                                key={entry.id}
                                                                className="border border-border rounded-lg p-3 bg-card space-y-1.5 group"
                                                            >
                                                                <div className="flex items-start justify-between gap-2">
                                                                    <p className="text-sm font-semibold text-foreground leading-snug">
                                                                        {entry.company_name}
                                                                    </p>
                                                                    <button
                                                                        onClick={() => deleteEntry(entry.id)}
                                                                        className="shrink-0 text-muted-foreground/40 hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
                                                                        aria-label="Remove from pipeline"
                                                                    >
                                                                        <Trash2 className="h-3.5 w-3.5" />
                                                                    </button>
                                                                </div>
                                                                {entry.sector && (
                                                                    <p className="text-xs text-muted-foreground">{entry.sector}</p>
                                                                )}
                                                                {entry.estimated_amount && (
                                                                    <p className="text-xs font-mono text-foreground">{entry.estimated_amount}</p>
                                                                )}
                                                                {nextLabel && (
                                                                    <Button
                                                                        variant="ghost"
                                                                        size="sm"
                                                                        className="h-6 text-xs w-full justify-start gap-1 text-muted-foreground hover:text-foreground px-0"
                                                                        disabled={movingId === entry.id}
                                                                        onClick={() => moveToNextStage(entry)}
                                                                    >
                                                                        {movingId === entry.id
                                                                            ? <Loader2 className="h-3 w-3 animate-spin" />
                                                                            : <ChevronRight className="h-3 w-3" />
                                                                        }
                                                                        Move to {nextLabel}
                                                                    </Button>
                                                                )}
                                                            </div>
                                                        );
                                                    })
                                                )}
                                            </CardContent>
                                        </Card>
                                    );
                                })}
                            </div>
                        )}
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
                                ? 'Detailed Project Report — review before submitting'
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
                                <span className="text-sm">Generating…</span>
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
                                        ? `DPR_${openSheet.key}.txt`
                                        : `CSR_Proposal_${openSheet.key}.txt`
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
