"""
Data extraction workflow using Firecrawl and Apify APIs.

PURPOSE: Orchestrates async data extraction jobs — start extraction,
poll for completion, normalize results (Apify tweets/Instagram posts),
and format as CSV. Supports three channels: website (Firecrawl),
social/Twitter (Apify), and Instagram (Apify).

DEPENDS ON: workflows/firecrawl_client (FirecrawlClient, FirecrawlError),
    workflows/apify_client (Twitter/Instagram scrapers)
USED BY: routers/data_extractor.py
"""

import csv
import io
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field

from .firecrawl_client import FirecrawlClient, FirecrawlError

def normalize_apify_results(items: Any) -> List[Dict[str, Any]]:
    """
    Normalize Apify tweet items into a flat list ready for CSV/download.

    This keeps only the most useful fields and flattens the author object
    to avoid nested JSON in CSV output.
    """
    normalized: List[Dict[str, Any]] = []

    if not items:
        return normalized

    if isinstance(items, dict):
        items = [items]

    for item in items:
        if not isinstance(item, dict):
            normalized.append({"text": str(item)})
            continue

        author = item.get("author") or {}
        media_list = (
            (item.get("extendedEntities") or {}).get("media")
            or item.get("media")
            or []
        )
        normalized.append({
            "id": item.get("id") or item.get("tweet_id"),
            "text": item.get("text"),
            "url": item.get("url") or item.get("tweet_url"),
            "created_at": item.get("created_at") or item.get("date"),
            "author_username": author.get("username") if isinstance(author, dict) else None,
            "author_name": author.get("name") if isinstance(author, dict) else None,
            "favorite_count": item.get("favorite_count") or item.get("like_count"),
            "retweet_count": item.get("retweet_count"),
            "reply_count": item.get("reply_count"),
            "quote_count": item.get("quote_count"),
            "lang": item.get("lang"),
            "media_urls": ", ".join(
                m.get("media_url_https") or m.get("url", "")
                for m in media_list
                if isinstance(m, dict)
            ) or None,
            "media_type": ", ".join(
                m.get("type", "")
                for m in media_list
                if isinstance(m, dict)
            ) or None,
        })

    return normalized


def normalize_instagram_results(items: Any) -> List[Dict[str, Any]]:
    """
    Normalize Apify Instagram items into a flat list ready for CSV.

    Extracts key fields from Instagram post data returned by apidojo/instagram-scraper.
    """
    normalized: List[Dict[str, Any]] = []

    if not items:
        return normalized

    if isinstance(items, dict):
        items = [items]

    for item in items:
        if not isinstance(item, dict):
            normalized.append({"caption": str(item)})
            continue

        owner = item.get("owner") or {}
        location = item.get("location") or {}
        image = item.get("image") or {}
        video = item.get("video") or {}
        images_list = item.get("images") or []

        # Build comma-separated image URLs from carousel, falling back to single image
        if images_list and isinstance(images_list, list):
            image_urls = ", ".join(
                img.get("url", "") for img in images_list if isinstance(img, dict)
            ) or None
        else:
            image_urls = image.get("url") if isinstance(image, dict) else None

        normalized.append({
            "id": item.get("id"),
            "code": item.get("code"),
            "url": item.get("url"),
            "created_at": item.get("createdAt"),
            "caption": item.get("caption"),
            "like_count": item.get("likeCount"),
            "comment_count": item.get("commentCount"),
            "is_video": item.get("isVideo"),
            "is_pinned": item.get("isPinned"),
            "is_paid_partnership": item.get("isPaidPartnership"),
            "owner_username": owner.get("username") if isinstance(owner, dict) else None,
            "owner_name": owner.get("fullName") if isinstance(owner, dict) else None,
            "owner_followers": owner.get("followerCount") if isinstance(owner, dict) else None,
            "location_name": location.get("name") if isinstance(location, dict) else None,
            "image_urls": image_urls,
            "video_url": video.get("url") if isinstance(video, dict) else None,
            "video_duration": video.get("duration") if isinstance(video, dict) else None,
            "video_play_count": video.get("playCount") if isinstance(video, dict) else None,
        })

    return normalized


def normalize_facebook_results(items: Any) -> List[Dict[str, Any]]:
    """
    Normalize cleansyntax/facebook-profile-posts-scraper output into a flat list ready for CSV.
    """
    normalized: List[Dict[str, Any]] = []

    if not items:
        return normalized

    if isinstance(items, dict):
        items = [items]

    for item in items:
        if not isinstance(item, dict):
            normalized.append({"text": str(item)})
            continue

        # Skip metadata rows (e.g. profile_id resolution)
        if not item.get("post_id"):
            continue

        # Skip error items
        if item.get("error"):
            continue

        author = item.get("author") or {}
        image_obj = item.get("image") or {}
        album = item.get("album_preview") or []

        # Collect image URLs from single image and album preview
        image_urls = []
        if isinstance(image_obj, dict) and image_obj.get("uri"):
            image_urls.append(image_obj["uri"])
        for preview in album:
            if isinstance(preview, dict) and preview.get("image_file_uri"):
                image_urls.append(preview["image_file_uri"])

        # Convert unix timestamp to ISO string
        ts = item.get("timestamp")
        if isinstance(ts, (int, float)):
            from datetime import datetime, timezone
            ts = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

        normalized.append({
            "id": item.get("post_id"),
            "text": item.get("message") or item.get("message_rich"),
            "url": item.get("url"),
            "created_at": ts,
            "author_name": author.get("name") if isinstance(author, dict) else None,
            "like_count": item.get("reactions_count"),
            "comment_count": item.get("comments_count"),
            "share_count": item.get("reshare_count"),
            "media_urls": ", ".join(image_urls) or None,
            "media_type": item.get("type"),
        })

    return normalized


def normalize_instagram_comments(items: Any) -> List[Dict[str, Any]]:
    """
    Normalize Apify Instagram comment items into a flat list ready for CSV.
    """
    normalized: List[Dict[str, Any]] = []

    if not items:
        return normalized

    if isinstance(items, dict):
        items = [items]

    for item in items:
        if not isinstance(item, dict):
            normalized.append({"text": str(item)})
            continue

        # Skip error items returned by the actor for invalid/private posts
        if item.get("error") or item.get("requestErrorMessages"):
            continue

        parent_id = item.get("parentId") or item.get("parent_id")
        normalized.append({
            "id": item.get("id"),
            "text": item.get("text"),
            "author_username": item.get("ownerUsername") or item.get("owner_username") or item.get("username"),
            "created_at": item.get("timestamp") or item.get("createdAt"),
            "like_count": item.get("likesCount") or item.get("likeCount"),
            "is_reply": bool(parent_id),
            "parent_id": parent_id,
        })

    return normalized


class DataExtractRequest(BaseModel):
    """Request model for data extraction."""
    url: str = Field(..., description="URL to extract data from")
    target: str = Field(..., description="Description of what data to extract")
    channel: str = Field(default="website", description="Channel type: website, social, instagram, facebook, or instagram_comments")
    criteria: Optional[str] = Field(default=None, description="Criteria or keywords for social extraction")


class DataExtractResponse(BaseModel):
    """Response model for data extraction."""
    csv_content: str = Field(..., description="CSV formatted extracted data")
    filename: str = Field(default="data.csv", description="Suggested filename for download")


def is_data_effectively_empty(data: Any) -> bool:
    """
    Check if extracted data is effectively empty.

    Firecrawl may return status "completed" with wrapper dicts like
    {"names": []} or {"pardonRecipients": []} where the key is dynamic
    but the value is always an empty collection. The old inline check
    only caught None, "", [], {} — missing these wrapper cases.
    """
    if data is None or data == "":
        return True
    if isinstance(data, list) and len(data) == 0:
        return True
    if isinstance(data, dict):
        if len(data) == 0:
            return True
        # All values are empty lists or empty dicts
        if all(
            (isinstance(v, list) and len(v) == 0) or
            (isinstance(v, dict) and len(v) == 0)
            for v in data.values()
        ):
            return True
    return False


def format_data_as_csv(data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> str:
    """
    Format extracted data as CSV.

    The Firecrawl API returns data in various formats. This function
    handles both single objects and lists of objects, converting them
    to CSV format matching the n8n workflow output.

    Args:
        data: Extracted data (dict or list of dicts)

    Returns:
        CSV formatted string with headers
    """
    output = io.StringIO()

    # Handle case where data is a list
    if isinstance(data, list):
        if not data:
            # Empty list - return empty CSV with just headers
            writer = csv.writer(output)
            writer.writerow(["message"])
            writer.writerow(["No data extracted"])
            return output.getvalue()

        # Use first item to determine headers
        first_item = data[0]
        if isinstance(first_item, dict):
            headers = list(first_item.keys())
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            for item in data:
                if isinstance(item, dict):
                    writer.writerow(item)
                else:
                    # Non-dict items in list
                    writer.writerow({headers[0]: str(item)})
        else:
            # List of non-dict values
            writer = csv.writer(output)
            writer.writerow(["value"])
            for item in data:
                writer.writerow([str(item)])

    # Handle single dict
    elif isinstance(data, dict):
        if not data:
            # Empty dict
            writer = csv.writer(output)
            writer.writerow(["message"])
            writer.writerow(["No data extracted"])
            return output.getvalue()

        # Check if this is a wrapper with an array inside (any key name)
        # Firecrawl often returns {key_name: [array]} - unwrap it
        if len(data) == 1:
            single_value = list(data.values())[0]
            if isinstance(single_value, list):
                return format_data_as_csv(single_value)

        # Regular dict - convert to key-value pairs (matching n8n behavior)
        headers = list(data.keys())
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerow(data)

    else:
        # Scalar value
        writer = csv.writer(output)
        writer.writerow(["value"])
        writer.writerow([str(data)])

    return output.getvalue()


async def extract_data_async(
    request: DataExtractRequest,
    api_key: str
) -> DataExtractResponse:
    """
    Execute data extraction workflow.

    This is the main workflow function that:
    1. Initiates Firecrawl extraction job
    2. Polls until completion (max 5 minutes)
    3. Formats result as CSV
    4. Returns CSV content for download

    Args:
        request: Extraction request with URL and target
        api_key: Firecrawl API key from environment

    Returns:
        DataExtractResponse with CSV content

    Raises:
        FirecrawlError: If extraction fails at any stage
    """
    client = FirecrawlClient(api_key=api_key)

    try:
        # Execute extraction and wait for completion
        extracted_data = await client.extract_and_wait(
            url=request.url,
            prompt=request.target
        )

        # Format as CSV
        csv_content = format_data_as_csv(extracted_data)

        return DataExtractResponse(
            csv_content=csv_content,
            filename="data.csv"
        )

    except FirecrawlError as e:
        # Re-raise with context
        raise FirecrawlError(f"Data extraction failed: {str(e)}")


async def start_data_extraction_job(
    request: DataExtractRequest,
    settings: Any
) -> Dict[str, str]:
    """
    Start a data extraction job (async).
    Returns dict with job_id and service used.
    """
    if request.channel == "facebook":
        if not settings.apify_api_token:
            raise ValueError("Apify API token not configured")

        # Reject Facebook Page URLs
        url_lower = request.url.lower()
        if "/pages/" in url_lower or "/pg/" in url_lower:
            raise ValueError("Facebook Pages are not supported. Please enter a profile URL (e.g. facebook.com/username).")

        from .apify_client import start_facebook_scraper_async

        job_id = await start_facebook_scraper_async(
            url=request.url,
            max_items=20
        )
        return {"job_id": job_id, "service": "apify_facebook"}

    elif request.channel == "instagram_comments":
        if not settings.apify_api_token:
            raise ValueError("Apify API token not configured")

        from .apify_client import start_instagram_comments_async

        job_id = await start_instagram_comments_async(
            url=request.url,
            max_items=200
        )
        return {"job_id": job_id, "service": "apify_instagram_comments"}

    elif request.channel == "instagram":
        if not settings.apify_api_token:
            raise ValueError("Apify API token not configured")

        from .apify_client import start_instagram_scraper_async

        job_id = await start_instagram_scraper_async(
            url=request.url,
            max_items=20
        )
        return {"job_id": job_id, "service": "apify_instagram"}

    elif request.channel == "social":
        if not settings.apify_api_token:
            raise ValueError("Apify API token not configured")

        from .apify_client import start_twitter_scraper_async

        job_id = await start_twitter_scraper_async(
            url=request.url,
            keywords=None,
            max_tweets=100
        )
        return {"job_id": job_id, "service": "apify"}

    else:
        # Website extraction (Firecrawl)
        if not settings.firecrawl_api_key:
            raise ValueError("Firecrawl API key not configured")

        client = FirecrawlClient(api_key=settings.firecrawl_api_key)
        job_id = await client.start_extraction(
            url=request.url,
            prompt=request.target
        )
        return {"job_id": job_id, "service": "firecrawl"}


async def check_data_extraction_job(
    job_id: str,
    service: str,
    settings: Any
) -> Dict[str, Any]:
    """
    Check status of a data extraction job.
    Returns dict with status, data (if done), and error (if failed).
    """
    if service == "apify_facebook":
        if not settings.apify_api_token:
            raise ValueError("Apify API token not configured")

        from .apify_client import check_facebook_scraper_status

        result = await check_facebook_scraper_status(job_id)
        normalized_status = result["normalized_status"]
        data = result.get("data")
        if normalized_status == "completed":
            data = normalize_facebook_results(data)

        return {
            "status": normalized_status,
            "raw_status": result["status"],
            "data": data,
            "error": result.get("error"),
        }

    elif service == "apify_instagram_comments":
        if not settings.apify_api_token:
            raise ValueError("Apify API token not configured")

        from .apify_client import check_instagram_comments_status

        result = await check_instagram_comments_status(job_id)
        normalized_status = result["normalized_status"]
        data = result.get("data")
        if normalized_status == "completed":
            data = normalize_instagram_comments(data)

        return {
            "status": normalized_status,
            "raw_status": result["status"],
            "data": data,
            "error": result.get("error"),
        }

    elif service == "apify_instagram":
        if not settings.apify_api_token:
            raise ValueError("Apify API token not configured")

        from .apify_client import check_instagram_scraper_status

        result = await check_instagram_scraper_status(job_id)
        normalized_status = result["normalized_status"]
        data = result.get("data")
        if normalized_status == "completed":
            data = normalize_instagram_results(data)

        return {
            "status": normalized_status,
            "raw_status": result["status"],
            "data": data,
            "error": result.get("error"),
        }

    elif service == "apify":
        if not settings.apify_api_token:
            raise ValueError("Apify API token not configured")

        from .apify_client import check_twitter_scraper_status

        result = await check_twitter_scraper_status(job_id)
        normalized_status = result["normalized_status"]
        data = result.get("data")
        if normalized_status == "completed":
            data = normalize_apify_results(data)

        return {
            "status": normalized_status,
            "raw_status": result["status"],
            "data": data,
            "error": result.get("error"),
        }

    else:
        # Firecrawl
        if not settings.firecrawl_api_key:
            raise ValueError("Firecrawl API key not configured")

        client = FirecrawlClient(api_key=settings.firecrawl_api_key)
        status_data = await client.get_job_status(job_id)

        raw_status = status_data.get("status")
        # Firecrawl statuses: queued, processing, completed, failed
        # Map to: running, completed, failed
        if raw_status in ["queued", "processing"]:
            normalized_status = "running"
        elif raw_status == "completed":
            normalized_status = "completed"
        else:
            normalized_status = "failed"

        return {
            "status": normalized_status,
            "raw_status": raw_status,
            "data": status_data.get("data"),
            "error": status_data.get("error")
        }
