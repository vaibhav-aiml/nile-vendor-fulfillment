import uuid
from typing import List, Tuple
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.vendor import Vendor, PartnershipStatus
from app.models.booking import FulfillmentRequest, FulfillmentStatus, BookingChannel
from app.schemas.contracts import ItineraryFulfillmentIntakeRequest, ItineraryItemIntake


class DuplicateIntakeError(Exception):
    """Raised when an intake request for an itinerary is already processed."""
    pass


class VendorNotFoundError(Exception):
    """Raised when an intake item refers to a vendor not present in the DB."""
    pass


def route_and_dispatch_request(db: Session, request: FulfillmentRequest, vendor: Vendor):
    """
    Evaluates vendor partnership status and dispatches fulfillment workflow:
    - Partnered: programmatic booking attempt via Celery task
    - Non-partnered: queues request for HITL manual outreach in Ops Dashboard
    """
    from app.workers.tasks import attempt_partner_booking, initiate_hitl_outreach

    if vendor.partnership_status == PartnershipStatus.PARTNERED:
        request.booking_channel = BookingChannel.PROGRAMMATIC_API
        request.status = FulfillmentStatus.PENDING
        db.commit()
        db.refresh(request)
        
        try:
            attempt_partner_booking.apply_async(args=[str(request.id)], retry=False)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not enqueue partner booking task to broker (is Redis running?): {e}")
    else:
        request.booking_channel = BookingChannel.HITL_MANUAL
        request.status = FulfillmentStatus.PENDING
        
        now_utc = datetime.now(timezone.utc)
        request.sla_deadline = now_utc + timedelta(hours=settings.OUTREACH_SLA_HOURS)
        db.commit()
        db.refresh(request)

        try:
            initiate_hitl_outreach.apply_async(args=[str(request.id)], retry=False)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not enqueue HITL outreach task to broker (is Redis running?): {e}")


def process_itinerary_intake(
    db: Session,
    intake: ItineraryFulfillmentIntakeRequest
) -> Tuple[List[FulfillmentRequest], bool]:
    """
    Idempotent processing of an incoming itinerary fulfillment request.
    
    Returns:
        Tuple[List[FulfillmentRequest], bool]:
        - List of FulfillmentRequest entities
        - Boolean `is_duplicate`: True if requests were already present and retrieved,
          False if newly created and dispatched.
    """
    existing_requests = (
        db.query(FulfillmentRequest)
        .filter(FulfillmentRequest.itinerary_id == intake.itinerary_id)
        .all()
    )

    if existing_requests:
        # Idempotency safeguard: return already created requests rather than re-creating duplicates
        return existing_requests, True

    created_requests: List[FulfillmentRequest] = []

    for item in intake.items:
        try:
            vendor_uuid = uuid.UUID(item.vendor_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid vendor_id UUID format: '{item.vendor_id}'"
            )

        vendor = db.query(Vendor).filter(Vendor.id == vendor_uuid).first()
        if not vendor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vendor with id '{item.vendor_id}' not found. Discovery module sync may be required."
            )

        req = FulfillmentRequest(
            itinerary_id=intake.itinerary_id,
            vendor_id=vendor.id,
            service_date_start=item.service_date_start,
            service_date_end=item.service_date_end,
            group_size=item.group_size,
            notes=item.notes,
            pricing_locked=None,
        )
        db.add(req)
        db.flush()  # Flush to get req.id

        created_requests.append((req, vendor))

    # Commit all created requests first so workers see the persisted rows
    db.commit()

    for req, vendor in created_requests:
        route_and_dispatch_request(db, req, vendor)

    db.expire_all()
    final_requests = [req for req, _ in created_requests]
    for req in final_requests:
        db.refresh(req)

    return final_requests, False
