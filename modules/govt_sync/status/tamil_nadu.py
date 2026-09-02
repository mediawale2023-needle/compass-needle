"""
Tamil Nadu CM Helpline (Mudhalvarin Mugavari) authenticated status reader.

Operates only on an already-open, tenant-scoped Playwright live session that a
human has signed into. Flow:

    (checkpoint?) -> open My Petitions -> (checkpoint?) -> find THIS grievance's
    card structurally -> open it -> (checkpoint?) -> read the rendered status,
    department, last-updated, Action Taken Report, and replies -> normalize.

It never authenticates, never answers OTP/CAPTCHA, and never clicks anything
that would submit, edit, or reply to a grievance. Every "expected element not
found" path returns a fail-closed state — never a guessed status.

Selectors below are calibrated from a verified authenticated live DOM
inspection of the Tamil Nadu CM Helpline portal. Keep them TN-specific and
fail-closed: a missing/ambiguous element is not a successful status check.
"""
import re

from ..adapters.base import normalize_status_keywords
from ..filing.tamil_nadu import (
    _safe_body_text,
    detect_human_checkpoint,
    extract_reference,
    extract_short_id,
)
from .base import StatusCheckReply, StatusCheckResult, StatusCheckState


_CHECKPOINT_STATE = {
    "auth": StatusCheckState.AUTH_REQUIRED,
    "otp": StatusCheckState.OTP_REQUIRED,
    "captcha": StatusCheckState.CAPTCHA_REQUIRED,
}

_LAYOUT_SELECTOR = "#layoutContainer.Layout__twoColumn[role='main']"
_LIST_COLUMN_SELECTOR = ".Layout__layout1[data-id='column1']"
_LIST_BOX_SELECTOR = ".TicketListLeftContainer1__boxView"
_CARD_SELECTOR = ".TicketListItem__container"
_TITLE_SELECTOR = "[data-id^='ticket_title_']"
_SHORT_ID_SELECTOR = "[data-id^='ticket_id_']"
_CREATED_TIME_SELECTOR = "[data-id^='createdTime_'][title]"
_CARD_DEPARTMENT_SELECTOR = "[data-id='ticket_department_name']"
_CARD_STATUS_SELECTOR = ".TicketListItem_status .Badge__badge"
_EMPTY_LIST_SELECTOR = "[data-id='no_ticket']"
_EMPTY_LIST_TITLE_SELECTOR = "[data-id='no_ticket_title']"
_DETAIL_WRAPPER_SELECTOR = ".TicketDetailLeftContainer__wrapper"
_DETAIL_STATUS_SELECTOR = "[data-id='ticket_status_value']"
_DETAIL_STATUS_FALLBACK_SELECTOR = "[data-id^='ticket_status_']"
_POST_CONTAINER_SELECTOR = ".Post__container"
_POST_CONTENT_SELECTOR = ".Post__postContent"
_ENDUSER_THREAD_SELECTOR = ".enduser_thread"
_WEB_CONTENT_SELECTOR = ".web_cont"
_ACTION_TAKEN_UNAVAILABLE = "Action Taken Report iframe not accessible"

_MY_PETITIONS_LABELS = (
    "My Petitions", "My Grievances", "My Area", "My Tickets", "My Complaints",
    "எனது மனுக்கள்", "எனது குறைகள்", "எனது பகுதி",
)

# Portal status phrases seen or plausible in the walkthrough — used ONLY to
# lift a raw_list_status string out of a card's visible text when the card has
# no obvious status element. Never normalized here; never treated as canonical.
_STATUS_PHRASES = (
    "Pending Action", "Received", "Under Process", "In Process", "Processing",
    "Forwarded", "Assigned", "Disposed", "Resolved", "Closed", "Rejected",
    "Reopened", "Awaiting", "Acknowledged", "Registered",
)


def _url(page) -> str:
    return getattr(page, "url", "") or ""


async def _loc_text(loc) -> str:
    try:
        return await loc.inner_text(timeout=2000)
    except Exception:
        return ""


async def _count(loc) -> int:
    try:
        return await loc.count()
    except Exception:
        return 0


async def _all(loc) -> list:
    try:
        return await loc.all()
    except Exception:
        return []


async def _wait_settle(page, ms: int = 1200) -> None:
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    try:
        await page.wait_for_timeout(ms)
    except Exception:
        pass


def _phrase_in(text: str) -> str | None:
    lowered = (text or "").lower()
    for phrase in _STATUS_PHRASES:
        if phrase.lower() in lowered:
            return phrase
    return None


def _short_id_for(reference: str) -> str | None:
    tail = (reference or "").rstrip("/").rsplit("/", 1)[-1]
    digits = re.sub(r"\D", "", tail)
    return f"#{digits}" if len(digits) >= 5 else None


def _match_cards(cards: list, reference: str, short_id: str | None):
    """(matches, how). Exact full-reference match first; short ticket id only
    when it is unique AND the full reference appears on no card. Never guesses."""
    ref_l = reference.lower()
    exact = [(c, t) for (c, t) in cards if ref_l in (t or "").lower()]
    if exact:
        return exact, "reference"
    if short_id:
        digits = short_id.lstrip("#")
        tok = re.compile(rf"(?<!\d){re.escape(digits)}(?!\d)")
        by_id = [
            (c, t) for (c, t) in cards
            if ref_l not in (t or "").lower() and (f"#{digits}" in (t or "") or tok.search(t or ""))
        ]
        if by_id:
            return by_id, "short_id"
    return [], None


async def _attr(loc, name: str) -> str | None:
    try:
        return await loc.get_attribute(name, timeout=1000)
    except Exception:
        return None


async def _first_text(root, selector: str) -> str | None:
    try:
        loc = root.locator(selector).first
        if await _count(loc):
            txt = (await _loc_text(loc)).strip()
            if txt:
                return txt
    except Exception:
        return None
    return None


async def _labelled_value(page, labels: tuple[str, ...]) -> str | None:
    """Value of a 'Label: value' / dt-dd / th-td / label+sibling pair."""
    for label in labels:
        try:
            node = page.get_by_text(
                re.compile(rf"^\s*{re.escape(label)}\s*:?\s*$", re.I)
            ).first
            if await _count(node):
                container = node.locator(
                    "xpath=ancestor::*[self::tr or self::li or self::div or self::dl][1]"
                )
                raw = await _loc_text(container)
                if raw:
                    stripped = re.sub(rf"^\s*{re.escape(label)}\s*:?\s*", "", raw, flags=re.I)
                    line = next((ln.strip() for ln in stripped.splitlines() if ln.strip()), "")
                    if line and line.lower() != label.lower():
                        return line
        except Exception:
            continue
    body = await _safe_body_text(page)
    for label in labels:
        m = re.search(rf"{re.escape(label)}\s*[:\-]\s*(.+)", body, re.I)
        if m:
            value = m.group(1).splitlines()[0].strip()
            if value:
                return value
    return None


async def _extract_replies(page) -> list:
    # Verified DOM identifies the original petitioner post/thread
    # (.Post__container/.Post__postContent/.enduser_thread/.web_cont), but not a
    # stable officer reply/comment selector. Returning [] is safer than
    # misclassifying the original complaint as a reply.
    return []


async def _extract_action_taken_report_from_frames(page) -> str | None:
    """ATR/officer activity is rendered in a zappsusercontent iframe.

    Do not infer ATR from the parent body. If Playwright can read an accessible
    child frame, return matching frame text; otherwise report explicit
    unavailability without blocking the primary status read.
    """
    frames = list(getattr(page, "frames", []) or [])
    for frame in frames[1:]:
        url = str(getattr(frame, "url", "") or "")
        if "zappsusercontent.in" not in url and "action" not in url.lower():
            continue
        try:
            text = (await frame.locator("body").inner_text(timeout=2000)).strip()
        except Exception:
            continue
        if not text:
            continue
        labelled = await _labelled_value(frame, ("Action Taken Report", "Action Taken", "ATR",
                                                 "Resolution", "Reply", "Remarks", "Officer Remarks"))
        return labelled or text[:4000]
    if any("zappsusercontent.in" in str(getattr(frame, "url", "") or "") for frame in frames[1:]):
        return _ACTION_TAKEN_UNAVAILABLE
    return None


async def _extract_detail(page) -> dict:
    detail_status = await _first_text(page, _DETAIL_STATUS_SELECTOR)
    if not detail_status:
        detail_status = await _first_text(page, _DETAIL_STATUS_FALLBACK_SELECTOR)
    return {
        "status": detail_status,
        "last_updated": None,
        "department": None,
        "atr": await _extract_action_taken_report_from_frames(page),
        "replies": await _extract_replies(page),
    }


class TamilNaduStatusAdapter:
    state_key = "tamil_nadu"
    status_area_path = "/portal/ta/myarea"

    def __init__(self, portal_row: dict):
        self.portal = portal_row or {}

    def status_area_url(self) -> str:
        base = str(self.portal.get("base_url") or "https://cmhelpline.tnega.org").rstrip("/")
        field_schema = self.portal.get("field_schema") or {}
        path = field_schema.get("status_area_path") or self.status_area_path
        return f"{base}{path}"

    async def _checkpoint(self, page, *, mid_flow: bool = False) -> StatusCheckResult | None:
        url = _url(page)
        text = await _safe_body_text(page)
        checkpoint = detect_human_checkpoint(url, text)
        if not checkpoint:
            return None
        if checkpoint.kind == "auth" and mid_flow:
            return StatusCheckResult(
                state=StatusCheckState.SESSION_EXPIRED,
                note="The Tamil Nadu portal sign-in expired mid-check. Sign in again in the browser, then check again.",
                current_url=url,
            )
        return StatusCheckResult(
            state=_CHECKPOINT_STATE[checkpoint.kind], note=checkpoint.note, current_url=url,
        )

    async def _list_rendered(self, page) -> bool:
        for sel in (_LAYOUT_SELECTOR, _LIST_BOX_SELECTOR, _CARD_SELECTOR, _EMPTY_LIST_SELECTOR, _EMPTY_LIST_TITLE_SELECTOR):
            if await _count(page.locator(sel)):
                return True
        body = await _safe_body_text(page)
        return bool(re.search(r"no\s+(petitions|grievances|records|tickets|complaints)", body, re.I))

    async def _open_my_petitions(self, page) -> StatusCheckResult | None:
        """Prefer a real nav element (so the app's own viewId is used) over
        assuming the My Petitions URL. Returns a result on failure, else None."""
        clicked = False
        for label in _MY_PETITIONS_LABELS:
            try:
                link = page.get_by_role("link", name=re.compile(re.escape(label), re.I)).first
                if await _count(link):
                    await link.click(timeout=5000)
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            try:
                await page.goto(self.status_area_url(), wait_until="domcontentloaded", timeout=20000)
            except Exception:
                return StatusCheckResult(
                    state=StatusCheckState.PETITIONS_LOADING,
                    note="Could not open the Tamil Nadu My Petitions area — verify manually on the portal.",
                    current_url=_url(page),
                )
        await _wait_settle(page)
        if not await self._list_rendered(page):
            return StatusCheckResult(
                state=StatusCheckState.PETITIONS_LOADING,
                note="The Tamil Nadu My Petitions list did not finish loading — check again in a moment.",
                current_url=_url(page),
            )
        return None

    async def _petition_cards(self, page) -> list:
        containers = await _all(page.locator(_LIST_BOX_SELECTOR))
        cards = []
        for container in containers:
            items = await _all(container.locator(_CARD_SELECTOR))
            for item in items:
                if len(cards) >= 60:
                    return cards
                title = await _first_text(item, _TITLE_SELECTOR) or ""
                short = await _first_text(item, _SHORT_ID_SELECTOR) or ""
                full_text = "\n".join(part for part in (title, short, await _loc_text(item)) if part).strip()
                if full_text:
                    cards.append((item, full_text))
        return cards

    async def _card_status(self, card, card_text: str) -> str | None:
        loc = card.locator(_CARD_STATUS_SELECTOR).first
        if await _count(loc):
            txt = (await _loc_text(loc)).strip()
            if txt:
                return txt
            data_id = await _attr(loc, "data-id") or ""
            m = re.match(r"ticketStatus_(.+?)_\d+$", data_id)
            if m:
                return m.group(1).replace("_", " ").strip()
        return _phrase_in(card_text)

    async def _card_created_at(self, card) -> str | None:
        loc = card.locator(_CREATED_TIME_SELECTOR).first
        if not await _count(loc):
            return None
        return await _attr(loc, "title")

    async def _card_department(self, card) -> str | None:
        return await _first_text(card, _CARD_DEPARTMENT_SELECTOR)

    async def check_status_on_page(self, page, reference_number: str) -> StatusCheckResult:
        reference_number = (reference_number or "").strip()
        if page is None:
            return StatusCheckResult(
                state=StatusCheckState.PORTAL_ERROR,
                note="No live Tamil Nadu browser page is available.",
            )
        if not reference_number:
            return StatusCheckResult(
                state=StatusCheckState.STATUS_CHECK_INCONCLUSIVE,
                note="No Tamil Nadu reference number on file to look up.",
                current_url=_url(page),
            )
        short_id = _short_id_for(reference_number) or extract_short_id(reference_number)

        # 1. Blocked right now?
        checkpoint = await self._checkpoint(page)
        if checkpoint:
            return checkpoint

        # 2. My Petitions.
        nav = await self._open_my_petitions(page)
        if nav is not None:
            return nav

        # 3. The session can drop on that navigation.
        checkpoint = await self._checkpoint(page, mid_flow=True)
        if checkpoint:
            return checkpoint

        # 4. Identify this grievance's card — structurally, never by guessing.
        cards = await self._petition_cards(page)
        if not cards:
            return StatusCheckResult(
                state=StatusCheckState.CASE_NOT_FOUND,
                matched_count=0,
                reference_number=reference_number,
                short_id=short_id,
                note="No petitions were listed on the Tamil Nadu portal for this signed-in account — verify manually.",
                current_url=_url(page),
            )
        matches, how = _match_cards(cards, reference_number, short_id)
        if not matches:
            return StatusCheckResult(
                state=StatusCheckState.CASE_NOT_FOUND,
                matched_count=0,
                reference_number=reference_number,
                short_id=short_id,
                note="No Tamil Nadu petition matched this reference number — verify manually on the portal.",
                current_url=_url(page),
            )
        if len(matches) > 1:
            return StatusCheckResult(
                state=StatusCheckState.AMBIGUOUS_MATCH,
                matched_count=len(matches),
                reference_number=reference_number,
                short_id=short_id,
                note="More than one Tamil Nadu petition matched — this grievance can't be identified automatically. Verify manually.",
                current_url=_url(page),
            )

        card, card_text = matches[0]
        raw_list_status = await self._card_status(card, card_text)
        card_created_at = await self._card_created_at(card)
        card_department = await self._card_department(card)

        # 5. Open the ticket. Read-only click — opening a detail view, nothing
        #    that submits/edits/replies.
        try:
            opener = card.locator(_TITLE_SELECTOR).first
            if await _count(opener):
                await opener.click(timeout=5000)
            else:
                fallback = card.locator("a, button").first
                if await _count(fallback):
                    await fallback.click(timeout=5000)
                else:
                    await card.click(timeout=5000)
        except Exception:
            return StatusCheckResult(
                state=StatusCheckState.STATUS_FORM_LOADING,
                raw_list_status=raw_list_status,
                reference_number=reference_number,
                short_id=short_id,
                matched_count=1,
                note="Could not open the Tamil Nadu petition detail — check again in a moment.",
                current_url=_url(page),
            )
        await _wait_settle(page)

        checkpoint = await self._checkpoint(page, mid_flow=True)
        if checkpoint:
            return checkpoint

        # 6. Read the rendered detail.
        detail_wrapper = page.locator(_DETAIL_WRAPPER_SELECTOR).first
        if not await _count(detail_wrapper):
            return StatusCheckResult(
                state=StatusCheckState.STATUS_FORM_LOADING,
                raw_list_status=raw_list_status,
                last_updated=None,
                department=card_department,
                reference_number=reference_number,
                short_id=short_id,
                matched_count=1,
                note="Tamil Nadu petition detail did not render the verified detail container — check again in a moment.",
                current_url=_url(page),
            )
        detail = await _extract_detail(page)
        detail_text = await _loc_text(detail_wrapper)
        found_refs = [ref for ref in re.findall(
            r"\bTN/[A-Z0-9]+/[A-Z0-9]+/[A-Z]/PORTAL/[0-9A-Z]{7}/[0-9]{5,}\b",
            detail_text,
            flags=re.I,
        )]
        if not any(ref.lower() == reference_number.lower() for ref in found_refs):
            found_ref = extract_reference(detail_text)
            return StatusCheckResult(
                state=StatusCheckState.STATUS_CHECK_INCONCLUSIVE,
                raw_list_status=raw_list_status,
                reference_number=found_ref,
                short_id=short_id,
                matched_count=1,
                note="Opened a Tamil Nadu petition detail without verified matching reference text — verify manually.",
                current_url=_url(page),
            )

        raw_detail_status = detail.get("status")
        replies = detail.get("replies") or []
        common = dict(
            raw_list_status=raw_list_status,
            raw_detail_status=raw_detail_status,
            created_at=card_created_at,
            last_updated=detail.get("last_updated"),
            department=detail.get("department") or card_department,
            action_taken_report=detail.get("atr"),
            replies=replies,
            reference_number=reference_number,
            short_id=short_id,
            matched_count=1,
            current_url=_url(page),
        )
        if not (raw_detail_status or raw_list_status):
            return StatusCheckResult(
                state=StatusCheckState.STATUS_CHECK_INCONCLUSIVE,
                note="Reached the Tamil Nadu petition but no status text could be read — verify manually on the portal.",
                **common,
            )

        # 7. Normalize the DETAIL wording first (the authoritative view),
        #    falling back to the list wording. normalize_status_keywords() is
        #    itself fail-closed on cross-bucket ambiguity.
        normalized = normalize_status_keywords(raw_detail_status or raw_list_status or "")
        if not normalized:
            return StatusCheckResult(
                state=StatusCheckState.STATUS_CHECK_INCONCLUSIVE,
                note=(
                    f"The Tamil Nadu portal's wording ({(raw_detail_status or raw_list_status)!r}) "
                    "did not map to a known status — recorded for manual review."
                ),
                **common,
            )
        return StatusCheckResult(
            state=StatusCheckState.STATUS_CHECKED,
            normalized_status=normalized,
            note="Read from the authenticated Tamil Nadu portal.",
            **common,
        )
