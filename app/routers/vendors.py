import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape

from app.core.database import get_db
from app.models.vendor import Vendor, VendorCategory, PartnershipStatus, VerificationStatus
from app.schemas.vendor import VendorCreate, VendorUpdate, VendorResponse, Coordinates

router = APIRouter(
    prefix="/api/v1/vendors",
    tags=["Vendors"],
)


def _convert_vendor_to_response(vendor: Vendor) -> VendorResponse:
    """Helper to serialize vendor with coordinate extraction from PostGIS geometry."""
    coords = None
    if vendor.location is not None:
        try:
            shape = to_shape(vendor.location)
            coords = Coordinates(longitude=shape.x, latitude=shape.y)
        except Exception:
            pass

    return VendorResponse(
        id=vendor.id,
        name=vendor.name,
        category=vendor.category,
        partnership_status=vendor.partnership_status,
        verification_status=vendor.verification_status,
        contact_name=vendor.contact_name,
        contact_phone=vendor.contact_phone,
        contact_email=vendor.contact_email,
        address=vendor.address,
        coordinates=coords,
        created_at=vendor.created_at,
        updated_at=vendor.updated_at,
    )


@router.post("/", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
def create_vendor(
    payload: VendorCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new vendor in the system (e.g. synced from Vendor Discovery/Intelligence modules).
    """
    loc = None
    if payload.coordinates:
        loc = WKTElement(f"POINT({payload.coordinates.longitude} {payload.coordinates.latitude})", srid=4326)

    vendor = Vendor(
        name=payload.name,
        category=payload.category,
        partnership_status=payload.partnership_status,
        verification_status=payload.verification_status,
        contact_name=payload.contact_name,
        contact_phone=payload.contact_phone,
        contact_email=payload.contact_email,
        address=payload.address,
        location=loc,
    )
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return _convert_vendor_to_response(vendor)


@router.get("/", response_model=List[VendorResponse])
def list_vendors(
    partnership_status: Optional[PartnershipStatus] = Query(None, description="Filter by partnership status"),
    category: Optional[VendorCategory] = Query(None, description="Filter by category"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    List vendors with optional filters.
    """
    query = db.query(Vendor)
    if partnership_status:
        query = query.filter(Vendor.partnership_status == partnership_status)
    if category:
        query = query.filter(Vendor.category == category)

    vendors = query.offset(skip).limit(limit).all()
    return [_convert_vendor_to_response(v) for v in vendors]


@router.get("/{vendor_id}", response_model=VendorResponse)
def get_vendor(
    vendor_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Retrieve vendor by ID.
    """
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor '{vendor_id}' not found.",
        )
    return _convert_vendor_to_response(vendor)
