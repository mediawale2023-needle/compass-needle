"""Keep citizen phone numbers out of server logs.

`mask_phone()` is for code that deliberately logs a number. `PhoneRedactionFilter`
is the safety net installed on every handler at startup: it rewrites each record's
final message (and any traceback) so a 10–13 digit run, or an Indian number written
with spaces ("+91 98765 43210"), keeps only its last four digits. Message text is
never logged deliberately; see the call sites that log lengths instead.
"""
from __future__ import annotations

import logging
import re

_PHONE_RE = re.compile(
    r"(?<![\w.])(?:\+?91[\s-]?\d{5}[\s-]?\d{5}|\+?\d{10,13})(?![\w.])"
)


def mask_phone(value) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if not digits:
        return ""
    return f"***{digits[-4:]}" if len(digits) > 4 else "***"


def redact(text: str) -> str:
    return _PHONE_RE.sub(lambda m: mask_phone(m.group(0)), text)


class PhoneRedactionFilter(logging.Filter):
    """Mask phone numbers in the formatted message and traceback of every record."""

    _fmt = logging.Formatter()

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        record.msg = redact(message)
        record.args = None
        if record.exc_info and not record.exc_text:
            try:
                record.exc_text = self._fmt.formatException(record.exc_info)
            except Exception:
                record.exc_text = None
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True


def install(*logger_names: str) -> None:
    """Attach the filter to the handlers of the root logger and the named loggers."""
    flt = PhoneRedactionFilter()
    for name in ("", *logger_names):
        for handler in logging.getLogger(name).handlers:
            if not any(isinstance(f, PhoneRedactionFilter) for f in handler.filters):
                handler.addFilter(flt)
