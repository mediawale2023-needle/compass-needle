"""Staff Overview Presence Map: mapped localities, distinct people, gazetteer places with no contact."""
import json
import os
import sys
from datetime import datetime

os.environ.setdefault("JWT_SECRET", "test-secret-key-32-characters-minimum-ok")
os.environ.setdefault("ENV", "test")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.dashboard_overview import OverviewDeps, presence_map, presence_status  # noqa: E402


def _deps(places, calls=None):
    def q(sql, params):
        if calls is not None:
            calls.append(params)
        return [{"canonical_name": p} for p in places]
    return OverviewDeps(q=q, q_one=lambda *a: {}, group_bundles=lambda *a, **k: [], coerce_iso=lambda v: v,
                        coerce_datetime=lambda v: v, utcnow=datetime.utcnow,
                        parse_meta=lambda m: json.loads(m) if isinstance(m, str) else (m or {}))


def _case(phone, loc, status="new"):
    return {"user_phone": phone, "status": status, "case_metadata": json.dumps({"matched_value": loc} if loc else {})}


def test_counts_distinct_people_per_mapped_locality_and_lists_untouched_places():
    cases = [_case(f"+91{i}", "Tilakwadi") for i in range(11)] + [_case("+910", "Tilakwadi")]   # 11 people, 12 complaints
    cases += [_case("+9150", "Shahapur"), _case("+9151", "Shahapur"), _case("+9152", "Shahapur")]
    cases += [_case("+9160", "Khasbag")]
    cases += [_case("+9170", "Anagol", status="irrelevant")]          # spam is not presence
    cases += [_case("+9180", "")]                                      # unmapped: not a locality
    calls = []
    out = presence_map(cases, {"constituency": "Belgaum Dakshin", "seat_type": "mla"}, _deps(["Tilakwadi", "Udyambag", "Angol"], calls))
    assert [(l["name"], l["people"], l["complaints"], l["status"]) for l in out["localities"]] == [
        ("Tilakwadi", 11, 12, "strong"), ("Shahapur", 3, 3, "growing"), ("Khasbag", 1, 1, "thin"),
        ("Angol", 0, 0, "none"), ("Udyambag", 0, 0, "none"),
    ]
    assert (out["with_presence"], out["total"], out["gazetteer_known"]) == (3, 5, True)
    assert calls[0] == {"st": "mla", "sn": "Belgaum Dakshin"}
    assert "+91" not in json.dumps(out)                                 # people are counted, never listed


def test_without_a_locality_list_only_contacted_places_show():
    out = presence_map([_case("+911", "Camp")], {"constituency": "", "seat_type": "mp"}, _deps(["Should not load"]))
    assert out == {"localities": [{"name": "Camp", "people": 1, "complaints": 1, "status": "thin"}],
                   "with_presence": 1, "total": 1, "gazetteer_known": False}


def test_status_thresholds():
    assert [presence_status(n) for n in (0, 1, 2, 3, 9, 10)] == ["none", "thin", "thin", "growing", "growing", "strong"]
