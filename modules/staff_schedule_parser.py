"""
staff_schedule_parser.py — Structured parser for PA/staff WhatsApp schedule text.

Converts messages like:
  "Meeting with Chief Minister on Wednesday at 5 PM"
into tenant-safe dashboard engagement payloads.

Uses GPT-4o-mini for multilingual parsing with a conservative regex fallback.
If the parser is not reasonably sure the message is a schedule/note/calendar
command, it returns None so the existing staff case-query flow can continue.
"""
import json
import logging
import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from openai import OpenAI

logger = logging.getLogger("needle.staff_schedule_parser")

INDIA_TZ = ZoneInfo("Asia/Kolkata")

_WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_SCHEDULE_KEYWORDS = (
    "meeting", "meet", "schedule", "appointment", "visit", "call", "review",
    "briefing", "event", "program", "programme", "hearing", "बैठक", "मीटिंग",
    "भेंट", "कार्यक्रम", "दौरा", "समीक्षा", "कॉल", "अपॉइंटमेंट",
)
_NOTE_KEYWORDS = ("note", "reminder", "remember", "नोट", "याद", "रिमाइंडर")


def _get_client():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key, timeout=30.0)


def _today_india():
    return datetime.now(INDIA_TZ)


def _next_weekday(reference: datetime, weekday: int) -> datetime:
    days_ahead = weekday - reference.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return reference + timedelta(days=days_ahead)


def _has_schedule_signal(text: str) -> bool:
    lowered = text.lower()
    has_keyword = any(keyword in lowered for keyword in _SCHEDULE_KEYWORDS)
    has_note = any(keyword in lowered for keyword in _NOTE_KEYWORDS)
    has_url = "http://" in lowered or "https://" in lowered or "meet.google.com" in lowered
    has_time = bool(re.search(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b|\b\d{1,2}:\d{2}\b", lowered))
    has_day = bool(re.search(r"\b(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", lowered))
    return has_keyword or has_note or has_url or (has_time and has_day)


def _normalize_time(hour: int, minute: int) -> str:
    return f"{hour:02d}:{minute:02d}"


def _extract_time(message: str) -> str | None:
    text = message.lower()
    match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or "0")
        meridian = match.group(3)
        if meridian == "pm" and hour != 12:
            hour += 12
        if meridian == "am" and hour == 12:
            hour = 0
        return _normalize_time(hour, minute)
    match = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return _normalize_time(hour, minute)
    return None


def _extract_date(message: str, reference: datetime) -> str | None:
    text = message.lower()
    if "today" in text or "aaj" in text:
        return reference.date().isoformat()
    if "tomorrow" in text or "kal" in text:
        return (reference + timedelta(days=1)).date().isoformat()
    for name, weekday_index in _WEEKDAY_INDEX.items():
        if re.search(rf"\b{name}\b", text):
            return _next_weekday(reference, weekday_index).date().isoformat()
    explicit = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if explicit:
        return explicit.group(1)
    return None


def _fallback_parse(message: str) -> dict | None:
    reference = _today_india()
    if not _has_schedule_signal(message):
        return None

    lowered = message.lower()
    if any(keyword in lowered for keyword in _NOTE_KEYWORDS) and not _extract_date(message, reference) and not _extract_time(message):
        entry_type = "note"
    elif "http://" in lowered or "https://" in lowered or "meet.google.com" in lowered:
        entry_type = "calendar"
    else:
        entry_type = "schedule"

    scheduled_for = _extract_date(message, reference)
    start_time = _extract_time(message)
    is_all_day = bool(scheduled_for and not start_time and entry_type == "schedule")

    if entry_type == "schedule" and not scheduled_for and not start_time:
        return None

    title = message.strip()
    calendar_url_match = re.search(r"(https?://\S+)", message)
    return {
        "entry_type": entry_type,
        "title": title[:160],
        "notes": None,
        "location": None,
        "scheduled_for": scheduled_for or reference.date().isoformat(),
        "start_time": start_time,
        "end_time": None,
        "is_all_day": is_all_day,
        "calendar_url": calendar_url_match.group(1) if calendar_url_match else None,
        "confidence": "fallback",
    }


def parse_staff_schedule_message(message: str) -> dict | None:
    client = _get_client()
    reference = _today_india()
    reference_date = reference.date().isoformat()
    reference_weekday = reference.strftime("%A")

    if client:
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You parse WhatsApp messages from Indian MP/MLA office staff into dashboard schedule items. "
                            "The message can be in English, Hindi, Hinglish, Marathi, Kannada, Tamil, Telugu, Malayalam, Bengali, Gujarati, Punjabi, Urdu, or mixed language. "
                            f"Today in India is {reference_weekday}, {reference_date}. "
                            "Return ONLY JSON with exactly these keys: "
                            "{\"is_schedule\": false, \"entry_type\": \"schedule\", \"title\": \"\", \"notes\": \"\", "
                            "\"location\": \"\", \"scheduled_for\": \"\", \"start_time\": \"\", \"end_time\": \"\", "
                            "\"is_all_day\": false, \"calendar_url\": \"\", \"confidence\": \"low\"}. "
                            "Rules: "
                            "1. Set is_schedule=true only when the message is clearly asking to save a meeting, reminder, visit, note, event, or calendar item for staff. "
                            "2. If the message looks like a grievance query, citizen complaint, ack command, or unrelated chat, set is_schedule=false. "
                            "3. entry_type must be one of schedule, note, calendar. Use calendar only when the message contains or refers to a meeting/calendar link. "
                            "4. title must be short, clear, and in the message language when possible. "
                            "5. scheduled_for must be YYYY-MM-DD when a date/day can be inferred; otherwise empty string for note entries. "
                            "6. start_time and end_time must be HH:MM 24-hour format when present, otherwise empty string. "
                            "7. is_all_day=true only if a day/date is known and no time is given for a schedule item. "
                            "8. confidence must be high, medium, or low."
                        ),
                    },
                    {"role": "user", "content": message},
                ],
                max_tokens=220,
                temperature=0,
            )
            raw = response.choices[0].message.content or "{}"
            parsed = json.loads(raw)
            if not parsed.get("is_schedule"):
                return None

            entry_type = str(parsed.get("entry_type") or "schedule").strip().lower()
            if entry_type not in {"schedule", "note", "calendar"}:
                entry_type = "schedule"

            confidence = str(parsed.get("confidence") or "low").strip().lower()
            if confidence not in {"high", "medium", "low"}:
                confidence = "low"

            title = str(parsed.get("title") or "").strip()
            if not title:
                return None

            scheduled_for = str(parsed.get("scheduled_for") or "").strip()
            start_time = str(parsed.get("start_time") or "").strip()
            end_time = str(parsed.get("end_time") or "").strip()
            calendar_url = str(parsed.get("calendar_url") or "").strip() or None
            notes = str(parsed.get("notes") or "").strip() or None
            location = str(parsed.get("location") or "").strip() or None
            is_all_day = bool(parsed.get("is_all_day"))

            if entry_type == "schedule" and not (scheduled_for or start_time or is_all_day):
                return None
            if confidence == "low" and entry_type == "schedule":
                return None

            return {
                "entry_type": entry_type,
                "title": title[:160],
                "notes": notes,
                "location": location,
                "scheduled_for": scheduled_for or reference_date,
                "start_time": start_time or None,
                "end_time": end_time or None,
                "is_all_day": is_all_day,
                "calendar_url": calendar_url,
                "confidence": confidence,
            }
        except Exception as exc:
            logger.warning("Staff schedule GPT parse failed (%s), using fallback", exc)

    return _fallback_parse(message)
