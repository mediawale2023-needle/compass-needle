'use client';

// Compact operational counter strip — a single hairline row, not KPI cards.
// Only truthful counts computed by useBriefcaseCases: needsYou (new +
// pending_review + awaiting_location), newToday, uncategorised. No SLA metric,
// no fabricated scoring, no serif numerals, no icon grid.
const C = {
    surface: '#FFFEFB',
    border: '#E4DECB',
    ink: '#211F19',
    muted: '#6C6858',
};
const SANS = '"Public Sans", "Noto Sans Devanagari", system-ui, sans-serif';
const MONO = '"IBM Plex Mono", ui-monospace, SFMono-Regular, monospace';

export default function BriefcaseTriageStrip({ triage }) {
    const counters = [
        { key: 'needsYou', label: 'Needs attention', value: triage?.needsYou || 0 },
        { key: 'newToday', label: 'New today', value: triage?.newToday || 0 },
        { key: 'uncategorised', label: 'Uncategorised', value: triage?.uncategorised || 0 },
    ];

    return (
        <div
            style={{
                display: 'flex',
                flexWrap: 'wrap',
                background: C.surface,
                border: `1px solid ${C.border}`,
                fontFamily: SANS,
            }}
        >
            {counters.map((c, i) => (
                <div
                    key={c.key}
                    style={{
                        display: 'inline-flex',
                        alignItems: 'baseline',
                        gap: 8,
                        padding: '9px 16px',
                        borderRight: i < counters.length - 1 ? `1px solid ${C.border}` : 'none',
                        minWidth: 0,
                    }}
                >
                    <span
                        style={{
                            fontFamily: MONO,
                            fontSize: 9.5,
                            letterSpacing: '0.08em',
                            textTransform: 'uppercase',
                            color: C.muted,
                        }}
                    >
                        {c.label}
                    </span>
                    <span style={{ fontSize: 15, fontWeight: 700, color: C.ink, letterSpacing: '-0.01em' }}>
                        {c.value.toLocaleString()}
                    </span>
                </div>
            ))}
        </div>
    );
}
