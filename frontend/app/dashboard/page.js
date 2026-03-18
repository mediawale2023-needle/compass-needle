'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet } from '@/lib/api';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
    Loader2,
    AlertTriangle,
    CheckCircle2,
    Building2,
    Mail,
    PenTool,
    Gift,
    ArrowRight,
    TrendingUp,
    Clock,
    FileText,
    ChevronDown,
    ChevronUp,
    ExternalLink,
    Briefcase,
    BarChart2,
    CalendarClock,
    FileQuestion,
} from 'lucide-react';

function PQCalendarCard({ pq }) {
    if (!pq || pq.window_state === 'unknown') return null;

    const configs = {
        open: {
            border:   'border-l-blue-500',
            bg:       'bg-blue-50/50',
            dot:      'bg-blue-500',
            ping:     'bg-blue-400',
            label:    `${pq.days_remaining} day${pq.days_remaining !== 1 ? 's' : ''} left to submit`,
            sublabel: `Deadline: ${pq.window_close}`,
            showCta:  true,
        },
        not_yet: {
            border:   'border-l-muted',
            bg:       '',
            dot:      'bg-muted-foreground/40',
            ping:     null,
            label:    `PQ window opens in ${pq.days_until_open} day${pq.days_until_open !== 1 ? 's' : ''}`,
            sublabel: `Opens ${pq.next_window_open} · Closes ${pq.window_close}`,
            showCta:  false,
        },
        closed: {
            border:   'border-l-amber-400',
            bg:       'bg-amber-50/30',
            dot:      'bg-amber-400',
            ping:     null,
            label:    'Submission deadline passed',
            sublabel: `${pq.target_session} starts ${pq.session_start}`,
            showCta:  false,
        },
        in_session: {
            border:   'border-l-muted',
            bg:       '',
            dot:      'bg-muted-foreground/40',
            ping:     null,
            label:    pq.next_session_name
                        ? `PQ window for ${pq.next_session_name} opens ${pq.next_window_open}`
                        : 'PQ submissions open during recess',
            sublabel: null,
            showCta:  false,
        },
    };

    const cfg = configs[pq.window_state] || configs.not_yet;

    return (
        <Card className={cn('border-l-4', cfg.border, cfg.bg)}>
            <CardContent className="py-4">
                <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div className="flex items-start gap-2.5">
                        <div className="mt-0.5 shrink-0">
                            {cfg.ping ? (
                                <span className="relative flex h-2.5 w-2.5">
                                    <span className={cn('animate-ping absolute inline-flex h-full w-full rounded-full opacity-75', cfg.ping)} />
                                    <span className={cn('relative inline-flex rounded-full h-2.5 w-2.5', cfg.dot)} />
                                </span>
                            ) : (
                                <span className={cn('block h-2.5 w-2.5 rounded-full', cfg.dot)} />
                            )}
                        </div>
                        <div>
                            <div className="flex items-center gap-2 flex-wrap">
                                <CalendarClock className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                                <span className="text-sm font-semibold text-foreground">
                                    PQ Calendar — {pq.target_session}
                                </span>
                                {pq.pqs_drafted > 0 && (
                                    <Badge variant="secondary" className="flex items-center gap-1 text-[10px]">
                                        <FileQuestion className="h-2.5 w-2.5" />
                                        {pq.pqs_drafted} drafted
                                    </Badge>
                                )}
                            </div>
                            <p className="text-xs text-muted-foreground mt-0.5">{cfg.label}</p>
                            {cfg.sublabel && (
                                <p className="text-xs text-muted-foreground/70 mt-0.5">{cfg.sublabel}</p>
                            )}
                        </div>
                    </div>
                    {cfg.showCta && (
                        <Button asChild size="sm">
                            <Link href="/dashboard/drafter?mode=question">
                                Draft a PQ
                                <ArrowRight className="h-4 w-4 ml-1" />
                            </Link>
                        </Button>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}

const QUICK_ACTIONS = [
    { label: 'Upload Letter', href: '/dashboard/letterbox', desc: 'Scan or upload', icon: Mail },
    { label: 'Draft Response', href: '/dashboard/drafter', desc: 'AI-assisted writing', icon: PenTool },
    { label: 'Find a Scheme', href: '/dashboard/schemes', desc: 'Match constituents', icon: Gift },
];

function daysAgo(dateStr) {
    if (!dateStr) return null;
    const diff = Date.now() - new Date(dateStr).getTime();
    return Math.floor(diff / (1000 * 60 * 60 * 24));
}

function AgeBadge({ days }) {
    if (days === null) return null;
    return (
        <Badge variant="outline" className={cn(
            "text-[10px] font-bold shrink-0",
            days >= 14 && "border-destructive text-destructive bg-destructive/10",
            days >= 7 && days < 14 && "border-amber-500 text-amber-600 bg-amber-50",
            days < 7 && "border-emerald-500 text-emerald-600 bg-emerald-50"
        )}>
            {days}d
        </Badge>
    );
}

export default function DashboardPage() {
    const { user } = useAuth();
    const router = useRouter();

    const [summary, setSummary] = useState(null);
    const [reportCard, setReportCard] = useState(null);
    const [news, setNews] = useState({ national: [], local: [] });
    const [newsTab, setNewsTab] = useState('national');
    const [showNews, setShowNews] = useState(true);
    const [parliament, setParliament] = useState(null);
    const [parlExpanded, setParlExpanded] = useState(false);
    const [pqCalendar, setPqCalendar] = useState(null);
    const [staleCases, setStaleCases] = useState([]);
    const [allCases, setAllCases] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function load() {
            try {
                const [sum, rc, nat, loc, parl, cases, pqCal] = await Promise.all([
                    apiGet('/api/dashboard/summary').catch(() => ({
                        category_breakdown: {}, status_breakdown: {}, red_zones: [], critical_count: 0,
                    })),
                    apiGet('/api/activity/report-card').catch(() => null),
                    apiGet('/api/news?news_type=national').catch(() => ({ articles: [] })),
                    apiGet('/api/news?news_type=local').catch(() => ({ articles: [] })),
                    apiGet('/api/parliament/status').catch(() => null),
                    apiGet('/api/cases?page=1&limit=50').catch(() => ({ cases: [] })),
                    apiGet('/api/parliament/pq-calendar').catch(() => null),
                ]);

                setSummary(sum);
                setReportCard(rc);
                setNews({ national: nat.articles || [], local: loc.articles || [] });
                setParliament(parl);
                setPqCalendar(pqCal);

                const fetchedCases = cases.cases || cases.items || [];
                setAllCases(fetchedCases);
                const pending = fetchedCases
                    .filter(c => (c.status || '').toLowerCase() === 'new')
                    .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
                    .slice(0, 6);
                setStaleCases(pending);
            } catch (err) {
                console.error(err);
                setSummary({ category_breakdown: {}, status_breakdown: {}, red_zones: [], critical_count: 0 });
            } finally {
                setLoading(false);
            }
        }
        load();
    }, []);

    if (loading) return (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <span className="text-sm text-muted-foreground">Loading dashboard...</span>
        </div>
    );

    const cats = summary?.category_breakdown || {};
    const statuses = summary?.status_breakdown || {};
    const totalCases = Object.values(statuses).reduce((a, b) => a + b, 0);
    const maxCat = Math.max(...Object.values(cats), 1);
    const newCount = statuses['new'] || 0;
    const redCount = summary?.red_zones?.length || 0;
    const hasUrgent = newCount > 0 || redCount > 0;
    const isEmpty = totalCases === 0;

    const STAT_CARDS = [
        { label: 'Total Cases', value: totalCases, color: 'primary', filter: '', icon: Briefcase },
        { label: 'New / Open', value: statuses['new'] || 0, color: 'blue', filter: 'new', icon: AlertTriangle },
        { label: 'In Progress', value: statuses['in_progress'] || 0, color: 'amber', filter: 'in_progress', icon: Clock },
        { label: 'Resolved', value: statuses['resolved'] || 0, color: 'emerald', filter: 'resolved', icon: CheckCircle2 },
    ];

    const resolvedCount = statuses['resolved'] || 0;
    const resolutionRate = totalCases > 0 ? Math.round((resolvedCount / totalCases) * 100) : 0;
    const avgAge = allCases.length > 0
        ? Math.round(allCases.reduce((sum, c) => sum + (daysAgo(c.created_at) || 0), 0) / allCases.length)
        : 0;
    const oneWeekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
    const newThisWeek = allCases.filter(c =>
        (c.status || '').toLowerCase() === 'new' && new Date(c.created_at).getTime() > oneWeekAgo
    ).length;
    const topIssue = Object.keys(cats)[0] || '—';

    const OUTCOME_METRICS = [
        { label: 'Resolution Rate', value: totalCases > 0 ? `${resolutionRate}%` : '—', icon: CheckCircle2, highlight: resolutionRate >= 60 ? 'emerald' : resolutionRate >= 30 ? 'amber' : 'destructive' },
        { label: 'Avg Case Age', value: allCases.length > 0 ? `${avgAge}d` : '—', icon: Clock, highlight: avgAge <= 7 ? 'emerald' : avgAge <= 14 ? 'amber' : 'destructive' },
        { label: 'New This Week', value: newThisWeek, icon: TrendingUp, highlight: newThisWeek === 0 ? 'emerald' : newThisWeek <= 5 ? 'amber' : 'destructive' },
        { label: 'Top Issue', value: topIssue, icon: AlertTriangle, highlight: 'default' },
    ];

    return (
        <div className="space-y-6">
            {/* Parliament Status */}
            {parliament && (
                <Card className={cn(
                    "border-l-4",
                    parliament.in_session ? "border-l-emerald-500 bg-emerald-50/50" : "border-l-muted"
                )}>
                    <CardContent className="py-4">
                        {parliament.in_session ? (
                            <div className="space-y-3">
                                <button
                                    onClick={() => setParlExpanded(v => !v)}
                                    className="w-full text-left focus:outline-none"
                                >
                                    <div className="flex items-center justify-between flex-wrap gap-2">
                                        <div className="flex items-center gap-2">
                                            <span className="relative flex h-2.5 w-2.5">
                                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                                                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
                                            </span>
                                            <span className="font-semibold text-emerald-800">
                                                House in Session — {parliament.session_name}
                                            </span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-xs text-muted-foreground">
                                                {parliament.day}, {parliament.date}
                                            </span>
                                            {parliament.business_items?.length > 0 && (
                                                parlExpanded
                                                    ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
                                                    : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                                            )}
                                        </div>
                                    </div>
                                </button>
                                {parliament.business_items?.length > 0 && (
                                    parlExpanded ? (
                                        <ol className="space-y-1.5 border-t border-emerald-200 pt-3">
                                            {parliament.business_items.map((item, i) => (
                                                <li key={i} className="flex items-start gap-2 text-sm text-emerald-900">
                                                    <span className="shrink-0 mt-0.5 h-4 w-4 rounded-full bg-emerald-100 text-emerald-700 text-[10px] font-bold flex items-center justify-center">
                                                        {i + 1}
                                                    </span>
                                                    {item}
                                                </li>
                                            ))}
                                        </ol>
                                    ) : (
                                        <div className="flex flex-wrap gap-1.5">
                                            {parliament.business_items.slice(0, 2).map((item, i) => (
                                                <Badge key={i} variant="secondary" className="bg-emerald-100 text-emerald-700 hover:bg-emerald-200">
                                                    {item}
                                                </Badge>
                                            ))}
                                            {parliament.business_items.length > 2 && (
                                                <Badge variant="outline" className="text-muted-foreground cursor-pointer" onClick={() => setParlExpanded(true)}>
                                                    +{parliament.business_items.length - 2} more
                                                </Badge>
                                            )}
                                        </div>
                                    )
                                )}
                            </div>
                        ) : (
                            <div className="flex items-center justify-between gap-2">
                                <div className="flex items-center gap-2">
                                    <span className="h-2.5 w-2.5 rounded-full bg-muted-foreground/40" />
                                    <span className="text-sm text-muted-foreground">{parliament.message}</span>
                                </div>
                                {parliament.next_session && (
                                    <span className="text-xs text-muted-foreground">
                                        Next: {parliament.next_session}
                                    </span>
                                )}
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* PQ Calendar */}
            <PQCalendarCard pq={pqCalendar} />

            {/* Attention Banner */}
            {hasUrgent && (
                <Card className="border-destructive/50 bg-destructive/5">
                    <CardContent className="py-4 flex items-center justify-between gap-4 flex-wrap">
                        <div className="flex items-center gap-3">
                            <div className="h-10 w-10 rounded-full bg-destructive/10 flex items-center justify-center shrink-0">
                                <AlertTriangle className="h-5 w-5 text-destructive" />
                            </div>
                            <div>
                                <p className="font-semibold text-destructive">
                                    {newCount > 0 && `${newCount} new grievance${newCount !== 1 ? 's' : ''} need${newCount === 1 ? 's' : ''} attention`}
                                    {newCount > 0 && redCount > 0 && ' · '}
                                    {redCount > 0 && `${redCount} zone${redCount !== 1 ? 's' : ''} flagged`}
                                </p>
                                <p className="text-xs text-muted-foreground mt-0.5">
                                    Review these items to keep your constituents happy
                                </p>
                            </div>
                        </div>
                        <Button variant="destructive" size="sm" asChild>
                            <Link href="/dashboard/sansadx?status=new">
                                Review Now
                                <ArrowRight className="h-4 w-4 ml-1" />
                            </Link>
                        </Button>
                    </CardContent>
                </Card>
            )}

            {/* Empty State */}
            {isEmpty ? (
                <Card className="text-center py-12">
                    <CardContent className="space-y-4">
                        <div className="h-20 w-20 mx-auto rounded-full bg-primary/10 flex items-center justify-center">
                            <Building2 className="h-10 w-10 text-primary" />
                        </div>
                        <div>
                            <h2 className="text-lg font-bold text-foreground">Welcome to Compass Needle</h2>
                            <p className="text-sm text-muted-foreground mt-2 max-w-md mx-auto">
                                Your constituency office is ready. Start by uploading a letter from a constituent,
                                logging a new case, or drafting your first parliamentary question.
                            </p>
                        </div>
                        <div className="flex flex-wrap justify-center gap-3 pt-4">
                            <Button asChild>
                                <Link href="/dashboard/letterbox">Upload a Letter</Link>
                            </Button>
                            <Button variant="outline" asChild>
                                <Link href="/dashboard/sansadx">Log a Case</Link>
                            </Button>
                            <Button variant="ghost" asChild>
                                <Link href="/dashboard/drafter">Draft a PQ</Link>
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            ) : (
                <>
                    {/* Quick Actions */}
                    <div className="grid grid-cols-3 gap-3">
                        {QUICK_ACTIONS.map(({ label, href, desc, icon: Icon }) => (
                            <Link key={href} href={href}>
                                <Card className="h-full card-hover cursor-pointer">
                                    <CardContent className="p-4 text-center">
                                        <div className="h-10 w-10 mx-auto rounded-lg bg-primary/10 flex items-center justify-center mb-3">
                                            <Icon className="h-5 w-5 text-primary" />
                                        </div>
                                        <p className="text-sm font-semibold text-foreground">{label}</p>
                                        <p className="text-xs text-muted-foreground mt-0.5">{desc}</p>
                                    </CardContent>
                                </Card>
                            </Link>
                        ))}
                    </div>

                    {/* Stat Cards */}
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                        {STAT_CARDS.map(({ label, value, color, filter, icon: Icon }) => {
                            const href = filter ? `/dashboard/sansadx?status=${filter}` : '/dashboard/sansadx';
                            return (
                                <Link key={label} href={href}>
                                    <Card className={cn(
                                        "card-hover cursor-pointer border-l-4",
                                        color === 'primary' && "border-l-primary",
                                        color === 'blue' && "border-l-blue-500",
                                        color === 'amber' && "border-l-amber-500",
                                        color === 'emerald' && "border-l-emerald-500"
                                    )}>
                                        <CardContent className="p-5">
                                            <div className="flex items-center justify-between mb-3">
                                                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                                    {label}
                                                </span>
                                                <Icon className={cn(
                                                    "h-4 w-4",
                                                    color === 'primary' && "text-primary",
                                                    color === 'blue' && "text-blue-500",
                                                    color === 'amber' && "text-amber-500",
                                                    color === 'emerald' && "text-emerald-500"
                                                )} />
                                            </div>
                                            <p className="text-3xl font-bold text-foreground">{value}</p>
                                            <p className="text-xs text-muted-foreground mt-2">
                                                View cases →
                                            </p>
                                        </CardContent>
                                    </Card>
                                </Link>
                            );
                        })}
                    </div>

                    {/* Main Grid */}
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* Category Breakdown */}
                        <Card className="lg:col-span-2">
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <TrendingUp className="h-5 w-5 text-primary" />
                                    Category Breakdown
                                </CardTitle>
                                <CardDescription>
                                    Click any category to view those cases in Briefcase
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                {Object.keys(cats).length > 0 ? (
                                    <div className="space-y-4">
                                        {Object.entries(cats)
                                            .sort((a, b) => b[1] - a[1])
                                            .slice(0, 8)
                                            .map(([cat, count]) => {
                                                const pct = Math.round((count / maxCat) * 100);
                                                return (
                                                    <button
                                                        key={cat}
                                                        className="w-full text-left group"
                                                        onClick={() => router.push(`/dashboard/sansadx?category=${encodeURIComponent(cat)}`)}
                                                    >
                                                        <div className="flex items-center justify-between mb-2">
                                                            <span className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">
                                                                {cat}
                                                            </span>
                                                            <span className="text-sm font-bold text-foreground">
                                                                {count}
                                                            </span>
                                                        </div>
                                                        <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
                                                            <div
                                                                className="h-full rounded-full bg-primary transition-all group-hover:bg-primary/80"
                                                                style={{ width: `${pct}%` }}
                                                            />
                                                        </div>
                                                    </button>
                                                );
                                            })}
                                    </div>
                                ) : (
                                    <div className="text-center py-8 text-muted-foreground">
                                        No data available
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Right Column */}
                        <div className="space-y-6">
                            {/* Constituency Health */}
                            <Card>
                                <CardHeader className="pb-3">
                                    <div className="flex items-center justify-between">
                                        <CardTitle className="flex items-center gap-2 text-base">
                                            <BarChart2 className="h-4 w-4 text-primary" />
                                            Constituency Health
                                        </CardTitle>
                                        <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
                                            {new Date().toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })}
                                        </span>
                                    </div>
                                    <CardDescription>Outcome metrics — not output</CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid grid-cols-2 gap-3">
                                        {OUTCOME_METRICS.map(({ label, value, icon: Icon, highlight }) => (
                                            <div key={label} className={cn(
                                                "rounded-lg p-3",
                                                highlight === 'emerald' && "bg-emerald-50",
                                                highlight === 'amber' && "bg-amber-50",
                                                highlight === 'destructive' && "bg-destructive/5",
                                                highlight === 'default' && "bg-primary/5",
                                            )}>
                                                <div className="flex items-center gap-1.5 mb-1">
                                                    <Icon className={cn(
                                                        "h-3.5 w-3.5",
                                                        highlight === 'emerald' && "text-emerald-600",
                                                        highlight === 'amber' && "text-amber-500",
                                                        highlight === 'destructive' && "text-destructive",
                                                        highlight === 'default' && "text-primary",
                                                    )} />
                                                </div>
                                                <p className={cn(
                                                    "text-2xl font-bold truncate",
                                                    label === 'Top Issue' ? "text-base mt-1" : "text-foreground"
                                                )}>{value}</p>
                                                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mt-0.5 leading-tight">{label}</p>
                                            </div>
                                        ))}
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Pending Triage */}
                            <Card>
                                <CardHeader className="pb-3">
                                    <CardTitle className="flex items-center gap-2 text-base">
                                        <Clock className="h-4 w-4 text-amber-500" />
                                        Pending Triage
                                    </CardTitle>
                                    <CardDescription>
                                        New cases no one has touched yet
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-0">
                                    {staleCases.length > 0 ? (
                                        <div className="divide-y divide-border -mx-6">
                                            {staleCases.map(c => {
                                                const age = daysAgo(c.created_at);
                                                const summary = c.raw_message
                                                    ? c.raw_message.slice(0, 80) + (c.raw_message.length > 80 ? '…' : '')
                                                    : c.category || '—';
                                                const sub = [c.category, c.user_phone].filter(Boolean).join(' · ');
                                                return (
                                                    <button
                                                        key={c.id}
                                                        className="w-full px-6 py-3 flex items-start justify-between gap-2 hover:bg-accent/50 transition-colors text-left"
                                                        onClick={() => router.push(`/dashboard/sansadx?status=new&case_id=${c.id}`)}
                                                    >
                                                        <div className="min-w-0">
                                                            <p className="text-xs font-bold text-muted-foreground">#{c.id}</p>
                                                            <p className="text-sm font-medium text-foreground leading-snug line-clamp-2">{summary}</p>
                                                            {sub && <p className="text-xs text-muted-foreground truncate mt-0.5">{sub}</p>}
                                                        </div>
                                                        <AgeBadge days={age} />
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    ) : (
                                        <div className="flex items-center gap-2 text-emerald-600 py-2">
                                            <CheckCircle2 className="h-4 w-4" />
                                            <span className="text-sm">All new cases actioned — great work!</span>
                                        </div>
                                    )}
                                </CardContent>
                                <div className="px-6 py-3 border-t border-border">
                                    <Button variant="link" className="p-0 h-auto text-primary" asChild>
                                        <Link href="/dashboard/sansadx?status=new">
                                            View all pending cases →
                                        </Link>
                                    </Button>
                                </div>
                            </Card>
                        </div>
                    </div>

                    {/* Media Monitoring */}
                    <Card>
                        <CardHeader className="cursor-pointer" onClick={() => setShowNews(v => !v)}>
                            <div className="flex items-center justify-between">
                                <div>
                                    <CardTitle className="flex items-center gap-2">
                                        <FileText className="h-5 w-5 text-primary" />
                                        Media Monitoring
                                    </CardTitle>
                                    <CardDescription className="mt-1">
                                        Your name in the press · Critical issues in your constituency
                                    </CardDescription>
                                </div>
                                <Button variant="ghost" size="sm" className="h-8 w-8 p-0 shrink-0">
                                    {showNews ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                                </Button>
                            </div>
                        </CardHeader>
                        {showNews && (
                            <CardContent className="pt-0">
                                <Tabs value={newsTab} onValueChange={setNewsTab}>
                                    <TabsList className="mb-4">
                                        <TabsTrigger value="national">In the News</TabsTrigger>
                                        <TabsTrigger value="local">Constituency</TabsTrigger>
                                    </TabsList>
                                    <TabsContent value="national" className="mt-0">
                                        <NewsList articles={news.national} emptyText="No press coverage found today" />
                                    </TabsContent>
                                    <TabsContent value="local" className="mt-0">
                                        <NewsList articles={news.local} emptyText="No local coverage found today" />
                                    </TabsContent>
                                </Tabs>
                            </CardContent>
                        )}
                    </Card>
                </>
            )}
        </div>
    );
}

function NewsList({ articles, emptyText = 'No coverage found today' }) {
    if (articles.length === 0) {
        return (
            <p className="text-sm text-muted-foreground text-center py-4">
                {emptyText}
            </p>
        );
    }
    return (
        <ul className="space-y-3">
            {articles.slice(0, 5).map((a, i) => (
                <li key={i}>
                    <a
                        href={a.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="group flex items-start gap-2 text-sm text-foreground hover:text-primary transition-colors"
                    >
                        <ExternalLink className="h-3.5 w-3.5 mt-0.5 shrink-0 text-muted-foreground group-hover:text-primary" />
                        <span className="leading-snug">{a.title}</span>
                    </a>
                </li>
            ))}
        </ul>
    );
}
