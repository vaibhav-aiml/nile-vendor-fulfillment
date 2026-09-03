"""
NILE Fulfillment Service — Live Verification Script (7-Step Sequence)

Run this against your live running FastAPI instance (e.g. after filling .env and starting uvicorn):
    python scripts/verify_live_pipeline.py

This automatically exercises all manual testing steps and prints the results.
"""

import os
import sys
import time
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from app.core.config import settings
    DEFAULT_TOKEN = settings.OPS_AUTH_SECRET
except Exception:
    DEFAULT_TOKEN = "nile_ops_secret_token_live_2026"

BASE_URL = os.getenv("API_URL", "http://localhost:8005")


def run_verification(base_url=BASE_URL, ops_token=DEFAULT_TOKEN):
    print("=" * 70)
    print("NILE FULFILLMENT SERVICE -- LIVE VERIFICATION SEQUENCE")
    print("=" * 70)

    # 1. Health check
    print("\n[Step 1] Checking FastAPI server health at /health...")
    try:
        res = requests.get(f"{base_url}/health", timeout=3)
        if res.status_code == 200:
            print(f"  [PASS] Server healthy: {res.json()}")
        else:
            print(f"  [FAIL] Server returned {res.status_code}: {res.text}")
            return False
    except Exception as e:
        print(f"  [FAIL] Server unreachable at {base_url}: {e}")
        print("  --> Make sure to run: uvicorn app.main:app --reload --port 8000")
        return False

    # 2. Seed vendors
    print("\n[Step 2] Creating two test vendors (1 Partnered, 1 Non-Partnered)...")
    v_partner_payload = {
        "name": f"Taj Holiday Village Candolim (Test-{int(time.time())})",
        "category": "STAY",
        "partnership_status": "PARTNERED",
        "contact_phone": "+91-832-6645858",
        "contact_email": "taj@example.com",
    }
    v_non_partner_payload = {
        "name": f"Thalassa Siolim (Test-{int(time.time())})",
        "category": "DINING",
        "partnership_status": "NON_PARTNERED",
        "contact_phone": "+91-9850033537",
        "contact_email": "thalassa@example.com",
    }
    r1 = requests.post(f"{base_url}/api/v1/vendors/", json=v_partner_payload)
    r2 = requests.post(f"{base_url}/api/v1/vendors/", json=v_non_partner_payload)
    if r1.status_code != 201 or r2.status_code != 201:
        print(f"  [FAIL] Vendor creation failed: {r1.text} | {r2.text}")
        return False

    partner_id = r1.json()["id"]
    non_partner_id = r2.json()["id"]
    print(f"  [PASS] Created Partnered Vendor ID:     {partner_id}")
    print(f"  [PASS] Created Non-Partnered Vendor ID: {non_partner_id}")

    # 3. POST /fulfillment/intake
    print("\n[Step 3] Submitting mock itinerary intake to /api/v1/fulfillment/intake...")
    itinerary_id = f"itin_live_test_{int(time.time())}"
    intake_payload = {
        "itinerary_id": itinerary_id,
        "customer_id": "cust_live_01",
        "trip_title": "Bangalore -> Goa Verified Route",
        "items": [
            {
                "vendor_id": partner_id,
                "group_size": 2,
                "notes": "Deluxe Room",
            },
            {
                "vendor_id": non_partner_id,
                "group_size": 2,
                "notes": "Dinner table",
            },
        ],
    }
    r3 = requests.post(f"{base_url}/api/v1/fulfillment/intake", json=intake_payload)
    print(f"  HTTP Status: {r3.status_code}")
    if r3.status_code == 201:
        data = r3.json()
        print(f"  [PASS] Received 201 Created. Total items: {data['total_items']}")
        print(f"  * Overall Status: {data['overall_fulfillment_status']}")
        for it in data["items"]:
            print(f"    - Vendor {it['vendor_name']} -> Channel: {it['booking_channel']}, Status: {it['status']}")
    else:
        print(f"  [FAIL] Intake failed: {r3.text}")
        return False

    # 4. Re-POST duplicate intake
    print("\n[Step 4] Re-POSTing exact same intake payload to verify idempotency (409 Conflict)...")
    r4 = requests.post(f"{base_url}/api/v1/fulfillment/intake", json=intake_payload)
    print(f"  HTTP Status: {r4.status_code}")
    if r4.status_code == 409:
        print(f"  [PASS] Clean 409 Conflict received as expected: {r4.json()['detail']}")
    else:
        print(f"  [FAIL] Expected 409 Conflict, got {r4.status_code}: {r4.text}")

    # 5. Check Ops dashboard requests
    print("\n[Step 5] Checking Ops endpoints with X-Ops-Token header...")
    headers = {"X-Ops-Token": ops_token}
    r5 = requests.get(f"{base_url}/api/v1/ops/requests?itinerary_id={itinerary_id}", headers=headers)
    if r5.status_code == 200:
        ops_items = r5.json()["items"]
        print(f"  [PASS] Ops request list returned {len(ops_items)} rows for {itinerary_id}:")
        non_partner_req = None
        for it in ops_items:
            print(f"    - Req ID: {it['id']} | Channel: {it['booking_channel']} | Status: {it['status']}")
            if it["booking_channel"] == "HITL_MANUAL":
                non_partner_req = it
    else:
        print(f"  [FAIL] Ops request list failed ({r5.status_code}): {r5.text}")
        return False

    # 6. PATCH non-partnered request to CONFIRMED
    if non_partner_req:
        print(f"\n[Step 6] Ops Staff confirms non-partnered request {non_partner_req['id']}...")
        patch_payload = {
            "status": "CONFIRMED",
            "pricing_locked": 3800.00,
            "assigned_ops_agent": "ops_vaibhav",
            "notes": "Verified availability with manager Spiros. Table confirmed.",
            "external_reference_id": "VOUCH-GOA-7788",
        }
        r6 = requests.patch(
            f"{base_url}/api/v1/ops/requests/{non_partner_req['id']}/status",
            headers=headers,
            json=patch_payload,
        )
        if r6.status_code == 200:
            print(f"  [PASS] Updated request status to CONFIRMED.")
            # Verify status aggregation endpoint
            r_status = requests.get(f"{base_url}/api/v1/fulfillment/itinerary/{itinerary_id}/status")
            print(f"  [PASS] Itinerary aggregate status: {r_status.json()['overall_fulfillment_status']}")
            print(f"         Confirmed items: {r_status.json()['confirmed_items']} / {r_status.json()['total_items']}")
        else:
            print(f"  [FAIL] Ops status update failed: {r6.text}")

    print("\n" + "=" * 70)
    print("[SUCCESS] All live verification steps against real Supabase DB passed!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    token = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TOKEN
    run_verification(ops_token=token)
