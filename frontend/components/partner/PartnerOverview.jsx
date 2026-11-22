'use client';

import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { partnerClientOverview } from '@/lib/partnerApi';
import { fmtCount } from '@/lib/partnerFormat';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

// Government outcomes only (what the portals report). Needle's own resolution rate lives on the Analytics tab.
const GOVT_TILES = [
    ['ready', 'Ready to file'],
    ['submitted', 'Submitted'],
    ['registered', 'Registered'],
    ['forwarded', 'Forwarded'],
    ['awaiting_action', 'Awaiting action'],
    ['resolved', 'Resolved'],
    ['disposed', 'Disposed'],
    ['rejected', 'Rejected'],
    ['awaiting_verification', 'Awaiting verification'],
    ['sync_issues', 'Sync issues'],
];

const TONE = { red: 'text-red-600', amber: 'text-amber-600', rust: 'text-orange-700', green: 'text-emerald-700' };

function Tile({ label, value, tone }) {
    return (
        <Card>
            <CardContent className="p-4">
                <div className={`text-3xl font-semibold tabular-nums ${TONE[tone] || 'text-primary'}`}>{fmtCount(value)}</div>
                <div className="mt-1 text-sm text-muted-foreground">{label}</div>
            </CardContent>
        </Card>
    );
}

function CountList({ title, items, empty }) {
    return (
        <Card>
            <CardHeader className="pb-2"><CardTitle className="text-base">{title}</CardTitle></CardHeader>
            <CardContent>
                {items.length === 0 ? (
                    <p className="text-sm text-muted-foreground">{empty}</p>
                ) : (
                    <ul className="space-y-2">
                        {items.map((item) => (
                            <li key={item.key} className="flex items-center justify-between gap-3 text-sm">
                                <span>{item.label}</span>
                                <span className="font-medium tabular-nums">{item.count}</span>
                            </li>
                        ))}
                    </ul>
                )}
            </CardContent>
        </Card>
    );
}

export default function PartnerOverview({ seatId, onUnauthorized }) {
    const [overview, setOverview] = useState(null);
    const [status, setStatus] = useState('loading'); // loading | ready | error
    const [error, setError] = useState('');

    const load = useCallback(async () => {
        setStatus('loading');
        setError('');
        try {
            const res = await partnerClientOverview(seatId);
            setOverview(res.overview);
            setStatus('ready');
        } catch (err) {
            if (err.status === 401 && onUnauthorized) return onUnauthorized();
            setError(err.message || 'The overview could not be loaded.');
            setStatus('error');
        }
    }, [seatId, onUnauthorized]);

    useEffect(() => { load(); }, [load]);

    if (status === 'error') {
        return (
            <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm">
                <div className="flex items-start gap-2 text-destructive">
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                    <span>The overview is unavailable right now. {error}</span>
                </div>
                <Button variant="outline" size="sm" onClick={load}><RefreshCw aria-hidden="true" /> Retry</Button>
            </div>
        );
    }

    if (status === 'loading' || !overview) {
        return (
            <div className="space-y-4" aria-busy="true" aria-label="Loading overview">
                <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-24" />)}</div>
                <Skeleton className="h-40" />
            </div>
        );
    }

    const gt = overview.government_tracking || {};
    return (
        <div className="space-y-6">
            <section aria-label="Needs attention">
                <h2 className="mb-3 font-serif text-xl font-semibold">Needs attention</h2>
                <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
                    {overview.attention_counts.map((c) => <Tile key={c.key} label={c.label} value={c.value} tone={c.tone} />)}
                </div>
                <p className="mt-2 text-xs text-muted-foreground">
                    Counts of grievance threads. Individual grievances and citizen details are not shown to partners.
                </p>
            </section>

            <section aria-label="Government tracking">
                <h2 className="font-serif text-xl font-semibold">Government tracking</h2>
                <p className="mb-3 text-sm text-muted-foreground">
                    What the government portals report. This is separate from Needle&apos;s own resolution figures on the Analytics tab.
                </p>
                <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
                    {GOVT_TILES.map(([key, label]) => <Tile key={key} label={label} value={gt[key]} />)}
                </div>
            </section>

            <div className="grid gap-4 md:grid-cols-2">
                <CountList title="Constituency pressure"
                    items={(overview.constituency_pressure || []).map((a) => ({ key: a.name, label: a.name, count: a.count }))}
                    empty="No area breakdown available yet." />
                <CountList title="Issue pressure"
                    items={(overview.issue_pressure || []).map((i) => ({ key: i.title, label: i.title, count: i.count }))}
                    empty="No grievances yet." />
            </div>

            <section aria-label="Office pending">
                <Card>
                    <CardHeader className="pb-2"><CardTitle className="text-base">Office pending</CardTitle></CardHeader>
                    <CardContent>
                        <ul className="space-y-2">
                            {(overview.office_pending || []).map((o) => (
                                <li key={o.key} className="flex items-center justify-between gap-3 text-sm">
                                    <span>{o.label}</span>
                                    <span className="font-medium tabular-nums">{o.value}</span>
                                </li>
                            ))}
                        </ul>
                    </CardContent>
                </Card>
            </section>
        </div>
    );
}
