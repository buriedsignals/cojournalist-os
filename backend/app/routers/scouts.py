"""
Page Scout (type "web") API endpoints.

PURPOSE: Two endpoints for website change detection:
- POST /scouts/execute (Lambda): Scheduled scrape + change detection +
  criteria analysis + notification. Auth: X-Service-Key.
- POST /scouts/test (UI): Preview scrape without establishing baseline.
  Auth: session cookie. Rate-limited.

DEPENDS ON: services/scout_service, dependencies (auth, service key),
    schemas/scouts (GeocodedLocation)
USED BY: Lambda (scheduled execution), frontend (test scrape),
    main.py (router mount)
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.services.scout_service import ScoutService
from app.schemas.scouts import GeocodedLocation
from app.dependencies import verify_service_key, verify_scraper_key, get_current_user, get_user_org_id

logger = logging.getLogger(__name__)

# Rate limiter for test endpoints
limiter = Limiter(key_func=get_remote_address)

router = APIRouter()
scout_service = ScoutService()


# =============================================================================
# Web Scout Endpoints
# =============================================================================

class ExecuteRequest(BaseModel):
    """Request body for scout execution."""
    url: str
    criteria: Optional[str] = None
    userId: Optional[str] = None  # Optional: Lambda sends it; frontend omits it (derived from JWT)
    scraperName: Optional[str] = None
    location: Optional[GeocodedLocation] = None  # For information unit storage
    topic: Optional[str] = Field(default=None, max_length=200)  # For topic-based information unit storage
    preferredLanguage: str = "en"
    provider: Optional[str] = None
    skip_credit_charge: bool = False


class ExecuteResponse(BaseModel):
    """Response body for scout execution."""
    scraper_status: bool
    criteria_status: bool
    summary: str
    provider: Optional[str] = None
    content_hash: Optional[str] = None


@router.post("/scouts/execute", response_model=ExecuteResponse)
async def execute_scout(
    request: ExecuteRequest,
    _: None = Depends(verify_scraper_key)
):
    """
    Execute a scout scrape and criteria check.
    Called by AWS Lambda on schedule.

    Returns format expected by scraper-lambda:
    - scraper_status: True if scrape succeeded
    - criteria_status: True if content matches criteria
    - summary: Contextual summary of changes (if criteria matched)
    """
    logger.info(f"Scout execute request for {request.url}")

    # Look up org_id for team billing
    org_id = await get_user_org_id(request.userId) if request.userId else None

    return await scout_service.execute(
        url=request.url,
        criteria=request.criteria,
        user_id=request.userId,
        scraper_name=request.scraperName,
        location=request.location,
        topic=request.topic,
        preferred_language=request.preferredLanguage,
        skip_credit_charge=request.skip_credit_charge,
        provider=request.provider,
        org_id=org_id,
    )


@router.post("/scouts/test", response_model=ExecuteResponse)
@limiter.limit("5/minute")
async def test_scout(
    request: Request,
    test_request: ExecuteRequest,
    user: dict = Depends(get_current_user),
):
    """
    Test a URL against criteria (for frontend testing).
    Requires session cookie authentication.
    Skips duplicate check and notification.

    Runs two tasks concurrently:
    - Task A: Plain preview scrape for summary/criteria result
    - Task B: Double-probe — two changeTracking calls to verify baseline storage
    """
    # Enforce authenticated user owns this request
    test_request.userId = user["user_id"]

    # Apply DEV_ prefix in development mode (must match scraper.py schedule_monitoring)
    scraper_name = test_request.scraperName
    if scraper_name and settings.environment == "development" and not scraper_name.startswith("DEV_"):
        scraper_name = f"DEV_{scraper_name}"

    logger.info(f"Scout test request for {test_request.url} (name: {scraper_name})")

    # Task A: Preview scrape (fast, ~500ms)
    preview_task = asyncio.create_task(
        scout_service.execute(
            url=test_request.url,
            criteria=test_request.criteria,
            user_id=test_request.userId,
            scraper_name=scraper_name,
            location=test_request.location,
            topic=test_request.topic,
            preferred_language=test_request.preferredLanguage,
            skip_duplicate_check=True,
            skip_notification=True,
            skip_credit_charge=True,
            preview_mode=True,
        )
    )

    # Task B: Double-probe (verifies changeTracking baseline storage)
    probe_task = asyncio.create_task(
        scout_service.double_probe(
            url=test_request.url,
            user_id=test_request.userId,
            scraper_name=scraper_name,
        )
    )

    result = await preview_task

    if result.get("scraper_status"):
        result["provider"] = await probe_task
    else:
        probe_task.cancel()

    return result


# =============================================================================
# Health Check Endpoint
# =============================================================================

@router.get("/scouts/health")
async def scouts_health():
    """Health check for scout endpoints."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "3.0.0",
        "endpoints": [
            "/scouts/execute",
            "/scouts/test",
        ],
        "note": "pulse moved to /pulse/*"
    }
