"""
Apify Client for executing actors and retrieving results.

PURPOSE: Start, poll, and retrieve results from Apify actors for social
media scraping (Twitter/X and Instagram). Provides both async-start/poll
and synchronous run-and-wait interfaces.

DEPENDS ON: config (get_settings for APIFY_API_TOKEN)
USED BY: workflows/data_extractor.py (via lazy imports)
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

class ApifyError(Exception):
    """Base exception for Apify errors."""
    pass

APIFY_STATUS_MAP = {
    "READY": "running",
    "RUNNING": "running",
    "SUCCEEDED": "completed",
    "FAILED": "failed",
    "ABORTED": "failed",
    "TIMED-OUT": "failed",
}

class ApifyClient:
    """
    Client for interacting with Apify API.
    """
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.apify.com/v2"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

    async def start_actor_run(
        self, 
        actor_id: str, 
        run_input: Dict[str, Any],
        memory_mbytes: Optional[int] = None,
        timeout_secs: Optional[int] = None
    ) -> str:
        """
        Start an actor run and return the run ID.
        """
        url = f"{self.base_url}/acts/{actor_id}/runs"
        params = {}
        if memory_mbytes:
            params["memory"] = memory_mbytes
        if timeout_secs:
            params["timeout"] = timeout_secs

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url, 
                    headers=self.headers, 
                    json=run_input,
                    params=params
                )
                response.raise_for_status()
                data = response.json()
                return data["data"]["id"]
            except httpx.HTTPStatusError as e:
                logger.error(f"Apify API error: {e.response.text}")
                raise ApifyError(f"Failed to start actor: {e.response.text}")
            except Exception as e:
                logger.error(f"Unexpected error starting Apify actor: {str(e)}")
                raise ApifyError(f"Unexpected error: {str(e)}")

    async def get_run(self, run_id: str) -> Dict[str, Any]:
        """
        Get information about a specific run.
        """
        url = f"{self.base_url}/actor-runs/{run_id}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()["data"]
            except Exception as e:
                raise ApifyError(f"Failed to get run info: {str(e)}")

    async def get_dataset_items(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Get items from a dataset.
        """
        url = f"{self.base_url}/datasets/{dataset_id}/items"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                raise ApifyError(f"Failed to get dataset items: {str(e)}")

    async def poll_run(self, run_id: str, interval_secs: int = 5) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Poll a run until it finishes. Yields status updates.
        """
        while True:
            run_info = await self.get_run(run_id)
            status = run_info["status"]
            
            yield {
                "status": status,
                "run_info": run_info
            }

            if status in ["SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"]:
                break
            
            await asyncio.sleep(interval_secs)

async def start_twitter_scraper_async(
    url: str, 
    keywords: Optional[str] = None,
    max_tweets: int = 20
) -> str:
    """
    Start the Twitter scraper actor asynchronously.
    Returns the run ID.
    """
    settings = get_settings()
    if not settings.apify_api_token:
        raise ApifyError("APIFY_API_TOKEN not configured")

    client = ApifyClient(settings.apify_api_token)
    
    # Actor ID provided by user
    actor_id = "61RPP7dywgiy0JPD0"

    # Actor expects simple arrays of strings and maxItems limiter.
    capped_max = min(max_tweets, 100)
    run_input = {
        "startUrls": [url],
        "maxItems": capped_max,
    }

    # Provide search terms when keywords are supplied (comma separated).
    if keywords:
        terms = [k.strip() for k in keywords.split(",") if k.strip()]
        if terms:
            run_input["searchTerms"] = terms

    # If scraping a single conversation, include the ID so the actor doesn't expand unnecessarily.
    if "/status/" in url:
        try:
            conversation_id = url.split("/status/")[1].split("/")[0]
            if conversation_id:
                run_input["conversationIds"] = [conversation_id]
        except Exception:
            pass

    # For profile URLs, also pass the handle so the actor keeps scope tight.
    # Example: https://x.com/buriedsignals -> buriedsignals
    try:
        parts = url.rstrip("/").split("/")
        handle = None
        if "status" in parts:
            status_idx = parts.index("status")
            if status_idx > 0:
                handle = parts[status_idx - 1]
        elif parts:
            handle = parts[-1]

        if handle and handle not in {"status", ""}:
            run_input["twitterHandles"] = [handle]
    except Exception:
        # Non-fatal; the actor can still use the start URL alone.
        pass

    run_id = await client.start_actor_run(actor_id, run_input)
    logger.info(f"Started Apify run {run_id} for URL {url}")
    return run_id


async def check_twitter_scraper_status(run_id: str) -> Dict[str, Any]:
    """
    Check the status of a Twitter scraper run.
    Returns dict with status and data (if completed).
    """
    settings = get_settings()
    if not settings.apify_api_token:
        raise ApifyError("APIFY_API_TOKEN not configured")

    client = ApifyClient(settings.apify_api_token)
    
    run_info = await client.get_run(run_id)
    status = run_info["status"]
    normalized_status = APIFY_STATUS_MAP.get(status, "running")

    result = {
        "status": status,
        "normalized_status": normalized_status,
        "data": None,
        "error": None,
    }

    if status == "SUCCEEDED":
        dataset_id = run_info["defaultDatasetId"]
        items = await client.get_dataset_items(dataset_id)
        result["data"] = items
    elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
        result["error"] = f"Run failed with status: {status}"

    return result

async def run_twitter_scraper(
    url: str,
    keywords: Optional[str] = None,
    max_tweets: int = 20
) -> List[Dict[str, Any]]:
    """
    Run the Twitter scraper actor (Legacy synchronous method).
    """
    # ... existing implementation ...
    # Re-implement using the async methods to avoid duplication if desired,
    # but for now keeping as is or wrapping is fine.
    # Let's keep the original implementation for backward compatibility if needed,
    # or better yet, use the new methods.

    run_id = await start_twitter_scraper_async(url, keywords, max_tweets)

    settings = get_settings()
    client = ApifyClient(settings.apify_api_token)

    # Poll for completion
    dataset_id = None
    async for update in client.poll_run(run_id):
        status = update["status"]
        logger.debug(f"Apify run {run_id} status: {status}")

        if status == "SUCCEEDED":
            dataset_id = update["run_info"]["defaultDatasetId"]
        elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
            raise ApifyError(f"Apify run failed with status: {status}")

    if not dataset_id:
        raise ApifyError("Run succeeded but no dataset ID found")

    # Fetch results
    items = await client.get_dataset_items(dataset_id)
    return items


async def start_instagram_scraper_async(
    url: str,
    max_items: int = 100
) -> str:
    """
    Start the Instagram scraper actor asynchronously.
    Returns the run ID.
    """
    settings = get_settings()
    if not settings.apify_api_token:
        raise ApifyError("APIFY_API_TOKEN not configured")

    client = ApifyClient(settings.apify_api_token)

    # Actor ID: apidojo/instagram-scraper
    actor_id = "culc72xb7MP3EbaeX"

    run_input = {
        "startUrls": [url],
        "maxItems": min(max_items, 100),  # Cap at 100
    }

    run_id = await client.start_actor_run(actor_id, run_input)
    logger.info(f"Started Apify Instagram run {run_id} for URL {url}")
    return run_id


async def check_instagram_scraper_status(run_id: str) -> Dict[str, Any]:
    """
    Check the status of an Instagram scraper run.
    Returns dict with status and data (if completed).
    """
    settings = get_settings()
    if not settings.apify_api_token:
        raise ApifyError("APIFY_API_TOKEN not configured")

    client = ApifyClient(settings.apify_api_token)

    run_info = await client.get_run(run_id)
    status = run_info["status"]
    normalized_status = APIFY_STATUS_MAP.get(status, "running")

    result = {
        "status": status,
        "normalized_status": normalized_status,
        "data": None,
        "error": None,
    }

    if status == "SUCCEEDED":
        dataset_id = run_info["defaultDatasetId"]
        items = await client.get_dataset_items(dataset_id)
        result["data"] = items
    elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
        result["error"] = f"Run failed with status: {status}"

    return result


# --- Facebook Profile Posts ---

FACEBOOK_ACTOR_ID = "cleansyntax~facebook-profile-posts-scraper"


async def start_facebook_scraper_async(
    url: str,
    max_items: int = 100
) -> str:
    """
    Start the Facebook profile posts scraper actor asynchronously.
    Uses cleansyntax/facebook-profile-posts-scraper which supports
    both pages and profiles via profile URL.
    Returns the run ID.
    """
    settings = get_settings()
    if not settings.apify_api_token:
        raise ApifyError("APIFY_API_TOKEN not configured")

    client = ApifyClient(settings.apify_api_token)

    run_input = {
        "endpoint": "profile_posts_by_url",
        "urls_text": url,
        "max_posts": min(max_items, 100),
    }

    run_id = await client.start_actor_run(FACEBOOK_ACTOR_ID, run_input)
    logger.info(f"Started Apify Facebook run {run_id} for URL {url}")
    return run_id


async def check_facebook_scraper_status(run_id: str) -> Dict[str, Any]:
    """
    Check the status of a Facebook scraper run.
    Returns dict with status and data (if completed).
    """
    settings = get_settings()
    if not settings.apify_api_token:
        raise ApifyError("APIFY_API_TOKEN not configured")

    client = ApifyClient(settings.apify_api_token)

    run_info = await client.get_run(run_id)
    status = run_info["status"]
    normalized_status = APIFY_STATUS_MAP.get(status, "running")

    result = {
        "status": status,
        "normalized_status": normalized_status,
        "data": None,
        "error": None,
    }

    if status == "SUCCEEDED":
        dataset_id = run_info["defaultDatasetId"]
        items = await client.get_dataset_items(dataset_id)
        result["data"] = items
    elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
        result["error"] = f"Run failed with status: {status}"

    return result


# --- TikTok Profile Videos ---

TIKTOK_ACTOR_ID = "novi~tiktok-user-api"


async def start_tiktok_scraper_async(
    url: str,
    max_items: int = 20
) -> str:
    """
    Start the TikTok profile videos scraper actor asynchronously.
    Uses novi/tiktok-user-api which scrapes a user's recent videos.
    Returns the run ID.
    """
    settings = get_settings()
    if not settings.apify_api_token:
        raise ApifyError("APIFY_API_TOKEN not configured")

    client = ApifyClient(settings.apify_api_token)

    run_input = {
        "urls": [url],
        "limit": min(max_items, 100),
    }

    run_id = await client.start_actor_run(TIKTOK_ACTOR_ID, run_input)
    logger.info(f"Started Apify TikTok run {run_id} for URL {url}")
    return run_id


async def check_tiktok_scraper_status(run_id: str) -> Dict[str, Any]:
    """
    Check the status of a TikTok scraper run.
    Returns dict with status and data (if completed).
    """
    settings = get_settings()
    if not settings.apify_api_token:
        raise ApifyError("APIFY_API_TOKEN not configured")

    client = ApifyClient(settings.apify_api_token)

    run_info = await client.get_run(run_id)
    status = run_info["status"]
    normalized_status = APIFY_STATUS_MAP.get(status, "running")

    result = {
        "status": status,
        "normalized_status": normalized_status,
        "data": None,
        "error": None,
    }

    if status == "SUCCEEDED":
        dataset_id = run_info["defaultDatasetId"]
        items = await client.get_dataset_items(dataset_id)
        result["data"] = items
    elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
        result["error"] = f"Run failed with status: {status}"

    return result


# --- Instagram Comments ---

INSTAGRAM_COMMENTS_ACTOR_ID = "apify~instagram-comment-scraper"


async def start_instagram_comments_async(
    url: str,
    max_items: int = 50
) -> str:
    """
    Start the Instagram comments scraper actor asynchronously.
    Accepts a post URL (e.g., https://www.instagram.com/p/ABC123/).
    Returns the run ID.

    Reduced from 200 to 50 items for cost control ($0.0023/comment).
    """
    settings = get_settings()
    if not settings.apify_api_token:
        raise ApifyError("APIFY_API_TOKEN not configured")

    client = ApifyClient(settings.apify_api_token)

    run_input = {
        "directUrls": [url],
        "resultsLimit": min(max_items, 500),
    }

    run_id = await client.start_actor_run(INSTAGRAM_COMMENTS_ACTOR_ID, run_input)
    logger.info(f"Started Apify Instagram Comments run {run_id} for URL {url}")
    return run_id


async def check_instagram_comments_status(run_id: str) -> Dict[str, Any]:
    """
    Check the status of an Instagram comments scraper run.
    Returns dict with status and data (if completed).
    """
    settings = get_settings()
    if not settings.apify_api_token:
        raise ApifyError("APIFY_API_TOKEN not configured")

    client = ApifyClient(settings.apify_api_token)

    run_info = await client.get_run(run_id)
    status = run_info["status"]
    normalized_status = APIFY_STATUS_MAP.get(status, "running")

    result = {
        "status": status,
        "normalized_status": normalized_status,
        "data": None,
        "error": None,
    }

    if status == "SUCCEEDED":
        dataset_id = run_info["defaultDatasetId"]
        items = await client.get_dataset_items(dataset_id)
        result["data"] = items
    elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
        result["error"] = f"Run failed with status: {status}"

    return result
