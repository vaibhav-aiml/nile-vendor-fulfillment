import uuid
from typing import List, Tuple
from datetime import datetime, timedelta, timezone, time as dt_time
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.vendor import Vendor, PartnershipStatus
from app.models.booking import FulfillmentRequest, FulfillmentStatus, BookingChannel
from app.schemas.contracts import ItineraryFulfillmentIntakeRequest


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


def _resolve_vendor(db: Session, vendor_id_str: str, label: str) -> Vendor:
    """
    Look up a Vendor by its string ID (expected to be a UUID).

    TBD — pending confirmation from Yashaswini: assumes hotel_id / activity_id
    from her schema map directly to our Vendor.id. If a translation step is
    needed, this is the single function to change.
    """
    try:
        vendor_uuid = uuid.UUID(vendor_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID format for {label}: '{vendor_id_str}'"
        )

    vendor = db.query(Vendor).filter(Vendor.id == vendor_uuid).first()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor with id '{vendor_id_str}' ({label}) not found. Discovery module sync may be required."
        )
    return vendor


def process_itinerary_intake(
    db: Session,
    intake: ItineraryFulfillmentIntakeRequest
) -> Tuple[List[FulfillmentRequest], bool]:
    """
    Idempotent processing of an incoming itinerary fulfillment request.

    Flattens Yashaswini's nested itinerary structure into FulfillmentRequest rows:
    - 1 row for the hotel (vendor_id = hotel_id)
    - 1 row per activity across all days (vendor_id = activity_id)

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
        return existing_requests, True

    itinerary = intake.itinerary
    created_requests: List[Tuple[FulfillmentRequest, Vendor]] = []

    # --- Hotel → 1 FulfillmentRequest ---
    # Hotel has no per-item date range, so fall back to trip-level start/end dates
    hotel_vendor = _resolve_vendor(db, itinerary.hotel.hotel_id, "hotel_id")
    hotel_req = FulfillmentRequest(
        itinerary_id=intake.itinerary_id,
        vendor_id=hotel_vendor.id,
        service_date_start=datetime.combine(itinerary.start_date, dt_time.min, tzinfo=timezone.utc),
        service_date_end=datetime.combine(itinerary.end_date, dt_time.min, tzinfo=timezone.utc),
        group_size=intake.group_size,
        notes=None,
        pricing_locked=None,
    )
    db.add(hotel_req)
    db.flush()
    created_requests.append((hotel_req, hotel_vendor))

    # --- Activities → 1 FulfillmentRequest per activity across all days ---
    for day_plan in itinerary.days:
        for activity in day_plan.activities:
            activity_vendor = _resolve_vendor(db, activity.activity_id, "activity_id")

            # Compose full datetime from DayPlan.date + activity's HH:MM times
            start_hour, start_minute = map(int, activity.start_time.split(":"))
            end_hour, end_minute = map(int, activity.end_time.split(":"))

            activity_req = FulfillmentRequest(
                itinerary_id=intake.itinerary_id,
                vendor_id=activity_vendor.id,
                service_date_start=datetime.combine(
                    day_plan.date,
                    dt_time(start_hour, start_minute),
                    tzinfo=timezone.utc,
                ),
                service_date_end=datetime.combine(
                    day_plan.date,
                    dt_time(end_hour, end_minute),
                    tzinfo=timezone.utc,
                ),
                group_size=intake.group_size,
                notes=None,
                pricing_locked=None,
            )
            db.add(activity_req)
            db.flush()
            created_requests.append((activity_req, activity_vendor))

    # Commit all created requests so workers see persisted rows
    db.commit()

    for req, vendor in created_requests:
        route_and_dispatch_request(db, req, vendor)

    db.expire_all()
    final_requests = [req for req, _ in created_requests]
    for req in final_requests:
        db.refresh(req)

    return final_requests, False
