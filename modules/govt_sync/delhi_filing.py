"""
modules/govt_sync/delhi_filing.py — Delhi CM Jan Sunwai FILING facts, catalogue and validation.

Everything here comes from a supervised, browser-only look at the official portal (2026-11-02):
the post-OTP filing form (/OnlineEntryNew) and the public category-mapping page
(/get-online-category-mapping). Nothing is guessed, nothing is read from another state's portal, and
this module makes no network request.

Rules this module enforces (read before extending):
  * Only VERIFIED rules are hard errors: mandatory fields, the two 250-character address limits, the
    PDF-only / 1 MB / filename rules for the optional supporting document.
  * UNKNOWN things are warnings at most. The Grievance Details maximum length is UNKNOWN, so it is never
    an error; the portal's note about special characters in Grievance Details is passed on as a notice
    (its exact wording / character set was not preserved, so no character is rejected).
  * The catalogue (modules/data/delhi_catalogue.json) is keyed by the portal's own text. The portal shows
    no department or category codes, so none are invented. Every department carries completeness
    metadata; a partial catalogue is never presented as complete, and an incomplete one never blocks
    filing: staff can type the category/location exactly as the portal shows it, and Needle records that
    value as "staff_typed_unverified".
  * The catalogue covers all 90 departments (schema_version 2, built by scripts/import_delhi_catalogue.py from the
    public mapping page). It is not proof that every category is in the filing form, so a category that is not
    in the list (any department, complete or partial) is only a warning and is recorded as staff_typed_unverified.
    Delhi Police is partial: 19 long cells are not text-verified.
  * Provenance is explicit: an AI suggestion is `ai_suggested`; a value staff picked from the catalogue is
    `staff_confirmed`; a value staff typed because the catalogue lacks it is `staff_typed_unverified`.
"""
import json
import os
import re
from functools import lru_cache

CATALOGUE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "delhi_catalogue.json")

# ── Verified field rules (filing form, /OnlineEntryNew) ─────────────────────────────────────────────
ADDRESS_MAX_CHARS = 250                 # Residential Address and Grievance Area Address (live counters on the form)
ATTACHMENT_MAX_BYTES = 1024 * 1024      # "PDF only, maximum 1 MB"
ATTACHMENT_MAX_NAME_CHARS = 99          # filename must be shorter than 100 characters
# Characters the form lists as not allowed in the supporting document's file name (in addition to spaces,
# parentheses and ".."). Recorded from the form's own note during the supervised session.
ATTACHMENT_FORBIDDEN_NAME_CHARS = "<>`='~%\"*^$&#"

# Grievance Details: the portal shows a live counter but no maximum was visible. UNKNOWN. This number is
# ONLY the point at which Needle shows a "may be too long for the portal" warning; it is not a portal limit.
GRIEVANCE_DETAILS_SOFT_WARN_CHARS = 1500
GRIEVANCE_DETAILS_SPECIAL_CHARS_NOTICE = (
    "The portal's form carries a note to avoid special characters in Grievance Details. Needle does not reject any "
    "character (the exact set is not recorded); keep to plain letters, numbers and ordinary punctuation and read the "
    "note on the portal."
)

APPLICANT_FIELDS = (
    # key, portal label, mandatory?, note
    ("applicant_name", "Name", True, "Mandatory. With Group Grievance ticked the portal changes this field to the group's name."),
    ("father_husband_name", "Father/Husband Name", True, "Mandatory for individual applicants; disabled by the portal for a Group Grievance."),
    ("gender", "Gender", True, "Mandatory for individual applicants; disabled by the portal for a Group Grievance."),
    ("mobile_1", "Mobile No. 1", True, "Mandatory; the portal pre-fills it from the OTP verification, so Needle never collects it."),
    ("residential_address", "Residential Address", True, f"Mandatory, at most {ADDRESS_MAX_CHARS} characters."),
    ("mobile_2", "Mobile No. 2", False, "Optional."),
    ("email", "Email", False, "Optional."),
)
GRIEVANCE_FIELDS = (
    ("department", "Department", True, "Mandatory (90 departments)."),
    ("category", "Grievance Category", True, "Mandatory; the list depends on the department."),
    ("location", "Location", True, "Mandatory; the list depends on the department (and category)."),
    ("grievance_details", "Grievance Details", True, "Mandatory; maximum length NOT verified."),
    ("grievance_area_address", "Grievance Area Address", True, f"Mandatory, at most {ADDRESS_MAX_CHARS} characters."),
    ("old_reference_number", "Reference No 1 (old reference)", False, "Optional; revealed by the portal's old-reference tick box."),
    ("supporting_document", "Supporting document", False, "Optional; PDF only, at most 1 MB, restricted file name."),
)

SOURCE_AI = "ai_suggested"
SOURCE_STAFF_CONFIRMED = "staff_confirmed"
SOURCE_STAFF_TYPED = "staff_typed_unverified"
SELECTION_SOURCES = (SOURCE_AI, SOURCE_STAFF_CONFIRMED, SOURCE_STAFF_TYPED)

# Filing record states used in audit payloads / API responses. Deliberately NOT a new cases.govt_status value.
STATE_STAFF_REPORTED_FILED = "staff_reported_filed"
STATE_VERIFIED_BY_PORTAL = "verified_by_portal"   # reserved: only a real, authorised portal lookup may ever set this


def field_rules() -> dict:
    """Single source of truth for the UI (counters, attachment pre-check, labels)."""
    return {
        "address_max_chars": ADDRESS_MAX_CHARS,
        "grievance_details": {
            "portal_max_chars": None,
            "portal_max_verified": False,
            "soft_warn_chars": GRIEVANCE_DETAILS_SOFT_WARN_CHARS,
            "special_chars_notice": GRIEVANCE_DETAILS_SPECIAL_CHARS_NOTICE,
        },
        "attachment": {
            "content_type": "application/pdf",
            "extension": ".pdf",
            "max_bytes": ATTACHMENT_MAX_BYTES,
            "max_name_chars": ATTACHMENT_MAX_NAME_CHARS,
            "forbidden_name_chars": ATTACHMENT_FORBIDDEN_NAME_CHARS,
            "no_spaces": True, "no_parentheses": True, "no_double_dots": True,
        },
        "applicant_fields": [{"key": k, "label": l, "mandatory": m, "note": n} for k, l, m, n in APPLICANT_FIELDS],
        "grievance_fields": [{"key": k, "label": l, "mandatory": m, "note": n} for k, l, m, n in GRIEVANCE_FIELDS],
    }


# ── Catalogue ──────────────────────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _load_catalogue() -> dict:
    with open(CATALOGUE_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def reload_catalogue() -> None:
    """Test hook / after a data refresh."""
    _load_catalogue.cache_clear()


def catalogue_meta() -> dict:
    cat = _load_catalogue()
    return {
        "portal": cat.get("portal"),
        "source": cat.get("source"),
        "ids_policy": cat.get("ids_policy"),
        "text_policy": cat.get("text_policy"),
        "department_count": len(cat.get("departments", [])),
        "category_row_count": sum(len(d.get("categories") or []) for d in cat.get("departments", [])),
        "departments_complete": sum(1 for d in cat.get("departments", []) if (d.get("catalogue") or {}).get("complete") and d.get("categories")),
        "departments_partial": sum(1 for d in cat.get("departments", []) if not ((d.get("catalogue") or {}).get("complete") and d.get("categories"))),
    }


def _catalogue_summary(d: dict) -> dict:
    """Completeness + provenance metadata shared by the department list and the per-department category response."""
    cat = d.get("catalogue") or {}
    cats = d.get("categories") or []
    complete = bool(cat.get("complete")) and bool(cats)
    return {
        "portal_option_value_observed": d.get("portal_option_value_observed"),   # department dropdown value as observed; NOT a category ID
        "categories_status": cat.get("status"),
        "categories_complete": complete,
        "capture_status": cat.get("capture_status") or ("complete" if complete else ("partial" if cats else "not_captured")),
        "unverified_row_count": cat.get("unverified_row_count") or 0,
        "categories_note": cat.get("complete_note"),
        "captured_at_utc": cat.get("captured_at_utc"),
        "form_comparison": cat.get("form_comparison"),
    }


def _department_entry(name) -> dict | None:
    name = (name or "").strip() if isinstance(name, str) else ""
    if not name:
        return None
    for d in _load_catalogue().get("departments", []):
        if d.get("name") == name:     # exact portal text only: no case-folding, no fuzzy matching
            return d
    return None


def list_departments() -> list[dict]:
    """Departments in the portal's own order, with completeness metadata and NO category rows."""
    out = []
    for d in _load_catalogue().get("departments", []):
        loc = d.get("locations") or {}
        out.append({
            "name": d["name"],
            **_catalogue_summary(d),
            "category_count": len(d.get("categories") or []),
            "locations_status": loc.get("status"),
            "location_count": len(loc.get("items") or []),
        })
    return out


def get_categories(department: str) -> dict | None:
    d = _department_entry(department)
    if not d:
        return None
    cat = d.get("catalogue") or {}
    loc = d.get("locations") or {}
    cats = d.get("categories") or []
    return {
        "department": d["name"],
        **_catalogue_summary(d),
        "capture_notes": cat.get("capture_notes") or [],
        "verification_summary": cat.get("verification_summary") or {},
        "categories": cats,           # portal order, verbatim
        "locations_status": loc.get("status"),
        "locations": loc.get("items") or [],
    }


def category_in_catalogue(department: str, category: str) -> bool:
    d = _department_entry(department)
    if not d or not isinstance(category, str):
        return False
    wanted = category.strip()
    return any(c.get("text") == wanted or c.get("text_raw") == wanted for c in d.get("categories") or [])


def location_in_catalogue(department: str, location: str) -> bool:
    d = _department_entry(department)
    if not d or not isinstance(location, str):
        return False
    return location.strip() in [str(x) for x in ((d.get("locations") or {}).get("items") or [])]


# ── Validation ─────────────────────────────────────────────────────────────────────────────────────
def _issue(field, code, message):
    return {"field": field, "code": code, "message": message}


def validate_attachment(filename, size_bytes, content_type=None) -> dict:
    """Pre-check ONLY the verified restrictions of the optional supporting document. Needle never uploads it;
    staff attach it on the portal themselves."""
    errors = []
    name = filename if isinstance(filename, str) else ""
    if not name.strip():
        errors.append(_issue("supporting_document", "filename_missing", "The file has no name."))
        return {"ok": False, "errors": errors, "warnings": []}
    if not name.lower().endswith(".pdf"):
        errors.append(_issue("supporting_document", "not_pdf", "Only PDF files are accepted by the portal."))
    if content_type and content_type.split(";")[0].strip().lower() not in ("application/pdf", "application/x-pdf"):
        errors.append(_issue("supporting_document", "not_pdf", "Only PDF files are accepted by the portal."))
    if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0:
        errors.append(_issue("supporting_document", "size_unknown", "The file size is missing, so the 1 MB limit cannot be checked."))
    elif size_bytes > ATTACHMENT_MAX_BYTES:
        errors.append(_issue("supporting_document", "too_large", "The portal accepts a PDF of at most 1 MB."))
    if " " in name:
        errors.append(_issue("supporting_document", "name_has_space", "The file name must not contain spaces."))
    if "(" in name or ")" in name:
        errors.append(_issue("supporting_document", "name_has_parentheses", "The file name must not contain parentheses."))
    if ".." in name:
        errors.append(_issue("supporting_document", "name_has_double_dots", "The file name must not contain '..'."))
    bad = sorted({ch for ch in name if ch in ATTACHMENT_FORBIDDEN_NAME_CHARS})
    if bad:
        errors.append(_issue("supporting_document", "name_has_special_chars",
                             "The file name contains characters the portal does not allow: " + " ".join(bad)))
    if len(name) > ATTACHMENT_MAX_NAME_CHARS:
        errors.append(_issue("supporting_document", "name_too_long", "The file name must be shorter than 100 characters."))
    return {"ok": not errors, "errors": errors, "warnings": []}


def _s(payload, key) -> str:
    v = payload.get(key)
    return v.strip() if isinstance(v, str) else ""


def _selection_source(payload, key):
    sel = payload.get("selection_sources")
    return sel.get(key) if isinstance(sel, dict) else None


def validate_filing(payload: dict) -> dict:
    """Validate a Delhi filing worksheet. Returns {"ok", "errors", "warnings", "notices", "ready_to_file"}.

    `ok`/`ready_to_file` mean ONLY "the verified portal rules are satisfied" — not that anything was filed or
    that the portal will accept it. Incomplete catalogues produce warnings, never errors."""
    payload = payload if isinstance(payload, dict) else {}
    errors, warnings, notices = [], [], []
    group = payload.get("group_grievance") is True

    for key, label, mandatory, _ in APPLICANT_FIELDS:
        if key == "mobile_1":
            continue  # prefilled by the portal from the OTP login; Needle does not collect it
        if not mandatory:
            continue
        if group and key in ("father_husband_name", "gender"):
            continue  # the portal disables these for a Group Grievance
        if not _s(payload, key):
            errors.append(_issue(key, "required", f"{label} is required by the portal."))
    for key in ("residential_address", "grievance_area_address"):
        v = payload.get(key)
        if isinstance(v, str) and len(v.strip()) > ADDRESS_MAX_CHARS:
            label = "Residential Address" if key == "residential_address" else "Grievance Area Address"
            errors.append(_issue(key, "too_long", f"{label} can have at most {ADDRESS_MAX_CHARS} characters (now {len(v.strip())})."))

    # Department / category / location
    dept = _s(payload, "department")
    entry = _department_entry(dept) if dept else None
    if not dept:
        errors.append(_issue("department", "required", "Department is required by the portal."))
    elif not entry:
        errors.append(_issue("department", "not_in_catalogue", "This is not one of the 90 department names on the portal. Pick it from the list."))

    cat = _s(payload, "category")
    if not cat:
        errors.append(_issue("category", "required", "Grievance Category is required by the portal."))
    elif entry:
        if (entry.get("categories") or []):
            if not category_in_catalogue(dept, cat):
                # Never a hard block, partial catalogue or not: the list comes from the PUBLIC mapping page, which has not
                # been compared with the filing form's own dropdown, so it cannot prove a category is absent from the form.
                # The value is recorded as staff_typed_unverified (see normalise_selection_sources).
                if (entry.get("catalogue") or {}).get("complete"):
                    warnings.append(_issue("category", "not_in_catalogue_unverified",
                                           "This category is not in Needle's copy of the portal's mapping list for this department. That list has not been compared with the filing form, so it is not blocked. Check it on the portal and type it exactly as the portal shows it. It is recorded as typed by staff and unverified."))
                else:
                    warnings.append(_issue("category", "not_in_partial_catalogue",
                                           "Needle's category list for this department is partial, so it cannot confirm this category. Check it on the portal and type it exactly as the portal shows it. It is recorded as typed by staff and unverified."))
        else:
            warnings.append(_issue("category", "catalogue_not_captured",
                                   "Needle has not captured this department's category list. Choose the category on the portal and type it here exactly as the portal shows it."))
    src = _selection_source(payload, "category")
    if cat and src == SOURCE_AI:
        errors.append(_issue("category", "ai_suggestion_unconfirmed", "The category is only an AI suggestion. Staff must confirm it."))
    if dept and _selection_source(payload, "department") == SOURCE_AI:
        errors.append(_issue("department", "ai_suggestion_unconfirmed", "The department is only an AI suggestion. Staff must confirm it."))

    loc = _s(payload, "location")
    if not loc:
        errors.append(_issue("location", "required", "Location is required by the portal."))
    elif entry:
        loc_items = (entry.get("locations") or {}).get("items") or []
        if loc_items:
            if not location_in_catalogue(dept, loc):
                errors.append(_issue("location", "not_in_catalogue", "This location is not in the portal's list for this department. Pick it from the list, exactly as shown."))
        else:
            warnings.append(_issue("location", "catalogue_not_captured",
                                   "Needle has not captured this department's location list. Choose the location on the portal and type it here exactly as the portal shows it."))
    if loc and _selection_source(payload, "location") == SOURCE_AI:
        errors.append(_issue("location", "ai_suggestion_unconfirmed", "The location is only an AI suggestion. Staff must confirm it."))

    # Grievance details: mandatory, maximum UNKNOWN => warning only
    gd = _s(payload, "grievance_details")
    if not gd:
        errors.append(_issue("grievance_details", "required", "Grievance Details is required by the portal."))
    else:
        if len(gd) > GRIEVANCE_DETAILS_SOFT_WARN_CHARS:
            warnings.append(_issue("grievance_details", "long_unknown_limit",
                                   f"Grievance Details is {len(gd)} characters. The portal's maximum is not known; if the portal's counter shows it is too long, shorten it there."))
        notices.append(_issue("grievance_details", "special_characters_note", GRIEVANCE_DETAILS_SPECIAL_CHARS_NOTICE))
    if not _s(payload, "grievance_area_address"):
        errors.append(_issue("grievance_area_address", "required", "Grievance Area Address is required by the portal."))

    # Optional attachment metadata (never the file itself)
    att = payload.get("attachment")
    if isinstance(att, dict):
        r = validate_attachment(att.get("filename"), att.get("size_bytes"), att.get("content_type"))
        errors.extend(r["errors"])
    elif att is not None:
        errors.append(_issue("supporting_document", "bad_metadata", "Attachment details were not understood."))

    if payload.get("old_reference_number") not in (None, "") and not isinstance(payload.get("old_reference_number"), str):
        errors.append(_issue("old_reference_number", "bad_value", "The old reference number must be text."))

    ok = not errors
    return {"ok": ok, "ready_to_file": ok, "errors": errors, "warnings": warnings, "notices": notices}


def normalise_selection_sources(payload: dict) -> dict:
    """Return department/category/location provenance, derived server-side so the client cannot claim
    `staff_confirmed` for a value that is not in the catalogue.

      * a catalogue-exact value the client marked staff_confirmed -> staff_confirmed
      * a value NOT in a captured catalogue                       -> staff_typed_unverified (or the field is rejected by validate_filing)
      * anything the client marked ai_suggested                   -> ai_suggested (stays unconfirmed)
    """
    payload = payload if isinstance(payload, dict) else {}
    claimed = payload.get("selection_sources") if isinstance(payload.get("selection_sources"), dict) else {}
    dept = _s(payload, "department")
    out = {}
    for key, check in (("department", None), ("category", category_in_catalogue), ("location", location_in_catalogue)):
        val = _s(payload, key)
        if not val:
            continue
        claim = claimed.get(key)
        if claim == SOURCE_AI:
            out[key] = SOURCE_AI
            continue
        if key == "department":
            out[key] = SOURCE_STAFF_CONFIRMED if _department_entry(val) else SOURCE_STAFF_TYPED
            continue
        out[key] = SOURCE_STAFF_CONFIRMED if check(dept, val) else SOURCE_STAFF_TYPED
    return out


# Reference recorded by staff (the acknowledgement/complaint number from the portal)
def filing_record_state(*, has_reference: bool, verified_by_portal: bool = False) -> str | None:
    """`verified_by_portal` can only be true after an authorised real portal lookup, which Needle does not
    perform. It is a parameter so the distinction exists in one place and is tested."""
    if verified_by_portal:
        return STATE_VERIFIED_BY_PORTAL
    return STATE_STAFF_REPORTED_FILED if has_reference else None
