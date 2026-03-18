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
    ChevronRight,
    ChevronDown,
    CheckCircle2,
    MapPin,
    Zap,
    Target,
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

// ─── Opportunity Card with embedded company recommendations ───
function OpportunityCard({ opp, statusColor, dprLoading, onGenerateDPR }) {
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
                    <Badge variant="outline" className={cn(
                        'shrink-0',
                        opp.status === 'ready'
                            ? 'border-destructive text-destructive bg-destructive/5'
                            : 'border-amber-500 text-amber-600 bg-amber-50',
                    )}>
                        {opp.volume} complaints
                    </Badge>
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
                                opp.status === 'ready' ? 'bg-destructive' : 'bg-amber-500')}
                            style={{ width: `${Math.min(100, opp.progress_pct || 0)}%` }}
                        />
                    </div>
                    <span className="text-xs font-mono text-muted-foreground">{opp.progress_pct || 0}%</span>
                </div>

                <div className="mt-2 flex items-center justify-between">
                    <p className="text-xs text-muted-foreground">
                        Sector: <span className="font-semibold text-foreground">{opp.csr_sector}</span>
                    </p>
                    {opp.velocity_7d > 0 && (
                        <span className="text-xs text-amber-600 flex items-center gap-1">
                            <Zap className="h-3 w-3" />+{opp.velocity_7d} this week
                        </span>
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
                                        {co.suggested_next_action === 'dpr' && (
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                className="h-7 text-xs gap-1.5"
                                                disabled={dprLoading === dprKey}
                                                onClick={() => onGenerateDPR(opp, co)}
                                            >
                                                {dprLoading === dprKey
                                                    ? <><Loader2 className="h-3 w-3 animate-spin" />Generating…</>
                                                    : 'Generate DPR'
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

export default function CSRPage() {
    const { user } = useAuth();
    const router = useRouter();

    // ─── Live Data State ───
    const [opportunities, setOpportunities] = useState([]);
    const [opportunitiesLoading, setOpportunitiesLoading] = useState(true);
    const [opportunitiesError, setOpportunitiesError] = useState(null);
    const [strategicMatches, setStrategicMatches] = useState([]);
    const [matchesLoading, setMatchesLoading] = useState(true);
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

    // ─── Fetch enriched opportunities with company recommendations ───
    const fetchOpportunities = async () => {
        setOpportunitiesLoading(true);
        setOpportunitiesError(null);
        try {
            const data = await apiGet('/api/csr/opportunities');
            setOpportunities(data.opportunities || []);
        } catch (err) {
            console.error('Opportunities fetch failed:', err);
            setOpportunitiesError('Failed to load opportunities.');
        } finally {
            setOpportunitiesLoading(false);
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

    useEffect(() => { fetchOpportunities(); }, []);
    useEffect(() => { fetchMatches(); }, []);

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

    // ─── Generate DPR from opportunity-first recommendation ───
    const generateDPRFromOpportunity = async (opp, company) => {
        const key = `${opp.category}-${company.name}`;
        setDprLoading(key);
        try {
            const data = await apiPost('/api/csr/generate-dpr', {
                category: opp.category,
                area: opp.area,
                volume: opp.volume,
                company: company.name,
                sector: company.sector || opp.csr_sector || '',
            }, { timeout: AI_TIMEOUT, noRetry: true });
            setOpenSheet({
                type: 'dpr',
                key,
                title: `DPR — ${opp.category} × ${company.name}`,
                content: data.content,
            });
        } catch {
            setOpenSheet({
                type: 'dpr',
                key,
                title: `DPR — ${company.name}`,
                content: 'Error generating DPR. Please try again.',
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

    const opportunitiesReady = opportunities.filter(o => o.status === 'ready').length;
    const opportunitiesMonitoring = opportunities.filter(o => o.status === 'monitoring').length;
    const totalMatches = strategicMatches.length;

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
                {opportunitiesLoading ? (
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
                                <p className="text-3xl font-bold text-destructive mt-1">{opportunitiesReady}</p>
                                <p className="text-xs text-muted-foreground mt-1">200+ verified complaints</p>
                            </CardContent>
                        </Card>
                        <Card className="border-l-4 border-l-amber-500">
                            <CardContent className="p-5">
                                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                                    Monitoring
                                </p>
                                <p className="text-3xl font-bold text-amber-600 mt-1">{opportunitiesMonitoring}</p>
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
            </div>

            {/* ─── Tab Navigation ─── */}
            <Tabs value={activeTab} onValueChange={setActiveTab}>
                <div className="overflow-x-auto">
                    <TabsList className="w-max min-w-full sm:w-auto">
                        <TabsTrigger value="live">
                            <Activity className="h-3.5 w-3.5 mr-1.5" />
                            Opportunities ({opportunities.length})
                        </TabsTrigger>
                        <TabsTrigger value="matches">
                            <TrendingUp className="h-3.5 w-3.5 mr-1.5" />
                            Strategic Matches ({totalMatches})
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
                                        Clusters appear here when 100+ complaints accumulate for the same issue and location.
                                    </p>
                                </CardContent>
                            </Card>
                        ) : (
                            <>
                                {/* CSR-Ready (200+) */}
                                {opportunitiesReady > 0 && (
                                    <div className="space-y-3">
                                        <div className="flex items-center gap-2">
                                            <Badge variant="destructive">CSR-Ready</Badge>
                                            <span className="text-xs text-muted-foreground">200+ verified complaints — pitch companies now</span>
                                        </div>
                                        <div className="space-y-4">
                                            {opportunities.filter(o => o.status === 'ready').map((opp, i) => (
                                                <OpportunityCard
                                                    key={i}
                                                    opp={opp}
                                                    statusColor="border-l-destructive"
                                                    dprLoading={dprLoading}
                                                    onGenerateDPR={generateDPRFromOpportunity}
                                                />
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Monitoring (100–199) */}
                                {opportunitiesMonitoring > 0 && (
                                    <div className="space-y-3">
                                        <div className="flex items-center gap-2">
                                            <Badge variant="outline" className="border-amber-500 text-amber-600 bg-amber-50">
                                                Monitoring
                                            </Badge>
                                            <span className="text-xs text-muted-foreground">Approaching threshold — identify companies early</span>
                                        </div>
                                        <div className="space-y-4">
                                            {opportunities.filter(o => o.status === 'monitoring').map((opp, i) => (
                                                <OpportunityCard
                                                    key={i}
                                                    opp={opp}
                                                    statusColor="border-l-amber-500"
                                                    dprLoading={dprLoading}
                                                    onGenerateDPR={generateDPRFromOpportunity}
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
