from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers import ops_router, fulfillment_router, vendors_router

app = FastAPI(
    title="NILE — Vendor Partnership & Fulfillment Service",
    description=(
        "Final stage in the NILE 5-stage travel planning pipeline. "
        "Responsible for vendor partnership branching, programmatic vs. HITL ops bookings, "
        "SLA escalation, and upstream status reporting."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fulfillment_router)
app.include_router(ops_router)
app.include_router(vendors_router)


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": "nile-fulfillment-service",
        "environment": settings.ENVIRONMENT,
        "outreach_sla_hours": settings.OUTREACH_SLA_HOURS,
    }


@app.get("/", tags=["Health"])
def root():
    return {
        "message": "Welcome to NILE Vendor Partnership & Fulfillment Service",
        "docs": "/docs",
        "health": "/health",
    }
