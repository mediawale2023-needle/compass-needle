// Issue Pressure (staff Overview): turns /api/dashboard/overview/issue-insight rows into the
// headline, the verdict, the one-paragraph read and the suggested moves. Moves are fixed
// template rules filled with the office's own numbers — not AI-written.

export const QUADRANTS = {
    plank: { label: 'Campaign plank', sub: 'Widespread and rising', color: '#A33A32' },
    flash: { label: 'Flashpoint', sub: 'Rising fast in a few places', color: '#B98118' },
    chronic: { label: 'Chronic', sub: 'Widespread but steady', color: '#45667C' },
    watch: { label: 'Watch', sub: 'Small and steady', color: '#8A8270' },
};

export const LEGEND = {
    plank: { title: 'Widespread and rising.', aspirant: 'Own it publicly.', elected: 'Fix it visibly, fast.' },
    flash: { title: 'Rising fast in a few places.', aspirant: 'Be on the ground first.', elected: 'Contain it locally.' },
    chronic: { title: 'Widespread, steady.', aspirant: 'A promise with a date.', elected: 'Show steady delivery.' },
    watch: { title: 'Small, steady.', aspirant: 'Resolve quietly.', elected: 'Resolve quietly.' },
};

export function quadrantOf(issue) {
    return QUADRANTS[issue?.quadrant] ? issue.quadrant : 'watch';
}

export function growthPct(issue) {
    if (!issue || !issue.previous) return null;
    return Math.round(((issue.complaints - issue.previous) / issue.previous) * 100);
}

/** "+68%" on a real base; "2 → 9" when the previous count is too small for a percentage. */
export function changeLabel(issue) {
    if (!issue) return '';
    if (!issue.previous) return issue.complaints ? 'new' : '—';
    if (issue.previous < 5) return `${issue.previous} → ${issue.complaints}`;
    const g = growthPct(issue);
    return `${g > 0 ? '+' : ''}${g}%`;
}

const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
const lower = (s) => String(s || '').toLowerCase();
const joinTwo = (names) => names.filter(Boolean).slice(0, 2).join(' and ');

export function headline(issues, days) {
    const list = Array.isArray(issues) ? issues : [];
    const plank = list.find((i) => i.quadrant === 'plank');
    const riser = list
        .filter((i) => i.quadrant === 'flash' || i.quadrant === 'plank')
        .filter((i) => i !== plank)
        .sort((a, b) => (b.complaints - b.previous) - (a.complaints - a.previous))[0];
    const top = plank || list[0];
    if (!top) return null;
    return {
        lead: top.issue,
        leadText: plank ? 'is the issue that unites the constituency' : 'is what people raise most',
        riser: riser ? { name: lower(riser.issue), from: riser.previous, to: riser.complaints, days } : null,
    };
}

export function verdict(issue, elected) {
    const q = quadrantOf(issue);
    return {
        plank: elected ? 'Fix this before it becomes the story' : 'Own this issue',
        flash: elected ? 'Contain it locally, fast' : 'Be first on the ground',
        chronic: elected ? 'Show steady delivery on it' : 'Make it your long-term promise',
        watch: 'Keep watching',
    }[q];
}

function deptLine(issue) {
    if (!issue.department) return issue.filed ? `${plural(issue.filed, 'filing')} with government` : 'nothing filed with government yet';
    return `${issue.department}: ${issue.filed_resolved} of ${plural(issue.filed, 'filing')} resolved`;
}

/** One paragraph: the facts that make this issue matter, in the order a consultant would say them. */
export function insight(issue, days, news) {
    const q = quadrantOf(issue);
    const locs = (issue.localities || []).map((l) => l.name);
    const g = growthPct(issue);
    const newsBit = news ? ` Local papers have carried it ${news === 1 ? 'once' : `${news} times`}.` : '';
    const stale = issue.open_over_30_days
        ? ` ${plural(issue.open_over_30_days, 'complaint has', 'complaints have')} waited over a month.`
        : '';
    if (q === 'plank') {
        return `${plural(issue.complaints, 'complaint')} from ${plural(issue.people, 'person', 'people')} in ${plural(issue.locality_count, 'locality', 'localities')}`
            + `${g !== null ? `, ${g >= 0 ? 'up' : 'down'} ${Math.abs(g)}% on the previous ${days} days` : ''}.${stale} ${deptLine(issue)}.${newsBit}`;
    }
    if (q === 'flash') {
        return `Went from ${issue.previous} to ${issue.complaints} complaints in ${days} days${locs.length ? `, mostly in ${joinTwo(locs)}` : ''}.${newsBit} ${deptLine(issue)}.`;
    }
    if (q === 'chronic') {
        return `${plural(issue.complaints, 'complaint')} across ${plural(issue.locality_count, 'locality', 'localities')}, roughly flat.`
            + `${issue.oldest_open_days ? ` The oldest open one is ${issue.oldest_open_days} days old.` : ''} People have stopped expecting a fix, so a real one stands out.`;
    }
    return `${plural(issue.complaints, 'complaint')}${locs[0] ? `, mostly from ${locs[0]}` : ''}. Not a campaign issue yet.${stale}`;
}

/** Up to three moves: [bold lead, rest of the sentence]. */
export function moves(issue, elected) {
    const q = quadrantOf(issue);
    const top = issue.localities?.[0];
    const where = top ? top.name : 'the worst-hit locality';
    const share = top && issue.complaints ? Math.round((top.complaints / issue.complaints) * 100) : null;
    const dept = issue.department || 'the department';
    const open = issue.open_over_30_days || 0;
    const name = lower(issue.issue);
    if (q === 'plank') {
        return elected ? [
            [`Site visit with ${dept} in ${where}`, 'and announce a date for the fix.'],
            [open ? `Clear the ${plural(open, 'oldest complaint')}` : 'Close every open complaint', 'and tell each person when it is done.'],
            ['Report back in 30 days', 'at the same place, with before and after.'],
        ] : [
            [`Public hearing in ${where}`, share !== null ? `${share}% of these complaints come from there.` : 'make it the stage.'],
            [`Written demand to ${dept}`, open ? `listing the ${plural(open, 'complaint')} unresolved for over a month; share it with the press.` : 'with the complaints and their ages; share it with the press.'],
            [`RTI on the ${name} budget`, 'for the constituency — the answer becomes the next story.'],
        ];
    }
    if (q === 'flash') {
        return elected ? [
            [`Call ${dept} today`, `ask for visible action in ${where}.`],
            [`Reply to all ${plural(issue.complaints, 'complainant')}`, 'within 48 hours with what was done.'],
            ['Put out a statement', 'before it becomes an opposition talking point.'],
        ] : [
            [`Visit ${where} this week`, 'with the people who complained — be the first public face on it.'],
            [`Meet ${dept}`, 'and share what you were told with the residents.'],
            ['Local press note', issue.languages?.[0] ? `in ${issue.languages[0].name}.` : 'in the language people wrote in.'],
        ];
    }
    if (q === 'chronic') {
        const two = joinTwo((issue.localities || []).map((l) => l.name));
        return [
            ['Make it a promise with a date', two ? `specific to ${two}.` : 'specific to the worst-hit localities.'],
            ['Track it publicly', 'a monthly count of open complaints.'],
            ['Close the oldest first', issue.oldest_open_days ? `the ${issue.oldest_open_days}-day case is the one people remember.` : 'old cases are the ones people remember.'],
        ];
    }
    return [['Resolve the open ones', 'and tell the people affected.']];
}

export function languagesLine(issue) {
    const langs = issue?.languages || [];
    if (!langs.length) return '';
    return langs.map((l) => `${l.name} ${l.share}%`).join(' · ');
}

/** Local news stories tagged with this issue (from the Local Signals feed). */
export function newsCount(issue, signals) {
    if (!Array.isArray(signals)) return null;
    return signals.filter((s) => s && s.issue === issue.issue).length;
}

export function draftHref(issue, elected, days) {
    const facts = [
        `${issue.complaints} complaints about ${lower(issue.issue)} in the last ${days} days (previously ${issue.previous})`,
        `${issue.people} people in ${issue.locality_count} localities${issue.localities?.length ? `: ${issue.localities.slice(0, 4).map((l) => `${l.name} (${l.complaints})`).join(', ')}` : ''}`,
        issue.open_over_30_days ? `${issue.open_over_30_days} unresolved for over 30 days` : null,
        issue.department ? `${issue.department}: ${issue.filed_resolved} of ${issue.filed} filings resolved` : null,
    ].filter(Boolean).join('\n');
    const params = new URLSearchParams({
        subject: `${issue.issue} — ${elected ? 'action needed' : 'residents demand action'}`,
        context: facts,
    });
    if (issue.department) params.set('recipient', issue.department);
    return `/dashboard/drafter?${params.toString()}`;
}

export function isValidInsight(res) {
    return Boolean(res && Array.isArray(res.issues) && typeof res.period_days === 'number');
}
