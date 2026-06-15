export const dashboardPalette = {
    paper: '#F2EBD9',
    paperDeep: '#E8E0CB',
    surface: '#FBF6E7',
    surfaceWarm: '#F7F0DC',
    ink: '#1A1812',
    ink2: '#4A453A',
    ink3: '#7A7263',
    hair: 'rgba(26,24,18,0.14)',
    hairStrong: 'rgba(26,24,18,0.32)',
    green: '#006A4D',
    greenDeep: '#003B2A',
    greenInk: '#024A36',
    greenTint: '#DFE9E2',
    saffron: '#C76A1A',
    saffronTint: '#F4E3CE',
    red: '#8B2E1F',
    redTint: '#F2DAD3',
    blue: '#23496B',
    blueTint: '#DDE5EE',
    neutralTint: '#E8E2CC',
};

export const dashboardFonts = {
    serif: '"Source Serif 4", Georgia, serif',
    mono: '"JetBrains Mono", "Fira Code", monospace',
    sans: '"Inter", system-ui, sans-serif',
};

export function getDashboardStatusStyle(status) {
    const norm = (status || '').toLowerCase();
    if (norm === 'new') return { bg: dashboardPalette.saffronTint, fg: dashboardPalette.saffron, dot: dashboardPalette.saffron };
    if (norm === 'in_progress') return { bg: dashboardPalette.blueTint, fg: dashboardPalette.blue, dot: dashboardPalette.blue };
    if (norm === 'resolved') return { bg: dashboardPalette.greenTint, fg: dashboardPalette.greenInk, dot: dashboardPalette.green };
    return { bg: dashboardPalette.neutralTint, fg: dashboardPalette.ink2, dot: dashboardPalette.ink2 };
}

export function getDashboardStatusLabel(status) {
    const norm = (status || '').toLowerCase();
    if (norm === 'new') return 'Open';
    if (norm === 'in_progress') return 'In Progress';
    if (norm === 'resolved') return 'Resolved';
    return status || '—';
}
