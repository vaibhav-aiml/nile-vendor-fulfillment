# NILE — Vendor Partnership & Fulfillment Service

**Stage 5 of 5** in the NILE AI-powered travel planning pipeline for South India, launching with the Bangalore → Goa corridor.

[![Tests](https://img.shields.io/badge/tests-19%2F19%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.13-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-async-009688)]()
[![Next.js](https://img.shields.io/badge/Next.js-14-black)]()

This service is the final leg of the NILE pipeline — it takes a finalized, optimized itinerary and turns it into confirmed bookings, coordinating between automated partner integrations and a human-in-the-loop operations team for everyone else.

```
Customer Intent          Itinerary Planning        Vendor Discovery         Vendor Intelligence      Vendor Partnership & Fulfillment
   (Jigisha)         →       (Yashaswini)       →       (Aman)          →       (Gargeyi)         →         (Vaibhav) ← this service
```

---

## Why this service exists

NILE fulfills bookings through a **hybrid model**: some vendors are directly partnered and can be booked programmatically, while most (at launch) are not — for those, a human operations team has to call, confirm availability, lock pricing, and finalize the booking manually.

This service is the routing brain and system of record for that hybrid process. It:

- Decides, per vendor, whether a booking goes down the **automated** path or the **human-in-the-loop (HITL)** path
- Gives operations staff a dashboard to work non-partnered bookings without touching a database directly
- Tracks a hard SLA on manual outreach and automatically escalates anything that stalls
- Reports a single, honest fulfillment status back upstream — one failed booking is enough to flag the whole itinerary as needing attention, never a false "all confirmed"
- Is deliberately built so that as more vendors become partners, moving them from manual to automatic requires no architectural changes — just a new adapter

---

## How a booking flows through the system

```
                    POST /api/v1/fulfillment/intake
                                  │
                                  ▼
                    Vendor lookup: partnered or not?
                          │                    │
                 ┌────────┘                    └────────┐
                 ▼                                       ▼
        PARTNERED                              NON-PARTNERED
        Celery: attempt_partner_booking          Celery: initiate_hitl_outreach
        via PartnerBookingAdapter                 → queued for Ops Dashboard
                 │                                       │
                 ▼                                       ▼
          CONFIRMED / REJECTED              Ops agent works the queue manually
                                              (calls vendor, locks price, updates
                                               status via the dashboard)
                                                       │
                                          ┌────────────┼─────────────┐
                                          ▼                          ▼
                                   CONFIRMED / REJECTED      SLA breached (no response
                                                              within OUTREACH_SLA_HOURS)
                                                                       │
                                                                       ▼
                                                          Celery Beat auto-escalates
                                                          → ALTERNATE_NEEDED
                                                          → event fired on Redis
                                  │
                                  ▼
              status_aggregator.py rolls every item up into one
              overall_fulfillment_status per itinerary, reported via
              GET /api/v1/fulfillment/itinerary/{id}/status
```

**One rule governs the aggregate status:** if *any* item in an itinerary is `REJECTED` or `ALTERNATE_NEEDED`, the whole itinerary reports `BLOCKED_ALTERNATE_NEEDED` — even if nine out of ten bookings are confirmed. The customer-facing product should never show "all good" when it isn't.

---

## What's implemented

| Area | Details |
|---|---|
| **Partnered vs. non-partnered routing** | Branches on `vendor.partnership_status`; partnered vendors get a `PartnerBookingAdapter` stub ready for real API integrations, non-partnered vendors get queued for HITL outreach |
| **SLA monitoring** | Configurable `OUTREACH_SLA_HOURS` (default 24h); a Celery Beat task periodically scans for breached deadlines and auto-escalates them |
| **Idempotency** | A composite unique constraint on `(itinerary_id, vendor_id)` plus explicit `409 Conflict` handling — re-submitting the same itinerary payload never creates duplicate bookings |
| **Status aggregation** | A dedicated service rolls up all bookings tied to one itinerary into a single, honest overall status |
| **Event emission** | `BOOKING_CONFIRMED`, `BOOKING_REJECTED`, `OUTREACH_TIMEOUT`, and `ALTERNATE_NEEDED` are published over Redis Pub/Sub for downstream services to react to |
| **Ops Dashboard** | A mobile-first Next.js console for internal staff to see pending outreach, view vendor contact details, and update booking status, pricing, and notes — protected by a token-based auth dependency |
| **Geospatial vendor data** | Vendor locations stored as PostGIS points (`SRID 4326`) for future proximity/routing queries |

---

## Tech stack

| Layer | Choice |
|---|---|
| API | Python, FastAPI |
| Database | PostgreSQL + PostGIS |
| Async / background jobs | Celery + Redis (worker + beat) |
| Migrations | Alembic |
| Ops Dashboard | Next.js, TypeScript |
| Testing | Pytest, in-memory SQLite, eager Celery execution |

---

## Project structure

```
fulfillment-service/
├── app/
│   ├── core/               # config, DB session, ops-token auth
│   ├── models/              # Vendor, FulfillmentRequest (SQLAlchemy + GeoAlchemy2)
│   ├── schemas/             # Pydantic schemas + isolated upstream/downstream mock contracts
│   ├── services/
│   │   ├── routing.py               # partnered / non-partnered branching, idempotency
│   │   ├── status_aggregator.py     # itinerary-level status rollup
│   │   ├── partner_booking.py       # abstract adapter for partner APIs
│   │   └── event_publisher.py       # Redis Pub/Sub event emission
│   ├── workers/             # Celery app, booking + SLA escalation tasks
│   └── routers/              # fulfillment intake/status, ops dashboard, vendor endpoints
├── ops-dashboard/          # Next.js / TypeScript operations console
├── alembic/                 # DB migrations (PostGIS extension, schema, spatial index)
├── scripts/
│   ├── seed_demo_data.py           # seeds real Bangalore→Goa vendor examples
│   └── verify_live_pipeline.py      # end-to-end smoke test against a running instance
└── tests/                    # 19 tests covering routing, SLA, aggregation, ops API, contracts
```

---

## Getting started

### 1. Configure environment

```bash
cp .env.example .env
```

Fill in:

```bash
DATABASE_URL=postgresql://postgres:password@localhost:5432/nile_fulfillment
REDIS_URL=redis://localhost:6379/0
OUTREACH_SLA_HOURS=24
OPS_AUTH_SECRET=your_ops_secret_token_here
```

### 2. Install & migrate

```bash
pip install -r requirements.txt

# Postgres needs the PostGIS extension:
# CREATE EXTENSION IF NOT EXISTS postgis;

alembic upgrade head
```

### 3. Run the service

```bash
# Terminal 1 — API
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Celery worker
celery -A app.workers.celery_app worker --loglevel=info

# Terminal 3 — Celery beat (SLA escalation)
celery -A app.workers.celery_app beat --loglevel=info

# Terminal 4 — Ops Dashboard
cd ops-dashboard && npm install && npm run dev
```

- API docs: `http://localhost:8000/docs`
- Ops console: `http://localhost:3000`

### 4. Try the full flow

```bash
python scripts/seed_demo_data.py
python scripts/verify_live_pipeline.py <YOUR_OPS_TOKEN>
```

This seeds a partnered vendor (Taj Holiday Village, Candolim) and a non-partnered one (Thalassa Greek Taverna, Siolim), then exercises intake → routing → idempotency → ops update → SLA escalation → event emission end to end.

---

## Testing

```bash
pytest -v
```

19 tests run entirely against in-memory SQLite with `task_always_eager=True`, so the full suite runs with no live database, Redis, or external dependency — anyone can clone and verify the logic in seconds.

| Suite | Covers |
|---|---|
| `test_routing.py` | Partnered/non-partnered branching, duplicate-intake idempotency |
| `test_status_aggregator.py` | Every overall-status rule, including single-failure blocking |
| `test_celery_sla.py` | SLA breach detection using real past/future deadlines, not empty-set checks |
| `test_ops_api.py` | Auth enforcement, filtering, status updates, event emission on rejection |
| `test_contracts.py` | Upstream/downstream schema validation |
| `test_fulfillment_api.py` | Full intake-to-status lifecycle |

---

## API reference

### `POST /api/v1/fulfillment/intake`
Receives a finalized itinerary and routes each item to the appropriate booking path.

```json
{
  "itinerary_id": "itin_blr_goa_001",
  "customer_id": "cust_12345",
  "group_size": 4,
  "itinerary": {
    "destination": "Goa",
    "start_date": "2026-10-10",
    "end_date": "2026-10-12",
    "hotel": {
      "hotel_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "name": "Taj Holiday Village Resort"
    },
    "days": [
      {
        "day": 1,
        "date": "2026-10-10",
        "activities": [
          {
            "activity_id": "7ca85f64-5717-4562-b3fc-2c963f66bbb7",
            "name": "Scuba Diving at Grande Island",
            "start_time": "09:00",
            "end_time": "12:00",
            "estimated_cost": 3500.00
          }
        ]
      }
    ],
    "estimated_total_cost": 18000.00
  }
}
```

### `GET /api/v1/fulfillment/itinerary/{itinerary_id}/status`
Returns the rolled-up status for every booking in an itinerary.

```json
{
  "itinerary_id": "itin_blr_goa_001",
  "overall_fulfillment_status": "PARTIALLY_CONFIRMED",
  "total_items": 2,
  "confirmed_items": 1,
  "pending_items": 1,
  "failed_or_alternate_items": 0,
  "items": [ ... ]
}
```

### Ops Dashboard endpoints (require `X-Ops-Token` header)
| Endpoint | Purpose |
|---|---|
| `GET /api/v1/ops/requests` | List bookings, filterable by status, vendor, date, SLA breach |
| `GET /api/v1/ops/vendors/{id}/contact` | Vendor contact details for manual outreach |
| `PATCH /api/v1/ops/requests/{id}/status` | Update status, lock pricing, assign an agent, log notes |

Full interactive documentation is available at `/docs` once the API is running.

---

## Design decisions worth knowing about

- **Why the nested intake schema?** The intake payload mirrors Yashaswini's confirmed `Itinerary` schema from the Itinerary & Recommendation Engine exactly (one hotel, days with nested activities). The flattening logic in `routing.py` maps this nested structure into individual `FulfillmentRequest` rows. Two fields (`group_size`, `customer_id`) are assumed to arrive as envelope siblings — their exact source is pending confirmation.
- **Why Redis Pub/Sub and not Kafka?** Redis is already a dependency for Celery. Introducing a second message broker for event emission wasn't justified at this stage — the interface is kept clean enough to swap later if volume demands it.
- **Why a static ops token instead of full JWT auth?** This is a phase-1 internal tool for a small ops team, not a public-facing surface. A shared secret header is proportionate to the actual risk right now and can be upgraded to per-agent auth without touching the booking logic.
- **Why does `REJECTED` stay separate from `ALTERNATE_NEEDED` at the row level?** They mean different things operationally — a vendor declining is not the same as a booking that never got a response — even though both currently block the same aggregate status. Preserving the distinction now avoids losing operational history later.

---

## Roadmap

- [x] ~~Replace mock contracts with confirmed schemas from Itinerary Planning and Vendor Discovery~~
- [ ] Implement real `PartnerBookingAdapter` integrations as vendor partnerships are signed
- [ ] Wire an actual re-ranking request back to Itinerary Planning on `ALTERNATE_NEEDED`
- [ ] Move Ops Dashboard auth from a shared static token to per-agent authentication
- [ ] Add proximity-based vendor suggestions using the existing PostGIS location data

---

## Part of NILE

This repository implements one stage of a five-stage system. See the pipeline overview above for how it fits alongside Customer Intent, Itinerary Planning, Vendor Discovery, and Vendor Intelligence.
