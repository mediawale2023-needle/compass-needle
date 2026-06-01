"""
Voice-note transcript normalization.

This module sits between raw ASR output and grievance classification. It keeps
the citizen's language intact, uses tenant geography to build a shortlist of
plausible localities, and optionally asks Gemini to clean ASR drift without
translating or over-editing the complaint.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from modules.geography_resolver import resolve_location, suggest_location_candidates

logger = logging.getLogger("needle.voice_note_normalizer")


@dataclass
class VoiceNoteNormalizationResult:
    raw_transcript: str
    normalized_text: str
    extracted_language: str = ""
    mentioned_location_original: str = ""
    mentioned_location_roman: str = ""
    confidence: str = ""
    provider: str = "sarvam"
    notes: dict[str, Any] = field(default_factory=dict)


_VOICE_NOTE_NORMALIZATION_PROMPT = """You are cleaning a speech-to-text transcript of a citizen grievance sent via WhatsApp voice note to an Indian elected-office workflow.

Return ONLY valid JSON:
{
  "normalized_text": "same language as the citizen, corrected only for obvious ASR drift, no translation",
  "detected_language": "language name if clear, else Unknown",
  "mentioned_location_original": "exact location phrase present in normalized_text if clear, else empty string",
  "mentioned_location_roman": "Roman rendering of the location only if clear, else empty string",
  "confidence": "high, medium, or low"
}

Rules:
1. Keep the citizen's meaning and language exactly. Do not translate.
2. Correct only likely speech-recognition drift, especially locality names, while staying conservative.
3. If the shortlist of possible localities does not clearly fit the transcript, do not force one.
4. Do not add new facts, issue details, or names that are not supported by the transcript.
5. Preserve issue wording unless it is obviously a speech-to-text spelling drift.
"""


def _json_from_text(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    return json.loads(cleaned)


def _fallback_normalization(
    transcript: str,
    *,
    candidate_locations: list[dict[str, Any]],
    detected_language: str,
) -> VoiceNoteNormalizationResult:
    top = candidate_locations[0] if candidate_locations else {}
    return VoiceNoteNormalizationResult(
        raw_transcript=transcript,
        normalized_text=transcript,
        extracted_language=detected_language or "Unknown",
        mentioned_location_original="",
        mentioned_location_roman=str(top.get("matched_value") or "").strip(),
        confidence="medium" if top else "low",
        notes={
            "normalizer": "fallback",
            "candidate_locations": candidate_locations,
        },
    )


def normalize_voice_note_transcript(
    transcript: str,
    *,
    tenant_id: int,
    detected_language: str = "",
    caption: str = "",
) -> VoiceNoteNormalizationResult:
    clean_transcript = str(transcript or "").strip()
    if not clean_transcript:
        return VoiceNoteNormalizationResult(
            raw_transcript="",
            normalized_text="",
            extracted_language=detected_language or "Unknown",
            confidence="low",
            notes={"normalizer": "empty"},
        )

    direct_location = resolve_location(clean_transcript, tenant_id=tenant_id)
    candidate_locations = suggest_location_candidates(clean_transcript, tenant_id=tenant_id, limit=5)
    prompt = _VOICE_NOTE_NORMALIZATION_PROMPT
    if caption.strip():
        prompt += f"\n\nCitizen caption:\n{caption.strip()}"
    prompt += "\n\nPossible localities for this tenant seat:\n"
    if candidate_locations:
        for idx, candidate in enumerate(candidate_locations, start=1):
            prompt += (
                f"{idx}. {candidate.get('matched_value')} | "
                f"{candidate.get('assembly_constituency')} | "
                f"confidence={candidate.get('confidence_level')} | "
                f"score={candidate.get('score')}\n"
            )
    else:
        prompt += "None\n"
    prompt += f"\nRaw transcript:\n{clean_transcript}"

    try:
        from core.gemini_client import get_gemini_client
        from google.genai import types
    except Exception as exc:
        logger.warning("Voice-note normalizer Gemini import unavailable: %s", exc)
        return _fallback_normalization(
            clean_transcript,
            candidate_locations=candidate_locations,
            detected_language=detected_language,
        )

    client = get_gemini_client()
    if not client:
        return _fallback_normalization(
            clean_transcript,
            candidate_locations=candidate_locations,
            detected_language=detected_language,
        )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )
        payload = _json_from_text(response.text)
        normalized_text = str(payload.get("normalized_text") or clean_transcript).strip() or clean_transcript
        return VoiceNoteNormalizationResult(
            raw_transcript=clean_transcript,
            normalized_text=normalized_text,
            extracted_language=str(payload.get("detected_language") or detected_language or "Unknown").strip(),
            mentioned_location_original=str(payload.get("mentioned_location_original") or "").strip(),
            mentioned_location_roman=str(payload.get("mentioned_location_roman") or "").strip(),
            confidence=str(payload.get("confidence") or "").strip() or ("high" if direct_location.get("location_resolved") else "medium"),
            provider="sarvam+gemini",
            notes={
                "normalizer": "gemini",
                "candidate_locations": candidate_locations,
                "direct_location": direct_location,
            },
        )
    except Exception as exc:
        logger.warning("Voice-note normalizer Gemini call failed: %s", exc)
        return _fallback_normalization(
            clean_transcript,
            candidate_locations=candidate_locations,
            detected_language=detected_language,
        )
