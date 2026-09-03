import uuid
from datetime import datetime, timezone, timedelta
from app.models.vendor import Vendor, PartnershipStatus, VendorCategory
from app.models.booking import FulfillmentRequest, FulfillmentStatus, BookingChannel
from app.schemas.contracts import ItineraryFulfillmentIntakeRequest, ItineraryItemIntake
from app.services.routing import process_itinerary_intake
from app.core.config import settings


def test_routing_partnered_vendor(db_session):
    """
    Verify that a partnered vendor is routed to PROGRAMMATIC_API
    and the programmatic booking adapter confirms the booking.
    """
    partner_vendor = Vendor(
        id=uuid.uuid4(),
        name="Taj Holiday Village Resort & Spa, Goa",
        category=VendorCategory.STAY,
        partnership_status=PartnershipStatus.PARTNERED,
    )
    db_session.add(partner_vendor)
    db_session.commit()

    intake = ItineraryFulfillmentIntakeRequest(
        itinerary_id="itin_partnered_001",
        items=[
            ItineraryItemIntake(
                vendor_id=str(partner_vendor.id),
                group_size=2,
                notes="Deluxe Sea View Cottage",
            )
        ],
    )

    requests, is_duplicate = process_itinerary_intake(db_session, intake)
    assert is_duplicate is False
    assert len(requests) == 1

    req = requests[0]
    assert req.booking_channel == BookingChannel.PROGRAMMATIC_API
    assert req.status == FulfillmentStatus.CONFIRMED
    assert req.external_reference_id is not None
    assert "PARTNER-CONF-" in req.external_reference_id


def test_routing_non_partnered_vendor(db_session):
    """
    Verify that a non-partnered vendor is routed to HITL_MANUAL,
    marked PENDING, and assigned an SLA deadline.
    """
    local_shack = Vendor(
        id=uuid.uuid4(),
        name="Curlies Beach Shack, Anjuna",
        category=VendorCategory.DINING,
        partnership_status=PartnershipStatus.NON_PARTNERED,
        contact_phone="+91-9876543210",
    )
    db_session.add(local_shack)
    db_session.commit()

    intake = ItineraryFulfillmentIntakeRequest(
        itinerary_id="itin_nonpartnered_002",
        items=[
            ItineraryItemIntake(
                vendor_id=str(local_shack.id),
                group_size=6,
                notes="Sunset table reservation",
            )
        ],
    )

    requests, is_duplicate = process_itinerary_intake(db_session, intake)
    assert is_duplicate is False
    assert len(requests) == 1

    req = requests[0]
    assert req.booking_channel == BookingChannel.HITL_MANUAL
    assert req.status == FulfillmentStatus.PENDING
    assert req.sla_deadline is not None

    # Check that sla_deadline is approximately now + OUTREACH_SLA_HOURS
    expected_sla = datetime.now(timezone.utc) + timedelta(hours=settings.OUTREACH_SLA_HOURS)
    deadline = req.sla_deadline if req.sla_deadline.tzinfo else req.sla_deadline.replace(tzinfo=timezone.utc)
    delta_seconds = abs((deadline - expected_sla).total_seconds())
    assert delta_seconds < 60  # within 1 minute


def test_idempotency_duplicate_intake(db_session):
    """
    Verify idempotency on intake: submitting the same itinerary_id again
    does not create duplicate FulfillmentRequest rows.
    """
    vendor = Vendor(
        id=uuid.uuid4(),
        name="Goa Scuba Adventures",
        category=VendorCategory.ACTIVITY,
        partnership_status=PartnershipStatus.NON_PARTNERED,
    )
    db_session.add(vendor)
    db_session.commit()

    intake = ItineraryFulfillmentIntakeRequest(
        itinerary_id="itin_idempotency_test",
        items=[
            ItineraryItemIntake(
                vendor_id=str(vendor.id),
                group_size=2,
            )
        ],
    )

    reqs_1, is_dup_1 = process_itinerary_intake(db_session, intake)
    assert is_dup_1 is False
    assert len(reqs_1) == 1
    first_req_id = reqs_1[0].id

    reqs_2, is_dup_2 = process_itinerary_intake(db_session, intake)
    assert is_dup_2 is True
    assert len(reqs_2) == 1
    assert reqs_2[0].id == first_req_id

    # Total rows in DB should strictly remain 1
    total_in_db = db_session.query(FulfillmentRequest).filter(FulfillmentRequest.itinerary_id == "itin_idempotency_test").count()
    assert total_in_db == 1
