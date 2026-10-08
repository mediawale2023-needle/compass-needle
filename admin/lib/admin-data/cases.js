/**
 * Case analytics derivations over /api/admin/cases/aggregates. Pure and
 * deterministic; they never fill gaps with invented values.
 */

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function weekLabel(isoDate) {
    const [year, month, day] = String(isoDate || '').split('-').map(Number);
    if (!year || !month || !day) return '';
    return `${day} ${MONTHS[month - 1]}`;
}

/**
 * Weekly new vs resolved and the open-case trend. The final week from the
 * backend is in progress, so the chart series cover COMPLETED weeks only and
 * the current week is reported separately — a partial week must not read as
 * a collapse in intake.
 */
export function caseTrend(aggregates) {
    const weekly = aggregates?.weekly;
    if (!Array.isArray(weekly) || weekly.length === 0) return null;
    const current = weekly[weekly.length - 1];
    const completed = weekly.slice(0, -1);
    const lastCompleted = completed.length ? completed[completed.length - 1] : null;
    const openNow = aggregates.open_now ?? current.open_at_end;
    return {
        labels: completed.map((week) => weekLabel(week.week_start)),
        newCases: completed.map((week) => Number(week.new || 0)),
        resolved: completed.map((week) => Number(week.resolved || 0)),
        openAtEnd: [...completed.map((week) => Number(week.open_at_end || 0)), Number(openNow || 0)],
        thisWeek: { new: Number(current.new || 0), resolved: Number(current.resolved || 0), weekStart: current.week_start },
        openChange: lastCompleted ? Number(openNow || 0) - Number(lastCompleted.open_at_end || 0) : null,
    };
}

/** Open cases older than 14 days, summed from the ageing bands. */
export function openOverDays(aggregates, days = 14) {
    const bands = aggregates?.ageing;
    if (!Array.isArray(bands)) return null;
    return bands.filter((band) => Number(band.min_days) > days).reduce((sum, band) => sum + Number(band.count || 0), 0);
}

/** "3.2 days" / "18 hours" from median hours; null when unknown. */
export function formatDuration(hours) {
    if (hours === null || hours === undefined || Number.isNaN(Number(hours))) return null;
    const value = Number(hours);
    if (value < 24) return `${Math.round(value)} ${Math.round(value) === 1 ? 'hour' : 'hours'}`;
    const days = value / 24;
    return `${days.toFixed(1)} days`;
}
