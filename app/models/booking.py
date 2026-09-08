import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, Numeric, Text, Enum as SAEnum, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class FulfillmentStatus(str, enum.Enum):
    PENDING = "PENDING"
    VENDOR_CONTACTED = "VENDOR_CONTACTED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    NO_RESPONSE = "NO_RESPONSE"
    ALTERNATE_REQUIRED = "ALTERNATE_REQUIRED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class BookingChannel(str, enum.Enum):
    PROGRAMMATIC_API = "PROGRAMMATIC_API"
    HITL_MANUAL = "HITL_MANUAL"


class FulfillmentRequest(Base):
    __tablename__ = "fulfillment_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Mock Foreign Key from upstream itinerary
    itinerary_id = Column(String(100), nullable=False, index=True)
    
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True)

    # State Machine Status
    status = Column(
        SAEnum(FulfillmentStatus, name="fulfillment_status_enum"),
        nullable=False,
        default=FulfillmentStatus.PENDING,
        index=True
    )

    # Booking Channel determined by routing logic
    booking_channel = Column(
        SAEnum(BookingChannel, name="booking_channel_enum"),
        nullable=False,
        default=BookingChannel.HITL_MANUAL
    )

    # Trip / Fulfillment specifications
    service_date_start = Column(DateTime(timezone=True), nullable=True)
    service_date_end = Column(DateTime(timezone=True), nullable=True)
    group_size = Column(Integer, default=1, nullable=False)

    # HITL Operations & Audit fields
    pricing_locked = Column(Numeric(10, 2), nullable=True)
    assigned_ops_agent = Column(String(100), nullable=True, index=True)
    sla_deadline = Column(DateTime(timezone=True), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    external_reference_id = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    vendor = relationship("Vendor", back_populates="fulfillment_requests")

    # Idempotency constraint: avoid duplicate requests for the same itinerary + vendor
    __table_args__ = (
        UniqueConstraint("itinerary_id", "vendor_id", name="uq_itinerary_vendor"),
    )

    def __repr__(self) -> str:
        return f"<FulfillmentRequest id={self.id} itinerary={self.itinerary_id} status={self.status}>"
