import uuid
from app.models.vendor import Vendor, PartnershipStatus, VendorCategory
from app.models.booking import FulfillmentRequest, FulfillmentStatus


def test_intake_and_status_endpoints(client, db_session):
    """
    Test full cycle with nested itinerary schema:
    1. Seed vendors (1 partnered hotel, 1 non-partnered activity)
    2. Submit nested itinerary via /fulfillment/intake
    3. Verify flattening: 1 hotel row + 1 activity row = 2 total items
    4. Verify status report returns PARTIALLY_CONFIRMED
    5. Query /fulfillment/itinerary/{itinerary_id}/status
    6. Duplicate intake returns 409 Conflict
    """
    v_hotel = Vendor(
        id=uuid.uuid4(),
        name="Goa Marriott Resort",
        category=VendorCategory.STAY,
        partnership_status=PartnershipStatus.PARTNERED,
    )
    v_activity = Vendor(
        id=uuid.uuid4(),
        name="Britto's Baga Watersports",
        category=VendorCategory.ACTIVITY,
        partnership_status=PartnershipStatus.NON_PARTNERED,
    )
    db_session.add_all([v_hotel, v_activity])
    db_session.commit()

    intake_payload = {
        "itinerary_id": "itin_end_to_end_001",
        "customer_id": "cust_8899",
        "group_size": 2,
        "itinerary": {
            "destination": "Goa",
            "start_date": "2026-11-01",
            "end_date": "2026-11-03",
            "hotel": {
                "hotel_id": str(v_hotel.id),
                "name": "Goa Marriott Resort",
            },
            "days": [
                {
                    "day": 1,
                    "date": "2026-11-01",
                    "activities": [
                        {
                            "activity_id": str(v_activity.id),
                            "name": "Jet Skiing at Baga Beach",
                            "start_time": "10:00",
                            "end_time": "12:00",
                            "estimated_cost": 2500.00,
                        }
                    ],
                }
            ],
            "estimated_total_cost": 15000.00,
        },
    }

    res = client.post("/api/v1/fulfillment/intake", json=intake_payload)
    assert res.status_code == 201
    data = res.json()
    assert data["itinerary_id"] == "itin_end_to_end_001"
    assert data["total_items"] == 2  # 1 hotel + 1 activity
    assert data["confirmed_items"] == 1  # The partnered hotel was booked immediately
    assert data["pending_items"] == 1    # The non-partnered activity is pending HITL outreach
    assert data["overall_fulfillment_status"] == "PARTIALLY_CONFIRMED"

    res_status = client.get("/api/v1/fulfillment/itinerary/itin_end_to_end_001/status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["itinerary_id"] == "itin_end_to_end_001"
    assert len(status_data["items"]) == 2

    # Duplicate intake returns clean HTTP 409 Conflict (never 500)
    res_dup = client.post("/api/v1/fulfillment/intake", json=intake_payload)
    assert res_dup.status_code == 409
    assert "already been ingested" in res_dup.json()["detail"]

    # Direct duplicate test
    res_conflict = client.post("/api/v1/fulfillment/intake", json=intake_payload)
    assert res_conflict.status_code == 409
