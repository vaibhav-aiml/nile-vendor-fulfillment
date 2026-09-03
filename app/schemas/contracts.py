# ==============================================================================
# MOCK CONTRACTS — pending confirmation from Yashaswini/Aman (NILE Pipeline)
# ==============================================================================
# Upstream pipeline: Customer Intent -> Itinerary Planning -> Vendor Discovery
#                   -> Vendor Intelligence -> Vendor Partnership & Fulfillment
# ==============================================================================

from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from app.models.booking import FulfillmentStatus
from app.models.vendor import PartnershipStatus


class ItineraryItemIntake(BaseModel):
    """
    # MOCK — pending confirmation from Yashaswini/Aman
    Represents a single bookable item/activity/stay from the finalized itinerary.
    """
    vendor_id: str = Field(..., description="UUID of the selected vendor from Vendor Discovery")
    service_date_start: Optional[datetime] = Field(None, description="Start date/time of booking")
    service_date_end: Optional[datetime] = Field(None, description="End date/time of booking")
    group_size: int = Field(1, ge=1, description="Number of travelers")
    max_budget: Optional[Decimal] = Field(None, description="Max budget allocated from itinerary planner")
    notes: Optional[str] = Field(None, description="Specific customer requirements or preferences")


class ItineraryFulfillmentIntakeRequest(BaseModel):
    """
    # MOCK — pending confirmation from Yashaswini/Aman
    Payload received by this module when an itinerary is finalized and ready for fulfillment.
    """
    itinerary_id: str = Field(..., description="Unique itinerary identifier from Itinerary Planning stage")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    trip_title: Optional[str] = Field("Bangalore to Goa Route", description="Human-readable title")
    items: List[ItineraryItemIntake] = Field(..., min_length=1, description="List of vendor items to fulfill")


class FulfillmentItemStatusReport(BaseModel):
    """
    # MOCK — pending confirmation
    Individual booking status report sent back upstream to update customer itinerary.
    """
    request_id: str
    vendor_id: str
    vendor_name: Optional[str] = None
    partnership_status: PartnershipStatus
    status: FulfillmentStatus
    booking_channel: str
    pricing_locked: Optional[Decimal] = None
    external_reference_id: Optional[str] = None
    notes: Optional[str] = None
    sla_deadline: Optional[datetime] = None


class OverallFulfillmentStatus(str):
    """
    # MOCK — pending confirmation
    Aggregate status of the entire itinerary fulfillment.
    """
    ALL_CONFIRMED = "ALL_CONFIRMED"
    PARTIALLY_CONFIRMED = "PARTIALLY_CONFIRMED"
    BLOCKED_ALTERNATE_NEEDED = "BLOCKED_ALTERNATE_NEEDED"
    IN_PROGRESS = "IN_PROGRESS"
    CANCELLED = "CANCELLED"


class ItineraryFulfillmentStatusResponse(BaseModel):
    """
    # MOCK — pending confirmation
    Full status payload reported back upstream to Yashaswini (Itinerary Planning)
    and customer-facing applications.
    """
    itinerary_id: str
    overall_fulfillment_status: str
    total_items: int
    confirmed_items: int
    pending_items: int
    failed_or_alternate_items: int
    items: List[FulfillmentItemStatusReport]
    last_updated: datetime
