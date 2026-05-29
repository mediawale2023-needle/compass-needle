'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPost, AI_TIMEOUT } from '@/lib/api';
import { canAccessSansadAI } from '@/lib/account';
import { ResearchDeskExperience } from '@/app/dashboard/copilot/page';
import {
    Bot, Building2, ChevronLeft, ChevronRight, Landmark,
    Loader2, MapPin, Radar, RefreshCw, Search, AlertTriangle,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { SchemesExperience } from '@/app/dashboard/schemes/page';

function formatDate(value) {
    if (!value) return null;
    try {
        return new Date(value).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' });
    } catch {
        return value;
    }
}

function ListSection({ title, items }) {
    const rows = Array.isArray(items) ? items.filter(Boolean) : [];
    if (!rows.length) return null;
    return (
        <div className="rounded-xl border border-border/60 overflow-hidden bg-card/50">
            <div className="px-4 py-3 border-b border-border/40 bg-muted/30">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">{title}</p>
            </div>
            <div className="divide-y divide-border/30">
                {rows.map((item, index) => (
                    <div key={`${title}-${index}`} className="px-4 py-3 flex items-start gap-3">
                        <span className="text-emerald-400/70 mt-1">•</span>
                        <p className="text-sm text-foreground leading-relaxed">{item}</p>
                    </div>
                ))}
            </div>
        </div>
    );
}

function DeltaSection({ deltas }) {
    const hasContent =
        deltas?.changed_numbers?.length ||
        deltas?.changed_deadlines?.length ||
        deltas?.stance_shifts?.length;

    if (!hasContent) return null;

    return (
        <div className="rounded-xl border border-amber-500/20 overflow-hidden bg-card/50">
            <div className="px-4 py-3 border-b border-border/40 bg-amber-500/5 flex items-center gap-2">
                <Radar className="h-4 w-4 text-amber-400" />
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-400">Shifts On Record</p>
            </div>
            <div className="p-4 space-y-4">
                <ListSection title="Changed Numbers" items={deltas?.changed_numbers} />
                <ListSection title="Changed Deadlines" items={deltas?.changed_deadlines} />
                <ListSection title="Stance Shifts" items={deltas?.stance_shifts} />
            </div>
        </div>
    );
}

function IssueBrief({ ministry, topic, issueIds = [], stateLabel, onBack, color }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState(null);

    const loadBrief = useCallback(async ({ silent = false } = {}) => {
        if (!silent) {
            setLoading(true);
            setError(null);
            setData(null);
        }
        try {
            const params = new URLSearchParams({ ministry, topic });
            if (stateLabel) params.set('state', stateLabel);
            if (issueIds.length) params.set('issue_ids', issueIds.join(','));
            const result = await apiGet(`/api/sansadai/intelligence?${params.toString()}`, { timeout: AI_TIMEOUT });
            setData(result);
            setError(null);
        } catch (e) {
            setError(e.message);
        } finally {
            if (!silent) setLoading(false);
            setRefreshing(false);
        }
    }, [ministry, topic, issueIds, stateLabel]);

    useEffect(() => {
        loadBrief();
    }, [loadBrief]);

    useEffect(() => {
        if (!data?.pending && !data?.is_stale) return undefined;
        const timer = setInterval(() => loadBrief({ silent: true }), 3000);
        return () => clearInterval(timer);
    }, [data?.pending, data?.is_stale, loadBrief]);

    const refreshBrief = async () => {
        setRefreshing(true);
        try {
            const params = new URLSearchParams({ ministry, topic });
            if (stateLabel) params.set('state', stateLabel);
            if (issueIds.length) params.set('issue_ids', issueIds.join(','));
            await apiPost(`/api/sansadai/intelligence/refresh?${params.toString()}`, {});
            await loadBrief();
        } catch (e) {
            setError(e.message);
            setRefreshing(false);
        }
    };

    const intel = data?.intel || {};

    return (
        <div className="space-y-6">
            <div className="flex items-start gap-3">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={onBack}
                    className="mt-0.5 h-8 w-8 p-0 text-muted-foreground hover:text-foreground shrink-0"
                >
                    <ChevronLeft className="h-5 w-5" />
                </Button>
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                        <h1 className="text-xl font-bold text-foreground leading-tight">{topic}</h1>
                        {data?.pending && (
                            <Badge variant="outline" className="text-xs text-blue-400 border-blue-400/30 gap-1">
                                <Loader2 className="h-3 w-3 animate-spin" /> Preparing
                            </Badge>
                        )}
                        {data?.is_stale && (
                            <Badge variant="outline" className="text-xs text-amber-400 border-amber-400/30 gap-1">
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
                    <p className="text-sm text-muted-foreground mt-1">{ministry}</p>
                    <div className="flex items-center gap-3 mt-1 flex-wrap">
                        <span className="flex items-center gap-1 text-xs text-emerald-400/80">
                            <MapPin className="h-3 w-3" />
                            {data?.state || stateLabel || 'National'}
                        </span>
                        {data?.generated_at && (
                            <span className="text-xs text-muted-foreground/50">
                                Analysed {formatDate(data.generated_at)}
                            </span>
                        )}
                    </div>
                </div>
            </div>

            {loading && (
                <Card className="border-border/60">
                    <CardContent className="flex flex-col items-center justify-center py-20 gap-4">
                        <Loader2 className="h-8 w-8 animate-spin" style={{ color }} />
                        <div className="text-center space-y-1">
                            <p className="text-sm font-medium text-foreground">Reading the government record…</p>
                            <p className="text-xs text-muted-foreground">Compiling issue-level ministry answers and changes over time.</p>
                        </div>
                    </CardContent>
                </Card>
            )}

            {!loading && error && (
                <Card className="border-destructive/30">
                    <CardContent className="py-10 text-center space-y-2">
                        <AlertTriangle className="h-8 w-8 text-destructive/60 mx-auto" />
                        <p className="text-sm text-muted-foreground">Could not load SansadAI brief. {error}</p>
                    </CardContent>
                </Card>
            )}

            {!loading && !error && data?.pending && !Object.keys(intel).length && (
                <Card className="border-border/60">
                    <CardContent className="flex flex-col items-center justify-center py-20 gap-4">
                        <Loader2 className="h-8 w-8 animate-spin" style={{ color }} />
                        <div className="text-center space-y-1">
                            <p className="text-sm font-medium text-foreground">Preparing issue brief…</p>
                            <p className="text-xs text-muted-foreground">We&apos;re synthesizing the record in the background.</p>
                        </div>
                    </CardContent>
                </Card>
            )}

            {!loading && !error && data?.no_data && (
                <Card className="border-border/60">
                    <CardContent className="py-14 text-center space-y-2">
                        <Bot className="h-10 w-10 text-muted-foreground/30 mx-auto" />
                        <p className="text-sm font-medium text-foreground">No government record found</p>
                        <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                            There are no answered parliamentary questions on record for this ministry-topic combination yet.
                        </p>
                    </CardContent>
                </Card>
            )}

            {!loading && !error && Object.keys(intel).length > 0 && (
                <div className="space-y-4">
                    {intel.current_government_position && (
                        <div className="rounded-xl border border-border/60 overflow-hidden bg-card/50">
                            <div className="px-4 py-3 border-b border-border/40 bg-primary/5 flex items-center gap-2">
                                <Landmark className="h-4 w-4 text-primary" />
                                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">Current Government Position</p>
                            </div>
                            <div className="p-5 space-y-2">
                                <p className="text-sm text-foreground leading-relaxed">
                                    {intel.current_government_position.summary || intel.current_government_position.latest_update}
                                </p>
                                {intel.current_government_position.latest_date && (
                                    <p className="text-xs text-muted-foreground">
                                        Updated {formatDate(intel.current_government_position.latest_date)}
                                    </p>
                                )}
                            </div>
                        </div>
                    )}

                    <ListSection title="Key Numbers On Record" items={intel.key_numbers_on_record} />
                    <ListSection title="Gaps And Limits" items={intel.implementation_gaps} />
                    <ListSection title={`State-Specific Mentions${data?.state ? ` — ${data.state}` : ''}`} items={intel.state_specific_mentions} />
                    <DeltaSection deltas={intel.deltas_on_record} />

                    <p className="text-xs text-muted-foreground/40 text-center pt-1">
                        Derived from answered parliamentary questions and ministry replies, organized issue-wise.
                    </p>
                </div>
            )}
        </div>
    );
}

function TopicList({ ministry, stateLabel, focusState, onFocusChange, onBack, onSelectIssue }) {
    const [topics, setTopics] = useState([]);
    const [resolvedState, setResolvedState] = useState(focusState || null);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');

    useEffect(() => {
        let active = true;
        setLoading(true);
        setTopics([]);
        setResolvedState(focusState || null);
        const params = new URLSearchParams();
        if (focusState) params.set('state', focusState);
        apiGet(`/api/sansadai/ministry/${encodeURIComponent(ministry)}/topics${params.toString() ? `?${params.toString()}` : ''}`)
            .then((data) => {
                if (!active) return;
                setTopics(data.topics || []);
                setResolvedState(data.state || focusState || null);
                setLoading(false);
            })
            .catch(() => {
                if (active) setLoading(false);
            });
        return () => {
            active = false;
        };
    }, [ministry, focusState]);

    const filtered = topics.filter((item) =>
        !search ||
        (item.topic || '').toLowerCase().includes(search.toLowerCase()) ||
        (item.signal || '').toLowerCase().includes(search.toLowerCase()) ||
        (item.tags || []).some((tag) => (tag || '').toLowerCase().includes(search.toLowerCase()))
    );

    return (
        <div className="space-y-5">
            <div className="flex items-start justify-between gap-4 flex-wrap">
                <div className="flex items-center gap-3">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={onBack}
                    className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground shrink-0"
                >
                    <ChevronLeft className="h-5 w-5" />
                </Button>
                <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium mb-0.5">Ministry</p>
                    <h1 className="text-lg font-bold text-foreground leading-tight">{ministry}</h1>
                    {resolvedState && <p className="text-xs text-muted-foreground mt-1">Focused on {resolvedState}</p>}
                </div>
                </div>
                {stateLabel && (
                    <div className="inline-flex rounded-full border border-border bg-muted/20 p-1">
                        <button
                            type="button"
                            onClick={() => onFocusChange(null)}
                            className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors ${!focusState ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
                        >
                            National
                        </button>
                        <button
                            type="button"
                            onClick={() => onFocusChange(stateLabel)}
                            className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors ${focusState ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
                        >
                            {stateLabel}
                        </button>
                    </div>
                )}
            </div>

            <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                    placeholder="Search issues…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
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
                    No issues found for this ministry.
                    {focusState && (
                        <button
                            type="button"
                            onClick={() => onFocusChange(null)}
                            className="block mx-auto mt-3 text-primary hover:underline"
                        >
                            View national record
                        </button>
                    )}
                </div>
            )}

            {!loading && filtered.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {filtered.map((item) => (
                        <button
                            key={item.topic}
                            onClick={() => onSelectIssue(item)}
                            className="w-full text-left rounded-xl border border-border/60 bg-card hover:bg-muted/20 hover:border-border hover:shadow-sm transition-all duration-150 p-4 group"
                        >
                            <div className="flex items-start justify-between gap-3 h-full">
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors leading-snug">
                                        {item.topic}
                                    </p>
                                    {item.latest_activity && (
                                        <p className="text-xs text-muted-foreground/60 mt-2">
                                            Updated {formatDate(item.latest_activity)}
                                        </p>
                                    )}
                                    {item.signal && (
                                        <p className="text-sm text-muted-foreground mt-3 leading-relaxed line-clamp-3">
                                            <span className="font-semibold text-foreground/80">Signal:</span> {item.signal}
                                        </p>
                                    )}
                                    {(item.tags || []).length > 0 && (
                                        <div className="flex items-center gap-1.5 flex-wrap mt-3">
                                            {(item.tags || []).slice(0, 4).map((tag) => (
                                                <span key={tag} className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                                                    {tag}
                                                </span>
                                            ))}
                                        </div>
                                    )}
                                </div>
                                <ChevronRight className="h-4 w-4 text-muted-foreground/30 group-hover:text-muted-foreground transition-colors shrink-0 mt-0.5" />
                            </div>
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}

function MinistryOverview({
    onSelectMinistry,
    showIntro = true,
    heading = 'SansadAI',
    description = 'Government record, organized by issue instead of raw PQ archives',
}) {
    const [ministries, setMinistries] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');

    useEffect(() => {
        apiGet('/api/sansadai/ministries')
            .then((data) => {
                setMinistries(data.ministries || []);
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, []);

    const filtered = ministries.filter((item) =>
        !search || (item.ministry || '').toLowerCase().includes(search.toLowerCase())
    );

    return (
        <div className="space-y-6">
            {showIntro && (
                <div>
                    <h1 className="text-2xl font-bold text-foreground">{heading}</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        {description}
                    </p>
                </div>
            )}

            <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                    placeholder="Search ministries…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="pl-9 bg-muted/30 border-border/60 text-sm"
                />
            </div>

            {loading && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {Array.from({ length: 9 }).map((_, index) => (
                        <div key={index} className="h-28 rounded-xl bg-muted/30 animate-pulse" />
                    ))}
                </div>
            )}

            {!loading && filtered.length === 0 && (
                <div className="text-center py-16 text-sm text-muted-foreground">
                    No ministries found.
                </div>
            )}

            {!loading && filtered.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {filtered.map((item) => (
                        <button
                            key={item.ministry}
                            onClick={() => onSelectMinistry(item.ministry)}
                            className="text-left rounded-xl border border-border/60 bg-card hover:bg-muted/20 hover:border-border hover:shadow-sm transition-all duration-150 p-4 group"
                        >
                            <div className="flex items-start justify-between gap-2 mb-3">
                                <div className="h-9 w-9 rounded-lg bg-muted/50 flex items-center justify-center shrink-0 group-hover:bg-primary/10 transition-colors">
                                    <Building2 className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
                                </div>
                                <ChevronRight className="h-4 w-4 text-muted-foreground/30 group-hover:text-muted-foreground transition-colors mt-0.5 shrink-0" />
                            </div>
                            <p className="text-sm font-semibold text-foreground leading-snug mb-2 group-hover:text-primary transition-colors line-clamp-2">
                                {item.ministry}
                            </p>
                            {item.latest_activity && (
                                <p className="text-xs text-muted-foreground/40">
                                    Latest answered record {formatDate(item.latest_activity)}
                                </p>
                            )}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}

export function GovernmentIntelExperience({
    routeBase = '/dashboard/sansadai',
    fixedParams = {},
    embedded = false,
    heading = 'SansadAI',
    description = 'Government record, organized by issue instead of raw PQ archives',
}) {
    const { user } = useAuth();
    const router = useRouter();
    const searchParams = useSearchParams();

    const stateLabel = user?.state || null;
    const initialView = searchParams.get('view');
    const initialMinistry = searchParams.get('ministry');
    const initialTopic = searchParams.get('topic');
    const initialIssueIds = searchParams.get('issue_ids');
    const initialStateFocus = searchParams.get('state_focus');

    const [screen, setScreen] = useState(
        initialView === 'topic' || initialView === 'brief' ? initialView : 'overview'
    );
    const [activeMinistry, setActiveMinistry] = useState(initialMinistry || null);
    const [activeTopic, setActiveTopic] = useState(initialTopic || null);
    const [activeIssueIds, setActiveIssueIds] = useState(
        initialIssueIds ? initialIssueIds.split(',').filter(Boolean) : []
    );
    const [focusState, setFocusState] = useState(initialStateFocus || null);

    const color = user?.theme_color || '#006a4d';

    if (user && !canAccessSansadAI(user)) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-center px-6">
                <div className="h-16 w-16 rounded-full bg-muted flex items-center justify-center">
                    <Bot className="h-7 w-7 text-muted-foreground" />
                </div>
                <div>
                    <h2 className="text-lg font-semibold text-foreground">SansadAI is restricted</h2>
                    <p className="text-sm text-muted-foreground mt-1">Available to elected-office accounts only.</p>
                </div>
            </div>
        );
    }

    useEffect(() => {
        const params = new URLSearchParams();
        Object.entries(fixedParams || {}).forEach(([key, value]) => {
            if (value) params.set(key, value);
        });
        if (screen !== 'overview') params.set('view', screen);
        if (activeMinistry) params.set('ministry', activeMinistry);
        if (activeTopic) params.set('topic', activeTopic);
        if (activeIssueIds.length) params.set('issue_ids', activeIssueIds.join(','));
        if (focusState) params.set('state_focus', focusState);
        const qs = params.toString();
        router.replace(qs ? `${routeBase}?${qs}` : routeBase, { scroll: false });
    }, [screen, activeMinistry, activeTopic, activeIssueIds, focusState, fixedParams, routeBase, router]);

    const goMinistry = (ministry) => {
        setActiveMinistry(ministry);
        setActiveTopic(null);
        setActiveIssueIds([]);
        setScreen('topic');
    };

    const goIssue = (item) => {
        if (item.ministry && item.ministry !== activeMinistry) return;
        setActiveTopic(item.topic);
        setActiveIssueIds(item.issue_ids || []);
        setScreen('brief');
    };

    const changeFocusState = (state) => {
        setFocusState(state);
        setActiveTopic(null);
        setActiveIssueIds([]);
        setScreen('topic');
    };

    const goBack = () => {
        if (screen === 'brief') {
            setActiveTopic(null);
            setActiveIssueIds([]);
            setScreen('topic');
            return;
        }
        setActiveMinistry(null);
        setActiveIssueIds([]);
        setScreen('overview');
    };

    return (
        <div className="max-w-5xl mx-auto">
            {screen === 'overview' && (
                <MinistryOverview
                    onSelectMinistry={goMinistry}
                    showIntro={!embedded}
                    heading={heading}
                    description={description}
                />
            )}
            {screen === 'topic' && activeMinistry && (
                <TopicList
                    ministry={activeMinistry}
                    stateLabel={stateLabel}
                    focusState={focusState}
                    onFocusChange={changeFocusState}
                    onBack={goBack}
                    onSelectIssue={goIssue}
                />
            )}
            {screen === 'brief' && activeMinistry && activeTopic && (
                <IssueBrief
                    ministry={activeMinistry}
                    topic={activeTopic}
                    issueIds={activeIssueIds}
                    stateLabel={focusState}
                    onBack={goBack}
                    color={color}
                />
            )}
        </div>
    );
}

export default function SansadAIPage() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const requestedTab = searchParams.get('tab');
    const requestedSessionId = searchParams.get('session');
    const activeTab = requestedTab === 'government-intel' || requestedTab === 'research'
        ? requestedTab
        : 'schemes';

    const tabButtonClass = (tab) => (
        `inline-flex items-center rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === tab
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-border bg-card text-muted-foreground hover:text-foreground'
        }`
    );

    const openTab = (tab) => {
        router.replace(`/dashboard/sansadai?tab=${tab}`, { scroll: false });
    };

    const schemesParams = useMemo(() => ({ tab: 'schemes' }), []);
    const governmentParams = useMemo(() => ({ tab: 'government-intel' }), []);
    const researchParams = useMemo(() => ({ tab: 'research' }), []);

    return (
        <div className="space-y-6 max-w-5xl mx-auto">
            <div>
                <h1 className="text-2xl font-bold text-foreground">SansadAI</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    One parliamentary intelligence surface for schemes, government record, and persistent research workspaces.
                </p>
            </div>

            <div className="flex items-center gap-3 flex-wrap">
                <button type="button" className={tabButtonClass('schemes')} onClick={() => openTab('schemes')}>
                    Schemes
                </button>
                <button type="button" className={tabButtonClass('government-intel')} onClick={() => openTab('government-intel')}>
                    Government Intel
                </button>
                <button type="button" className={tabButtonClass('research')} onClick={() => openTab('research')}>
                    Research
                </button>
            </div>

            {activeTab === 'schemes' ? (
                <SchemesExperience
                    routeBase="/dashboard/sansadai"
                    fixedParams={schemesParams}
                    embedded
                    heading="Schemes"
                    description="What the government has said about its schemes in Parliament"
                />
            ) : activeTab === 'government-intel' ? (
                <GovernmentIntelExperience
                    routeBase="/dashboard/sansadai"
                    fixedParams={governmentParams}
                    embedded
                    heading="Government Intel"
                    description="Government record, organized by issue instead of raw PQ archives"
                />
            ) : (
                <ResearchDeskExperience
                    embedded
                    heading="Research Desk"
                    description="Analyse documents, interrogate them, and connect them to parliamentary memory."
                    routeBase="/dashboard/sansadai"
                    fixedParams={researchParams}
                    initialSessionId={requestedSessionId}
                />
            )}
        </div>
    );
}
