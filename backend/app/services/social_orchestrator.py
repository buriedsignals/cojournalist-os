"""
Social media scout orchestrator.

PURPOSE: Normalize posts from Apify scrapers, detect new/removed posts,
validate profiles, generate AI summaries, and send notifications for
social media monitoring scouts.

DEPENDS ON: config (Apify token, OpenRouter key), http_client (connection pooling),
    embedding_utils (multimodal embeddings), notification_service (email),
    user_service (email lookup), openrouter (AI summary),
    apify_client (actor start/poll for Instagram + X scrapers)
USED BY: routers/social.py

ARCHITECTURE — Two-layer detection:

    Layer 1: ID-based diffing (identify_new_posts / identify_removed_posts)
        The POSTS# baseline stored at schedule time contains post IDs only (no
        embeddings). Each execution scrapes the profile, compares post IDs against
        the baseline, and returns posts whose IDs are absent from the previous
        snapshot. This is cheap, deterministic, and sufficient for detecting new
        and removed content. Both test and execute endpoints fetch the same
        max_items (20) so the baseline covers the same window as execution.

    Layer 2: Criteria matching (match_criteria, on-the-fly embeddings)
        Only runs in "criteria" mode, and only on new posts identified by Layer 1.
        Each new post is embedded at execution time (text-only for X, multimodal
        text+image via Gemini for Instagram) and compared against the criteria
        text embedding via cosine similarity. The baseline never stores embeddings
        because they're only needed for the criteria comparison, not for diffing.

    Flow:
        scrape → ID diff against baseline → new posts only → embed + compare
        against criteria → notify if matches found → overwrite baseline

APIFY ACTORS:
    Instagram: culc72xb7MP3EbaeX (apidojo/instagram-scraper) — returns individual posts
    X/Twitter: 61RPP7dywgiy0JPD0 — returns individual tweets
    Facebook: cleansyntax~facebook-profile-posts-scraper — returns profile posts
    All are delegated to via app.workflows.apify_client functions.
"""
from __future__ import annotations

import asyncio
import html
import logging
from typing import Optional

from app.config import settings
from app.dependencies import get_user_email
from app.services.http_client import get_http_client
from app.services.notification_service import NotificationService, markdown_to_html
from app.services.openrouter import openrouter_chat
from app.services.embedding_utils import generate_embedding_multimodal, generate_embedding, cosine_similarity
from app.schemas.social import NormalizedPost, PostSnapshot
from app.workflows.apify_client import (
    start_instagram_scraper_async,
    check_instagram_scraper_status,
    start_twitter_scraper_async,
    check_twitter_scraper_status,
    start_facebook_scraper_async,
    check_facebook_scraper_status,
    start_tiktok_scraper_async,
    check_tiktok_scraper_status,
    ApifyError,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def normalize_instagram_posts(raw_items: list[dict]) -> list[NormalizedPost]:
    """Map apidojo/instagram-scraper (culc72xb7MP3EbaeX) output to NormalizedPost.

    Key mapping (from actor output):
    - id -> id
    - code -> shortcode for URL
    - caption -> text
    - owner.username -> author
    - createdAt -> timestamp
    - image.url -> image_urls (single nested object)
    - video.url -> video_url (when isVideo is true)
    - likeCount, commentCount -> engagement
    """
    posts = []
    for item in raw_items:
        post_id = item.get("id") or item.get("code") or ""
        if not post_id:
            continue

        # Extract image URL from nested object
        image_urls = []
        image_obj = item.get("image")
        if isinstance(image_obj, dict) and image_obj.get("url"):
            image_urls.append(image_obj["url"])

        # Video URL only when isVideo flag is set
        video_url = None
        if item.get("isVideo"):
            video_obj = item.get("video")
            if isinstance(video_obj, dict):
                video_url = video_obj.get("url")

        shortcode = item.get("code", str(post_id))
        owner = item.get("owner", {})
        author = owner.get("username", "") if isinstance(owner, dict) else ""
        url = f"https://www.instagram.com/p/{shortcode}/"

        posts.append(NormalizedPost(
            id=str(post_id),
            url=url,
            text=item.get("caption", "") or "",
            author=author,
            timestamp=item.get("createdAt", ""),
            image_urls=image_urls,
            video_url=video_url,
            platform="instagram",
            engagement={
                "likes": item.get("likeCount", 0),
                "comments": item.get("commentCount", 0),
            },
        ))
    return posts


def normalize_x_posts(raw_items: list[dict]) -> list[NormalizedPost]:
    """Map apify twitter scraper (61RPP7dywgiy0JPD0) output to NormalizedPost."""
    posts = []
    for item in raw_items:
        post_id = item.get("id") or item.get("id_str") or ""
        if not post_id:
            continue

        author = item.get("author", {})
        if isinstance(author, dict):
            author_handle = author.get("username", "")
        else:
            author_handle = str(author)

        url = item.get("url", "")
        if not url and author_handle:
            url = f"https://x.com/{author_handle}/status/{post_id}"

        # Extract media URLs from extendedEntities or media array
        image_urls = []
        media_list = (
            (item.get("extendedEntities") or {}).get("media")
            or item.get("media")
            or []
        )
        for med in media_list:
            if isinstance(med, dict):
                media_url = med.get("media_url_https") or med.get("url", "")
                if media_url:
                    image_urls.append(media_url)

        posts.append(NormalizedPost(
            id=str(post_id),
            url=url,
            text=item.get("text", "") or "",
            author=author_handle,
            timestamp=item.get("created_at", ""),
            image_urls=image_urls,
            video_url=None,
            platform="x",
            engagement={
                "likes": item.get("favorite_count", 0),
                "retweets": item.get("retweet_count", 0),
                "replies": item.get("reply_count", 0),
            },
        ))
    return posts


def normalize_facebook_posts(raw_items: list[dict]) -> list[NormalizedPost]:
    """Map cleansyntax/facebook-profile-posts-scraper output to NormalizedPost.

    Key mapping (from actor output):
    - post_id -> id
    - url -> url
    - message -> text
    - author.name -> author
    - timestamp (unix epoch int) -> timestamp
    - image.uri / album_preview[].image_file_uri -> image_urls
    - reactions_count -> likes
    - comments_count -> comments
    - reshare_count -> shares
    """
    posts = []
    for item in raw_items:
        # Skip metadata/error items (e.g. profile_id resolution rows)
        post_id = str(item.get("post_id") or "")
        if not post_id:
            continue

        # Author from nested author object
        author = ""
        author_obj = item.get("author")
        if isinstance(author_obj, dict):
            author = author_obj.get("name", "")

        # Image: single image or album preview
        image_urls = []
        image_obj = item.get("image")
        if isinstance(image_obj, dict) and image_obj.get("uri"):
            image_urls.append(image_obj["uri"])
        album = item.get("album_preview") or []
        for preview in album:
            if isinstance(preview, dict):
                uri = preview.get("image_file_uri", "")
                if uri:
                    image_urls.append(uri)

        # Video
        video_url = None
        video_obj = item.get("video")
        if isinstance(video_obj, dict):
            video_url = video_obj.get("url")

        # Timestamp: actor returns unix epoch int
        ts = item.get("timestamp") or ""
        if isinstance(ts, (int, float)):
            from datetime import datetime, timezone
            ts = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

        posts.append(NormalizedPost(
            id=post_id,
            url=item.get("url") or "",
            text=item.get("message") or item.get("message_rich") or "",
            author=author,
            timestamp=str(ts),
            image_urls=image_urls,
            video_url=video_url,
            platform="facebook",
            engagement={
                "likes": item.get("reactions_count") or 0,
                "comments": item.get("comments_count") or 0,
                "shares": item.get("reshare_count") or 0,
            },
        ))
    return posts


def normalize_tiktok_posts(raw_items: list[dict]) -> list[NormalizedPost]:
    """Map novi/tiktok-user-api output to NormalizedPost.

    Key mapping (from actor output):
    - aweme_id -> id
    - desc -> text
    - create_time (unix) -> timestamp (ISO 8601)
    - share_url -> url (fallback: constructed from author + id)
    - author.unique_id -> author
    - video.cover.url_list[0] -> image_urls (cover thumbnail for embedding)
    - video.play_addr.url_list[0] -> video_url
    - No engagement fields — content-only for journalist criteria matching.
    """
    posts = []
    for item in raw_items:
        post_id = str(item.get("aweme_id") or item.get("id") or "")
        if not post_id:
            continue

        # Author
        author_obj = item.get("author") or {}
        author = author_obj.get("unique_id") or author_obj.get("nickname") or ""

        # Cover image (for multimodal embedding)
        image_urls = []
        video_obj = item.get("video") or {}
        cover = video_obj.get("cover") or {}
        cover_urls = cover.get("url_list") or []
        if cover_urls:
            image_urls.append(cover_urls[0])

        # Video play URL
        video_url = None
        play_addr = video_obj.get("play_addr") or {}
        play_urls = play_addr.get("url_list") or []
        if play_urls:
            video_url = play_urls[0]

        # Timestamp: actor returns unix epoch int
        ts = item.get("create_time") or ""
        if isinstance(ts, (int, float)):
            from datetime import datetime, timezone
            ts = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

        # URL: prefer share_url, fallback to constructed URL
        url = item.get("share_url") or ""
        if not url and author and post_id:
            url = f"https://www.tiktok.com/@{author}/video/{post_id}"

        posts.append(NormalizedPost(
            id=post_id,
            url=url,
            text=item.get("desc") or item.get("content_desc") or "",
            author=author,
            timestamp=str(ts),
            image_urls=image_urls,
            video_url=video_url,
            platform="tiktok",
            engagement={},
        ))
    return posts


# ---------------------------------------------------------------------------
# Post diffing
# ---------------------------------------------------------------------------

def identify_new_posts(
    current_posts: list[NormalizedPost],
    previous_ids: set[str],
) -> list[NormalizedPost]:
    """Filter posts that are not in the previous snapshot."""
    return [p for p in current_posts if p.id not in previous_ids]


def identify_removed_posts(
    current_ids: set[str],
    snapshot: list[PostSnapshot],
) -> list[PostSnapshot]:
    """Find posts present in the snapshot but absent from current scrape."""
    return [s for s in snapshot if s.post_id not in current_ids]


# ---------------------------------------------------------------------------
# Profile utilities
# ---------------------------------------------------------------------------

def is_facebook_page_url(handle: str) -> bool:
    """Detect Facebook Page URLs (not personal profiles).

    Pages use URL patterns like /pages/Name/123, /pg/Name, or are
    well-known brand pages. We reject obvious page-format URLs so users
    use profile handles instead.
    """
    clean = handle.lstrip("@").strip().lower()
    # Obvious page URL patterns
    if clean.startswith("pages/") or clean.startswith("pg/"):
        return True
    # Full URL pasted with /pages/ or /pg/
    if "/pages/" in clean or "/pg/" in clean:
        return True
    return False


def build_profile_url(platform: str, handle: str) -> str:
    """Build full profile URL from platform + handle."""
    clean = handle.lstrip("@").strip()
    if platform == "instagram":
        return f"https://www.instagram.com/{clean}/"
    elif platform == "x":
        return f"https://x.com/{clean}"
    elif platform == "facebook":
        return f"https://www.facebook.com/{clean}/"
    elif platform == "tiktok":
        return f"https://www.tiktok.com/@{clean}"
    return ""


async def validate_profile(platform: str, handle: str) -> tuple[bool, str]:
    """Check that a social profile exists before scraping.

    Uses GET for X/Twitter (HEAD returns 4xx for logged-out requests),
    HEAD for other platforms. For Facebook, rejects obvious Page URLs.

    Returns:
        (valid, profile_url)  — or (False, error_message) on rejection
    """
    if platform == "facebook" and is_facebook_page_url(handle):
        return False, "Facebook Pages are not supported. Please enter a personal profile handle (e.g. 'username')."

    url = build_profile_url(platform, handle)
    if not url:
        return False, ""

    try:
        client = await get_http_client()
        # X/Twitter and TikTok reject HEAD requests for logged-out users; use GET instead
        if platform in ("x", "tiktok"):
            response = await client.get(url, follow_redirects=True, timeout=10.0)
        else:
            response = await client.head(url, follow_redirects=True, timeout=10.0)
        valid = response.status_code < 400
        return valid, url
    except Exception as e:
        logger.warning(f"Profile validation failed for {platform}/{handle}: {e}")
        return False, url


# ---------------------------------------------------------------------------
# Apify scraping
# ---------------------------------------------------------------------------

async def scrape_profile(
    platform: str,
    handle: str,
    max_items: int = 20,
) -> list[NormalizedPost]:
    """Start Apify actor run via apify_client, poll until complete, return normalized posts.

    Uses the proven actor IDs from apify_client:
    - Instagram: culc72xb7MP3EbaeX (apidojo/instagram-scraper)
    - X: 61RPP7dywgiy0JPD0

    Args:
        platform: "instagram" or "x"
        handle: Profile handle (without @)
        max_items: Maximum posts to fetch

    Returns:
        List of NormalizedPost objects
    """
    url = build_profile_url(platform, handle)
    if not url:
        raise ValueError(f"Unsupported platform: {platform}")

    if platform == "instagram":
        run_id = await start_instagram_scraper_async(url, max_items=max_items)
        for _ in range(60):
            await asyncio.sleep(2)
            result = await check_instagram_scraper_status(run_id)
            if result["normalized_status"] == "completed":
                return normalize_instagram_posts(result.get("data") or [])
            if result["normalized_status"] == "failed":
                raise ApifyError(f"Apify Instagram run {run_id} failed: {result.get('error')}")
        raise ApifyError(f"Apify Instagram run {run_id} timed out after 120s")

    elif platform == "x":
        run_id = await start_twitter_scraper_async(url, max_tweets=max_items)
        for _ in range(60):
            await asyncio.sleep(2)
            result = await check_twitter_scraper_status(run_id)
            if result["normalized_status"] == "completed":
                return normalize_x_posts(result.get("data") or [])
            if result["normalized_status"] == "failed":
                raise ApifyError(f"Apify X run {run_id} failed: {result.get('error')}")
        raise ApifyError(f"Apify X run {run_id} timed out after 120s")

    elif platform == "facebook":
        run_id = await start_facebook_scraper_async(url, max_items=max_items)
        for _ in range(60):
            await asyncio.sleep(2)
            result = await check_facebook_scraper_status(run_id)
            if result["normalized_status"] == "completed":
                return normalize_facebook_posts(result.get("data") or [])
            if result["normalized_status"] == "failed":
                raise ApifyError(f"Apify Facebook run {run_id} failed: {result.get('error')}")
        raise ApifyError(f"Apify Facebook run {run_id} timed out after 120s")

    elif platform == "tiktok":
        run_id = await start_tiktok_scraper_async(url, max_items=max_items)
        for _ in range(60):
            await asyncio.sleep(2)
            result = await check_tiktok_scraper_status(run_id)
            if result["normalized_status"] == "completed":
                return normalize_tiktok_posts(result.get("data") or [])
            if result["normalized_status"] == "failed":
                raise ApifyError(f"Apify TikTok run {run_id} failed: {result.get('error')}")
        raise ApifyError(f"Apify TikTok run {run_id} timed out after 120s")

    else:
        raise ValueError(f"Unsupported platform: {platform}")


# ---------------------------------------------------------------------------
# Image download (for multimodal embeddings)
# ---------------------------------------------------------------------------

async def download_image(url: str, timeout: int = 15) -> Optional[bytes]:
    """Download image bytes from a CDN URL.

    Returns None on failure instead of raising.
    """
    try:
        client = await get_http_client()
        response = await client.get(url, timeout=float(timeout), follow_redirects=True)
        if response.status_code == 200:
            return response.content
        logger.warning(f"Image download failed ({response.status_code}): {url[:80]}")
        return None
    except Exception as e:
        logger.warning(f"Image download error: {e}")
        return None


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

async def generate_post_embedding(
    post: NormalizedPost,
    include_images: bool = True,
) -> Optional[list[float]]:
    """Generate embedding for a social media post.

    All platforms with images: multimodal embedding (text + first image) via Gemini.
    Posts without images: text-only embedding.
    """
    try:
        text = f"{post.author}: {post.text}" if post.text else post.author

        if include_images and post.image_urls:
            image_data = await download_image(post.image_urls[0])
            if image_data:
                return await generate_embedding_multimodal(
                    text=text,
                    image_bytes=image_data,
                    task_type="SEMANTIC_SIMILARITY",
                )

        # Fallback to text-only
        return await generate_embedding(text, "SEMANTIC_SIMILARITY")
    except Exception as e:
        logger.error(f"Post embedding failed for {post.id}: {e}")
        return None


# ---------------------------------------------------------------------------
# AI summary
# ---------------------------------------------------------------------------

SOCIAL_SUMMARY_SYSTEM = """You are a social media analyst. Summarize the recent posts from the given profile.
Focus on: key themes, notable announcements, tone/sentiment.
Output a concise markdown summary (3-5 bullet points max).
Write in the language specified by the user."""

async def summarize_posts(
    posts: list[NormalizedPost],
    handle: str,
    language: str = "en",
) -> str:
    """Generate AI summary of recent social media posts via OpenRouter.

    Args:
        posts: Normalized posts to summarize
        handle: Profile handle for context
        language: Language code for output

    Returns:
        Markdown summary string
    """
    if not posts:
        return "No recent posts found."

    # Build content from posts (max 10)
    content_parts = []
    for p in posts[:10]:
        line = f"- @{p.author} ({p.timestamp}): {p.text[:300]}"
        if p.engagement:
            eng_parts = [f"{k}: {v}" for k, v in p.engagement.items() if v]
            if eng_parts:
                line += f" [{', '.join(eng_parts)}]"
        content_parts.append(line)

    content = f"Profile: @{handle}\nPlatform: {posts[0].platform}\n\nRecent posts:\n" + "\n".join(content_parts)

    try:
        response = await openrouter_chat(
            messages=[
                {"role": "system", "content": SOCIAL_SUMMARY_SYSTEM},
                {"role": "user", "content": f"Language: {language}\n\n{content}"},
            ],
            max_tokens=500,
            temperature=0.3,
        )
        return response["content"].strip()
    except Exception as e:
        logger.error(f"Social summary generation failed: {e}")
        return f"Summary unavailable for @{handle}."


# ---------------------------------------------------------------------------
# Criteria matching
# ---------------------------------------------------------------------------

async def match_criteria(
    posts: list[NormalizedPost],
    criteria: str,
    platform: str,
) -> list[NormalizedPost]:
    """Match posts against user criteria using embedding similarity.

    Embeds the criteria as a retrieval query and compares against each post's
    embedding. Posts with cosine similarity > 0.65 are returned as matches.
    """
    if not posts or not criteria:
        return []

    # Embed criteria as a retrieval query
    criteria_embedding = await generate_embedding(criteria, "RETRIEVAL_QUERY")

    matched = []
    for post in posts:
        post_embedding = await generate_post_embedding(
            post, include_images=True
        )
        if not post_embedding:
            continue

        similarity = cosine_similarity(criteria_embedding, post_embedding)
        if similarity > 0.65:  # Threshold TBD — recalibrate empirically
            matched.append(post)

    return matched


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

async def send_social_notification(
    user_id: str,
    scout_name: str,
    platform: str,
    handle: str,
    summary: str,
    new_posts: list[NormalizedPost],
    removed_posts: list[PostSnapshot] | None = None,
    language: str = "en",
    topic: str | None = None,
) -> bool:
    """Send social scout email notification.

    Looks up user email via get_user_email, builds HTML via
    NotificationService._build_email_html, sends via _send_email_with_retry.

    Args:
        user_id: User ID for email lookup
        scout_name: Scout name for subject line
        platform: Social platform name
        handle: Profile handle
        summary: AI-generated markdown summary
        new_posts: List of new posts detected
        removed_posts: Optional list of removed posts
        language: Language code
        topic: Optional topic for email subject context

    Returns:
        True if email sent successfully
    """
    email = await get_user_email(user_id)
    if not email:
        logger.warning(f"No email found for user {user_id}, skipping notification")
        return False

    ns = NotificationService()

    # Build articles list from new posts
    articles = []
    for post in new_posts[:5]:
        articles.append({
            "title": f"@{post.author}" if post.author else "New Post",
            "summary": post.text[:150] if post.text else "",
            "url": post.url,
            "source": platform,
        })

    # Build removal section if tracking removals
    post_content = ""
    if removed_posts:
        removal_lines = []
        for rp in removed_posts[:5]:
            removal_lines.append(
                f'<div style="margin-bottom: 8px; padding: 8px; background: #fff3f3; border-radius: 4px;">'
                f'<span style="color: #dc2626; font-weight: 600;">Removed:</span> '
                f'{html.escape(rp.caption_truncated)}'
                f'</div>'
            )
        post_content = (
            '<div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid #e5e7eb;">'
            '<h3 style="margin: 0 0 12px 0; color: #333;">Removed Posts</h3>'
            + "\n".join(removal_lines)
            + '</div>'
        )

    profile_url = build_profile_url(platform, handle)
    safe_handle = html.escape(handle)
    safe_scout_name = html.escape(scout_name)
    safe_profile_url = html.escape(profile_url)

    html_content = ns._build_email_html(
        header_title=f"Social Scout Update",
        header_subtitle=safe_scout_name,
        header_gradient=("#e11d48", "#be123c"),
        accent_color="#e11d48",
        context_label=f"@{safe_handle} on {platform.upper()}",
        summary=summary,
        articles=articles,
        articles_section_title="New Posts",
        extra_content=(
            f'<div style="margin-bottom: 16px; padding: 12px; background: #f8f9fa; border-radius: 6px;">'
            f'<p style="margin: 0 0 4px 0; font-size: 12px; color: #666; text-transform: uppercase;">PROFILE</p>'
            f'<a href="{safe_profile_url}" style="color: #e11d48; text-decoration: none;">{safe_profile_url}</a>'
            f'</div>'
        ),
        cta_text="",
        post_content=post_content,
    )

    return await ns._send_email_with_retry(
        to_email=email,
        subject=(
            f"[coJournalist] Social Scout: {topic} - @{handle} - {scout_name}"
            if topic
            else f"[coJournalist] Social Scout: @{handle} - {scout_name}"
        ),
        html_content=html_content,
    )
