import uuid
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.security import verify_ops_token
from app.models.booking import FulfillmentRequest, FulfillmentStatus, BookingChannel
from app.models.vendor import Vendor
from app.schemas.booking import (
    OpsStatusUpdateRequest,
    FulfillmentRequestResponse,
    FulfillmentRequestListResponse,
)
from app.schemas.vendor import VendorContactResponse
from app.services.event_publisher import event_publisher

router = APIRouter(
    prefix="/api/v1/ops",
    tags=["Ops Dashboard"],
    dependencies=[Depends(verify_ops_token)],
)


@router.get("/requests", response_model=FulfillmentRequestListResponse)
def list_fulfillment_requests(
    status_filter: Optional[FulfillmentStatus] = Query(None, alias="status", description="Filter by booking status"),
    vendor_id: Optional[uuid.UUID] = Query(None, description="Filter by specific vendor ID"),
    itinerary_id: Optional[str] = Query(None, description="Filter by itinerary ID"),
    sla_breached: Optional[bool] = Query(None, description="Filter for requests that have breached SLA"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
):
    """
    List fulfillment requests with filtering options for Ops staff.
    """
    query = db.query(FulfillmentRequest)

    if status_filter:
        query = query.filter(FulfillmentRequest.status == status_filter)

    if vendor_id:
        query = query.filter(FulfillmentRequest.vendor_id == vendor_id)

    if itinerary_id:
        query = query.filter(FulfillmentRequest.itinerary_id == itinerary_id)

    if sla_breached is True:
        now_utc = datetime.now(timezone.utc)
        query = query.filter(
            FulfillmentRequest.sla_deadline.isnot(None),
            FulfillmentRequest.sla_deadline < now_utc,
            FulfillmentRequest.status.in_([FulfillmentStatus.PENDING, FulfillmentStatus.OUTREACH_IN_PROGRESS]),
        )

    total = query.count()
    items = (
        query.order_by(FulfillmentRequest.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    return FulfillmentRequestListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
    )


@router.get("/requests/{request_id}", response_model=FulfillmentRequestResponse)
def get_fulfillment_request(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Retrieve single fulfillment request details.
    """
    req = db.query(FulfillmentRequest).filter(FulfillmentRequest.id == request_id).first()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fulfillment request '{request_id}' not found.",
        )
    return req


@router.patch("/requests/{request_id}/status", response_model=FulfillmentRequestResponse)
def update_fulfillment_status(
    request_id: uuid.UUID,
    update_data: OpsStatusUpdateRequest,
    db: Session = Depends(get_db),
):
    """
    HITL Ops Staff endpoint: manually update booking status (e.g. Outreach In Progress, Confirmed, Rejected, Alternate Needed).
    Also locks pricing, records agent identity, and appends outreach notes.
    """
    req = db.query(FulfillmentRequest).filter(FulfillmentRequest.id == request_id).first()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fulfillment request '{request_id}' not found.",
        )

    prev_status = req.status
    req.status = update_data.status

    if update_data.pricing_locked is not None:
        req.pricing_locked = update_data.pricing_locked

    if update_data.assigned_ops_agent:
        req.assigned_ops_agent = update_data.assigned_ops_agent

    if update_data.external_reference_id:
        req.external_reference_id = update_data.external_reference_id

    if update_data.notes:
        timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        note_entry = f"[{timestamp_str} - {update_data.assigned_ops_agent or 'Ops'}]: {update_data.notes}"
        req.notes = f"{req.notes}\n{note_entry}" if req.notes else note_entry

    db.commit()
    db.refresh(req)

    if req.status == FulfillmentStatus.CONFIRMED:
        event_type = "BOOKING_CONFIRMED"
    elif req.status == FulfillmentStatus.REJECTED:
        event_type = "BOOKING_REJECTED"
    elif req.status == FulfillmentStatus.ALTERNATE_NEEDED:
        event_type = "ALTERNATE_NEEDED"

    event_publisher.publish_event(
        event_type=event_type,
        payload={
            "request_id": str(req.id),
            "itinerary_id": req.itinerary_id,
            "vendor_id": str(req.vendor_id),
            "previous_status": prev_status.value if hasattr(prev_status, "value") else str(prev_status),
            "new_status": req.status.value if hasattr(req.status, "value") else str(req.status),
            "pricing_locked": float(req.pricing_locked) if req.pricing_locked else None,
            "assigned_ops_agent": req.assigned_ops_agent,
            "external_reference_id": req.external_reference_id,
        },
    )

    return req


@router.get("/vendors/{vendor_id}/contact", response_model=VendorContactResponse)
def get_vendor_contact(
    vendor_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Dedicated view for Ops staff to view vendor contact information for manual outreach.
    """
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor '{vendor_id}' not found.",
        )
    return vendor
