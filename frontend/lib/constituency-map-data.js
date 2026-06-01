import seatRegistry from '@/data/maps/registry.json';
import belgaumDakshinManifest from '@/data/maps/mla/belgaum-dakshin.manifest.json';

function normalize(value) {
    return String(value || '')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

const MANIFESTS = {
    'mla:belgaum-dakshin': belgaumDakshinManifest,
};

function registryEntryMatches(entry, normalizedSeatType, normalizedConstituency) {
    if (entry.seat_type && normalizedSeatType && normalize(entry.seat_type) !== normalizedSeatType) {
        return false;
    }
    return (entry.aliases || []).some((alias) => normalize(alias) === normalizedConstituency);
}

function toComponentMapConfig(entry, manifest) {
    return {
        seatKey: manifest.seat_key,
        seatType: manifest.seat_type,
        seatName: manifest.seat_name,
        state: manifest.state || null,
        assetPath: manifest.asset?.path,
        aspectRatio: manifest.asset?.aspect_ratio || '1 / 1',
        features: manifest.features || [],
        fallbackAnchors: manifest.fallback_anchors || [],
        registryStatus: entry.status || 'draft',
        version: entry.version || 1,
    };
}

export function normalizeConstituencyMapToken(value) {
    return normalize(value);
}

export function getConstituencyMapConfig({ constituency, seatType }) {
    const normalizedSeatType = normalize(seatType);
    const normalizedConstituency = normalize(constituency);
    const entry = seatRegistry.find((candidate) =>
        registryEntryMatches(candidate, normalizedSeatType, normalizedConstituency)
    );
    if (!entry) return null;

    const manifest = MANIFESTS[entry.manifest_key];
    if (!manifest) return null;

    return toComponentMapConfig(entry, manifest);
}

export function resolveConstituencyHotspot(config, area, fallbackIndex = 0) {
    const normalizedArea = normalize(area);
    const feature = config?.features?.find((item) =>
        (item.aliases || []).some((alias) => {
            const normalizedAlias = normalize(alias);
            return normalizedArea.includes(normalizedAlias) || normalizedAlias.includes(normalizedArea);
        })
    );

    if (feature?.anchor) {
        return { x: feature.anchor.x, y: feature.anchor.y, featureKey: feature.feature_key, label: feature.label };
    }

    const fallback = config?.fallbackAnchors?.[fallbackIndex % Math.max(config?.fallbackAnchors?.length || 1, 1)] || { x: 50, y: 50 };
    return { x: fallback.x, y: fallback.y, featureKey: null, label: area };
}
