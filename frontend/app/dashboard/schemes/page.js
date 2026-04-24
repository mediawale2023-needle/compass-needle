'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPost, AI_TIMEOUT } from '@/lib/api';
import { useRouter, useSearchParams } from 'next/navigation';
import {
    Lock, ChevronRight, ChevronLeft, Loader2, RefreshCw,
    Building2, FileText, TrendingUp, AlertTriangle,
    BarChart3, CircleDot, Search,
    MapPin, Globe, ArrowLeftRight, Wrench
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

function LockedModule() {
    return (
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-center px-6">
            <div className="h-16 w-16 rounded-full bg-muted flex items-center justify-center">
                <Lock className="h-7 w-7 text-muted-foreground" />
            </div>
            <div>
                <h2 className="text-lg font-semibold text-foreground">Scheme Intelligence is restricted</h2>
                <p className="text-sm text-muted-foreground mt-1">Available to the MP only.</p>
            </div>
        </div>
    );
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function shortMinistry(name) {
    return (name || '')
        .replace(/^Ministry of\s+/i, '')
        .replace(/^Department of\s+/i, 'Dept. of ')
        .replace(/^Ministry for\s+/i, '');
}

function formatDate(d) {
    if (!d) return null;
    try {
        return new Date(d).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' });
    } catch { return d; }
}

function answerBand(count) {
    if (!count || count === 0)
        return { label: 'No Data',   color: 'bg-muted text-muted-foreground',          dot: 'bg-muted-foreground' };
    if (count < 5)
        return { label: 'Limited',   color: 'bg-blue-500/10 text-blue-400',             dot: 'bg-blue-400' };
    if (count < 15)
        return { label: 'Moderate',  color: 'bg-amber-500/10 text-amber-400',           dot: 'bg-amber-400' };
    return         { label: 'Extensive', color: 'bg-emerald-500/10 text-emerald-400',   dot: 'bg-emerald-400' };
}

// ── Layer sub-components ───────────────────────────────────────────────────────

function LayerHeader({ icon: Icon, title, subtitle, colorClass }) {
    return (
        <div className={`flex items-center gap-2.5 px-4 py-3 border-b border-border/40 ${colorClass}`}>
            <Icon className="h-4 w-4 shrink-0" />
            <div className="flex-1 min-w-0">
                <span className="text-xs font-semibold tracking-widest uppercase">{title}</span>
                {subtitle && <span className="text-xs text-muted-foreground ml-2">{subtitle}</span>}
            </div>
        </div>
    );
}

function DataRow({ label, value }) {
    return (
        <div className="flex flex-col gap-0.5">
            <span className="text-xs text-muted-foreground uppercase tracking-wide font-medium">{label}</span>
            {value
                ? <span className="text-sm text-foreground leading-relaxed">{value}</span>
                : <span className="text-sm text-muted-foreground/40 italic">Not on record</span>
            }
        </div>
    );
}

// ── Shared sub-section: Fund Flow grid ────────────────────────────────────────

function FundFlowGrid({ ff, compact = false }) {
    if (!ff) return null;
    const fields = compact
        ? [['Funds Received', ff.received], ['Utilisation', ff.utilization], ['Discrepancies', ff.discrepancies]]
        : [['Allocated', ff.allocated], ['Released', ff.released], ['Disbursed', ff.disbursed], ['Utilisation', ff.utilization_pct], ['Discrepancies', ff.discrepancies]];
    const visible = fields.filter(([, v]) => v);
    if (!visible.length) return null;
    return (
        <div>
            <span className="text-xs text-muted-foreground uppercase tracking-wide font-medium block mb-2">
                Fund Flow
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {visible.map(([label, value]) => (
                    <DataRow key={label} label={label} value={value} />
                ))}
            </div>
        </div>
    );
}

// ── Layer 1: Your State ────────────────────────────────────────────────────────

function YourStateLayer({ data: ys, state }) {
    if (!ys) return null;

    const ff    = ys.fund_flow || {};
    const impl  = ys.implementation || {};
    const facts = Array.isArray(ys.key_facts) ? ys.key_facts.filter(Boolean) : [];

    const hasFF   = ff.received || ff.utilization || ff.discrepancies;
    const hasImpl = impl.progress || impl.achievements || impl.challenges;
    const hasContent = hasFF || ys.beneficiaries || hasImpl || facts.length > 0;

    if (!hasContent) {
        return (
            <div className="rounded-xl border border-border/60 overflow-hidden">
                <LayerHeader
                    icon={MapPin}
                    title={`Your State — ${state}`}
                    colorClass="bg-emerald-500/5 text-emerald-400"
                />
                <div className="px-4 py-6 text-center bg-card/50">
                    <p className="text-sm text-muted-foreground/50 italic">
                        No specific mention of {state} found in parliamentary answers for this scheme.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="rounded-xl border border-emerald-500/20 overflow-hidden">
            <LayerHeader
                icon={MapPin}
                title={`Your State — ${state}`}
                colorClass="bg-emerald-500/8 text-emerald-400"
            />
            <div className="px-4 py-4 bg-card/50 space-y-4">
                {hasFF && <FundFlowGrid ff={ff} compact />}
                {ys.beneficiaries && <DataRow label="Beneficiaries" value={ys.beneficiaries} />}
                {hasImpl && (
                    <div>
                        <span className="text-xs text-muted-foreground uppercase tracking-wide font-medium block mb-2">
                            On the Ground
                        </span>
                        <div className="space-y-2">
                            {impl.progress     && <DataRow label="Progress"     value={impl.progress} />}
                            {impl.achievements && <DataRow label="Achievements" value={impl.achievements} />}
                            {impl.challenges   && <DataRow label="Challenges"   value={impl.challenges} />}
                        </div>
                    </div>
                )}
                {facts.length > 0 && (
                    <div>
                        <span className="text-xs text-muted-foreground uppercase tracking-wide font-medium block mb-2">
                            Key Facts
                        </span>
                        <ul className="space-y-1.5">
                            {facts.map((f, i) => (
                                <li key={i} className="flex items-start gap-2">
                                    <span className="text-emerald-400/60 mt-1.5 shrink-0">•</span>
                                    <span className="text-sm text-foreground leading-relaxed">{f}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        </div>
    );
}

// ── Layer 2: National Picture ──────────────────────────────────────────────────

function NationalLayer({ data: np }) {
    if (!np) return null;

    const ff    = np.fund_flow || {};
    const bc    = np.beneficiary_coverage || {};
    const impl  = np.implementation_status || {};
    const ca    = np.challenges_acknowledged || {};
    const stats = Array.isArray(np.key_statistics) ? np.key_statistics.filter(Boolean) : [];
    const lp    = np.latest_position || {};

    // Fallback: old format had these directly on np
    const totalAlloc = ff.allocated || np.total_allocation;
    const totalBen   = bc.total_beneficiaries || np.total_beneficiaries;

    return (
        <div className="rounded-xl border border-border/60 overflow-hidden">
            <LayerHeader
                icon={Globe}
                title="National Picture"
                colorClass="bg-blue-500/5 text-blue-400"
            />
            <div className="px-4 py-4 bg-card/50 space-y-4">

                {lp.statement && (
                    <div className="rounded-lg bg-primary/5 border border-primary/10 px-4 py-3">
                        <div className="flex items-center gap-1.5 mb-1.5">
                            <CircleDot className="h-3.5 w-3.5 text-primary" />
                            <span className="text-xs font-semibold text-primary uppercase tracking-wider">
                                Ministry&apos;s Latest
                            </span>
                            {lp.date && (
                                <span className="ml-auto text-xs text-muted-foreground shrink-0">
                                    {formatDate(lp.date)}
                                </span>
                            )}
                        </div>
                        <p className="text-sm text-foreground leading-relaxed italic">
                            &ldquo;{lp.statement}&rdquo;
                        </p>
                    </div>
                )}

                {/* Fund flow — full 5-field version */}
                {(ff.allocated || ff.released || ff.disbursed || ff.utilization_pct || ff.discrepancies) && (
                    <FundFlowGrid ff={ff} compact={false} />
                )}

                {/* Beneficiary coverage */}
                {(totalBen || bc.demographic_breakdown || bc.coverage_note) && (
                    <div>
                        <span className="text-xs text-muted-foreground uppercase tracking-wide font-medium block mb-2">
                            Beneficiary Coverage
                        </span>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                            {totalBen && <DataRow label="Total Beneficiaries"   value={totalBen} />}
                            {bc.demographic_breakdown && <DataRow label="Breakdown" value={bc.demographic_breakdown} />}
                            {bc.coverage_note && <DataRow label="Note" value={bc.coverage_note} />}
                        </div>
                    </div>
                )}

                {/* Implementation */}
                {(impl.progress || impl.achievements || impl.timeline || np.progress) && (
                    <div>
                        <span className="text-xs text-muted-foreground uppercase tracking-wide font-medium block mb-2">
                            Implementation
                        </span>
                        <div className="space-y-2">
                            {(impl.progress   || np.progress)  && <DataRow label="Progress"     value={impl.progress   || np.progress} />}
                            {impl.achievements && <DataRow label="Achievements" value={impl.achievements} />}
                            {impl.timeline     && <DataRow label="Timeline"     value={impl.timeline} />}
                        </div>
                    </div>
                )}

                {/* Challenges */}
                {(ca.delays || ca.gaps || ca.pending_issues) && (
                    <div>
                        <span className="text-xs text-muted-foreground uppercase tracking-wide font-medium block mb-2">
                            Challenges Acknowledged
                        </span>
                        <div className="space-y-2">
                            {ca.delays         && <DataRow label="Delays"          value={ca.delays} />}
                            {ca.gaps           && <DataRow label="Gaps"            value={ca.gaps} />}
                            {ca.pending_issues && <DataRow label="Pending Issues"  value={ca.pending_issues} />}
                        </div>
                    </div>
                )}

                {/* Key statistics */}
                {stats.length > 0 && (
                    <div>
                        <span className="text-xs text-muted-foreground uppercase tracking-wide font-medium block mb-2">
                            Key Statistics from Parliament
                        </span>
                        <ul className="space-y-1.5">
                            {stats.map((s, i) => (
                                <li key={i} className="flex items-start gap-2">
                                    <span className="text-xs text-muted-foreground/40 font-mono mt-0.5 shrink-0 w-5">
                                        {String(i + 1).padStart(2, '0')}
                                    </span>
                                    <span className="text-sm text-foreground leading-relaxed">{s}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        </div>
    );
}

// ── Layer 3: Other States ──────────────────────────────────────────────────────

function OtherStatesLayer({ data: os, currentState }) {
    if (!os) return null;

    const mentioned = Array.isArray(os.top_mentioned)
        ? os.top_mentioned.filter(s => s && s !== currentState)
        : [];
    const hasContent = mentioned.length > 0 || os.comparison || os.lagging_issues;
    if (!hasContent) return null;

    return (
        <div className="rounded-xl border border-border/60 overflow-hidden">
            <LayerHeader
                icon={ArrowLeftRight}
                title="Other States"
                subtitle="— how they compare"
                colorClass="bg-violet-500/5 text-violet-400"
            />
            <div className="px-4 py-4 bg-card/50 space-y-3">
                {mentioned.length > 0 && (
                    <div>
                        <span className="text-xs text-muted-foreground uppercase tracking-wide font-medium block mb-2">
                            States Mentioned in Parliament
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                            {mentioned.map(s => (
                                <span key={s}
                                    className="text-xs px-2.5 py-1 rounded-full bg-muted text-muted-foreground border border-border/40">
                                    {s}
                                </span>
                            ))}
                        </div>
                    </div>
                )}
                {os.comparison    && <DataRow label="Comparison"              value={os.comparison} />}
                {os.lagging_issues && <DataRow label="Issues Reported Elsewhere" value={os.lagging_issues} />}
            </div>
        </div>
    );
}

// ── Screen 3: Intelligence Brief ──────────────────────────────────────────────

function SchemeBrief({ scheme, onBack, color }) {
    const [data, setData]       = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError]     = useState(null);
    const [refreshing, setRefreshing] = useState(false);

    const loadBrief = useCallback(async ({ silent = false } = {}) => {
        if (!silent) {
            setLoading(true);
            setError(null);
            setData(null);
        }
        try {
            const brief = await apiGet(`/api/schemes/intelligence/${encodeURIComponent(scheme.name)}`, { timeout: AI_TIMEOUT });
            setData(brief);
            setError(null);
        } catch (e) {
            setError(e.message);
        } finally {
            if (!silent) setLoading(false);
            setRefreshing(false);
        }
    }, [scheme.name]);

    useEffect(() => {
        loadBrief();
    }, [loadBrief]);

    useEffect(() => {
        if (!data?.pending && !data?.is_stale) return undefined;
        const poll = setInterval(() => {
            loadBrief({ silent: true });
        }, 3000);
        return () => clearInterval(poll);
    }, [data?.pending, data?.is_stale, loadBrief]);

    const refreshBrief = async () => {
        setRefreshing(true);
        try {
            await apiPost(`/api/schemes/intelligence/${encodeURIComponent(scheme.name)}/refresh`, {});
            await loadBrief();
        } catch (e) {
            setError(e.message);
            setRefreshing(false);
        }
    };

    const intel     = data?.intel || {};
    const isNewFmt  = !!intel.national_picture;

    // Legacy format fields (for briefs cached before state-aware update)
    const ff    = intel.fund_flow || {};
    const bc    = intel.beneficiary_coverage || {};
    const impl  = intel.implementation_status || {};
    const ca    = intel.challenges_acknowledged || {};
    const lp    = intel.latest_position || {};
    const stats = Array.isArray(intel.key_statistics) ? intel.key_statistics : [];

    return (
        <div className="space-y-6">
            {/* Breadcrumb / back */}
            <div className="flex items-start gap-3">
                <Button variant="ghost" size="sm" onClick={onBack}
                    className="mt-0.5 h-8 w-8 p-0 text-muted-foreground hover:text-foreground shrink-0">
                    <ChevronLeft className="h-5 w-5" />
                </Button>
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                        <h1 className="text-xl font-bold text-foreground leading-tight">
                            {scheme.full_name || scheme.name}
                        </h1>
                        {data?.pending && (
                            <Badge variant="outline" className="text-xs text-blue-400 border-blue-400/30 gap-1 shrink-0">
                                <Loader2 className="h-3 w-3 animate-spin" /> Preparing
                            </Badge>
                        )}
                        {data?.is_stale && (
                            <Badge variant="outline" className="text-xs text-amber-400 border-amber-400/30 gap-1 shrink-0">
                                <RefreshCw className="h-3 w-3" /> Updating
                            </Badge>
                        )}
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={refreshBrief}
                            disabled={refreshing}
                            className="h-7 gap-1.5"
                        >
                            {refreshing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                            Refresh
                        </Button>
                    </div>
                    <p className="text-sm text-muted-foreground mt-0.5">{scheme.ministry}</p>
                    <div className="flex items-center gap-3 mt-0.5 flex-wrap">
                        {data?.state && (
                            <span className="flex items-center gap-1 text-xs text-emerald-400/70">
                                <MapPin className="h-3 w-3" /> {data.state}
                            </span>
                        )}
                        {data?.generated_at && (
                            <p className="text-xs text-muted-foreground/50">
                                Analysed {formatDate(data.generated_at)}
                            </p>
                        )}
                    </div>
                </div>
            </div>

            {/* Loading */}
            {loading && (
                <Card className="border-border/60">
                    <CardContent className="flex flex-col items-center justify-center py-20 gap-4">
                        <Loader2 className="h-8 w-8 animate-spin" style={{ color }} />
                        <div className="text-center space-y-1">
                            <p className="text-sm font-medium text-foreground">Reading parliamentary record…</p>
                            <p className="text-xs text-muted-foreground">Analysing ministry responses from Lok Sabha &amp; Rajya Sabha</p>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Error */}
            {!loading && error && (
                <Card className="border-destructive/30">
                    <CardContent className="py-10 text-center space-y-2">
                        <AlertTriangle className="h-8 w-8 text-destructive/60 mx-auto" />
                        <p className="text-sm text-muted-foreground">Could not load intelligence. {error}</p>
                    </CardContent>
                </Card>
            )}

            {!loading && !error && data?.pending && !Object.keys(intel).length && (
                <Card className="border-border/60">
                    <CardContent className="flex flex-col items-center justify-center py-20 gap-4">
                        <Loader2 className="h-8 w-8 animate-spin" style={{ color }} />
                        <div className="text-center space-y-1">
                            <p className="text-sm font-medium text-foreground">Preparing scheme brief…</p>
                            <p className="text-xs text-muted-foreground">
                                We&apos;re compiling the latest ministry record in the background.
                            </p>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* No data */}
            {!loading && !error && data?.no_data && (
                <Card className="border-border/60">
                    <CardContent className="py-14 text-center space-y-2">
                        <FileText className="h-10 w-10 text-muted-foreground/30 mx-auto" />
                        <p className="text-sm font-medium text-foreground">No parliamentary record found</p>
                        <p className="text-xs text-muted-foreground max-w-xs mx-auto">
                            This scheme has not appeared in the ministry answers we have analysed.
                        </p>
                    </CardContent>
                </Card>
            )}

            {/* ── New 3-layer format ── */}
            {!loading && !error && isNewFmt && (
                <div className="space-y-4">
                    {intel.your_state && (
                        <YourStateLayer data={intel.your_state} state={data?.state} />
                    )}
                    <NationalLayer data={intel.national_picture} />
                    <OtherStatesLayer data={intel.other_states} currentState={data?.state} />
                    <p className="text-xs text-muted-foreground/40 text-center pt-1">
                        Derived exclusively from ministry responses in Parliament (Starred &amp; Unstarred Questions).
                    </p>
                </div>
            )}

            {/* ── Legacy 6-section format (cached briefs before state-aware update) ── */}
            {!loading && !error && !isNewFmt && Object.keys(intel).length > 0 && (
                <div className="space-y-4">
                    {lp.statement && (
                        <div className="rounded-xl border border-border/60 bg-card overflow-hidden">
                            <div className="flex items-center gap-2 px-4 py-3 bg-primary/5 border-b border-border/40">
                                <CircleDot className="h-4 w-4 text-primary" />
                                <span className="text-xs font-semibold tracking-widest uppercase text-primary">
                                    Ministry&apos;s Latest Position
                                </span>
                                {lp.date && (
                                    <span className="ml-auto text-xs text-muted-foreground shrink-0">
                                        {formatDate(lp.date)}
                                    </span>
                                )}
                            </div>
                            <div className="px-5 py-5">
                                <p className="text-sm text-foreground leading-relaxed italic">
                                    &ldquo;{lp.statement}&rdquo;
                                </p>
                            </div>
                        </div>
                    )}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="rounded-xl border border-border/60 overflow-hidden">
                            <LayerHeader icon={BarChart3}    title="Fund Flow"      colorClass="bg-blue-500/5 text-blue-400" />
                            <div className="px-4 py-4 bg-card/50 space-y-3">
                                <DataRow label="Allocated"   value={ff.allocated} />
                                <DataRow label="Released"    value={ff.released} />
                                <DataRow label="Disbursed"   value={ff.disbursed} />
                                <DataRow label="Utilisation" value={ff.utilization_pct} />
                                {ff.discrepancies && <DataRow label="Discrepancies" value={ff.discrepancies} />}
                            </div>
                        </div>
                        <div className="rounded-xl border border-border/60 overflow-hidden">
                            <LayerHeader icon={TrendingUp}   title="Coverage"       colorClass="bg-emerald-500/5 text-emerald-400" />
                            <div className="px-4 py-4 bg-card/50 space-y-3">
                                <DataRow label="Total Beneficiaries"   value={bc.total_beneficiaries} />
                                <DataRow label="Demographic Breakdown" value={bc.demographic_breakdown} />
                                {bc.coverage_note && <DataRow label="Coverage Note" value={bc.coverage_note} />}
                                {bc.states_mentioned?.length > 0 && (
                                    <div>
                                        <span className="text-xs text-muted-foreground uppercase tracking-wide font-medium block mb-1.5">States on Record</span>
                                        <div className="flex flex-wrap gap-1.5">
                                            {bc.states_mentioned.map(s => (
                                                <span key={s} className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground">{s}</span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                        <div className="rounded-xl border border-border/60 overflow-hidden">
                            <LayerHeader icon={Wrench}       title="Implementation" colorClass="bg-violet-500/5 text-violet-400" />
                            <div className="px-4 py-4 bg-card/50 space-y-3">
                                <DataRow label="Progress"     value={impl.progress} />
                                <DataRow label="Achievements" value={impl.achievements} />
                                <DataRow label="Timeline"     value={impl.timeline} />
                            </div>
                        </div>
                        <div className="rounded-xl border border-border/60 overflow-hidden">
                            <LayerHeader icon={AlertTriangle} title="Challenges"    colorClass="bg-rose-500/5 text-rose-400" />
                            <div className="px-4 py-4 bg-card/50 space-y-3">
                                <DataRow label="Delays"          value={ca.delays} />
                                <DataRow label="Gaps"            value={ca.gaps} />
                                <DataRow label="Pending Issues"  value={ca.pending_issues} />
                            </div>
                        </div>
                    </div>
                    {stats.length > 0 && (
                        <div className="rounded-xl border border-border/60 overflow-hidden">
                            <LayerHeader icon={FileText} title="Key Statistics" colorClass="bg-muted/20 text-muted-foreground" />
                            <div className="divide-y divide-border/30">
                                {stats.map((stat, i) => (
                                    <div key={i} className="px-4 py-3 flex items-start gap-3 bg-card/30">
                                        <span className="text-xs text-muted-foreground/40 font-mono mt-0.5 shrink-0 w-5">
                                            {String(i + 1).padStart(2, '0')}
                                        </span>
                                        <p className="text-sm text-foreground leading-relaxed">{stat}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                    <p className="text-xs text-muted-foreground/40 text-center pt-1">
                        Derived exclusively from ministry responses in Parliament.
                    </p>
                </div>
            )}
        </div>
    );
}

// ── Screen 2: Schemes under a Ministry ────────────────────────────────────────

function MinistrySchemes({ ministry, onBack, onSelectScheme, color }) {
    const [schemes, setSchemes] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch]   = useState('');

    useEffect(() => {
        setLoading(true);
        apiGet(`/api/schemes/ministry/${encodeURIComponent(ministry)}`)
            .then(d => { setSchemes(d.schemes || []); setLoading(false); })
            .catch(() => setLoading(false));
    }, [ministry]);

    const filtered = schemes.filter(s => {
        if (!search) return true;
        const q = search.toLowerCase();
        return (s.name || '').toLowerCase().includes(q)
            || (s.full_name || '').toLowerCase().includes(q);
    });

    return (
        <div className="space-y-5">
            <div className="flex items-center gap-3">
                <Button variant="ghost" size="sm" onClick={onBack}
                    className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground shrink-0">
                    <ChevronLeft className="h-5 w-5" />
                </Button>
                <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium mb-0.5">Ministry</p>
                    <h1 className="text-lg font-bold text-foreground leading-tight">{ministry}</h1>
                </div>
            </div>

            <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                    placeholder="Search schemes…"
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    className="pl-9 bg-muted/30 border-border/60 text-sm"
                />
            </div>

            {loading && (
                <div className="flex items-center justify-center py-16">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
            )}

            {!loading && filtered.length === 0 && (
                <div className="text-center py-16 text-sm text-muted-foreground">
                    No schemes found{search ? ' for this search' : ' for this ministry'}.
                </div>
            )}

            {!loading && filtered.length > 0 && (
                <div className="space-y-2">
                    <p className="text-xs text-muted-foreground">
                        {filtered.length} scheme{filtered.length !== 1 ? 's' : ''} with parliamentary record
                    </p>
                    {filtered.map(scheme => {
                        const band = answerBand(scheme.answer_count);
                        return (
                            <button
                                key={scheme.id}
                                onClick={() => onSelectScheme(scheme)}
                                className="w-full text-left rounded-xl border border-border/60 bg-card hover:bg-muted/20 hover:border-border transition-all duration-150 p-4 group"
                            >
                                <div className="flex items-start justify-between gap-3">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 flex-wrap mb-1.5">
                                            <p className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors leading-snug">
                                                {scheme.full_name || scheme.name}
                                            </p>
                                            {scheme.intel_status === 'ready' && (
                                                <span className="text-xs px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-medium shrink-0">
                                                    Ready
                                                </span>
                                            )}
                                        </div>
                                        <div className="flex items-center gap-3 flex-wrap">
                                            <span className={`text-xs px-2 py-0.5 rounded-full font-medium flex items-center gap-1.5 ${band.color}`}>
                                                <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${band.dot}`} />
                                                {band.label} record
                                            </span>
                                            {scheme.last_seen && (
                                                <span className="text-xs text-muted-foreground/50">
                                                    Last discussed {formatDate(scheme.last_seen)}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    <ChevronRight className="h-4 w-4 text-muted-foreground/30 group-hover:text-muted-foreground transition-colors shrink-0 mt-0.5" />
                                </div>
                            </button>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

// ── Screen 1: Ministry Overview ───────────────────────────────────────────────

function MinistryOverview({ onSelectMinistry }) {
    const [ministries, setMinistries] = useState([]);
    const [loading, setLoading]       = useState(true);
    const [search, setSearch]         = useState('');

    useEffect(() => {
        apiGet('/api/schemes/ministries')
            .then(d => { setMinistries(d.ministries || []); setLoading(false); })
            .catch(() => setLoading(false));
    }, []);

    const filtered = ministries.filter(m =>
        !search || (m.ministry || '').toLowerCase().includes(search.toLowerCase())
    );

    const totalSchemes  = ministries.reduce((s, m) => s + (m.scheme_count  || 0), 0);

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-foreground">Scheme Intelligence</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    What the government has said about its schemes in Parliament
                </p>
            </div>

            {!loading && ministries.length > 0 && (
                <div className="grid grid-cols-3 gap-3">
                    {[
                        { label: 'Ministries',        value: ministries.length,                  icon: Building2  },
                        { label: 'Schemes tracked',   value: totalSchemes,                        icon: FileText   },
                    ].map(({ label, value, icon: Icon }) => (
                        <Card key={label} className="border-border/60 bg-card/60">
                            <CardContent className="p-4 flex items-center gap-3">
                                <div className="h-9 w-9 rounded-lg bg-muted/50 flex items-center justify-center shrink-0">
                                    <Icon className="h-4 w-4 text-muted-foreground" />
                                </div>
                                <div>
                                    <p className="text-lg font-bold text-foreground leading-none">{value}</p>
                                    <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                    placeholder="Search ministries…"
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    className="pl-9 bg-muted/30 border-border/60 text-sm"
                />
            </div>

            {loading && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {Array.from({ length: 9 }).map((_, i) => (
                        <div key={i} className="h-28 rounded-xl bg-muted/30 animate-pulse" />
                    ))}
                </div>
            )}

            {!loading && filtered.length === 0 && (
                <div className="text-center py-16 space-y-2">
                    <p className="text-sm text-muted-foreground">No ministries found.</p>
                    <p className="text-xs text-muted-foreground/50">
                        Run the scheme extraction job to populate data.
                    </p>
                </div>
            )}

            {!loading && filtered.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {filtered.map(m => {
                        const band = answerBand(m.total_answers);
                        return (
                            <button
                                key={m.ministry}
                                onClick={() => onSelectMinistry(m.ministry)}
                                className="text-left rounded-xl border border-border/60 bg-card hover:bg-muted/20 hover:border-border hover:shadow-sm transition-all duration-150 p-4 group"
                            >
                                <div className="flex items-start justify-between gap-2 mb-3">
                                    <div className="h-9 w-9 rounded-lg bg-muted/50 flex items-center justify-center shrink-0 group-hover:bg-primary/10 transition-colors">
                                        <Building2 className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
                                    </div>
                                    <ChevronRight className="h-4 w-4 text-muted-foreground/30 group-hover:text-muted-foreground transition-colors mt-0.5 shrink-0" />
                                </div>

                                <p className="text-sm font-semibold text-foreground leading-snug mb-2 group-hover:text-primary transition-colors line-clamp-2">
                                    {shortMinistry(m.ministry)}
                                </p>

                                <div className="flex items-center gap-2 flex-wrap">
                                    <span className="text-xs text-muted-foreground">
                                        {m.scheme_count} scheme{m.scheme_count !== 1 ? 's' : ''}
                                    </span>
                                    <span className="text-muted-foreground/30 text-xs">·</span>
                                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium flex items-center gap-1.5 ${band.color}`}>
                                        <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${band.dot}`} />
                                        {band.label}
                                    </span>
                                </div>

                                {m.latest_activity && (
                                    <p className="text-xs text-muted-foreground/40 mt-1.5">
                                        Last activity {formatDate(m.latest_activity)}
                                    </p>
                                )}
                            </button>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

// ── Root ──────────────────────────────────────────────────────────────────────

export default function SchemesPage() {
    const { user } = useAuth();
    const router = useRouter();
    const searchParams = useSearchParams();

    const initialView = searchParams.get('view');
    const initialMinistry = searchParams.get('ministry');
    const initialScheme = searchParams.get('scheme');
    const initialSchemeName = searchParams.get('scheme_name');

    const [screen, setScreen] = useState(
        initialView === 'scheme' || initialView === 'ministry' ? initialView : 'overview'
    );
    const [activeMinistry, setMinistry] = useState(initialMinistry || null);
    const [activeScheme, setScheme] = useState(
        initialScheme
            ? {
                name: initialScheme,
                full_name: initialSchemeName || initialScheme,
                ministry: initialMinistry || '',
            }
            : null
    );

    const color = user?.theme_color || '#006a4d';

    if (user && user.role !== 'mp' && user.role !== 'admin') {
        return <LockedModule />;
    }

    const goMinistry = (ministry) => { setMinistry(ministry); setScheme(null); setScreen('ministry'); };
    const goScheme   = (scheme)   => { setScheme(scheme); setScreen('scheme'); };
    const goBack     = () => {
        if (screen === 'scheme')   { setScreen('ministry'); setScheme(null); }
        else                       { setScreen('overview'); setMinistry(null); }
    };

    useEffect(() => {
        const params = new URLSearchParams();
        if (screen !== 'overview') params.set('view', screen);
        if (activeMinistry) params.set('ministry', activeMinistry);
        if (screen === 'scheme' && activeScheme?.name) {
            params.set('scheme', activeScheme.name);
            params.set('scheme_name', activeScheme.full_name || activeScheme.name);
        }
        const qs = params.toString();
        router.replace(qs ? `/dashboard/schemes?${qs}` : '/dashboard/schemes', { scroll: false });
    }, [screen, activeMinistry, activeScheme, router]);

    return (
        <div className="max-w-5xl mx-auto">
            {screen === 'overview'  && <MinistryOverview onSelectMinistry={goMinistry} color={color} />}
            {screen === 'ministry'  && activeMinistry && (
                <MinistrySchemes ministry={activeMinistry} onBack={goBack} onSelectScheme={goScheme} color={color} />
            )}
            {screen === 'scheme'    && activeScheme && (
                <SchemeBrief scheme={activeScheme} onBack={goBack} color={color} />
            )}
        </div>
    );
}
