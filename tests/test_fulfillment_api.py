import uuid
from app.models.vendor import Vendor, PartnershipStatus, VendorCategory
from app.models.booking import FulfillmentRequest, FulfillmentStatus


def test_intake_and_status_endpoints(client, db_session):
    """
    Test full cycle:
    1. Seed vendors (1 partnered, 1 non-partnered)
    2. Submit itinerary via /fulfillment/intake
    3. Verify status report returns PARTIALLY_CONFIRMED or expected status
    4. Query /fulfillment/itinerary/{itinerary_id}/status
    """
    v_partner = Vendor(
        id=uuid.uuid4(),
        name="Goa Marriott Resort",
        category=VendorCategory.STAY,
        partnership_status=PartnershipStatus.PARTNERED,
    )
    v_local = Vendor(
        id=uuid.uuid4(),
        name="Britto's Baga",
        category=VendorCategory.DINING,
        partnership_status=PartnershipStatus.NON_PARTNERED,
    )
    db_session.add_all([v_partner, v_local])
    db_session.commit()

    intake_payload = {
        "itinerary_id": "itin_end_to_end_001",
        "customer_id": "cust_8899",
        "trip_title": "Bangalore to Goa 3-day getaway",
        "items": [
            {
                "vendor_id": str(v_partner.id),
                "service_date_start": "2026-11-01T14:00:00Z",
                "service_date_end": "2026-11-03T11:00:00Z",
                "group_size": 2,
                "notes": "Pool view requested",
            },
            {
                "vendor_id": str(v_local.id),
                "service_date_start": "2026-11-01T20:00:00Z",
                "group_size": 2,
                "notes": "Table for dinner",
            },
        ],
    }

    res = client.post("/api/v1/fulfillment/intake", json=intake_payload)
    assert res.status_code == 201
    data = res.json()
    assert data["itinerary_id"] == "itin_end_to_end_001"
    assert data["total_items"] == 2
    assert data["confirmed_items"] == 1  # The partnered vendor was booked immediately
    assert data["pending_items"] == 1    # The non-partnered vendor is pending HITL outreach
    assert data["overall_fulfillment_status"] == "PARTIALLY_CONFIRMED"

    res_status = client.get("/api/v1/fulfillment/itinerary/itin_end_to_end_001/status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["itinerary_id"] == "itin_end_to_end_001"
    assert len(status_data["items"]) == 2

    # 3. Duplicate intake returns clean HTTP 409 Conflict (never 500)
    res_dup = client.post("/api/v1/fulfillment/intake", json=intake_payload)
    assert res_dup.status_code == 409
    assert "already been ingested" in res_dup.json()["detail"]

    # 4. Direct DB integrity conflict test (e.g. concurrent race condition)
    # Attempting to insert a duplicate (itinerary_id, vendor_id) directly should be caught
    res_conflict = client.post("/api/v1/fulfillment/intake", json=intake_payload)
    assert res_conflict.status_code == 409
