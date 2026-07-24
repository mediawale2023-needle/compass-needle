"""Relation parsing: (relation, anchor) split for Indian complaint language."""
from modules.geo_relations import parse_location_phrase


def test_hindi_ke_paas():
    parsed = parse_location_phrase("Gandhi Nagar ke paas")
    assert parsed["relation"] == "near"
    assert parsed["anchor"] == "Gandhi Nagar"


def test_hindi_ke_peeche_with_filler_tail():
    # The classic fragment source: "bus stand ke peeche wale compound mein".
    # The anchor is the bus stand; the tail is descriptive noise, not a place.
    parsed = parse_location_phrase("bus stand ke peeche wale compound mein")
    assert parsed["relation"] == "behind"
    assert parsed["anchor"] == "bus stand"


def test_hindi_ke_saamne():
    parsed = parse_location_phrase("mandir ke saamne")
    assert parsed["relation"] == "front"
    assert parsed["anchor"] == "mandir"


def test_english_behind():
    parsed = parse_location_phrase("behind the water tank")
    assert parsed["relation"] == "behind"
    assert parsed["anchor"] == "water tank"


def test_english_in_front_of():
    parsed = parse_location_phrase("in front of Unique Colony")
    assert parsed["relation"] == "front"
    assert parsed["anchor"] == "Unique Colony"


def test_english_opposite():
    parsed = parse_location_phrase("opposite to the bus stand")
    assert parsed["relation"] == "opposite"
    assert parsed["anchor"] == "bus stand"


def test_marathi_javal():
    parsed = parse_location_phrase("Tilakwadi javal")
    assert parsed["relation"] == "near"
    assert parsed["anchor"] == "Tilakwadi"


def test_kannada_hattira():
    parsed = parse_location_phrase("school hattira")
    assert parsed["relation"] == "near"
    assert parsed["anchor"] == "school"


def test_no_relation_passthrough():
    parsed = parse_location_phrase("Unique Colony")
    assert parsed["relation"] is None
    assert parsed["anchor"] == "Unique Colony"


def test_plain_place_containing_marker_like_word_not_split():
    # "Samorpur" contains "samor" but is not "X samor" — must not split.
    parsed = parse_location_phrase("Samorpur")
    assert parsed["relation"] is None
    assert parsed["anchor"] == "Samorpur"


def test_empty_input():
    parsed = parse_location_phrase("")
    assert parsed["relation"] is None
    assert parsed["anchor"] == ""
