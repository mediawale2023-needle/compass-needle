# Existing NEEDLE Geography System Audit

## Scope and method

This is a read-only architecture inventory of the repository at the audit branch base. It records what exists, where authority lives and what must remain isolated from a future national geography master. No application code, database, API, resolver, map, tenant configuration or infrastructure was changed.

## Current data flow

```text
tenant/seat configuration
  -> shared geography JSON or tenant_override geography_data
  -> deterministic geography_resolver.py
  -> WhatsApp geography decision (accept / clarify / awaiting_location)
  -> tenant-scoped case fields and diagnostics

same curated entities
  -> gazetteer.py
  -> geo_resolver_v2.py (shadow/three-way decision)
  -> resolution log and discovery queue

shared geography / boundary asset
  -> seat map generator and manifest
  -> /api/maps/seat-manifest
  -> dashboard SVG renderer
```

## Component inventory

| Component | Current role | Data authority / scope | National-master implication |
|---|---|---|---|
| `modules/geography_resolver.py` | Deterministic alias, exact, normalized, fuzzy, phonetic and transliteration matching; fails closed on ambiguity. | Seat/tenant-scoped curated geography. | Useful product behavior, not a national ingestion or authority layer. |
| `modules/whatsapp_geography.py` | Applies resolver results to WhatsApp intake and preserves diagnostics; unknown locations enter clarification/awaiting state. | Tenant-scoped case intake. | Must remain untouched during dataset build. |
| `modules/gazetteer.py` | Builds typed place candidates and variants from current shared geography/manual corrections. | Closed, seat-scoped registry. | Its entity/provenance ideas are reusable conceptually; its storage and product coupling are not the national design. |
| `modules/geo_resolver_v2.py` | Relation parsing, candidate lookup and accept/ask/abstain policy; supports shadow comparison. | Existing gazetteer. | A good benchmark for validation experiments, not an integration target in Phase 0. |
| `modules/geo_relations.py` | Infers assembly–parliament relationships from the current resolver index and rejects duplicates. | Derived from current curated data. | National relationships must instead be sourced and temporally versioned. |
| `sansadx_backend/db.py` geography models | `GeoPlace`, variants, resolution log, discovery queue, seat manifest and boundary assets. | Operational product DB, tenant/seat oriented. | Do not extend for the independent project. The proposed master model is storage-neutral. |
| `TenantOverride` geography keys | Stores shared/legacy geography and manual corrections. | Tenant and seat configuration. | Not suitable as a national source-of-truth; no migration is proposed. |
| `modules/seat_maps.py`, `seat_boundaries.py`, `seat_map_generator.py` | Stores/generates dashboard map manifests, boundaries, anchors and SVG. | Product visualization assets. | Keep separate from authoritative geometry and validation. |
| `modules/parliamentary_boundary_importer.py` | Imports bundled Datameet 2019 parliamentary GeoJSON by seat/state. | Third-party derived asset, 543 features. | Must be labelled third-party and must not establish official authority. |
| `modules/assembly_boundary_importer.py` | Imports bundled normalized Datameet assembly GeoJSON. | Third-party derived asset, 4,182 features across 30 state/UT labels; some pre-delimitation data. | Coverage and vintage are insufficient for an authoritative national release. |
| `data/geography/` | Locality/polling-roll-style curated JSON. | 24 files in Aligarh, Belagavi, Ghaziabad and Kalyan Dombivli directory groups. | Valuable fixtures only; far from nationwide completeness. |
| `frontend/components/dashboard/DashboardConstituencyMap.jsx` | Projects inline GeoJSON to SVG, renders hotspots and a synthetic legacy fallback. | Dashboard manifest and presentation contract. | Rendering fallback can appear geographic without authoritative geometry; do not reuse as a data-quality signal. |
| `frontend/lib/constituency-map-data.js` | Frontend manifest fallback. | Narrow seat-specific fallback. | Not a national catalog. |
| Admin Shared Geography / seat-map screens | Curation, corrections, discovery, boundaries and audit workflows. | Existing operational tenants/seats. | No change in this phase; future integration is explicitly undecided. |
| `main.py` startup geography bootstrap | Creates/migrates current tables and performs configured bootstrap work. | Production startup path. | A national pipeline must never run as application startup migration. |

## Data assets and observed coverage

- Parliamentary boundary bundle: 543 features, 36 state/UT labels, approximately 1.9 MB; repository attribution is Datameet, not ECI/SoI.
- Assembly boundary bundle: 4,182 features, 30 state/UT labels, approximately 9.6 MB; repository attribution is Datameet and observed metadata includes pre-delimitation material.
- Local constituency geography: 24 JSON files across four directory groups. It is curated for present pilots, not systematic national coverage.
- A single constituency-library JSON exists for Belgaum Lok Sabha context.
- Geography persistence uses ordinary relational/JSON fields. No PostGIS national store, nationwide release manifest or immutable raw-source archive exists.

Counts describe repository contents, not legal/current electoral truth.

## Strengths worth preserving as principles

- Tenant scoping and fail-closed ambiguity behavior.
- Separation of canonical entities from variants.
- Provenance/status fields and resolution evidence logs.
- Explicit ask/abstain outcomes instead of forced guesses.
- Manual review and discovery queues.
- API/dashboard separation through a map manifest.

## Gaps relative to an authoritative national master

1. No source registry with retrieval time, publication vintage, licence, checksum and lineage.
2. No immutable raw snapshot layer or reproducible acquisition pipeline.
3. No nationwide canonical identifiers/crosswalks across LGD, Census, ECI and postal systems.
4. No temporal model for renames, splits, mergers, delimitation and effective dates.
5. No topology/coverage validation suite or release-level quality report.
6. No complete official PC/AC polygons, village polygons, wards or polling stations.
7. Product labels such as “verified” can describe an import workflow even when the upstream boundary is a third-party derivative; source authority needs a distinct field.
8. Map fallbacks and generated anchors are visualization conveniences, not authoritative geospatial evidence.

## Coupling and regression risks

- Resolver outputs affect case routing and constituency acceptance; changing data can change citizen-facing behavior and tenant isolation outcomes.
- Seat maps combine geometry, presentation anchors and UI dimensions. A national geometry replacement could alter map layout, hotspot positions and responsive behavior.
- Startup bootstrap and operational tables are production-sensitive. Bulk national data does not belong in this path.
- Legacy aliases/manual corrections encode hard-won local knowledge but may conflict with current official entities or silently cross vintages.
- Electoral constituency membership is not safely inferred from name similarity or geometry alone; statutory orders and effective dates control.

## Audit conclusion

The existing implementation should remain operational and untouched. It is a consumer-oriented, seat-scoped geography system—not the substrate on which to conduct national acquisition. The independent repository should produce evidence-backed releases first. A later, separately approved decision can compare those releases with the product contract and select PostGIS, files, APIs or imports.
