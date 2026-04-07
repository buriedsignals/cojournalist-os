"""
Pulse API router — Smart Scout (type pulse) endpoints.

PURPOSE: Two main endpoints:
- POST /pulse/search (UI): Rate-limited search for preview, returns articles.
  Auth: session cookie.
- POST /pulse/execute (Lambda): Scheduled execution with full pipeline
  (dedup, fact extraction, notification). Auth: X-Service-Key.

DEPENDS ON: dependencies (auth, credits), services/pulse_orchestrator,
    services/notification_service, services/execute_pipeline,
    schemas/pulse, schemas/common, utils/logging
USED BY: frontend (Smart Scout panel), Lambda (scheduled execution),
    main.py (router mount)
"""
import asyncio
import logging
import os
import time
from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.dependencies import get_current_user, get_user_email, get_user_org_id, verify_service_key, verify_scraper_key
from app.services.user_service import UserService
from app.models.modes import ScoutMode
from app.services.pulse_orchestrator import PulseOrchestrator
from app.services.notification_service import NotificationService, group_facts_by_source
from app.services.execute_pipeline import (
    fetch_recent_facts,
    run_post_orchestrator_pipeline,
    PipelineContext,
)
from app.schemas.pulse import (
    PulseSearchRequest,
    PulseSearchResponse,
    PulseExecuteRequest,
    PulseExecuteResponse,
)
from app.schemas.common import AINewsArticle
from app.utils.pricing import get_pulse_cost
from app.utils.logging import log_scout_execution

logger = logging.getLogger(__name__)

# Initialize services
notification_service = NotificationService()

# Rate limiter for expensive AI operations
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/pulse", tags=["Pulse"])


# =============================================================================
# UI-Triggered Search Endpoint
# =============================================================================

@router.post("/search", response_model=PulseSearchResponse)
@limiter.limit("10/minute")
async def search_pulse(
    request: Request,
    search_request: PulseSearchRequest,
    user: dict = Depends(get_current_user)
):
    """
    AI-orchestrated news pulse search.

    Returns curated local news articles for the specified location.
    Takes 30-60 seconds for AI to search, scrape, and curate.
    """
    location_display = search_request.location.displayName if search_request.location else None
    logger.info(f"[Pulse] Search - location: {location_display}, criteria: {search_request.criteria}, category: {search_request.category}")

    # Extract location parts (guarded for None)
    city = search_request.location.city or "" if search_request.location else ""
    country = search_request.location.country if search_request.location else None
    location_str = location_display or ""

    if search_request.location and not city and not country:
        raise HTTPException(status_code=400, detail="Location must include at least a country")

    try:
        # Initialize AI orchestrator
        orchestrator = PulseOrchestrator()

        # Merge request-level + user-level excluded domains (order-preserving dedup)
        user_excluded = user.get("excluded_domains") or []
        request_excluded = search_request.excluded_domains or []
        merged_excluded = list(dict.fromkeys(user_excluded + request_excluded))

        # Execute AI-orchestrated search (pulse mode)
        result = await orchestrator.search_news(
            location=location_str or None,
            city=city or None,
            country=country,
            category=search_request.category,
            custom_filter_prompt=search_request.custom_filter_prompt,
            language=user.get("preferred_language", "en"),
            excluded_domains=merged_excluded,
            source_mode=search_request.source_mode,
            criteria=search_request.criteria,
            exclude_urls=search_request.exclude_urls,
            priority_sources=search_request.priority_sources,
        )

        logger.info(
            f"[Pulse] Search completed - "
            f"status: {result.status}, "
            f"articles: {len(result.articles)}, "
            f"queries: {len(result.search_queries_used)}, "
            f"scraped: {len(result.urls_scraped)}, "
            f"time: {result.processing_time_ms}ms"
        )

        # NOTE: UI search is preview-only - no unit storage here.
        # Units are stored when the scout is scheduled and executed via /execute endpoint.

        # Convert to response model
        return PulseSearchResponse(
            status=result.status,
            mode=ScoutMode.PULSE,
            category=result.category,
            task_completed=result.task_completed,
            response_markdown=result.response_markdown,
            articles=[
                AINewsArticle(
                    title=a.title,
                    url=a.url,
                    source=a.source,
                    summary=a.summary,
                    date=a.date,
                    imageUrl=a.imageUrl,
                    verified=a.verified
                )
                for a in result.articles
            ],
            totalResults=result.total_results,
            search_queries_used=result.search_queries_used,
            urls_scraped=result.urls_scraped,
            processing_time_ms=result.processing_time_ms,
            summary=result.summary,
            filteredOutCount=result.filtered_out_count,
        )

    except Exception as e:
        logger.error(f"[Pulse] Search failed: {e}", exc_info=True)
        return PulseSearchResponse(
            status="failed",
            mode=ScoutMode.PULSE,
            category=search_request.category,
            task_completed=False,
            response_markdown="Search failed. Please try again.",
            articles=[],
            totalResults=0,
            search_queries_used=[],
            urls_scraped=[],
            processing_time_ms=0,
            summary="",
            error="Internal error"
        )


# =============================================================================
# Lambda-Triggered Execution Endpoint
# =============================================================================

@router.post("/execute", response_model=PulseExecuteResponse)
async def execute_pulse_scout(
    request: PulseExecuteRequest,
    _: None = Depends(verify_scraper_key)
):
    """
    Execute Pulse scout.

    Called by AWS Lambda on schedule.
    ALWAYS sends notification regardless of results.
    """
    start_time = time.time()

    # Get user email from DynamoDB (notification will be skipped if unavailable)
    user_email = await get_user_email(request.userId)
    if not user_email:
        logger.warning(f"Could not fetch email for user {request.userId}, notification will be skipped")

    # Suppress notification on initial run (first run from UI scheduling)
    if request.skip_notification:
        logger.info(f"Skipping notification for {request.scraperName} (initial run)")
        user_email = None

    try:
        location_display = request.location.displayName if request.location else None
        scope_label = location_display or request.topic or "Unknown"
        logger.info(f"Pulse scout for {scope_label}")

        # Fetch recent facts and build recent_findings for orchestrator prompt injection
        recent_facts, recent_findings = await fetch_recent_facts(
            user_id=request.userId,
            scout_id=request.scraperName,
            scout_type="pulse",
        )

        # Fetch user data from DynamoDB (no JWT for service-key auth)
        excluded_domains = []
        org_id = None
        try:
            us = UserService()
            user_data = await us.get_user(request.userId)
            excluded_domains = (user_data.get("excluded_domains") or []) if user_data else []
            org_id = user_data.get("org_id") if user_data else None
        except Exception as exc:
            logger.warning(f"Could not fetch user data for {request.userId}: {exc}")

        # Merge per-scout + user-level excluded domains
        scout_excluded = request.excluded_domains or []
        merged_excluded = list(dict.fromkeys(excluded_domains + scout_excluded))

        # Search local news using orchestrator (both categories in parallel)
        orchestrator = PulseOrchestrator()
        shared_kwargs = dict(
            location=location_display,
            city=request.location.city if request.location else None,
            country=request.location.country if request.location else None,
            recent_findings=recent_findings,
            language=request.preferred_language,
            excluded_domains=merged_excluded,
            source_mode=request.source_mode,
            criteria=request.criteria,
            priority_sources=request.priority_sources,
        )

        # Niche + location (no criteria): skip government — institutional
        # content contradicts niche promise of community/indie sources
        is_niche_location = (
            request.source_mode == "niche"
            and request.location
            and not request.criteria
        )

        if is_niche_location:
            (news_result,) = await asyncio.gather(
                orchestrator.search_news(**shared_kwargs, category="news"),
                return_exceptions=True,
            )
            gov_result = None
        else:
            news_result, gov_result = await asyncio.gather(
                orchestrator.search_news(**shared_kwargs, category="news"),
                orchestrator.search_news(**shared_kwargs, category="government"),
                return_exceptions=True,
            )

        # Handle partial failures
        if isinstance(news_result, Exception):
            logger.error(f"[Pulse] News category failed: {news_result}")
            news_result = None
        if isinstance(gov_result, Exception):
            logger.error(f"[Pulse] Government category failed: {gov_result}")
            gov_result = None

        # Extract news articles
        news_articles = [a.model_dump() for a in news_result.articles] if news_result and news_result.articles else []
        news_urls = {a.get("url") for a in news_articles}

        # Extract gov articles (exclude any URLs already in news)
        gov_articles_raw = [a.model_dump() for a in gov_result.articles] if gov_result and gov_result.articles else []
        gov_urls = {a.get("url") for a in gov_articles_raw} - news_urls

        # Cross-category deduplication (embedding-based)
        if news_articles and gov_articles_raw:
            from app.services.news_utils import cross_category_dedup
            news_articles, gov_articles_raw = await cross_category_dedup(
                news_articles, gov_articles_raw,
            )
            # Recompute URL sets after cross-category dedup
            news_urls = {a.get("url") for a in news_articles}
            gov_urls = {a.get("url") for a in gov_articles_raw} - news_urls

        # Combined for fact processing
        all_articles = news_articles + [a for a in gov_articles_raw if a.get("url") in gov_urls]

        # Summaries
        summary = (news_result.summary if news_result else "") or ""
        gov_summary = (gov_result.summary if gov_result else "") or ""

        # If no summary generated, create a basic one
        if not summary and all_articles:
            summary = f"Found {len(all_articles)} news articles for {scope_label}."
        elif not summary:
            summary = f"No recent news found for {scope_label}."

        articles_count = len(news_articles) + len(gov_articles_raw)

        # Pulse-specific notification callback
        async def send_notification(processing_result, exec_summary, email):
            if not processing_result.new_facts:
                logger.info(f"No new facts for {request.scraperName} - skipping notification")
                return False
            if not email:
                logger.warning(f"Skipping notification for {request.scraperName} - no email available")
                return False

            # Split new_facts into news vs gov by source_url
            news_new_facts = [f for f in processing_result.new_facts if f.get("source_url") in news_urls]
            gov_new_facts = [f for f in processing_result.new_facts if f.get("source_url") in gov_urls]

            # Group facts by source for both sections
            notification_articles = group_facts_by_source(news_new_facts, source_limit=5)
            gov_notification_articles = group_facts_by_source(gov_new_facts, source_limit=5) if gov_new_facts else []

            return await notification_service.send_pulse_alert(
                to_email=email,
                scout_name=request.scraperName,
                location=location_display,
                summary=summary,
                articles=notification_articles,
                topic=request.topic,
                language=request.preferred_language,
                gov_articles=gov_notification_articles,
                gov_summary=gov_summary,
            )

        # Run shared post-orchestrator pipeline
        ctx = PipelineContext(
            user_id=request.userId,
            scraper_name=request.scraperName,
            scout_type="pulse",
            location=request.location,
            topic=request.topic,
            preferred_language=request.preferred_language,
            start_time=start_time,
            credit_cost=get_pulse_cost(request.source_mode, request.location is not None),
            skip_credit_charge=request.skip_credit_charge,
            skip_unit_extraction=request.skip_unit_extraction,
            team_org_id=org_id,
        )
        pipeline_result = await run_post_orchestrator_pipeline(
            articles=all_articles,
            ctx=ctx,
            recent_facts=recent_facts,
            user_email=user_email,
            send_notification=send_notification,
            extra_log_fields={"articles_count": articles_count},
        )

        return PulseExecuteResponse(
            scraper_status=True,
            criteria_status=not pipeline_result.all_duplicates,
            summary=summary,
            articles_count=articles_count,
            notification_sent=pipeline_result.notification_sent,
        )

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.exception(f"Pulse scout failed: {e}")

        log_scout_execution(
            scout_type="pulse",
            user_id=request.userId,
            scraper_name=request.scraperName,
            status="error",
            duration_ms=duration_ms,
            extra={"error": str(e)}
        )

        return PulseExecuteResponse(
            scraper_status=False,
            criteria_status=False,
            summary="An error occurred while processing the Smart Scout",
            articles_count=0,
            notification_sent=False
        )


# =============================================================================
# Health Check Endpoint
# =============================================================================

@router.get("/health")
async def pulse_health_check():
    """Health check endpoint for pulse service."""
    try:
        orchestrator = PulseOrchestrator()
        return {
            "status": "healthy",
            "service": "pulse",
            "firecrawl_configured": bool(orchestrator.firecrawl_key),
            "openrouter_configured": bool(orchestrator.openrouter_key)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "pulse",
            "error": str(e)
        }
