"""
scripts/import_delhi_catalogue.py — build modules/data/delhi_catalogue.json from a Delhi public-mapping capture.

Offline and read-only with respect to the capture: it reads `delhi_catalogue_cleaned.json` (from the capture
deliverables) and writes the Needle catalogue file. It never contacts the Delhi portal and never touches the raw evidence.

Usage:
    python scripts/import_delhi_catalogue.py PATH/TO/delhi_catalogue_cleaned.json [--out modules/data/delhi_catalogue.json]

Rules enforced here (the same ones the catalogue file states about itself):
  * names, category text, L1/L2/L3 posts, disposal days and ordering are copied verbatim - no decoding, no spelling fixes,
    no merging of similar/duplicate categories;
  * `portal_option_value_observed` is the portal dropdown's own option value for the DEPARTMENT. It is not a Needle ID and
    no category IDs are created;
  * a department is `complete` only if the capture says so; Delhi Police stays partial (see verification);
  * locations are never populated (the public page does not expose them).
"""
import argparse
import collections
import json
import os
import sys

SCHEMA_VERSION = 2
DEFAULT_OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "modules", "data", "delhi_catalogue.json")

UNVERIFIED = "screenshot_repaired_not_text_verified"

IDS_POLICY = ("The portal shows no category codes and no Needle ID is invented. A department is identified by its exact portal name "
              "and a category by its exact portal text. `seq` is only the S.No. shown on the public mapping page. "
              "`portal_option_value_observed` is the value attribute of the portal's own department dropdown option as it was "
              "observed; it is a department option value, never a category ID.")
TEXT_POLICY = ("Original portal text and ordering are preserved, including spelling mistakes, inconsistent casing, duplicate rows and "
               "literal HTML-entity text such as '&amp;amp;'. `text_raw` is what the capture returned; `text` is currently identical to it "
               "because nothing is decoded or corrected. Never rewrite either field.")
MAPPING_NOTE = ("Captured from the portal's PUBLIC category-mapping page. That page is not proof that every category appears in the "
                "filing form's own dropdown, and the form's dropdown has not been compared with it.")


def build(capture: dict) -> dict:
    depts = []
    totals = collections.Counter()
    for d in capture["departments"]:
        cats = []
        ver = collections.Counter()
        for c in d["categories"]:
            row = {
                "seq": c["seq"],
                "text_raw": c["category_text"],
                "text": c["category_text"],
                "l1": {"post_raw": c["l1"]["post"], "post": c["l1"]["post"], "disposal_days": c["l1"]["disposal_days"]},
                "l2": {"post_raw": c["l2"]["post"], "post": c["l2"]["post"], "disposal_days": c["l2"]["disposal_days"]},
                "l3": {"post_raw": c["l3"]["post"], "post": c["l3"]["post"], "disposal_days": c["l3"]["disposal_days"]},
                "verification": c["verification"],
            }
            if c.get("extraction_note"):
                row["extraction_note"] = c["extraction_note"]
            ver[c["verification"]] += 1
            cats.append(row)
        if len(cats) != d["row_count"]:
            raise SystemExit(f"{d['name']}: row_count {d['row_count']} != {len(cats)} rows")
        partial = d["capture_status"] != "complete"
        unverified = ver.get(UNVERIFIED, 0)
        note = MAPPING_NOTE
        if partial:
            note = ("PARTIAL: " + (" ".join(d.get("capture_notes") or []) or "see capture notes") + " " + MAPPING_NOTE)
        depts.append({
            "name": d["name"],
            "portal_option_value_observed": d["portal_option_value_observed"],
            "catalogue": {
                "status": "captured_partial_verification" if partial else "captured",
                "capture_status": d["capture_status"],
                "row_count": len(cats),
                "complete": not partial,
                "complete_note": note,
                "unverified_row_count": unverified,
                "verification_summary": dict(ver),
                "capture_notes": d.get("capture_notes") or [],
                "captured_at_utc": d["captured_at_utc"],
                "form_comparison": "pending",
                "source": "mapping_page",
                "source_page": d["source_page"],
            },
            "categories": cats,
            "locations": {"status": "not_captured", "items": []},
        })
        totals["rows"] += len(cats)
        totals["partial" if partial else "complete"] += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "portal": "Delhi CM Jan Sunwai",
        "portal_url": "https://cmjansunwai.delhi.gov.in/",
        "source": {"page": capture["source_page"], "schema": capture.get("schema"), "kind": "public_category_mapping_page"},
        "ids_policy": IDS_POLICY,
        "text_policy": TEXT_POLICY,
        "locations_policy": capture.get("locations") or "Location lists are not on the public page: not captured, never assumed equal across departments.",
        "department_count": len(depts),
        "category_row_count": totals["rows"],
        "departments_complete": totals["complete"],
        "departments_partial": totals["partial"],
        "departments": depts,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("capture")
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    with open(args.capture, encoding="utf-8") as fh:
        capture = json.load(fh)
    out = build(capture)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {args.out}: {out['department_count']} departments, {out['category_row_count']} category rows, "
          f"{out['departments_complete']} complete, {out['departments_partial']} partial")
    return 0


if __name__ == "__main__":
    sys.exit(main())
