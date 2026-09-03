import uuid
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from app.schemas.contracts import (
    ItineraryFulfillmentIntakeRequest,
    ItineraryItemIntake,
    FulfillmentItemStatusReport,
    OverallFulfillmentStatus,
    ItineraryFulfillmentStatusResponse,
)
from app.models.booking import FulfillmentStatus
from app.models.vendor import PartnershipStatus


def test_mock_itinerary_intake_payload_valid():
    """Validates that the upstream mock contract correctly parses a standard itinerary intake."""
    vendor_1 = str(uuid.uuid4())
    vendor_2 = str(uuid.uuid4())

    payload = {
        "itinerary_id": "itin_blr_goa_001",
        "customer_id": "cust_12345",
        "trip_title": "Bangalore to Goa 4-Day Roadtrip",
        "items": [
            {
                "vendor_id": vendor_1,
                "service_date_start": "2026-10-10T10:00:00Z",
                "service_date_end": "2026-10-10T12:00:00Z",
                "group_size": 4,
                "max_budget": "5000.00",
                "notes": "Prefer window seating or outdoor deck"
            },
            {
                "vendor_id": vendor_2,
                "service_date_start": "2026-10-11T14:00:00Z",
                "service_date_end": "2026-10-12T11:00:00Z",
                "group_size": 4,
                "max_budget": "12000.00",
                "notes": "King beds requested"
            }
        ]
    }

    parsed = ItineraryFulfillmentIntakeRequest.model_validate(payload)
    assert parsed.itinerary_id == "itin_blr_goa_001"
    assert len(parsed.items) == 2
    assert parsed.items[0].vendor_id == vendor_1
    assert parsed.items[0].group_size == 4
    assert parsed.items[0].max_budget == Decimal("5000.00")


def test_mock_status_response_serialization():
    """Validates the downstream status reporting contract schema."""
    vendor_id = str(uuid.uuid4())
    req_id = str(uuid.uuid4())

    report = FulfillmentItemStatusReport(
        request_id=req_id,
        vendor_id=vendor_id,
        vendor_name="Goa Beachside Resort",
        partnership_status=PartnershipStatus.PARTNERED,
        status=FulfillmentStatus.CONFIRMED,
        booking_channel="PROGRAMMATIC_API",
        pricing_locked=Decimal("4500.00"),
        external_reference_id="PARTNER-CONF-ABC1234",
        notes="Programmatic booking confirmed",
    )

    response = ItineraryFulfillmentStatusResponse(
        itinerary_id="itin_blr_goa_001",
        overall_fulfillment_status=OverallFulfillmentStatus.ALL_CONFIRMED,
        total_items=1,
        confirmed_items=1,
        pending_items=0,
        failed_or_alternate_items=0,
        items=[report],
        last_updated=datetime.now(timezone.utc),
    )

    data = response.model_dump()
    assert data["itinerary_id"] == "itin_blr_goa_001"
    assert data["overall_fulfillment_status"] == "ALL_CONFIRMED"
    assert data["confirmed_items"] == 1
    assert data["items"][0]["external_reference_id"] == "PARTNER-CONF-ABC1234"
