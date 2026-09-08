import uuid
from decimal import Decimal
import pytest
from app.models.booking import FulfillmentRequest, FulfillmentStatus, BookingChannel
from app.models.vendor import Vendor, PartnershipStatus, VendorCategory
from app.schemas.contracts import OverallFulfillmentStatus
from app.services.status_aggregator import (
    compute_overall_fulfillment_status,
    build_itinerary_status_response,
)


def _mock_request(status: FulfillmentStatus, vendor_partnership: PartnershipStatus = PartnershipStatus.NON_PARTNERED):
    vendor = Vendor(
        id=uuid.uuid4(),
        name="Test Vendor",
        category=VendorCategory.ACTIVITY,
        partnership_status=vendor_partnership,
    )
    return FulfillmentRequest(
        id=uuid.uuid4(),
        itinerary_id="itin_123",
        vendor_id=vendor.id,
        vendor=vendor,
        status=status,
        booking_channel=BookingChannel.HITL_MANUAL,
        pricing_locked=Decimal("1500.00") if status == FulfillmentStatus.CONFIRMED else None,
    )


def test_status_empty():
    assert compute_overall_fulfillment_status([]) == OverallFulfillmentStatus.IN_PROGRESS


def test_status_all_confirmed():
    reqs = [
        _mock_request(FulfillmentStatus.CONFIRMED),
        _mock_request(FulfillmentStatus.CONFIRMED),
    ]
    assert compute_overall_fulfillment_status(reqs) == OverallFulfillmentStatus.ALL_CONFIRMED


def test_status_all_completed():
    """ALL_COMPLETED is only returned when every item is COMPLETED."""
    reqs = [
        _mock_request(FulfillmentStatus.COMPLETED),
        _mock_request(FulfillmentStatus.COMPLETED),
    ]
    assert compute_overall_fulfillment_status(reqs) == OverallFulfillmentStatus.ALL_COMPLETED


def test_status_mixed_confirmed_and_completed_is_not_all_confirmed():
    """
    Mixed CONFIRMED + COMPLETED must NOT report ALL_CONFIRMED.
    'Trip already happened' vs 'trip is booked and upcoming' are different signals.
    """
    reqs = [
        _mock_request(FulfillmentStatus.CONFIRMED),
        _mock_request(FulfillmentStatus.COMPLETED),
    ]
    result = compute_overall_fulfillment_status(reqs)
    assert result != OverallFulfillmentStatus.ALL_CONFIRMED
    assert result == OverallFulfillmentStatus.PARTIALLY_CONFIRMED


def test_status_partially_confirmed():
    reqs = [
        _mock_request(FulfillmentStatus.CONFIRMED),
        _mock_request(FulfillmentStatus.VENDOR_CONTACTED),
    ]
    assert compute_overall_fulfillment_status(reqs) == OverallFulfillmentStatus.PARTIALLY_CONFIRMED


def test_status_blocked_alternate_required():
    reqs = [
        _mock_request(FulfillmentStatus.CONFIRMED),
        _mock_request(FulfillmentStatus.REJECTED),
        _mock_request(FulfillmentStatus.VENDOR_CONTACTED),
    ]
    assert compute_overall_fulfillment_status(reqs) == OverallFulfillmentStatus.BLOCKED_ALTERNATE_REQUIRED

    reqs_alt = [
        _mock_request(FulfillmentStatus.CONFIRMED),
        _mock_request(FulfillmentStatus.ALTERNATE_REQUIRED),
    ]
    assert compute_overall_fulfillment_status(reqs_alt) == OverallFulfillmentStatus.BLOCKED_ALTERNATE_REQUIRED


def test_status_no_response_is_blocking():
    """NO_RESPONSE should trigger BLOCKED_ALTERNATE_REQUIRED just like REJECTED."""
    reqs = [
        _mock_request(FulfillmentStatus.CONFIRMED),
        _mock_request(FulfillmentStatus.NO_RESPONSE),
    ]
    assert compute_overall_fulfillment_status(reqs) == OverallFulfillmentStatus.BLOCKED_ALTERNATE_REQUIRED


def test_status_all_cancelled():
    reqs = [
        _mock_request(FulfillmentStatus.CANCELLED),
        _mock_request(FulfillmentStatus.CANCELLED),
    ]
    assert compute_overall_fulfillment_status(reqs) == OverallFulfillmentStatus.CANCELLED


def test_status_all_pending_or_in_progress():
    reqs = [
        _mock_request(FulfillmentStatus.PENDING),
        _mock_request(FulfillmentStatus.VENDOR_CONTACTED),
    ]
    assert compute_overall_fulfillment_status(reqs) == OverallFulfillmentStatus.IN_PROGRESS


def test_build_itinerary_status_response_counts():
    reqs = [
        _mock_request(FulfillmentStatus.CONFIRMED),
        _mock_request(FulfillmentStatus.VENDOR_CONTACTED),
        _mock_request(FulfillmentStatus.REJECTED),
    ]
    resp = build_itinerary_status_response("itin_123", reqs)

    assert resp.itinerary_id == "itin_123"
    assert resp.overall_fulfillment_status == OverallFulfillmentStatus.BLOCKED_ALTERNATE_REQUIRED
    assert resp.total_items == 3
    assert resp.confirmed_items == 1
    assert resp.pending_items == 1
    assert resp.failed_or_alternate_items == 1
    assert len(resp.items) == 3
