function normalize(value) {
    return String(value || '')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

const REAL_CONSTITUENCY_MAPS = [
    {
        key: 'mla:belgaum dakshin',
        seatType: 'mla',
        constituencies: [
            'belgaum dakshin',
            'belgaum south',
            'belagavi south',
            'belgaum dakhshin',
        ],
        assetPath: '/maps/mla/belgaum-dakshin-outline.svg',
        aspectRatio: '72 / 63',
        anchors: [
            { x: 49, y: 15, aliases: ['peeranwadi', 'khadarwadi', 'hunchanatti', 'majagaon'] },
            { x: 31, y: 28, aliases: ['hindawadi', 'hindwadi', 'jain basti', 'nanawadi', 'nanawadai'] },
            { x: 45, y: 34, aliases: ['tilakwadi', 'budhawar peth', 'somawar peth', 'vaccine depot', 'gajanan maharaj', 'godshewadi', 'godshewadi', 'r c nagar', 'subhash chandra nagar', 'govaves'] },
            { x: 24, y: 58, aliases: ['angol', 'bhagya nagar'] },
            { x: 68, y: 40, aliases: ['shahapur', 'nath pai circle', 'teli patil galli', 'khasabag', 'basavan galli', 'meerapur', 'kacheri galli', 'alawan galli', 'mahadwar road', 'gudshed road'] },
            { x: 56, y: 69, aliases: ['vadgaon', 'vadagaon', 'vadagon', 'june belagavi', 'june belgaavi', 'rajwada', 'rajawada', 'rajawad', 'malprabha nagar', 'chavadi galli'] },
            { x: 79, y: 63, aliases: ['yellur', 'awacharatti', 'yaramal', 'masagoudanahatti', 'masagoudanahatti', 'dhamne', 'balagamatti', 'machhe', 'macche'] },
        ],
    },
];

export function normalizeConstituencyMapToken(value) {
    return normalize(value);
}

export function getConstituencyMapConfig({ constituency, seatType }) {
    const normalizedSeatType = normalize(seatType);
    const normalizedConstituency = normalize(constituency);

    return REAL_CONSTITUENCY_MAPS.find((entry) => {
        if (entry.seatType && normalizedSeatType && entry.seatType !== normalizedSeatType) return false;
        return entry.constituencies.some((alias) => alias === normalizedConstituency);
    }) || null;
}

export function resolveConstituencyHotspot(config, area, fallbackIndex = 0) {
    const normalizedArea = normalize(area);
    const anchor = config?.anchors?.find((item) => item.aliases.some((alias) => {
        const normalizedAlias = normalize(alias);
        return normalizedArea.includes(normalizedAlias) || normalizedAlias.includes(normalizedArea);
    }));

    if (anchor) return { x: anchor.x, y: anchor.y };

    const fallbackPositions = [
        { x: 25, y: 26 },
        { x: 42, y: 22 },
        { x: 62, y: 28 },
        { x: 21, y: 51 },
        { x: 43, y: 45 },
        { x: 68, y: 48 },
        { x: 34, y: 71 },
        { x: 57, y: 73 },
    ];

    return fallbackPositions[fallbackIndex % fallbackPositions.length];
}
