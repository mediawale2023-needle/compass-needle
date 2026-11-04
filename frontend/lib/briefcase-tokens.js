// ─────────────────────────────────────────────────────────────────────────
// Briefcase Gen 2 — canonical design tokens
// ─────────────────────────────────────────────────────────────────────────
// These are the values the Briefcase actually renders today. Before this
// module they were re-declared as a local `const C = {…}` inside each
// component, which is how three generations of palette drifted apart:
//
//   Gen 1  lib/dashboard-theme.js + components/briefcase/briefcase-shared.jsx
//          (paper #F2EBD9, surface #FBF6E7, ink #1A1812, green #006A4D)
//   Gen 2  THIS FILE — what the Briefcase list, header, triage strip and
//          Overview actually paint.
//   Gen 2b components/briefcase/BriefcaseCaseModal.jsx
//          (paper #F4F0E7, ink #24251F, green #234F3A, amber #8A5C17)
//
// Gen 2 is canonical. Gen 1 and Gen 2b are NOT migrated here on purpose:
// their values differ enough that rewriting them would visibly redesign the
// case-detail workspace and the cluster/deleted views, and this
// canonicalisation pass is required to be visually inert. They are marked
// deprecated at their definitions and should be migrated only behind a
// deliberate visual review.
//
// Adding a colour here is a design decision. Prefer reusing a token over
// introducing a near-duplicate — near-duplicates are exactly what produced
// the drift this module exists to stop.

export const gen2 = {
    // ── Ground and surfaces ──────────────────────────────────────────────
    // Surfaces lift by lightness on a warm ground, never by elevation.
    bg:          '#F3EEE2',   // page canvas
    surface:     '#FFFEFB',   // cards, rows, work surfaces
    surfaceWarm: '#F8F1E0',   // recessed / secondary surface
    paper:       '#EEE5D2',   // secondary paper, strip backgrounds

    // ── Hairlines ────────────────────────────────────────────────────────
    // Separation is a hairline, not a shadow.
    hair:        '#E4DECB',   // default border
    hairStrong:  '#C9BFA9',   // input borders, emphasis
    hairSoft:    '#DDD6C5',   // internal dividers

    // ── Ink ──────────────────────────────────────────────────────────────
    // `faint` (~3.7:1 on surface) is below WCAG AA for small text, so any
    // secondary information a reader needs — ages, "Since" dates, refs,
    // column heads — uses `muted` (~5.5:1). Keep `faint` for placeholders,
    // empty dashes and decorative glyphs.
    ink:         '#211F19',   // primary text
    muted:       '#6C6858',   // secondary text
    faint:       '#8A8270',   // tertiary / metadata

    // ── Brand ────────────────────────────────────────────────────────────
    // Green is the only brand accent and is used sparingly — a 2px rail or
    // a primary action, not a fill.
    green:       '#2B6E4C',
    greenDeep:   '#245F45',
    greenSoft:   '#E4EBDD',

    // ── State ────────────────────────────────────────────────────────────
    // Colour is reserved for state. No blue / purple / slate in status.
    err:         '#A33A32',
    rust:        '#BC6A36',
    rustInk:     '#8A4A22',
    rustSoft:    '#F1DED0',
    amber:       '#C9821C',
    amberInk:    '#7C5514',
    amberSoft:   '#F2E6CF',
    neutralSoft: '#ECE6D8',

    // ── Interaction ──────────────────────────────────────────────────────
    rowHover:    '#FCFAF3',
    activeTint:  '#F7F2E7',
};

// Hierarchy comes from switching typeface, not escalating size:
// serif = identity, sans = human prose, mono = machine fact.
export const gen2Fonts = {
    serif: '"Source Serif 4", Georgia, serif',
    sans:  '"Public Sans", "Noto Sans Devanagari", system-ui, sans-serif',
    mono:  '"IBM Plex Mono", ui-monospace, SFMono-Regular, monospace',
};

// Structural geometry is square. The small radii that exist in Briefcase
// apply only to skeleton bars and popovers, never to a structural surface.
export const gen2Radius = {
    structural: 0,
    skeleton:   2,
    control:    4,
    popover:    6,
};

// The only "shadow" on a structural surface is a hairline pretending to be
// one. Real shadows are reserved for the overlay plane (the case Sheet).
export const gen2Shadow = {
    surface: '0 1px 0 rgba(19,52,43,0.03)',
    overlay: '-10px 0 30px rgba(33,31,25,0.12)',
};

// Type scale for the Briefcase list surfaces (header, triage strip, filters,
// table/cards, pagination, cluster & deleted views). Before this scale each
// component picked its own 9–13px values, which left case IDs, status labels
// and metadata at 9–10px — too small to scan on a 13" laptop. Sizes are px.
//
// Hierarchy is still carried mainly by typeface and weight (see gen2Fonts):
// the citizen's message is the largest body text in a row, the issue title
// sits just under it in bold, and machine facts (refs, stages, pills) stay
// mono at a smaller but readable size.
export const gen2Type = {
    // mono, uppercase, letter-spaced micro-labels: column heads, QUICK/SORT,
    // counter labels, card field labels
    label:    10.5,
    // Needle status pill (mono, uppercase, inside a bordered chip)
    badge:    10.5,
    // mono machine metadata: thread count, age, gov't reference numbers
    meta:     11.5,
    // government stage line (mono, bold, uppercase)
    stage:    11.5,
    // tags and counts: category chip, tab counts, active-filter chips
    tag:      11.5,
    // sans secondary text: location, "Since", supporting status line
    small:    12.5,
    // buttons, selects, date inputs, quick chips, pagination
    control:  12.5,
    // case reference
    caseId:   13,
    // issue title and row-level emphasis
    title:    13.5,
    // citizen complaint text and other primary prose; search input
    body:     14,
    // primary navigation tabs
    tab:      14,
    // triage counter numerals
    counter:  16,
};
