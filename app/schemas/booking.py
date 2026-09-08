from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, computed_field
from app.models.booking import FulfillmentStatus, BookingChannel
from app.schemas.vendor import VendorResponse


class FulfillmentRequestBase(BaseModel):
    itinerary_id: str
    vendor_id: UUID
    service_date_start: Optional[datetime] = None
    service_date_end: Optional[datetime] = None
    group_size: int = Field(1, ge=1)
    notes: Optional[str] = None


class FulfillmentRequestCreate(FulfillmentRequestBase):
    pass


class OpsStatusUpdateRequest(BaseModel):
    """
    Schema for internal ops staff to update request status, lock pricing, assign agent, and add notes.
    """
    status: FulfillmentStatus
    pricing_locked: Optional[Decimal] = None
    assigned_ops_agent: Optional[str] = None
    notes: Optional[str] = None
    external_reference_id: Optional[str] = None


class FulfillmentRequestResponse(FulfillmentRequestBase):
    id: UUID
    status: FulfillmentStatus
    booking_channel: BookingChannel
    pricing_locked: Optional[Decimal] = None
    assigned_ops_agent: Optional[str] = None
    sla_deadline: Optional[datetime] = None
    external_reference_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    vendor: Optional[VendorResponse] = None

    @computed_field
    def is_sla_breached(self) -> bool:
        """
        True if the request is still pending or in progress and current time has passed sla_deadline.
        """
        if self.sla_deadline and self.status in (
            FulfillmentStatus.PENDING,
            FulfillmentStatus.VENDOR_CONTACTED,
        ):
            now = datetime.now(timezone.utc)
            deadline = self.sla_deadline if self.sla_deadline.tzinfo else self.sla_deadline.replace(tzinfo=timezone.utc)
            return now > deadline
        return False

    model_config = ConfigDict(from_attributes=True)


class FulfillmentRequestListResponse(BaseModel):
    items: List[FulfillmentRequestResponse]
    total: int
    page: int
    size: int
