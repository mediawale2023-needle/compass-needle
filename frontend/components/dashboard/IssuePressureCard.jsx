'use client';

import { useEffect, useState } from 'react';
import { apiGet, apiPost } from '@/lib/api';
import { gen2, gen2Fonts } from '@/lib/briefcase-tokens';
import {
    LEGEND, QUADRANTS, changeLabel, draftHref, growthPct, headline, insight, isValidInsight,
    languagesLine, moves, newsCount, quadrantOf, verdict,
} from '@/lib/issueInsight';

// Staff Overview: Issue Pressure. Every issue placed on how widespread it is and how fast
// it is rising, then a brief per issue that a leader can act on.
const PERIODS = [30, 90];

function Spark({ values, color }) {
    const v = Array.isArray(values) && values.length > 1 ? values : [0, 0];
    const w = 90, h = 24, mx = Math.max(...v), mn = Math.min(...v);
    const x = (i) => 2 + (i * (w - 4)) / (v.length - 1);
    const y = (n) => h - 3 - ((n - mn) / (mx - mn || 1)) * (h - 6);
    const d = v.map((n, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(n).toFixed(1)}`).join('');
    return <svg className="ip-spark" width={w} height={h} aria-hidden="true"><path d={d} fill="none" stroke={color} strokeWidth="1.8" /></svg>;
}

function Matrix({ issues, selected, onSelect }) {
    const W = 520, H = 250, L = 36, R = 12, T = 14, B = 34;
    const xs = (i) => L + ((Math.min(i.locality_count || 0, 6) + 0.5) / 7) * (W - L - R);
    const gv = (i) => Math.max(-0.5, Math.min(2.5, i.previous ? (i.complaints - i.previous) / i.previous : (i.complaints >= 3 ? 1.5 : 0)));
    const ys = (i) => T + (1 - (gv(i) + 0.5) / 3) * (H - T - B);
    const midx = L + (3.5 / 7) * (W - L - R);
    const midy = T + (1 - (0.3 + 0.5) / 3) * (H - T - B);
    return (
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Issues by how widespread they are and how fast they are rising">
            <rect x={midx} y={T} width={W - R - midx} height={midy - T} fill="#F5E1D9" opacity=".55" />
            <line x1={L} x2={W - R} y1={midy} y2={midy} stroke={gen2.hairStrong} strokeDasharray="3 3" />
            <line x1={midx} x2={midx} y1={T} y2={H - B} stroke={gen2.hairStrong} strokeDasharray="3 3" />
            <text x={W - R - 6} y={T + 14} textAnchor="end" fontSize="10.5" fontWeight="600" fill={QUADRANTS.plank.color}>CAMPAIGN PLANK</text>
            <text x={L + 6} y={T + 14} fontSize="10.5" fontWeight="600" fill="#8A5D12">FLASHPOINT</text>
            <text x={W - R - 6} y={H - B - 8} textAnchor="end" fontSize="10.5" fontWeight="600" fill={QUADRANTS.chronic.color}>CHRONIC</text>
            <text x={L + 6} y={H - B - 8} fontSize="10.5" fontWeight="600" fill={QUADRANTS.watch.color}>WATCH</text>
            <text x={(L + W - R) / 2} y={H - 8} textAnchor="middle" fontSize="11" fill={gen2.muted}>How widespread → (localities affected)</text>
            <text transform={`translate(12 ${(T + H - B) / 2}) rotate(-90)`} textAnchor="middle" fontSize="11" fill={gen2.muted}>Rising faster →</text>
            {issues.map((i, k) => {
                const q = quadrantOf(i);
                const r = 6 + Math.sqrt(i.people || 0) * 3.2;
                const cx = xs(i), cy = ys(i), on = k === selected;
                const labelLeft = cx > W - 150;
                return (
                    <g key={i.issue} className="ip-bub" role="button" tabIndex={0} aria-label={`${i.issue}: ${QUADRANTS[q].label}`}
                        onClick={() => onSelect(k)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(k); } }}>
                        <circle cx={cx} cy={cy} r={r} fill={QUADRANTS[q].color} fillOpacity={on ? 0.95 : 0.7}
                            stroke={on ? gen2.ink : '#fff'} strokeWidth={on ? 2.5 : 1.5} />
                        <text x={labelLeft ? cx - r - 5 : cx + r + 5} y={cy + 4} textAnchor={labelLeft ? 'end' : 'start'}
                            fontSize="12" fontWeight={on ? 700 : 600} fill={gen2.ink}>{i.issue}</text>
                    </g>
                );
            })}
        </svg>
    );
}

export default function IssuePressureCard({ signals = null, onNavigate }) {
    const [days, setDays] = useState(90);
    const [data, setData] = useState(null);
    const [status, setStatus] = useState('loading');
    const [sel, setSel] = useState(0);
    const [note, setNote] = useState('');

    useEffect(() => {
        let cancelled = false;
        setStatus('loading');
        apiGet(`/api/dashboard/overview/issue-insight?days=${days}`)
            .then((res) => {
                if (cancelled) return;
                if (isValidInsight(res)) { setData(res); setStatus('ready'); setSel(0); setNote(''); }
                else setStatus('error');
            })
            .catch(() => { if (!cancelled) setStatus('error'); });
        return () => { cancelled = true; };
    }, [days]);

    const go = (href) => (typeof onNavigate === 'function' ? onNavigate(href) : undefined);
    const issues = data?.issues || [];
    const issue = issues[Math.min(sel, Math.max(issues.length - 1, 0))];
    const elected = data?.edition && data.edition !== 'aspirant';
    const role = elected ? 'elected' : 'aspirant';
    const read = headline(issues, days);

    async function planVisit(i) {
        const place = i.localities?.[0]?.name;
        if (!place) return;
        setNote('');
        const d = new Date();
        const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
        try {
            await apiPost('/api/dashboard/engagements', {
                entry_type: 'schedule', title: `Visit ${place} — ${i.issue}`, location: place, scheduled_for: today, is_all_day: true,
                notes: `${i.localities[0].complaints} ${i.issue} complaints from ${place}.`,
            });
            setNote(`Visit to ${place} added to today's schedule. Set the time there.`);
        } catch {
            setNote('Could not add the visit. Try again.');
        }
    }

    return (
        <section className="op-panel ip" aria-label="Issue Pressure">
            <div className="op-section-head">
                <div>
                    <h2>Issue Pressure</h2>
                    <p className="ip-sub">What people are complaining about — and what to do with it</p>
                </div>
                <div className="ip-seg" role="group" aria-label="Period">
                    {PERIODS.map((p) => (
                        <button key={p} type="button" aria-pressed={days === p} onClick={() => setDays(p)}>{p} days</button>
                    ))}
                </div>
            </div>
            {status === 'loading' && !data ? <p className="ip-empty">Loading…</p> : null}
            {status === 'error' ? <p className="ip-empty" role="alert">Issue Pressure could not be loaded.</p> : null}
            {status !== 'error' && data && !issues.length ? <p className="ip-empty">No complaints in the last {days} days.</p> : null}
            {status !== 'error' && issue ? (
                <>
                    {read ? (
                        <div className="ip-read">
                            <div className="ip-kick">The read</div>
                            <p>
                                <b>{read.lead}</b> {read.leadText}
                                {read.riser ? <> — and <em>{read.riser.name} is rising fastest</em>, {read.riser.from} → {read.riser.to} in {read.riser.days} days.</> : '.'}
                            </p>
                        </div>
                    ) : null}
                    <div className="ip-mx">
                        <Matrix issues={issues} selected={sel} onSelect={setSel} />
                        <div className="ip-legend">
                            {Object.keys(QUADRANTS).map((q) => (
                                <div key={q}><span className={`ip-q ${q}`}>{QUADRANTS[q].label}</span><b>{LEGEND[q].title}</b>{LEGEND[q][role]}</div>
                            ))}
                            <div className="ip-faint">Bubble size = people affected. Click a bubble or a tab.</div>
                        </div>
                    </div>
                    <div className="ip-tabs" role="tablist" aria-label="Issues">
                        {issues.map((i, k) => (
                            <button key={i.issue} type="button" role="tab" aria-selected={k === sel} onClick={() => setSel(k)}>
                                <span className="ip-tn">{i.issue}</span>
                                <span className="ip-ts">{QUADRANTS[quadrantOf(i)].label} · {i.complaints}</span>
                            </button>
                        ))}
                    </div>
                    <Brief issue={issue} days={days} elected={elected} news={newsCount(issue, signals)}
                        note={note} onDraft={() => go(draftHref(issue, elected, days))}
                        onVisit={() => planVisit(issue)}
                        onOpen={() => go(`/dashboard/sansadx?category=${encodeURIComponent(issue.issue)}`)} />
                </>
            ) : null}
            <style>{CSS}</style>
        </section>
    );
}

function Brief({ issue, days, elected, news, note, onDraft, onVisit, onOpen }) {
    const q = quadrantOf(issue);
    const g = growthPct(issue);
    const locs = issue.localities || [];
    const max = locs[0]?.complaints || 1;
    const place = locs[0]?.name;
    return (
        <div className="ip-brief" role="tabpanel" aria-label={issue.issue}>
            <div className="ip-bt">
                <div>
                    <span className={`ip-q ${q}`}>{QUADRANTS[q].label}</span><span className="ip-kick ip-qsub">{QUADRANTS[q].sub}</span>
                    <h3>{issue.issue}</h3>
                    <div className="ip-kick ip-verdict">{verdict(issue, elected)}</div>
                </div>
                <Spark values={issue.trend} color={QUADRANTS[q].color} />
            </div>
            <p className="ip-insight">{insight(issue, days, news)}</p>
            <div className="ip-facts">
                <div><strong>{issue.people}</strong><span>people affected</span></div>
                <div><strong>{issue.locality_count}</strong><span>localities</span></div>
                <div><strong className={g !== null && g > 0 ? 'red' : ''}>{changeLabel(issue)}</strong><span>vs previous {days} days</span></div>
                <div><strong className={issue.open_over_30_days ? 'red' : ''}>{issue.open_over_30_days}</strong><span>unresolved over 30 days</span></div>
                <div><strong>{news === null ? '—' : news}</strong><span>local news stories</span></div>
            </div>
            <div className="ip-two">
                <div>
                    <div className="ip-kick">Where it hurts</div>
                    {locs.length ? locs.slice(0, 5).map((l) => (
                        <div className="ip-loc" key={l.name}>
                            <span>{l.name}</span>
                            <span className="ip-bar" aria-hidden="true"><i style={{ width: `${(l.complaints / max) * 100}%` }} /></span>
                            <span className="ip-n">{l.complaints}</span>
                        </div>
                    )) : <p className="ip-faint">No mapped localities yet.</p>}
                    {issue.quotes?.length ? (
                        <>
                            <div className="ip-kick ip-gap">In their words</div>
                            {issue.quotes.map((qt) => (
                                <blockquote className="ip-voice" key={qt.text}>
                                    “{qt.text}”
                                    {qt.locality ? <small>{qt.locality} · {qt.locality_complaints} complaint{qt.locality_complaints === 1 ? '' : 's'}</small> : null}
                                </blockquote>
                            ))}
                        </>
                    ) : null}
                    {languagesLine(issue) ? <p className="ip-faint">Complaints came in: {languagesLine(issue)} — use these languages for outreach.</p> : null}
                </div>
                <div>
                    <div className="ip-kick">{elected ? 'What to do' : 'Campaign moves'}</div>
                    <ol className="ip-moves">
                        {moves(issue, elected).map(([b, d], k) => (
                            <li key={b}><span className="ip-mn">{k + 1}</span><span><b>{b}</b> — {d}</span></li>
                        ))}
                    </ol>
                </div>
            </div>
            {note ? <p className="ip-note" role="status">{note}</p> : null}
            <div className="ip-acts">
                <button type="button" className="ip-btn primary" onClick={onDraft}>{issue.department ? `Draft letter to ${issue.department}` : 'Draft a letter'}</button>
                {place ? <button type="button" className="ip-btn" onClick={onVisit}>Plan visit to {place}</button> : null}
                <button type="button" className="ip-btn" onClick={onOpen}>Open {issue.complaints} complaint{issue.complaints === 1 ? '' : 's'}</button>
            </div>
        </div>
    );
}

const CSS = `
    .ip { min-width: 0; max-width: 100%; }
    .ip .op-section-head { align-items: flex-start; }
    .ip-sub { margin: 4px 0 0; font-size: 12px; color: ${gen2.muted}; }
    .ip-seg { display: inline-flex; border: 1px solid ${gen2.hairStrong}; flex: none; }
    .ip-seg button { border: 0; background: none; padding: 4px 9px; font: 600 11.5px ${gen2Fonts.sans}; color: ${gen2.muted}; cursor: pointer; }
    .ip-seg button[aria-pressed=true] { background: ${gen2.ink}; color: #fff; }
    .ip-empty { padding: 12px 16px; margin: 0; color: ${gen2.muted}; font-size: 12.5px; }
    .ip-kick { font-family: ${gen2Fonts.mono}; font-size: 10px; letter-spacing: .12em; text-transform: uppercase; color: ${gen2.muted}; }
    .ip-read { padding: 14px 16px 4px; }
    .ip-read p { margin: 6px 0 0; font-family: ${gen2Fonts.serif}; font-size: 20px; line-height: 1.3; font-weight: 500; letter-spacing: -.01em; color: ${gen2.ink}; }
    .ip-read em { color: ${gen2.err}; font-style: italic; }
    .ip-mx { display: grid; grid-template-columns: minmax(0, 1fr) 200px; gap: 14px; padding: 8px 16px 14px; align-items: center; }
    .ip-mx svg { width: 100%; height: auto; display: block; font-family: ${gen2Fonts.sans}; }
    .ip-bub { cursor: pointer; }
    .ip-bub:focus { outline: none; }
    .ip-bub:focus-visible circle, .ip-bub:hover circle { stroke: ${gen2.ink}; stroke-width: 2; }
    .ip-legend { display: grid; gap: 9px; font-size: 12px; color: ${gen2.muted}; }
    .ip-legend b { display: block; color: ${gen2.ink}; font-size: 12.5px; margin-top: 3px; }
    .ip-faint { font-size: 12px; color: ${gen2.muted}; margin: 6px 0 0; }
    .ip-q { display: inline-block; font-family: ${gen2Fonts.mono}; font-size: 9.5px; letter-spacing: .05em; text-transform: uppercase; padding: 2px 6px; }
    .ip-q.plank { background: ${gen2.err}; color: #fff; }
    .ip-q.flash { background: #F4E7C9; color: #8A5D12; }
    .ip-q.chronic { background: #E2E8EA; color: #45667C; }
    .ip-q.watch { background: #ECEAE4; color: #5F5A50; }
    .ip-tabs { display: flex; border-top: 1px solid ${gen2.hair}; border-bottom: 1px solid ${gen2.hair}; overflow-x: auto; }
    .ip-tabs button { border: 0; border-right: 1px solid ${gen2.hair}; background: none; padding: 10px 14px; text-align: left; cursor: pointer; min-width: 150px; font: inherit; color: inherit; }
    .ip-tabs button[aria-selected=true] { background: ${gen2.surfaceWarm}; box-shadow: inset 0 -2px 0 ${gen2.ink}; }
    .ip-tabs button:focus-visible { outline: 2px solid ${gen2.green}; outline-offset: -2px; }
    .ip-tn { display: block; font-weight: 600; font-size: 13px; white-space: nowrap; color: ${gen2.ink}; }
    .ip-ts { display: block; font-size: 11.5px; color: ${gen2.muted}; white-space: nowrap; }
    .ip-brief { padding: 16px; }
    .ip-bt { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
    .ip-qsub { margin-left: 8px; }
    .ip-bt h3 { font-family: ${gen2Fonts.serif}; font-size: 22px; font-weight: 650; margin: 6px 0 2px; color: ${gen2.ink}; letter-spacing: -.02em; }
    .ip-verdict { color: ${gen2.ink}; }
    .ip-spark { flex: none; }
    .ip-insight { font-size: 14px; line-height: 1.5; color: #3B372F; margin: 8px 0 14px; max-width: 680px; }
    .ip-facts { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); border: 1px solid ${gen2.hair}; margin-bottom: 14px; }
    .ip-facts div { padding: 10px 12px; border-left: 1px solid ${gen2.hair}; }
    .ip-facts div:first-child { border-left: 0; }
    .ip-facts strong { display: block; font-family: ${gen2Fonts.serif}; font-size: 22px; line-height: 1.1; font-weight: 650; color: ${gen2.ink}; font-variant-numeric: tabular-nums; }
    .ip-facts strong.red { color: ${gen2.err}; }
    .ip-facts span { font-size: 11.5px; color: ${gen2.muted}; }
    .ip-two { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 18px; }
    .ip-gap { margin-top: 14px; }
    .ip-loc { display: grid; grid-template-columns: minmax(0, 130px) 1fr 26px; gap: 8px; align-items: center; font-size: 12.5px; margin-top: 6px; color: ${gen2.ink}; }
    .ip-bar { height: 7px; background: ${gen2.hair}; border-radius: 4px; overflow: hidden; }
    .ip-bar i { display: block; height: 100%; background: ${gen2.err}; }
    .ip-n { text-align: right; font-variant-numeric: tabular-nums; }
    .ip-voice { border-left: 3px solid ${gen2.hairStrong}; padding: 3px 0 3px 12px; margin: 6px 0; font-family: ${gen2Fonts.serif}; font-style: italic; font-size: 15px; line-height: 1.4; color: #3B372F; }
    .ip-voice small { display: block; font-family: ${gen2Fonts.mono}; font-style: normal; font-size: 10.5px; letter-spacing: .06em; text-transform: uppercase; color: ${gen2.muted}; margin-top: 2px; }
    .ip-moves { list-style: none; margin: 6px 0 0; padding: 0; display: grid; gap: 8px; }
    .ip-moves li { display: grid; grid-template-columns: 22px 1fr; gap: 8px; font-size: 13px; line-height: 1.45; color: #3B372F; }
    .ip-moves b { color: ${gen2.ink}; }
    .ip-mn { width: 20px; height: 20px; border-radius: 50%; background: ${gen2.ink}; color: #fff; display: grid; place-items: center; font-size: 11px; font-weight: 600; }
    .ip-note { margin: 12px 0 0; font-size: 12.5px; color: ${gen2.green}; }
    .ip-acts { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 16px; padding-top: 14px; border-top: 1px solid ${gen2.hair}; }
    .ip-btn { border: 1px solid ${gen2.hairStrong}; background: ${gen2.surface}; padding: 6px 12px; font: 600 12.5px ${gen2Fonts.sans}; cursor: pointer; color: ${gen2.ink}; }
    .ip-btn:hover { background: ${gen2.surfaceWarm}; }
    .ip-btn.primary { background: ${gen2.green}; border-color: ${gen2.green}; color: #fff; }
    .ip-btn.primary:hover { background: ${gen2.greenDeep}; }
    .ip-btn:focus-visible { outline: 2px solid ${gen2.green}; outline-offset: 2px; }
    @media (max-width: 760px) {
        .ip-mx { grid-template-columns: minmax(0, 1fr); }
        .ip-facts { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .ip-facts div { border-left: 0; border-top: 1px solid ${gen2.hair}; }
        .ip-facts div:nth-child(-n+2) { border-top: 0; }
        .ip-facts div:nth-child(even) { border-left: 1px solid ${gen2.hair}; }
        .ip-facts div:last-child { grid-column: 1 / -1; border-left: 0; }
        .ip-two { grid-template-columns: minmax(0, 1fr); }
        .ip-read p { font-size: 17px; }
        .ip .op-section-head { flex-wrap: wrap; }
    }
`;
