'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet } from '@/lib/api';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
    Loader2, FileQuestion, MessageSquare, ScrollText, Clock,
    AlertTriangle, ChevronLeft, ChevronRight, ExternalLink,
    PenTool, RefreshCw, Building2,
} from 'lucide-react';

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmtDate(d) {
    if (!d) return '—';
    try {
        return new Date(d).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
    } catch { return d; }
}

function fmtSession(s) {
    if (!s) return '—';
    return s.replace(/\(Part\s+/i, '(Pt. ');
}

const Q_TYPE_COLORS = {
    starred:      'bg-amber-100 text-amber-700',
    unstarred:    'bg-blue-100 text-blue-700',
    short_notice: 'bg-purple-100 text-purple-700',
};

const PMB_STATUS_COLORS = {
    introduced: 'bg-blue-100 text-blue-700',
    lapsed:     'bg-slate-100 text-slate-500',
    withdrawn:  'bg-orange-100 text-orange-700',
    passed:     'bg-emerald-100 text-emerald-700',
};

function EmptyState({ icon: Icon, label, action }) {
    return (
        <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
            <div className="h-14 w-14 rounded-full bg-muted flex items-center justify-center">
                <Icon className="h-6 w-6 text-muted-foreground/50" />
            </div>
            <div>
                <p className="text-sm font-medium text-foreground">{label}</p>
                <p className="text-xs text-muted-foreground mt-1">
                    No records synced yet. Ask your admin to run the parliament backfill.
                </p>
            </div>
            {action}
        </div>
    );
}

function Pager({ page, pages, onPage }) {
    if (pages <= 1) return null;
    return (
        <div className="flex items-center justify-between pt-3 border-t border-border">
            <span className="text-xs text-muted-foreground">Page {page} of {pages}</span>
            <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
                    <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
                    <ChevronRight className="h-4 w-4" />
                </Button>
            </div>
        </div>
    );
}

// ── Overview tab ──────────────────────────────────────────────────────────────

function OverviewTab({ record }) {
    if (!record) return (
        <div className="space-y-3 py-6">
            {[1, 2, 3].map(i => <Skeleton key={i} className="h-24 w-full rounded-xl" />)}
        </div>
    );

    const { totals, sessions, all_sessions, sync_status, last_synced, house } = record;
    const hasData = Object.values(totals).some(v => v > 0);

    const STAT_CARDS = [
        {
            key: 'questions',
            label: 'Parliamentary Questions',
            icon: FileQuestion,
            count: totals.questions,
            color: 'text-blue-600',
            bg: 'bg-blue-50',
            tab: 'questions',
        },
        {
            key: 'debates',
            label: 'Debate Speeches',
            icon: MessageSquare,
            count: totals.debates,
            color: 'text-purple-600',
            bg: 'bg-purple-50',
            tab: 'debates',
        },
        {
            key: 'pmbs',
            label: "Private Members' Bills",
            icon: ScrollText,
            count: totals.pmbs,
            color: 'text-amber-600',
            bg: 'bg-amber-50',
            tab: 'pmbs',
        },
        {
            key: 'zero_hour',
            label: 'Zero Hour / Special Mentions',
            icon: Clock,
            count: totals.zero_hour,
            color: 'text-emerald-600',
            bg: 'bg-emerald-50',
            tab: 'zero_hour',
        },
    ];

    return (
        <div className="space-y-6">
            {/* Sync Status */}
            <Card className={cn(
                'border-l-4',
                sync_status === 'active'    && 'border-l-emerald-500 bg-emerald-50/30',
                sync_status === 'pending'   && 'border-l-amber-400',
                sync_status === 'error'     && 'border-l-destructive bg-destructive/5',
                sync_status === 'unmatched' && 'border-l-slate-300',
                !sync_status               && 'border-l-muted',
            )}>
                <CardContent className="py-3">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                        <div className="flex items-center gap-2">
                            <span className={cn(
                                'inline-block h-2 w-2 rounded-full',
                                sync_status === 'active'    && 'bg-emerald-500',
                                sync_status === 'pending'   && 'bg-amber-400',
                                sync_status === 'error'     && 'bg-destructive',
                                sync_status === 'unmatched' && 'bg-slate-400',
                                !sync_status               && 'bg-muted-foreground/40',
                            )} />
                            <span className="text-sm font-medium text-foreground capitalize">
                                Parliament Sync: {sync_status || 'Not configured'}
                            </span>
                            {house && (
                                <Badge variant="secondary" className="text-[10px] capitalize">
                                    {house.replace('_', ' ')}
                                </Badge>
                            )}
                        </div>
                        {last_synced && (
                            <span className="text-xs text-muted-foreground">
                                Last synced {fmtDate(last_synced)}
                            </span>
                        )}
                    </div>
                    {sync_status === 'unmatched' && (
                        <p className="text-xs text-muted-foreground mt-1">
                            MP identity not matched yet. Contact your admin to complete Parliament Sync setup.
                        </p>
                    )}
                    {sync_status === 'pending' && (
                        <p className="text-xs text-muted-foreground mt-1">
                            Parliament data backfill not started. Contact your admin to enable data sync.
                        </p>
                    )}
                </CardContent>
            </Card>

            {/* Summary cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {STAT_CARDS.map(({ key, label, icon: Icon, count, color, bg }) => (
                    <Card key={key} className="relative overflow-hidden">
                        <CardContent className="p-5">
                            <div className={cn('h-10 w-10 rounded-lg flex items-center justify-center mb-3', bg)}>
                                <Icon className={cn('h-5 w-5', color)} />
                            </div>
                            <p className="text-3xl font-bold text-foreground">{count}</p>
                            <p className="text-xs text-muted-foreground mt-1 leading-snug">{label}</p>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {hasData ? (
                /* Session breakdown table */
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Session Breakdown</CardTitle>
                        <CardDescription>Activity per parliamentary session</CardDescription>
                    </CardHeader>
                    <CardContent className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-border">
                                    <th className="text-left text-xs font-medium text-muted-foreground pb-2 pr-4">Session</th>
                                    <th className="text-right text-xs font-medium text-muted-foreground pb-2 px-3">Questions</th>
                                    <th className="text-right text-xs font-medium text-muted-foreground pb-2 px-3">Debates</th>
                                    <th className="text-right text-xs font-medium text-muted-foreground pb-2 px-3">PMBs</th>
                                    <th className="text-right text-xs font-medium text-muted-foreground pb-2 pl-3">Zero Hour</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-border">
                                {all_sessions.map(sess => {
                                    const qCount  = sessions.questions.find(s => s.session === sess)?.count || 0;
                                    const dCount  = sessions.debates.find(s => s.session === sess)?.count || 0;
                                    const pCount  = sessions.pmbs.find(s => s.session === sess)?.count || 0;
                                    const zCount  = sessions.zero_hour.find(s => s.session === sess)?.count || 0;
                                    return (
                                        <tr key={sess} className="hover:bg-accent/30 transition-colors">
                                            <td className="py-2.5 pr-4 font-medium text-foreground">{fmtSession(sess)}</td>
                                            <td className="py-2.5 px-3 text-right tabular-nums">{qCount || '—'}</td>
                                            <td className="py-2.5 px-3 text-right tabular-nums">{dCount || '—'}</td>
                                            <td className="py-2.5 px-3 text-right tabular-nums">{pCount || '—'}</td>
                                            <td className="py-2.5 pl-3 text-right tabular-nums">{zCount || '—'}</td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </CardContent>
                </Card>
            ) : (
                <EmptyState
                    icon={Building2}
                    label="No parliamentary data available yet"
                    action={
                        <Button variant="outline" size="sm" asChild>
                            <Link href="/dashboard/drafter?mode=question">
                                <PenTool className="h-4 w-4 mr-2" />
                                Draft a Parliamentary Question
                            </Link>
                        </Button>
                    }
                />
            )}
        </div>
    );
}

// ── Questions tab ──────────────────────────────────────────────────────────────

function QuestionsTab({ sessions }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [session, setSession] = useState('');
    const [page, setPage] = useState(1);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams({ page: String(page), limit: '20' });
            if (session) params.set('session', session);
            const d = await apiGet(`/api/parliament/questions?${params}`);
            setData(d);
        } catch { setData(null); }
        finally { setLoading(false); }
    }, [session, page]);

    useEffect(() => { load(); }, [load]);
    useEffect(() => { setPage(1); }, [session]);

    const questions = data?.questions || [];
    const total = data?.total || 0;

    return (
        <div className="space-y-4">
            <div className="flex items-center gap-3 flex-wrap">
                <select
                    className="text-sm border rounded-lg px-3 py-1.5 bg-background"
                    value={session}
                    onChange={e => setSession(e.target.value)}
                >
                    <option value="">All Sessions</option>
                    {sessions.map(s => <option key={s} value={s}>{fmtSession(s)}</option>)}
                </select>
                <span className="text-xs text-muted-foreground">{total} question{total !== 1 ? 's' : ''}</span>
                <Button variant="ghost" size="sm" onClick={load} className="h-8 ml-auto gap-1.5 text-muted-foreground">
                    <RefreshCw className="h-3.5 w-3.5" />
                    Refresh
                </Button>
            </div>

            {loading ? (
                <div className="space-y-3">{[1,2,3,4,5].map(i => <Skeleton key={i} className="h-20 w-full rounded-xl" />)}</div>
            ) : questions.length === 0 ? (
                <EmptyState
                    icon={FileQuestion}
                    label="No questions on record"
                    action={
                        <Button variant="outline" size="sm" asChild>
                            <Link href="/dashboard/drafter?mode=question">
                                <PenTool className="h-4 w-4 mr-2" />
                                Draft a Parliamentary Question
                            </Link>
                        </Button>
                    }
                />
            ) : (
                <>
                    <div className="divide-y divide-border border rounded-xl overflow-hidden">
                        {questions.map(q => (
                            <div key={q.id} className="p-4 hover:bg-accent/30 transition-colors">
                                <div className="flex items-start justify-between gap-3 flex-wrap">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 flex-wrap mb-1">
                                            <Badge variant="secondary" className={cn('text-[10px]', Q_TYPE_COLORS[q.question_type] || 'bg-slate-100 text-slate-600')}>
                                                {(q.question_type || 'unstarred').replace('_', ' ')}
                                            </Badge>
                                            {q.question_number && (
                                                <span className="text-xs font-mono text-muted-foreground">#{q.question_number}</span>
                                            )}
                                            <span className="text-xs text-muted-foreground">{fmtSession(q.session_name)}</span>
                                        </div>
                                        <p className="text-sm font-medium text-foreground leading-snug line-clamp-2">
                                            {q.subject || 'No subject on record'}
                                        </p>
                                        {q.ministry && (
                                            <p className="text-xs text-muted-foreground mt-1">{q.ministry}</p>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0">
                                        {q.answer_text && (
                                            <Badge variant="secondary" className="bg-emerald-100 text-emerald-700 text-[10px]">
                                                Answer Available
                                            </Badge>
                                        )}
                                        <span className="text-xs text-muted-foreground">{fmtDate(q.date_asked)}</span>
                                    </div>
                                </div>
                                {q.answer_text && (
                                    <details className="mt-2">
                                        <summary className="text-xs text-primary cursor-pointer hover:underline">
                                            View Answer
                                        </summary>
                                        <p className="text-xs text-muted-foreground mt-1.5 leading-relaxed whitespace-pre-wrap line-clamp-6">
                                            {q.answer_text}
                                        </p>
                                    </details>
                                )}
                            </div>
                        ))}
                    </div>
                    <Pager page={page} pages={data?.pages || 1} onPage={setPage} />
                </>
            )}
        </div>
    );
}

// ── Debates tab ────────────────────────────────────────────────────────────────

function DebatesTab({ sessions }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [session, setSession] = useState('');
    const [page, setPage] = useState(1);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams({ page: String(page), limit: '20' });
            if (session) params.set('session', session);
            const d = await apiGet(`/api/parliament/debates?${params}`);
            setData(d);
        } catch { setData(null); }
        finally { setLoading(false); }
    }, [session, page]);

    useEffect(() => { load(); }, [load]);
    useEffect(() => { setPage(1); }, [session]);

    const debates = data?.debates || [];
    const total = data?.total || 0;

    return (
        <div className="space-y-4">
            <div className="flex items-center gap-3 flex-wrap">
                <select
                    className="text-sm border rounded-lg px-3 py-1.5 bg-background"
                    value={session}
                    onChange={e => setSession(e.target.value)}
                >
                    <option value="">All Sessions</option>
                    {sessions.map(s => <option key={s} value={s}>{fmtSession(s)}</option>)}
                </select>
                <span className="text-xs text-muted-foreground">{total} speech{total !== 1 ? 'es' : ''}</span>
                <Button variant="ghost" size="sm" onClick={load} className="h-8 ml-auto gap-1.5 text-muted-foreground">
                    <RefreshCw className="h-3.5 w-3.5" />
                    Refresh
                </Button>
            </div>

            {loading ? (
                <div className="space-y-3">{[1,2,3,4,5].map(i => <Skeleton key={i} className="h-20 w-full rounded-xl" />)}</div>
            ) : debates.length === 0 ? (
                <EmptyState icon={MessageSquare} label="No debate speeches on record" />
            ) : (
                <>
                    <div className="divide-y divide-border border rounded-xl overflow-hidden">
                        {debates.map(d => (
                            <div key={d.id} className="p-4 hover:bg-accent/30 transition-colors">
                                <div className="flex items-start justify-between gap-3 flex-wrap">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 flex-wrap mb-1">
                                            <span className="text-xs text-muted-foreground">{fmtSession(d.session_name)}</span>
                                            {d.bill_reference && (
                                                <Badge variant="secondary" className="text-[10px] bg-purple-100 text-purple-700">
                                                    {d.bill_reference}
                                                </Badge>
                                            )}
                                        </div>
                                        <p className="text-sm font-medium text-foreground leading-snug line-clamp-2">
                                            {d.topic || 'General Debate'}
                                        </p>
                                        {d.speech_excerpt && (
                                            <p className="text-xs text-muted-foreground mt-1.5 leading-relaxed line-clamp-3">
                                                {d.speech_excerpt}
                                            </p>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0">
                                        {d.full_speech_url && (
                                            <a
                                                href={d.full_speech_url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-xs text-primary hover:underline flex items-center gap-1"
                                            >
                                                Full Speech <ExternalLink className="h-3 w-3" />
                                            </a>
                                        )}
                                        <span className="text-xs text-muted-foreground">{fmtDate(d.date)}</span>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                    <Pager page={page} pages={data?.pages || 1} onPage={setPage} />
                </>
            )}
        </div>
    );
}

// ── PMBs tab ───────────────────────────────────────────────────────────────────

function PMBsTab({ sessions }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [session, setSession] = useState('');

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (session) params.set('session', session);
            const d = await apiGet(`/api/parliament/pmbs?${params}`);
            setData(d);
        } catch { setData(null); }
        finally { setLoading(false); }
    }, [session]);

    useEffect(() => { load(); }, [load]);

    const pmbs = data?.pmbs || [];
    const total = data?.total || 0;

    return (
        <div className="space-y-4">
            <div className="flex items-center gap-3 flex-wrap">
                <select
                    className="text-sm border rounded-lg px-3 py-1.5 bg-background"
                    value={session}
                    onChange={e => setSession(e.target.value)}
                >
                    <option value="">All Sessions</option>
                    {sessions.map(s => <option key={s} value={s}>{fmtSession(s)}</option>)}
                </select>
                <span className="text-xs text-muted-foreground">{total} bill{total !== 1 ? 's' : ''}</span>
                <Button variant="ghost" size="sm" onClick={load} className="h-8 ml-auto gap-1.5 text-muted-foreground">
                    <RefreshCw className="h-3.5 w-3.5" />
                    Refresh
                </Button>
            </div>

            {loading ? (
                <div className="space-y-3">{[1,2,3].map(i => <Skeleton key={i} className="h-28 w-full rounded-xl" />)}</div>
            ) : pmbs.length === 0 ? (
                <EmptyState icon={ScrollText} label="No Private Members' Bills on record" />
            ) : (
                <div className="divide-y divide-border border rounded-xl overflow-hidden">
                    {pmbs.map(b => (
                        <div key={b.id} className="p-4 hover:bg-accent/30 transition-colors">
                            <div className="flex items-start justify-between gap-3 flex-wrap">
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 flex-wrap mb-1">
                                        <Badge variant="secondary" className={cn('text-[10px]', PMB_STATUS_COLORS[b.current_status] || 'bg-slate-100 text-slate-600')}>
                                            {b.current_status || 'introduced'}
                                        </Badge>
                                        <span className="text-xs font-mono text-muted-foreground">{b.bill_number}</span>
                                        <span className="text-xs text-muted-foreground">{fmtSession(b.session_name)}</span>
                                    </div>
                                    <p className="text-sm font-medium text-foreground leading-snug">
                                        {b.title || 'Untitled Bill'}
                                    </p>
                                    {b.subject && (
                                        <p className="text-xs text-muted-foreground mt-1 line-clamp-2 leading-relaxed">
                                            {b.subject}
                                        </p>
                                    )}
                                </div>
                                <div className="flex items-center gap-2 shrink-0">
                                    {b.bill_text_url && (
                                        <a
                                            href={b.bill_text_url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="text-xs text-primary hover:underline flex items-center gap-1"
                                        >
                                            View Bill <ExternalLink className="h-3 w-3" />
                                        </a>
                                    )}
                                    <span className="text-xs text-muted-foreground">{fmtDate(b.date_introduced)}</span>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

// ── Zero Hour tab ──────────────────────────────────────────────────────────────

function ZeroHourTab({ sessions }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [session, setSession] = useState('');
    const [page, setPage] = useState(1);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams({ page: String(page), limit: '20' });
            if (session) params.set('session', session);
            const d = await apiGet(`/api/parliament/zero-hour?${params}`);
            setData(d);
        } catch { setData(null); }
        finally { setLoading(false); }
    }, [session, page]);

    useEffect(() => { load(); }, [load]);
    useEffect(() => { setPage(1); }, [session]);

    const submissions = data?.submissions || [];
    const total = data?.total || 0;

    return (
        <div className="space-y-4">
            <div className="flex items-center gap-3 flex-wrap">
                <select
                    className="text-sm border rounded-lg px-3 py-1.5 bg-background"
                    value={session}
                    onChange={e => setSession(e.target.value)}
                >
                    <option value="">All Sessions</option>
                    {sessions.map(s => <option key={s} value={s}>{fmtSession(s)}</option>)}
                </select>
                <span className="text-xs text-muted-foreground">{total} submission{total !== 1 ? 's' : ''}</span>
                <Button variant="ghost" size="sm" onClick={load} className="h-8 ml-auto gap-1.5 text-muted-foreground">
                    <RefreshCw className="h-3.5 w-3.5" />
                    Refresh
                </Button>
            </div>

            {loading ? (
                <div className="space-y-3">{[1,2,3,4,5].map(i => <Skeleton key={i} className="h-16 w-full rounded-xl" />)}</div>
            ) : submissions.length === 0 ? (
                <EmptyState icon={Clock} label="No Zero Hour submissions on record" />
            ) : (
                <>
                    <div className="divide-y divide-border border rounded-xl overflow-hidden">
                        {submissions.map(s => (
                            <div key={s.id} className="p-4 hover:bg-accent/30 transition-colors">
                                <div className="flex items-start justify-between gap-3 flex-wrap">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 flex-wrap mb-1">
                                            <span className="text-xs text-muted-foreground">{fmtSession(s.session_name)}</span>
                                            <span className="text-xs text-muted-foreground">{fmtDate(s.date)}</span>
                                        </div>
                                        <p className="text-sm font-medium text-foreground leading-snug">
                                            {s.subject || 'Zero Hour Submission'}
                                        </p>
                                        {s.text_excerpt && (
                                            <p className="text-xs text-muted-foreground mt-1 line-clamp-2 leading-relaxed">
                                                {s.text_excerpt}
                                            </p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                    <Pager page={page} pages={data?.pages || 1} onPage={setPage} />
                </>
            )}
        </div>
    );
}

// ── Page ───────────────────────────────────────────────────────────────────────

const TABS = [
    { key: 'overview',   label: 'Overview',          icon: Building2 },
    { key: 'questions',  label: 'Questions',          icon: FileQuestion },
    { key: 'debates',    label: 'Debates',            icon: MessageSquare },
    { key: 'pmbs',       label: "Members' Bills",     icon: ScrollText },
    { key: 'zero_hour',  label: 'Zero Hour',          icon: Clock },
];

export default function ParliamentPage() {
    const { user } = useAuth();
    const [record, setRecord] = useState(null);
    const [recordLoading, setRecordLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('overview');

    const color = user?.theme_color || '#006a4d';

    useEffect(() => {
        setRecordLoading(true);
        apiGet('/api/parliament/my-record')
            .then(d => setRecord(d))
            .catch(() => setRecord(null))
            .finally(() => setRecordLoading(false));
    }, []);

    const sessions = record?.all_sessions || [];

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                    <h1 className="text-2xl font-bold text-foreground">Parliamentary Record</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Your questions, debates, bills, and zero-hour submissions across all sessions.
                    </p>
                </div>
                <Button variant="outline" size="sm" asChild>
                    <Link href="/dashboard/drafter?mode=question">
                        <PenTool className="h-4 w-4 mr-2" />
                        Draft a Question
                    </Link>
                </Button>
            </div>

            {/* Tab navigation */}
            <div className="border-b border-border">
                <nav className="flex gap-1 overflow-x-auto">
                    {TABS.map(({ key, label, icon: Icon }) => {
                        const count = key !== 'overview' ? record?.totals?.[key] : null;
                        return (
                            <button
                                key={key}
                                onClick={() => setActiveTab(key)}
                                className={cn(
                                    'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap',
                                    activeTab === key
                                        ? 'border-primary text-foreground'
                                        : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
                                )}
                                style={activeTab === key ? { borderColor: color, color } : {}}
                            >
                                <Icon className="h-4 w-4 shrink-0" />
                                {label}
                                {count != null && count > 0 && (
                                    <Badge variant="secondary" className="text-[10px] h-4 px-1 min-w-4">
                                        {count}
                                    </Badge>
                                )}
                            </button>
                        );
                    })}
                </nav>
            </div>

            {/* Tab content */}
            <div>
                {activeTab === 'overview' && (
                    recordLoading
                        ? <div className="space-y-3 py-4">{[1,2,3].map(i => <Skeleton key={i} className="h-24 rounded-xl" />)}</div>
                        : <OverviewTab record={record} />
                )}
                {activeTab === 'questions' && <QuestionsTab sessions={sessions} />}
                {activeTab === 'debates'   && <DebatesTab sessions={sessions} />}
                {activeTab === 'pmbs'      && <PMBsTab sessions={sessions} />}
                {activeTab === 'zero_hour' && <ZeroHourTab sessions={sessions} />}
            </div>
        </div>
    );
}
