# ==============================================================================
# UPSTREAM INTAKE CONTRACT — mirrors Yashaswini's confirmed Itinerary schema
# ==============================================================================
# Source: https://github.com/yashashwanidixit/nile-recommendation/blob/main/schemas/itinerary.py
#
# Upstream pipeline: Customer Intent -> Itinerary Planning -> Vendor Discovery
#                    -> Vendor Intelligence -> Vendor Partnership & Fulfillment
# ==============================================================================

from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from app.models.booking import FulfillmentStatus
from app.models.vendor import PartnershipStatus


# ---------------------------------------------------------------------------
# Intake schemas — mirroring Yashaswini's Itinerary structure exactly
# ---------------------------------------------------------------------------

class ActivityPlanIntake(BaseModel):
    """Single bookable activity within a day, from Yashaswini's ActivityPlan."""
    # TBD — pending confirmation from Yashaswini: assumes activity_id maps
    # directly to our Vendor.id (UUID). If a translation/lookup step is needed,
    # the mapping logic in routing.py is the single point to change.
    activity_id: str
    name: str
    start_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):[0-5]\d$", description="HH:MM format")
    end_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):[0-5]\d$", description="HH:MM format")
    estimated_cost: float = Field(..., ge=0.0)


class DayPlanIntake(BaseModel):
    """A single day's plan containing its date and activities."""
    day: int = Field(..., ge=1)
    date: date
    activities: List[ActivityPlanIntake]


class HotelPlanIntake(BaseModel):
    """Single hotel for the entire trip, from Yashaswini's HotelPlan."""
    # TBD — pending confirmation from Yashaswini: assumes hotel_id maps
    # directly to our Vendor.id (UUID). If a translation/lookup step is needed,
    # the mapping logic in routing.py is the single point to change.
    hotel_id: str
    name: str


class ItineraryIntake(BaseModel):
    """
    Mirrors Yashaswini's Itinerary model exactly.
    One hotel for the whole trip, activities nested inside day plans.
    """
    # TODO: CTO has requested category, location, and user_preferences per item —
    # pending confirmation this will be added to Yashaswini's upstream Itinerary
    # schema before we can consume it here.
    destination: str
    start_date: date
    end_date: date
    hotel: HotelPlanIntake
    days: List[DayPlanIntake]
    estimated_total_cost: float = Field(..., ge=0.0)


class ItineraryFulfillmentIntakeRequest(BaseModel):
    """
    Envelope payload received when an itinerary is finalized and ready for fulfillment.

    itinerary_id is a required, independently-provided unique identifier — it is
    never derived from destination/dates or any other field combination.
    """
    itinerary_id: str = Field(..., description="Unique itinerary identifier, provided independently")
    # TBD — pending confirmation from Yashaswini: customer_id and group_size are
    # not present in her Itinerary schema. We assume they arrive as sibling fields
    # alongside the itinerary object in the actual API call. Once the real envelope
    # shape is confirmed, update these fields accordingly.
    customer_id: Optional[str] = Field(None, description="Customer identifier (TBD — source unconfirmed)")
    group_size: int = Field(1, ge=1, description="Number of travelers (TBD — source unconfirmed)")
    itinerary: ItineraryIntake = Field(..., description="Nested itinerary from Yashaswini's Itinerary schema")


# ---------------------------------------------------------------------------
# Downstream status response schemas — unchanged from original
# ---------------------------------------------------------------------------

class FulfillmentItemStatusReport(BaseModel):
    """Individual booking status report sent back upstream."""
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
    """Aggregate status of the entire itinerary fulfillment."""
    ALL_CONFIRMED = "ALL_CONFIRMED"
    ALL_COMPLETED = "ALL_COMPLETED"
    PARTIALLY_CONFIRMED = "PARTIALLY_CONFIRMED"
    BLOCKED_ALTERNATE_REQUIRED = "BLOCKED_ALTERNATE_REQUIRED"
    IN_PROGRESS = "IN_PROGRESS"
    CANCELLED = "CANCELLED"


class ItineraryFulfillmentStatusResponse(BaseModel):
    """
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
