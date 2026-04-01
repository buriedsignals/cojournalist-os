"""
Civic Scout router.

PURPOSE: Three endpoints for civic (council website) monitoring:
- POST /civic/discover (session auth, rate limited 3/hour) — crawl a council
  website and return AI-ranked candidate URLs.
- POST /civic/execute (service key auth) — full civic scout execution
  (fetch pages, detect new PDFs, extract promises, notify, store records).
- POST /civic/notify-promises (service key auth) — send a digest email for
  mature promises found by the promise-checker Lambda.

DEPENDS ON: dependencies (auth), schemas/civic, services/civic_orchestrator,
    services/execution_deduplication, services/notification_service, utils/credits
USED BY: frontend (Civic Scout panel), Lambda (scheduled execution,
    promise-checker), main.py (router mount)
"""
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.dependencies import (
    decrement_credit,
    get_current_user,
    get_user_email,
    verify_service_key,
    validate_credits,
)
from app.schemas.civic import (
    CivicDiscoverRequest,
    CivicDiscoverResponse,
    CivicExecuteRequest,
    CivicExecuteResult,
    CivicTestRequest,
    CivicTestResponse,
)
from app.config import get_settings
from app.services.civic_orchestrator import CivicOrchestrator
from app.services.execution_deduplication import ExecutionDeduplicationService
from app.services.notification_service import NotificationService
from app.utils.pricing import CREDIT_COSTS

logger = logging.getLogger(__name__)

# Rate limiter for expensive crawl operations
limiter = Limiter(key_func=get_remote_address)

# Initialize notification service
notification_service = NotificationService()

router = APIRouter(prefix="/civic", tags=["Civic"])


# ---------------------------------------------------------------------------
# POST /civic/discover — session auth, rate limited 3/hour
# ---------------------------------------------------------------------------


@router.post("/discover", response_model=CivicDiscoverResponse)
@limiter.limit("3/hour")
async def discover_civic_urls(
    request: Request,
    body: CivicDiscoverRequest,
    user: dict = Depends(get_current_user),
):
    """Crawl a council website and return AI-ranked candidate URLs.

    Rate limited to 3 requests/hour (Firecrawl crawl is expensive).
    Validates credits before running the crawl.
    """
    user_id = user["user_id"]
    org_id = user.get("org_id")
    settings = get_settings()

    # Civic Scout requires Pro tier (skip for self-hosted Supabase — no tiers)
    if settings.deployment_target != "supabase" and user.get("tier", "free") == "free":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Track the Council requires a Pro plan.",
        )

    cost = CREDIT_COSTS["civic_discover"]

    # Validate credits (raises 402 if insufficient); skip for Supabase
    if settings.deployment_target != "supabase":
        await validate_credits(user_id, cost, org_id=org_id)

    try:
        orchestrator = CivicOrchestrator()
        candidates = await orchestrator.discover(body.root_domain)
    except Exception as e:
        logger.exception("Civic discover failed for %s: %s", body.root_domain, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Discovery failed. Please try again.",
        )

    # Decrement credits after successful discovery
    try:
        await decrement_credit(
            user_id, cost, org_id=org_id,
            operation="civic_discover", scout_name=body.root_domain,
            scout_type="civic",
        )
    except Exception as e:
        logger.error("Failed to decrement credits for %s: %s", user_id, e)

    return CivicDiscoverResponse(candidates=candidates)


# ---------------------------------------------------------------------------
# POST /civic/test — session auth, rate limited 3/hour
# ---------------------------------------------------------------------------


@router.post("/test", response_model=CivicTestResponse)
@limiter.limit("3/hour")
async def test_civic_extraction(
    request: Request,
    body: CivicTestRequest,
    user: dict = Depends(get_current_user),
):
    """Test extraction on selected council URLs before scheduling a scout.

    Rate limited to 3 requests/hour (downloads and parses documents).
    Validates credits before running extraction.
    """
    user_id = user["user_id"]
    org_id = user.get("org_id")
    settings = get_settings()

    # Civic Scout requires Pro tier (skip for self-hosted Supabase — no tiers)
    if settings.deployment_target != "supabase" and user.get("tier", "free") == "free":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Track the Council requires a Pro plan.",
        )

    cost = CREDIT_COSTS["civic_discover"]

    # Validate credits (raises 402 if insufficient); skip for Supabase
    if settings.deployment_target != "supabase":
        await validate_credits(user_id, cost, org_id=org_id)

    try:
        orchestrator = CivicOrchestrator()
        promises, documents_found = await orchestrator.test(
            body.tracked_urls, body.criteria
        )
    except Exception as e:
        logger.exception("Civic test failed for %s: %s", user_id, e)
        return CivicTestResponse(
            valid=False,
            documents_found=0,
            sample_promises=[],
            error="Extraction failed. Please try again.",
        )

    return CivicTestResponse(
        valid=True,
        documents_found=documents_found,
        sample_promises=promises,
    )


# ---------------------------------------------------------------------------
# POST /civic/execute — service key auth (Lambda calls this)
# ---------------------------------------------------------------------------


@router.post("/execute", response_model=CivicExecuteResult)
async def execute_civic_scout(
    payload: CivicExecuteRequest,
    _: None = Depends(verify_service_key),
):
    """Execute a civic scout: fetch pages, detect new PDFs, extract promises, notify.

    Called by Lambda on schedule. Uses ExecutionDeduplicationService to
    avoid duplicate notifications when page content has not changed.
    """
    user_id = payload.user_id
    scraper_name = payload.scraper_name
    started_at = datetime.utcnow().isoformat() + "Z"

    try:
        orchestrator = CivicOrchestrator()
        result = await orchestrator.execute(payload)
    except Exception as e:
        logger.exception("Civic execute failed for %s/%s: %s", user_id, scraper_name, e)
        return CivicExecuteResult(
            status="error",
            summary=f"Execution error: {str(e)}",
            promises_found=0,
            new_pdf_urls=[],
            is_duplicate=False,
        )

    # Store EXEC# record via deduplication service
    try:
        exec_dedup = ExecutionDeduplicationService()
        await exec_dedup.store_execution(
            user_id=user_id,
            scout_name=scraper_name,
            scout_type="civic",
            summary_text=result.summary[:150],
            is_duplicate=result.is_duplicate,
            started_at=started_at,
        )
    except Exception as e:
        logger.error("Failed to store EXEC# record for %s/%s: %s", user_id, scraper_name, e)

    # Send notification when new promises were found
    if not result.is_duplicate and result.promises_found > 0:
        try:
            user_email = await get_user_email(user_id)
            if user_email:
                blocks = [f"## {result.promises_found} New Promise(s) Found"]
                for p in result.promises:
                    block = [f"### {p.promise_text}"]
                    if p.context:
                        block.append(p.context)
                    if p.due_date:
                        block.append(f"**Due:** {p.due_date}")
                    if p.source_url:
                        block.append(f"[View source document]({p.source_url})")
                    blocks.append("\n".join(block))
                summary_md = "\n\n".join(blocks)
                await notification_service.send_civic_alert(
                    to_email=user_email,
                    scout_name=scraper_name,
                    summary=summary_md,
                    language=payload.language,
                )
        except Exception as e:
            logger.error(
                "Failed to send civic notification for %s/%s: %s",
                user_id,
                scraper_name,
                e,
            )

    return result


# ---------------------------------------------------------------------------
# POST /civic/notify-promises — service key auth (promise-checker Lambda)
# ---------------------------------------------------------------------------


@router.post("/notify-promises")
async def notify_civic_promises(
    payload: dict[str, Any],
    _: None = Depends(verify_service_key),
):
    """Send a digest email for promises surfaced by the promise-checker Lambda.

    Expects JSON body:
      {
        "user_id": "<str>",
        "scraper_name": "<str>",
        "promises": [{"promise_text": "...", "due_date": "...", ...}, ...]
        "language": "<str>  (optional, default 'en')"
      }

    Fetches user email, builds a markdown digest, sends notification,
    and returns a status dict.
    """
    user_id = payload.get("user_id")
    scraper_name = payload.get("scraper_name", "Civic Scout")
    promises: list[dict] = payload.get("promises", [])
    language: str = payload.get("language", "en")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="user_id is required",
        )

    if not promises:
        logger.info("notify-promises: no promises for %s/%s — skipping", user_id, scraper_name)
        return {"notification_sent": False, "reason": "no_promises"}

    # Fetch user email
    user_email = await get_user_email(user_id)
    if not user_email:
        logger.warning(
            "notify-promises: could not fetch email for %s — skipping", user_id
        )
        return {"notification_sent": False, "reason": "no_email"}

    # Build accountability-framed digest
    blocks = [
        "## Promises Due for Review",
        "The following commitments are approaching their stated deadline. "
        "Follow up to verify whether they have been delivered.",
    ]
    for p in promises:
        text = p.get("promise_text", "")
        due = p.get("due_date", "")
        source = p.get("source_url", "")
        block = [f"### {text}"]
        if due:
            block.append(f"**Deadline:** {due}")
        if source:
            block.append(f"[View source document]({source})")
        blocks.append("\n".join(block))

    digest_markdown = "\n\n".join(blocks)

    # Send notification
    try:
        sent = await notification_service.send_civic_alert(
            to_email=user_email,
            scout_name=scraper_name,
            summary=digest_markdown,
            language=language,
        )
    except Exception as e:
        logger.error(
            "notify-promises: notification failed for %s/%s: %s",
            user_id,
            scraper_name,
            e,
        )
        return {"notification_sent": False, "reason": "send_error"}

    # Update PROMISE# status to "notified" in storage
    try:
        promise_ids = [p.get("promise_id") for p in promises if p.get("promise_id")]
        if promise_ids:
            orchestrator = CivicOrchestrator()
            await orchestrator.mark_promises_notified(user_id, scraper_name, promise_ids)
    except Exception as e:
        logger.error(
            "notify-promises: failed to update promise status for %s/%s: %s",
            user_id,
            scraper_name,
            e,
        )

    return {"notification_sent": sent, "promises_count": len(promises)}
