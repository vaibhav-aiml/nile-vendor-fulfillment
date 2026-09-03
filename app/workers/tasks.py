import uuid
import asyncio
import logging
from datetime import datetime, timezone
from celery import shared_task
from app.core.database import SessionLocal
from app.core.config import settings
from app.models.booking import FulfillmentRequest, FulfillmentStatus, BookingChannel
from app.models.vendor import Vendor
from app.services.partner_booking import get_partner_adapter
from app.services.event_publisher import event_publisher

logger = logging.getLogger(__name__)


@shared_task(name="app.workers.tasks.attempt_partner_booking")
def attempt_partner_booking(request_id_str: str) -> dict:
    """
    Async background task to execute programmatic booking for partnered vendors.
    """
    db = SessionLocal()
    try:
        req_uuid = uuid.UUID(request_id_str)
        req = db.query(FulfillmentRequest).filter(FulfillmentRequest.id == req_uuid).first()
        if not req:
            logger.error(f"FulfillmentRequest {request_id_str} not found for partner booking.")
            return {"status": "error", "message": "Request not found"}

        vendor = db.query(Vendor).filter(Vendor.id == req.vendor_id).first()
        adapter = get_partner_adapter(vendor.category.value if vendor else None)

        booking_result = asyncio.run(
            adapter.book(
                request_id=str(req.id),
                vendor_id=str(req.vendor_id),
                service_date_start=req.service_date_start,
                service_date_end=req.service_date_end,
                group_size=req.group_size,
            )
        )

        if booking_result.success:
            req.status = FulfillmentStatus.CONFIRMED
            req.external_reference_id = booking_result.external_reference_id
            if booking_result.pricing_locked:
                req.pricing_locked = booking_result.pricing_locked
            req.notes = (req.notes or "") + f" [Programmatic booking confirmed: ref={req.external_reference_id}]"
            db.commit()

            event_publisher.publish_event(
                event_type="BOOKING_CONFIRMED",
                payload={
                    "request_id": str(req.id),
                    "itinerary_id": req.itinerary_id,
                    "vendor_id": str(req.vendor_id),
                    "external_reference_id": req.external_reference_id,
                    "pricing_locked": float(req.pricing_locked) if req.pricing_locked else None,
                },
            )
            return {"status": "confirmed", "external_ref": req.external_reference_id}
        else:
            req.status = FulfillmentStatus.ALTERNATE_NEEDED
            req.notes = (req.notes or "") + f" [Programmatic booking failed: {booking_result.error_message}]"
            db.commit()

            event_publisher.publish_event(
                event_type="ALTERNATE_NEEDED",
                payload={
                    "request_id": str(req.id),
                    "itinerary_id": req.itinerary_id,
                    "vendor_id": str(req.vendor_id),
                    "reason": booking_result.error_message or "Partner API rejection",
                },
            )
            return {"status": "alternate_needed", "reason": booking_result.error_message}
    except Exception as e:
        logger.exception(f"Unexpected error executing partner booking for {request_id_str}: {e}")
        db.rollback()
        return {"status": "error", "error": str(e)}
    finally:
        db.close()


@shared_task(name="app.workers.tasks.initiate_hitl_outreach")
def initiate_hitl_outreach(request_id_str: str) -> dict:
    """
    Background task to initiate HITL operations outreach for non-partnered vendors.
    Queues the request into the internal Ops Dashboard.
    """
    db = SessionLocal()
    try:
        req_uuid = uuid.UUID(request_id_str)
        req = db.query(FulfillmentRequest).filter(FulfillmentRequest.id == req_uuid).first()
        if not req:
            return {"status": "error", "message": "Request not found"}

        logger.info(f"Queued HITL outreach for request {request_id_str}, vendor {req.vendor_id}. SLA deadline: {req.sla_deadline}")
        
        event_publisher.publish_event(
            event_type="OUTREACH_QUEUED",
            payload={
                "request_id": str(req.id),
                "itinerary_id": req.itinerary_id,
                "vendor_id": str(req.vendor_id),
                "sla_deadline": req.sla_deadline.isoformat() if req.sla_deadline else None,
            }
        )
        return {"status": "queued", "request_id": request_id_str}
    finally:
        db.close()


@shared_task(name="app.workers.tasks.check_outreach_sla_timeouts")
def check_outreach_sla_timeouts() -> dict:
    """
    Periodic check for non-partnered requests exceeding SLA without confirmation.
    Escalates status to ALTERNATE_NEEDED and emits notification event.
    """
    db = SessionLocal()
    now_utc = datetime.now(timezone.utc)
    escalated_count = 0

    try:
        breached_requests = (
            db.query(FulfillmentRequest)
            .filter(
                FulfillmentRequest.booking_channel == BookingChannel.HITL_MANUAL,
                FulfillmentRequest.status.in_([FulfillmentStatus.PENDING, FulfillmentStatus.OUTREACH_IN_PROGRESS]),
                FulfillmentRequest.sla_deadline.isnot(None),
                FulfillmentRequest.sla_deadline < now_utc,
            )
            .all()
        )

        for req in breached_requests:
            req.status = FulfillmentStatus.ALTERNATE_NEEDED
            escalation_note = (
                f"\n[SYSTEM SLA ESCALATION] Outreach SLA exceeded after "
                f"{settings.OUTREACH_SLA_HOURS}h without vendor confirmation. "
                f"Marked for alternate vendor selection."
            )
            req.notes = (req.notes or "") + escalation_note
            escalated_count += 1

            event_publisher.publish_event(
                event_type="OUTREACH_TIMEOUT",
                payload={
                    "request_id": str(req.id),
                    "itinerary_id": req.itinerary_id,
                    "vendor_id": str(req.vendor_id),
                    "sla_deadline": req.sla_deadline.isoformat() if req.sla_deadline else None,
                    "status": FulfillmentStatus.ALTERNATE_NEEDED.value,
                    "reason": f"SLA of {settings.OUTREACH_SLA_HOURS} hours expired",
                },
            )

        if escalated_count > 0:
            db.commit()
            logger.warning(f"SLA Escalation: {escalated_count} requests marked ALTERNATE_NEEDED.")

        return {"escalated_count": escalated_count}
    except Exception as e:
        logger.exception(f"Error during SLA timeout check: {e}")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()
