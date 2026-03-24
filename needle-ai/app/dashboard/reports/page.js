'use client';

import { useState, useEffect } from 'react';
import { apiGet, apiBlob } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
    BarChart3,
    Download,
    FileText,
    TrendingUp,
    MapPin,
    Calendar,
    Loader2,
    MessageSquare,
} from 'lucide-react';

function BarItem({ label, value, maxValue, color = 'bg-primary' }) {
    const pct = maxValue > 0 ? Math.round((value / maxValue) * 100) : 0;
    return (
        <div className="flex items-center gap-3 py-1.5">
            <span className="text-sm text-foreground w-32 truncate">{label}</span>
            <div className="flex-1 h-6 bg-secondary rounded-md overflow-hidden relative">
                <div
                    className={`h-full ${color} rounded-md transition-all duration-700`}
                    style={{ width: `${pct}%` }}
                />
                <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs font-medium text-foreground">
                    {value}
                </span>
            </div>
        </div>
    );
}

export default function ReportsPage() {
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);
    const [downloading, setDownloading] = useState(false);

    useEffect(() => {
        const fetchSummary = async () => {
            try {
                const data = await apiGet('/api/dashboard/summary');
                setSummary(data);
            } catch {
                // Fail silently
            } finally {
                setLoading(false);
            }
        };
        fetchSummary();
    }, []);

    const handleDownloadPDF = async () => {
        setDownloading(true);
        try {
            const blob = await apiBlob('/api/reports/grievance');
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `grievance_report_${new Date().toISOString().split('T')[0]}.pdf`;
            a.click();
            URL.revokeObjectURL(url);
        } catch {
            // Fail silently
        } finally {
            setDownloading(false);
        }
    };

    const byCategory = summary?.by_category || [];
    const byStatus = summary?.by_status || [];
    const total = summary?.total || 0;
    const maxCatCount = byCategory.length > 0 ? Math.max(...byCategory.map(c => c.count)) : 0;
    const maxStatusCount = byStatus.length > 0 ? Math.max(...byStatus.map(s => s.count)) : 0;

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-xl font-bold text-foreground">Reports</h1>
                    <p className="text-sm text-muted-foreground mt-0.5">Analytics and export for your grievance data.</p>
                </div>
                <Button onClick={handleDownloadPDF} disabled={downloading}>
                    {downloading ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                        <Download className="h-4 w-4 mr-2" />
                    )}
                    Export PDF
                </Button>
            </div>

            {/* Summary Cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <Card>
                    <CardContent className="p-4 text-center">
                        <MessageSquare className="h-6 w-6 text-primary mx-auto mb-2" />
                        <p className="text-2xl font-bold">{loading ? '—' : total}</p>
                        <p className="text-xs text-muted-foreground">Total Messages</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="p-4 text-center">
                        <TrendingUp className="h-6 w-6 text-blue-500 mx-auto mb-2" />
                        <p className="text-2xl font-bold">{loading ? '—' : byCategory.length}</p>
                        <p className="text-xs text-muted-foreground">Categories</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="p-4 text-center">
                        <BarChart3 className="h-6 w-6 text-emerald-500 mx-auto mb-2" />
                        <p className="text-2xl font-bold">{loading ? '—' : byStatus.length}</p>
                        <p className="text-xs text-muted-foreground">Status Types</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="p-4 text-center">
                        <Calendar className="h-6 w-6 text-amber-500 mx-auto mb-2" />
                        <p className="text-2xl font-bold">{new Date().toLocaleDateString('en-IN', { month: 'short', year: 'numeric' })}</p>
                        <p className="text-xs text-muted-foreground">Report Period</p>
                    </CardContent>
                </Card>
            </div>

            <div className="grid lg:grid-cols-2 gap-6">
                {/* By Category */}
                <Card>
                    <CardContent className="p-5">
                        <h2 className="font-semibold text-foreground mb-4 flex items-center gap-2">
                            <TrendingUp className="h-5 w-5 text-primary" />
                            By Category
                        </h2>
                        {loading ? (
                            <div className="space-y-2">
                                {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
                            </div>
                        ) : byCategory.length > 0 ? (
                            <div className="space-y-1">
                                {byCategory.map(cat => (
                                    <BarItem key={cat.category} label={cat.category} value={cat.count} maxValue={maxCatCount} />
                                ))}
                            </div>
                        ) : (
                            <p className="text-sm text-muted-foreground text-center py-6">No data</p>
                        )}
                    </CardContent>
                </Card>

                {/* By Status */}
                <Card>
                    <CardContent className="p-5">
                        <h2 className="font-semibold text-foreground mb-4 flex items-center gap-2">
                            <BarChart3 className="h-5 w-5 text-primary" />
                            By Status
                        </h2>
                        {loading ? (
                            <div className="space-y-2">
                                {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
                            </div>
                        ) : byStatus.length > 0 ? (
                            <div className="space-y-1">
                                {byStatus.map(s => (
                                    <BarItem
                                        key={s.status}
                                        label={s.status}
                                        value={s.count}
                                        maxValue={maxStatusCount}
                                        color={
                                            s.status === 'new' ? 'bg-blue-500' :
                                            s.status === 'resolved' ? 'bg-emerald-500' :
                                            s.status === 'emergency' ? 'bg-red-500' :
                                            s.status === 'in_progress' ? 'bg-amber-500' :
                                            'bg-slate-400'
                                        }
                                    />
                                ))}
                            </div>
                        ) : (
                            <p className="text-sm text-muted-foreground text-center py-6">No data</p>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
