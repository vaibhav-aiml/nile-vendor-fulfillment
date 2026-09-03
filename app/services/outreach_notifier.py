import logging
from typing import Optional
import requests
from app.core.config import settings

logger = logging.getLogger(__name__)


def send_whatsapp_vendor_notification(
    to_phone: str,
    vendor_name: str,
    itinerary_id: str,
    custom_message: Optional[str] = None,
) -> bool:
    """
    Sends an automated WhatsApp notification to a vendor using Twilio's WhatsApp API.
    If Twilio credentials are not configured, logs a warning and gracefully skips.
    """
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        logger.warning("Twilio credentials not configured. Skipping WhatsApp notification.")
        return False

    # Ensure to_phone is formatted for WhatsApp (e.g. whatsapp:+91...)
    to_whatsapp = to_phone if to_phone.startswith("whatsapp:") else f"whatsapp:{to_phone}"
    from_whatsapp = settings.TWILIO_WHATSAPP_FROM

    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"

    data = {
        "To": to_whatsapp,
        "From": from_whatsapp,
    }

    # If a template SID is configured, use it (required for initial outbound business session)
    if settings.TWILIO_WHATSAPP_TEMPLATE_SID:
        data["ContentSid"] = settings.TWILIO_WHATSAPP_TEMPLATE_SID
    else:
        body = (
            custom_message
            or f"Hello {vendor_name}! You have a new booking inquiry from NILE Travel for itinerary {itinerary_id}. Please check your phone for ops verification."
        )
        data["Body"] = body

    try:
        res = requests.post(
            url,
            data=data,
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            timeout=10,
        )
        if res.status_code in (200, 201):
            msg_sid = res.json().get("sid")
            logger.info(f"WhatsApp notification sent to {to_whatsapp} for {vendor_name}. Message SID: {msg_sid}")
            return True
        else:
            logger.error(f"Twilio WhatsApp error ({res.status_code}): {res.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message via Twilio: {e}")
        return False


def send_email_vendor_notification(
    to_email: str,
    vendor_name: str,
    itinerary_id: str,
    service_date: Optional[str] = None,
    group_size: int = 1,
) -> bool:
    """
    Sends an automated email booking inquiry to a non-partnered vendor using Resend API.
    """
    if not settings.RESEND_API_KEY:
        logger.warning("Resend API key not configured. Skipping email notification.")
        return False

    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
        "Content-Type": "application/json",
    }

    subject = f"Booking Inquiry: NILE Travel Platform (Itinerary {itinerary_id})"
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
        <h2 style="color: #0f172a;">NILE Travel Platform — Booking Inquiry</h2>
        <p>Dear <strong>{vendor_name}</strong>,</p>
        <p>Our operations team has received a travel itinerary booking request for your establishment on the Bangalore &rarr; Goa route.</p>
        <div style="background-color: #f8fafc; padding: 15px; border-radius: 6px; margin: 20px 0;">
            <p style="margin: 5px 0;"><strong>Itinerary ID:</strong> {itinerary_id}</p>
            <p style="margin: 5px 0;"><strong>Party Size:</strong> {group_size} travelers</p>
            {f'<p style="margin: 5px 0;"><strong>Requested Date:</strong> {service_date}</p>' if service_date else ''}
        </div>
        <p>Our operations staff will contact your reservations desk shortly to confirm availability and lock pricing.</p>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
        <p style="font-size: 12px; color: #64748b;">This automated notice was dispatched by the NILE Vendor Fulfillment Service.</p>
    </div>
    """

    payload = {
        "from": settings.RESEND_FROM_EMAIL,
        "to": to_email,
        "subject": subject,
        "html": html_content,
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code in (200, 201):
            email_id = res.json().get("id")
            logger.info(f"Outreach email dispatched to {to_email} via Resend. Email ID: {email_id}")
            return True
        else:
            logger.error(f"Resend email dispatch error ({res.status_code}): {res.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to dispatch email via Resend: {e}")
        return False
