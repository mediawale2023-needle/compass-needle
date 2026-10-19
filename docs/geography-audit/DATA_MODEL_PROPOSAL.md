# Storage-Neutral National Geography Data Model

## Decision boundary

This document proposes a logical exchange model for the future independent repository. It does **not** select PostGIS, an API, a NEEDLE import mechanism or a production database. Canonical releases should be serializable to open tabular/geospatial formats and testable without NEEDLE.

## Design rules

1. Identity, geometry, names and relationships are separate, versioned objects.
2. Every assertion carries source, vintage, retrieval and transformation lineage.
3. Administrative, electoral, postal and service-delivery hierarchies remain separate namespaces.
4. Relationships are effective-dated; no “current” overwrite destroys history.
5. Missing, unavailable, restricted and not-applicable are distinct states.
6. Source assertions are immutable. Canonical decisions are reproducible derived records.
7. Human decisions record reviewer, reason and evidence; no unexplained manual fix.

## Core entities

| Entity | Essential fields |
|---|---|
| `source` | `source_id`, publisher, title, canonical URL, jurisdiction, licence status/URL/hash, access class, publication/retrieval timestamps |
| `artifact` | `artifact_id`, `source_id`, original filename, media type, bytes, SHA-256, storage locator, format, encoding, extraction status |
| `release` | `release_id`, semantic/date version, created time, schema version, included snapshots, validation result, publication class |
| `place` | stable project UUID, namespace/type, status, valid interval, successor/predecessor references |
| `place_identifier` | place UUID, scheme (`LGD`, `CENSUS_2011`, `ECI`, `PIN`, source-local), value, valid interval, source assertion |
| `place_name` | place UUID, name, language/script, name kind, normalized search form, valid interval, source assertion |
| `geometry` | geometry UUID, place UUID, geometry role, CRS, representation locator, source artifact/feature, vintage, precision/quality flags |
| `relationship` | subject UUID, predicate, object UUID, validity, source assertion, derivation method, confidence/review status |
| `polling_station` | station identity within election/revision context, number/name/address, AC reference, location/building reference, validity and source |
| `crosswalk_assertion` | left/right identifier, relation (`same_as`, `successor_of`, `overlaps`, `unresolved`), method, score, reviewer, source evidence |
| `validation_result` | rule, target, severity, observed/expected values, run/version, disposition |
| `coverage_observation` | jurisdiction/layer/snapshot, expected/observed count, status, missing reason, evidence |

## Place taxonomy

Minimum namespaces/types:

- Administrative: country, state/UT, district, subdistrict/tehsil/taluk, development block, village, hamlet where officially represented.
- Local government: district/intermediate/village panchayat, urban local body, municipal zone, municipal ward.
- Electoral: parliamentary constituency, assembly constituency, polling station, polling location/building and electoral-roll part.
- Postal: circle, region, division, post office and PIN/service area.

Types do not imply cross-namespace containment. For example, a PIN is not the parent of a village, and a polling part is not interchangeable with a polling station.

## Relationship vocabulary

Use explicit predicates such as `administered_by`, `within_administrative`, `represented_by_pc`, `represented_by_ac`, `ac_segment_of_pc`, `served_by_post_office`, `uses_polling_location`, `split_from`, `merged_into` and `same_as_source_entity`. Record whether a relationship is:

- source-declared;
- code-joined;
- geometry-derived;
- name/hierarchy-derived;
- manually adjudicated.

Only source-declared or reviewed relationships should be release-authoritative for electoral composition.

## Geometry contract

- Preserve original bytes and CRS before normalization.
- Normalize release geometry to a documented CRS (normally EPSG:4326 for exchange) without discarding source geometry.
- Support `Polygon` and `MultiPolygon`; never coerce islands/enclaves into a single ring.
- Store precision, simplification method/tolerance and lineage. Simplified web geometry is a derivative, never the master.
- Record validity repair separately; do not silently rewrite invalid source geometry.
- Provide GeoParquet/GeoPackage for bulk analysis and GeoJSON only for bounded extracts. Shapefile may be retained as source, not preferred canonical output.

## Null and confidence semantics

Every absent field or layer uses one of: `unknown`, `not_published`, `not_found`, `access_restricted`, `not_applicable`, or `withheld`. A numeric confidence score is insufficient by itself; it must accompany the derivation method and decision state (`accepted`, `needs_review`, `rejected`, `unresolved`).

## Release contents

A release manifest should enumerate schemas, artifacts, tables/layers, row/feature counts, jurisdiction coverage, temporal cutoff, hashes, licence/redistribution class, validation report and known gaps. Restricted raw artifacts may be referenced but excluded from a public release.

## Storage sizing assumptions

SoI describes a roughly 15 GB national vector product before the project adds raw revisions, derived formats, indexes and validation outputs. Plan an initial working envelope of **100–250 GB** for pilot-to-first-national processing, with lifecycle/version policies rather than destructive overwrite. This is a capacity-planning assumption, not a measured acquisition total. A full history of high-resolution geometry and frequent snapshots could exceed it materially.

Git should contain manifests, schemas, source adapters, fixtures and reports. Large raw/canonical artifacts belong in checksum-addressed object storage with local development samples. Secrets, portal credentials and licensed raw data must never be committed.

## Open decisions deferred

- PostGIS versus file-first lakehouse/query engines.
- Public API shape and hosting.
- Search/geocoding implementation.
- Tile generation and CDN.
- NEEDLE import, sync or runtime consumption.

Those decisions should follow pilot measurements for size, query patterns, licence constraints and update cadence.

