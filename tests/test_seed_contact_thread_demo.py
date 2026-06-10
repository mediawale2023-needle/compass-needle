from types import SimpleNamespace

import pytest

from scripts import seed_contact_thread_demo as seed_demo


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, *_args, **_kwargs):
        return _FakeResult(self._rows)


def test_build_demo_cases_stays_in_one_assembly():
    cases = seed_demo._build_demo_cases(10, demo_assembly="Belgaum South")

    assert cases
    assert {case["assembly"] for case in cases} == {"Belgaum South"}
    assert {case["assembly_constituency"] for case in cases} == {"Belgaum South"}


def test_resolve_demo_assembly_uses_single_matching_geography_row():
    tenant = SimpleNamespace(id=10, seat_type="mla", constituency="Belgaum Dakshin")
    args = SimpleNamespace(demo_assembly=None)
    db = _FakeDB([("mla:Belgaum Dakshin/Belgaum South",)])

    resolved = seed_demo._resolve_demo_assembly(db, tenant, args)

    assert resolved == "Belgaum South"


def test_resolve_demo_assembly_requires_explicit_choice_for_ambiguous_mla_scope():
    tenant = SimpleNamespace(id=10, seat_type="mla", constituency="Belgaum Dakshin")
    args = SimpleNamespace(demo_assembly=None)
    db = _FakeDB(
        [
            ("mla:Belgaum Dakshin/Belgaum South",),
            ("mla:Belgaum Dakshin/Yellur",),
        ]
    )

    with pytest.raises(ValueError) as exc:
        seed_demo._resolve_demo_assembly(db, tenant, args)

    assert "ambiguous MLA geography assemblies" in str(exc.value)
