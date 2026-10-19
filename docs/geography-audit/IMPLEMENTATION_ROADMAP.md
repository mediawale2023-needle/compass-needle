# Independent National Geography Master — Implementation Roadmap

## Governing sequence

**Complete audit → approve/create independent repository → acquire pilot data → validate/version data → expand nationally → decide NEEDLE integration later.**

No phase below authorizes creation of the repository, bulk downloads, product changes or production deployment. Phase gates require explicit approval.

## Phase 0 — audit (this PR)

**Outputs:** repository inventory, official-source register, 36-jurisdiction coverage matrix, logical model, linking/validation architecture, map-processing assessment, roadmap and executive decision.

**Exit:** draft documentation-only PR; no application changes. Outcome: conditional go for an independent pilot.

## Phase 1 — repository and governance foundation (1–2 weeks)

After approval:

- create `needle-india-geography-master` with owners/review policy;
- adopt source/artifact/release manifests and schema versioning;
- define licence classifications and public/restricted release rules;
- configure checksum-addressed object storage, secrets and CI fixtures;
- select four pilot jurisdictions and write acceptance metrics;
- record architecture decisions, including why NEEDLE integration is out of scope.

**Gate:** reproducible empty pipeline, threat/licence review, no bulk data yet.

## Phase 2 — administrative pilot acquisition (2–4 weeks)

- snapshot LGD administrative/local-government entities and mappings;
- acquire SoI ABDB and only approved pilot village packages;
- acquire Census 2011 location directory and India Post directory;
- preserve original artifacts, checksums, terms and retrieval evidence;
- profile schemas, encodings, CRS, counts and code population.

Pilot set should include: a high-coverage state, a northeastern state absent from the verified SoI village list, a Union Territory, and a jurisdiction with recent electoral change. Assam, Karnataka or Maharashtra, Puducherry/Delhi, and Jammu & Kashmir provide useful stress cases; final selection depends on licensing/access.

**Gate:** 100% artifact provenance; documented legal disposition; source-faithful staged data.

## Phase 3 — canonical administrative model and validation (3–6 weeks)

- implement canonical entities/names/identifiers/history;
- make LGD the current administrative identity spine;
- construct Census↔LGD crosswalks with accept/review/abstain evidence;
- normalize geometry and run topology/hierarchy checks;
- publish pilot coverage and disagreement reports;
- measure storage, processing time, auto-link precision and review workload.

**Gate:** agreed precision/coverage thresholds, explainable unresolved set, reproducible pilot release.

## Phase 4 — electoral and polling pilot (3–6 weeks)

- encode ECI delimitation/current composition with effective dates;
- source official pilot PC/AC maps or mark official geometry unavailable;
- ingest one current CEO polling-station publication per pilot;
- separate station, building/location and roll part;
- validate constituency relationships against statutory material;
- establish permissions for derived/public electoral data.

**Gate:** legal relationships are source-cited; third-party geometry remains comparison-only; coordinates are never fabricated.

## Phase 5 — national administrative expansion (6–16 weeks, rolling)

- process jurisdictions in batches with per-state manifests;
- publish completeness dashboard and exception register;
- prioritize missing SoI village states and municipal wards as dedicated workstreams;
- version source updates and explain count/geometry deltas;
- run independent sample review before each release candidate.

**Gate:** all 36 jurisdictions have an explicit state for every target layer; no blank means “assumed complete.”

## Phase 6 — national electoral/polling expansion (ongoing)

- track ECI orders and CEO portals separately by jurisdiction/election;
- build adapters only for stable, permitted official routes;
- use manual documented acquisition for unstable PDFs/viewers;
- maintain an open blocker list for official vector boundaries and station coordinates;
- never backfill gaps with invented points or unlabeled third-party boundaries.

**Gate:** release claims match verified coverage; licence and vintage visible per layer.

## Phase 7 — release operations

- immutable release manifests and signed/checksummed artifacts;
- changelog, schema migration notes and quality report;
- public/restricted artifact separation;
- scheduled source monitoring with human approval of meaningful changes;
- rollback and supersession policy; reproducible rebuild tests.

## Deferred integration decision

Only after stable releases and measured access patterns should a separate architecture review choose among PostGIS, file/object-store queries, APIs, tiles or application imports. That review must include NEEDLE tenant isolation, resolver behavior, map UX, migrations, latency, cost and rollback. None is selected here.

## Team and effort assumptions

A credible pilot needs geospatial/data engineering, research/data stewardship, electoral-domain review and legal/licensing support. Nationwide polling and ward coverage is an ongoing publishing operation, not a one-time engineering sprint. Dates are planning ranges, not delivery commitments; access and licensing can dominate the schedule.

## Immediate next approval request

Approve or reject only: (a) creation of the independent repository, (b) the four-jurisdiction pilot, and (c) limited acquisition of the first datasets listed in the executive summary. Do not bundle NEEDLE integration into that approval.
