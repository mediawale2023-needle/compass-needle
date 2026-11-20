'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AlertCircle, ArrowRight, Loader2, Plus, RefreshCw } from 'lucide-react';
import { usePartnerSession } from '@/lib/partnerSession';
import { partnerClients, partnerRequestSeat } from '@/lib/partnerApi';
import { PERIODS, SEAT_STATUS, fmtCount, fmtDays, fmtPct } from '@/lib/partnerFormat';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Textarea } from '@/components/ui/textarea';

function PeriodPicker({ days, onChange }) {
    return (
        <div role="group" aria-label="Reporting period" className="inline-flex rounded-lg border bg-card p-1">
            {PERIODS.map((p) => (
                <button
                    key={p}
                    type="button"
                    aria-pressed={days === p}
                    onClick={() => onChange(p)}
                    className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                        days === p ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'
                    }`}
                >
                    {p} days
                </button>
            ))}
        </div>
    );
}

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

function SeatRequestForm({ onCreated, onCancel }) {
    const [label, setLabel] = useState('');
    const [constituency, setConstituency] = useState('');
    const [seatType, setSeatType] = useState('mla');
    const [notes, setNotes] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');

    async function submit(e) {
        e.preventDefault();
        setBusy(true);
        setError('');
        try {
            await partnerRequestSeat({
                client_label: label.trim(),
                constituency: constituency.trim(),
                seat_type: seatType,
                notes: notes.trim(),
            });
            onCreated();
        } catch (err) {
            setError(err.message || 'Could not send the request.');
        } finally {
            setBusy(false);
        }
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle className="font-serif text-xl">Request a client seat</CardTitle>
                <CardDescription>The Needle team sets the seat up and links it to your account, usually within 48 hours.</CardDescription>
            </CardHeader>
            <CardContent>
                <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                        <Label htmlFor="seat-label">Client name</Label>
                        <Input id="seat-label" required maxLength={120} value={label} onChange={(e) => setLabel(e.target.value)} />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="seat-constituency">Constituency</Label>
                        <Input id="seat-constituency" maxLength={120} value={constituency} onChange={(e) => setConstituency(e.target.value)} />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="seat-type">Seat type</Label>
                        <select
                            id="seat-type"
                            value={seatType}
                            onChange={(e) => setSeatType(e.target.value)}
                            className="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                            <option value="mla">MLA (state assembly)</option>
                            <option value="mp">MP (Lok Sabha / Rajya Sabha)</option>
                        </select>
                    </div>
                    <div className="space-y-2 sm:col-span-2">
                        <Label htmlFor="seat-notes">Notes for the Needle team (optional)</Label>
                        <Textarea id="seat-notes" maxLength={1000} rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
                    </div>
                    {error && (
                        <div role="alert" className="flex items-start gap-2 text-sm text-destructive sm:col-span-2">
                            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                            <span>{error}</span>
                        </div>
                    )}
                    <div className="flex gap-2 sm:col-span-2">
                        <Button type="submit" disabled={busy || !label.trim()}>
                            {busy ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
                            Send request
                        </Button>
                        <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
                    </div>
                </form>
            </CardContent>
        </Card>
    );
}

export default function PartnerDashboardPage() {
    const router = useRouter();
    const { ready, token, mustChangePassword } = usePartnerSession();
    const [days, setDays] = useState(30);
    const [data, setData] = useState(null);
    const [status, setStatus] = useState('loading'); // loading | ready | error
    const [error, setError] = useState('');
    const [showForm, setShowForm] = useState(false);
    const [notice, setNotice] = useState('');

    const load = useCallback(async () => {
        setStatus('loading');
        setError('');
        try {
            setData(await partnerClients(days));
            setStatus('ready');
        } catch (err) {
            if (err.status === 401) {
                router.replace('/partner');
                return;
            }
            setError(err.message || 'Client data could not be loaded.');
            setStatus('error');
        }
    }, [days, router]);

    useEffect(() => {
        if (!ready) return;
        if (!token || mustChangePassword) {
            router.replace('/partner');
            return;
        }
        load();
    }, [ready, token, mustChangePassword, load, router]);

    if (!ready || !token) return null;

    const atCap = data ? data.seats_used >= data.seat_cap : false;

    return (
        <div className="space-y-6">
            <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                    <h1 className="font-serif text-3xl font-semibold">Your clients</h1>
                    <p className="mt-1 text-sm text-muted-foreground">
                        {data ? `${data.seats_used} of ${data.seat_cap} seats used` : 'Loading seat usage…'}
                    </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <PeriodPicker days={days} onChange={setDays} />
                    <Button variant="outline" onClick={() => { setNotice(''); setShowForm((v) => !v); }} disabled={!data || atCap}
                        title={atCap ? 'Seat cap reached. Contact Needle to raise it.' : undefined}>
                        <Plus aria-hidden="true" /> Request client seat
                    </Button>
                </div>
            </div>

            {notice && (
                <div role="status" className="rounded-lg border border-primary/30 bg-primary/10 p-3 text-sm">{notice}</div>
            )}
            {showForm && (
                <SeatRequestForm
                    onCancel={() => setShowForm(false)}
                    onCreated={() => {
                        setShowForm(false);
                        setNotice('Seat requested. It will show as "Awaiting activation" until Needle links it.');
                        load();
                    }}
                />
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

            {status === 'loading' && !data && (
                <div className="space-y-4" aria-busy="true" aria-label="Loading clients">
                    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                        {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24" />)}
                    </div>
                    <Skeleton className="h-48" />
                </div>
            )}

            {data && status !== 'error' && (
                <>
                    <section aria-label={`Portfolio totals, last ${days} days`} className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                        <Kpi label="Grievances received" value={fmtCount(data.portfolio.total)} />
                        <Kpi label="Resolved" value={fmtCount(data.portfolio.resolved)} />
                        <Kpi label="Still open" value={fmtCount(data.portfolio.open)} />
                        <Kpi label="Critical" value={fmtCount(data.portfolio.critical)} />
                    </section>

                    {data.clients.length === 0 ? (
                        <Card>
                            <CardContent className="p-8 text-center">
                                <h2 className="font-serif text-xl font-semibold">No clients yet</h2>
                                <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
                                    Request a seat for your first client. Once Needle activates it, their grievance
                                    numbers and your branded report appear here.
                                </p>
                                <Button className="mt-4" onClick={() => setShowForm(true)}><Plus aria-hidden="true" /> Request client seat</Button>
                            </CardContent>
                        </Card>
                    ) : (
                        <Card className="overflow-x-auto">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Client</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead className="text-right">Received</TableHead>
                                        <TableHead className="text-right">Resolved</TableHead>
                                        <TableHead className="text-right">Open</TableHead>
                                        <TableHead className="text-right">Critical</TableHead>
                                        <TableHead className="text-right">Avg. to resolve</TableHead>
                                        <TableHead><span className="sr-only">Open client</span></TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {data.clients.map((c) => {
                                        const s = c.summary;
                                        const st = SEAT_STATUS[c.status] || { label: c.status, variant: 'secondary' };
                                        return (
                                            <TableRow key={c.id}>
                                                <TableCell>
                                                    <div className="font-medium">{c.client_label}</div>
                                                    <div className="text-xs text-muted-foreground">
                                                        {[c.constituency, c.seat_type === 'mla' ? 'MLA' : 'MP'].filter(Boolean).join(' · ')}
                                                    </div>
                                                </TableCell>
                                                <TableCell><Badge variant={st.variant}>{st.label}</Badge></TableCell>
                                                <TableCell className="text-right tabular-nums">{fmtCount(s?.total)}</TableCell>
                                                <TableCell className="text-right tabular-nums">{fmtPct(s?.resolution_rate)}</TableCell>
                                                <TableCell className="text-right tabular-nums">{fmtCount(s?.open)}</TableCell>
                                                <TableCell className="text-right tabular-nums">{fmtCount(s?.critical)}</TableCell>
                                                <TableCell className="text-right tabular-nums">{fmtDays(s?.avg_resolution_days)}</TableCell>
                                                <TableCell className="text-right">
                                                    {c.status === 'active' ? (
                                                        <Link
                                                            href={`/partner/dashboard/clients/${c.id}`}
                                                            className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                                                            aria-label={`Open ${c.client_label}`}
                                                        >
                                                            Open <ArrowRight className="h-4 w-4" aria-hidden="true" />
                                                        </Link>
                                                    ) : null}
                                                </TableCell>
                                            </TableRow>
                                        );
                                    })}
                                </TableBody>
                            </Table>
                        </Card>
                    )}
                </>
            )}
        </div>
    );
}
