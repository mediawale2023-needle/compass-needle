"""
modules/govt_sync/browser_session.py — live, staff-controllable browser
sessions for filing a grievance on a real government portal.

Runs on the EC2 backend host itself (not Railway — this needs a real,
persistent machine, see modules/govt_sync/__init__.py). One shared headless
Chromium process is kept warm; each "live session" is an isolated browser
context (own cookies/state) for one case's filing attempt.

What this module does — and deliberately does NOT do:
  0. Forces English on every page it opens: sets the browser context's
     locale/Accept-Language (works for portals that honor standard content
     negotiation) and, on every navigation, clicks any visible "English"-type
     toggle it finds (works for the ones that don't — confirmed true for
     Karnataka's iPGRS, which opened in Kannada regardless of locale). Both
     are best-effort and never block the session if a portal doesn't
     cooperate — see _ensure_english().
  1. Opens the portal and holds the session open for a staff viewer to
     attach and log in for real (credentials, CAPTCHA, OTP — all human).
  2. Keeps watching after that: `_on_page_load` fires on every subsequent
     navigation (login redirect, ...). If a portal's post-login grievance
     form URL is known (field_schema.post_login_entry_path, admin-configured,
     empty by default), the system navigates straight there the first time
     it detects a real navigation after login — "log in, land on the form"
     with no staff click needed to get there. That is the extent of the
     automation: no field on that form is ever touched programmatically.
  3. Streams the live page to the staff dashboard as a sequence of JPEG
     frames over CDP's Page.startScreencast (api_router.py relays these over
     a WebSocket) and relays the staff's mouse/keyboard back into the real
     page via Playwright's own page.mouse / page.keyboard — so logging in,
     solving the CAPTCHA/OTP, filling in every grievance field, and clicking
     Submit all happen for real, on the real portal, typed by the human.
  4. On request, tries to auto-read the reference number the portal shows
     after submission (selector or regex, both admin-configurable and both
     optional) — falls back to staff pasting it in manually via the existing
     POST /api/cases/{id}/govt/submit endpoint if that doesn't find anything.

  This module used to also auto-fill grievance fields (department, subject,
  description, filer name, ...) from admin-configured CSS selectors. That
  was removed by product decision, not because it broke: auto-typing values
  into a form staff haven't reviewed compounds the fingerprinting/blast-
  radius risk (see PROJECT_MEMORY.md) for a step that just isn't necessary —
  staff can read the AI worksheet fields (shown as copy-paste text in
  Briefcase) and type them in themselves during the same live session. Keep
  it that way unless a fresh, explicit decision reintroduces autofill.

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

# Indian government portals almost always expose an explicit "English" link
# rather than honoring Accept-Language/navigator.language (confirmed true for
# Karnataka's iPGRS — it opened in Kannada regardless of the browser context's
# locale). Deliberately text-based, not a CSS selector: unlike department/
# subject/description fields, "English" as a visible label is close to
# universal across these portals, so this one heuristic is worth trying
# everywhere instead of needing per-portal selector configuration.
_ENGLISH_TOGGLE_TEXTS = ["English", "ENGLISH", "English Version", "View in English", "EN"]

_DEV_DOM_MAX_BODY_CHARS = 12_000
_DEV_DOM_MAX_HTML_CHARS = 30_000
_DEV_DOM_MAX_ELEMENTS = 160
_DEV_DOM_MAX_TEXT_CHARS = 800
_DEV_DOM_ALLOWED_ATTRS = (
    "id", "name", "type", "role", "aria-label", "aria-labelledby",
    "aria-describedby", "placeholder", "title", "href", "class",
    "data-testid", "data-test", "data-cy",
)
_DEV_DOM_SENSITIVE_ATTR_RE = re.compile(r"(password|passwd|pwd|otp|token|secret|cookie|auth|session|csrf)", re.I)
_DEV_DOM_SENSITIVE_TEXT_RE = re.compile(
    r"(?i)\b(password|passwd|pwd|otp|one[- ]?time password|token|secret|cookie|authorization|bearer|csrf)\b"
    r"(\s*[:=\-]?\s*)([^\s<,;]{2,})"
)
_DEV_DOM_REFERENCE_RE = re.compile(r"\bTN/[A-Z0-9]+/[A-Z0-9]+/[A-Z]/PORTAL/[0-9A-Z]{7}/[0-9]{5,}\b")
_DEV_DOM_RELEVANT_TEXT_RE = re.compile(
    r"(petition|grievance|ticket|complaint|status|pending|received|disposed|resolved|closed|"
    r"under process|action taken|reply|remark|department|last updated|#\d{5,}|"
    r"மனு|குறை|நிலை|துறை)",
    re.I,
)
_DEV_DOM_STRUCTURAL_SELECTORS = (
    "input", "textarea", "select", "button", "a", "iframe", "[role]",
)
_DEV_DOM_RELEVANT_SELECTORS = (
    "article", "li", "tr", "td", "th", "section", "div", "span", "p", "label",
)


def _truncate(value: str | None, limit: int) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + f"... [truncated {len(text) - limit} chars]"


def _redact_dev_dom_text(value: str | None) -> str:
    text = "" if value is None else str(value)
    text = _DEV_DOM_SENSITIVE_TEXT_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", text)
    text = re.sub(
        r"(?i)\s+[a-z0-9:_-]*(password|passwd|pwd|otp|token|secret|cookie|auth|session|csrf)[a-z0-9:_-]*"
        r"\s*=\s*(?:(['\"])[^'\"]*\2|[^\s>]+)",
        " data-redacted=\"[REDACTED]\"",
        text,
    )
    text = re.sub(
        r"(?i)(value|content)\s*=\s*(['\"])[^'\"]*(password|otp|token|secret|cookie|auth|csrf)[^'\"]*\2",
        r"\1=\2[REDACTED]\2",
        text,
    )
    text = re.sub(r"(?i)\b(value)\s*=\s*(['\"])[^'\"]*\2", r"\1=\2[REDACTED]\2", text)
    return text


def _safe_dev_dom_attr(name: str, value: str | None) -> str | None:
    if value is None or _DEV_DOM_SENSITIVE_ATTR_RE.search(name or ""):
        return None
    if (name or "").lower() == "href" and str(value).lower().startswith("javascript:"):
        return "[REDACTED]"
    return _truncate(_redact_dev_dom_text(value), 500)


async def _ensure_english(page) -> bool:
    """Best-effort click of a visible English-language toggle. Returns True
    if something was clicked (not proof the site actually switched — just
    that we found and clicked a matching element). Never raises; a portal
    with no such link, or one already in English, just no-ops."""
    for label in _ENGLISH_TOGGLE_TEXTS:
        try:
            locator = page.get_by_text(label, exact=True).first
            if await locator.count() == 0:
                continue
            await locator.click(timeout=3000)
            await page.wait_for_load_state("domcontentloaded", timeout=NAV_TIMEOUT_MS)
            logger.info(f"Govt sync: clicked '{label}' language toggle")
            return True
        except Exception:
            continue  # try the next candidate label; a portal may have none of these
    return False


@dataclass
class LiveSession:
    session_id: str
    tenant_id: int
    case_id: int
    portal: dict
    context: object   # playwright.async_api.BrowserContext
    page: object       # playwright.async_api.Page
    cdp: object        # playwright.async_api.CDPSession
    created_at: float = field(default_factory=time.time)
    last_activity_at: float = field(default_factory=time.time)
    streaming: bool = False
    ws = None
    send_frame = None
    navigated_to_form: bool = False   # guards the one auto-navigate-to-post-login-form attempt
    nav_running: bool = False         # re-entrancy guard for the "load" handler
    last_seen_url: str | None = None


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


def list_session_metas(tenant_id: int | None = None) -> list[dict]:
    """In-memory live sessions. Pass tenant_id to scope to one office;
    omit it only for ops/count. Never returns another tenant's rows when
    tenant_id is set."""
    now = time.time()
    out = []
    for session in _sessions.values():
        if tenant_id is not None and session.tenant_id != tenant_id:
            continue
        out.append({
            "session_id": session.session_id,
            "tenant_id": session.tenant_id,
            "case_id": session.case_id,
            "portal_name": session.portal.get("portal_name"),
            "otp_bound": session.portal.get("otp_bound"),
            "viewport": VIEWPORT,
            "created_at": session.created_at,
            "last_activity_at": session.last_activity_at,
            "age_seconds": int(now - session.created_at),
            "idle_seconds": int(now - session.last_activity_at),
            "streaming": session.streaming,
            "ws_path": f"/api/govt/session/{session.session_id}/stream",
        })
    out.sort(key=lambda item: item["created_at"])
    return out


async def close_sessions_for_tenant(tenant_id: int) -> int:
    async with _lock:
        ids = [sid for sid, session in _sessions.items() if session.tenant_id == tenant_id]
    for sid in ids:
        await close_session(sid)
    return len(ids)


async def start_session(tenant_id: int, case_id: int, portal: dict) -> LiveSession:
    """Open the portal and hold it open for a staff viewer to attach and log in."""
    async with _lock:
        if len(_sessions) >= MAX_CONCURRENT_SESSIONS:
            raise RuntimeError(
                f"{MAX_CONCURRENT_SESSIONS} live portal sessions are already open — "
                "wait for one to finish or close it, then try again."
            )

    browser = await _ensure_browser()
    field_schema = portal.get("field_schema") or {}
    # First line of defense: standard HTTP content negotiation. Some portals
    # honor this and serve English by default without any further action.
    # Karnataka's iPGRS does not (confirmed — it opened in Kannada regardless),
    # which is why _ensure_english() below exists as the real fix; this is
    # just free insurance for whichever portals *do* respect it.
    context = await browser.new_context(
        viewport=VIEWPORT, locale="en-US",
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
    )
    context.set_default_timeout(NAV_TIMEOUT_MS)
    page = await context.new_page()
    cdp = await context.new_cdp_session(page)

    session_id = uuid.uuid4().hex
    session = LiveSession(
        session_id=session_id, tenant_id=tenant_id, case_id=case_id, portal=portal, context=context, page=page, cdp=cdp,
    )

    entry_path = field_schema.get("entry_path") or ""
    entry_url = portal["base_url"].rstrip("/") + entry_path
    try:
        await page.goto(entry_url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    except Exception as e:
        await context.close()
        raise RuntimeError(f"Could not open {portal['portal_name']}: {e}")

    await _ensure_english(page)
    session.last_seen_url = page.url

    # From here on, every real navigation (login redirect, staff clicking
    # around, ...) re-triggers this automatically. Registered *after* the
    # initial goto above so it doesn't double-fire on the page we just
    # handled by hand.
    def _on_load(_=None):
        asyncio.create_task(_on_page_load(session))

    page.on("load", _on_load)

    async with _lock:
        _sessions[session_id] = session
    logger.info(f"Govt sync: opened live session {session_id} for case={case_id} portal={portal['portal_name']}")
    return session


async def _on_page_load(session: "LiveSession"):
    """Fires on every navigation after the first. If the portal has a known
    post-login form path configured (field_schema.post_login_entry_path) and
    we haven't gone there yet this session, navigate straight to it once —
    that's the "log in, land on the form" behavior once an admin has
    actually captured that URL. No field on that form is ever touched
    programmatically — this function's only job is getting staff to the
    right page, not filling it in.
    """
    if session.nav_running:
        return  # a previous load is still being handled; this one will get picked up by the next event
    session.nav_running = True
    try:
        # Let the page actually settle — "load" can fire before late-rendered
        # content exists, especially on portals that finish building the DOM
        # client-side after the base document loads.
        await asyncio.sleep(0.8)

        page = session.page
        current_url = page.url
        if current_url == session.last_seen_url:
            return  # no real navigation (e.g. a sub-resource "load"), nothing to do
        session.last_seen_url = current_url
        session.last_activity_at = time.time()

        # Some portals reset to the regional language on every fresh page
        # (not just the first one) — re-check on each navigation, not only
        # at session start. Cheap no-op if the page is already in English.
        await _ensure_english(page)

        field_schema = session.portal.get("field_schema") or {}
        post_login_path = field_schema.get("post_login_entry_path")
        if post_login_path and not session.navigated_to_form:
            target_url = session.portal["base_url"].rstrip("/") + post_login_path
            if current_url.rstrip("/") != target_url.rstrip("/"):
                session.navigated_to_form = True  # set before navigating — the resulting "load" re-enters here once
                try:
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
                    logger.info(f"Govt sync: auto-navigated session {session.session_id} to configured post-login form")
                except Exception as e:
                    logger.warning(f"Govt sync: auto-navigate to post_login_entry_path failed for {session.session_id}: {e}")
    except Exception as e:
        logger.debug(f"Govt sync: _on_page_load failed for {session.session_id}: {e}")
    finally:
        session.nav_running = False


async def attach_stream(session_id: str, websocket, send_frame) -> LiveSession | None:
    """Start CDP screencast for `session_id` and route frames through `send_frame(dict)`."""
    async with _lock:
        session = _sessions.get(session_id)
    if not session:
        return None

    session.ws = websocket
    session.send_frame = send_frame
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
    session.send_frame = None
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
        "viewport": VIEWPORT, "otp_bound": session.portal.get("otp_bound"),
        "portal_name": session.portal.get("portal_name"),
    }


def get_live_session(session_id: str) -> LiveSession | None:
    """Return the in-memory session object for server-side filing helpers.

    Existing callers should keep using get_session_meta() unless they truly
    need access to the Playwright page. API endpoints must still enforce
    tenant/case ownership before operating on the returned session.
    """
    return _sessions.get(session_id)


def is_session_expired(session_id: str) -> bool:
    session = _sessions.get(session_id)
    if not session:
        return True
    return (time.time() - session.last_activity_at) > SESSION_IDLE_SECONDS


async def inspect_live_session_dom(session_id: str) -> dict | None:
    """Read a bounded, redacted DOM snapshot from an existing live session.

    Development-only callers use this to calibrate read-only selectors against
    the real Playwright page after a human has authenticated in the streamed
    browser. It deliberately exposes no browser-control primitive: no click,
    no typing, no navigation, no caller-supplied JavaScript, no cookies/storage.
    """
    session = get_live_session(session_id)
    if not session:
        return None

    async def _text_from(root) -> str:
        try:
            return _redact_dev_dom_text(await root.locator("body").inner_text(timeout=1500))
        except Exception:
            return ""

    async def _html_from(root) -> str:
        try:
            return _redact_dev_dom_text(await root.content())
        except Exception:
            return ""

    async def _element_snapshot(locator, tag_hint: str | None = None) -> dict | None:
        try:
            text = _redact_dev_dom_text(await locator.inner_text(timeout=800))
        except Exception:
            text = ""
        attrs = {}
        for attr in _DEV_DOM_ALLOWED_ATTRS:
            try:
                safe = _safe_dev_dom_attr(attr, await locator.get_attribute(attr, timeout=500))
            except Exception:
                safe = None
            if safe not in (None, ""):
                attrs[attr] = safe
        tag = tag_hint or attrs.get("role") or "element"
        return {
            "tag": tag,
            "role": attrs.get("role"),
            "text": _truncate(text.strip(), _DEV_DOM_MAX_TEXT_CHARS),
            "attributes": attrs,
        }

    async def _collect_elements(root) -> list[dict]:
        elements: list[dict] = []
        seen: set[tuple[str, str, str]] = set()

        async def add_from_selector(selector: str, *, relevant_only: bool = False):
            if len(elements) >= _DEV_DOM_MAX_ELEMENTS:
                return
            try:
                loc = root.locator(selector)
                count = min(await loc.count(), _DEV_DOM_MAX_ELEMENTS - len(elements))
            except Exception:
                return
            for idx in range(count):
                if len(elements) >= _DEV_DOM_MAX_ELEMENTS:
                    return
                item = loc.nth(idx)
                snap = await _element_snapshot(item, selector)
                if not snap:
                    continue
                text = snap.get("text") or ""
                attrs = snap.get("attributes") or {}
                useful = bool(text or attrs)
                if relevant_only:
                    useful = bool(_DEV_DOM_REFERENCE_RE.search(text) or _DEV_DOM_RELEVANT_TEXT_RE.search(text))
                if not useful:
                    continue
                key = (selector, text[:120], json.dumps(attrs, sort_keys=True))
                if key in seen:
                    continue
                seen.add(key)
                elements.append(snap)

        for selector in _DEV_DOM_STRUCTURAL_SELECTORS:
            await add_from_selector(selector)
        for selector in _DEV_DOM_RELEVANT_SELECTORS:
            await add_from_selector(selector, relevant_only=True)
        return elements

    async def _frame_snapshot(frame, index: int) -> dict:
        body_text = await _text_from(frame)
        html = await _html_from(frame)
        return {
            "index": index,
            "name": _truncate(getattr(frame, "name", "") or "", 200),
            "url": _truncate(_redact_dev_dom_text(getattr(frame, "url", "") or ""), 2000),
            "body_text": _truncate(body_text, _DEV_DOM_MAX_BODY_CHARS),
            "html": _truncate(html, _DEV_DOM_MAX_HTML_CHARS),
            "elements": await _collect_elements(frame),
        }

    page = session.page
    body_text = await _text_from(page)
    html = await _html_from(page)
    try:
        title = await page.title()
    except Exception:
        title = ""

    frames = []
    for idx, frame in enumerate(getattr(page, "frames", []) or []):
        if idx == 0:
            continue
        frames.append(await _frame_snapshot(frame, idx))

    return {
        "session_id": session.session_id,
        "case_id": session.case_id,
        "portal_name": session.portal.get("portal_name"),
        "url": _truncate(_redact_dev_dom_text(getattr(page, "url", "") or ""), 2000),
        "title": _truncate(_redact_dev_dom_text(title), 500),
        "body_text": _truncate(body_text, _DEV_DOM_MAX_BODY_CHARS),
        "html": _truncate(html, _DEV_DOM_MAX_HTML_CHARS),
        "elements": await _collect_elements(page),
        "frames": frames,
        "limits": {
            "max_body_chars": _DEV_DOM_MAX_BODY_CHARS,
            "max_html_chars": _DEV_DOM_MAX_HTML_CHARS,
            "max_elements": _DEV_DOM_MAX_ELEMENTS,
            "max_text_chars": _DEV_DOM_MAX_TEXT_CHARS,
        },
    }


async def sweep_idle_sessions():
    """Close any session idle longer than SESSION_IDLE_SECONDS. Run on a timer from main.py."""
    now = time.time()
    async with _lock:
        stale = [sid for sid, s in _sessions.items() if now - s.last_activity_at > SESSION_IDLE_SECONDS]
    for sid in stale:
        logger.info(f"Govt sync: closing idle live session {sid}")
        await close_session(sid)
