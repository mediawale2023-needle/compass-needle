/**
 * Consultant briefing — pure helpers that turn the counts-only /briefing payload into words.
 *
 * Everything here is deterministic templating over aggregate numbers: no AI, no case text,
 * no citizen details. The briefing talks about the constituency's issues only; delivery
 * figures (filed, resolved, pending) live in the momentum cards, not in the prose.
 */

/** Fractional change, or null when there is no comparison (all time) or no baseline. */
export function change(now, previous) {
    if (previous === null || previous === undefined || !previous) return null;
    return (now - previous) / previous;
}

/** "↑ 18%", "↓ 6%", "no change", "new" or null (no comparison period). */
export function changeLabel(now, previous) {
    if (previous === null || previous === undefined) return null;
    if (!previous) return now ? 'new' : 'no change';
    const c = (now - previous) / previous;
    if (Math.abs(c) < 0.005) return 'no change';
    return `${c > 0 ? '↑' : '↓'} ${Math.round(Math.abs(c) * 100)}%`;
}

/**
 * Tone of a change for a metric. goodWhen: 'up' (more is better) or 'down' (less is better).
 * Returns 'good' | 'bad' | 'flat' | null.
 */
export function changeTone(now, previous, goodWhen) {
    if (previous === null || previous === undefined) return null;
    if (now === previous) return 'flat';
    const up = now > previous;
    return up === (goodWhen === 'up') ? 'good' : 'bad';
}

export function joinNames(names) {
    const list = (names || []).filter(Boolean);
    if (list.length <= 1) return list[0] || '';
    return `${list.slice(0, -1).join(', ')} and ${list[list.length - 1]}`;
}

function localityNames(issue, n = 2) {
    return (issue?.top_localities || []).slice(0, n).map((l) => l.name);
}

function lower(name) {
    return name ? name.charAt(0).toLowerCase() + name.slice(1) : name;
}

function riseVerb(issue) {
    const { count, previous } = issue;
    if (!previous) return `rose from none to ${count}`;
    const ratio = count / previous;
    if (ratio >= 2.5) return `rose ${Math.round(ratio)}-fold`;
    if (ratio >= 1.9) return 'doubled';
    return `rose ${Math.round((ratio - 1) * 100)}%`;
}

/** The fastest-rising issue worth calling out, or null. */
export function findRiser(issues, exclude) {
    const candidates = (issues || []).filter((i) => i !== exclude && i.previous !== null && i.previous !== undefined
        && i.count >= 3 && i.count > i.previous && (i.previous === 0 || (i.count - i.previous) / i.previous >= 0.25));
    candidates.sort((a, b) => {
        const ga = a.previous ? (a.count - a.previous) / a.previous : a.count;
        const gb = b.previous ? (b.count - b.previous) / b.previous : b.count;
        return gb - ga || b.count - a.count;
    });
    return candidates[0] || null;
}

/**
 * Build the briefing: { headline: { lead, emphasis }, points: [{ tone, strong, rest }], text }.
 * `received` is the number of complaints in the period (the share denominator).
 */
export function buildBriefing(briefing) {
    const received = briefing?.momentum?.received?.now || 0;
    const issues = (briefing?.issues || []).filter((i) => i.count > 0);
    if (!received || !issues.length) {
        const headline = { lead: 'No complaints were received in this period.', emphasis: null };
        return { headline, points: [], text: headline.lead };
    }

    const top = issues[0];
    const share = Math.round((top.count / received) * 100);
    const riser = findRiser(issues, top) || (findRiser([top]) ? top : null);
    const topLocs = localityNames(top);

    let lead;
    let emphasis = null;
    if (riser && riser !== top) {
        lead = `${top.name} accounts for ${share}% of complaints, and`;
        const where = localityNames(riser);
        emphasis = `${lower(riser.name)} complaints ${riseVerb(riser)}${where.length ? ` in ${joinNames(where)}` : ''}.`;
    } else {
        lead = `${top.name} accounts for ${share}% of complaints${topLocs.length ? `, concentrated in ${joinNames(topLocs)}` : ''}.`;
        if (riser === top) emphasis = `These complaints ${riseVerb(top)} on the previous period.`;
    }

    const points = [];
    const topChange = changeLabel(top.count, top.previous);
    const topChangeWords = topChange && topChange !== 'new' && topChange !== 'no change'
        ? `, ${topChange.startsWith('↑') ? 'up' : 'down'} ${topChange.slice(2)}` : '';
    const topLocCount = (top.top_localities || []).slice(0, 2).reduce((s, l) => s + l.count, 0);
    points.push({
        tone: 'crit',
        strong: `${top.name} is the biggest issue: ${top.count} complaint${top.count === 1 ? '' : 's'}${topChangeWords}.`,
        rest: topLocs.length ? ` ${joinNames(topLocs)} account for ${Math.round((topLocCount / top.count) * 100)}% of them.` : '',
    });

    if (riser && riser !== top) {
        const where = localityNames(riser);
        points.push({
            tone: 'crit',
            strong: `${riser.name} complaints ${riseVerb(riser)}`,
            rest: ` (${riser.previous} → ${riser.count})${where.length ? `, led by ${joinNames(where)}` : ''} — the sharpest rise in the constituency.`,
        });
    }

    const used = new Set([top, riser]);
    const hasCompare = top.previous !== null && top.previous !== undefined;
    const steady = issues.find((i) => !used.has(i) && i.count >= 3 && (!hasCompare
        || (i.previous && Math.abs((i.count - i.previous) / i.previous) <= 0.15)));
    if (steady) {
        used.add(steady);
        const where = localityNames(steady);
        points.push({
            tone: 'warn',
            strong: hasCompare ? `${steady.name} remains a steady concern` : `${steady.name} is the next biggest issue`,
            rest: ` at ${steady.count} complaints${where.length ? `, concentrated in ${joinNames(where)}` : ''}.`,
        });
    }

    const easing = (briefing?.issues || []).filter((i) => !used.has(i) && i.previous >= 3 && i.count < i.previous * 0.9).slice(0, 2);
    if (easing.length) {
        const still = localityNames(easing[0], 1)[0];
        points.push({
            tone: 'go',
            strong: `${joinNames(easing.map((i) => i.name))} complaints eased`,
            rest: ` this period${still ? `; ${still} still reports the most ${lower(easing[0].name)} complaints` : ''}.`,
        });
    }

    const headline = { lead, emphasis };
    const text = [
        [lead, emphasis].filter(Boolean).join(' '),
        ...points.map((p) => `• ${p.strong}${p.rest}`),
    ].join('\n');
    return { headline, points: points.slice(0, 4), text };
}

/** The delivery callout under the funnel, or null when there is nothing to flag. */
export function funnelCallout(funnel) {
    if (!funnel || !funnel.received) return null;
    if (funnel.ready_to_file > 0) {
        const waited = funnel.oldest_ready_days ? `; the oldest has waited ${funnel.oldest_ready_days} day${funnel.oldest_ready_days === 1 ? '' : 's'}` : '';
        return {
            tone: 'warn',
            title: 'The drop is at filing.',
            body: `${funnel.ready_to_file} grievance${funnel.ready_to_file === 1 ? ' is' : 's are'} prepared for filing with government but not yet submitted${waited}. Raise this with the office this week.`,
        };
    }
    if (funnel.pending / funnel.received > 0.5) {
        return {
            tone: 'warn',
            title: 'Most grievances have no action yet.',
            body: `${funnel.pending} of ${funnel.received} grievances received in this period are still pending.`,
        };
    }
    return {
        tone: 'go',
        title: 'Grievances are moving.',
        body: `${funnel.action_taken} of ${funnel.received} grievances received in this period have seen action.`,
    };
}

/** "This month's briefing" for the presets, otherwise "Briefing". */
export function briefingEyebrow(period) {
    if (period?.kind === 'days') {
        if (period.days === 7) return "This week's briefing";
        if (period.days === 30) return "This month's briefing";
        if (period.days === 90) return "This quarter's briefing";
        if (period.days === 365) return "This year's briefing";
    }
    return 'Briefing';
}
