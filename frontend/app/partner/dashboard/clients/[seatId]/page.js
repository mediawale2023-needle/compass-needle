'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertCircle, ArrowLeft, Download, ExternalLink, FileText, Loader2, RefreshCw } from 'lucide-react';
import { usePartnerSession } from '@/lib/partnerSession';
import { partnerClientReport, partnerClientSummary } from '@/lib/partnerApi';
import { PERIODS, fmtCount, fmtDays, fmtPct } from '@/lib/partnerFormat';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

function Kpi({ label, value }) {
    return (
        <Card>
            <CardContent className="p-4">
                <div className="text-3xl font-semibold tabular-nums text-primary">{value}</div>
                <div className="mt-1 text-sm text-muted-foreground">{label}</div>
            </CardContent>
        </Card>
    );
}

function WeeklyChart({ weekly }) {
    const max = Math.max(1, ...weekly.map((w) => w.received));
    const description = weekly
        .map((w) => `week ending ${w.week_ending}: ${w.received} received, ${w.resolved} resolved`)
        .join('; ');
    return (
        <div>
            <div role="img" aria-label={`Weekly grievances, last 8 weeks. ${description}`} className="flex h-32 items-end gap-2 border-b">
                {weekly.map((w) => (
                    <div key={w.week_ending} className="flex h-full flex-1 flex-col justify-end" title={`${w.week_ending}: ${w.received} received, ${w.resolved} resolved`}>
                        <div className="relative w-full rounded-t bg-primary/25" style={{ height: `${Math.max((w.received / max) * 100, 2)}%` }}>
                            <div className="absolute bottom-0 w-full rounded-t bg-primary" style={{ height: `${w.received ? (w.resolved / w.received) * 100 : 0}%` }} />
                        </div>
                    </div>
                ))}
            </div>
            <div className="mt-2 flex items-center gap-4 text-xs text-muted-foreground">
                <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-sm bg-primary/25" aria-hidden="true" /> Received</span>
                <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-sm bg-primary" aria-hidden="true" /> Resolved</span>
            </div>
        </div>
    );
}

function RankedList({ title, items }) {
    const max = Math.max(1, ...items.map((i) => i.count));
    return (
        <Card>
            <CardHeader className="pb-2"><CardTitle className="text-base">{title}</CardTitle></CardHeader>
            <CardContent>
                {items.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No grievances in this period.</p>
                ) : (
                    <ul className="space-y-3">
                        {items.map((item) => (
                            <li key={item.name}>
                                <div className="flex justify-between gap-3 text-sm">
                                    <span className="truncate">{item.name}</span>
                                    <span className="tabular-nums text-muted-foreground">{item.count}</span>
                                </div>
                                <div className="mt-1 h-1.5 rounded bg-muted" aria-hidden="true">
                                    <div className="h-1.5 rounded bg-primary" style={{ width: `${(item.count / max) * 100}%` }} />
                                </div>
                            </li>
                        ))}
                    </ul>
                )}
            </CardContent>
        </Card>
    );
}

function ReportPanel({ seatId, days, clientLabel }) {
    const [html, setHtml] = useState(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');

    // A report for another period or client is stale; drop it rather than show mismatched numbers.
    useEffect(() => {
        setHtml(null);
        setError('');
    }, [seatId, days]);

    async function loadReport() {
        setBusy(true);
        setError('');
        try {
            setHtml(await partnerClientReport(seatId, days));
        } catch (err) {
            setError(err.message || 'The report could not be generated.');
        } finally {
            setBusy(false);
        }
    }

    function blobUrl() {
        return URL.createObjectURL(new Blob([html], { type: 'text/html;charset=utf-8' }));
    }

    function openForPrint() {
        const url = blobUrl();
        window.open(url, '_blank', 'noopener');
        setTimeout(() => URL.revokeObjectURL(url), 60000);
    }

    function download() {
        const url = blobUrl();
        const a = document.createElement('a');
        a.href = url;
        a.download = `${clientLabel.replace(/[^a-z0-9]+/gi, '-').toLowerCase() || 'client'}-report-${days}d.html`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    return (
        <Card>
            <CardHeader className="flex-row flex-wrap items-center justify-between gap-3 space-y-0">
                <CardTitle className="font-serif text-xl">Branded report</CardTitle>
                <div className="flex flex-wrap gap-2">
                    {!html ? (
                        <Button onClick={loadReport} disabled={busy}>
                            {busy ? <Loader2 className="animate-spin" aria-hidden="true" /> : <FileText aria-hidden="true" />}
                            Generate report
                        </Button>
                    ) : (
                        <>
                            <Button variant="outline" onClick={openForPrint}><ExternalLink aria-hidden="true" /> Open to print or save PDF</Button>
                            <Button variant="outline" onClick={download}><Download aria-hidden="true" /> Download HTML</Button>
                        </>
                    )}
                </div>
            </CardHeader>
            <CardContent>
                {error && (
                    <div role="alert" className="flex items-start gap-2 text-sm text-destructive">
                        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /> <span>{error}</span>
                    </div>
                )}
                {!html && !error && (
                    <p className="text-sm text-muted-foreground">
                        A client-ready summary under your brand: last {days} days, aggregate figures only, no citizen details.
                    </p>
                )}
                {html && (
                    // Fully sandboxed: no scripts, no same-origin access, even if report markup were ever wrong.
                    <iframe title={`${clientLabel} report preview`} sandbox="" srcDoc={html}
                        className="h-[640px] w-full rounded-lg border bg-white" />
                )}
            </CardContent>
        </Card>
    );
}

export default function PartnerClientPage() {
    const router = useRouter();
    const params = useParams();
    const seatId = params?.seatId;
    const { ready, token, mustChangePassword } = usePartnerSession();
    const [days, setDays] = useState(30);
    const [result, setResult] = useState(null);
    const [status, setStatus] = useState('loading'); // loading | ready | error | missing
    const [error, setError] = useState('');

    const load = useCallback(async () => {
        setStatus('loading');
        setError('');
        try {
            setResult(await partnerClientSummary(seatId, days));
            setStatus('ready');
        } catch (err) {
            if (err.status === 401) return router.replace('/partner');
            if (err.status === 404 || err.status === 409) {
                setError(err.message);
                setStatus('missing');
                return;
            }
            setError(err.message || 'Client data could not be loaded.');
            setStatus('error');
        }
    }, [seatId, days, router]);

    useEffect(() => {
        if (!ready) return;
        if (!token || mustChangePassword) {
            router.replace('/partner');
            return;
        }
        load();
    }, [ready, token, mustChangePassword, load, router]);

    if (!ready || !token) return null;

    const client = result?.client;
    const s = result?.summary;

    return (
        <div className="space-y-6">
            <Link href="/partner/dashboard" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
                <ArrowLeft className="h-4 w-4" aria-hidden="true" /> All clients
            </Link>

            {status === 'missing' && (
                <div role="alert" className="rounded-lg border p-6">
                    <h1 className="font-serif text-2xl font-semibold">This client isn&apos;t available</h1>
                    <p className="mt-2 text-sm text-muted-foreground">{error}</p>
                </div>
            )}

            {status === 'error' && (
                <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm">
                    <div className="flex items-start gap-2 text-destructive">
                        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                        <span>Client data is unavailable right now. {error}</span>
                    </div>
                    <Button variant="outline" size="sm" onClick={load}><RefreshCw aria-hidden="true" /> Retry</Button>
                </div>
            )}

            {status === 'loading' && !result && (
                <div className="space-y-4" aria-busy="true" aria-label="Loading client">
                    <Skeleton className="h-10 w-72" />
                    <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-24" />)}</div>
                    <Skeleton className="h-40" />
                </div>
            )}

            {result && status !== 'missing' && status !== 'error' && (
                <>
                    <div className="flex flex-wrap items-end justify-between gap-4">
                        <div>
                            <h1 className="font-serif text-3xl font-semibold">{client.client_label}</h1>
                            <p className="mt-1 text-sm text-muted-foreground">
                                {[client.constituency, client.seat_type === 'mla' ? 'MLA' : 'MP'].filter(Boolean).join(' · ')}
                            </p>
                        </div>
                        <div role="group" aria-label="Reporting period" className="inline-flex rounded-lg border bg-card p-1">
                            {PERIODS.map((p) => (
                                <button key={p} type="button" aria-pressed={days === p} onClick={() => setDays(p)}
                                    className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                                        days === p ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}`}>
                                    {p} days
                                </button>
                            ))}
                        </div>
                    </div>

                    <section aria-label={`Headline numbers, last ${days} days`} className="grid grid-cols-2 gap-4 lg:grid-cols-5">
                        <Kpi label="Received" value={fmtCount(s.total)} />
                        <Kpi label="Resolved" value={fmtPct(s.resolution_rate)} />
                        <Kpi label="Still open" value={fmtCount(s.open)} />
                        <Kpi label="Critical" value={fmtCount(s.critical)} />
                        <Kpi label="Avg. to resolve" value={fmtDays(s.avg_resolution_days)} />
                    </section>

                    <Card>
                        <CardHeader className="pb-2"><CardTitle className="text-base">Weekly volume, last 8 weeks</CardTitle></CardHeader>
                        <CardContent><WeeklyChart weekly={s.weekly} /></CardContent>
                    </Card>

                    <div className="grid gap-4 md:grid-cols-2">
                        <RankedList title="Top issue categories" items={s.top_categories} />
                        <RankedList title="Where complaints come from" items={s.top_locations} />
                    </div>

                    <ReportPanel seatId={seatId} days={days} clientLabel={client.client_label} />
                </>
            )}
        </div>
    );
}
