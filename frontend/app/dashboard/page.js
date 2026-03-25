'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet } from '@/lib/api';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
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
    TrendingDown,
    Clock,
    FileText,
    MapPin,
    MessageSquare,
    Users,
    Flame,
    CalendarClock,
    FileQuestion,
    Zap,
    Target,
    Eye,
} from 'lucide-react';

// Priority indicator component
function PriorityIndicator({ level }) {
    if (level === 'critical') {
        return (
            <span className="inline-flex items-center gap-1.5 text-destructive font-semibold text-xs">
                <Flame className="h-3.5 w-3.5" />
                HIGH PRIORITY
            </span>
        );
    }
    if (level === 'attention') {
        return (
            <span className="inline-flex items-center gap-1.5 text-amber-600 font-semibold text-xs">
                <AlertTriangle className="h-3.5 w-3.5" />
                NEEDS ATTENTION
            </span>
        );
    }
    return null;
}

// Today's Briefing Item - Headline style
function BriefingItem({ headline, subtext, priority, onClick, trend }) {
    return (
        <button
            onClick={onClick}
            className={cn(
                "w-full text-left p-4 rounded-lg transition-all duration-200 group",
                "hover:bg-accent/50",
                priority === 'critical' && "bg-destructive/5 border-l-4 border-l-destructive",
                priority === 'attention' && "bg-amber-50/50 border-l-4 border-l-amber-500",
                !priority && "border-l-4 border-l-transparent hover:border-l-primary/30"
            )}
        >
            <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                    {priority && (
                        <div className="mb-2">
                            <PriorityIndicator level={priority} />
                        </div>
                    )}
                    <h3 className="text-base font-semibold text-foreground group-hover:text-primary transition-colors leading-snug">
                        {headline}
                    </h3>
                    {subtext && (
                        <p className="text-sm text-muted-foreground mt-1 leading-relaxed">
                            {subtext}
                        </p>
                    )}
                </div>
                {trend && (
                    <div className={cn(
                        "flex items-center gap-1 text-xs font-bold shrink-0 px-2 py-1 rounded",
                        trend > 0 ? "text-destructive bg-destructive/10" : "text-emerald-600 bg-emerald-50"
                    )}>
                        {trend > 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                        {Math.abs(trend)}%
                    </div>
                )}
            </div>
        </button>
    );
}

// Action Card - "What You Should Do Today"
function ActionCard({ icon: Icon, title, description, href, urgent }) {
    return (
        <Link href={href}>
            <Card className={cn(
                "h-full transition-all duration-200 hover:shadow-md hover:-translate-y-0.5 cursor-pointer group",
                urgent && "ring-2 ring-destructive/20 bg-destructive/5"
            )}>
                <CardContent className="p-5">
                    <div className="flex items-start gap-4">
                        <div className={cn(
                            "h-12 w-12 rounded-xl flex items-center justify-center shrink-0",
                            urgent ? "bg-destructive/10" : "bg-primary/10"
                        )}>
                            <Icon className={cn(
                                "h-6 w-6",
                                urgent ? "text-destructive" : "text-primary"
                            )} />
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                                <h3 className="font-semibold text-foreground group-hover:text-primary transition-colors">
                                    {title}
                                </h3>
                                {urgent && (
                                    <Badge variant="destructive" className="text-[10px] h-5">
                                        Urgent
                                    </Badge>
                                )}
                            </div>
                            <p className="text-sm text-muted-foreground mt-1">
                                {description}
                            </p>
                        </div>
                        <ArrowRight className="h-5 w-5 text-muted-foreground group-hover:text-primary group-hover:translate-x-1 transition-all shrink-0" />
                    </div>
                </CardContent>
            </Card>
        </Link>
    );
}

// Insight Card - Active metrics instead of passive
function InsightCard({ label, value, change, changeLabel, icon: Icon, highlight }) {
    return (
        <div className={cn(
            "p-4 rounded-xl",
            highlight === 'critical' && "bg-destructive/10",
            highlight === 'warning' && "bg-amber-50",
            highlight === 'success' && "bg-emerald-50",
            !highlight && "bg-accent/50"
        )}>
            <div className="flex items-center gap-2 mb-2">
                <Icon className={cn(
                    "h-4 w-4",
                    highlight === 'critical' && "text-destructive",
                    highlight === 'warning' && "text-amber-600",
                    highlight === 'success' && "text-emerald-600",
                    !highlight && "text-primary"
                )} />
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {label}
                </span>
            </div>
            <p className={cn(
                "text-2xl font-bold",
                highlight === 'critical' && "text-destructive",
                highlight === 'warning' && "text-amber-700",
                highlight === 'success' && "text-emerald-700",
                !highlight && "text-foreground"
            )}>
                {value}
            </p>
            {change !== undefined && (
                <p className={cn(
                    "text-xs mt-1",
                    change > 0 ? "text-destructive" : "text-emerald-600"
                )}>
                    {change > 0 ? '+' : ''}{change}% {changeLabel}
                </p>
            )}
        </div>
    );
}

// PQ Calendar Card
function PQCalendarCard({ pq }) {
    if (!pq || pq.window_state === 'unknown') return null;

    const configs = {
        open: {
            border: 'border-l-primary',
            bg: 'bg-primary/5',
            dot: 'bg-primary',
            ping: 'bg-primary/60',
            label: `${pq.days_remaining} day${pq.days_remaining !== 1 ? 's' : ''} left to submit`,
            sublabel: `Deadline: ${pq.window_close}`,
            showCta: true,
            urgent: pq.days_remaining <= 3,
        },
        not_yet: {
            border: 'border-l-muted',
            bg: '',
            dot: 'bg-muted-foreground/40',
            ping: null,
            label: `PQ window opens in ${pq.days_until_open} day${pq.days_until_open !== 1 ? 's' : ''}`,
            sublabel: `Opens ${pq.next_window_open}`,
            showCta: false,
        },
        closed: {
            border: 'border-l-amber-400',
            bg: 'bg-amber-50/30',
            dot: 'bg-amber-400',
            ping: null,
            label: 'Submission deadline passed',
            sublabel: `${pq.target_session} starts ${pq.session_start}`,
            showCta: false,
        },
        in_session: {
            border: 'border-l-muted',
            bg: '',
            dot: 'bg-muted-foreground/40',
            ping: null,
            label: pq.next_session_name
                ? `PQ window for ${pq.next_session_name} opens ${pq.next_window_open}`
                : 'PQ submissions open during recess',
            sublabel: null,
            showCta: false,
        },
    };

    const cfg = configs[pq.window_state] || configs.not_yet;

    return (
        <div className={cn('rounded-lg border-l-4 p-4', cfg.border, cfg.bg)}>
            <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="flex items-start gap-3">
                    <div className="mt-1 shrink-0">
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
                            <CalendarClock className="h-4 w-4 text-muted-foreground shrink-0" />
                            <span className="text-sm font-semibold text-foreground">
                                PQ Calendar — {pq.target_session}
                            </span>
                            {pq.pqs_drafted > 0 && (
                                <Badge variant="secondary" className="text-[10px]">
                                    <FileQuestion className="h-2.5 w-2.5 mr-1" />
                                    {pq.pqs_drafted} drafted
                                </Badge>
                            )}
                        </div>
                        <p className="text-sm text-muted-foreground mt-0.5">{cfg.label}</p>
                        {cfg.sublabel && (
                            <p className="text-xs text-muted-foreground/70 mt-0.5">{cfg.sublabel}</p>
                        )}
                    </div>
                </div>
                {cfg.showCta && (
                    <Button asChild size="sm" variant={cfg.urgent ? "destructive" : "default"}>
                        <Link href="/dashboard/drafter?mode=question">
                            Draft a PQ
                            <ArrowRight className="h-4 w-4 ml-1" />
                        </Link>
                    </Button>
                )}
            </div>
        </div>
    );
}

function daysAgo(dateStr) {
    if (!dateStr) return null;
    const diff = Date.now() - new Date(dateStr).getTime();
    return Math.floor(diff / (1000 * 60 * 60 * 24));
}

export default function DashboardPage() {
    const { user } = useAuth();
    const router = useRouter();

    const [summary, setSummary] = useState(null);
    const [news, setNews] = useState({ national: [], local: [] });
    const [parliament, setParliament] = useState(null);
    const [pqCalendar, setPqCalendar] = useState(null);
    const [allCases, setAllCases] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function load() {
            try {
                const [sum, nat, loc, parl, cases, pqCal] = await Promise.all([
                    apiGet('/api/dashboard/summary').catch(() => ({
                        category_breakdown: {}, status_breakdown: {}, red_zones: [], critical_count: 0,
                    })),
                    apiGet('/api/news?news_type=national').catch(() => ({ articles: [] })),
                    apiGet('/api/news?news_type=local').catch(() => ({ articles: [] })),
                    apiGet('/api/parliament/status').catch(() => null),
                    apiGet('/api/cases?page=1&limit=50').catch(() => ({ cases: [] })),
                    apiGet('/api/parliament/pq-calendar').catch(() => null),
                ]);

                setSummary(sum);
                setNews({ national: nat.articles || [], local: loc.articles || [] });
                setParliament(parl);
                setPqCalendar(pqCal);
                setAllCases(cases.cases || cases.items || []);
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
            <span className="text-sm text-muted-foreground">Loading your command center...</span>
        </div>
    );

    // Derive insights from data
    const cats = summary?.category_breakdown || {};
    const statuses = summary?.status_breakdown || {};
    const totalCases = Object.values(statuses).reduce((a, b) => a + b, 0);
    const newCount = statuses['new'] || 0;
    const inProgressCount = statuses['in_progress'] || 0;
    const resolvedCount = statuses['resolved'] || 0;
    const redZones = summary?.red_zones || [];
    const isEmpty = totalCases === 0;

    // Calculate trends and insights
    const resolutionRate = totalCases > 0 ? Math.round((resolvedCount / totalCases) * 100) : 0;
    const avgAge = allCases.length > 0
        ? Math.round(allCases.reduce((sum, c) => sum + (daysAgo(c.created_at) || 0), 0) / allCases.length)
        : 0;
    
    // Get top issues with counts
    const topIssues = Object.entries(cats)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3);
    
    // Get pending cases for actions
    const pendingCases = allCases
        .filter(c => (c.status || '').toLowerCase() === 'new')
        .sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
    const oldestPending = pendingCases[0];
    const oldestAge = oldestPending ? daysAgo(oldestPending.created_at) : 0;

    // Build Today's Briefing items - Active insights, not passive metrics
    const briefingItems = [];

    // Critical: Cases needing attention
    if (newCount > 5) {
        briefingItems.push({
            headline: `${newCount} unattended grievances in your inbox`,
            subtext: oldestAge > 7 
                ? `The oldest has been waiting ${oldestAge} days. Your response rate is slipping.` 
                : 'Several constituents are waiting for your response.',
            priority: 'critical',
            onClick: () => router.push('/dashboard/sansadx?status=new'),
        });
    } else if (newCount > 0) {
        briefingItems.push({
            headline: `${newCount} new case${newCount !== 1 ? 's' : ''} awaiting review`,
            subtext: 'Quick triage recommended before end of day.',
            priority: newCount >= 3 ? 'attention' : null,
            onClick: () => router.push('/dashboard/sansadx?status=new'),
        });
    }

    // Red zones / hot spots
    if (redZones.length > 0) {
        briefingItems.push({
            headline: `${redZones[0]} has rising complaints`,
            subtext: `This area is generating more cases than average. Consider a field visit.`,
            priority: 'attention',
            trend: 30,
            onClick: () => router.push(`/dashboard/sansadx?zone=${encodeURIComponent(redZones[0])}`),
        });
    }

    // Top category insight
    if (topIssues.length > 0) {
        const [topCat, topCount] = topIssues[0];
        const catPct = totalCases > 0 ? Math.round((topCount / totalCases) * 100) : 0;
        briefingItems.push({
            headline: `"${topCat}" is your #1 issue (${catPct}% of cases)`,
            subtext: topIssues.length > 1 
                ? `Followed by "${topIssues[1][0]}" and "${topIssues[2]?.[0] || 'others'}"` 
                : 'Consider addressing this category in your next public communication.',
            onClick: () => router.push(`/dashboard/sansadx?category=${encodeURIComponent(topCat)}`),
        });
    }

    // Parliament session context
    if (parliament?.in_session) {
        briefingItems.push({
            headline: `House is in session: ${parliament.session_name}`,
            subtext: parliament.business_items?.length > 0 
                ? `Today: ${parliament.business_items.slice(0, 2).join(', ')}` 
                : 'Track proceedings and prepare for questions.',
            onClick: () => router.push('/dashboard/drafter?mode=question'),
        });
    }

    // Media mentions
    const relevantNews = [...(news.national || []), ...(news.local || [])].slice(0, 1);
    if (relevantNews.length > 0) {
        briefingItems.push({
            headline: 'You are in the news today',
            subtext: relevantNews[0]?.title?.slice(0, 80) + '...',
            onClick: () => window.open(relevantNews[0]?.link, '_blank'),
        });
    }

    // Fallback: If no briefing items, show a positive message
    if (briefingItems.length === 0) {
        briefingItems.push({
            headline: 'All caught up for today',
            subtext: 'No urgent matters require your attention. Great work staying on top of things!',
        });
    }

    // Build action items - "What You Should Do Today"
    const actions = [];
    
    if (newCount > 0) {
        actions.push({
            icon: MessageSquare,
            title: `Respond to ${newCount} pending case${newCount !== 1 ? 's' : ''}`,
            description: oldestAge > 3 ? `Oldest waiting ${oldestAge} days` : 'Keep response time low',
            href: '/dashboard/sansadx?status=new',
            urgent: oldestAge > 7,
        });
    }

    if (redZones.length > 0) {
        actions.push({
            icon: MapPin,
            title: `Visit ${redZones[0]}`,
            description: 'High complaint density — constituents need to see you',
            href: `/dashboard/sansadx?zone=${encodeURIComponent(redZones[0])}`,
            urgent: false,
        });
    }

    if (pqCalendar?.window_state === 'open' && pqCalendar.days_remaining <= 5) {
        actions.push({
            icon: PenTool,
            title: 'Draft a Parliamentary Question',
            description: `${pqCalendar.days_remaining} days left before deadline`,
            href: '/dashboard/drafter?mode=question',
            urgent: pqCalendar.days_remaining <= 2,
        });
    }

    // Default actions if none derived
    if (actions.length === 0) {
        actions.push(
            {
                icon: Mail,
                title: 'Upload a letter',
                description: 'Scan or upload constituent correspondence',
                href: '/dashboard/letterbox',
                urgent: false,
            },
            {
                icon: Gift,
                title: 'Find a scheme',
                description: 'Match constituents to government benefits',
                href: '/dashboard/schemes',
                urgent: false,
            }
        );
    }

    // Ensure we always have 3 actions
    const defaultActions = [
        { icon: Mail, title: 'Upload a letter', description: 'Scan or upload correspondence', href: '/dashboard/letterbox', urgent: false },
        { icon: PenTool, title: 'Draft a response', description: 'AI-assisted writing', href: '/dashboard/drafter', urgent: false },
        { icon: Gift, title: 'Find a scheme', description: 'Match to benefits', href: '/dashboard/schemes', urgent: false },
    ];
    while (actions.length < 3) {
        const next = defaultActions.find(d => !actions.some(a => a.href === d.href));
        if (next) actions.push(next);
        else break;
    }

    return (
        <div className="space-y-8 max-w-5xl mx-auto">
            {/* HERO: Today's Briefing */}
            <section className="space-y-4">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="headline-hero">
                            Good {new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 17 ? 'afternoon' : 'evening'}, {user?.display_name?.split(' ')[0]}
                        </h1>
                        <p className="text-muted-foreground mt-1">
                            {new Date().toLocaleDateString('en-IN', { 
                                weekday: 'long', 
                                day: 'numeric', 
                                month: 'long' 
                            })} — Here&apos;s what matters today
                        </p>
                    </div>
                </div>

                {/* Today's Briefing Card - Full width hero */}
                <Card className="border-2 border-primary/10">
                    <CardHeader className="pb-2">
                        <CardTitle className="flex items-center gap-2 headline-section">
                            <Eye className="h-6 w-6 text-primary" />
                            Today&apos;s Briefing
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="pt-2">
                        <div className="divide-y divide-border">
                            {briefingItems.slice(0, 5).map((item, i) => (
                                <BriefingItem key={i} {...item} />
                            ))}
                        </div>
                    </CardContent>
                </Card>
            </section>

            {/* Empty State */}
            {isEmpty ? (
                <Card className="text-center py-12">
                    <CardContent className="space-y-4">
                        <div className="h-20 w-20 mx-auto rounded-full bg-primary/10 flex items-center justify-center">
                            <Building2 className="h-10 w-10 text-primary" />
                        </div>
                        <div>
                            <h2 className="headline-card">Welcome to your Command Center</h2>
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
                    {/* ACTION STRIP: What You Should Do Today */}
                    <section className="space-y-4">
                        <div className="flex items-center gap-2">
                            <Zap className="h-5 w-5 text-primary" />
                            <h2 className="headline-section">What You Should Do Today</h2>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            {actions.slice(0, 3).map((action, i) => (
                                <ActionCard key={i} {...action} />
                            ))}
                        </div>
                    </section>

                    {/* PQ Calendar - contextual */}
                    {pqCalendar && pqCalendar.window_state !== 'unknown' && (
                        <PQCalendarCard pq={pqCalendar} />
                    )}

                    {/* INSIGHTS GRID: Active metrics */}
                    <section className="space-y-4">
                        <div className="flex items-center gap-2">
                            <Target className="h-5 w-5 text-primary" />
                            <h2 className="headline-section">Your Pulse</h2>
                        </div>
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                            <InsightCard
                                label="Pending Response"
                                value={newCount}
                                icon={Clock}
                                highlight={newCount > 10 ? 'critical' : newCount > 5 ? 'warning' : newCount > 0 ? null : 'success'}
                            />
                            <InsightCard
                                label="In Progress"
                                value={inProgressCount}
                                icon={TrendingUp}
                            />
                            <InsightCard
                                label="Resolution Rate"
                                value={`${resolutionRate}%`}
                                icon={CheckCircle2}
                                highlight={resolutionRate >= 60 ? 'success' : resolutionRate >= 30 ? 'warning' : 'critical'}
                            />
                            <InsightCard
                                label="Avg Response Time"
                                value={`${avgAge}d`}
                                icon={Users}
                                highlight={avgAge <= 5 ? 'success' : avgAge <= 14 ? 'warning' : 'critical'}
                            />
                        </div>
                    </section>

                    {/* Top Issues - Condensed */}
                    {topIssues.length > 0 && (
                        <section className="space-y-4">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <FileText className="h-5 w-5 text-primary" />
                                    <h2 className="headline-section">Top Issues</h2>
                                </div>
                                <Button variant="ghost" size="sm" asChild>
                                    <Link href="/dashboard/sansadx">
                                        View all cases
                                        <ArrowRight className="h-4 w-4 ml-1" />
                                    </Link>
                                </Button>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                {topIssues.map(([cat, count], i) => {
                                    const pct = totalCases > 0 ? Math.round((count / totalCases) * 100) : 0;
                                    return (
                                        <button
                                            key={cat}
                                            onClick={() => router.push(`/dashboard/sansadx?category=${encodeURIComponent(cat)}`)}
                                            className="text-left p-4 rounded-xl bg-card border border-border hover:border-primary/30 hover:bg-accent/50 transition-all group"
                                        >
                                            <div className="flex items-center justify-between mb-2">
                                                <span className="text-xs font-bold text-muted-foreground">
                                                    #{i + 1}
                                                </span>
                                                <span className="text-xs font-semibold text-primary">
                                                    {pct}%
                                                </span>
                                            </div>
                                            <h3 className="font-semibold text-foreground group-hover:text-primary transition-colors truncate">
                                                {cat}
                                            </h3>
                                            <p className="text-sm text-muted-foreground mt-1">
                                                {count} case{count !== 1 ? 's' : ''}
                                            </p>
                                            <div className="mt-3 w-full h-1.5 bg-secondary rounded-full overflow-hidden">
                                                <div
                                                    className="h-full rounded-full bg-primary transition-all"
                                                    style={{ width: `${pct}%` }}
                                                />
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        </section>
                    )}
                </>
            )}
        </div>
    );
}
