"""
tests/test_govt_delhi_filing.py — Delhi filing catalogue + validation rules (pure logic, no app, no network).

Local, synthetic tests only: nothing here contacts the Delhi portal. The catalogue under test is the
captured data in modules/data/delhi_catalogue.json.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.govt_sync import delhi_filing as df  # noqa: E402


def _ok_payload(**over):
    p = {
        "group_grievance": False,
        "applicant_name": "Test Applicant", "father_husband_name": "Test Father", "gender": "Male",
        "residential_address": "1 Test Street, Delhi",
        "department": "Delhi Police", "category": "Abuse of Power", "location": "Some Constituency",
        "grievance_details": "Synthetic grievance text for a test.",
        "grievance_area_address": "Test Colony, Delhi",
    }
    p.update(over)
    return p


def _codes(res, kind="errors"):
    return {(i["field"], i["code"]) for i in res[kind]}


# ── Catalogue integrity ─────────────────────────────────────────────────────────────────────────────
def test_catalogue_has_exactly_90_unique_departments_in_portal_order():
    deps = df.list_departments()
    names = [d["name"] for d in deps]
    assert len(names) == 90 and len(set(names)) == 90
    assert "Delhi Police" in names
    assert df.catalogue_meta()["department_count"] == 90


def test_no_invented_identifiers_anywhere():
    raw = open(df.CATALOGUE_PATH, encoding="utf-8").read()
    data = json.loads(raw)
    forbidden = {"id", "dept_id", "department_id", "category_id", "code", "department_code", "category_code"}
    for d in data["departments"]:
        assert not (forbidden & set(d)), d["name"]
        for c in d["categories"]:
            assert not (forbidden & set(c))
    assert "invent" in data["ids_policy"].lower()


def test_delhi_police_capture_is_all_369_rows_in_order():
    info = df.get_categories("Delhi Police")
    cats = info["categories"]
    assert len(cats) == 369
    assert [c["seq"] for c in cats] == list(range(1, 370))
    assert len({c["text"] for c in cats}) == 369            # no duplicate texts
    assert cats[0]["text"] == "Abuse of Power"
    assert cats[-1]["text"] == "Violation of traffic rules, traffic"


def test_every_police_row_has_three_levels_and_disposal_days():
    for c in df.get_categories("Delhi Police")["categories"]:
        for lvl, days in (("l1", 21), ("l2", 10), ("l3", 10)):
            assert c[lvl]["post"].strip(), (c["seq"], lvl)
            assert c[lvl]["disposal_days"] == days, (c["seq"], lvl)
            assert "post_raw" in c[lvl]


def test_portal_typos_are_preserved_not_corrected():
    texts = [c["text"] for c in df.get_categories("Delhi Police")["categories"]]
    assert any("Rullings" in t for t in texts)           # the portal's own spelling
    assert any(t.endswith("Provisional & Logistics (P&L)") for t in texts)


def test_delhi_police_is_partial_with_19_long_cells_not_text_verified():
    info = df.get_categories("Delhi Police")
    assert info["categories_complete"] is False and info["capture_status"] == "partial"
    assert info["categories_status"] == "captured_partial_verification"
    assert info["unverified_row_count"] == 19
    assert info["form_comparison"] == "pending"
    assert "PARTIAL" in info["categories_note"] and "not proof" in info["categories_note"]
    flagged = [c["seq"] for c in info["categories"] if c["verification"] == "screenshot_repaired_not_text_verified"]
    assert flagged == [186, 194, 204, 209, 215, 221, 232, 247, 262, 268, 277, 310, 318, 326, 337, 349, 361, 362, 367]
    assert info["verification_summary"]["screenshot_repaired_not_text_verified"] == 19


# ── All 90 departments / 1,814 category rows ────────────────────────────────────────────────────────
def test_all_90_departments_have_captured_categories_and_only_police_is_partial():
    deps = df.list_departments()
    assert len(deps) == 90
    assert sum(d["category_count"] for d in deps) == 1814
    assert all(d["category_count"] >= 1 for d in deps)
    partial = [d["name"] for d in deps if not d["categories_complete"]]
    assert partial == ["Delhi Police"]
    assert all(d["locations_status"] == "not_captured" and d["location_count"] == 0 for d in deps)   # never assumed
    meta = df.catalogue_meta()
    assert (meta["category_row_count"], meta["departments_complete"], meta["departments_partial"]) == (1814, 89, 1)


def test_every_department_returns_its_rows_in_portal_order_with_authorities_and_days():
    for d in df.list_departments():
        info = df.get_categories(d["name"])
        cats = info["categories"]
        assert len(cats) == d["category_count"] > 0, d["name"]
        assert [c["seq"] for c in cats] == list(range(1, len(cats) + 1)), d["name"]       # S.No. order as displayed
        for c in cats:
            assert c["text_raw"] and c["text"] == c["text_raw"], (d["name"], c["seq"])     # nothing decoded or corrected
            for lvl in ("l1", "l2", "l3"):
                assert c[lvl]["post"].strip() and c[lvl]["post"] == c[lvl]["post_raw"], (d["name"], c["seq"], lvl)
                assert isinstance(c[lvl]["disposal_days"], int)
            assert c["verification"]


def test_department_option_values_are_department_values_not_category_ids():
    deps = {d["name"]: d for d in df.list_departments()}
    assert deps["Delhi Police"]["portal_option_value_observed"] == "1"
    assert deps["Delhi Jal Board"]["portal_option_value_observed"] == "227420"
    assert deps["Delhi Commission for Women"]["portal_option_value_observed"] == "227460"
    assert len({d["portal_option_value_observed"] for d in deps.values()}) == 90
    for d in json.load(open(df.CATALOGUE_PATH, encoding="utf-8"))["departments"]:
        for c in d["categories"]:
            assert "portal_option_value_observed" not in c and not ({"id", "category_id", "code"} & set(c))


def test_djb_and_dcw_recaptures():
    assert len(df.get_categories("Delhi Jal Board")["categories"]) == 15
    dcw = df.get_categories("Delhi Commission for Women")["categories"]
    assert len(dcw) == 1
    assert dcw[0]["text"].startswith("Dowry, Domestic Violence, Divorce")
    assert (dcw[0]["l1"]["post"], dcw[0]["l2"]["post"], dcw[0]["l3"]["post"]) == ("Assistant Secretary", "Member Secretary", "Chairperson")


def test_portal_spelling_entities_and_duplicates_are_preserved_verbatim():
    ar = [c["text"] for c in df.get_categories("Administrative Reforms Department")["categories"]]
    assert any("Miscellanoeous" in t for t in ar)                                          # portal spelling kept
    dsiidc = df.get_categories("Delhi State Industrial and Infrastructure Development Corporation")["categories"]
    assert dsiidc[10]["text_raw"] == "Issues of Salary Appointment PF ESI Gratuaty &amp;amp; others"   # entity text not decoded
    assert (dsiidc[10]["l1"]["disposal_days"], dsiidc[10]["l2"]["disposal_days"], dsiidc[10]["l3"]["disposal_days"]) == (10, 10, 10)
    rev = df.get_categories("Department of Revenue")["categories"]
    assert rev[40]["text"] == rev[41]["text"] == "Medical / Vaccination"                  # duplicates not merged
    assert df.category_in_catalogue("Department of Revenue", "Medical / Vaccination")


def test_partial_flag_is_per_department_and_row_level_is_exposed():
    info = df.get_categories("Delhi Jal Board")
    assert info["categories_complete"] is True and info["capture_status"] == "complete" and info["unverified_row_count"] == 0
    assert not any(c["verification"] == "screenshot_repaired_not_text_verified" for d in df.list_departments() if d["name"] != "Delhi Police"
                   for c in df.get_categories(d["name"])["categories"])


def test_lookup_is_exact_text_only():
    assert df.get_categories("delhi police") is None
    assert df.get_categories("Delhi Police ") is not None          # surrounding whitespace only is tolerated
    assert df.category_in_catalogue("Delhi Police", "Abuse of Power")
    assert not df.category_in_catalogue("Delhi Police", "abuse of power")
    assert not df.category_in_catalogue("Delhi Police", "Abuse of power (similar)")


# ── Mandatory fields ────────────────────────────────────────────────────────────────────────────────
def test_complete_individual_worksheet_is_ready():
    r = df.validate_filing(_ok_payload())
    assert r["ok"] and r["ready_to_file"] and not r["errors"]


@pytest.mark.parametrize("field", [
    "applicant_name", "father_husband_name", "gender", "residential_address", "department", "category",
    "location", "grievance_details", "grievance_area_address",
])
def test_each_mandatory_field_is_required(field):
    r = df.validate_filing(_ok_payload(**{field: "   "}))
    assert (field, "required") in _codes(r)
    assert not r["ready_to_file"]


def test_mobile_1_is_never_required_from_staff():
    r = df.validate_filing(_ok_payload())             # no mobile_1 key at all
    assert not any(e["field"] == "mobile_1" for e in r["errors"])


def test_optional_fields_may_be_empty():
    r = df.validate_filing(_ok_payload(mobile_2=None, email=None, old_reference_number=None))
    assert r["ok"]


def test_group_grievance_does_not_require_father_or_gender():
    r = df.validate_filing(_ok_payload(group_grievance=True, father_husband_name=None, gender=None))
    assert r["ok"], r["errors"]
    # the (group) name itself is still mandatory
    r2 = df.validate_filing(_ok_payload(group_grievance=True, applicant_name="", father_husband_name=None, gender=None))
    assert ("applicant_name", "required") in _codes(r2)


def test_individual_applicant_requires_father_and_gender():
    r = df.validate_filing(_ok_payload(father_husband_name=None, gender=None))
    assert {("father_husband_name", "required"), ("gender", "required")} <= _codes(r)


# ── Address limits ──────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("field", ["residential_address", "grievance_area_address"])
def test_address_limit_is_250_inclusive(field):
    assert df.validate_filing(_ok_payload(**{field: "a" * 250}))["ok"]
    r = df.validate_filing(_ok_payload(**{field: "a" * 251}))
    assert (field, "too_long") in _codes(r) and not r["ok"]


# ── Grievance details: maximum UNKNOWN => never an error ─────────────────────────────────────────────
def test_long_grievance_details_is_a_warning_not_an_error():
    r = df.validate_filing(_ok_payload(grievance_details="x" * 9000))
    assert r["ok"]
    assert ("grievance_details", "long_unknown_limit") in _codes(r, "warnings")


def test_grievance_details_always_carries_the_special_character_notice_but_rejects_nothing():
    r = df.validate_filing(_ok_payload(grievance_details="Road <broken> & 'bad' #1 50%"))
    assert r["ok"]
    assert ("grievance_details", "special_characters_note") in _codes(r, "notices")
    rules = df.field_rules()["grievance_details"]
    assert rules["portal_max_chars"] is None and rules["portal_max_verified"] is False


# ── Catalogue-driven selections ─────────────────────────────────────────────────────────────────────
def test_unknown_department_is_rejected():
    r = df.validate_filing(_ok_payload(department="Department of Imaginary Affairs"))
    assert ("department", "not_in_catalogue") in _codes(r)


def test_unknown_category_is_a_warning_even_for_a_complete_department_and_never_blocks():
    assert df.get_categories("Department of Revenue")["categories_complete"] is True
    r = df.validate_filing(_ok_payload(department="Department of Revenue", category="medical / vaccination"))     # wrong case
    assert r["ok"] and r["ready_to_file"], r["errors"]
    assert ("category", "not_in_catalogue_unverified") in _codes(r, "warnings")
    assert not [e for e in r["errors"] if e["field"] == "category"]
    assert "unverified" in next(w for w in r["warnings"] if w["code"] == "not_in_catalogue_unverified")["message"]
    # an exact catalogue value raises no category warning at all
    ok = df.validate_filing(_ok_payload(department="Department of Revenue", category="Medical / Vaccination"))
    assert ok["ok"] and not [w for w in ok["warnings"] if w["field"] == "category"]


def test_unknown_category_is_recorded_staff_typed_unverified_never_substituted_or_confirmed():
    p = _ok_payload(department="Department of Revenue", category="Not a listed category", selection_sources={"category": "staff_confirmed"})
    assert df.normalise_selection_sources(p)["category"] == df.SOURCE_STAFF_TYPED
    assert p["category"] == "Not a listed category"                                         # input untouched: nothing substituted
    # near-miss text is not auto-corrected to a similar category
    assert not df.category_in_catalogue("Department of Revenue", "Medical/Vaccination")


def test_ai_suggested_unknown_category_still_needs_staff_confirmation():
    r = df.validate_filing(_ok_payload(department="Department of Revenue", category="Not a listed category",
                                       selection_sources={"category": "ai_suggested"}))
    assert ("category", "ai_suggestion_unconfirmed") in _codes(r) and not r["ready_to_file"]
    assert ("category", "not_in_catalogue_unverified") in _codes(r, "warnings")


def test_partial_catalogue_never_blocks_a_category_it_cannot_confirm():
    # Delhi Police is partial: a category that is not in the list is a warning, not an error.
    r = df.validate_filing(_ok_payload(category="Abuse of power"))                       # wrong case
    assert r["ok"] and r["ready_to_file"], r["errors"]
    assert ("category", "not_in_partial_catalogue") in _codes(r, "warnings")
    assert ("category", "not_in_catalogue") not in _codes(r)
    s = df.normalise_selection_sources(_ok_payload(category="Abuse of power", selection_sources={"category": "staff_confirmed"}))
    assert s["category"] == df.SOURCE_STAFF_TYPED                                          # still not claimed as confirmed
    # an exact row from the partial list stays confirmable, including one of the 19 not-text-verified rows
    long_row = next(c for c in df.get_categories("Delhi Police")["categories"] if c["seq"] == 186)
    assert df.validate_filing(_ok_payload(category=long_row["text"]))["ok"]


@pytest.fixture
def dept_without_categories(monkeypatch):
    """A department whose category list is not captured (all 90 now have rows, so synthesise the empty case)."""
    import copy
    data = copy.deepcopy(df._load_catalogue())
    target = data["departments"][5]
    target["categories"] = []
    target["catalogue"] = {"status": "not_captured", "capture_status": "not_captured", "row_count": None, "complete": False,
                           "complete_note": "not captured", "form_comparison": "pending", "source": "mapping_page"}
    monkeypatch.setattr(df, "_load_catalogue", lambda: data)
    return target["name"]


def test_department_without_category_data_does_not_block_filing(dept_without_categories):
    dept = dept_without_categories
    info = df.get_categories(dept)
    assert info["categories"] == [] and info["categories_complete"] is False and info["capture_status"] == "not_captured"
    r = df.validate_filing(_ok_payload(department=dept, category="Typed exactly as the portal shows it"))
    assert r["ok"], r["errors"]
    assert ("category", "catalogue_not_captured") in _codes(r, "warnings")
    assert ("location", "catalogue_not_captured") in _codes(r, "warnings")
    assert df.normalise_selection_sources(_ok_payload(department=dept, category="Typed exactly as the portal shows it"))["category"] == df.SOURCE_STAFF_TYPED


def test_location_is_never_blocked_or_assumed_for_any_department():
    for d in df.list_departments():
        r = df.validate_filing(_ok_payload(department=d["name"], category=df.get_categories(d["name"])["categories"][0]["text"], location="Typed location"))
        assert r["ok"], (d["name"], r["errors"])
        assert ("location", "catalogue_not_captured") in _codes(r, "warnings")


def test_importer_marks_non_complete_capture_partial_and_invents_no_ids(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("import_delhi_catalogue", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "import_delhi_catalogue.py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    row = lambda i, t, v: {"seq": i, "category_text": t, "l1": {"post": "A", "disposal_days": 21}, "l2": {"post": "B", "disposal_days": 10},
                           "l3": {"post": "C", "disposal_days": 10}, "verification": v}
    cap = {"source_page": "https://example.invalid/page", "departments": [
        {"name": "D1", "portal_option_value_observed": "7", "row_count": 2, "capture_status": "complete", "captured_at_utc": "t", "source_page": "p", "capture_notes": [],
         "categories": [row(1, "Alpha &amp;amp; Beta", "page_text_full"), row(2, "Alpha &amp;amp; Beta", "page_text_full")]},
        {"name": "D2", "portal_option_value_observed": "8", "row_count": 1, "capture_status": "partial", "captured_at_utc": "t", "source_page": "p", "capture_notes": ["n"],
         "categories": [row(1, "Gamma", "screenshot_repaired_not_text_verified")]}]}
    out = mod.build(cap)
    d1, d2 = out["departments"]
    assert d1["catalogue"]["complete"] is True and d2["catalogue"]["complete"] is False and d2["catalogue"]["unverified_row_count"] == 1
    assert [c["text"] for c in d1["categories"]] == ["Alpha &amp;amp; Beta"] * 2           # not decoded, not merged
    assert d1["portal_option_value_observed"] == "7" and "id" not in d1 and "id" not in d1["categories"][0]
    assert (out["department_count"], out["category_row_count"], out["departments_partial"]) == (2, 3, 1)
    with pytest.raises(SystemExit):
        bad = json.loads(json.dumps(cap)); bad["departments"][0]["row_count"] = 5
        mod.build(bad)


def test_ai_suggestions_must_be_confirmed_by_staff():
    r = df.validate_filing(_ok_payload(selection_sources={"department": "ai_suggested", "category": "ai_suggested"}))
    assert {("department", "ai_suggestion_unconfirmed"), ("category", "ai_suggestion_unconfirmed")} <= _codes(r)
    assert not r["ready_to_file"]


def test_client_cannot_claim_staff_confirmed_for_an_uncatalogued_value():
    p = _ok_payload(category="Not a real category", selection_sources={"category": "staff_confirmed"})
    assert df.normalise_selection_sources(p)["category"] == df.SOURCE_STAFF_TYPED


def test_catalogue_exact_values_become_staff_confirmed_and_location_is_typed_when_uncaptured():
    s = df.normalise_selection_sources(_ok_payload(selection_sources={"department": "staff_confirmed"}))
    assert s["department"] == df.SOURCE_STAFF_CONFIRMED
    assert s["category"] == df.SOURCE_STAFF_CONFIRMED
    assert s["location"] == df.SOURCE_STAFF_TYPED


def test_ai_provenance_survives_normalisation():
    s = df.normalise_selection_sources(_ok_payload(selection_sources={"department": "ai_suggested"}))
    assert s["department"] == df.SOURCE_AI


# ── Attachment (PDF only, <= 1 MB, restricted file name) ────────────────────────────────────────────
def test_valid_pdf_passes():
    assert df.validate_attachment("proof_1.pdf", 1024 * 1024, "application/pdf")["ok"]


@pytest.mark.parametrize("name,size,ctype,code", [
    ("proof.docx", 100, None, "not_pdf"),
    ("proof.pdf", 100, "image/png", "not_pdf"),
    ("proof.pdf", 1024 * 1024 + 1, "application/pdf", "too_large"),
    ("my proof.pdf", 100, None, "name_has_space"),
    ("proof(1).pdf", 100, None, "name_has_parentheses"),
    ("proof..pdf", 100, None, "name_has_double_dots"),
    ("a" * 96 + ".pdf", 100, None, "name_too_long"),
])
def test_attachment_rules(name, size, ctype, code):
    r = df.validate_attachment(name, size, ctype)
    assert code in {e["code"] for e in r["errors"]} and not r["ok"]


@pytest.mark.parametrize("ch", list(df.ATTACHMENT_FORBIDDEN_NAME_CHARS))
def test_each_listed_forbidden_filename_character_is_rejected(ch):
    r = df.validate_attachment(f"pro{ch}of.pdf", 100)
    assert "name_has_special_chars" in {e["code"] for e in r["errors"]}


def test_exactly_99_character_name_is_allowed_and_100_is_not():
    assert df.validate_attachment("a" * 95 + ".pdf", 100)["ok"]           # 99
    assert not df.validate_attachment("a" * 96 + ".pdf", 100)["ok"]        # 100


def test_attachment_size_must_be_known():
    r = df.validate_attachment("proof.pdf", None)
    assert "size_unknown" in {e["code"] for e in r["errors"]}


def test_attachment_metadata_flows_through_worksheet_validation():
    r = df.validate_filing(_ok_payload(attachment={"filename": "bad name.pdf", "size_bytes": 10, "content_type": "application/pdf"}))
    assert ("supporting_document", "name_has_space") in _codes(r)


# ── Verification vocabulary ─────────────────────────────────────────────────────────────────────────
def test_reference_alone_is_staff_reported_never_verified():
    assert df.filing_record_state(has_reference=True) == df.STATE_STAFF_REPORTED_FILED
    assert df.filing_record_state(has_reference=False) is None
    assert df.STATE_STAFF_REPORTED_FILED != df.STATE_VERIFIED_BY_PORTAL


def test_field_rules_expose_the_verified_limits_only():
    rules = df.field_rules()
    assert rules["address_max_chars"] == 250
    assert rules["attachment"]["max_bytes"] == 1048576
    labels = {f["label"] for f in rules["applicant_fields"]} | {f["label"] for f in rules["grievance_fields"]}
    assert {"Name", "Father/Husband Name", "Gender", "Mobile No. 1", "Residential Address", "Mobile No. 2", "Email",
            "Department", "Grievance Category", "Location", "Grievance Details", "Grievance Area Address"} <= labels
