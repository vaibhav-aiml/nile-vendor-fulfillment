import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from app.models.vendor import Vendor, PartnershipStatus, VendorCategory
from app.models.booking import FulfillmentRequest, FulfillmentStatus, BookingChannel
from app.core.config import settings


def test_ops_auth_unauthorized(client):
    """Endpoints under /ops require the X-Ops-Token header."""
    res = client.get("/api/v1/ops/requests")
    assert res.status_code == 401

    res_invalid = client.get("/api/v1/ops/requests", headers={"X-Ops-Token": "wrong-secret"})
    assert res_invalid.status_code == 401


def test_ops_list_and_filter_requests(client, db_session, ops_auth_headers):
    """Test listing and filtering requests in Ops Dashboard API."""
    v = Vendor(
        id=uuid.uuid4(),
        name="Dudhsagar Trekking Co.",
        category=VendorCategory.ACTIVITY,
        partnership_status=PartnershipStatus.NON_PARTNERED,
    )
    v2 = Vendor(
        id=uuid.uuid4(),
        name="Goa Spice Plantation",
        category=VendorCategory.ACTIVITY,
        partnership_status=PartnershipStatus.NON_PARTNERED,
    )
    db_session.add_all([v, v2])
    db_session.commit()

    r1 = FulfillmentRequest(
        id=uuid.uuid4(),
        itinerary_id="itin_filter_test",
        vendor_id=v.id,
        status=FulfillmentStatus.PENDING,
        booking_channel=BookingChannel.HITL_MANUAL,
    )
    r2 = FulfillmentRequest(
        id=uuid.uuid4(),
        itinerary_id="itin_filter_test",
        vendor_id=v2.id,
        status=FulfillmentStatus.CONFIRMED,
        booking_channel=BookingChannel.HITL_MANUAL,
    )
    db_session.add_all([r1, r2])
    db_session.commit()

    # List all
    res = client.get("/api/v1/ops/requests", headers=ops_auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2

    # Filter by status PENDING
    res_pending = client.get("/api/v1/ops/requests?status=PENDING", headers=ops_auth_headers)
    assert res_pending.status_code == 200
    assert res_pending.json()["total"] == 1
    assert res_pending.json()["items"][0]["status"] == "PENDING"


def test_ops_status_update(client, db_session, ops_auth_headers):
    """Ops staff updates status, locks price, assigns agent, and logs notes."""
    v = Vendor(
        id=uuid.uuid4(),
        name="Anjuna Kayak Club",
        category=VendorCategory.ACTIVITY,
        partnership_status=PartnershipStatus.NON_PARTNERED,
        contact_phone="+91-9999988888",
    )
    db_session.add(v)
    db_session.commit()

    req = FulfillmentRequest(
        id=uuid.uuid4(),
        itinerary_id="itin_ops_update",
        vendor_id=v.id,
        status=FulfillmentStatus.OUTREACH_IN_PROGRESS,
        booking_channel=BookingChannel.HITL_MANUAL,
    )
    db_session.add(req)
    db_session.commit()

    update_payload = {
        "status": "CONFIRMED",
        "pricing_locked": "3200.00",
        "assigned_ops_agent": "ops_vaibhav",
        "notes": "Spoke to manager Ramesh. Confirmed 4 double kayaks.",
        "external_reference_id": "VOUCH-7890",
    }

    res = client.patch(
        f"/api/v1/ops/requests/{req.id}/status",
        headers=ops_auth_headers,
        json=update_payload,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "CONFIRMED"
    assert data["pricing_locked"] == "3200.00"
    assert data["assigned_ops_agent"] == "ops_vaibhav"
    assert data["external_reference_id"] == "VOUCH-7890"
    assert "Spoke to manager Ramesh" in data["notes"]


def test_ops_get_vendor_contact(client, db_session, ops_auth_headers):
    """Ops staff views vendor contact details for manual outreach."""
    v = Vendor(
        id=uuid.uuid4(),
        name="Fontainhas Heritage Walk",
        category=VendorCategory.GUIDE,
        partnership_status=PartnershipStatus.NON_PARTNERED,
        contact_name="Mario Fernandes",
        contact_phone="+91-9822112233",
        contact_email="mario@panjimwalks.com",
        address="31st January Road, Altinho, Panaji, Goa",
    )
    db_session.add(v)
    db_session.commit()

    res = client.get(f"/api/v1/ops/vendors/{v.id}/contact", headers=ops_auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Fontainhas Heritage Walk"
    assert data["contact_name"] == "Mario Fernandes"
    assert data["contact_phone"] == "+91-9822112233"
    assert data["contact_email"] == "mario@panjimwalks.com"
