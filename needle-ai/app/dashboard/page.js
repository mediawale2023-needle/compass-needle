'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
    MessageSquare,
    AlertTriangle,
    CheckCircle2,
    Clock,
    TrendingUp,
    Users,
    MapPin,
    Zap,
} from 'lucide-react';

function StatCard({ icon: Icon, label, value, color, loading }) {
    return (
        <Card className="card-hover">
            <CardContent className="p-4 flex items-center gap-4">
                <div className={`h-12 w-12 rounded-xl flex items-center justify-center shrink-0 ${color}`}>
                    <Icon className="h-6 w-6 text-white" />
                </div>
                <div className="min-w-0">
                    <p className="text-sm text-muted-foreground">{label}</p>
                    {loading ? (
                        <Skeleton className="h-7 w-16 mt-1" />
                    ) : (
                        <p className="text-2xl font-bold text-foreground">{value}</p>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}

function CategoryItem({ name, count, total }) {
    const pct = total > 0 ? Math.round((count / total) * 100) : 0;
    return (
        <div className="flex items-center justify-between py-2">
            <span className="text-sm text-foreground truncate">{name}</span>
            <div className="flex items-center gap-3">
                <div className="w-24 h-2 bg-secondary rounded-full overflow-hidden">
                    <div
                        className="h-full bg-primary rounded-full transition-all duration-500"
                        style={{ width: `${pct}%` }}
                    />
                </div>
                <span className="text-sm font-medium text-muted-foreground w-8 text-right">{count}</span>
            </div>
        </div>
    );
}

export default function TodayPage() {
    const { user } = useAuth();
    const [summary, setSummary] = useState(null);
    const [recentCases, setRecentCases] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [summaryData, casesData] = await Promise.all([
                    apiGet('/api/dashboard/summary').catch(() => null),
                    apiGet('/api/cases?page=1&per_page=5').catch(() => ({ cases: [] })),
                ]);
                setSummary(summaryData);
                setRecentCases(casesData.cases || []);
            } catch {
                // Fail silently
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    const byStatus = summary?.by_status || [];
    const byCategory = summary?.by_category || [];
    const totalCases = summary?.total || 0;
    const newCount = byStatus.find(s => s.status === 'new')?.count || 0;
    const emergencyCount = byStatus.find(s => s.status === 'emergency')?.count || 0;
    const resolvedCount = byStatus.find(s => s.status === 'resolved')?.count || 0;
    const inProgressCount = byStatus.find(s => s.status === 'in_progress')?.count || 0;

    const greeting = () => {
        const hour = new Date().getHours();
        if (hour < 12) return 'Good morning';
        if (hour < 17) return 'Good afternoon';
        return 'Good evening';
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold text-foreground">
                    {greeting()}, {user?.display_name?.split(' ')[0] || 'there'}
                </h1>
                <p className="text-muted-foreground mt-1">
                    Here's what's happening in your constituency today.
                </p>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard
                    icon={MessageSquare}
                    label="New Messages"
                    value={newCount}
                    color="bg-blue-500"
                    loading={loading}
                />
                <StatCard
                    icon={AlertTriangle}
                    label="Emergency"
                    value={emergencyCount}
                    color="bg-red-500"
                    loading={loading}
                />
                <StatCard
                    icon={Clock}
                    label="In Progress"
                    value={inProgressCount}
                    color="bg-amber-500"
                    loading={loading}
                />
                <StatCard
                    icon={CheckCircle2}
                    label="Resolved"
                    value={resolvedCount}
                    color="bg-emerald-500"
                    loading={loading}
                />
            </div>

            <div className="grid lg:grid-cols-2 gap-6">
                {/* Top Categories */}
                <Card>
                    <CardContent className="p-5">
                        <div className="flex items-center gap-2 mb-4">
                            <TrendingUp className="h-5 w-5 text-primary" />
                            <h2 className="font-semibold text-foreground">Top Categories</h2>
                        </div>
                        {loading ? (
                            <div className="space-y-3">
                                {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
                            </div>
                        ) : byCategory.length > 0 ? (
                            <div className="divide-y divide-border">
                                {byCategory.slice(0, 8).map((cat) => (
                                    <CategoryItem
                                        key={cat.category}
                                        name={cat.category}
                                        count={cat.count}
                                        total={totalCases}
                                    />
                                ))}
                            </div>
                        ) : (
                            <p className="text-sm text-muted-foreground py-4 text-center">No data yet</p>
                        )}
                    </CardContent>
                </Card>

                {/* Recent Messages */}
                <Card>
                    <CardContent className="p-5">
                        <div className="flex items-center gap-2 mb-4">
                            <Zap className="h-5 w-5 text-primary" />
                            <h2 className="font-semibold text-foreground">Recent Messages</h2>
                        </div>
                        {loading ? (
                            <div className="space-y-3">
                                {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
                            </div>
                        ) : recentCases.length > 0 ? (
                            <div className="space-y-3">
                                {recentCases.map((c) => (
                                    <div key={c.id} className="flex items-start gap-3 p-3 rounded-lg bg-secondary/50 hover:bg-secondary transition-colors">
                                        <div className="shrink-0 mt-0.5">
                                            <MessageSquare className="h-4 w-4 text-muted-foreground" />
                                        </div>
                                        <div className="min-w-0 flex-1">
                                            <p className="text-sm text-foreground line-clamp-2">{c.raw_message}</p>
                                            <div className="flex items-center gap-2 mt-1.5">
                                                <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                                                    {c.category || 'General'}
                                                </Badge>
                                                {c.location && (
                                                    <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
                                                        <MapPin className="h-3 w-3" />
                                                        {c.location}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                        <Badge
                                            variant="outline"
                                            className={`shrink-0 text-[10px] ${
                                                c.status === 'new' ? 'status-new' :
                                                c.status === 'emergency' ? 'status-escalated' :
                                                c.status === 'resolved' ? 'status-resolved' :
                                                'status-in_progress'
                                            }`}
                                        >
                                            {c.status}
                                        </Badge>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-sm text-muted-foreground py-4 text-center">No messages yet. Share your WhatsApp number to start receiving grievances.</p>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
