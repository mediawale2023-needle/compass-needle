from modules.whatsapp_geography import finalize_geography_decision


def _resolver(mapping):
    def _resolve(text, scope_parliamentary=None, tenant_id=None):
        return mapping.get(text, {"location_resolved": False})

    return _resolve


def _resolve_constituency(_location, _tenant_id):
    return None, None


def _decision(message, ai_payload=None, status="awaiting_location", reply="please tell village/ward"):
    ai_payload = ai_payload or {}
    return finalize_geography_decision(
        grievance=ai_payload.get("grievance_data", {}).copy(),
        ai_result=ai_payload,
        status=status,
        political_reply=reply,
        detected_language="Marathi",
        message_body=message,
        current_tenant=2,
        is_emergency_complaint=False,
        resolve_location_fn=_resolver({
            "Shahapur madhe rasta kharab aahe": {
                "location_resolved": True,
                "matched_value": "Shahapur",
                "assembly_constituency": "Belgaum Dakshin",
                "confidence": "high",
            },
            "Tilakwadi madhe rasta kharab aahe": {
                "location_resolved": True,
                "matched_value": "Tilakwadi",
                "assembly_constituency": "Belgaum Dakshin",
                "confidence": "high",
            },
            "Meerapur Galli Shahapur madhe light nhi": {
                "location_resolved": True,
                "matched_value": "Meerapur Galli Shahapur",
                "assembly_constituency": "Belgaum Dakshin",
                "confidence": "high",
            },
        }),
        resolve_constituency_fn=_resolve_constituency,
        get_tenant_constituency_fn=lambda _tenant_id: "Belagavi",
        assembly_belongs_to_parliamentary_fn=lambda assembly, constituency: assembly in {
            "Belgaum Dakshin",
            "Belgaum Uttar",
            "Belgaum Rural",
        } and constituency == "Belagavi",
    )


def test_raw_geography_overrides_stale_missing_location_reply():
    result = _decision("Tilakwadi madhe rasta kharab aahe")

    assert result["status"] == "new"
    assert result["location_name"] == "Tilakwadi"
    assert result["final_constituency"] == "Belgaum Dakshin"
    assert result["grievance"]["geography_confidence"] == "exact"
    assert result["grievance"]["geography_source"] == "raw_message"
    assert result["political_reply"].startswith("Ji,")
    assert "ward" not in result["political_reply"].lower()


def test_resolved_marathi_message_gets_marathi_ack_even_if_ai_claims_hindi():
    result = _decision(
        "Tilakwadi madhe rasta kharab aahe",
        ai_payload={"detected_language": "Hindi", "grievance_data": {}},
        status="awaiting_location",
        reply="Ji, maine Tilakwadi mein paani ki samasya note ki hai.",
    )

    assert result["status"] == "new"
    assert result["location_name"] == "Tilakwadi"
    assert result["political_reply"].startswith("Ji,")
    assert "Tumcha sandesh" in result["political_reply"]
    assert "Ji, maine" not in result["political_reply"]


def test_location_is_saved_at_user_level_not_polling_detail():
    result = _decision("Shahapur madhe rasta kharab aahe")

    assert result["location_name"] == "Shahapur"
    assert result["grievance"]["location"] == "Shahapur"
    assert result["final_constituency"] == "Belgaum Dakshin"


def test_location_preserves_user_supplied_detail():
    result = _decision("Meerapur Galli Shahapur madhe light nhi")

    assert result["location_name"] == "Meerapur Galli Shahapur"
    assert result["grievance"]["location"] == "Meerapur Galli Shahapur"
    assert result["final_constituency"] == "Belgaum Dakshin"


def test_resolver_hint_does_not_leak_into_reply_or_saved_location():
    result = finalize_geography_decision(
        grievance={},
        ai_result={},
        status="awaiting_location",
        political_reply="please tell village/ward",
        detected_language="Kannada",
        message_body="ಸದಾಶಿವ ನಗರದಲ್ಲಿ ನೀರಿಲ್ಲ ಸ್ವಲ್ಪ ನೋಡಬೇಕು",
        resolver_message_body="ಸದಾಶಿವ ನಗರದಲ್ಲಿ ನೀರಿಲ್ಲ ಸ್ವಲ್ಪ ನೋಡಬೇಕು\n\nLocation: Sadashivanagar / ಸದಾಶಿವ ನಗರ",
        current_tenant=2,
        is_emergency_complaint=False,
        resolve_location_fn=lambda text, **_kwargs: {
            "location_resolved": "Location:" in text,
            "matched_value": "Sadashiv Nagar",
            "assembly_constituency": "Belgaum Uttar",
            "confidence": "db_alias_boundary",
        },
        resolve_constituency_fn=lambda *_args, **_kwargs: (None, None),
        get_tenant_constituency_fn=lambda _tenant_id: "Belagavi",
    )

    assert result["status"] == "new"
    assert result["location_name"] == "Sadashiv Nagar"
    assert result["final_constituency"] == "Belgaum Uttar"
    assert result["grievance"]["geography_confidence"] == "boundary"
    assert "Location:" not in result["political_reply"]
    assert "ಸದಾಶಿವ ನಗರ" not in result["political_reply"]
    assert "ನಿಮ್ಮ" in result["political_reply"]


def test_ai_location_blob_is_cleaned_before_dashboard_metadata():
    result = finalize_geography_decision(
        grievance={"location": "ಸದಾಶಿವ ನಗರದಲ್ಲಿ ನೀರಿಲ್ಲ ಸ್ವಲ್ಪ ನೋಡಬೇಕು\n\nLocation: Sadashivanagar / ಸದಾಶಿವ ನಗರ"},
        ai_result={},
        status="new",
        political_reply="noted",
        detected_language="Kannada",
        message_body="ಸದಾಶಿವ ನಗರದಲ್ಲಿ ನೀರಿಲ್ಲ ಸ್ವಲ್ಪ ನೋಡಬೇಕು",
        current_tenant=2,
        is_emergency_complaint=False,
        resolve_location_fn=lambda *_args, **_kwargs: {"location_resolved": False},
        resolve_constituency_fn=lambda location, _tenant_id: (location, "Belgaum Uttar"),
        get_tenant_constituency_fn=lambda _tenant_id: "Belagavi",
    )

    assert result["location_name"] == "Sadashivanagar"
    assert result["grievance"]["location"] == "Sadashivanagar"
    assert result["final_constituency"] == "Belgaum Uttar"


def test_unresolved_ai_location_stays_awaiting_location():
    result = finalize_geography_decision(
        grievance={"location": "Unknown Place"},
        ai_result={},
        status="new",
        political_reply="Your complaint is noted",
        detected_language="English",
        message_body="Unknown Place road issue",
        current_tenant=2,
        is_emergency_complaint=False,
        resolve_location_fn=lambda *_args, **_kwargs: {"location_resolved": False},
        resolve_constituency_fn=lambda *_args, **_kwargs: (None, None),
        get_tenant_constituency_fn=lambda _tenant_id: "Belagavi",
    )

    assert result["status"] == "awaiting_location"
    assert result["final_constituency"] == "Unknown"
    assert "location" in result["political_reply"].lower()


def test_rejects_ai_assembly_outside_tenant_constituency():
    result = finalize_geography_decision(
        grievance={"location": "Shanti Baswad", "assembly_constituency": "Ulhasnagar"},
        ai_result={"assembly_constituency": "Ulhasnagar"},
        status="new",
        political_reply="Your complaint is noted",
        detected_language="Marathi",
        message_body="शांती बसवाड मध्ये रस्ता खराब आहे.",
        current_tenant=2,
        is_emergency_complaint=False,
        resolve_location_fn=lambda *_args, **_kwargs: {"location_resolved": False},
        resolve_constituency_fn=lambda location, _tenant_id: ("Santibastawad", "Belgaum Rural"),
        get_tenant_constituency_fn=lambda _tenant_id: "Belagavi",
        assembly_belongs_to_parliamentary_fn=lambda assembly, constituency: (
            assembly == "Belgaum Rural" and constituency == "Belagavi"
        ),
    )

    assert result["status"] == "new"
    assert result["location_name"] == "Shanti Baswad"
    assert result["final_constituency"] == "Belgaum Rural"
    assert result["grievance"]["assembly_constituency"] == "Belgaum Rural"


def test_invalid_ai_assembly_becomes_awaiting_location_when_location_cannot_resolve():
    result = finalize_geography_decision(
        grievance={"location": "Shanti Baswad", "assembly_constituency": "Ulhasnagar"},
        ai_result={"assembly_constituency": "Ulhasnagar"},
        status="new",
        political_reply="Your complaint is noted",
        detected_language="English",
        message_body="Shanti Baswad road issue",
        current_tenant=2,
        is_emergency_complaint=False,
        resolve_location_fn=lambda *_args, **_kwargs: {"location_resolved": False},
        resolve_constituency_fn=lambda *_args, **_kwargs: (None, None),
        get_tenant_constituency_fn=lambda _tenant_id: "Belagavi",
        assembly_belongs_to_parliamentary_fn=lambda assembly, constituency: (
            assembly == "Belgaum Rural" and constituency == "Belagavi"
        ),
    )

    assert result["status"] == "awaiting_location"
    assert result["final_constituency"] == "Unknown"
    assert "location" in result["political_reply"].lower()


def test_sentence_like_ai_location_does_not_leak_into_saved_location():
    result = finalize_geography_decision(
        grievance={"location": "तलाठी पैसे मागत आहे माझं काम होत नाही आहे"},
        ai_result={},
        status="new",
        political_reply="Your complaint is noted",
        detected_language="Marathi",
        message_body="तलाठी पैसे मागत आहे, माझं काम होत नाही आहे.",
        current_tenant=2,
        is_emergency_complaint=False,
        resolve_location_fn=lambda *_args, **_kwargs: {"location_resolved": False},
        resolve_constituency_fn=lambda *_args, **_kwargs: (None, None),
        get_tenant_constituency_fn=lambda _tenant_id: "Belagavi",
    )

    assert result["location_name"] is None
    assert result["final_constituency"] == "Unknown"
    assert result["grievance"]["location"] is None


def test_optional_category_without_location_stays_new():
    result = finalize_geography_decision(
        grievance={},
        ai_result={},
        status="new",
        political_reply="Your complaint is noted",
        detected_language="Marathi",
        message_body="तलाठी पैसे मागत आहे, माझं काम होत नाही आहे.",
        current_tenant=2,
        is_emergency_complaint=False,
        location_required=False,
        resolve_location_fn=lambda *_args, **_kwargs: {"location_resolved": False},
        resolve_constituency_fn=lambda *_args, **_kwargs: (None, None),
        get_tenant_constituency_fn=lambda _tenant_id: "Belagavi",
    )

    assert result["status"] == "new"
    assert result["final_constituency"] == "Unknown"


def test_required_category_without_location_stays_awaiting_location():
    result = finalize_geography_decision(
        grievance={"location": "Unknown locality"},
        ai_result={},
        status="new",
        political_reply="Your complaint is noted",
        detected_language="Marathi",
        message_body="Unknown locality madhe paani nahi",
        current_tenant=2,
        is_emergency_complaint=False,
        location_required=True,
        resolve_location_fn=lambda *_args, **_kwargs: {"location_resolved": False},
        resolve_constituency_fn=lambda *_args, **_kwargs: (None, None),
        get_tenant_constituency_fn=lambda _tenant_id: "Belagavi",
    )

    assert result["status"] == "awaiting_location"
    assert result["final_constituency"] == "Unknown"


def test_low_confidence_speech_match_goes_to_pending_review():
    result = finalize_geography_decision(
        grievance={},
        ai_result={},
        status="new",
        political_reply="Your complaint is noted",
        detected_language="Marathi",
        message_body="फळगावच्या सरकारी शाळेमध्ये पाणी भरला आहे",
        current_tenant=2,
        is_emergency_complaint=False,
        resolve_location_fn=lambda *_args, **_kwargs: {
            "location_resolved": True,
            "matched_value": "Vadgaon",
            "assembly_constituency": "Belgaum Dakshin",
            "confidence_level": "speech_phonetic",
            "match_type": "speech_phonetic",
        },
        resolve_constituency_fn=lambda *_args, **_kwargs: (None, None),
        get_tenant_constituency_fn=lambda _tenant_id: "Belagavi",
    )

    assert result["status"] == "pending_review"
    assert result["final_constituency"] == "Belgaum Dakshin"
    assert result["grievance"]["geography_confidence"] == "speech_phonetic"
    assert result["grievance"]["needs_geography_review"] is True


def test_ai_assembly_alone_does_not_become_final_truth():
    result = finalize_geography_decision(
        grievance={"assembly_constituency": "Belgaum Rural"},
        ai_result={"assembly_constituency": "Belgaum Rural"},
        status="new",
        political_reply="Your complaint is noted",
        detected_language="English",
        message_body="Please help",
        current_tenant=2,
        is_emergency_complaint=False,
        resolve_location_fn=lambda *_args, **_kwargs: {"location_resolved": False},
        resolve_constituency_fn=lambda *_args, **_kwargs: (None, None),
        get_tenant_constituency_fn=lambda _tenant_id: "Belagavi",
        assembly_belongs_to_parliamentary_fn=lambda assembly, constituency: (
            assembly == "Belgaum Rural" and constituency == "Belagavi"
        ),
    )

    assert result["status"] == "new"
    assert result["final_constituency"] == "Unknown"
