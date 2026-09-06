"""
NILE Fulfillment Service — Seed & Verification Helper Script
Run this script to seed sample vendors (Partnered hotel, Non-Partnered dining,
Partnered activity) into your database for the Bangalore -> Goa launch route.

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

        # 1. Partnered Hotel (Programmatic API route)
        v_hotel = Vendor(
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

        # 2. Non-Partnered Dining Vendor (HITL Manual Ops Outreach route)
        v_dining = Vendor(
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

        # 3. Partnered Activity Vendor (Programmatic API route)
        v_activity = Vendor(
            id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
            name="Grande Island Scuba Diving, Goa",
            category=VendorCategory.ACTIVITY,
            partnership_status=PartnershipStatus.PARTNERED,
            verification_status=VerificationStatus.VERIFIED,
            contact_name="Adventure Desk",
            contact_phone="+91-832-2268726",
            contact_email="bookings@grandescuba.com",
            address="Vasco da Gama, Goa 403802",
        )

        # Upsert or merge
        db.merge(v_hotel)
        db.merge(v_dining)
        db.merge(v_activity)
        db.commit()

        print("\n[SUCCESS] Seeded Vendors successfully:")
        print(f"  * [PARTNERED HOTEL]    ID: {v_hotel.id} | Name: {v_hotel.name}")
        print(f"  * [NON-PARTNERED]      ID: {v_dining.id} | Name: {v_dining.name}")
        print(f"  * [PARTNERED ACTIVITY] ID: {v_activity.id} | Name: {v_activity.name}")
        print("\n[INFO] Sample Intake Payload for Swagger (/docs):")
        print("""
{
  "itinerary_id": "itin_blr_goa_demo_01",
  "customer_id": "cust_rahul_99",
  "group_size": 2,
  "itinerary": {
    "destination": "Goa",
    "start_date": "2026-10-15",
    "end_date": "2026-10-17",
    "hotel": {
      "hotel_id": "11111111-1111-1111-1111-111111111111",
      "name": "Taj Holiday Village Resort & Spa, Candolim"
    },
    "days": [
      {
        "day": 1,
        "date": "2026-10-15",
        "activities": [
          {
            "activity_id": "33333333-3333-3333-3333-333333333333",
            "name": "Scuba Diving at Grande Island",
            "start_time": "09:00",
            "end_time": "12:00",
            "estimated_cost": 3500.00
          }
        ]
      },
      {
        "day": 2,
        "date": "2026-10-16",
        "activities": [
          {
            "activity_id": "22222222-2222-2222-2222-222222222222",
            "name": "Dinner at Thalassa Greek Taverna",
            "start_time": "19:00",
            "end_time": "21:30",
            "estimated_cost": 4000.00
          }
        ]
      }
    ],
    "estimated_total_cost": 22500.00
  }
}
        """)
    finally:
        db.close()

if __name__ == "__main__":
    seed()
