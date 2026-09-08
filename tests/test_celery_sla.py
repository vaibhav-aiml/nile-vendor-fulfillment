import uuid
from datetime import datetime, timezone, timedelta
from app.models.booking import FulfillmentRequest, FulfillmentStatus, BookingChannel
from app.models.vendor import Vendor, PartnershipStatus, VendorCategory
from app.workers.tasks import check_outreach_sla_timeouts
from app.core.config import settings


def test_check_outreach_sla_timeouts_escalation(db_session):
    """
    Test that requests whose SLA deadline has passed are automatically
    escalated to ALTERNATE_REQUIRED by the periodic worker task.
    Explicitly enables SLA enforcement for this test.
    """
    original_flag = settings.SLA_ENFORCEMENT_ENABLED
    settings.SLA_ENFORCEMENT_ENABLED = True

    try:
        v = Vendor(
            id=uuid.uuid4(),
            name="Goa Watersports Center",
            category=VendorCategory.ACTIVITY,
            partnership_status=PartnershipStatus.NON_PARTNERED,
        )
        db_session.add(v)
        db_session.commit()

        now_utc = datetime.now(timezone.utc)

        # 1. Breached request (deadline was 2 hours ago)
        req_breached = FulfillmentRequest(
            id=uuid.uuid4(),
            itinerary_id="itin_sla_001",
            vendor_id=v.id,
            status=FulfillmentStatus.VENDOR_CONTACTED,
            booking_channel=BookingChannel.HITL_MANUAL,
            sla_deadline=now_utc - timedelta(hours=2),
        )

        # 2. Healthy request (deadline is in 10 hours)
        req_healthy = FulfillmentRequest(
            id=uuid.uuid4(),
            itinerary_id="itin_sla_002",
            vendor_id=v.id,
            status=FulfillmentStatus.PENDING,
            booking_channel=BookingChannel.HITL_MANUAL,
            sla_deadline=now_utc + timedelta(hours=10),
        )

        # 3. Already confirmed request (should never be escalated even if created long ago)
        req_confirmed = FulfillmentRequest(
            id=uuid.uuid4(),
            itinerary_id="itin_sla_003",
            vendor_id=v.id,
            status=FulfillmentStatus.CONFIRMED,
            booking_channel=BookingChannel.HITL_MANUAL,
            sla_deadline=now_utc - timedelta(hours=5),
        )

        db_session.add_all([req_breached, req_healthy, req_confirmed])
        db_session.commit()

        result = check_outreach_sla_timeouts()

        assert result["escalated_count"] == 1

        updated_breached = db_session.query(FulfillmentRequest).filter(FulfillmentRequest.id == req_breached.id).first()
        updated_healthy = db_session.query(FulfillmentRequest).filter(FulfillmentRequest.id == req_healthy.id).first()
        updated_confirmed = db_session.query(FulfillmentRequest).filter(FulfillmentRequest.id == req_confirmed.id).first()

        assert updated_breached.status == FulfillmentStatus.ALTERNATE_REQUIRED
        assert "[SYSTEM SLA ESCALATION]" in updated_breached.notes

        assert updated_healthy.status == FulfillmentStatus.PENDING
        assert updated_confirmed.status == FulfillmentStatus.CONFIRMED
    finally:
        settings.SLA_ENFORCEMENT_ENABLED = original_flag


def test_sla_task_noop_when_disabled(db_session):
    """
    Confirms the SLA timeout task is a no-op when SLA_ENFORCEMENT_ENABLED is False (the default).
    """
    original_flag = settings.SLA_ENFORCEMENT_ENABLED
    settings.SLA_ENFORCEMENT_ENABLED = False

    try:
        v = Vendor(
            id=uuid.uuid4(),
            name="Noop Test Vendor",
            category=VendorCategory.ACTIVITY,
            partnership_status=PartnershipStatus.NON_PARTNERED,
        )
        db_session.add(v)
        db_session.commit()

        now_utc = datetime.now(timezone.utc)
        req_breached = FulfillmentRequest(
            id=uuid.uuid4(),
            itinerary_id="itin_sla_noop",
            vendor_id=v.id,
            status=FulfillmentStatus.VENDOR_CONTACTED,
            booking_channel=BookingChannel.HITL_MANUAL,
            sla_deadline=now_utc - timedelta(hours=48),
        )
        db_session.add(req_breached)
        db_session.commit()

        result = check_outreach_sla_timeouts()

        assert result["skipped"] is True

        db_session.expire_all()
        unchanged = db_session.query(FulfillmentRequest).filter(FulfillmentRequest.id == req_breached.id).first()
        assert unchanged.status == FulfillmentStatus.VENDOR_CONTACTED
    finally:
        settings.SLA_ENFORCEMENT_ENABLED = original_flag
