"""
Tamil Nadu Mudhalvarin Mugavari filing assistant.

This adapter operates only on an already-open, tenant-scoped Playwright live
session. It never reads OTP/CAPTCHA values, never bypasses portal controls,
and never posts directly to Zoho/Desk APIs. The final Submit click is exposed
as a separate staff-confirmed action.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from .base import FilingActionResult, FilingState, HumanCheckpoint, PortalValidationError


TN_REFERENCE_RE = re.compile(
    r"\bTN/[A-Z0-9]+/[A-Z0-9]+/[A-Z]/PORTAL/[0-9A-Z]{7}/[0-9]{5,}\b",
    re.IGNORECASE,
)
TN_SHORT_ID_RE = re.compile(r"#\s*([0-9]{5,})\b")


@dataclass(frozen=True)
class TamilNaduField:
    key: str
    labels: tuple[str, ...]
    required: bool = False
    kind: str = "text"
    submission_key: str | None = None


class TamilNaduFilingAdapter:
    state_key = "tamil_nadu"
    form_path = "/portal/ta/newticket"
    signin_path = "/portal/ta/signin"

    fields = (
        TamilNaduField("address", ("Address", "முகவரி"), True, "text"),
        TamilNaduField("gender", ("Gender", "பாலினம்"), True, "select"),
        TamilNaduField("differently_abled", ("Differently Abled", "மாற்றுத்திறனாளி"), True, "select"),
        TamilNaduField("petition_scope", ("Public / Individual / Association", "Community / Individual", "Public"), True, "select"),
        TamilNaduField("department", ("Government Department", "அரசு துறை"), True, "select", "department"),
        TamilNaduField("local_body_type", ("Local Body Type", "உள்ளாட்சி வகை"), False, "select"),
        TamilNaduField("grievance_type", ("Grievance Type", "குறை வகை"), True, "select"),
        TamilNaduField("grievance_subtype", ("Grievance SubType", "Grievance Sub Type", "துணை குறை"), True, "select"),
        TamilNaduField("district", ("District", "மாவட்டம்"), True, "select", "district"),
        TamilNaduField("taluk", ("Taluk", "வட்டம்"), False, "select"),
        TamilNaduField("revenue_division", ("Revenue Division", "வருவாய் கோட்டம்"), True, "select"),
        TamilNaduField("block", ("Block", "வட்டாரம்"), False, "select"),
        TamilNaduField("village_panchayat", ("Village Panchayat", "ஊராட்சி"), False, "select"),
        TamilNaduField("street_name", ("Street Name", "தெரு"), False, "text"),
        TamilNaduField("door_no", ("Door No", "Door Number", "கதவு"), False, "text"),
        TamilNaduField("responsible_officer", ("Responsible Officer", "பொறுப்பு அலுவலர்"), True, "select"),
        TamilNaduField("subject", ("Subject", "பொருள்"), True, "text", "subject"),
    )

    def __init__(self, portal_row: dict):
        self.portal = portal_row or {}

    def portal_urls(self) -> dict:
        base = str(self.portal.get("base_url") or "https://cmhelpline.tnega.org").rstrip("/")
        return {
            "signin": f"{base}{self.signin_path}",
            "form": f"{base}{self.form_path}",
        }

    def required_input_fields(self) -> list[str]:
        return [field.key for field in self.fields if field.required]

    def build_field_values(self, submission: dict, staff_fields: dict) -> dict:
        submission = submission or {}
        staff_fields = staff_fields or {}
        values = {}
        for field in self.fields:
            raw_value = staff_fields.get(field.key)
            if raw_value in (None, "") and field.submission_key:
                raw_value = submission.get(field.submission_key)
            if raw_value not in (None, ""):
                values[field.key] = str(raw_value).strip()
        description = staff_fields.get("description") or submission.get("description")
        if description not in (None, ""):
            values["description"] = str(description).strip()
        return values

    def validate_required_inputs(self, values: dict) -> None:
        missing = []
        for key in self.required_input_fields():
            if not str(values.get(key) or "").strip():
                missing.append(key)
        if not str(values.get("description") or "").strip():
            missing.append("description")
        if missing:
            raise PortalValidationError(
                "Tamil Nadu filing needs staff-provided values before Needle can fill the portal form.",
                missing_fields=missing,
            )

    async def inspect_state(self, page) -> FilingActionResult:
        url = page.url
        text = await _safe_body_text(page)
        checkpoint = detect_human_checkpoint(url, text)
        if checkpoint:
            return FilingActionResult(
                state={
                    "otp": FilingState.OTP_REQUIRED,
                    "captcha": FilingState.CAPTCHA_REQUIRED,
                    "auth": FilingState.AUTH_REQUIRED,
                }[checkpoint.kind],
                note=checkpoint.note,
                human_checkpoints=[checkpoint],
                current_url=url,
            )
        if "/newticket" not in url:
            return FilingActionResult(
                state=FilingState.AUTH_REQUIRED,
                note="Open the Tamil Nadu grievance form after signing in.",
                current_url=url,
            )
        return FilingActionResult(state=FilingState.FORM_LOADING, current_url=url)

    async def prepare_to_submit(self, page, submission: dict, staff_fields: dict, attachments: list[str] | None = None) -> FilingActionResult:
        state = await self.inspect_state(page)
        if state.state in (FilingState.AUTH_REQUIRED, FilingState.OTP_REQUIRED, FilingState.CAPTCHA_REQUIRED):
            return state

        values = self.build_field_values(submission, staff_fields)
        self.validate_required_inputs(values)

        await _ensure_form_page(page, self.portal_urls()["form"])
        for field in self.fields:
            value = values.get(field.key)
            if not value:
                continue
            if field.kind == "select":
                await select_dropdown(page, field.labels, value)
            else:
                await fill_text_field(page, field.labels, value)
            await page.wait_for_timeout(250)

        await fill_rich_text(page, values["description"])

        attachment_results = []
        for attachment_path in attachments or []:
            try:
                attachment_results.append(await upload_file(page, attachment_path))
            except PortalValidationError as exc:
                attachment_results.append({
                    "source_path": attachment_path,
                    "file_name": Path(attachment_path).name,
                    "status": "failed",
                    "error": str(exc),
                })
                return FilingActionResult(
                    state=FilingState.ATTACHMENT_ERROR,
                    attachment_results=attachment_results,
                    validation_errors=[str(exc)],
                    note="Tamil Nadu portal rejected or did not visibly accept a selected attachment.",
                    current_url=page.url,
                )

        checkpoint = detect_human_checkpoint(page.url, await _safe_body_text(page))
        if checkpoint:
            return FilingActionResult(
                state={
                    "otp": FilingState.OTP_REQUIRED,
                    "captcha": FilingState.CAPTCHA_REQUIRED,
                    "auth": FilingState.AUTH_REQUIRED,
                }[checkpoint.kind],
                note=checkpoint.note,
                human_checkpoints=[checkpoint],
                current_url=page.url,
            )

        errors = await detect_validation_errors(page)
        if errors:
            return FilingActionResult(
                state=FilingState.VALIDATION_ERROR,
                validation_errors=errors,
                note="Tamil Nadu portal validation still needs staff review.",
                current_url=page.url,
            )

        return FilingActionResult(
            state=FilingState.READY_TO_SUBMIT,
            note="Form is filled. Staff must review the browser and explicitly submit.",
            fields={
                "department": values.get("department"),
                "grievance_type": values.get("grievance_type"),
                "district": values.get("district"),
                "reference": "Not yet assigned",
            },
            attachment_results=attachment_results,
            current_url=page.url,
        )

    async def submit_confirmed(self, page) -> FilingActionResult:
        checkpoint = detect_human_checkpoint(page.url, await _safe_body_text(page))
        if checkpoint:
            return FilingActionResult(
                state={
                    "otp": FilingState.OTP_REQUIRED,
                    "captcha": FilingState.CAPTCHA_REQUIRED,
                    "auth": FilingState.AUTH_REQUIRED,
                }[checkpoint.kind],
                note=checkpoint.note,
                human_checkpoints=[checkpoint],
                current_url=page.url,
            )

        try:
            submit = page.get_by_role("button", name=re.compile(r"submit|சமர்ப்பி", re.I)).first
            await submit.click(timeout=5000)
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception as exc:
            return FilingActionResult(
                state=FilingState.SUBMISSION_AMBIGUOUS,
                note=f"Submit action did not complete conclusively. Staff must verify in Tamil Nadu portal before retrying. ({type(exc).__name__})",
                current_url=page.url,
            )

        text = await _safe_body_text(page)
        reference = extract_reference(text)
        short_id = extract_short_id(text) or extract_short_id(page.url)
        if reference:
            return FilingActionResult(
                state=FilingState.SUBMITTED,
                reference_number=reference,
                short_id=short_id,
                note="Tamil Nadu grievance submitted and reference captured.",
                current_url=page.url,
            )
        if "/ticket/" in page.url and short_id:
            return FilingActionResult(
                state=FilingState.REFERENCE_CAPTURE_FAILED,
                short_id=short_id,
                note="Tamil Nadu ticket page opened, but full reference could not be captured automatically.",
                current_url=page.url,
            )
        return FilingActionResult(
            state=FilingState.SUBMISSION_AMBIGUOUS,
            note="Portal response was ambiguous. Staff must verify whether the grievance was created before retrying.",
            current_url=page.url,
        )


def detect_human_checkpoint(url: str, text: str) -> HumanCheckpoint | None:
    haystack = f"{url}\n{text}".lower()
    if "signin" in haystack or "sign in" in haystack or "login" in haystack:
        return HumanCheckpoint("auth", "Tamil Nadu portal sign-in is required. Staff must authenticate in the live browser.")
    if "otp" in haystack or "one time password" in haystack:
        return HumanCheckpoint("otp", "Tamil Nadu portal is asking for an OTP. Staff must enter it manually.")
    if "captcha" in haystack:
        return HumanCheckpoint("captcha", "Tamil Nadu portal is asking for CAPTCHA. Staff must solve it manually.")
    return None


def extract_reference(text: str) -> str | None:
    match = TN_REFERENCE_RE.search(text or "")
    return match.group(0).upper() if match else None


def extract_short_id(text: str) -> str | None:
    match = TN_SHORT_ID_RE.search(text or "")
    return f"#{match.group(1)}" if match else None


async def _safe_body_text(page) -> str:
    try:
        return await page.locator("body").inner_text(timeout=3000)
    except Exception:
        return ""


async def _ensure_form_page(page, form_url: str) -> None:
    if "/newticket" not in page.url:
        await page.goto(form_url, wait_until="domcontentloaded", timeout=20000)
    await page.wait_for_load_state("domcontentloaded", timeout=20000)


async def fill_text_field(page, labels: tuple[str, ...], value: str) -> None:
    locator = await _find_control(page, labels)
    await locator.fill(value, timeout=5000)


async def select_dropdown(page, labels: tuple[str, ...], value: str) -> None:
    locator = await _find_control(page, labels)
    try:
        await locator.select_option(label=value, timeout=3000)
        return
    except Exception:
        pass
    await locator.click(timeout=5000)
    option = page.get_by_role("option", name=re.compile(re.escape(value), re.I)).first
    try:
        await option.click(timeout=5000)
        return
    except Exception:
        pass
    option_text = page.get_by_text(re.compile(rf"^{re.escape(value)}$", re.I)).first
    await option_text.click(timeout=5000)


async def _find_control(page, labels: tuple[str, ...]):
    for label in labels:
        try:
            control = page.get_by_label(re.compile(re.escape(label), re.I)).first
            if await control.count():
                return control
        except Exception:
            pass
    for label in labels:
        try:
            node = page.get_by_text(re.compile(re.escape(label), re.I)).first
            if await node.count():
                container = node.locator("xpath=ancestor::*[self::div or self::section or self::li][1]")
                control = container.locator("input, textarea, select, [role='combobox']").first
                if await control.count():
                    return control
        except Exception:
            pass
    raise PortalValidationError(f"Could not find portal field labelled like: {', '.join(labels)}")


async def fill_rich_text(page, value: str) -> None:
    for frame in page.frames:
        try:
            editable = frame.locator("[contenteditable='true'], body").first
            if await editable.count():
                await editable.click(timeout=2000)
                await editable.fill(value, timeout=5000)
                text = await editable.inner_text(timeout=3000)
                if value[:40] in text:
                    return
        except Exception:
            continue
    locator = await _find_control(page, ("Grievance Details", "Description", "குறை விவரம்"))
    await locator.fill(value, timeout=5000)


async def upload_file(page, attachment_path: str) -> dict:
    path = Path(attachment_path)
    if not path.exists() or not path.is_file():
        raise PortalValidationError("Attachment file is not available to upload.")
    chooser = page.locator("input[type='file']").first
    if not await chooser.count():
        raise PortalValidationError("Tamil Nadu portal attachment control was not found.")
    await chooser.set_input_files(str(path), timeout=10000)
    file_name = path.name
    try:
        await page.get_by_text(re.compile(re.escape(file_name), re.I)).first.wait_for(timeout=8000)
    except Exception:
        error_texts = await detect_validation_errors(page)
        if error_texts:
            raise PortalValidationError("; ".join(error_texts[:3]))
        raise PortalValidationError(f"Attachment upload could not be visibly verified for {file_name}.")
    return {"source_path": str(path), "file_name": file_name, "status": "uploaded"}


async def detect_validation_errors(page) -> list[str]:
    errors = []
    for selector in (".error", ".field-error", "[role='alert']", ".formValidationError"):
        try:
            texts = await page.locator(selector).all_inner_texts(timeout=1000)
            errors.extend([text.strip() for text in texts if text.strip()])
        except Exception:
            continue
    return list(dict.fromkeys(errors))[:10]
