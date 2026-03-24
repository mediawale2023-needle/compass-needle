"""
Email dispatch for escalation letters via AWS SES.
Uses boto3 to send formal letters to government officers.
Falls back gracefully if SES is not configured.
"""
import os
import logging
from datetime import datetime

logger = logging.getLogger("needle.email")

SES_REGION = os.getenv("AWS_SES_REGION", "ap-south-1")
SES_FROM_EMAIL = os.getenv("SES_FROM_EMAIL", "")
SES_ENABLED = bool(SES_FROM_EMAIL)


def send_escalation_email(officer_email, officer_name, officer_designation,
                          mp_name, constituency, case_ref, letter_content,
                          subject=None):
    """
    Send an escalation letter to a government officer via SES.
    Returns (success: bool, message_id: str or None, error: str or None)
    """
    if not SES_ENABLED:
        logger.warning("SES not configured (SES_FROM_EMAIL not set). Email not sent.")
        return False, None, "Email not configured. Set SES_FROM_EMAIL environment variable."

    if not officer_email:
        return False, None, "Officer email not provided"

    try:
        import boto3
        client = boto3.client('ses', region_name=SES_REGION)

        if not subject:
            subject = f"Grievance Escalation — {case_ref or 'Case'} — {constituency}"

        html_body = f"""
        <div style="font-family: 'Georgia', serif; max-width: 700px; margin: 0 auto; padding: 40px; color: #1a1a1a;">
            <div style="border-bottom: 3px solid #1a365d; padding-bottom: 20px; margin-bottom: 30px;">
                <h2 style="margin: 0; color: #1a365d; font-size: 18px;">Office of {mp_name}</h2>
                <p style="margin: 4px 0 0; color: #666; font-size: 13px;">{constituency}</p>
            </div>

            <p style="font-size: 14px; margin-bottom: 8px;"><strong>To:</strong> {officer_name}, {officer_designation}</p>
            <p style="font-size: 14px; margin-bottom: 8px;"><strong>Date:</strong> {datetime.utcnow().strftime('%d %B %Y')}</p>
            {f'<p style="font-size: 14px; margin-bottom: 20px;"><strong>Ref:</strong> {case_ref}</p>' if case_ref else ''}

            <div style="font-size: 14px; line-height: 1.8; white-space: pre-wrap; margin: 24px 0;">
{letter_content}
            </div>

            <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd;">
                <p style="font-size: 14px; margin: 0;">Regards,</p>
                <p style="font-size: 14px; font-weight: bold; margin: 4px 0 0;">{mp_name}</p>
            </div>

            <div style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #eee; font-size: 11px; color: #999;">
                This is an official communication sent via Needle Grievance Intelligence Platform.
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
Sent via Needle Grievance Intelligence Platform.
"""

        response = client.send_email(
            Source=f"{mp_name} <{SES_FROM_EMAIL}>",
            Destination={'ToAddresses': [officer_email]},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {
                    'Text': {'Data': text_body, 'Charset': 'UTF-8'},
                    'Html': {'Data': html_body, 'Charset': 'UTF-8'},
                }
            }
        )

        message_id = response.get('MessageId', '')
        logger.info(f"Escalation email sent to {officer_email} (SES ID: {message_id})")
        return True, message_id, None

    except ImportError:
        logger.error("boto3 not installed. Cannot send SES emails.")
        return False, None, "boto3 not installed"
    except Exception as e:
        logger.exception(f"SES email failed: {e}")
        return False, None, str(e)
