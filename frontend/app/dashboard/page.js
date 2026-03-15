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
    FileEdit,
    Search,
    MessageSquare,
    BarChart2,
} from 'lucide-react';

const TYPE_LABELS = {
    draft_letter: 'Letter',
    draft_question: 'PQ',
    analysis: 'Analysis',
    copilot_chat: 'Chat',
};

const TYPE_ICONS = {
    draft_letter: FileText,
    draft_question: FileEdit,
    analysis: Search,
    copilot_chat: MessageSquare,
};

const QUICK_ACTIONS = [
    { label: 'Upload Letter', href: '/dashboard/letterbox', desc: 'Scan or upload', icon: Mail },
    { label: 'Draft Response', href: '/dashboard/drafter', desc: 'AI-assisted writing', icon: PenTool },
    { label: 'Find a Scheme', href: '/dashboard/schemes', desc: 'Match constituents', icon: Gift },
];

function getGreeting() {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
}

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
    const [recentActivity, setRecent] = useState([]);
    const [staleCases, setStaleCases] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function load() {
            try {
                const [sum, rc, nat, loc, parl, hist, cases] = await Promise.all([
                    apiGet('/api/dashboard/summary').catch(() => ({
                        category_breakdown: {}, status_breakdown: {}, red_zones: [], critical_count: 0,
                    })),
                    apiGet('/api/activity/report-card').catch(() => null),
                    apiGet('/api/news?news_type=national').catch(() => ({ articles: [] })),
                    apiGet('/api/news?news_type=local').catch(() => ({ articles: [] })),
                    apiGet('/api/parliament/status').catch(() => null),
                    apiGet('/api/history?limit=5').catch(() => ({ items: [] })),
                    apiGet('/api/cases?page=1&limit=50').catch(() => ({ cases: [] })),
                ]);

                setSummary(sum);
                setReportCard(rc);
                setNews({ national: nat.articles || [], local: loc.articles || [] });
                setParliament(parl);
                setRecent(hist.items || []);

                const allCases = cases.cases || cases.items || [];
                const pending = allCases
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

    const REPORT_CARD_ITEMS = [
        { label: 'Letters Drafted', value: reportCard?.letters_drafted ?? '—', icon: FileText },
        { label: 'Questions Filed', value: reportCard?.questions_drafted ?? '—', icon: FileEdit },
        { label: 'Docs Analysed', value: reportCard?.docs_analysed ?? '—', icon: Search },
        { label: 'Cases Reviewed', value: reportCard?.cases_reviewed ?? '—', icon: CheckCircle2 },
    ];

    return (
        <div className="space-y-6">
            {/* Greeting */}
            <div>
                <h1 className="text-2xl font-bold text-foreground">
                    {getGreeting()}, {user?.display_name}
                </h1>
                <p className="text-sm text-muted-foreground mt-1">
                    {user?.constituency} · {user?.house}
                </p>
            </div>

            {/* Parliament Status */}
            {parliament && (
                <Card className={cn(
                    "border-l-4",
                    parliament.in_session ? "border-l-emerald-500 bg-emerald-50/50" : "border-l-muted"
                )}>
                    <CardContent className="py-4">
                        {parliament.in_session ? (
                            <div className="space-y-3">
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
                                    <span className="text-xs text-muted-foreground">
                                        {parliament.day}, {parliament.date}
                                    </span>
                                </div>
                                {parliament.business_items?.length > 0 && (
                                    <div className="flex items-center justify-between gap-3 flex-wrap">
                                        <div className="flex flex-wrap gap-1.5">
                                            {parliament.business_items.slice(0, 2).map((item, i) => (
                                                <Badge key={i} variant="secondary" className="bg-emerald-100 text-emerald-700 hover:bg-emerald-200">
                                                    {item}
                                                </Badge>
                                            ))}
                                        </div>
                                        <Button asChild size="sm">
                                            <Link href={`/dashboard/drafter?topic=${encodeURIComponent(parliament.business_items[0] || '')}`}>
                                                Draft a PQ
                                                <ArrowRight className="h-4 w-4 ml-1" />
                                            </Link>
                                        </Button>
                                    </div>
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

            {/* Attention Banner */}
            {hasUrgent ? (
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
            ) : (
                <Card className="border-emerald-200 bg-emerald-50/50">
                    <CardContent className="py-4 flex items-center gap-3">
                        <div className="h-10 w-10 rounded-full bg-emerald-100 flex items-center justify-center shrink-0">
                            <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                        </div>
                        <div>
                            <p className="font-semibold text-emerald-800">All clear — no new escalations today</p>
                            <p className="text-xs text-emerald-600/80 mt-0.5">Great job staying on top of things!</p>
                        </div>
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
                            {/* Report Card */}
                            <Card>
                                <CardHeader className="pb-3">
                                    <div className="flex items-center justify-between">
                                        <CardTitle className="flex items-center gap-2 text-base">
                                            <BarChart2 className="h-4 w-4 text-primary" />
                                            Report Card
                                        </CardTitle>
                                        <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
                                            {reportCard?.period_label || new Date().toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })}
                                        </span>
                                    </div>
                                    <CardDescription>Your activity this month</CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid grid-cols-2 gap-3">
                                        {REPORT_CARD_ITEMS.map(({ label, value, icon: Icon }) => (
                                            <div key={label} className="rounded-lg p-3 bg-primary/5">
                                                <div className="flex items-center gap-1.5 mb-1">
                                                    <Icon className="h-3.5 w-3.5 text-primary" />
                                                </div>
                                                <p className="text-2xl font-bold text-foreground">{value}</p>
                                                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mt-0.5 leading-tight">{label}</p>
                                            </div>
                                        ))}
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Awaiting Response */}
                            <Card>
                                <CardHeader className="pb-3">
                                    <CardTitle className="flex items-center gap-2 text-base">
                                        <Clock className="h-4 w-4 text-amber-500" />
                                        Awaiting Response
                                    </CardTitle>
                                    <CardDescription>
                                        New cases pending initiation
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-0">
                                    {staleCases.length > 0 ? (
                                        <div className="divide-y divide-border -mx-6">
                                            {staleCases.map(c => {
                                                const age = daysAgo(c.created_at);
                                                const contact = c.user_phone || c.contact_name || '—';
                                                const category = c.category || '—';
                                                return (
                                                    <button
                                                        key={c.id}
                                                        className="w-full px-6 py-3 flex items-start justify-between gap-2 hover:bg-accent/50 transition-colors text-left"
                                                        onClick={() => router.push('/dashboard/sansadx?status=new')}
                                                    >
                                                        <div className="min-w-0">
                                                            <p className="text-xs font-bold text-muted-foreground">#{c.id}</p>
                                                            <p className="text-sm font-medium text-foreground truncate">{contact}</p>
                                                            <p className="text-xs text-muted-foreground truncate">{category}</p>
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
                                            View all new cases →
                                        </Link>
                                    </Button>
                                </div>
                            </Card>
                        </div>
                    </div>

                    {/* Recent Activity */}
                    {recentActivity.length > 0 && (
                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between">
                                <CardTitle className="flex items-center gap-2">
                                    <Clock className="h-5 w-5 text-primary" />
                                    Recent Activity
                                </CardTitle>
                                <Button variant="link" className="p-0 h-auto" asChild>
                                    <Link href="/dashboard/archives">View all →</Link>
                                </Button>
                            </CardHeader>
                            <CardContent className="p-0">
                                <div className="divide-y divide-border">
                                    {recentActivity.map(item => {
                                        const Icon = TYPE_ICONS[item.activity_type] || FileText;
                                        return (
                                            <button
                                                key={item.id}
                                                className="w-full px-6 py-3 flex items-center gap-4 hover:bg-accent/50 transition-colors text-left"
                                                onClick={() => router.push('/dashboard/archives')}
                                            >
                                                <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                                                    <Icon className="h-4 w-4 text-primary" />
                                                </div>
                                                <div className="flex-1 min-w-0 flex items-center gap-2">
                                                    <Badge variant="secondary" className="text-[10px] shrink-0">
                                                        {TYPE_LABELS[item.activity_type] || item.activity_type}
                                                    </Badge>
                                                    <span className="text-sm text-foreground truncate">
                                                        {item.title}
                                                    </span>
                                                </div>
                                                <span className="text-xs text-muted-foreground shrink-0">
                                                    {item.created_at
                                                        ? new Date(item.created_at).toLocaleString('en-IN', {
                                                            day: '2-digit', month: 'short',
                                                            hour: '2-digit', minute: '2-digit',
                                                        })
                                                        : '—'}
                                                </span>
                                            </button>
                                        );
                                    })}
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {/* News Feed */}
                    <Card>
                        <CardHeader className="cursor-pointer" onClick={() => setShowNews(v => !v)}>
                            <div className="flex items-center justify-between">
                                <CardTitle className="flex items-center gap-2">
                                    <FileText className="h-5 w-5 text-primary" />
                                    News Feed
                                </CardTitle>
                                <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                                    {showNews ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                                </Button>
                            </div>
                        </CardHeader>
                        {showNews && (
                            <CardContent className="pt-0">
                                <Tabs value={newsTab} onValueChange={setNewsTab}>
                                    <TabsList className="mb-4">
                                        <TabsTrigger value="national">National</TabsTrigger>
                                        <TabsTrigger value="local">Local</TabsTrigger>
                                    </TabsList>
                                    <TabsContent value="national" className="mt-0">
                                        <NewsList articles={news.national} />
                                    </TabsContent>
                                    <TabsContent value="local" className="mt-0">
                                        <NewsList articles={news.local} />
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

function NewsList({ articles }) {
    if (articles.length === 0) {
        return (
            <p className="text-sm text-muted-foreground text-center py-4">
                No coverage found today
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
