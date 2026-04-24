'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
    Building2, ChevronRight, ChevronLeft, Search,
    MapPin, Loader2, RefreshCw, FileText,
    Hammer, DollarSign, Users, TrendingUp, AlertTriangle,
    BookOpen, BarChart2, Briefcase, Globe, Leaf,
    FlaskConical, Scale, MoreHorizontal, ExternalLink,
    ChevronDown, ChevronUp, Lock,
} from 'lucide-react';

// ── Topic metadata ─────────────────────────────────────────────────────────────

const TOPIC_META = {
    'Infrastructure & Projects':       { icon: Hammer,        color: 'text-orange-600',  bg: 'bg-orange-50',  dot: 'bg-orange-500' },
    'Budget & Finance':                { icon: DollarSign,    color: 'text-emerald-600', bg: 'bg-emerald-50', dot: 'bg-emerald-500' },
    'Welfare & Beneficiaries':         { icon: Users,         color: 'text-blue-600',    bg: 'bg-blue-50',    dot: 'bg-blue-500' },
    'Implementation & Progress':       { icon: TrendingUp,    color: 'text-violet-600',  bg: 'bg-violet-50',  dot: 'bg-violet-500' },
    'Challenges & Delays':             { icon: AlertTriangle, color: 'text-red-600',     bg: 'bg-red-50',     dot: 'bg-red-500' },
    'Policy & Legislation':            { icon: BookOpen,      color: 'text-indigo-600',  bg: 'bg-indigo-50',  dot: 'bg-indigo-500' },
    'Data & Statistics':               { icon: BarChart2,     color: 'text-cyan-600',    bg: 'bg-cyan-50',    dot: 'bg-cyan-500' },
    'Appointments & Administration':   { icon: Briefcase,     color: 'text-slate-600',   bg: 'bg-slate-50',   dot: 'bg-slate-500' },
    'International & Bilateral':       { icon: Globe,         color: 'text-sky-600',     bg: 'bg-sky-50',     dot: 'bg-sky-500' },
    'Environment & Sustainability':    { icon: Leaf,          color: 'text-lime-600',    bg: 'bg-lime-50',    dot: 'bg-lime-500' },
    'Research & Technology':           { icon: FlaskConical,  color: 'text-purple-600',  bg: 'bg-purple-50',  dot: 'bg-purple-500' },
    'Legal & Regulatory':              { icon: Scale,         color: 'text-amber-600',   bg: 'bg-amber-50',   dot: 'bg-amber-500' },
    'Other':                           { icon: MoreHorizontal,color: 'text-gray-500',    bg: 'bg-gray-50',    dot: 'bg-gray-400' },
};

function fmtDate(d) {
    if (!d) return null;
    try { return new Date(d).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }); }
    catch { return d; }
}

function LockedModule() {
    return (
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-center px-6">
            <div className="h-16 w-16 rounded-full bg-muted flex items-center justify-center">
                <Lock className="h-7 w-7 text-muted-foreground" />
            </div>
            <div>
                <h2 className="text-lg font-semibold text-foreground">Parliament Intel is restricted</h2>
                <p className="text-sm text-muted-foreground mt-1">Available to the MP only.</p>
            </div>
        </div>
    );
}

// ── Screen 1: Ministry list ────────────────────────────────────────────────────

function MinistryOverview({ onSelectMinistry, color }) {
    const [ministries, setMinistries] = useState([]);
    const [loading, setLoading]       = useState(true);
    const [search, setSearch]         = useState('');

    useEffect(() => {
        apiGet('/api/parliament-intel/ministries')
            .then(d => setMinistries(d.ministries || []))
            .catch(() => {})
            .finally(() => setLoading(false));
    }, []);

    const filtered = ministries.filter(m =>
        !search || (m.ministry || '').toLowerCase().includes(search.toLowerCase())
    );

    const totalPQs = ministries.reduce((s, m) => s + (m.classified_count || 0), 0);

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-foreground">Parliament Intel</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    What the government has said in Parliament — classified by ministry and topic
                </p>
            </div>

            {/* Stats bar */}
            <div className="flex items-center gap-6 text-sm flex-wrap">
                <div className="flex items-center gap-2">
                    <span className="font-semibold text-foreground">{ministries.length}</span>
                    <span className="text-muted-foreground">Ministries</span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="font-semibold text-foreground">{totalPQs.toLocaleString()}</span>
                    <span className="text-muted-foreground">Classified PQs</span>
                </div>
            </div>

            {/* Search */}
            <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                    className="pl-9"
                    placeholder="Search ministries…"
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                />
            </div>

            {loading ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {[1,2,3,4,5,6].map(i => <Skeleton key={i} className="h-24 w-full rounded-xl" />)}
                </div>
            ) : filtered.length === 0 ? (
                <div className="text-center py-16 text-muted-foreground">
                    <Building2 className="h-10 w-10 mx-auto mb-3 opacity-30" />
                    <p className="text-sm">
                        {search ? 'No ministries match your search' : 'No classified PQs yet. Ask your admin to run Topic Classification.'}
                    </p>
                </div>
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {filtered.map(m => (
                        <button
                            key={m.ministry}
                            onClick={() => onSelectMinistry(m.ministry)}
                            className="text-left w-full p-4 rounded-xl border border-border bg-card hover:bg-accent/40 hover:border-border/80 transition-all group"
                        >
                            <div className="flex items-start justify-between gap-2">
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-semibold text-foreground leading-snug line-clamp-2 group-hover:text-primary transition-colors">
                                        {m.ministry}
                                    </p>
                                    <div className="flex items-center gap-3 mt-2 flex-wrap">
                                        <span className="text-xs text-muted-foreground">
                                            <span className="font-medium text-foreground">{m.classified_count?.toLocaleString()}</span> answers
                                        </span>
                                        <span className="text-xs text-muted-foreground">
                                            <span className="font-medium text-foreground">{m.topic_count}</span> topics
                                        </span>
                                    </div>
                                </div>
                                <ChevronRight className="h-4 w-4 text-muted-foreground/40 group-hover:text-muted-foreground shrink-0 mt-0.5 transition-colors" />
                            </div>
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}

// ── Screen 2: Topic cards ──────────────────────────────────────────────────────

function MinistryTopics({ ministry, mpState, onBack, onSelectTopic, color }) {
    const [topics, setTopics]   = useState([]);
    const [loading, setLoading] = useState(true);
    const [stateFilter, setStateFilter] = useState(mpState || '');

    const load = useCallback(() => {
        setLoading(true);
        const params = stateFilter ? `?state=${encodeURIComponent(stateFilter)}` : '';
        apiGet(`/api/parliament-intel/ministry/${encodeURIComponent(ministry)}/topics${params}`)
            .then(d => setTopics(d.topics || []))
            .catch(() => {})
            .finally(() => setLoading(false));
    }, [ministry, stateFilter]);

    useEffect(() => { load(); }, [load]);

    const totalAnswers = topics.reduce((s, t) => s + (t.total_count || 0), 0);
    const stateAnswers = stateFilter ? topics.reduce((s, t) => s + (t.state_count || 0), 0) : 0;

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-start gap-3">
                <Button variant="ghost" size="icon" className="h-8 w-8 mt-0.5 shrink-0" onClick={onBack}>
                    <ChevronLeft className="h-4 w-4" />
                </Button>
                <div className="flex-1 min-w-0">
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">Ministry</p>
                    <h2 className="text-xl font-bold text-foreground leading-snug">{ministry}</h2>
                </div>
            </div>

            {/* State filter */}
            <div className="flex items-center gap-3 p-3 rounded-xl border border-border bg-card flex-wrap">
                <MapPin className="h-4 w-4 text-muted-foreground shrink-0" />
                <div className="flex-1 min-w-[160px]">
                    <Input
                        className="h-8 text-sm"
                        placeholder="Filter by state (e.g. Karnataka)"
                        value={stateFilter}
                        onChange={e => setStateFilter(e.target.value)}
                    />
                </div>
                <Button variant="outline" size="sm" className="h-8" onClick={load}>
                    <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
                    Apply
                </Button>
                {stateFilter && (
                    <Button variant="ghost" size="sm" className="h-8 text-muted-foreground" onClick={() => setStateFilter('')}>
                        Clear
                    </Button>
                )}
            </div>

            {/* Summary */}
            {!loading && (
                <div className="flex items-center gap-6 text-sm flex-wrap">
                    <span className="text-muted-foreground">
                        <span className="font-semibold text-foreground">{totalAnswers.toLocaleString()}</span> total answers
                    </span>
                    {stateFilter && stateAnswers > 0 && (
                        <span className="flex items-center gap-1.5 text-muted-foreground">
                            <MapPin className="h-3.5 w-3.5" />
                            <span className="font-semibold text-foreground">{stateAnswers.toLocaleString()}</span> mention {stateFilter}
                        </span>
                    )}
                </div>
            )}

            {/* Topic cards */}
            {loading ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {[1,2,3,4,5,6].map(i => <Skeleton key={i} className="h-28 w-full rounded-xl" />)}
                </div>
            ) : topics.length === 0 ? (
                <div className="text-center py-16 text-muted-foreground">
                    <FileText className="h-10 w-10 mx-auto mb-3 opacity-30" />
                    <p className="text-sm">No classified PQs for this ministry yet.</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {topics.map(t => {
                        const meta = TOPIC_META[t.topic] || TOPIC_META['Other'];
                        const Icon = meta.icon;
                        const pct = stateFilter && t.total_count
                            ? Math.round((t.state_count || 0) / t.total_count * 100)
                            : null;
                        return (
                            <button
                                key={t.topic}
                                onClick={() => onSelectTopic(t.topic)}
                                className="text-left p-4 rounded-xl border border-border bg-card hover:bg-accent/40 hover:border-border/80 transition-all group"
                            >
                                <div className={cn('h-9 w-9 rounded-lg flex items-center justify-center mb-3', meta.bg)}>
                                    <Icon className={cn('h-4 w-4', meta.color)} />
                                </div>
                                <p className="text-sm font-semibold text-foreground leading-snug group-hover:text-primary transition-colors">
                                    {t.topic}
                                </p>
                                <div className="mt-2 space-y-1">
                                    <p className="text-xs text-muted-foreground">
                                        <span className="font-medium text-foreground">{t.total_count?.toLocaleString()}</span> answers
                                    </p>
                                    {stateFilter && (
                                        <div className="flex items-center gap-1.5">
                                            <span className={cn('inline-block h-1.5 w-1.5 rounded-full shrink-0', meta.dot)} />
                                            <span className="text-xs text-muted-foreground">
                                                <span className="font-medium text-foreground">{t.state_count || 0}</span> mention {stateFilter}
                                                {pct !== null && pct > 0 && (
                                                    <span className="text-muted-foreground/60"> ({pct}%)</span>
                                                )}
                                            </span>
                                        </div>
                                    )}
                                </div>
                            </button>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

// ── Screen 3: PQ list ─────────────────────────────────────────────────────────

function PQRow({ q }) {
    const [expanded, setExpanded] = useState(false);

    return (
        <div className="border-b border-border last:border-0">
            <div
                className="p-4 hover:bg-accent/20 transition-colors cursor-pointer"
                onClick={() => setExpanded(e => !e)}
            >
                <div className="flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                            {q.question_type && (
                                <Badge variant="secondary" className={cn(
                                    'text-[10px] capitalize',
                                    q.question_type === 'starred'   && 'bg-amber-100 text-amber-700',
                                    q.question_type === 'unstarred' && 'bg-blue-100 text-blue-700',
                                )}>
                                    {q.question_type.replace('_', ' ')}
                                </Badge>
                            )}
                            {q.session_name && (
                                <span className="text-xs text-muted-foreground">{q.session_name}</span>
                            )}
                            {q.date_asked && (
                                <span className="text-xs text-muted-foreground">{fmtDate(q.date_asked)}</span>
                            )}
                        </div>
                        <p className="text-sm font-medium text-foreground leading-snug">
                            {q.subject || 'Untitled question'}
                        </p>
                        {q.mp_name && (
                            <p className="text-xs text-muted-foreground mt-0.5">Asked by {q.mp_name}</p>
                        )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                        {q.prs_url && (
                            <a
                                href={q.prs_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={e => e.stopPropagation()}
                                className="text-xs text-primary hover:underline flex items-center gap-1"
                            >
                                PRS <ExternalLink className="h-3 w-3" />
                            </a>
                        )}
                        {expanded
                            ? <ChevronUp className="h-4 w-4 text-muted-foreground" />
                            : <ChevronDown className="h-4 w-4 text-muted-foreground" />
                        }
                    </div>
                </div>
            </div>

            {expanded && q.answer_text && (
                <div className="px-4 pb-4">
                    <div className="rounded-lg bg-muted/40 border border-border p-4">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                            Ministry Answer (verbatim)
                        </p>
                        <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
                            {q.answer_text}
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
}

function TopicQuestions({ ministry, topic, mpState, onBack, color }) {
    const [data, setData]         = useState(null);
    const [loading, setLoading]   = useState(true);
    const [page, setPage]         = useState(1);
    const [stateFilter, setStateFilter] = useState(mpState || '');
    const [stateInput, setStateInput]   = useState(mpState || '');

    const load = useCallback(() => {
        setLoading(true);
        const params = new URLSearchParams({ page: String(page), limit: '20' });
        if (stateFilter) params.set('state', stateFilter);
        apiGet(`/api/parliament-intel/ministry/${encodeURIComponent(ministry)}/topic/${encodeURIComponent(topic)}/questions?${params}`)
            .then(d => setData(d))
            .catch(() => setData(null))
            .finally(() => setLoading(false));
    }, [ministry, topic, stateFilter, page]);

    useEffect(() => { load(); }, [load]);
    useEffect(() => { setPage(1); }, [stateFilter]);

    const questions = data?.questions || [];
    const total     = data?.total || 0;
    const pages     = data?.pages || 1;

    const meta = TOPIC_META[topic] || TOPIC_META['Other'];
    const Icon = meta.icon;

    const applyState = () => { setStateFilter(stateInput); };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-start gap-3">
                <Button variant="ghost" size="icon" className="h-8 w-8 mt-0.5 shrink-0" onClick={onBack}>
                    <ChevronLeft className="h-4 w-4" />
                </Button>
                <div className="flex-1 min-w-0">
                    <p className="text-xs text-muted-foreground truncate">{ministry}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                        <div className={cn('h-7 w-7 rounded-md flex items-center justify-center shrink-0', meta.bg)}>
                            <Icon className={cn('h-3.5 w-3.5', meta.color)} />
                        </div>
                        <h2 className="text-xl font-bold text-foreground">{topic}</h2>
                    </div>
                </div>
            </div>

            {/* State filter */}
            <div className="flex items-center gap-2 flex-wrap">
                <MapPin className="h-4 w-4 text-muted-foreground shrink-0" />
                <Input
                    className="h-8 text-sm flex-1 min-w-[160px] max-w-xs"
                    placeholder="Filter by state…"
                    value={stateInput}
                    onChange={e => setStateInput(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && applyState()}
                />
                <Button variant="outline" size="sm" className="h-8" onClick={applyState}>
                    Apply
                </Button>
                {stateFilter && (
                    <Button variant="ghost" size="sm" className="h-8 text-muted-foreground"
                        onClick={() => { setStateFilter(''); setStateInput(''); }}>
                        Clear
                    </Button>
                )}
                <span className="text-xs text-muted-foreground ml-auto">
                    {total.toLocaleString()} answer{total !== 1 ? 's' : ''}
                    {stateFilter && ` mentioning ${stateFilter}`}
                </span>
            </div>

            {/* PQ list */}
            {loading ? (
                <div className="space-y-2">
                    {[1,2,3,4,5].map(i => <Skeleton key={i} className="h-20 w-full rounded-xl" />)}
                </div>
            ) : questions.length === 0 ? (
                <div className="text-center py-16 text-muted-foreground border rounded-xl">
                    <FileText className="h-10 w-10 mx-auto mb-3 opacity-30" />
                    <p className="text-sm">
                        {stateFilter
                            ? `No answers mention ${stateFilter} in this topic.`
                            : 'No questions found.'}
                    </p>
                </div>
            ) : (
                <>
                    <div className="rounded-xl border border-border overflow-hidden bg-card">
                        {questions.map(q => <PQRow key={q.id} q={q} />)}
                    </div>

                    {/* Pagination */}
                    {pages > 1 && (
                        <div className="flex items-center justify-between pt-2">
                            <span className="text-xs text-muted-foreground">Page {page} of {pages}</span>
                            <div className="flex gap-2">
                                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
                                    <ChevronLeft className="h-4 w-4" />
                                </Button>
                                <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(p => p + 1)}>
                                    <ChevronRight className="h-4 w-4" />
                                </Button>
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}

// ── Root ───────────────────────────────────────────────────────────────────────

export default function ParliamentIntelPage() {
    const { user } = useAuth();
    const [screen,   setScreen]   = useState('overview');
    const [ministry, setMinistry] = useState(null);
    const [topic,    setTopic]    = useState(null);
    const [mpState,  setMpState]  = useState('');

    const color = user?.theme_color || '#006a4d';

    // Fetch MP's home state from profile
    useEffect(() => {
        apiGet('/api/profile')
            .then(p => { if (p?.state) setMpState(p.state); })
            .catch(() => {});
    }, []);

    if (user && user.role !== 'mp' && user.role !== 'admin') {
        return <LockedModule />;
    }

    const goMinistry = (m) => { setMinistry(m); setTopic(null); setScreen('ministry'); };
    const goTopic    = (t) => { setTopic(t); setScreen('questions'); };
    const goBack     = () => {
        if (screen === 'questions') { setScreen('ministry'); setTopic(null); }
        else                        { setScreen('overview'); setMinistry(null); }
    };

    return (
        <div className="max-w-5xl mx-auto">
            {screen === 'overview' && (
                <MinistryOverview onSelectMinistry={goMinistry} color={color} />
            )}
            {screen === 'ministry' && ministry && (
                <MinistryTopics
                    ministry={ministry}
                    mpState={mpState}
                    onBack={goBack}
                    onSelectTopic={goTopic}
                    color={color}
                />
            )}
            {screen === 'questions' && ministry && topic && (
                <TopicQuestions
                    ministry={ministry}
                    topic={topic}
                    mpState={mpState}
                    onBack={goBack}
                    color={color}
                />
            )}
        </div>
    );
}
