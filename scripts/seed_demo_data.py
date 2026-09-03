"""
NILE Fulfillment Service — Seed & Verification Helper Script
Run this script to seed two sample vendors (one Partnered, one Non-Partnered)
into your database for the Bangalore -> Goa launch route.

Usage:
    python scripts/seed_demo_data.py
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import uuid
from app.core.database import SessionLocal
from app.models.vendor import Vendor, VendorCategory, PartnershipStatus, VerificationStatus

def seed():
    db = SessionLocal()
    try:
        print("[SEED] Seeding sample Bangalore -> Goa vendors...")

        # 1. Partnered Vendor (Programmatic API route)
        v_partnered = Vendor(
            id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            name="Taj Holiday Village Resort & Spa, Candolim",
            category=VendorCategory.STAY,
            partnership_status=PartnershipStatus.PARTNERED,
            verification_status=VerificationStatus.VERIFIED,
            contact_name="Reservations Desk",
            contact_phone="+91-832-6645858",
            contact_email="taj.candolim@ihcltata.com",
            address="Sinquerim, Candolim, Goa 403515",
        )

        # 2. Non-Partnered Vendor (HITL Manual Ops Outreach route)
        v_non_partnered = Vendor(
            id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            name="Thalassa Greek Taverna, Siolim",
            category=VendorCategory.DINING,
            partnership_status=PartnershipStatus.NON_PARTNERED,
            verification_status=VerificationStatus.UNVERIFIED,
            contact_name="Spiros / Manager on Duty",
            contact_phone="+91-9850033537",
            contact_email="reservations@thalassagrow.com",
            address="Plot No. 301, 1, Vaddy, Siolim, Goa 403517",
        )

        # Upsert or merge
        db.merge(v_partnered)
        db.merge(v_non_partnered)
        db.commit()

        print("\n[SUCCESS] Seeded Vendors successfully:")
        print(f"  * [PARTNERED]     ID: {v_partnered.id} | Name: {v_partnered.name}")
        print(f"  * [NON-PARTNERED] ID: {v_non_partnered.id} | Name: {v_non_partnered.name}")
        print("\n[INFO] Sample Intake Payload for Swagger (/docs):")
        print("""
{
  "itinerary_id": "itin_blr_goa_demo_01",
  "customer_id": "cust_rahul_99",
  "trip_title": "Bangalore to Goa Monsoon Getaway",
  "items": [
    {
      "vendor_id": "11111111-1111-1111-1111-111111111111",
      "service_date_start": "2026-10-15T14:00:00Z",
      "service_date_end": "2026-10-17T11:00:00Z",
      "group_size": 2,
      "max_budget": 15000.00,
      "notes": "Garden view cottage"
    },
    {
      "vendor_id": "22222222-2222-2222-2222-222222222222",
      "service_date_start": "2026-10-15T20:00:00Z",
      "group_size": 2,
      "max_budget": 4000.00,
      "notes": "Sunset view outdoor table"
    }
  ]
}
        """)
    finally:
        db.close()

if __name__ == "__main__":
    seed()
