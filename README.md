# NILE — Vendor Partnership & Fulfillment Service

Stage 5 in the **NILE** AI-powered travel planning pipeline (launching with the Bangalore → Goa route):

```
Customer Intent (Jigisha) 
   → Itinerary Planning (Yashaswini) 
   → Vendor Discovery (Aman) 
   → Vendor Intelligence (Gargeyi) 
   → Vendor Partnership & Fulfillment (Vaibhav / This Service)
```

---

## 🌟 Overview & Responsibilities

The **Vendor Partnership & Fulfillment Service** receives finalized itineraries and is responsible for:
1. **Partnered vs. Non-Partnered Routing**:
   - **Partnered Vendors**: Dispatches programmatic booking attempts via asynchronous Celery background tasks and clean adapter interfaces (`PartnerBookingAdapter`).
   - **Non-Partnered Vendors**: Pushes booking requests into a Human-in-the-Loop (HITL) queue for Ops staff manual outreach via the **Ops Dashboard**.
2. **SLA Monitoring & Escalation**:
   - Computes an outreach SLA deadline for non-partnered vendors (`OUTREACH_SLA_HOURS`, default 24h).
   - Periodic Celery Beat worker escalates timed-out requests to `ALTERNATE_NEEDED` and emits notification events.
3. **Idempotency**:
   - Prevents duplicate `FulfillmentRequest` creation on `POST /api/v1/fulfillment/intake` for the same `(itinerary_id, vendor_id)`.
4. **Upstream Status Aggregation**:
   - Reports full fulfillment status back upstream via a dedicated service (`status_aggregator.py`):
     - `ALL_CONFIRMED`
     - `PARTIALLY_CONFIRMED`
     - `BLOCKED_ALTERNATE_NEEDED` (priority alert on any rejection/timeout)
     - `IN_PROGRESS`
     - `CANCELLED`
5. **Event Emission**:
   - Emits lifecycle events (`BOOKING_CONFIRMED`, `BOOKING_REJECTED`, `OUTREACH_TIMEOUT`, `ALTERNATE_NEEDED`) over Redis Pub/Sub (`REDIS_EVENTS_CHANNEL`).

---

## 🏗️ Architecture & Folder Structure

```
fulfillment-service/
├── .env.example              # Template environment configuration
├── .gitignore
├── requirements.txt          # Python dependencies
├── alembic.ini               # Alembic database migration config
├── pytest.ini                # Pytest runner settings
├── README.md
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_schema.py  # PostGIS, vendors, and fulfillment tables
├── app/
│   ├── main.py               # FastAPI application & router mounting
│   ├── core/
│   │   ├── config.py         # Pydantic Settings & environment variables
│   │   ├── database.py       # SQLAlchemy engine, sessionmaker, Base
│   │   └── security.py       # Phase 1 static X-Ops-Token verification
│   ├── models/
│   │   ├── vendor.py         # Vendor model with PostGIS Point geometry
│   │   └── booking.py        # FulfillmentRequest state machine model
│   ├── schemas/
│   │   ├── contracts.py      # MOCK upstream/downstream schemas (pending team specs)
│   │   ├── vendor.py         # Vendor Pydantic schemas & coordinate serializer
│   │   └── booking.py        # Request & Ops status update schemas
│   ├── services/
│   │   ├── routing.py        # Routing logic & intake idempotency
│   │   ├── status_aggregator.py # Aggregates multiple requests into overall status
│   │   ├── partner_booking.py   # Abstract interface & stubs for partner APIs
│   │   └── event_publisher.py   # Redis Pub/Sub event emitter
│   ├── workers/
│   │   ├── celery_app.py     # Celery instance & periodic Beat schedule
│   │   └── tasks.py          # attempt_partner_booking, SLA escalation tasks
│   └── routers/
│       ├── ops.py            # Ops Dashboard endpoints (authenticated)
│       ├── fulfillment.py    # Intake & status inquiry endpoints
│       └── vendors.py        # Vendor CRUD & lookup
├── ops-dashboard/            # Mobile-first Next.js / TypeScript console
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.js
│   └── src/
│       ├── pages/index.tsx   # Dashboard with KPIs, filters, outreach modal
│       ├── services/api.ts   # Client communicating with FastAPI backend
│       └── styles/globals.css
└── tests/
    ├── conftest.py           # SQLite in-memory test DB & Celery eager setup
    ├── test_contracts.py     # Schema contract tests
    ├── test_status_aggregator.py # Aggregate fulfillment status rule tests
    ├── test_routing.py       # Partnered/non-partnered branching & idempotency tests
    ├── test_celery_sla.py    # SLA escalation worker tests
    ├── test_ops_api.py       # Ops endpoints & token security tests
    └── test_fulfillment_api.py # Full intake & status lifecycle tests
```

---

## ⚙️ Prerequisites & Setup

### 1. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Fill in your local PostgreSQL, Redis, and security secrets:
```ini
# PostgreSQL with PostGIS
DATABASE_URL=postgresql://postgres:password@localhost:5432/nile_fulfillment

# Redis (for Celery & Pub/Sub)
REDIS_URL=redis://localhost:6379/0

# SLA Configuration (hours)
OUTREACH_SLA_HOURS=24

# Ops Authentication Header (X-Ops-Token)
OPS_AUTH_SECRET=your_ops_secret_token_here
```

### 2. Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Database Migrations (PostgreSQL + PostGIS)
Ensure the `postgis` extension is available in PostgreSQL:
```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```
Run Alembic migrations:
```bash
alembic upgrade head
```

---

## 🚀 Running the Services

### 1. Start FastAPI Backend
```bash
uvicorn app.main:app --reload --port 8000
```
Interactive Swagger API documentation: `http://localhost:8000/docs`

### 2. Start Celery Background Worker
```bash
celery -A app.workers.celery_app worker --loglevel=info
```

### 3. Start Celery Beat (Periodic SLA Checks)
```bash
celery -A app.workers.celery_app beat --loglevel=info
```

### 4. Start Ops Dashboard Frontend
```bash
cd ops-dashboard
npm install
npm run dev
```
Open `http://localhost:3000` to access the Ops Console.

---

## 🔒 Ops Dashboard Authentication (Phase 1)
All endpoints under `/api/v1/ops/` require the static secret token configured in `OPS_AUTH_SECRET`:
```http
X-Ops-Token: <OPS_AUTH_SECRET>
```
In the Next.js Ops Dashboard, click the **🔑 Token** button in the header to view or update the active token.

---

## 🧪 Running Automated Tests

Run the complete test suite (18 unit and integration tests):
```bash
pytest -v
```

Tests run with in-memory SQLite and eager Celery execution (`task_always_eager=True`), requiring no live database or Redis server to execute.

---

## 📋 Upstream / Downstream Contracts

All contracts are isolated in [app/schemas/contracts.py](file:///c:/Users/CHANDRA%20SHEKHAR/OneDrive/Desktop/vendor-fulfillment/fulfillment-service/app/schemas/contracts.py) and marked `# MOCK — pending confirmation from Yashaswini/Aman`.

### Intake Request (`POST /api/v1/fulfillment/intake`):
```json
{
  "itinerary_id": "itin_blr_goa_001",
  "customer_id": "cust_12345",
  "trip_title": "Bangalore to Goa 4-Day Roadtrip",
  "items": [
    {
      "vendor_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "service_date_start": "2026-10-10T10:00:00Z",
      "service_date_end": "2026-10-10T12:00:00Z",
      "group_size": 4,
      "max_budget": 5000.00,
      "notes": "Outdoor deck preferred"
    }
  ]
}
```

### Upstream Status Response (`GET /api/v1/fulfillment/itinerary/{itinerary_id}/status`):
```json
{
  "itinerary_id": "itin_blr_goa_001",
  "overall_fulfillment_status": "PARTIALLY_CONFIRMED",
  "total_items": 2,
  "confirmed_items": 1,
  "pending_items": 1,
  "failed_or_alternate_items": 0,
  "items": [
    {
      "request_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "vendor_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "vendor_name": "Taj Holiday Village Resort & Spa",
      "partnership_status": "PARTNERED",
      "status": "CONFIRMED",
      "booking_channel": "PROGRAMMATIC_API",
      "pricing_locked": 4500.00,
      "external_reference_id": "PARTNER-CONF-98A1B2C3",
      "notes": "Programmatic booking confirmed"
    }
  ],
  "last_updated": "2026-09-03T08:30:00Z"
}
```
