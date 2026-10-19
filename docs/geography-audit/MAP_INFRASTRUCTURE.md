# Geometry Processing and Map Infrastructure Assessment

## Scope

This document covers acquisition QA, canonical geometry, reproducible derivatives and release packaging for the independent geography master. It deliberately does not design a NEEDLE map integration.

## Authority layers

Keep four layers distinct:

1. **Source geometry:** immutable bytes exactly as acquired.
2. **Normalized master:** repaired only through recorded transformations, common CRS, full practical precision.
3. **Analysis derivatives:** overlays, centroids/points-on-surface, intersections and crosswalk evidence.
4. **Presentation derivatives:** simplified geometry, vector tiles or bounded GeoJSON; never promoted back to authority.

## Recommended processing workflow

- Inspect archive safety, file inventory, encoding, CRS and sidecar metadata before extraction.
- Convert staged geometry to an open container while retaining all source attributes.
- Validate feature count, geometry type, empties, CRS bounds, validity and duplicate identifiers.
- Normalize winding/precision only with a documented, deterministic toolchain.
- Repair invalid geometry into a new derived layer with before/after metrics.
- Run parent-child overlay and topology tests using jurisdiction-specific tolerances.
- Produce full-precision canonical output first; create explicit simplification tiers afterward.
- Hash every output and bind it to tool versions, parameters and input artifacts.

## Format recommendation

| Need | Preferred format | Reason |
|---|---|---|
| Immutable source | Original archive/files | Evidentiary fidelity. |
| Bulk canonical/analysis | GeoParquet and/or GeoPackage | Open, efficient, typed, large-dataset friendly. |
| Human exchange | GeoPackage; CSV for non-spatial tables | Portable and inspectable. |
| Small extracts | GeoJSON | Interoperable but verbose; avoid national high-resolution payloads. |
| Web delivery if later approved | PMTiles/vector tiles | Efficient range delivery; regenerate from canonical data. |
| Source compatibility | Shapefile | Ingest only; field-name, encoding and size limits make it a poor canonical format. |

## QA map tooling

A local/static review viewer can use MapLibre GL JS, documented at [maplibre.org](https://maplibre.org/projects/gl-js/), with locally generated tiles or bounded GeoJSON. The viewer is a validation tool: source/derived toggles, feature inspection, boundary disagreement overlays, vintage/licence badges and issue links. It must never conceal missing layers with synthetic shapes.

## Boundary validation

- Geometry validity and non-empty checks.
- Expected bounds and plausible area checks.
- Same-level overlaps/gaps, with coast/island/enclave exceptions documented.
- Child coverage within parent using tolerances; flag, do not silently clip.
- Cross-vintage Hausdorff/area-change summaries to identify unexpected shifts.
- PC/AC count and relation checks against ECI material.
- Spot validation against source maps, never consumer basemaps alone.

## Storage and compute

Use checksum-addressed object storage for raw and generated artifacts, separate restricted/public buckets or prefixes, encryption, versioning and lifecycle rules. CI should validate schemas and small fixtures; scheduled/controlled jobs should process full states. A build manifest must make releases reproducible without requiring mutable “latest” URLs.

The first working capacity estimate is 100–250 GB, allowing several raw/normalized/derived snapshots around SoI’s approximately 15 GB product description. Measure pilot amplification before committing infrastructure. Costs should be estimated from actual stored GB, request volume, egress and compute duration using current provider pricing (for example [Amazon S3](https://aws.amazon.com/s3/pricing/) and [CloudFront](https://aws.amazon.com/cloudfront/pricing/?country=56)); this audit does not invent a fixed monthly amount.

## Security and licensing controls

- Treat ZIPs and shapefiles as untrusted inputs; cap extraction sizes and reject path traversal.
- Store portal credentials outside Git and acquisition logs.
- Tag every derivative with the most restrictive applicable source licence until legal review says otherwise.
- Generate public releases from an allowlist; do not assume transformations remove upstream restrictions.
- Exclude electoral-roll personal data. Polling-station directories should retain public institutional location fields only.

## Existing NEEDLE map caution

The current dashboard’s SVG projection, anchor coordinates and synthetic fallback are product presentation contracts. They are not validation infrastructure and should not influence the canonical national schema. Any future use of national releases in NEEDLE requires a separate visual/regression assessment after the dataset exists.
