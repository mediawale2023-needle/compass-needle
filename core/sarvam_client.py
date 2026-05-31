"""
Sarvam speech-to-text client helpers.

This module intentionally stays small and request-based so the backend can
switch voice-note transcription providers without changing the grievance flow.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import requests

logger = logging.getLogger("needle.sarvam")

SARVAM_STT_URL = os.getenv("SARVAM_STT_URL", "https://api.sarvam.ai/speech-to-text")
SARVAM_TIMEOUT_SECONDS = float(os.getenv("SARVAM_TIMEOUT_SECONDS", "45"))
SARVAM_MODEL = os.getenv("SARVAM_STT_MODEL", "saaras:v3")
SARVAM_MODE = os.getenv("SARVAM_STT_MODE", "transcribe")


@dataclass
class SarvamTranscriptionResult:
    ok: bool
    transcript: str = ""
    language_code: str = ""
    request_id: str = ""
    error: str = ""


def get_sarvam_api_key() -> str:
    return os.getenv("SARVAM_API_KEY", "").strip()


def transcribe_audio_bytes(
    audio_bytes: bytes,
    *,
    mime_type: str,
    file_name: str = "voice-note.ogg",
    language_code: str = "unknown",
) -> SarvamTranscriptionResult:
    api_key = get_sarvam_api_key()
    if not api_key:
        return SarvamTranscriptionResult(ok=False, error="sarvam_api_key_missing")
    if not audio_bytes:
        return SarvamTranscriptionResult(ok=False, error="empty_audio")

    files = {
        "file": (
            file_name,
            audio_bytes,
            mime_type or "audio/ogg",
        )
    }
    data = {
        "model": SARVAM_MODEL,
        "mode": SARVAM_MODE,
        "language_code": language_code or "unknown",
    }
    headers = {"api-subscription-key": api_key}

    try:
        response = requests.post(
            SARVAM_STT_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=SARVAM_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.warning("Sarvam STT request failed: %s", exc)
        return SarvamTranscriptionResult(ok=False, error=f"request_failed:{exc.__class__.__name__}")

    try:
        payload = response.json()
    except Exception:
        payload = {}

    if response.status_code >= 400:
        error = payload.get("error") if isinstance(payload, dict) else {}
        message = ""
        if isinstance(error, dict):
            message = str(error.get("message") or error.get("code") or "").strip()
        message = message or response.text[:160] or f"http_{response.status_code}"
        logger.warning("Sarvam STT error %s: %s", response.status_code, message)
        return SarvamTranscriptionResult(ok=False, error=f"http_{response.status_code}:{message}")

    transcript = str(payload.get("transcript") or "").strip() if isinstance(payload, dict) else ""
    if not transcript:
        return SarvamTranscriptionResult(ok=False, error="missing_transcript")

    return SarvamTranscriptionResult(
        ok=True,
        transcript=transcript,
        language_code=str(payload.get("language_code") or "").strip() if isinstance(payload, dict) else "",
        request_id=str(payload.get("request_id") or "").strip() if isinstance(payload, dict) else "",
    )
