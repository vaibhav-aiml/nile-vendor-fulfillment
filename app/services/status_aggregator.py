from typing import Sequence
from datetime import datetime, timezone
from app.models.booking import FulfillmentRequest, FulfillmentStatus
from app.schemas.contracts import (
    OverallFulfillmentStatus,
    FulfillmentItemStatusReport,
    ItineraryFulfillmentStatusResponse,
)


def compute_overall_fulfillment_status(requests: Sequence[FulfillmentRequest]) -> str:
    """
    Evaluates all FulfillmentRequest rows for a given itinerary and determines
    the aggregate status for upstream consumption.

    Rules:
    1. If no requests exist: IN_PROGRESS
    2. If ANY item is REJECTED or ALTERNATE_NEEDED: BLOCKED_ALTERNATE_NEEDED (priority alert)
    3. If ALL items are CONFIRMED: ALL_CONFIRMED
    4. If ALL items are CANCELLED: CANCELLED
    5. If at least one item is CONFIRMED and others are in progress: PARTIALLY_CONFIRMED
    6. Default (all pending / outreach in progress): IN_PROGRESS
    """
    if not requests:
        return OverallFulfillmentStatus.IN_PROGRESS

    statuses = [req.status for req in requests]

    # Priority 1: Blocking conditions requiring upstream intervention / re-ranking
    if any(s in (FulfillmentStatus.REJECTED, FulfillmentStatus.ALTERNATE_NEEDED) for s in statuses):
        return OverallFulfillmentStatus.BLOCKED_ALTERNATE_NEEDED

    # Priority 2: Full success
    if all(s == FulfillmentStatus.CONFIRMED for s in statuses):
        return OverallFulfillmentStatus.ALL_CONFIRMED

    # Priority 3: Full cancellation
    if all(s == FulfillmentStatus.CANCELLED for s in statuses):
        return OverallFulfillmentStatus.CANCELLED

    # Priority 4: Partial progress
    if any(s == FulfillmentStatus.CONFIRMED for s in statuses):
        return OverallFulfillmentStatus.PARTIALLY_CONFIRMED

    # Priority 5: Initial / ongoing outreach
    return OverallFulfillmentStatus.IN_PROGRESS


def build_itinerary_status_response(
    itinerary_id: str,
    requests: Sequence[FulfillmentRequest]
) -> ItineraryFulfillmentStatusResponse:
    """
    Constructs the standardized upstream status payload for an itinerary.
    """
    overall_status = compute_overall_fulfillment_status(requests)

    total_items = len(requests)
    confirmed_items = sum(1 for r in requests if r.status == FulfillmentStatus.CONFIRMED)
    pending_items = sum(
        1 for r in requests if r.status in (FulfillmentStatus.PENDING, FulfillmentStatus.OUTREACH_IN_PROGRESS)
    )
    failed_or_alternate_items = sum(
        1 for r in requests if r.status in (FulfillmentStatus.REJECTED, FulfillmentStatus.ALTERNATE_NEEDED)
    )

    item_reports = []
    for r in requests:
        vendor_name = r.vendor.name if r.vendor else None
        partnership_status = r.vendor.partnership_status if r.vendor else None
        item_reports.append(
            FulfillmentItemStatusReport(
                request_id=str(r.id),
                vendor_id=str(r.vendor_id),
                vendor_name=vendor_name,
                partnership_status=partnership_status,
                status=r.status,
                booking_channel=r.booking_channel.value if hasattr(r.booking_channel, "value") else str(r.booking_channel),
                pricing_locked=r.pricing_locked,
                external_reference_id=r.external_reference_id,
                notes=r.notes,
                sla_deadline=r.sla_deadline,
            )
        )

    return ItineraryFulfillmentStatusResponse(
        itinerary_id=itinerary_id,
        overall_fulfillment_status=overall_status,
        total_items=total_items,
        confirmed_items=confirmed_items,
        pending_items=pending_items,
        failed_or_alternate_items=failed_or_alternate_items,
        items=item_reports,
        last_updated=datetime.now(timezone.utc),
    )
