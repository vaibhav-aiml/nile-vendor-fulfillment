from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.vendor import VendorCategory, PartnershipStatus, VerificationStatus


class Coordinates(BaseModel):
    longitude: float = Field(..., ge=-180, le=180)
    latitude: float = Field(..., ge=-90, le=90)


class VendorBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    category: VendorCategory = VendorCategory.OTHER
    partnership_status: PartnershipStatus = PartnershipStatus.NON_PARTNERED
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address: Optional[str] = None
    coordinates: Optional[Coordinates] = None


class VendorCreate(VendorBase):
    pass


class VendorUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[VendorCategory] = None
    partnership_status: Optional[PartnershipStatus] = None
    verification_status: Optional[VerificationStatus] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address: Optional[str] = None
    coordinates: Optional[Coordinates] = None


class VendorContactResponse(BaseModel):
    """
    Dedicated view for Ops staff to quickly reach out to a vendor.
    """
    id: UUID
    name: str
    category: VendorCategory
    partnership_status: PartnershipStatus
    contact_name: Optional[str]
    contact_phone: Optional[str]
    contact_email: Optional[str]
    address: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class VendorResponse(VendorBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
