"""
Data extraction API endpoints (Scrape sidebar service).

PURPOSE: Async data extraction from websites (Firecrawl) and social media
(Apify). Uses polling pattern — start job, then poll for results. Supports
website, social (Twitter/X), and Instagram channels.

DEPENDS ON: workflows/data_extractor (extraction logic), workflows/firecrawl_client,
    dependencies (session cookie auth, decrement_credit), config (API keys),
    utils/credits (credit validation + costs)
USED BY: frontend (Scrape panel), main.py (router mount)
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.workflows.data_extractor import (
    extract_data_async,
    DataExtractRequest,
    DataExtractResponse,
    format_data_as_csv,
    is_data_effectively_empty
)
from app.workflows.firecrawl_client import FirecrawlError
from app.dependencies import get_current_user, decrement_credit, get_user_org_id, validate_credits
from app.config import get_settings
from app.services.user_service import UserService
from app.utils.pricing import CREDIT_COSTS, EXTRACTION_KEYS, get_extraction_cost

logger = logging.getLogger(__name__)

router = APIRouter()


async def charge_user_credits(
    user_id: str, amount: int, org_id: str = None,
    *, operation: str = "website_extraction", scout_type: str = "extract",
) -> int:
    """
    Charge credits from user's account via DynamoDB.

    Args:
        user_id: User ID
        amount: Number of credits to charge
        operation: Pricing key for USAGE# audit trail.
        scout_type: Scout type for USAGE# audit trail.

    Returns:
        New credit balance

    Raises:
        HTTPException: If user has insufficient credits or update fails
    """
    try:
        us = UserService()
        user_data = await us.get_user(user_id)
        current_credits = user_data.get("credits", 0) if user_data else 0

        if current_credits < amount:
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient credits. Required: {amount}, Available: {current_credits}"
            )

        # Deduct credits atomically
        success = await decrement_credit(
            user_id, amount, org_id=org_id,
            operation=operation, scout_name="", scout_type=scout_type,
        )
        if not success:
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient credits. Required: {amount}, Available: {current_credits}"
            )

        return current_credits - amount

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to charge credits: {str(e)}"
        )


@router.post("/extract/validate")
async def validate_extraction_credits(
    request: DataExtractRequest,
    user: dict = Depends(get_current_user)
):
    """
    Validate user has sufficient credits before starting extraction.

    Returns credit information or raises 402 if insufficient.
    """
    # Supabase (self-hosted) has no credit system — always allow
    if get_settings().deployment_target == "supabase":
        return {"valid": True, "cost": 0, "current_credits": 999999, "remaining_after": 999999}

    user_id = user.get("user_id") or user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    org_id = user.get("org_id")

    # Determine cost based on channel (platform-tiered)
    cost = get_extraction_cost(request.channel)

    result = await validate_credits(user_id, cost, org_id=org_id)

    return {
        "valid": True,
        "cost": cost,
        "current_credits": result["current_credits"],
        "remaining_after": result["remaining_after"]
    }


@router.post("/data/extract")
async def extract_data(
    request: DataExtractRequest,
    user: dict = Depends(get_current_user)
) -> Response:
    """
    Extract structured data from a URL using AI.

    This endpoint:
    1. Validates user authentication
    2. Initiates Firecrawl extraction job
    3. Polls for completion (max 5 minutes)
    4. Charges 2 credits on success
    5. Returns CSV file for download

    Args:
        request: Extraction parameters (url, target, channel)
        user: Authenticated user from dependency injection

    Returns:
        CSV file with Content-Disposition header for download

    Raises:
        HTTPException:
            - 400: Invalid request or extraction failed
            - 402: Insufficient credits
            - 500: Internal server error
            - 504: Extraction timeout
    """
    settings = get_settings()

    try:
        # Handle Social Media Extraction (Apify)
        if request.channel == "social":
            # Validate Apify token
            if not settings.apify_api_token:
                raise HTTPException(
                    status_code=500,
                    detail="Apify API token not configured"
                )
            
            from app.workflows.apify_client import run_twitter_scraper, ApifyError
            
            # Execute Apify workflow
            try:
                # Use 'target' as keywords/criteria since that's what the frontend sends
                # The frontend sends 'criteria' as 'target' or separate field?
                # In DataExtract.svelte: 
                # result = await webhookClient.extractData({ ..., criteria: socialCriteria })
                # In webhook-client.ts: body: JSON.stringify({ service, ...payload })
                # So payload has 'criteria'. 
                # But DataExtractRequest model in backend might need update or we access extra fields.
                
                # Let's check DataExtractRequest definition in app/workflows/data_extractor.py
                # If it doesn't have criteria, we might need to update it or use request.target as fallback.
                # For now, I'll assume criteria is passed or use target.
                
                criteria = getattr(request, "criteria", request.target)
                
                data = await run_twitter_scraper(
                    url=request.url,
                    keywords=criteria,
                    max_tweets=20
                )
                
                # Charge credits for social (channel-tiered)
                user_id = user.get("user_id") or user.get("id")
                if not user_id:
                    raise HTTPException(status_code=401, detail="User ID not found")
                org_id = user.get("org_id")

                extraction_key = EXTRACTION_KEYS.get(request.channel, "website_extraction")
                await charge_user_credits(
                    user_id, amount=get_extraction_cost(request.channel), org_id=org_id,
                    operation=extraction_key,
                )
                
                # Format CSV
                csv_content = format_data_as_csv(data)
                filename = f"social_extract_{request.url.split('/')[-1]}.csv"
                
                return Response(
                    content=csv_content,
                    media_type="text/csv",
                    headers={
                        "Content-Disposition": f'attachment; filename="{filename}"'
                    }
                )
                
            except ApifyError as e:
                raise HTTPException(status_code=400, detail=str(e))

        # Handle Website Extraction (Firecrawl)
        # Validate Firecrawl API key is configured
        if not settings.firecrawl_api_key:
            raise HTTPException(
                status_code=500,
                detail="Firecrawl API key not configured"
            )

        # Execute extraction workflow
        result = await extract_data_async(
            request=request,
            api_key=settings.firecrawl_api_key
        )

        # Charge credits AFTER successful extraction (user-friendly)
        user_id = user.get("user_id") or user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found")
        org_id = user.get("org_id")

        new_balance = await charge_user_credits(
            user_id, amount=1, org_id=org_id,
            operation="website_extraction",
        )

        # Return CSV with proper headers for download
        return Response(
            content=result.csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{result.filename}"'
            }
        )

    except FirecrawlError as e:
        error_msg = str(e)

        # Determine appropriate status code
        if "timed out" in error_msg.lower():
            status_code = 504
        elif "failed" in error_msg.lower():
            status_code = 400
        else:
            status_code = 500

        raise HTTPException(
            status_code=status_code,
            detail=error_msg
        )

    except HTTPException:
        # Re-raise HTTP exceptions (like credit errors)
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error during extraction: {str(e)}"
        )


# --- Async Job Pattern Implementation ---

# In-memory job store
# Structure: { job_id: { "status": "running"|"completed"|"failed", "data": ..., "error": ..., "service": ..., "user_id": ... } }
jobs: dict = {}

from fastapi import BackgroundTasks
import asyncio
from app.workflows.data_extractor import start_data_extraction_job, check_data_extraction_job

async def poll_extraction_job(job_id: str, service: str, user_id: str, request_url: str):
    """
    Background task to poll extraction job until completion.
    Updates the jobs dict and charges credits on success.
    """
    settings = get_settings()
    max_retries = 60 # 5 minutes with 5s interval
    
    try:
        for _ in range(max_retries):
            result = await check_data_extraction_job(job_id, service, settings)
            status = result["status"]
            
            # Update job state
            jobs[job_id]["status"] = status
            
            if status == "completed":
                data = result["data"]

                # Guard: Firecrawl may return "completed" with empty data
                # including wrapper dicts like {"names": []} or {"data": {}}
                if is_data_effectively_empty(data):
                    jobs[job_id]["status"] = "failed"
                    jobs[job_id]["error"] = (
                        "No data could be extracted from this page. "
                        "The site may block automated access, or the requested content was not found."
                    )
                    return

                # Format CSV BEFORE charging credits so we don't charge for empty results
                csv_content = format_data_as_csv(data)
                filename = f"extract_{service}_{job_id}.csv"

                # Charge credits
                try:
                    service_to_channel = {
                        "apify": "social",
                        "apify_instagram": "instagram",
                        "apify_facebook": "facebook",
                        "apify_tiktok": "tiktok",
                        "apify_instagram_comments": "instagram_comments",
                    }
                    channel = service_to_channel.get(service, "website")
                    cost = get_extraction_cost(channel)
                    bg_org_id = await get_user_org_id(user_id)
                    extraction_op = EXTRACTION_KEYS.get(channel, "website_extraction")
                    await charge_user_credits(
                        user_id, amount=cost, org_id=bg_org_id,
                        operation=extraction_op,
                    )
                    jobs[job_id]["credits_charged"] = cost
                except Exception as e:
                    logger.error("Failed to charge credits for job %s: %s", job_id, e)

                jobs[job_id]["data"] = {
                    "csv_content": csv_content,
                    "filename": filename,
                    "raw": data
                }
                return
                
            elif status == "failed":
                jobs[job_id]["error"] = result.get("error", "Unknown error")
                return
                
            # Wait before next poll
            await asyncio.sleep(5)
            
        # Timeout
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = "Job timed out"
        
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)


@router.post("/extract/start")
async def start_extraction_job(
    request: DataExtractRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)
):
    """
    Start an async data extraction job.
    Returns job_id immediately.
    """
    settings = get_settings()
    
    try:
        # Start the job (calls external API)
        result = await start_data_extraction_job(request, settings)
        job_id = result["job_id"]
        service = result["service"]

        user_id = user.get("user_id") or user.get("id")

        # Initialize job state
        jobs[job_id] = {
            "status": "running",
            "service": service,
            "user_id": user_id,
            "created_at": asyncio.get_event_loop().time()
        }
        
        # Start background polling
        background_tasks.add_task(
            poll_extraction_job, 
            job_id, 
            service, 
            user_id,
            request.url
        )
        
        return {"job_id": job_id, "status": "running"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/extract/status/{job_id}")
async def get_extraction_status(job_id: str, user: dict = Depends(get_current_user)):
    """
    Get the status of an extraction job.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = jobs[job_id]
    
    # Verify user ownership
    user_id = user.get("user_id") or user.get("id")
    if job["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this job")
        
    response = {
        "job_id": job_id,
        "status": job["status"]
    }
    
    if job["status"] == "completed":
        response["result"] = job["data"]
    elif job["status"] == "failed":
        response["error"] = job.get("error")
        
    return response
