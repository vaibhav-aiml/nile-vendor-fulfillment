import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Enum as SAEnum, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from sqlalchemy.ext.compiler import compiles
from app.core.database import Base

# Ensure SQLite can compile Geometry as TEXT in test environments without SpatiaLite
@compiles(Geometry, "sqlite")
def compile_geom_sqlite(type_, compiler, **kw):
    return "TEXT"


class VendorCategory(str, enum.Enum):
    STAY = "STAY"
    ACTIVITY = "ACTIVITY"
    TRANSPORT = "TRANSPORT"
    DINING = "DINING"
    GUIDE = "GUIDE"
    OTHER = "OTHER"


class PartnershipStatus(str, enum.Enum):
    PARTNERED = "PARTNERED"
    NON_PARTNERED = "NON_PARTNERED"


class VerificationStatus(str, enum.Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    SUSPENDED = "SUSPENDED"


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    category = Column(SAEnum(VendorCategory, name="vendor_category_enum"), nullable=False, default=VendorCategory.OTHER)
    partnership_status = Column(SAEnum(PartnershipStatus, name="partnership_status_enum"), nullable=False, default=PartnershipStatus.NON_PARTNERED, index=True)
    verification_status = Column(SAEnum(VerificationStatus, name="verification_status_enum"), nullable=False, default=VerificationStatus.UNVERIFIED)

    contact_name = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    contact_email = Column(String(255), nullable=True)
    address = Column(String(500), nullable=True)

    # PostGIS Location (Longitude, Latitude) with SRID 4326 (WGS84)
    location = Column(Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    fulfillment_requests = relationship("FulfillmentRequest", back_populates="vendor", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Vendor id={self.id} name='{self.name}' partnership={self.partnership_status}>"
