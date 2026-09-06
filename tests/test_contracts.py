import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
from pydantic import ValidationError
from app.schemas.contracts import (
    ItineraryFulfillmentIntakeRequest,
    ActivityPlanIntake,
    DayPlanIntake,
    HotelPlanIntake,
    ItineraryIntake,
    FulfillmentItemStatusReport,
    OverallFulfillmentStatus,
    ItineraryFulfillmentStatusResponse,
)
from app.models.booking import FulfillmentStatus
from app.models.vendor import PartnershipStatus


def _make_valid_intake_payload(hotel_id=None, activity_id=None):
    """Helper to build a valid nested intake payload dict."""
    return {
        "itinerary_id": "itin_blr_goa_001",
        "customer_id": "cust_12345",
        "group_size": 4,
        "itinerary": {
            "destination": "Goa",
            "start_date": "2026-10-10",
            "end_date": "2026-10-12",
            "hotel": {
                "hotel_id": hotel_id or str(uuid.uuid4()),
                "name": "Taj Holiday Village Resort",
            },
            "days": [
                {
                    "day": 1,
                    "date": "2026-10-10",
                    "activities": [
                        {
                            "activity_id": activity_id or str(uuid.uuid4()),
                            "name": "Scuba Diving at Grande Island",
                            "start_time": "09:00",
                            "end_time": "12:00",
                            "estimated_cost": 3500.00,
                        }
                    ],
                },
                {
                    "day": 2,
                    "date": "2026-10-11",
                    "activities": [
                        {
                            "activity_id": str(uuid.uuid4()),
                            "name": "Dudhsagar Falls Trek",
                            "start_time": "06:00",
                            "end_time": "14:00",
                            "estimated_cost": 2000.00,
                        },
                        {
                            "activity_id": str(uuid.uuid4()),
                            "name": "Spice Plantation Tour",
                            "start_time": "16:00",
                            "end_time": "18:00",
                            "estimated_cost": 800.00,
                        },
                    ],
                },
            ],
            "estimated_total_cost": 18000.00,
        },
    }


def test_itinerary_intake_payload_valid():
    """Validates that the nested intake contract correctly parses a real itinerary."""
    payload = _make_valid_intake_payload()
    parsed = ItineraryFulfillmentIntakeRequest.model_validate(payload)

    assert parsed.itinerary_id == "itin_blr_goa_001"
    assert parsed.customer_id == "cust_12345"
    assert parsed.group_size == 4
    assert parsed.itinerary.destination == "Goa"
    assert parsed.itinerary.hotel.name == "Taj Holiday Village Resort"
    assert len(parsed.itinerary.days) == 2
    assert len(parsed.itinerary.days[0].activities) == 1
    assert len(parsed.itinerary.days[1].activities) == 2
    assert parsed.itinerary.days[0].activities[0].start_time == "09:00"
    assert parsed.itinerary.estimated_total_cost == 18000.00


def test_intake_rejects_missing_hotel():
    """Hotel is required — omitting it must raise a validation error."""
    payload = _make_valid_intake_payload()
    del payload["itinerary"]["hotel"]
    with pytest.raises(ValidationError) as exc_info:
        ItineraryFulfillmentIntakeRequest.model_validate(payload)
    assert "hotel" in str(exc_info.value).lower()


def test_intake_rejects_missing_itinerary_id():
    """itinerary_id is required on the envelope — never optional or derived."""
    payload = _make_valid_intake_payload()
    del payload["itinerary_id"]
    with pytest.raises(ValidationError) as exc_info:
        ItineraryFulfillmentIntakeRequest.model_validate(payload)
    assert "itinerary_id" in str(exc_info.value).lower()


def test_intake_validates_time_format():
    """Activity times must be HH:MM (24h). Invalid formats must be rejected."""
    payload = _make_valid_intake_payload()
    payload["itinerary"]["days"][0]["activities"][0]["start_time"] = "25:00"
    with pytest.raises(ValidationError):
        ItineraryFulfillmentIntakeRequest.model_validate(payload)

    payload2 = _make_valid_intake_payload()
    payload2["itinerary"]["days"][0]["activities"][0]["end_time"] = "9:00"
    with pytest.raises(ValidationError):
        ItineraryFulfillmentIntakeRequest.model_validate(payload2)


def test_status_response_serialization():
    """Validates the downstream status reporting contract schema (unchanged)."""
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
