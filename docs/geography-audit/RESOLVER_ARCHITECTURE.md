# Independent Linking and Resolution Architecture

## Purpose

The future geography master needs a reproducible way to link official datasets and expose ambiguity for review. This is a dataset-construction resolver, not a design for routing NEEDLE cases.

## Pipeline

```text
immutable source artifacts
  -> format-specific extraction
  -> source-faithful staged records
  -> normalization (text, codes, dates, CRS)
  -> deterministic candidate generation
  -> evidence scoring and constraint checks
  -> accept / review / abstain
  -> versioned crosswalk assertions
  -> release validation and coverage report
```

## Resolution priority

1. Exact official identifier plus compatible source vintage.
2. Officially published crosswalk or relationship table.
3. Exact normalized name within an exact parent-code hierarchy.
4. Reviewed temporal successor/predecessor relationship.
5. Geometry evidence combined with name and hierarchy evidence.
6. Transliteration/alias/fuzzy evidence only as candidate generation.
7. Abstain when evidence conflicts or the margin is insufficient.

No fuzzy name match should become authoritative without hierarchy and/or geometry evidence. Automated decisions must be deterministic at a given code/data version.

## Normalization

- Preserve source text; create separate Unicode-normalized search fields.
- Represent language and script explicitly. Transliteration produces variants, never replacement names.
- Normalize punctuation, whitespace and well-defined abbreviations using versioned rules.
- Keep numbers meaningful for wards, constituencies and polling stations.
- Validate identifier check/format rules per scheme; never coerce one scheme into another.
- Parse dates and “as on” statements into explicit snapshot/effective fields.

## Candidate evidence

Each candidate record includes source/target IDs, features used, rule/model version, component scores, hard-constraint results, competing candidates and decision. Suggested evidence includes parent-code equality, district/subdistrict path, exact/variant name, script-aware edit distance, containment/overlap, centroid distance, temporal compatibility and source-declared mapping.

Hard contradictions—different official parent codes, incompatible effective periods, impossible type, or overlapping active identities—must block auto-acceptance regardless of name score.

## Electoral relationships

- Parse PC/AC composition first from ECI orders and current official lists.
- Store legal text/table citations and effective dates.
- Use geometry to validate or flag the relationship, not to replace statutory authority.
- Represent cross-district and cross-local-body constituencies normally; do not force them into a single administrative parent.
- Preserve delimitation versions. The same constituency name/number in a later order is not automatically the same identity.

## Polling stations

Model election/revision context explicitly. Extract polling station number, name, building/address, AC and publication date separately. Link a station to a place only when official codes or reviewed evidence support it. A station building may serve several stations/parts, and station numbers may be revised; do not construct a timeless national station ID from number alone.

## Human review

Review queues should be partitioned by source, jurisdiction and failure class. A reviewer sees original source rows/features, normalized candidates, hierarchy, map overlay where licensed, conflicts and past decisions. Decisions must be append-only, attributable, reason-coded and replayable after rule changes.

Useful queues:

- missing official code;
- duplicate active code/name;
- cross-source parent disagreement;
- geometry outside declared parent;
- renamed/split/merged entity;
- ambiguous transliteration;
- electoral order/geometry conflict;
- polling station with incomplete address;
- source regression since prior snapshot.

## Validation gates

Before a release:

- identifier uniqueness within scheme/vintage;
- required parent and relationship integrity;
- expected jurisdiction coverage and reconciled counts;
- valid geometry/type/CRS and no unexplained empty features;
- topology checks (self-intersection, overlaps, gaps) with source-aware exceptions;
- point-on-surface within parent where appropriate;
- PC/AC count and legal composition checks;
- snapshot-to-snapshot change budget and explained deltas;
- 100% provenance and licence classification;
- no accepted match below the policy threshold or with a hard contradiction.

## Evaluation corpus

Create small, legally distributable golden fixtures spanning duplicate village names, renamed districts, multilingual names, islands, enclaves, urban wards, recent delimitation and incomplete polling addresses. Measure precision, abstention and review workload separately. National completeness must never be improved by lowering precision.

## Relationship to NEEDLE

None is implemented or specified in this phase. A future integration review may consume a published release, but it must independently evaluate tenant isolation, resolver behavior, migration safety and map compatibility.

