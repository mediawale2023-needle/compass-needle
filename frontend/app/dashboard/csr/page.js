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
function OpportunityCard({ opp, statusColor, dprLoading, onGenerateDPR, onScheduleMeeting, onFindNGO }) {
    return (
        <Card className={cn('border-l-4', statusColor)}>
            <CardContent className="p-4">
                {/* Header */}
                <div className="flex justify-between items-start">
                    <div>
                        <p className="font-semibold text-foreground">{opp.category}</p>
                        <p className="text-sm text-muted-foreground mt-0.5 flex items-center gap-1">
                            <MapPin className="h-3 w-3 shrink-0" />{opp.area}
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
                                        {co.suggested_next_action === 'dpr' ? (
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
                                        ) : co.suggested_next_action === 'meeting' ? (
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                className="h-7 text-xs gap-1.5 text-blue-700 border-blue-300 hover:bg-blue-50"
                                                onClick={() => onScheduleMeeting(co, opp)}
                                            >
                                                <Users className="h-3 w-3" />Add to Pipeline
                                            </Button>
                                        ) : (
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                className="h-7 text-xs gap-1.5 text-purple-700 border-purple-300 hover:bg-purple-50"
                                                onClick={onFindNGO}
                                            >
                                                <Users className="h-3 w-3" />Find NGO Partner
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
                                                    onScheduleMeeting={addToPipelineFromOpportunity}
                                                    onFindNGO={() => setActiveTab('ngo')}
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
                                                    onScheduleMeeting={addToPipelineFromOpportunity}
                                                    onFindNGO={() => setActiveTab('ngo')}
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

                {/* ═══════════════════════════════════════════
                    TAB 5: NGO Partner Directory
                   ═══════════════════════════════════════════ */}
                <TabsContent value="ngo" className="mt-6">
                    <div className="space-y-4">
                        <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
                            <div>
                                <h2 className="text-base font-semibold text-foreground">NGO Implementation Partners</h2>
                                <p className="text-xs text-muted-foreground mt-0.5">
                                    Pre-screened implementation partners for CSR projects. Green = verified, Red = flagged.
                                </p>
                            </div>
                            <div className="flex gap-2 flex-wrap">
                                <select
                                    className="text-xs border border-border rounded-md px-2 py-1.5 bg-background text-foreground"
                                    value={ngoRiskFilter}
                                    onChange={e => setNgoRiskFilter(e.target.value)}
                                >
                                    <option value="">All Risk Levels</option>
                                    <option value="Green">Green (Verified)</option>
                                    <option value="Yellow">Yellow (Unverified)</option>
                                    <option value="Red">Red (Flagged)</option>
                                </select>
                                <select
                                    className="text-xs border border-border rounded-md px-2 py-1.5 bg-background text-foreground"
                                    value={ngoSectorFilter}
                                    onChange={e => setNgoSectorFilter(e.target.value)}
                                >
                                    <option value="">All Sectors</option>
                                    {ngoSectors.map(s => (
                                        <option key={s} value={s}>{s}</option>
                                    ))}
                                </select>
                            </div>
                        </div>

                        {ngoLoading ? (
                            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                                {[1,2,3,4,5,6].map(i => <Skeleton key={i} className="h-32 rounded-lg" />)}
                            </div>
                        ) : ngoError ? (
                            <ErrorCard message={ngoError} onRetry={fetchNGOs} />
                        ) : ngoPartners.length === 0 ? (
                            <Card>
                                <CardContent className="py-12 text-center text-muted-foreground text-sm">
                                    No NGO partners found.
                                </CardContent>
                            </Card>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                                {ngoPartners.map((ngo, i) => {
                                    const isGreen = ngo.Risk_Level === 'Green';
                                    const isRed = ngo.Risk_Level === 'Red';
                                    return (
                                        <Card key={i} className={cn(
                                            "border-l-4",
                                            isGreen ? "border-l-emerald-500" : isRed ? "border-l-destructive" : "border-l-amber-400"
                                        )}>
                                            <CardContent className="p-4 space-y-2">
                                                <div className="flex items-start justify-between gap-2">
                                                    <p className="text-sm font-semibold text-foreground leading-snug">
                                                        {ngo.NGO_Name}
                                                    </p>
                                                    <Badge
                                                        variant={isGreen ? "default" : isRed ? "destructive" : "secondary"}
                                                        className="shrink-0 text-[10px]"
                                                    >
                                                        {isGreen ? (
                                                            <><CheckCircle2 className="h-2.5 w-2.5 mr-1" />{ngo.Risk_Level}</>
                                                        ) : isRed ? (
                                                            <><XCircle className="h-2.5 w-2.5 mr-1" />{ngo.Risk_Level}</>
                                                        ) : ngo.Risk_Level}
                                                    </Badge>
                                                </div>
                                                {ngo.Sector && (
                                                    <p className="text-xs text-muted-foreground">{ngo.Sector}</p>
                                                )}
                                                {ngo.Capabilities && (
                                                    <p className="text-xs text-foreground/70 line-clamp-2">{ngo.Capabilities}</p>
                                                )}
                                                <div className="flex gap-3 text-[10px] text-muted-foreground font-mono">
                                                    {ngo.Darpan_ID && <span>Darpan: {ngo.Darpan_ID}</span>}
                                                    {ngo.CSR_1_Number && <span>CSR-1: {ngo.CSR_1_Number}</span>}
                                                </div>
                                            </CardContent>
                                        </Card>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </TabsContent>

                {/* ═══════════════════════════════════════════
                    TAB 6: Analytics Dashboard
                   ═══════════════════════════════════════════ */}
                <TabsContent value="analytics" className="mt-6">
                    <div className="space-y-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <h2 className="text-base font-semibold text-foreground">CSR Intelligence Analytics</h2>
                                <p className="text-xs text-muted-foreground mt-0.5">
                                    Pipeline conversion, geographic heatmap, funding totals, and opportunity scoreboard.
                                </p>
                            </div>
                            <div className="flex items-center gap-2">
                                {syncMessage && (
                                    <span className="text-xs text-muted-foreground">{syncMessage}</span>
                                )}
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={triggerSync}
                                    disabled={syncLoading}
                                    className="gap-1.5"
                                >
                                    {syncLoading
                                        ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Syncing…</>
                                        : <><RefreshCw className="h-3.5 w-3.5" /> Sync Opportunities</>
                                    }
                                </Button>
                            </div>
                        </div>

                        {analyticsLoading ? (
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                {[1,2,3,4].map(i => <Skeleton key={i} className="h-24 rounded-lg" />)}
                            </div>
                        ) : analytics ? (
                            <>
                                {/* KPI Row */}
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                    <Card className="border-l-4 border-l-primary">
                                        <CardContent className="p-4">
                                            <p className="text-xs text-muted-foreground uppercase tracking-wide font-semibold">Companies in DB</p>
                                            <p className="text-2xl font-bold text-foreground mt-1">{analytics.total_companies_in_db ?? '—'}</p>
                                        </CardContent>
                                    </Card>
                                    <Card className="border-l-4 border-l-destructive">
                                        <CardContent className="p-4">
                                            <p className="text-xs text-muted-foreground uppercase tracking-wide font-semibold">Zero Spend Violators</p>
                                            <p className="text-2xl font-bold text-destructive mt-1">{analytics.watchdog_zero_spend_count ?? '—'}</p>
                                        </CardContent>
                                    </Card>
                                    <Card className="border-l-4 border-l-emerald-500">
                                        <CardContent className="p-4">
                                            <p className="text-xs text-muted-foreground uppercase tracking-wide font-semibold">Total Utilised (₹L)</p>
                                            <p className="text-2xl font-bold text-emerald-600 mt-1">
                                                {analytics.constituency_funding_totals?.total_utilised
                                                    ? `₹${analytics.constituency_funding_totals.total_utilised.toFixed(1)}L`
                                                    : '—'}
                                            </p>
                                        </CardContent>
                                    </Card>
                                    <Card className="border-l-4 border-l-amber-500">
                                        <CardContent className="p-4">
                                            <p className="text-xs text-muted-foreground uppercase tracking-wide font-semibold">Pipeline Potential (₹L)</p>
                                            <p className="text-2xl font-bold text-amber-600 mt-1">
                                                {analytics.pipeline_potential_lakhs
                                                    ? `₹${parseFloat(analytics.pipeline_potential_lakhs).toFixed(0)}L`
                                                    : '—'}
                                            </p>
                                        </CardContent>
                                    </Card>
                                </div>

                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                    {/* Pipeline Funnel */}
                                    {analytics.pipeline_funnel?.length > 0 && (
                                        <Card>
                                            <CardHeader className="pb-3">
                                                <CardTitle className="text-sm font-semibold flex items-center gap-1.5">
                                                    <Target className="h-4 w-4 text-primary" />
                                                    Pipeline Funnel
                                                </CardTitle>
                                            </CardHeader>
                                            <CardContent className="space-y-2">
                                                {analytics.pipeline_funnel.map((stage, i) => (
                                                    <div key={stage.stage} className="flex items-center gap-3">
                                                        <span className="text-xs text-muted-foreground w-28 shrink-0 capitalize">
                                                            {stage.stage.replace('_', ' ')}
                                                        </span>
                                                        <div className="flex-1 bg-muted rounded-full h-2">
                                                            <div
                                                                className="h-2 rounded-full bg-primary transition-all"
                                                                style={{
                                                                    width: `${Math.max(4, (stage.count / Math.max(...analytics.pipeline_funnel.map(s => s.count), 1)) * 100)}%`
                                                                }}
                                                            />
                                                        </div>
                                                        <span className="text-xs font-mono text-foreground w-8 text-right">{stage.count}</span>
                                                    </div>
                                                ))}
                                            </CardContent>
                                        </Card>
                                    )}

                                    {/* Top Sectors */}
                                    {analytics.top_sectors?.length > 0 && (
                                        <Card>
                                            <CardHeader className="pb-3">
                                                <CardTitle className="text-sm font-semibold flex items-center gap-1.5">
                                                    <Zap className="h-4 w-4 text-amber-500" />
                                                    Top Grievance Sectors
                                                </CardTitle>
                                            </CardHeader>
                                            <CardContent className="space-y-2">
                                                {analytics.top_sectors.slice(0, 6).map((s, i) => (
                                                    <div key={s.category} className="flex items-center gap-3">
                                                        <span className="text-xs text-muted-foreground w-32 shrink-0 truncate" title={s.category}>
                                                            {s.category}
                                                        </span>
                                                        <div className="flex-1 bg-muted rounded-full h-2">
                                                            <div
                                                                className="h-2 rounded-full bg-amber-500 transition-all"
                                                                style={{
                                                                    width: `${Math.max(4, (s.total_volume / Math.max(...analytics.top_sectors.map(x => x.total_volume), 1)) * 100)}%`
                                                                }}
                                                            />
                                                        </div>
                                                        <span className="text-xs font-mono text-foreground w-10 text-right">{s.total_volume}</span>
                                                    </div>
                                                ))}
                                            </CardContent>
                                        </Card>
                                    )}

                                    {/* Opportunity Scoreboard */}
                                    {analytics.opportunity_scoreboard?.length > 0 && (
                                        <Card className="lg:col-span-2">
                                            <CardHeader className="pb-3">
                                                <CardTitle className="text-sm font-semibold flex items-center gap-1.5">
                                                    <TrendingUp className="h-4 w-4 text-primary" />
                                                    Opportunity Scoreboard
                                                </CardTitle>
                                                <CardDescription className="text-xs">Top-scored clusters ranked by opportunity score (0–100)</CardDescription>
                                            </CardHeader>
                                            <CardContent>
                                                <div className="space-y-2">
                                                    {analytics.opportunity_scoreboard.map((opp, i) => (
                                                        <div key={i} className="flex items-center gap-3 p-2 rounded-lg hover:bg-muted/50 transition-colors">
                                                            <span className="text-xs font-mono text-muted-foreground w-4">{i + 1}</span>
                                                            <div className="flex-1 min-w-0">
                                                                <p className="text-sm font-medium text-foreground truncate">
                                                                    {opp.category}
                                                                </p>
                                                                <p className="text-xs text-muted-foreground flex items-center gap-1">
                                                                    <MapPin className="h-3 w-3" />
                                                                    {opp.location || 'Unknown'} · {opp.complaint_count} complaints
                                                                </p>
                                                            </div>
                                                            <div className="flex items-center gap-2 shrink-0">
                                                                <Badge
                                                                    variant={opp.status === 'ready' ? 'default' : 'secondary'}
                                                                    className="text-[10px]"
                                                                >
                                                                    {opp.status}
                                                                </Badge>
                                                                <span className="text-sm font-bold text-primary w-10 text-right">
                                                                    {opp.opportunity_score?.toFixed(0)}
                                                                </span>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            </CardContent>
                                        </Card>
                                    )}

                                    {/* Geographic Heatmap */}
                                    {analytics.geographic_heatmap?.length > 0 && (
                                        <Card className="lg:col-span-2">
                                            <CardHeader className="pb-3">
                                                <CardTitle className="text-sm font-semibold flex items-center gap-1.5">
                                                    <MapPin className="h-4 w-4 text-blue-500" />
                                                    Geographic Heatmap
                                                </CardTitle>
                                                <CardDescription className="text-xs">Complaint volume by area — highest priority zones</CardDescription>
                                            </CardHeader>
                                            <CardContent>
                                                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                                                    {analytics.geographic_heatmap.slice(0, 16).map((area, i) => {
                                                        const maxComplaints = analytics.geographic_heatmap[0]?.total_complaints || 1;
                                                        const intensity = area.total_complaints / maxComplaints;
                                                        return (
                                                            <div
                                                                key={area.district}
                                                                className="rounded-lg p-3 text-center"
                                                                style={{
                                                                    backgroundColor: `rgba(239, 68, 68, ${0.1 + intensity * 0.6})`,
                                                                    border: `1px solid rgba(239, 68, 68, ${0.2 + intensity * 0.5})`
                                                                }}
                                                            >
                                                                <p className="text-xs font-semibold text-foreground truncate" title={area.district}>
                                                                    {area.district || 'Unknown'}
                                                                </p>
                                                                <p className="text-lg font-bold text-foreground">{area.total_complaints}</p>
                                                                <p className="text-[10px] text-muted-foreground">{area.cluster_count} clusters</p>
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            </CardContent>
                                        </Card>
                                    )}

                                    {/* Beneficiary Impact */}
                                    {analytics.constituency_funding_totals?.total_beneficiaries > 0 && (
                                        <Card>
                                            <CardHeader className="pb-3">
                                                <CardTitle className="text-sm font-semibold">Constituency Impact</CardTitle>
                                            </CardHeader>
                                            <CardContent className="grid grid-cols-2 gap-4">
                                                <div>
                                                    <p className="text-xs text-muted-foreground">Total Projects</p>
                                                    <p className="text-2xl font-bold text-foreground">
                                                        {analytics.constituency_funding_totals.project_count || 0}
                                                    </p>
                                                </div>
                                                <div>
                                                    <p className="text-xs text-muted-foreground">Beneficiaries</p>
                                                    <p className="text-2xl font-bold text-emerald-600">
                                                        {(analytics.constituency_funding_totals.total_beneficiaries || 0).toLocaleString()}
                                                    </p>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    )}
                                </div>
                            </>
                        ) : (
                            <Card>
                                <CardContent className="py-12 text-center text-sm text-muted-foreground">
                                    No analytics data available. Click "Sync Opportunities" to generate.
                                </CardContent>
                            </Card>
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
