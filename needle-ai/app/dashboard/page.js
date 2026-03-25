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
    Mail,
    ArrowRight,
    TrendingUp,
    TrendingDown,
    Clock,
    FileText,
    MapPin,
    MessageSquare,
    Users,
    Flame,
    Zap,
    Target,
    Eye,
    UserCheck,
    BarChart2,
} from 'lucide-react';

// ── Priority indicator ─────────────────────────────────────────────

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

// ── Today's Briefing item ──────────────────────────────────────────

function BriefingItem({ headline, subtext, priority, onClick, trend }) {
    return (
        <button
            onClick={onClick}
            className={cn(
                'w-full text-left p-4 rounded-lg transition-all duration-200 group',
                'hover:bg-accent/50',
                priority === 'critical' && 'bg-destructive/5 border-l-4 border-l-destructive',
                priority === 'attention' && 'bg-amber-50/50 border-l-4 border-l-amber-500',
                !priority && 'border-l-4 border-l-transparent hover:border-l-primary/30'
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
                {trend !== undefined && (
                    <div className={cn(
                        'flex items-center gap-1 text-xs font-bold shrink-0 px-2 py-1 rounded',
                        trend > 0 ? 'text-destructive bg-destructive/10' : 'text-emerald-600 bg-emerald-50'
                    )}>
                        {trend > 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                        {Math.abs(trend)}%
                    </div>
                )}
            </div>
        </button>
    );
}

// ── Action Card ────────────────────────────────────────────────────

function ActionCard({ icon: Icon, title, description, href, urgent }) {
    return (
        <Link href={href}>
            <Card className={cn(
                'h-full transition-all duration-200 hover:shadow-md hover:-translate-y-0.5 cursor-pointer group',
                urgent && 'ring-2 ring-destructive/20 bg-destructive/5'
            )}>
                <CardContent className="p-5">
                    <div className="flex items-start gap-4">
                        <div className={cn(
                            'h-12 w-12 rounded-xl flex items-center justify-center shrink-0',
                            urgent ? 'bg-destructive/10' : 'bg-primary/10'
                        )}>
                            <Icon className={cn('h-6 w-6', urgent ? 'text-destructive' : 'text-primary')} />
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

// ── Insight Card ───────────────────────────────────────────────────

function InsightCard({ label, value, icon: Icon, highlight }) {
    return (
        <div className={cn(
            'p-4 rounded-xl',
            highlight === 'critical' && 'bg-destructive/10',
            highlight === 'warning' && 'bg-amber-50',
            highlight === 'success' && 'bg-emerald-50',
            !highlight && 'bg-accent/50'
        )}>
            <div className="flex items-center gap-2 mb-2">
                <Icon className={cn(
                    'h-4 w-4',
                    highlight === 'critical' && 'text-destructive',
                    highlight === 'warning' && 'text-amber-600',
                    highlight === 'success' && 'text-emerald-600',
                    !highlight && 'text-primary'
                )} />
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {label}
                </span>
            </div>
            <p className={cn(
                'text-2xl font-bold',
                highlight === 'critical' && 'text-destructive',
                highlight === 'warning' && 'text-amber-700',
                highlight === 'success' && 'text-emerald-700',
                !highlight && 'text-foreground'
            )}>
                {value}
            </p>
        </div>
    );
}

// ── Helpers ────────────────────────────────────────────────────────

function daysAgo(dateStr) {
    if (!dateStr) return null;
    const diff = Date.now() - new Date(dateStr).getTime();
    return Math.floor(diff / (1000 * 60 * 60 * 24));
}

function getGreeting() {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
}

// ── Page ───────────────────────────────────────────────────────────

export default function HomePage() {
    const { user } = useAuth();
    const router = useRouter();

    const [summary, setSummary] = useState(null);
    const [escalations, setEscalations] = useState([]);
    const [cases, setCases] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        Promise.all([
            apiGet('/api/dashboard/summary').catch(() => null),
            apiGet('/api/escalations').catch(() => ({ escalations: [] })),
            apiGet('/api/cases?page=1&limit=50').catch(() => ({ cases: [] })),
        ]).then(([s, e, c]) => {
            setSummary(s);
            setEscalations(e?.escalations || []);
            setCases(c?.cases || c?.items || []);
        }).finally(() => setLoading(false));
    }, []);

    if (loading) return (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <span className="text-sm text-muted-foreground">Loading your command center...</span>
        </div>
    );

    // Derive data
    const sb = summary?.status_breakdown || {};
    const cb = summary?.category_breakdown || {};
    const redZones = summary?.red_zones || [];
    const totalCases = summary?.total_cases || Object.values(sb).reduce((a, b) => a + b, 0);
    const newCount = sb.new || 0;
    const inProgressCount = sb.in_progress || 0;
    const resolvedCount = sb.resolved || 0;
    const escalatedCount = sb.escalated || 0;
    const isEmpty = totalCases === 0;

    const resolutionRate = totalCases > 0 ? Math.round((resolvedCount / totalCases) * 100) : 0;

    const pendingCases = cases
        .filter(c => (c.status || '').toLowerCase() === 'new')
        .sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
    const oldestPending = pendingCases[0];
    const oldestAge = oldestPending ? daysAgo(oldestPending.created_at) : 0;

    const unsentEscalations = escalations.filter(e => !e.email_sent).length;

    const topIssues = Object.entries(cb)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3);

    // ── Today's Briefing ──────────────────────────────────────────

    const briefingItems = [];

    if (newCount > 5) {
        briefingItems.push({
            headline: `${newCount} unattended grievances in your inbox`,
            subtext: oldestAge > 7
                ? `The oldest has been waiting ${oldestAge} days. Your response rate is slipping.`
                : 'Several voters are waiting for your response.',
            priority: 'critical',
            onClick: () => router.push('/dashboard/messages'),
        });
    } else if (newCount > 0) {
        briefingItems.push({
            headline: `${newCount} new case${newCount !== 1 ? 's' : ''} awaiting review`,
            subtext: 'Quick triage recommended before end of day.',
            priority: newCount >= 3 ? 'attention' : null,
            onClick: () => router.push('/dashboard/messages'),
        });
    }

    if (unsentEscalations > 0) {
        briefingItems.push({
            headline: `${unsentEscalations} escalation letter${unsentEscalations !== 1 ? 's' : ''} drafted but not sent`,
            subtext: 'Officer emails are ready — dispatch them to keep cases moving.',
            priority: 'attention',
            onClick: () => router.push('/dashboard/messages'),
        });
    }

    if (escalatedCount > 0) {
        briefingItems.push({
            headline: `${escalatedCount} case${escalatedCount !== 1 ? 's' : ''} escalated to officers`,
            subtext: 'Follow up to ensure action has been taken.',
            onClick: () => router.push('/dashboard/messages'),
        });
    }

    if (redZones.length > 0) {
        briefingItems.push({
            headline: `${redZones[0]?.area || redZones[0]} has rising complaints`,
            subtext: 'This area is generating more cases than average. Consider a field visit.',
            priority: 'attention',
            trend: 30,
            onClick: () => router.push('/dashboard/messages'),
        });
    }

    if (topIssues.length > 0) {
        const [topCat, topCount] = topIssues[0];
        const catPct = totalCases > 0 ? Math.round((topCount / totalCases) * 100) : 0;
        briefingItems.push({
            headline: `"${topCat}" is your #1 issue (${catPct}% of cases)`,
            subtext: topIssues.length > 1
                ? `Followed by "${topIssues[1][0]}"${topIssues[2] ? ` and "${topIssues[2][0]}"` : ''}`
                : 'Consider addressing this in your next public communication.',
            onClick: () => router.push('/dashboard/messages'),
        });
    }

    if (briefingItems.length === 0) {
        briefingItems.push({
            headline: 'All caught up for today',
            subtext: 'No urgent matters require your attention. Great work staying on top of things!',
            onClick: undefined,
        });
    }

    // ── What You Should Do Today ──────────────────────────────────

    const actions = [];

    if (newCount > 0) {
        actions.push({
            icon: MessageSquare,
            title: `Respond to ${newCount} pending case${newCount !== 1 ? 's' : ''}`,
            description: oldestAge > 3 ? `Oldest waiting ${oldestAge} days` : 'Keep response time low',
            href: '/dashboard/messages',
            urgent: oldestAge > 7,
        });
    }

    if (unsentEscalations > 0) {
        actions.push({
            icon: Mail,
            title: `Send ${unsentEscalations} officer letter${unsentEscalations !== 1 ? 's' : ''}`,
            description: 'Escalation drafts ready — dispatch to officers',
            href: '/dashboard/messages',
            urgent: false,
        });
    }

    if (redZones.length > 0) {
        actions.push({
            icon: MapPin,
            title: `Visit ${redZones[0]?.area || redZones[0]}`,
            description: 'High complaint density — voters need to see you',
            href: '/dashboard/messages',
            urgent: false,
        });
    }

    const defaultActions = [
        { icon: MessageSquare, title: 'Review all cases', description: 'Manage and respond to grievances', href: '/dashboard/messages', urgent: false },
        { icon: UserCheck, title: 'Update voter contacts', description: 'Keep your CRM current', href: '/dashboard/contacts', urgent: false },
        { icon: BarChart2, title: 'View your reports', description: 'Constituency analytics and trends', href: '/dashboard/reports', urgent: false },
    ];
    while (actions.length < 3) {
        const next = defaultActions.find(d => !actions.some(a => a.href === d.href && a.title === d.title));
        if (next) actions.push(next);
        else break;
    }

    return (
        <div className="space-y-8 max-w-5xl mx-auto">

            {/* Header */}
            <section className="space-y-1">
                <h1 className="headline-hero">
                    {getGreeting()}, {user?.display_name?.split(' ')[0] || 'there'}
                </h1>
                <p className="text-muted-foreground">
                    {new Date().toLocaleDateString('en-IN', {
                        weekday: 'long', day: 'numeric', month: 'long',
                    })} — Here&apos;s what matters today
                </p>
            </section>

            {/* Today's Briefing */}
            <section className="space-y-4">
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

            {/* Empty state */}
            {isEmpty ? (
                <Card className="text-center py-12">
                    <CardContent className="space-y-4">
                        <div className="h-20 w-20 mx-auto rounded-full bg-primary/10 flex items-center justify-center">
                            <MessageSquare className="h-10 w-10 text-primary" />
                        </div>
                        <div>
                            <h2 className="headline-card">Welcome to your Command Center</h2>
                            <p className="text-sm text-muted-foreground mt-2 max-w-md mx-auto">
                                Share your WhatsApp number with voters to start receiving grievances. Your campaign office is ready.
                            </p>
                        </div>
                        <div className="flex flex-wrap justify-center gap-3 pt-4">
                            <Button asChild>
                                <Link href="/dashboard/messages">View Cases</Link>
                            </Button>
                            <Button variant="outline" asChild>
                                <Link href="/dashboard/contacts">Manage Contacts</Link>
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            ) : (
                <>
                    {/* What You Should Do Today */}
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

                    {/* Your Pulse */}
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
                                label="Escalated"
                                value={escalatedCount}
                                icon={TrendingUp}
                                highlight={escalatedCount > 5 ? 'warning' : null}
                            />
                            <InsightCard
                                label="Resolution Rate"
                                value={`${resolutionRate}%`}
                                icon={CheckCircle2}
                                highlight={resolutionRate >= 60 ? 'success' : resolutionRate >= 30 ? 'warning' : 'critical'}
                            />
                            <InsightCard
                                label="In Progress"
                                value={inProgressCount}
                                icon={Users}
                            />
                        </div>
                    </section>

                    {/* Top Issues */}
                    {topIssues.length > 0 && (
                        <section className="space-y-4">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <FileText className="h-5 w-5 text-primary" />
                                    <h2 className="headline-section">Top Issues</h2>
                                </div>
                                <Button variant="ghost" size="sm" asChild>
                                    <Link href="/dashboard/messages">
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
                                            onClick={() => router.push('/dashboard/messages')}
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
