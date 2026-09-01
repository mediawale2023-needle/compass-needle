from dataclasses import dataclass, field


class FilingState:
    AUTH_REQUIRED = "AUTH_REQUIRED"
    OTP_REQUIRED = "OTP_REQUIRED"
    CAPTCHA_REQUIRED = "CAPTCHA_REQUIRED"
    FORM_LOADING = "FORM_LOADING"
    DEPENDENCY_LOADING = "DEPENDENCY_LOADING"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    ATTACHMENT_ERROR = "ATTACHMENT_ERROR"
    READY_TO_SUBMIT = "READY_TO_SUBMIT"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    REFERENCE_CAPTURE_FAILED = "REFERENCE_CAPTURE_FAILED"
    SUBMISSION_AMBIGUOUS = "SUBMISSION_AMBIGUOUS"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    PORTAL_ERROR = "PORTAL_ERROR"


@dataclass
class HumanCheckpoint:
    kind: str
    note: str


class PortalValidationError(ValueError):
    def __init__(self, message: str, *, missing_fields: list[str] | None = None):
        super().__init__(message)
        self.missing_fields = missing_fields or []


@dataclass
class FilingActionResult:
    state: str
    note: str | None = None
    fields: dict = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    attachment_results: list[dict] = field(default_factory=list)
    human_checkpoints: list[HumanCheckpoint] = field(default_factory=list)
    reference_number: str | None = None
    short_id: str | None = None
    current_url: str | None = None

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "note": self.note,
            "fields": self.fields,
            "missing_fields": self.missing_fields,
            "validation_errors": self.validation_errors,
            "attachment_results": self.attachment_results,
            "human_checkpoints": [checkpoint.__dict__ for checkpoint in self.human_checkpoints],
            "reference_number": self.reference_number,
            "short_id": self.short_id,
            "current_url": self.current_url,
        }
