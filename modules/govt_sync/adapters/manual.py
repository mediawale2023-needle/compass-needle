"""
modules/govt_sync/adapters/manual.py — the manual-assisted adapter used by
every portal today (state_branded and cpgrams alike).

prepare_submission() does NOT drive a browser. It hands back the note staff
see in the dashboard: open the real portal, paste in the AI-translated
worksheet fields, solve the CAPTCHA/OTP yourself, submit, then paste the
reference number back into Needle. That last step is a separate API call
(POST /api/cases/{id}/govt/submit) — this adapter doesn't try to scrape a
reference number out of a page it never touched.

check_status() is the one place this adapter *does* talk to the portal
directly — but only a read-only GET against a public reference-number
lookup page, no login, no staff interaction. Selectors/status wording below
are best-effort keyword matching, not a verified scrape of the live DOM
(nobody on this team has portal access yet — see the TODO in
modules/data/govt_portals.json `field_schema.taxonomy_verified`). If a
portal changes its page or the request fails, this fails closed to
`checked=False` rather than guessing a status, so a broken adapter shows up
as "needs manual check" on the dashboard instead of silently reporting a
wrong status to a citizen.
"""
import logging

from .base import GovtPortalAdapter, StatusResult, SubmissionResult, normalize_status_keywords

logger = logging.getLogger("needle.govt_sync.adapter.manual")

_STATUS_TIMEOUT_SECONDS = 12


class ManualAssistedAdapter(GovtPortalAdapter):
    def prepare_submission(self, submission: dict) -> SubmissionResult:
        portal_name = self.portal.get("portal_name", "this portal")
        base_url = self.portal.get("base_url", "")
        otp_bound = self.portal.get("otp_bound", True)

        note = f"Open {base_url} and file this on {portal_name} yourself: copy the worksheet fields in, "
        note += "complete the OTP verification, " if otp_bound else ""
        note += "solve the CAPTCHA, submit, then paste the reference number Needle asks for below."

        return SubmissionResult(
            reference_number=None,
            requires_staff_action=True,
            staff_action_note=note,
        )

    def check_status(self, reference_number: str, tenant_id: int | None = None) -> StatusResult:
        # tenant_id unused — this adapter's checks are portal-scoped, not
        # tenant-scoped. Accepted for interface compatibility (see base.py).
        mode = self.portal.get("status_check_mode", "login_required")
        status_url = self.portal.get("status_check_url")

        if mode != "public_reference" or not status_url or not reference_number:
            return StatusResult(status="", raw_portal_status=None, checked=False)

        try:
            import requests
            from bs4 import BeautifulSoup

            resp = requests.get(
                status_url,
                params={"refNumber": reference_number, "grievanceId": reference_number},
                timeout=_STATUS_TIMEOUT_SECONDS,
                headers={"User-Agent": "Mozilla/5.0 (compatible; NeedleGovtSync/1.0)"},
            )
            resp.raise_for_status()
            page_text = BeautifulSoup(resp.text, "html.parser").get_text(" ", strip=True)
        except Exception as e:
            logger.warning(f"Status check request failed for {self.portal.get('portal_name')} ref={reference_number}: {e}")
            return StatusResult(status="", raw_portal_status=None, checked=False)

        normalized = normalize_status_keywords(page_text)
        if not normalized:
            logger.info(
                f"Status check for {self.portal.get('portal_name')} ref={reference_number} returned "
                f"no recognisable status keyword — needs manual look (page wording may not match yet)"
            )
            return StatusResult(status="", raw_portal_status=page_text[:500], checked=False)

        return StatusResult(status=normalized, raw_portal_status=page_text[:500], checked=True)
