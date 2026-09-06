import uuid
from datetime import datetime, date, timezone, timedelta, time as dt_time
from app.models.vendor import Vendor, PartnershipStatus, VendorCategory
from app.models.booking import FulfillmentRequest, FulfillmentStatus, BookingChannel
from app.schemas.contracts import ItineraryFulfillmentIntakeRequest
from app.services.routing import process_itinerary_intake
from app.core.config import settings


def _make_intake(itinerary_id, hotel_vendor_id, activity_vendors, group_size=2):
    """
    Build a valid ItineraryFulfillmentIntakeRequest from vendor objects.

    activity_vendors: list of tuples (vendor, day_number, date, start_time, end_time, name)
    """
    days_map = {}
    for vendor, day_num, day_date, start_t, end_t, name in activity_vendors:
        if day_num not in days_map:
            days_map[day_num] = {"day": day_num, "date": day_date.isoformat(), "activities": []}
        days_map[day_num]["activities"].append({
            "activity_id": str(vendor.id),
            "name": name,
            "start_time": start_t,
            "end_time": end_t,
            "estimated_cost": 1000.0,
        })

    return ItineraryFulfillmentIntakeRequest.model_validate({
        "itinerary_id": itinerary_id,
        "customer_id": "cust_test",
        "group_size": group_size,
        "itinerary": {
            "destination": "Goa",
            "start_date": "2026-10-10",
            "end_date": "2026-10-12",
            "hotel": {
                "hotel_id": str(hotel_vendor_id),
                "name": "Test Hotel",
            },
            "days": [days_map[k] for k in sorted(days_map.keys())],
            "estimated_total_cost": 10000.0,
        },
    })


def test_routing_partnered_vendor(db_session):
    """
    Verify that a partnered vendor (hotel) is routed to PROGRAMMATIC_API
    and the programmatic booking adapter confirms the booking.
    """
    hotel = Vendor(
        id=uuid.uuid4(),
        name="Taj Holiday Village Resort & Spa, Goa",
        category=VendorCategory.STAY,
        partnership_status=PartnershipStatus.PARTNERED,
    )
    activity_vendor = Vendor(
        id=uuid.uuid4(),
        name="Goa Scuba Adventures",
        category=VendorCategory.ACTIVITY,
        partnership_status=PartnershipStatus.PARTNERED,
    )
    db_session.add_all([hotel, activity_vendor])
    db_session.commit()

    intake = _make_intake(
        "itin_partnered_001",
        hotel.id,
        [(activity_vendor, 1, date(2026, 10, 10), "09:00", "12:00", "Scuba Diving")],
    )

    requests, is_duplicate = process_itinerary_intake(db_session, intake)
    assert is_duplicate is False
    assert len(requests) == 2  # 1 hotel + 1 activity

    hotel_req = [r for r in requests if r.vendor_id == hotel.id][0]
    assert hotel_req.booking_channel == BookingChannel.PROGRAMMATIC_API
    assert hotel_req.status == FulfillmentStatus.CONFIRMED
    assert hotel_req.external_reference_id is not None
    assert "PARTNER-CONF-" in hotel_req.external_reference_id


def test_routing_non_partnered_vendor(db_session):
    """
    Verify that a non-partnered vendor is routed to HITL_MANUAL,
    marked PENDING, and assigned an SLA deadline.
    """
    hotel = Vendor(
        id=uuid.uuid4(),
        name="Budget Guesthouse Anjuna",
        category=VendorCategory.STAY,
        partnership_status=PartnershipStatus.NON_PARTNERED,
        contact_phone="+91-9876543210",
    )
    activity_vendor = Vendor(
        id=uuid.uuid4(),
        name="Curlies Beach Shack, Anjuna",
        category=VendorCategory.DINING,
        partnership_status=PartnershipStatus.NON_PARTNERED,
    )
    db_session.add_all([hotel, activity_vendor])
    db_session.commit()

    intake = _make_intake(
        "itin_nonpartnered_002",
        hotel.id,
        [(activity_vendor, 1, date(2026, 10, 10), "19:00", "21:00", "Dinner")],
        group_size=6,
    )

    requests, is_duplicate = process_itinerary_intake(db_session, intake)
    assert is_duplicate is False
    assert len(requests) == 2

    hotel_req = [r for r in requests if r.vendor_id == hotel.id][0]
    assert hotel_req.booking_channel == BookingChannel.HITL_MANUAL
    assert hotel_req.status == FulfillmentStatus.PENDING
    assert hotel_req.sla_deadline is not None
    assert hotel_req.group_size == 6

    expected_sla = datetime.now(timezone.utc) + timedelta(hours=settings.OUTREACH_SLA_HOURS)
    deadline = hotel_req.sla_deadline if hotel_req.sla_deadline.tzinfo else hotel_req.sla_deadline.replace(tzinfo=timezone.utc)
    delta_seconds = abs((deadline - expected_sla).total_seconds())
    assert delta_seconds < 60


def test_idempotency_duplicate_intake(db_session):
    """
    Verify idempotency on intake: submitting the same itinerary_id again
    does not create duplicate FulfillmentRequest rows.
    """
    hotel = Vendor(
        id=uuid.uuid4(),
        name="Beach Hotel Goa",
        category=VendorCategory.STAY,
        partnership_status=PartnershipStatus.NON_PARTNERED,
    )
    activity_vendor = Vendor(
        id=uuid.uuid4(),
        name="Goa Scuba Adventures",
        category=VendorCategory.ACTIVITY,
        partnership_status=PartnershipStatus.NON_PARTNERED,
    )
    db_session.add_all([hotel, activity_vendor])
    db_session.commit()

    intake = _make_intake(
        "itin_idempotency_test",
        hotel.id,
        [(activity_vendor, 1, date(2026, 10, 10), "10:00", "12:00", "Scuba")],
    )

    reqs_1, is_dup_1 = process_itinerary_intake(db_session, intake)
    assert is_dup_1 is False
    assert len(reqs_1) == 2
    first_ids = {r.id for r in reqs_1}

    reqs_2, is_dup_2 = process_itinerary_intake(db_session, intake)
    assert is_dup_2 is True
    assert len(reqs_2) == 2
    assert {r.id for r in reqs_2} == first_ids

    total_in_db = db_session.query(FulfillmentRequest).filter(
        FulfillmentRequest.itinerary_id == "itin_idempotency_test"
    ).count()
    assert total_in_db == 2


def test_routing_flattens_hotel_plus_multiday_activities(db_session):
    """
    Critical multi-day test: 1 hotel + 3 activities across 2 days = 4 FulfillmentRequest rows.
    Verifies correct flattening and that each activity gets the right day's date.
    """
    hotel = Vendor(
        id=uuid.uuid4(),
        name="Taj Holiday Village Resort",
        category=VendorCategory.STAY,
        partnership_status=PartnershipStatus.PARTNERED,
    )
    scuba_vendor = Vendor(
        id=uuid.uuid4(),
        name="Grande Island Scuba",
        category=VendorCategory.ACTIVITY,
        partnership_status=PartnershipStatus.PARTNERED,
    )
    trek_vendor = Vendor(
        id=uuid.uuid4(),
        name="Dudhsagar Trekking Co.",
        category=VendorCategory.ACTIVITY,
        partnership_status=PartnershipStatus.NON_PARTNERED,
    )
    spice_vendor = Vendor(
        id=uuid.uuid4(),
        name="Sahakari Spice Farm",
        category=VendorCategory.ACTIVITY,
        partnership_status=PartnershipStatus.NON_PARTNERED,
    )
    db_session.add_all([hotel, scuba_vendor, trek_vendor, spice_vendor])
    db_session.commit()

    day1_date = date(2026, 10, 10)
    day2_date = date(2026, 10, 11)

    intake = _make_intake(
        "itin_multiday_001",
        hotel.id,
        [
            (scuba_vendor, 1, day1_date, "09:00", "12:00", "Scuba Diving"),
            (trek_vendor, 2, day2_date, "06:00", "14:00", "Dudhsagar Trek"),
            (spice_vendor, 2, day2_date, "16:00", "18:00", "Spice Plantation Tour"),
        ],
    )

    requests, is_duplicate = process_itinerary_intake(db_session, intake)
    assert is_duplicate is False
    assert len(requests) == 4  # 1 hotel + 3 activities

    # Hotel request uses trip-level dates
    # Note: SQLite strips timezone info, so compare naive datetimes
    hotel_req = [r for r in requests if r.vendor_id == hotel.id][0]
    assert hotel_req.service_date_start.replace(tzinfo=None) == datetime(2026, 10, 10, 0, 0)
    assert hotel_req.service_date_end.replace(tzinfo=None) == datetime(2026, 10, 12, 0, 0)

    # Scuba (day 1) gets day1_date + 09:00-12:00
    scuba_req = [r for r in requests if r.vendor_id == scuba_vendor.id][0]
    assert scuba_req.service_date_start.replace(tzinfo=None) == datetime(2026, 10, 10, 9, 0)
    assert scuba_req.service_date_end.replace(tzinfo=None) == datetime(2026, 10, 10, 12, 0)

    # Trek (day 2) gets day2_date + 06:00-14:00
    trek_req = [r for r in requests if r.vendor_id == trek_vendor.id][0]
    assert trek_req.service_date_start.replace(tzinfo=None) == datetime(2026, 10, 11, 6, 0)
    assert trek_req.service_date_end.replace(tzinfo=None) == datetime(2026, 10, 11, 14, 0)

    # Spice (day 2) gets day2_date + 16:00-18:00
    spice_req = [r for r in requests if r.vendor_id == spice_vendor.id][0]
    assert spice_req.service_date_start.replace(tzinfo=None) == datetime(2026, 10, 11, 16, 0)
    assert spice_req.service_date_end.replace(tzinfo=None) == datetime(2026, 10, 11, 18, 0)

    # All requests should inherit group_size from the envelope
    for req in requests:
        assert req.group_size == 2
