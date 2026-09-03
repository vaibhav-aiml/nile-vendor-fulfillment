from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.booking import FulfillmentRequest
from app.schemas.contracts import (
    ItineraryFulfillmentIntakeRequest,
    ItineraryFulfillmentStatusResponse,
)
from app.services.routing import process_itinerary_intake
from app.services.status_aggregator import build_itinerary_status_response

router = APIRouter(
    prefix="/api/v1/fulfillment",
    tags=["Fulfillment Lifecycle (Upstream/Downstream)"],
)


@router.post(
    "/intake",
    response_model=ItineraryFulfillmentStatusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Receive finalized itinerary for fulfillment",
)
def intake_itinerary(
    payload: ItineraryFulfillmentIntakeRequest,
    db: Session = Depends(get_db),
):
    """
    # MOCK CONTRACT ENDPOINT — pending confirmation from Yashaswini/Aman

    Receives a finalized itinerary payload, validates vendors, routes each item
    (programmatic booking for Partnered vs Celery HITL queue for Non-Partnered),
    and enforces idempotency on `itinerary_id`.
    """
    try:
        requests, is_duplicate = process_itinerary_intake(db, payload)
        if is_duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Conflict: Fulfillment requests for itinerary '{payload.itinerary_id}' "
                    f"have already been ingested. Use GET /api/v1/fulfillment/itinerary/"
                    f"{payload.itinerary_id}/status to check progress."
                ),
            )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        # Catch any database integrity error (e.g. race condition on unique constraint)
        if "IntegrityError" in type(e).__name__ or "UNIQUE constraint" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflict: Duplicate booking detected for itinerary '{payload.itinerary_id}'."
            )
        raise e
    
    response = build_itinerary_status_response(payload.itinerary_id, requests)
    return response


@router.get(
    "/itinerary/{itinerary_id}/status",
    response_model=ItineraryFulfillmentStatusResponse,
    summary="Report fulfillment status back upstream",
)
def get_itinerary_fulfillment_status(
    itinerary_id: str,
    db: Session = Depends(get_db),
):
    """
    # MOCK CONTRACT ENDPOINT — pending confirmation

    Aggregates all vendor booking states for a given itinerary and returns the
    overall status (ALL_CONFIRMED, PARTIALLY_CONFIRMED, BLOCKED_ALTERNATE_NEEDED, IN_PROGRESS).
    """
    requests = (
        db.query(FulfillmentRequest)
        .filter(FulfillmentRequest.itinerary_id == itinerary_id)
        .all()
    )

    if not requests:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No fulfillment requests found for itinerary '{itinerary_id}'.",
        )

    return build_itinerary_status_response(itinerary_id, requests)
