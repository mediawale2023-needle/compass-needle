'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { apiGet } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import {
    MessageSquare, AlertTriangle, CheckCircle2,
    Shield, Mail, MapPin, ArrowRight, Users, Zap,
    Clock, TrendingUp, Target,
} from 'lucide-react';

// ── Utilities ─────────────────────────────────────────────────────

function getGreeting() {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
}

function getTodayDate() {
    return new Date().toLocaleDateString('en-IN', {
        weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
    });
}

// ── Stat Card ─────────────────────────────────────────────────────

function StatCard({ label, value, borderColor, loading, onClick }) {
    return (
        <div
            className={cn(
                'bg-card border rounded-xl p-5 flex flex-col gap-1 border-l-4',
                borderColor,
                onClick && 'cursor-pointer hover:shadow-md transition-shadow'
            )}
            onClick={onClick}
        >
            {loading ? (
                <>
                    <Skeleton className="h-9 w-14" />
                    <Skeleton className="h-4 w-24 mt-1" />
                </>
            ) : (
                <>
                    <span className="text-3xl font-bold text-foreground tabular-nums">{value ?? 0}</span>
                    <span className="text-sm text-muted-foreground">{label}</span>
                </>
            )}
        </div>
    );
}

// ── Insight Card (Your Pulse) ─────────────────────────────────────

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

// ── Horizontal Bar ────────────────────────────────────────────────

function HBar({ name, count, max, color = 'bg-blue-400' }) {
    const pct = max > 0 ? Math.round((count / max) * 100) : 0;
    return (
        <div className="flex items-center gap-3 py-1.5">
            <span className="text-sm text-foreground w-36 truncate shrink-0">{name}</span>
            <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                <div className={cn('h-full rounded-full transition-all duration-500', color)} style={{ width: `${pct}%` }} />
            </div>
            <span className="text-sm font-medium text-muted-foreground w-8 text-right tabular-nums">{count}</span>
        </div>
    );
}

// ── Action Alert ──────────────────────────────────────────────────

function ActionAlert({ icon: Icon, iconColor, title, subtitle, href, router }) {
    return (
        <div
            className="flex items-start justify-between gap-3 p-3 rounded-lg border hover:bg-muted/40 cursor-pointer transition-colors group"
            onClick={() => router.push(href)}
        >
            <div className="flex items-start gap-3 min-w-0">
                <Icon className={cn('h-4 w-4 shrink-0 mt-0.5', iconColor)} />
                <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground leading-snug">{title}</p>
                    {subtitle && <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>}
                </div>
            </div>
            <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5 group-hover:translate-x-0.5 transition-transform" />
        </div>
    );
}

// ── Quick Action Button ────────────────────────────────────────────

function QuickAction({ icon: Icon, iconColor, label, href, router }) {
    return (
        <button
            onClick={() => router.push(href)}
            className="w-full flex items-center justify-between px-4 py-3 rounded-lg border hover:bg-muted/40 transition-colors group text-left"
        >
            <div className="flex items-center gap-3">
                <Icon className={cn('h-4 w-4', iconColor)} />
                <span className="text-sm font-medium text-foreground">{label}</span>
            </div>
            <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:translate-x-0.5 transition-transform" />
        </button>
    );
}

// ── Page ──────────────────────────────────────────────────────────

export default function HomePage() {
    const { user } = useAuth();
    const router = useRouter();
    const [summary, setSummary] = useState(null);
    const [escalations, setEscalations] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        Promise.all([
            apiGet('/api/dashboard/summary').catch(() => null),
            apiGet('/api/escalations').catch(() => ({ escalations: [] })),
        ]).then(([s, e]) => {
            setSummary(s);
            setEscalations(e?.escalations || []);
        }).finally(() => setLoading(false));
    }, []);

    const sb          = summary?.status_breakdown || {};
    const cb          = summary?.category_breakdown || {};
    const redZones    = summary?.red_zones || [];
    const critical    = summary?.critical_count || 0;
    const total       = summary?.total_cases || 0;

    const newCount       = sb.new || 0;
    const escalatedCount = sb.escalated || 0;
    const resolvedCount  = sb.resolved || 0;
    const inProgressCount = sb.in_progress || 0;

    const resolutionRate = total > 0 ? Math.round((resolvedCount / total) * 100) : 0;

    const unsentEscalations = escalations.filter(e => !e.email_sent).length;

    const categoryList = Object.entries(cb)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 7)
        .map(([name, count]) => ({ name, count }));

    const maxCat  = categoryList[0]?.count || 1;
    const maxArea = redZones[0]?.count || 1;

    // Build action alerts — only show items that are actually actionable
    const actionAlerts = [
        unsentEscalations > 0 && {
            icon: Mail,
            iconColor: 'text-amber-500',
            title: `${unsentEscalations} escalated case${unsentEscalations !== 1 ? 's' : ''} — officer email not sent`,
            subtitle: 'Letters are ready but not dispatched yet',
            href: '/dashboard/messages',
        },
        newCount > 0 && {
            icon: MessageSquare,
            iconColor: 'text-blue-500',
            title: `${newCount} new case${newCount !== 1 ? 's' : ''} waiting for response`,
            subtitle: 'Review, assign, or resolve incoming grievances',
            href: '/dashboard/messages',
        },
        critical > 0 && {
            icon: AlertTriangle,
            iconColor: 'text-red-500',
            title: `${critical} critical case${critical !== 1 ? 's' : ''} still open`,
            subtitle: 'High-priority issues flagged in your constituency',
            href: '/dashboard/messages',
        },
    ].filter(Boolean);

    return (
        <div className="space-y-6 max-w-6xl">

            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold text-foreground">
                    {getGreeting()}, {user?.display_name?.split(' ')[0] || 'there'}
                </h1>
                <p className="text-sm text-muted-foreground mt-0.5">{getTodayDate()}</p>
            </div>

            {/* Stat Cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard
                    label="New Cases"
                    value={newCount}
                    borderColor="border-l-blue-500"
                    loading={loading}
                    onClick={() => router.push('/dashboard/messages')}
                />
                <StatCard
                    label="Escalated"
                    value={escalatedCount}
                    borderColor="border-l-red-400"
                    loading={loading}
                    onClick={() => router.push('/dashboard/messages')}
                />
                <StatCard
                    label="Critical Open"
                    value={critical}
                    borderColor="border-l-red-600"
                    loading={loading}
                />
                <StatCard
                    label="Resolved"
                    value={resolvedCount}
                    borderColor="border-l-green-500"
                    loading={loading}
                />
            </div>

            {/* Your Pulse */}
            <div>
                <div className="flex items-center gap-2 mb-3">
                    <Target className="h-4 w-4 text-primary" />
                    <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Your Pulse</h2>
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
            </div>

            {/* Main Grid: 3/5 left + 2/5 right */}
            <div className="grid lg:grid-cols-5 gap-6 items-start">

                {/* Left Column */}
                <div className="lg:col-span-3 space-y-6">

                    {/* Top Issue Categories */}
                    <Card>
                        <CardContent className="p-5">
                            <h2 className="font-semibold text-foreground mb-4">Top Issue Categories</h2>
                            {loading ? (
                                <div className="space-y-3">
                                    {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-6 w-full" />)}
                                </div>
                            ) : categoryList.length > 0 ? (
                                <div className="divide-y divide-border/50">
                                    {categoryList.map(({ name, count }) => (
                                        <HBar key={name} name={name} count={count} max={maxCat} color="bg-blue-400" />
                                    ))}
                                </div>
                            ) : (
                                <p className="text-sm text-muted-foreground py-6 text-center">No data yet</p>
                            )}
                        </CardContent>
                    </Card>

                    {/* High-Complaint Areas — only shown when data exists */}
                    {(loading || redZones.length > 0) && (
                        <Card>
                            <CardContent className="p-5">
                                <div className="flex items-center justify-between mb-4">
                                    <div className="flex items-center gap-2">
                                        <MapPin className="h-4 w-4 text-muted-foreground" />
                                        <h2 className="font-semibold text-foreground">High-Complaint Areas</h2>
                                    </div>
                                    <span className="text-xs text-muted-foreground">3+ cases</span>
                                </div>
                                {loading ? (
                                    <div className="space-y-3">
                                        {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-6 w-full" />)}
                                    </div>
                                ) : (
                                    <div className="divide-y divide-border/50">
                                        {redZones.slice(0, 6).map(({ area, count }) => (
                                            <HBar key={area} name={area} count={count} max={maxArea} color="bg-primary/60" />
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    )}
                </div>

                {/* Right Column */}
                <div className="lg:col-span-2 space-y-6">

                    {/* Needs Action */}
                    <Card>
                        <CardContent className="p-5">
                            <div className="mb-4">
                                <h2 className="font-semibold text-foreground">Needs Action</h2>
                                <p className="text-xs text-muted-foreground mt-0.5">What requires attention right now</p>
                            </div>
                            {loading ? (
                                <div className="space-y-2">
                                    {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-16 w-full rounded-lg" />)}
                                </div>
                            ) : !total ? (
                                /* Empty state — no cases at all */
                                <div className="py-6 text-center space-y-2">
                                    <Zap className="h-8 w-8 text-muted-foreground/30 mx-auto" />
                                    <p className="text-sm font-medium text-foreground">No cases yet</p>
                                    <p className="text-xs text-muted-foreground leading-relaxed">
                                        Share your WhatsApp number with voters to start receiving grievances.
                                    </p>
                                </div>
                            ) : actionAlerts.length > 0 ? (
                                <div className="space-y-2">
                                    {actionAlerts.map((alert, i) => (
                                        <ActionAlert key={i} {...alert} router={router} />
                                    ))}
                                </div>
                            ) : (
                                /* All clear */
                                <div className="py-6 text-center">
                                    <CheckCircle2 className="h-8 w-8 text-green-500 mx-auto mb-2" />
                                    <p className="text-sm font-medium text-foreground">All clear</p>
                                    <p className="text-xs text-muted-foreground mt-1">No urgent items right now</p>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Quick Actions */}
                    <Card>
                        <CardContent className="p-5">
                            <h2 className="font-semibold text-foreground mb-4">Quick Actions</h2>
                            <div className="space-y-2">
                                <QuickAction
                                    icon={MessageSquare}
                                    iconColor="text-blue-500"
                                    label="View All Cases"
                                    href="/dashboard/messages"
                                    router={router}
                                />
                                <QuickAction
                                    icon={Shield}
                                    iconColor="text-amber-500"
                                    label="Officer Dispatches"
                                    href="/dashboard/messages"
                                    router={router}
                                />
                                <QuickAction
                                    icon={Users}
                                    iconColor="text-primary"
                                    label="Manage Officers"
                                    href="/dashboard/officers"
                                    router={router}
                                />
                            </div>
                        </CardContent>
                    </Card>

                </div>
            </div>
        </div>
    );
}
