"""Citizen phone numbers and message text stay out of server logs."""
import logging
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.log_redaction import PhoneRedactionFilter, install, mask_phone, redact  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_mask_phone_keeps_last_four():
    assert mask_phone("+91 98123 45678") == "***5678"
    assert mask_phone("919812345678") == "***5678"
    assert mask_phone("") == "" and mask_phone(None) == ""


def test_redact_masks_numbers_but_not_ids_or_small_numbers():
    line = "Sent to 919812345678 and +91 98000 00001 for case 1234 tenant=3 wamid.HBgMOTE5ODEyMzQ1Njc4FQIAEhgg took 12.5s"
    out = redact(line)
    assert "919812345678" not in out and "98000 00001" not in out
    assert "***5678" in out and "***0001" in out
    assert "case 1234 tenant=3" in out and "wamid.HBgMOTE5ODEyMzQ1Njc4FQIAEhgg" in out and "12.5s" in out


def test_filter_masks_formatted_args_and_tracebacks(caplog):
    log = logging.getLogger("needle.test.redaction")
    handler = logging.Handler()
    records = []
    handler.emit = records.append
    handler.addFilter(PhoneRedactionFilter())
    log.addHandler(handler)
    try:
        log.warning("Message from %s failed: %s", "919812345678", "boom")
        try:
            raise ValueError("bad number +919812345678")
        except ValueError:
            log.exception("send to %s", "+919812345678")
    finally:
        log.removeHandler(handler)
    assert records[0].getMessage() == "Message from ***5678 failed: boom"
    assert "919812345678" not in records[1].getMessage()
    assert "919812345678" not in (records[1].exc_text or "") and "***5678" in records[1].exc_text


def test_install_is_idempotent():
    root = logging.getLogger()
    added = False
    if not root.handlers:
        root.addHandler(logging.NullHandler())
        added = True
    install()
    install()
    for h in root.handlers:
        assert sum(isinstance(f, PhoneRedactionFilter) for f in h.filters) == 1
    if added:
        root.handlers.clear()


def test_no_message_text_diagnostics_left_in_code():
    for path in ("main.py", "sansadx_backend/ai_engine.py", "modules/briefcase_rules.py"):
        src = (ROOT / path).read_text()
        assert "INTENT_DIAG" not in src, path
        assert "raw_message[:160]" not in src, path
        assert "(message_body or \"\")[:240]" not in src, path


def test_backend_installs_redaction_on_import():
    src = (ROOT / "main.py").read_text()
    assert '_install_log_redaction("uvicorn", "uvicorn.error", "uvicorn.access")' in src
