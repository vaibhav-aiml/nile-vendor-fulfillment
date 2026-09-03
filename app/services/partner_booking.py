import uuid
from abc import ABC, abstractmethod
from typing import Optional
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel


class PartnerBookingResult(BaseModel):
    success: bool
    external_reference_id: Optional[str] = None
    pricing_locked: Optional[Decimal] = None
    error_message: Optional[str] = None


class PartnerBookingAdapter(ABC):
    """
    Clean abstract interface for programmatic vendor booking integrations.
    Individual partner APIs (e.g., hotel channel managers, tour booking APIs)
    will implement this interface once vendor partner specs are confirmed.
    """

    @abstractmethod
    async def check_availability(
        self,
        vendor_id: str,
        service_date_start: Optional[datetime],
        service_date_end: Optional[datetime],
        group_size: int
    ) -> bool:
        """Query partner API for real-time slot/room availability."""
        pass

    @abstractmethod
    async def book(
        self,
        request_id: str,
        vendor_id: str,
        service_date_start: Optional[datetime],
        service_date_end: Optional[datetime],
        group_size: int,
        max_budget: Optional[Decimal] = None
    ) -> PartnerBookingResult:
        """Execute programmatic booking with partner API."""
        pass

    @abstractmethod
    async def cancel(self, external_reference_id: str) -> bool:
        """Cancel an existing programmatic booking."""
        pass


class StubPartnerBookingAdapter(PartnerBookingAdapter):
    """
    Stub implementation for partnered vendors prior to live API credentials.
    Simulates a successful programmatic booking response.
    """

    async def check_availability(
        self,
        vendor_id: str,
        service_date_start: Optional[datetime],
        service_date_end: Optional[datetime],
        group_size: int
    ) -> bool:
        # Simulated partner availability check
        return True

    async def book(
        self,
        request_id: str,
        vendor_id: str,
        service_date_start: Optional[datetime],
        service_date_end: Optional[datetime],
        group_size: int,
        max_budget: Optional[Decimal] = None
    ) -> PartnerBookingResult:
        # Simulated instantaneous partner API booking confirmation
        ref_id = f"PARTNER-CONF-{uuid.uuid4().hex[:8].upper()}"
        return PartnerBookingResult(
            success=True,
            external_reference_id=ref_id,
            pricing_locked=max_budget or Decimal("2500.00"),
            error_message=None,
        )

    async def cancel(self, external_reference_id: str) -> bool:
        return True


def get_partner_adapter(vendor_category: Optional[str] = None) -> PartnerBookingAdapter:
    """
    Factory method to retrieve the appropriate partner API adapter.
    Defaults to the stub adapter for Phase 1.
    """
    return StubPartnerBookingAdapter()
