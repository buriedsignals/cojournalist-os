"""
Scraper router for managing scheduled scrapers and monitoring jobs.

PURPOSE: CRUD for scout schedules — create (POST /scrapers/monitoring),
list (GET /scrapers/active), delete (DELETE /scrapers/active/{name}),
validate credits (POST /scrapers/monitoring/validate), and manual trigger
(POST /scrapers/run-now). Orchestrates DynamoDB SCRAPER# records,
EventBridge schedules via API Gateway, and EXEC# baselines.

DEPENDS ON: config (AWS settings, INTERNAL_SERVICE_KEY), dependencies (session auth, decrement_credit),
    models/responses (request/response models), services/cron (EventBridge cron),
    services/schedule_service (for run-now), services/execution_deduplication
    (EXEC# baseline at schedule time), utils/credits (validation + costs)
USED BY: frontend (scouts panel), main.py (router mount)

CRITICAL: When scheduling a web scout, this router stores the initial EXEC#
baseline using content_hash from the test run. This prevents a redundant
re-scrape on the first scheduled execution. See CLAUDE.md "Schedule-Time Baseline".
"""
from __future__ import annotations

import hashlib
import hmac as hmac_mod
import json
import logging
import os
import time as time_mod
from datetime import datetime
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from pydantic import BaseModel

from app.config import settings
from app.dependencies import get_current_user, decrement_credit, validate_credits
from app.services.user_service import UserService
from app.models.responses import (
    MonitoringScheduleRequest,
    MonitoringScheduleResponse,
    CreditChargeRequest,
    CreditBalanceResponse,
    ValidateCreditsResponse,
    RunNowResponse,
)
try:
    from app.services.cron import build_scraper_cron, CronBuilderError
except ImportError:
    # OSS mirror: cron expressions built by SupabaseScheduler adapter
    def build_scraper_cron(*args, **kwargs): return "0 * * * *"
    class CronBuilderError(Exception): pass
from app.services.post_snapshot_service import PostSnapshotService
from app.services.scout_runner import ScoutRunner
from app.utils.pricing import calculate_monitoring_cost, CREDIT_COSTS, get_social_monitoring_cost, get_pulse_cost


# Lazy singleton for PostSnapshotService
_snapshot_svc: Optional[PostSnapshotService] = None


def _get_snapshot_service() -> PostSnapshotService:
    global _snapshot_svc
    if _snapshot_svc is None:
        _snapshot_svc = PostSnapshotService()
    return _snapshot_svc


def _build_aws_headers(user: dict) -> dict:
    """Build HMAC-signed headers for API Gateway calls.

    Signs user_id + timezone + timestamp with INTERNAL_SERVICE_KEY.
    The service-key-authorizer Lambda verifies this signature and
    populates the authorizer context for downstream Lambdas.
    """
    user_id = user["user_id"]
    timezone = user.get("timezone") or "UTC"
    timestamp = str(int(time_mod.time()))

    message = f"{user_id}:{timezone}:{timestamp}"
    signature = hmac_mod.new(
        settings.internal_service_key.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()

    return {
        "Content-Type": "application/json",
        "X-Service-Key": settings.internal_service_key,
        "X-User-Id": user_id,
        "X-User-Timezone": timezone,
        "X-Timestamp": timestamp,
        "X-Signature": signature,
    }


async def execute_initial_pulse_background(
    scraper_name: str,
    user_id: str,
    location: dict | None,
    topic: str | None,
    criteria: str | None,
    preferred_language: str,
):
    """Execute initial run for Pulse scout via internal HTTP call."""
    try:
        # Use same pattern as run_scout_now (internal HTTP call to execute endpoint)
        port = os.environ.get("PORT", "8000")
        execute_url = f"http://127.0.0.1:{port}/api/pulse/execute"

        payload = {
            "scraperName": scraper_name,
            "userId": user_id,
            "preferred_language": preferred_language,
        }
        if location:
            payload["location"] = location
        if topic:
            payload["topic"] = topic
        if criteria:
            payload["criteria"] = criteria

        # Initial run: skip notification, credit charge, and unit extraction
        payload["skip_notification"] = True
        payload["skip_credit_charge"] = True
        payload["skip_unit_extraction"] = True

        async with httpx.AsyncClient() as client:
            response = await client.post(
                execute_url,
                json=payload,
                headers={"X-Service-Key": settings.internal_service_key},
                timeout=120.0,  # Allow time for AI processing
            )

        if response.status_code == 200:
            logger.info(f"Initial run completed for pulse scout: {scraper_name}")
        else:
            logger.warning(f"Initial run returned {response.status_code} for {scraper_name}: {response.text[:200]}")

    except httpx.TimeoutException:
        logger.error(f"Initial run timed out for pulse scout {scraper_name} after 120s")
        # Don't fail - scout is already scheduled, user can "Run Now" later
    except Exception as e:
        logger.error(f"Initial run failed for pulse scout {scraper_name}: {e}")
        # Don't fail - scout is already scheduled, user can "Run Now" later



class MonitoringValidationRequest(BaseModel):
    """Request to validate monitoring credits before scheduling."""
    channel: str = "website"  # "website" or "social"
    regularity: str  # "daily", "weekly", "monthly"
    scout_type: str | None = None  # "pulse", "social", etc.
    platform: str | None = None  # "instagram", "x", "facebook" (social scouts)
    source_mode: str | None = None  # "reliable" or "niche" (pulse scouts)
    has_location: bool = False  # Whether the scout has a location (pulse scouts)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/scrapers/monitoring", response_model=MonitoringScheduleResponse)
async def schedule_monitoring(
    payload: MonitoringScheduleRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """
    Generate a cron expression for a monitoring job and (eventually) forward it to our scheduler.

    This endpoint currently only returns the computed cron metadata. The outbound scheduler
    integration will be added later once the API endpoint is available.
    """
    # Prefix scraper name with DEV_ in development mode for easy cleanup
    # Note: EventBridge only allows [0-9a-zA-Z-_.] in names
    scraper_name = payload.name
    if settings.environment == "development" and not scraper_name.startswith("DEV_"):
        scraper_name = f"DEV_{scraper_name}"

    # Validate timezone is set - don't silently fall back to UTC
    user_timezone = user.get("timezone")
    if not user_timezone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Timezone not set. Please set your timezone before scheduling monitoring jobs.",
        )

    try:
        cron_schedule = build_scraper_cron(
            timezone=user_timezone,
            regularity=payload.regularity,
            day_number=payload.day_number,
            time_str=payload.time,
        )
    except CronBuilderError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    logger.info(
        "Generated cron %s (%s) for user %s",
        cron_schedule.expression,
        cron_schedule.timezone,
        user.get("user_id"),
    )

    # Submit to AWS API Gateway
    aws_payload = {
        "name": scraper_name,
        "cron_expression": cron_schedule.expression,
        "timezone": cron_schedule.timezone,
        "url": payload.url,
        "criteria": payload.criteria,
        "monitoring": payload.monitoring,
        "regularity": payload.regularity,  # For storing in SCRAPER# record
        "time": payload.time,  # Original time string for UI display (e.g., "10:20")
        "scout_type": payload.scout_type,  # Scout type for Lambda routing
        "preferred_language": user.get("preferred_language", "en"),
        "provider": payload.provider,  # Detected scraping provider (web scouts)
    }

    # Add local scout specific fields if present
    if payload.scout_type in ("web", "pulse"):
        if payload.location:
            aws_payload["location"] = payload.location.model_dump(exclude_none=True)
        if payload.topic:
            aws_payload["topic"] = payload.topic
        if hasattr(payload, 'source_mode') and payload.source_mode and payload.source_mode != "niche":
            aws_payload["source_mode"] = payload.source_mode
        if payload.excluded_domains:
            aws_payload["excluded_domains"] = payload.excluded_domains
    elif payload.scout_type == "social":
        if payload.regularity == "daily":
            raise HTTPException(status_code=400, detail="Social scouts require weekly or monthly frequency")
        aws_payload["platform"] = payload.platform
        aws_payload["profile_handle"] = payload.profile_handle
        aws_payload["monitor_mode"] = payload.monitor_mode
        aws_payload["track_removals"] = payload.track_removals
        if payload.criteria:
            aws_payload["criteria"] = payload.criteria
        if payload.topic:
            aws_payload["topic"] = payload.topic
    elif payload.scout_type == "civic":
        aws_payload["root_domain"] = payload.root_domain or ""
        aws_payload["tracked_urls"] = payload.tracked_urls or []
        if payload.location:
            aws_payload["location"] = payload.location.model_dump(exclude_none=True)
        if payload.criteria:
            aws_payload["criteria"] = payload.criteria
        if payload.topic:
            aws_payload["topic"] = payload.topic

    logger.info(
        "Forwarding monitoring schedule request to AWS for user %s (initialized: %s)",
        user.get("user_id"),
        not user.get("needs_initialization", True),
    )
    logger.debug("AWS payload: %s", aws_payload)

    headers = _build_aws_headers(user)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.aws_api_base_url}/schedule_scraper",
                json=aws_payload,
                headers=headers,
                timeout=30.0,
            )

            if response.status_code != 200:
                error_detail = response.text
                error_json = None
                try:
                    error_json = response.json()
                    error_detail = error_json.get("error") or error_json.get("message") or error_detail
                except Exception:
                    pass

                logger.error(
                    "AWS scheduler error for user %s - Status: %d, Response: %s",
                    user.get("user_id"),
                    response.status_code,
                    error_json or response.text[:200],
                )
                logger.error("Request payload: %s", aws_payload)

                # Provide more helpful error messages
                if response.status_code == 401:
                    detail = "Authentication failed. Please ensure you have completed onboarding and try again."
                elif response.status_code == 403:
                    detail = "Access denied. Your account may not have permission to schedule monitoring jobs."
                else:
                    detail = f"Failed to schedule monitoring job: {error_detail}"

                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=detail,
                )

            aws_response = response.json()
            logger.info(
                "Successfully scheduled monitoring job '%s' in AWS: %s",
                payload.name,
                aws_response,
            )

            # For web scouts with a content hash, store EXEC# baseline record
            if payload.scout_type == "web" and payload.content_hash:
                from app.services.execution_deduplication import ExecutionDeduplicationService
                exec_dedup = ExecutionDeduplicationService()
                try:
                    await exec_dedup.store_execution(
                        user_id=user.get("user_id"),
                        scout_name=scraper_name,
                        scout_type="web",
                        summary_text="Baseline established",
                        is_duplicate=False,
                        started_at=datetime.utcnow().isoformat() + "Z",
                        content_hash=payload.content_hash,
                        provider=payload.provider,
                    )
                    logger.info(f"Stored EXEC# baseline for {scraper_name}")
                except Exception as e:
                    logger.warning(f"Failed to store EXEC# baseline for {scraper_name}: {e}")

            # For social scouts with baseline data, store initial POSTS# snapshot
            if payload.scout_type == "social" and payload.baseline_posts:
                try:
                    await _get_snapshot_service().store_snapshot(
                        user.get("user_id"),
                        scraper_name,
                        payload.baseline_posts,
                        payload.platform,
                        payload.profile_handle,
                    )
                    logger.info(f"Stored POSTS# baseline for social scout {scraper_name}")
                except Exception as e:
                    logger.warning(f"Failed to store POSTS# baseline for {scraper_name}: {e}")

            # For civic scouts with initial promises, store PROMISE# records
            if payload.scout_type == "civic" and payload.initial_promises:
                try:
                    from app.services.civic_orchestrator import CivicOrchestrator
                    from app.schemas.civic import Promise
                    orchestrator = CivicOrchestrator()
                    promises = []
                    for p in payload.initial_promises:
                        try:
                            promises.append(Promise(**p))
                        except Exception:
                            continue
                    if promises:
                        await orchestrator.store_promises(user.get("user_id"), scraper_name, promises)
                        logger.info(f"Stored {len(promises)} initial promises for civic scout {scraper_name}")
                except Exception as e:
                    logger.warning(f"Failed to store initial promises for {scraper_name}: {e}")

            # For pulse scouts, trigger initial execution to:
            # 1. Run the search and extract initial information units
            # 2. Store EXEC# record for Scouts panel status
            if payload.scout_type == "pulse":
                location_dict = payload.location.model_dump(exclude_none=True) if payload.location else None
                background_tasks.add_task(
                    execute_initial_pulse_background,
                    scraper_name,
                    user.get("user_id"),
                    location_dict,
                    payload.topic,
                    payload.criteria,
                    user.get("preferred_language", "en"),
                )
                logger.info(f"Queued initial run for pulse scout: {scraper_name}")

    except httpx.RequestError as exc:
        logger.error("Failed to connect to AWS API: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to scheduling service",
        )

    return MonitoringScheduleResponse(
        name=scraper_name,
        scout_type=payload.scout_type,
        url=payload.url,
        criteria=payload.criteria,
        channel=payload.channel,
        monitoring=payload.monitoring,
        regularity=payload.regularity,
        day_number=payload.day_number,
        time=payload.time,
        timezone=cron_schedule.timezone,
        cron_expression=cron_schedule.expression,
        metadata=cron_schedule.metadata(),
        location=payload.location,
    )


@router.post("/scrapers/monitoring/validate", response_model=ValidateCreditsResponse)
async def validate_monitoring_credits(
    payload: MonitoringValidationRequest,
    user: dict = Depends(get_current_user)
):
    """
    Validate user has sufficient credits for monitoring setup.

    Returns credit cost information or raises 402 if insufficient.
    """
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    org_id = user.get("org_id")

    # Calculate per-run cost based on scout type (platform-tiered for social, location-tiered for pulse)
    if payload.scout_type == "pulse":
        per_run_cost = get_pulse_cost(payload.source_mode, payload.has_location)
    elif payload.scout_type == "social" and payload.platform:
        per_run_cost = get_social_monitoring_cost(payload.platform)
    elif payload.scout_type == "social":
        per_run_cost = CREDIT_COSTS["social_monitoring_instagram"]  # fallback
    else:
        per_run_cost = CREDIT_COSTS["website_extraction"]

    # Calculate monthly cost based on frequency
    monthly_cost = calculate_monitoring_cost(per_run_cost, payload.regularity)

    result = await validate_credits(user_id, monthly_cost, org_id=org_id)

    return {
        "valid": True,
        "per_run_cost": per_run_cost,
        "monthly_cost": monthly_cost,
        "current_credits": result["current_credits"],
        "remaining_after": result["remaining_after"]
    }


@router.get("/scrapers/active")
async def get_active_scrapers(
    user: dict = Depends(get_current_user),
):
    """
    Fetch all active monitoring jobs from AWS for the authenticated user.
    """
    headers = _build_aws_headers(user)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.aws_api_base_url}/scheduled",
                headers=headers,
                timeout=30.0,
            )

            if response.status_code != 200:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get("error", error_detail)
                except Exception:
                    pass

                logger.error(
                    "AWS get scheduled jobs error (status %d): %s",
                    response.status_code,
                    error_detail,
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Failed to fetch active jobs: {error_detail}",
                )

            return response.json()
    except httpx.RequestError as exc:
        logger.error("Failed to connect to AWS API: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to scheduling service",
        )


@router.delete("/scrapers/active/{scraper_name}")
async def delete_active_scraper(
    scraper_name: str,
    user: dict = Depends(get_current_user),
):
    """
    Delete a specific monitoring job from AWS by scraper name.
    """
    headers = _build_aws_headers(user)

    try:
        # URL-encode the scraper name for AWS API (handles spaces, commas, colons, etc.)
        encoded_name = quote(scraper_name, safe='')
        aws_url = f"{settings.aws_api_base_url}/schedule_scraper/{encoded_name}"

        logger.info(
            "Deleting scraper '%s' (encoded: '%s') via AWS: %s",
            scraper_name,
            encoded_name,
            aws_url,
        )

        async with httpx.AsyncClient() as client:
            response = await client.delete(
                aws_url,
                headers=headers,
                timeout=30.0,
            )

            if response.status_code != 200:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get("error", error_detail)
                except Exception:
                    pass

                logger.error(
                    "AWS delete scraper error (status %d): %s",
                    response.status_code,
                    error_detail,
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Failed to delete monitoring job: {error_detail}",
                )

            aws_response = response.json()
            logger.info(
                "Successfully deleted monitoring job '%s' from AWS: %s",
                scraper_name,
                aws_response,
            )

            return aws_response
    except httpx.RequestError as exc:
        logger.error("Failed to connect to AWS API: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to scheduling service",
        )


@router.post("/scrapers/charge", response_model=CreditBalanceResponse)
async def charge_scrape_credits(
    payload: CreditChargeRequest,
    user: dict = Depends(get_current_user),
):
    """
    Deduct credits from the authenticated user for running a scrape/monitoring action.
    """
    user_id = user.get("user_id")
    org_id = user.get("org_id")

    try:
        us = UserService()
        user_data = await us.get_user(user_id)
        current_credits = user_data.get("credits", 0) if user_data else 0
    except Exception as exc:
        logger.error("Failed to load user %s for credit charge: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load user credits. Please retry shortly.",
        )

    if payload.amount > current_credits:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient credits to run this scrape.",
        )

    try:
        success = await decrement_credit(user_id, payload.amount, org_id=org_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Insufficient credits to run this scrape.",
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to deduct credits for %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update credits. Please retry.",
        )

    new_balance = current_credits - payload.amount

    logger.info(
        "Deducted %s credits from %s (new balance: %s)",
        payload.amount,
        user_id,
        new_balance,
    )

    return CreditBalanceResponse(credits=new_balance)


class RunNowRequest(BaseModel):
    """Request to manually trigger a scout execution."""
    scraper_name: str


@router.post("/scrapers/run-now", response_model=RunNowResponse)
async def run_scout_now(
    payload: RunNowRequest,
    user: dict = Depends(get_current_user),
):
    """
    Manually trigger a scout execution ("Run Now").

    Delegates to ScoutRunner.run_scout() which reads the SCRAPER# record,
    calls the appropriate internal execute endpoint, and stores a TIME# record.
    """
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")

    runner = ScoutRunner()
    result = await runner.run_scout(user_id, payload.scraper_name)

    if result.get("error") == "Scout not found":
        raise HTTPException(status_code=404, detail="Scout not found")

    return result
