"""
modules/govt_sync/browser_session.py — live, staff-controllable browser
sessions for filing a grievance on a real government portal.

Runs on the EC2 backend host itself (not Railway — this needs a real,
persistent machine, see modules/govt_sync/__init__.py). One shared headless
Chromium process is kept warm; each "live session" is an isolated browser
context (own cookies/state) for one case's filing attempt.

What this module does:
  1. Opens the portal, auto-fills every field the AI translated (department,
     subject, description, ...) using admin-configured CSS selectors —
     see modules/data/govt_portals.json `field_schema.selectors`. Fields with
     no selector configured yet are skipped and reported as a warning, not a
     crash — a portal with no selectors calibrated is still fully usable in
     "staff types everything by hand" mode, autofill just doesn't happen.
  2. Streams the live page to the staff dashboard as a sequence of JPEG
     frames over CDP's Page.startScreencast (api_router.py relays these over
     a WebSocket) and relays the staff's mouse/keyboard back into the real
     page via Playwright's own page.mouse / page.keyboard — so solving the
     CAPTCHA, entering the OTP, and clicking Submit all happen for real, on
     the real portal, by the human.
  3. On request, tries to auto-read the reference number the portal shows
     after submission (selector or regex, both admin-configurable and both
     optional) — falls back to staff pasting it in manually via the existing
     POST /api/cases/{id}/govt/submit endpoint if that doesn't find anything.

Concurrency is capped (GOVT_SYNC_MAX_LIVE_SESSIONS, default 3) because this
is one real EC2 box, not an autoscaled fleet — headless Chromium is not free.
Idle sessions (GOVT_SYNC_SESSION_IDLE_SECONDS, default 600s of no input) are
closed automatically so an abandoned tab doesn't leak a browser context
forever.
"""
import asyncio
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger("needle.govt_sync.browser")

MAX_CONCURRENT_SESSIONS = int(os.getenv("GOVT_SYNC_MAX_LIVE_SESSIONS", "3"))
SESSION_IDLE_SECONDS = int(os.getenv("GOVT_SYNC_SESSION_IDLE_SECONDS", "600"))
NAV_TIMEOUT_MS = 20_000
VIEWPORT = {"width": 1280, "height": 900}

# Headless Chromium needs --no-sandbox on most bare EC2 boxes (no user
# namespaces configured) — see scripts/setup_govt_sync_browser.sh. Only set
# this if you understand the tradeoff; it's the standard flag for running
# Chromium as a non-root, non-namespaced process.
_LAUNCH_ARGS = ["--no-sandbox", "--disable-dev-shm-usage"] if os.getenv("GOVT_SYNC_NO_SANDBOX", "1") == "1" else []

_DEFAULT_REFERENCE_REGEX = r"\b[A-Z]{2,10}[/\-][A-Z0-9]{2,10}[/\-][0-9]{2,10}[/\-][0-9A-Z]{3,10}\b"


@dataclass
class LiveSession:
    session_id: str
    tenant_id: int
    case_id: int
    portal: dict
    context: object   # playwright.async_api.BrowserContext
    page: object       # playwright.async_api.Page
    cdp: object        # playwright.async_api.CDPSession
    worksheet: dict = field(default_factory=dict)              # kept so retry_autofill() can re-run later
    portal_contact_number: str | None = None
    fill_warnings: list = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_activity_at: float = field(default_factory=time.time)
    streaming: bool = False
    ws = None


_playwright_ctx = None
_browser = None
_sessions: dict[str, LiveSession] = {}
_lock = asyncio.Lock()
_launch_lock = asyncio.Lock()


async def _ensure_browser():
    global _playwright_ctx, _browser
    if _browser is not None:
        return _browser
    async with _launch_lock:
        if _browser is not None:
            return _browser
        from playwright.async_api import async_playwright

        _playwright_ctx = await async_playwright().start()
        _browser = await _playwright_ctx.chromium.launch(headless=True, args=_LAUNCH_ARGS)
        logger.info(f"Govt sync: launched shared Chromium (args={_LAUNCH_ARGS})")
        return _browser


async def active_session_count() -> int:
    async with _lock:
        return len(_sessions)


async def start_session(tenant_id: int, case_id: int, portal: dict, worksheet: dict, portal_contact_number: str | None) -> LiveSession:
    """Open the portal, auto-fill what we can, and hold it open for a staff viewer to attach."""
    async with _lock:
        if len(_sessions) >= MAX_CONCURRENT_SESSIONS:
            raise RuntimeError(
                f"{MAX_CONCURRENT_SESSIONS} live portal sessions are already open — "
                "wait for one to finish or close it, then try again."
            )

    browser = await _ensure_browser()
    field_schema = portal.get("field_schema") or {}
    context = await browser.new_context(viewport=VIEWPORT)
    context.set_default_timeout(NAV_TIMEOUT_MS)
    page = await context.new_page()
    cdp = await context.new_cdp_session(page)

    session_id = uuid.uuid4().hex
    session = LiveSession(
        session_id=session_id, tenant_id=tenant_id, case_id=case_id, portal=portal, context=context, page=page, cdp=cdp,
        worksheet=worksheet, portal_contact_number=portal_contact_number,
    )

    entry_path = field_schema.get("entry_path") or ""
    entry_url = portal["base_url"].rstrip("/") + entry_path
    try:
        await page.goto(entry_url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    except Exception as e:
        await context.close()
        raise RuntimeError(f"Could not open {portal['portal_name']}: {e}")

    # First attempt, right after landing on entry_url. Many OTP-bound portals
    # (Karnataka's iPGRS included) put the actual grievance form behind a
    # citizen login/registration gate — there's nothing to fill in yet at
    # entry_url in that case, so this first pass often reports every field as
    # "no selector" not because none is configured, but because the fields
    # don't exist on this page at all. retry_autofill() below is what staff
    # use once they've logged in and reached the real form.
    session.fill_warnings = await _autofill(page, field_schema, worksheet, portal_contact_number)

    async with _lock:
        _sessions[session_id] = session
    logger.info(f"Govt sync: opened live session {session_id} for case={case_id} portal={portal['portal_name']}")
    return session


async def _autofill(page, field_schema: dict, worksheet: dict, portal_contact_number: str | None) -> list[str]:
    """Best-effort autofill using admin-configured selectors. Every field that
    fails (no selector configured yet, or the selector doesn't match — the
    portal changed its DOM) is reported, not swallowed, so staff know exactly
    what to type by hand instead."""
    selectors = field_schema.get("selectors") or {}
    values = {
        "department": worksheet.get("department"),
        "district": worksheet.get("district"),
        "subdistrict_or_ulb": worksheet.get("subdistrict_or_ulb"),
        "subject": worksheet.get("subject"),
        "description": worksheet.get("description"),
        "applicant_mobile": portal_contact_number,
    }
    warnings = []
    for key, value in values.items():
        if not value:
            continue
        selector = selectors.get(key)
        if not selector:
            warnings.append(f"No selector configured for '{key}' yet — enter it manually: {value}")
            continue
        try:
            locator = page.locator(selector).first
            tag = await locator.evaluate("el => el.tagName.toLowerCase()")
            if tag == "select":
                await locator.select_option(label=str(value))
            else:
                await locator.fill(str(value))
        except Exception as e:
            warnings.append(f"Auto-fill failed for '{key}' — enter it manually: {value} ({e})")
    return warnings


async def retry_autofill(session_id: str) -> list[str] | None:
    """Re-run autofill against wherever the page is *right now*.

    Exists because start_session()'s one-shot attempt happens immediately at
    entry_url, before a staff member has done anything — on an OTP-bound
    portal where the grievance form only exists after citizen login (see
    module docstring), that first pass has nothing to find. Staff log in and
    navigate to the real form themselves during the live session, then call
    this (POST /api/cases/{id}/govt/session/{id}/autofill) once they're
    looking at it, so autofill gets a real shot at whatever page selectors
    were actually calibrated against.
    """
    async with _lock:
        session = _sessions.get(session_id)
    if not session:
        return None
    session.last_activity_at = time.time()
    field_schema = session.portal.get("field_schema") or {}
    session.fill_warnings = await _autofill(session.page, field_schema, session.worksheet, session.portal_contact_number)
    return session.fill_warnings


async def attach_stream(session_id: str, websocket, send_frame) -> LiveSession | None:
    """Start CDP screencast for `session_id` and route frames through `send_frame(dict)`."""
    async with _lock:
        session = _sessions.get(session_id)
    if not session:
        return None

    session.ws = websocket
    session.streaming = True
    session.last_activity_at = time.time()

    def _on_frame(params):
        asyncio.create_task(_forward_frame(session, send_frame, params))

    session.cdp.on("Page.screencastFrame", _on_frame)
    try:
        await session.cdp.send("Page.startScreencast", {
            "format": "jpeg", "quality": 60, "everyNthFrame": 1,
            "maxWidth": VIEWPORT["width"], "maxHeight": VIEWPORT["height"],
        })
    except Exception as e:
        logger.warning(f"Govt sync: could not start screencast for {session_id}: {e}")
    return session


async def _forward_frame(session: LiveSession, send_frame, params: dict):
    try:
        await send_frame({"type": "frame", "data": params["data"]})
        await session.cdp.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]})
    except Exception:
        pass  # nosec B110 — client likely disconnected, cleanup happens on WS close


async def detach_stream(session_id: str):
    async with _lock:
        session = _sessions.get(session_id)
    if not session:
        return
    session.streaming = False
    session.ws = None
    try:
        await session.cdp.send("Page.stopScreencast")
    except Exception:
        pass  # nosec B110


async def relay_input(session_id: str, event: dict):
    async with _lock:
        session = _sessions.get(session_id)
    if not session:
        return
    session.last_activity_at = time.time()
    page = session.page
    try:
        etype = event.get("type")
        if etype == "mousemove":
            await page.mouse.move(event["x"], event["y"])
        elif etype == "mousedown":
            await page.mouse.move(event["x"], event["y"])
            await page.mouse.down()
        elif etype == "mouseup":
            await page.mouse.up()
        elif etype == "wheel":
            await page.mouse.wheel(event.get("deltaX", 0), event.get("deltaY", 0))
        elif etype == "keydown":
            key = event.get("key", "")
            if event.get("printable") and len(key) == 1:
                await page.keyboard.insert_text(key)
            elif key:
                await page.keyboard.press(key)
    except Exception as e:
        logger.debug(f"Govt sync: input relay error for {session_id}: {e}")


async def capture_reference(session_id: str) -> str | None:
    """Best-effort read of the reference number the portal shows post-submit."""
    async with _lock:
        session = _sessions.get(session_id)
    if not session:
        return None
    field_schema = session.portal.get("field_schema") or {}
    selector = field_schema.get("reference_selector")
    pattern = field_schema.get("reference_regex") or _DEFAULT_REFERENCE_REGEX

    try:
        if selector:
            text = await session.page.locator(selector).first.inner_text()
            match = re.search(pattern, text)
            if match:
                return match.group(0)
            if text and text.strip():
                return text.strip()
        body_text = await session.page.inner_text("body")
        match = re.search(pattern, body_text)
        if match:
            return match.group(0)
    except Exception as e:
        logger.info(f"Govt sync: reference capture failed for {session_id}: {e}")
    return None


async def close_session(session_id: str):
    async with _lock:
        session = _sessions.pop(session_id, None)
    if not session:
        return
    try:
        await session.cdp.send("Page.stopScreencast")
    except Exception:
        pass  # nosec B110
    try:
        await session.context.close()
    except Exception:
        pass  # nosec B110
    logger.info(f"Govt sync: closed live session {session_id}")


def get_session_meta(session_id: str) -> dict | None:
    session = _sessions.get(session_id)
    if not session:
        return None
    return {
        "session_id": session.session_id, "tenant_id": session.tenant_id, "case_id": session.case_id,
        "fill_warnings": session.fill_warnings, "viewport": VIEWPORT, "otp_bound": session.portal.get("otp_bound"),
        "portal_name": session.portal.get("portal_name"),
    }


async def sweep_idle_sessions():
    """Close any session idle longer than SESSION_IDLE_SECONDS. Run on a timer from main.py."""
    now = time.time()
    async with _lock:
        stale = [sid for sid, s in _sessions.items() if now - s.last_activity_at > SESSION_IDLE_SECONDS]
    for sid in stale:
        logger.info(f"Govt sync: closing idle live session {sid}")
        await close_session(sid)
