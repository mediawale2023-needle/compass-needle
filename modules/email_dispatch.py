"""
Email dispatch for escalation letters.
Supports two backends (checked in order):
  1. AWS SES  (set SES_FROM_EMAIL + AWS credentials)
  2. SMTP     (set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM)
Falls back gracefully if neither is configured.
"""
import os
import ssl
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

logger = logging.getLogger("needle.email")

# ─── SES config ───
SES_REGION = os.getenv("AWS_SES_REGION", "ap-south-1")
SES_FROM_EMAIL = os.getenv("SES_FROM_EMAIL", "")
SES_ENABLED = bool(SES_FROM_EMAIL)

# ─── SMTP config ───
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "") or SMTP_USER  # fallback to SMTP_USER
SMTP_ENABLED = bool(SMTP_HOST and SMTP_USER and SMTP_PASS)


def _build_email_content(officer_name, officer_designation, mp_name,
                         constituency, case_ref, letter_content):
    """Build HTML and plain text email bodies."""
    html_body = f"""
    <div style="font-family: 'Georgia', serif; max-width: 700px; margin: 0 auto; padding: 40px; color: #1a1a1a;">
        <div style="border-bottom: 3px solid #1a365d; padding-bottom: 20px; margin-bottom: 30px;">
            <h2 style="margin: 0; color: #1a365d; font-size: 18px;">Office of {mp_name}</h2>
            <p style="margin: 4px 0 0; color: #666; font-size: 13px;">{constituency}</p>
        </div>

        <p style="font-size: 14px; margin-bottom: 8px;"><strong>To:</strong> {officer_name}, {officer_designation}</p>
        <p style="font-size: 14px; margin-bottom: 8px;"><strong>Date:</strong> {datetime.utcnow().strftime('%d %B %Y')}</p>
        {'<p style="font-size: 14px; margin-bottom: 20px;"><strong>Ref:</strong> ' + case_ref + '</p>' if case_ref else ''}

        <div style="font-size: 14px; line-height: 1.8; white-space: pre-wrap; margin: 24px 0;">
{letter_content}
        </div>

        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd;">
            <p style="font-size: 14px; margin: 0;">Regards,</p>
            <p style="font-size: 14px; font-weight: bold; margin: 4px 0 0;">{mp_name}</p>
        </div>

        <div style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #eee; font-size: 11px; color: #999;">
            This is an official communication sent via Ambassador Grievance Intelligence Platform.
            Please respond at your earliest convenience.
        </div>
    </div>
    """

    text_body = f"""
Office of {mp_name}
{constituency}

To: {officer_name}, {officer_designation}
Date: {datetime.utcnow().strftime('%d %B %Y')}
{"Ref: " + case_ref if case_ref else ""}

{letter_content}

Regards,
{mp_name}

---
Sent via Ambassador Grievance Intelligence Platform.
"""
    return html_body, text_body


def _send_via_ses(to_email, subject, html_body, text_body, from_display_name):
    """Send via AWS SES. Returns (success, message_id, error)."""
    try:
        import boto3
        client = boto3.client('ses', region_name=SES_REGION)
        response = client.send_email(
            Source=f"{from_display_name} <{SES_FROM_EMAIL}>",
            Destination={'ToAddresses': [to_email]},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {
                    'Text': {'Data': text_body, 'Charset': 'UTF-8'},
                    'Html': {'Data': html_body, 'Charset': 'UTF-8'},
                }
            }
        )
        message_id = response.get('MessageId', '')
        logger.info(f"SES email sent to {to_email} (ID: {message_id})")
        return True, message_id, None
    except ImportError:
        return False, None, "boto3 not installed"
    except Exception as e:
        logger.exception(f"SES email failed: {e}")
        return False, None, str(e)


def _send_via_smtp(to_email, subject, html_body, text_body, from_display_name):
    """Send via SMTP (Gmail, Outlook, etc.). Returns (success, message_id, error)."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_display_name} <{SMTP_FROM}>"
        msg["To"] = to_email

        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, [to_email], msg.as_string())

        logger.info(f"SMTP email sent to {to_email} via {SMTP_HOST}")
        return True, f"smtp-{datetime.utcnow().isoformat()}", None
    except Exception as e:
        logger.exception(f"SMTP email failed: {e}")
        return False, None, str(e)


def send_escalation_email(officer_email, officer_name, officer_designation,
                          mp_name, constituency, case_ref, letter_content,
                          subject=None):
    """
    Send an escalation letter to a government officer.
    Tries SES first, then SMTP.
    Returns (success: bool, message_id: str or None, error: str or None)
    """
    if not officer_email:
        return False, None, "Officer email not provided"

    if not subject:
        subject = f"Grievance Escalation — {case_ref or 'Case'} — {constituency}"

    html_body, text_body = _build_email_content(
        officer_name, officer_designation, mp_name,
        constituency, case_ref, letter_content
    )

    # Try SES first
    if SES_ENABLED:
        success, mid, error = _send_via_ses(officer_email, subject, html_body, text_body, mp_name)
        if success:
            return True, mid, None
        logger.warning(f"SES failed ({error}), trying SMTP fallback...")

    # Try SMTP
    if SMTP_ENABLED:
        return _send_via_smtp(officer_email, subject, html_body, text_body, mp_name)

    # Neither configured
    config_hint = "Set SMTP_HOST, SMTP_USER, SMTP_PASS env vars (or SES_FROM_EMAIL for AWS SES)."
    logger.warning(f"No email backend configured. {config_hint}")
    return False, None, f"Email not configured. {config_hint}"
