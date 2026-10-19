# NEEDLE National Geography — Phase 0 Executive Summary

**Audit date:** 19 October 2026  
**Decision scope:** whether to begin an independent, dataset-first national geography project. This is not an integration design for NEEDLE.

## Recommendation

**CONDITIONAL GO** for creating `needle-india-geography-master` and running a controlled acquisition/validation pilot. **NO GO** for nationwide production claims, raw-data redistribution, or NEEDLE integration until the conditions below are closed.

India has strong official building blocks, but no verified single official package supplies the complete administrative, electoral, postal, ward and polling-station graph with current nationwide polygons and stable cross-system identifiers. The practical route is a versioned evidence pipeline: use Local Government Directory (LGD) as the current administrative identity spine, Survey of India (SoI) for licensed administrative geometry, Census 2011 for historical codes, Election Commission of India (ECI) orders/publications for electoral authority, state/UT CEO publications for polling stations, and Department of Posts data for postal reference. Every join must preserve its method, confidence, source vintage and review state.

## What the repository audit found

The current NEEDLE repository already has a capable, seat-scoped operational resolver, a typed gazetteer/shadow resolver, geography curation tools, audit logs and dashboard map machinery. It does **not** contain an authoritative national master. Its static locality coverage is narrow (24 constituency files across four directory groups), while the bundled nationwide-looking electoral boundary assets are third-party Datameet derivatives (543 parliamentary features and 4,182 assembly features), not verified official nationwide machine-readable ECI boundary releases. Those assets must not be mistaken for source-of-truth national data.

The present product is also tightly coupled to tenant seat scope and dashboard rendering conventions. This supports the revised strategy: build and validate the national dataset independently, then decide integration later.

## Availability conclusion

| Layer | Phase 0 conclusion |
|---|---|
| State/district/subdistrict identities | Official nationwide sources available through LGD; current snapshots and change reports require acquisition discipline. |
| Administrative boundaries | SoI publishes nationwide state/district/subdistrict boundary products. Use is subject to SoI-specific terms. |
| Villages | LGD provides current directories; Census provides the 2011 historical directory. SoI listed downloadable village boundary packages for 27 states/UTs at audit time, leaving nine without a verified package on that page. |
| Blocks, Gram Panchayats, ULBs and wards | LGD exposes entity and relationship downloads, but completeness and state practice vary; unmapped-entity reports must become quality gates. Official nationwide polygons were not verified. |
| Parliamentary and Assembly constituencies | ECI orders, atlases and lists are authoritative for legal composition. No official, current, nationwide SHP/GeoJSON boundary package was verified. |
| Polling stations | Official directories exist unevenly across CEO sites, commonly as PDFs, HTML viewers or electoral-roll sections. No stable nationwide bulk directory or public nationwide coordinate dataset was verified. |
| PIN codes | Department of Posts/OGD supplies a useful directory (and an OGD boundary catalog), but PIN geography is postal routing—not proof of an administrative or electoral relationship. |

The detailed state/UT assessment is in [INDIA_COVERAGE_MATRIX.csv](INDIA_COVERAGE_MATRIX.csv). `NOT_FOUND` means the audit did not verify an official publishable artifact; it does not assert non-existence.

## Conditions before the GO becomes unconditional

1. Obtain written licensing interpretation for SoI raw storage, transformations, derived products, public distribution and commercial use. SoI portal terms are more restrictive than the Government Open Data License (GODL).
2. Capture reproducible snapshots from LGD/OGD and record checksums, request parameters, publication dates and retrieval evidence.
3. Run a representative pilot across at least one high-coverage state, one northeastern state absent from the SoI village list, one Union Territory, and one state with recent electoral change.
4. Prove code-based joins where possible and quantify reviewed name/hierarchy/spatial joins where codes are absent.
5. Define acceptance thresholds for topology, coverage, referential integrity, temporal validity and cross-source disagreement before publishing a release.
6. Treat official PC/AC polygon acquisition and polling-station coordinates as open workstreams, not assumed inputs.

## First datasets to acquire

Acquire metadata and small representative samples before bulk download:

1. LGD state/district/subdistrict/block/village/local-body/ward directories, entity changes, GP–village and block–village mappings.
2. SoI ABDB state/district/subdistrict package plus metadata and licence evidence.
3. SoI village packages for four pilot jurisdictions only, pending licence review.
4. Census 2011 Location Code Directory for historical crosswalk work.
5. ECI 2008 delimitation order, subsequent Assam and Jammu & Kashmir orders, and the latest ECI constituency lists/atlas.
6. One current CEO polling-station directory per pilot jurisdiction.
7. Department of Posts All India PIN Code Directory as a non-authoritative enrichment layer.

## Principal blockers

- No verified official nationwide machine-readable PC/AC polygon release.
- Village-boundary availability on the SoI page is incomplete by state/UT and vintages are not uniform.
- Electoral and administrative hierarchies have different semantics and change cycles; many relationships are not simple containment.
- Polling-station publication is decentralized, format-fragmented and often lacks public coordinates or explicit reuse terms.
- Municipal-ward definitions and polygons are especially fragmented and fast-changing.
- SoI commercial reuse/redistribution rights require legal confirmation; ECI/CEO publications often lack an explicit open-data licence.
- Transliteration, renamed/split entities, duplicate names, enclaves and boundary disagreements require human review, not fuzzy matching alone.

## Proposed independent repository shape

```text
needle-india-geography-master/
  README.md
  LICENSES/                  # source-specific terms and legal decisions
  sources/                   # declarative source registry; no secrets
  schemas/                   # canonical and source schemas
  pipelines/{acquire,stage,normalize,link,validate,publish}/
  data/{raw,staged,canonical,releases}/  # large artifacts via object storage/manifests
  crosswalks/                # LGD, Census, ECI, postal mappings
  validations/{rules,reports,fixtures}/
  provenance/                # retrieval manifests, hashes, lineage
  docs/{coverage,decisions,runbooks}/
  tests/
```

Raw data should be immutable and access-controlled where terms require it. Git should hold code, schemas, manifests and small fixtures—not multi-gigabyte national artifacts. The logical model in [DATA_MODEL_PROPOSAL.md](DATA_MODEL_PROPOSAL.md) is storage-neutral; PostGIS, APIs and NEEDLE imports remain later decisions.

## Stop point

Phase 0 ends with this audit and the draft documentation PR. Do not create the new repository, perform bulk acquisition, modify NEEDLE, or choose a NEEDLE integration architecture without explicit approval.

