'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { apiGet } from '@/lib/api';
import { cn } from '@/lib/utils';
import DashboardControlBar from '@/components/DashboardControlBar';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
    AlertTriangle,
    ArrowRight,
    ArrowUpRight,
    BookOpen,
    Briefcase,
    Building2,
    CheckCircle2,
    ChevronDown,
    ChevronUp,
    Clock,
    ExternalLink,
    FileText,
    Gift,
    Mail,
    MapPinned,
    PenTool,
    Sparkles,
    TrendingUp,
    Users,
} from 'lucide-react';

const QUICK_ACTIONS = [
    { label: 'Upload Letter', href: '/dashboard/letterbox', desc: 'Scan or upload', icon: Mail },
    { label: 'Draft Response', href: '/dashboard/drafter', desc: 'AI-assisted writing', icon: PenTool },
    { label: 'Find a Scheme', href: '/dashboard/sansadai?tab=schemes', desc: 'Match constituents', icon: Gift },
];

function daysAgo(dateStr) {
    if (!dateStr) return null;
    const diff = Date.now() - new Date(dateStr).getTime();
    return Math.floor(diff / (1000 * 60 * 60 * 24));
}

function formatNewsDate(value) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
    });
}

function AgeBadge({ days }) {
    if (days === null) return null;
    return (
        <span
            className={cn(
                'font-mono-ui inline-flex min-w-[3rem] justify-center border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em]',
                days >= 14 && 'border-[#8b2e1f]/20 bg-[#f2dad3] text-[#8b2e1f]',
                days >= 7 && days < 14 && 'border-[#c76a1a]/20 bg-[#f4e3ce] text-[#9a4e14]',
                days < 7 && 'border-[#0d6a4d]/20 bg-[#dfe9e2] text-[#0d6a4d]'
            )}
        >
            {days}d
        </span>
    );
}

function MiniBar({ value, max, tone = 'green' }) {
    const width = `${Math.max(12, Math.round((value / (max || 1)) * 100))}%`;
    return (
        <div className="h-2 w-full overflow-hidden bg-[#e7deca]">
            <div
                className={cn(
                    'h-full',
                    tone === 'green' && 'bg-[#0d6a4d]',
                    tone === 'saffron' && 'bg-[#c76a1a]',
                    tone === 'ink' && 'bg-[#4a453a]'
                )}
                style={{ width }}
            />
        </div>
    );
}

function KpiCard({ label, value, note, accent = 'green', href, icon: Icon }) {
    const content = (
        <Card className="dashboard-kpi rounded-none border-0">
            <CardContent className="p-5">
                <div className="flex items-start justify-between gap-3">
                    <div>
                        <p className="font-mono-ui text-[10px] uppercase tracking-[0.18em] text-[#7a7263]">
                            {label}
                        </p>
                        <p className="font-editorial mt-3 text-4xl font-semibold tracking-[-0.03em] text-[#1a1812]">
                            {value}
                        </p>
                    </div>
                    <div
                        className={cn(
                            'flex h-10 w-10 items-center justify-center rounded-none border',
                            accent === 'green' && 'border-[#0d6a4d]/15 bg-[#dfe9e2] text-[#0d6a4d]',
                            accent === 'saffron' && 'border-[#c76a1a]/15 bg-[#f4e3ce] text-[#9a4e14]',
                            accent === 'ink' && 'border-[#4a453a]/10 bg-[#efe6d2] text-[#4a453a]',
                            accent === 'red' && 'border-[#8b2e1f]/15 bg-[#f2dad3] text-[#8b2e1f]'
                        )}
                    >
                        <Icon className="h-4 w-4" />
                    </div>
                </div>
                <div className="mt-5 flex items-center justify-between gap-3 border-t border-[var(--hairline)] pt-3">
                    <p className="text-sm text-[#4a453a]">{note}</p>
                    {href && <ArrowUpRight className="h-4 w-4 text-[#7a7263]" />}
                </div>
            </CardContent>
        </Card>
    );

    if (!href) return content;
    return <Link href={href}>{content}</Link>;
}

function SectionFrame({ eyebrow, title, description, action, children, className = '' }) {
    return (
        <section className={cn('dashboard-panel rounded-none p-5 md:p-6', className)}>
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--hairline)] pb-4">
                <div>
                    {eyebrow && (
                        <p className="font-mono-ui text-[10px] uppercase tracking-[0.2em] text-[#7a7263]">
                            {eyebrow}
                        </p>
                    )}
                    <h2 className="font-editorial mt-2 text-[1.8rem] font-semibold tracking-[-0.025em] text-[#1a1812]">
                        {title}
                    </h2>
                    {description && (
                        <p className="mt-2 max-w-2xl text-sm leading-6 text-[#4a453a]">
                            {description}
                        </p>
                    )}
                </div>
                {action}
            </div>
            <div className="pt-5">{children}</div>
        </section>
    );
}

export default function DashboardPage() {
    const { user } = useAuth();
    const router = useRouter();
    const canUseSansadAI = user?.role === 'mp' || user?.role === 'admin';

    const [summary, setSummary] = useState(null);
    const [reportCard, setReportCard] = useState(null);
    const [news, setNews] = useState({ national: [], local: [] });
    const [newsTab, setNewsTab] = useState('national');
    const [showNews, setShowNews] = useState(true);
    const [mediaSearch, setMediaSearch] = useState('');
    const [mediaSource, setMediaSource] = useState('');
    const [staleCases, setStaleCases] = useState([]);
    const [allCases, setAllCases] = useState([]);

    useEffect(() => {
        let cancelled = false;
        const safeSet = (fn) => {
            if (!cancelled) fn();
        };

        (async () => {
            const sum = await apiGet('/api/dashboard/summary').catch(() => ({
                category_breakdown: {},
                status_breakdown: {},
                red_zones: [],
                critical_count: 0,
            }));
            safeSet(() => setSummary(sum));
        })();

        (async () => {
            const cases = await apiGet('/api/cases?page=1&limit=50').catch(() => ({ cases: [] }));
            const fetchedCases = cases.cases || cases.items || [];
            const pending = fetchedCases
                .filter(c => (c.status || '').toLowerCase() === 'new')
                .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
                .slice(0, 6);
            safeSet(() => {
                setAllCases(fetchedCases);
                setStaleCases(pending);
            });
        })();

        const secondaryTimer = setTimeout(() => {
            (async () => {
                const rc = await apiGet('/api/activity/report-card').catch(() => null);
                safeSet(() => setReportCard(rc));
            })();

            (async () => {
                const [nat, loc] = await Promise.all([
                    apiGet('/api/news?news_type=national').catch(() => ({ articles: [] })),
                    apiGet('/api/news?news_type=local').catch(() => ({ articles: [] })),
                ]);
                safeSet(() => setNews({ national: nat.articles || [], local: loc.articles || [] }));
            })();
        }, 900);

        return () => {
            cancelled = true;
            clearTimeout(secondaryTimer);
        };
    }, []);

    const activeNews = news[newsTab] || [];
    const mediaSources = [...new Set(activeNews.map(a => a.source).filter(Boolean))].sort();
    const filteredNews = activeNews.filter(article => {
        const q = mediaSearch.trim().toLowerCase();
        const matchesSearch = !q || [article.title, article.source].some(v => (v || '').toLowerCase().includes(q));
        const matchesSource = !mediaSource || article.source === mediaSource;
        return matchesSearch && matchesSource;
    });

    const refreshNews = async () => {
        const [nat, loc] = await Promise.all([
            apiGet('/api/news?news_type=national').catch(() => ({ articles: [] })),
            apiGet('/api/news?news_type=local').catch(() => ({ articles: [] })),
        ]);
        setNews({ national: nat.articles || [], local: loc.articles || [] });
    };

    const cats = summary?.category_breakdown || {};
    const statuses = summary?.status_breakdown || {};
    const totalCases = Object.values(statuses).reduce((a, b) => a + b, 0);
    const maxCat = Math.max(...Object.values(cats), 1);
    const newCount = statuses.new || 0;
    const redCount = summary?.red_zones?.length || 0;
    const hasUrgent = newCount > 0 || redCount > 0;
    const isEmpty = totalCases === 0;

    const resolvedCount = statuses.resolved || 0;
    const resolutionRate = totalCases > 0 ? Math.round((resolvedCount / totalCases) * 100) : 0;
    const avgAge = allCases.length > 0
        ? Math.round(allCases.reduce((sum, c) => sum + (daysAgo(c.created_at) || 0), 0) / allCases.length)
        : 0;
    const oneWeekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
    const newThisWeek = allCases.filter(c =>
        (c.status || '').toLowerCase() === 'new' && new Date(c.created_at).getTime() > oneWeekAgo
    ).length;
    const topIssue = Object.entries(cats).sort((a, b) => b[1] - a[1])[0]?.[0] || '—';

    const quickActions = canUseSansadAI
        ? [...QUICK_ACTIONS, { label: 'Research Desk', href: '/dashboard/sansadai?tab=research', desc: 'Analyse docs', icon: BookOpen }]
        : QUICK_ACTIONS;

    const throughput = [
        { label: 'Letters drafted', value: reportCard?.letters_drafted ?? '—' },
        { label: 'Questions drafted', value: reportCard?.questions_drafted ?? '—' },
        { label: 'Documents analysed', value: reportCard?.docs_analysed ?? '—' },
        { label: 'Cases reviewed', value: reportCard?.cases_reviewed ?? '—' },
    ];

    return (
        <div className="space-y-6 md:space-y-8">
            <section className="dashboard-panel rounded-none overflow-hidden">
                <div className="flex h-1">
                    <div className="flex-1 bg-[#c76a1a]" />
                    <div className="flex-1 bg-[#f2ebd9]" />
                    <div className="flex-1 bg-[#0d6a4d]" />
                </div>
                <div className="grid gap-6 p-5 md:grid-cols-[1.35fr_0.95fr] md:p-7">
                    <div>
                        <p className="font-mono-ui text-[10px] uppercase tracking-[0.22em] text-[#7a7263]">
                            Constituency bulletin
                        </p>
                        <h1 className="font-editorial mt-3 max-w-3xl text-[2.25rem] font-semibold leading-tight tracking-[-0.03em] text-[#1a1812] md:text-[3rem]">
                            A calmer, sharper control room for constituency work.
                        </h1>
                        <p className="mt-4 max-w-2xl text-sm leading-7 text-[#4a453a] md:text-[15px]">
                            Monitor live grievance pressure, move quickly on letters and fieldwork, and keep your office aligned around the work that needs attention now.
                        </p>

                        <div className="mt-6 flex flex-wrap gap-3">
                            <span className="dashboard-pill font-mono-ui px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.18em]">
                                {user?.constituency || 'Constituency office'}
                            </span>
                            <span className="border border-[var(--hairline)] bg-[#efe6d2] px-3 py-2 text-sm text-[#4a453a]">
                                {newCount} new case{newCount !== 1 ? 's' : ''} awaiting action
                            </span>
                            <span className="border border-[var(--hairline)] bg-[#efe6d2] px-3 py-2 text-sm text-[#4a453a]">
                                {redCount} pressure zone{redCount !== 1 ? 's' : ''}
                            </span>
                        </div>
                    </div>

                    <div className="grid gap-3 md:grid-cols-2">
                        <Card className="dashboard-panel rounded-none border-0 bg-[#0d6a4d] text-[#f5eedf]">
                            <CardContent className="p-5">
                                <p className="font-mono-ui text-[10px] uppercase tracking-[0.2em] text-[#d7c9aa]">
                                    Resolution rate
                                </p>
                                <p className="font-editorial mt-3 text-4xl font-semibold tracking-[-0.03em]">
                                    {totalCases > 0 ? `${resolutionRate}%` : '—'}
                                </p>
                                <p className="mt-4 text-sm text-[#ecdfc5]/80">
                                    Of all cases currently represented in the live dashboard summary.
                                </p>
                            </CardContent>
                        </Card>

                        <Card className="dashboard-panel rounded-none border-0">
                            <CardContent className="p-5">
                                <p className="font-mono-ui text-[10px] uppercase tracking-[0.2em] text-[#7a7263]">
                                    This week
                                </p>
                                <p className="font-editorial mt-3 text-4xl font-semibold tracking-[-0.03em] text-[#1a1812]">
                                    {newThisWeek}
                                </p>
                                <p className="mt-4 text-sm text-[#4a453a]">
                                    Fresh grievances entered the queue in the last 7 days.
                                </p>
                            </CardContent>
                        </Card>

                        <Card className="dashboard-panel rounded-none border-0">
                            <CardContent className="p-5">
                                <p className="font-mono-ui text-[10px] uppercase tracking-[0.2em] text-[#7a7263]">
                                    Average case age
                                </p>
                                <p className="font-editorial mt-3 text-4xl font-semibold tracking-[-0.03em] text-[#1a1812]">
                                    {allCases.length > 0 ? `${avgAge}d` : '—'}
                                </p>
                                <p className="mt-4 text-sm text-[#4a453a]">
                                    Older queues are the fastest signal that follow-up bandwidth is slipping.
                                </p>
                            </CardContent>
                        </Card>

                        <Card className="dashboard-panel rounded-none border-0 bg-[#f4e3ce]">
                            <CardContent className="p-5">
                                <p className="font-mono-ui text-[10px] uppercase tracking-[0.2em] text-[#9a4e14]">
                                    Top issue
                                </p>
                                <p className="font-editorial mt-3 text-2xl font-semibold tracking-[-0.03em] text-[#1a1812]">
                                    {topIssue}
                                </p>
                                <p className="mt-4 text-sm text-[#6d4e33]">
                                    Highest current category concentration across the live dashboard summary.
                                </p>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </section>

            {hasUrgent && (
                <section className="dashboard-panel rounded-none border-l-4 border-l-[#8b2e1f] bg-[#fff7f3] px-5 py-4 md:px-6">
                    <div className="flex flex-wrap items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                            <div className="flex h-11 w-11 items-center justify-center rounded-none bg-[#f2dad3] text-[#8b2e1f]">
                                <AlertTriangle className="h-5 w-5" />
                            </div>
                            <div>
                                <p className="font-semibold text-[#8b2e1f]">
                                    {newCount > 0 && `${newCount} new grievance${newCount !== 1 ? 's' : ''} need${newCount === 1 ? 's' : ''} attention`}
                                    {newCount > 0 && redCount > 0 && ' · '}
                                    {redCount > 0 && `${redCount} zone${redCount !== 1 ? 's' : ''} flagged`}
                                </p>
                                <p className="mt-1 text-sm text-[#6f3f37]">
                                    Review these items quickly to keep constituency response time tight.
                                </p>
                            </div>
                        </div>
                        <Button asChild className="rounded-none bg-[#8b2e1f] text-white hover:bg-[#6f2417]">
                            <Link href="/dashboard/sansadx?status=new">
                                Review now
                                <ArrowRight className="ml-2 h-4 w-4" />
                            </Link>
                        </Button>
                    </div>
                </section>
            )}

            {isEmpty ? (
                <SectionFrame
                    eyebrow="First steps"
                    title="The constituency office is ready."
                    description="Start by bringing live work into the system: upload a letter, log a case, or open the AI desk for drafting and research."
                >
                    <div className="flex flex-col items-center gap-5 py-6 text-center">
                        <div className="flex h-20 w-20 items-center justify-center rounded-none border border-[var(--hairline)] bg-[#efe6d2] text-[#0d6a4d]">
                            <Building2 className="h-10 w-10" />
                        </div>
                        <div className="flex flex-wrap justify-center gap-3">
                            <Button asChild className="rounded-none bg-[#0d6a4d] text-white hover:bg-[#094f39]">
                                <Link href="/dashboard/letterbox">Upload a Letter</Link>
                            </Button>
                            <Button variant="outline" asChild className="rounded-none border-[var(--hairline-strong)] bg-transparent hover:bg-[#efe6d2]">
                                <Link href="/dashboard/sansadx">Log a Case</Link>
                            </Button>
                            {canUseSansadAI && (
                                <Button variant="outline" asChild className="rounded-none border-[var(--hairline-strong)] bg-transparent hover:bg-[#efe6d2]">
                                    <Link href="/dashboard/sansadai">Open SansadAI</Link>
                                </Button>
                            )}
                        </div>
                    </div>
                </SectionFrame>
            ) : (
                <>
                    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                        <KpiCard
                            label="Total cases"
                            value={totalCases}
                            note="View all live grievances in Briefcase"
                            accent="ink"
                            href="/dashboard/sansadx"
                            icon={Briefcase}
                        />
                        <KpiCard
                            label="New / open"
                            value={newCount}
                            note="Queue requiring first-touch handling"
                            accent="saffron"
                            href="/dashboard/sansadx?status=new"
                            icon={AlertTriangle}
                        />
                        <KpiCard
                            label="In progress"
                            value={statuses.in_progress || 0}
                            note="Cases already under active follow-up"
                            accent="green"
                            href="/dashboard/sansadx?status=in_progress"
                            icon={Clock}
                        />
                        <KpiCard
                            label="Resolved"
                            value={resolvedCount}
                            note="Completed closures represented in summary"
                            accent="green"
                            href="/dashboard/sansadx?status=resolved"
                            icon={CheckCircle2}
                        />
                    </div>

                    <SectionFrame
                        eyebrow="Action deck"
                        title="Move from signal to action."
                        description="The fastest-used tools stay in front so the office can draft, classify, research, and respond without changing mental context."
                    >
                        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                            {quickActions.map(({ label, href, desc, icon: Icon }) => (
                                <Link
                                    key={href}
                                    href={href}
                                    className="group border border-[var(--hairline)] bg-[rgba(251,246,231,0.82)] p-4 transition-all duration-200 hover:-translate-y-0.5 hover:border-[var(--hairline-strong)]"
                                >
                                    <div className="flex items-center justify-between">
                                        <div className="flex h-10 w-10 items-center justify-center rounded-none bg-[#efe6d2] text-[#0d6a4d]">
                                            <Icon className="h-4 w-4" />
                                        </div>
                                        <ArrowUpRight className="h-4 w-4 text-[#7a7263] transition-colors group-hover:text-[#0d6a4d]" />
                                    </div>
                                    <p className="font-editorial mt-4 text-xl font-semibold tracking-[-0.02em] text-[#1a1812]">
                                        {label}
                                    </p>
                                    <p className="mt-1 text-sm text-[#4a453a]">{desc}</p>
                                </Link>
                            ))}
                        </div>
                    </SectionFrame>

                    <div className="grid gap-6 xl:grid-cols-[1.45fr_0.95fr]">
                        <SectionFrame
                            eyebrow="Distribution"
                            title="Issue mix across the live queue."
                            description="Click any issue line to jump straight into the filtered Briefcase view."
                        >
                            {Object.keys(cats).length > 0 ? (
                                <div className="space-y-4">
                                    {Object.entries(cats)
                                        .sort((a, b) => b[1] - a[1])
                                        .slice(0, 8)
                                        .map(([cat, count], index) => (
                                            <button
                                                key={cat}
                                                className="w-full border-b border-[var(--hairline)] pb-4 text-left last:border-b-0 last:pb-0"
                                                onClick={() => router.push(`/dashboard/sansadx?category=${encodeURIComponent(cat)}`)}
                                            >
                                                <div className="mb-2 flex items-center justify-between gap-3">
                                                    <div className="flex items-center gap-3">
                                                        <span className="font-mono-ui text-[10px] uppercase tracking-[0.18em] text-[#7a7263]">
                                                            {String(index + 1).padStart(2, '0')}
                                                        </span>
                                                        <span className="font-medium text-[#1a1812]">{cat}</span>
                                                    </div>
                                                    <span className="font-editorial text-2xl font-semibold text-[#1a1812]">
                                                        {count}
                                                    </span>
                                                </div>
                                                <MiniBar value={count} max={maxCat} tone={index < 2 ? 'green' : index < 5 ? 'saffron' : 'ink'} />
                                            </button>
                                        ))}
                                </div>
                            ) : (
                                <p className="text-sm text-[#4a453a]">No category data available yet.</p>
                            )}
                        </SectionFrame>

                        <div className="space-y-6">
                            <SectionFrame
                                eyebrow="Pressure points"
                                title="Constituency health"
                                description="A quick office-level read on closure efficiency and queue pressure."
                            >
                                <div className="grid gap-3 sm:grid-cols-2">
                                    <MetricTile label="Resolution rate" value={totalCases > 0 ? `${resolutionRate}%` : '—'} icon={CheckCircle2} accent="green" />
                                    <MetricTile label="Average age" value={allCases.length > 0 ? `${avgAge}d` : '—'} icon={Clock} accent={avgAge > 14 ? 'red' : avgAge > 7 ? 'saffron' : 'green'} />
                                    <MetricTile label="New this week" value={newThisWeek} icon={TrendingUp} accent={newThisWeek > 5 ? 'saffron' : 'green'} />
                                    <MetricTile label="Flagged zones" value={redCount} icon={MapPinned} accent={redCount > 0 ? 'red' : 'ink'} />
                                </div>

                                {summary?.red_zones?.length > 0 && (
                                    <div className="mt-5 border-t border-[var(--hairline)] pt-4">
                                        <p className="font-mono-ui text-[10px] uppercase tracking-[0.18em] text-[#7a7263]">
                                            Active red zones
                                        </p>
                                        <div className="mt-3 space-y-2">
                                            {summary.red_zones.slice(0, 4).map((zone, idx) => (
                                                <div key={`${zone.area || zone.location || 'zone'}-${idx}`} className="flex items-center justify-between gap-3 border border-[var(--hairline)] bg-[#f7f0dc] px-3 py-2">
                                                    <span className="text-sm font-medium text-[#1a1812]">
                                                        {zone.area || zone.location || 'Flagged cluster'}
                                                    </span>
                                                    <span className="font-mono-ui text-[10px] uppercase tracking-[0.16em] text-[#8b2e1f]">
                                                        {zone.cnt || zone.count || 0} cases
                                                    </span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </SectionFrame>

                            <SectionFrame
                                eyebrow="First-touch queue"
                                title="Pending triage"
                                description="New cases that still need first review from the office."
                                action={(
                                    <Button variant="ghost" asChild className="rounded-none px-0 text-[#0d6a4d] hover:bg-transparent hover:text-[#083728]">
                                        <Link href="/dashboard/sansadx?status=new">
                                            View all
                                            <ArrowRight className="ml-2 h-4 w-4" />
                                        </Link>
                                    </Button>
                                )}
                            >
                                {staleCases.length > 0 ? (
                                    <div className="space-y-3">
                                        {staleCases.map(c => {
                                            const age = daysAgo(c.created_at);
                                            const summaryText = c.raw_message
                                                ? c.raw_message.slice(0, 95) + (c.raw_message.length > 95 ? '…' : '')
                                                : c.category || '—';
                                            const sub = [c.category, c.user_phone].filter(Boolean).join(' · ');
                                            return (
                                                <button
                                                    key={c.id}
                                                    className="flex w-full items-start justify-between gap-3 border border-[var(--hairline)] bg-[rgba(251,246,231,0.78)] px-4 py-4 text-left transition-all hover:-translate-y-0.5 hover:border-[var(--hairline-strong)]"
                                                    onClick={() => router.push(`/dashboard/sansadx?status=new&case_id=${c.id}`)}
                                                >
                                                    <div className="min-w-0">
                                                        <p className="font-mono-ui text-[10px] uppercase tracking-[0.16em] text-[#7a7263]">
                                                            Case #{c.id}
                                                        </p>
                                                        <p className="mt-2 text-sm font-medium leading-6 text-[#1a1812]">
                                                            {summaryText}
                                                        </p>
                                                        {sub && (
                                                            <p className="mt-1 text-xs text-[#7a7263]">{sub}</p>
                                                        )}
                                                    </div>
                                                    <AgeBadge days={age} />
                                                </button>
                                            );
                                        })}
                                    </div>
                                ) : (
                                    <div className="flex items-center gap-3 border border-[var(--hairline)] bg-[#dfe9e2] px-4 py-4 text-[#0d6a4d]">
                                        <CheckCircle2 className="h-4 w-4" />
                                        <span className="text-sm font-medium">All new cases actioned. The queue is clear.</span>
                                    </div>
                                )}
                            </SectionFrame>
                        </div>
                    </div>

                    <div className="grid gap-6 xl:grid-cols-[1.1fr_1fr]">
                        <SectionFrame
                            eyebrow="Office throughput"
                            title={reportCard?.period_label || 'This month'}
                            description="A simple read on what the office has already produced through drafting, analysis, and case review work."
                        >
                            <div className="grid gap-3 sm:grid-cols-2">
                                {throughput.map((item, index) => (
                                    <div key={item.label} className={cn(
                                        'border px-4 py-4',
                                        index === 0 && 'border-[#0d6a4d]/16 bg-[#dfe9e2]',
                                        index === 1 && 'border-[#c76a1a]/16 bg-[#f4e3ce]',
                                        index === 2 && 'border-[var(--hairline)] bg-[#efe6d2]',
                                        index === 3 && 'border-[#0d6a4d]/16 bg-[#eaf1ec]'
                                    )}>
                                        <p className="font-mono-ui text-[10px] uppercase tracking-[0.18em] text-[#7a7263]">
                                            {item.label}
                                        </p>
                                        <p className="font-editorial mt-3 text-4xl font-semibold tracking-[-0.03em] text-[#1a1812]">
                                            {item.value}
                                        </p>
                                    </div>
                                ))}
                            </div>
                        </SectionFrame>

                        <SectionFrame
                            eyebrow="Media desk"
                            title="Coverage and response watch"
                            description="Track national and local media references relevant to the constituency and office."
                            action={(
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-9 w-9 rounded-none border border-[var(--hairline)] bg-transparent hover:bg-[#efe6d2]"
                                    onClick={() => setShowNews(v => !v)}
                                >
                                    {showNews ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                                </Button>
                            )}
                        >
                            {showNews && (
                                <Tabs value={newsTab} onValueChange={(value) => { setNewsTab(value); setMediaSource(''); }}>
                                    <TabsList className="mb-4 h-auto rounded-none border border-[var(--hairline)] bg-[#efe6d2] p-1">
                                        <TabsTrigger value="national" className="rounded-none data-[state=active]:bg-[#fbf6e7] data-[state=active]:text-[#1a1812]">
                                            National media
                                        </TabsTrigger>
                                        <TabsTrigger value="local" className="rounded-none data-[state=active]:bg-[#fbf6e7] data-[state=active]:text-[#1a1812]">
                                            Local and digital
                                        </TabsTrigger>
                                    </TabsList>

                                    <DashboardControlBar
                                        className="mb-4 rounded-none border-[var(--hairline)] bg-[#f7f0dc] p-3"
                                        search={mediaSearch}
                                        onSearchChange={setMediaSearch}
                                        searchPlaceholder="Search headline or source..."
                                        onRefresh={refreshNews}
                                    >
                                        <select
                                            className="h-9 rounded-none border border-[var(--hairline)] bg-[#fbf6e7] px-3 text-sm text-[#1a1812]"
                                            value={mediaSource}
                                            onChange={e => setMediaSource(e.target.value)}
                                        >
                                            <option value="">All sources</option>
                                            {mediaSources.map(source => (
                                                <option key={source} value={source}>{source}</option>
                                            ))}
                                        </select>
                                        {(mediaSearch || mediaSource) && (
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="rounded-none"
                                                onClick={() => {
                                                    setMediaSearch('');
                                                    setMediaSource('');
                                                }}
                                            >
                                                Clear
                                            </Button>
                                        )}
                                    </DashboardControlBar>

                                    <TabsContent value="national" className="mt-0">
                                        <NewsList articles={filteredNews} emptyText="No national media coverage found today." />
                                    </TabsContent>
                                    <TabsContent value="local" className="mt-0">
                                        <NewsList articles={filteredNews} emptyText="No local or digital media coverage found today." />
                                    </TabsContent>
                                </Tabs>
                            )}
                        </SectionFrame>
                    </div>
                </>
            )}
        </div>
    );
}

function MetricTile({ label, value, icon: Icon, accent = 'ink' }) {
    return (
        <div
            className={cn(
                'border px-4 py-4',
                accent === 'green' && 'border-[#0d6a4d]/16 bg-[#eaf1ec]',
                accent === 'saffron' && 'border-[#c76a1a]/16 bg-[#f4e3ce]',
                accent === 'red' && 'border-[#8b2e1f]/16 bg-[#f2dad3]',
                accent === 'ink' && 'border-[var(--hairline)] bg-[#efe6d2]'
            )}
        >
            <div className="flex items-center gap-2 text-[#4a453a]">
                <Icon className="h-4 w-4" />
                <span className="font-mono-ui text-[10px] uppercase tracking-[0.16em]">{label}</span>
            </div>
            <p className="font-editorial mt-3 text-3xl font-semibold tracking-[-0.03em] text-[#1a1812]">
                {value}
            </p>
        </div>
    );
}

function NewsList({ articles, emptyText }) {
    if (articles.length === 0) {
        return <p className="text-sm text-[#4a453a]">{emptyText}</p>;
    }

    return (
        <div className="space-y-3">
            {articles.slice(0, 5).map((article, index) => (
                <a
                    key={`${article.link || article.title}-${index}`}
                    href={article.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group block border border-[var(--hairline)] bg-[rgba(251,246,231,0.78)] px-4 py-4 transition-all hover:-translate-y-0.5 hover:border-[var(--hairline-strong)]"
                >
                    <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                            <p className="text-sm font-medium leading-6 text-[#1a1812] group-hover:text-[#0d6a4d]">
                                {article.title}
                            </p>
                            <p className="mt-2 text-xs text-[#7a7263]">
                                {[article.source, formatNewsDate(article.published)].filter(Boolean).join(' · ')}
                            </p>
                        </div>
                        <ExternalLink className="mt-0.5 h-4 w-4 shrink-0 text-[#7a7263] group-hover:text-[#0d6a4d]" />
                    </div>
                </a>
            ))}
        </div>
    );
}
