"""
Social media scout router.

PURPOSE: Two endpoints for social media monitoring:
- POST /social/test (session auth) — validate a social profile via HTTP HEAD
- POST /social/execute (service key auth) — full social scout execution
  (scrape, diff, summarize/criteria, notify, store records)

DEPENDS ON: dependencies (auth), schemas/social, services/social_orchestrator,
    services/execution_deduplication, utils/credits
USED BY: frontend (social scout panel), Lambda (scheduled execution),
    main.py (router mount)
"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_current_user, verify_service_key, decrement_credit, get_user_org_id
from app.schemas.social import (
    SocialTestRequest,
    SocialTestResponse,
    SocialExecuteRequest,
    NormalizedPost,
    PostSnapshot,
)
from app.services.social_orchestrator import (
    validate_profile,
    scrape_profile,
    identify_new_posts,
    identify_removed_posts,
    summarize_posts,
    match_criteria,
    send_social_notification,
)
from app.services.execution_deduplication import ExecutionDeduplicationService
from app.services.post_snapshot_service import PostSnapshotService
from app.utils.pricing import get_social_monitoring_cost

logger = logging.getLogger(__name__)

router = APIRouter()

# Lazy PostSnapshotService singleton
_snapshot_svc = None


def _get_snapshot_service() -> PostSnapshotService:
    global _snapshot_svc
    if _snapshot_svc is None:
        _snapshot_svc = PostSnapshotService()
    return _snapshot_svc


# ---------------------------------------------------------------------------
# POST /social/test — validate profile (session auth)
# ---------------------------------------------------------------------------


@router.post("/social/test", response_model=SocialTestResponse)
async def test_social_profile(
    payload: SocialTestRequest,
    user: dict = Depends(get_current_user),
):
    """Validate a social media profile and scrape baseline posts via Apify.

    1. HTTP HEAD validation (fast fail if profile doesn't exist)
    2. If valid, scrape 20 posts via Apify for baseline
    3. Return post IDs + preview + full snapshot data

    The baseline is ID-based only (no embeddings). It's stored in POSTS# at
    schedule time so the first execution can diff against it. max_items must
    match the execute endpoint (20) to avoid false "new" detections.
    """
    # Step 1: Fast HEAD validation
    valid, profile_url = await validate_profile(payload.platform, payload.handle)

    if not valid:
        return SocialTestResponse(
            valid=False,
            profile_url=profile_url,
            error="Profile not found or inaccessible",
        )

    # Step 2: Scrape baseline posts via Apify (20 posts — must match execute's
    # max_items so the first scheduled run doesn't flag old posts as "new")
    post_ids: list[str] = []
    preview_posts: list[dict] = []
    posts_data: list[dict] = []

    try:
        posts = await scrape_profile(
            platform=payload.platform,
            handle=payload.handle,
            max_items=20,
        )

        for p in posts:
            post_ids.append(p.id)
            preview_posts.append({
                "id": p.id,
                "text": (p.text or "")[:120],
                "timestamp": p.timestamp,
            })
            posts_data.append({
                "post_id": p.id,
                "caption_truncated": (p.text or "")[:200],
                "image_url": p.image_urls[0] if p.image_urls else None,
                "timestamp": p.timestamp,
            })
    except Exception as e:
        logger.warning(f"Apify baseline scrape failed for {payload.platform}/@{payload.handle}: {e}")
        # HEAD succeeded, so profile is valid — return with empty baseline + warning
        return SocialTestResponse(
            valid=True,
            profile_url=profile_url,
            error=f"Profile valid but baseline scan failed: {str(e)[:100]}",
            post_ids=[],
            preview_posts=[],
            posts_data=[],
        )

    return SocialTestResponse(
        valid=True,
        profile_url=profile_url,
        post_ids=post_ids,
        preview_posts=preview_posts,
        posts_data=posts_data,
    )


# ---------------------------------------------------------------------------
# POST /social/execute — full execution (service key auth)
# ---------------------------------------------------------------------------


@router.post("/social/execute")
async def execute_social_scout(
    payload: SocialExecuteRequest,
    _: None = Depends(verify_service_key),
):
    """Execute a social media scout: scrape, diff, summarize, notify, store.

    Called by Lambda on schedule or by internal run-now proxy.

    Detection uses two layers (see social_orchestrator.py module docstring):
    1. ID-based diffing — compare scraped post IDs against POSTS# baseline
       to find new/removed posts. No embeddings needed.
    2. Criteria matching (criteria mode only) — embed new posts on-the-fly
       (multimodal for Instagram, text-only for X) and compare against
       criteria embedding via cosine similarity.
    """
    started_at = datetime.utcnow().isoformat() + "Z"
    user_id = payload.userId
    scout_name = payload.scraperName

    try:
        # 1. Scrape profile via Apify (max 20 posts)
        posts = await scrape_profile(
            platform=payload.platform,
            handle=payload.profile_handle,
            max_items=20,
        )

        if not posts:
            logger.warning(f"No posts returned for {payload.platform}/@{payload.profile_handle}")
            return {
                "scraper_status": False,
                "criteria_status": False,
                "summary": "No posts found",
                "notification_sent": False,
            }

        # 2. Load previous POSTS# snapshot from DynamoDB
        previous_ids = set()
        previous_snapshot = []
        snapshot = await _get_snapshot_service().get_snapshot(user_id, scout_name)
        if snapshot:
            # Handle both DynamoDB format (dict with "posts" key) and Supabase format (list directly)
            if isinstance(snapshot, dict):
                posts_list = snapshot.get("posts", [])
            elif isinstance(snapshot, list):
                posts_list = snapshot
            else:
                posts_list = []
            for s in posts_list:
                previous_ids.add(s.get("post_id", ""))
                previous_snapshot.append(PostSnapshot(**s))

        # 3. Identify new and removed posts
        new_posts = identify_new_posts(posts, previous_ids)
        current_ids = {p.id for p in posts}

        removed_posts = []
        possible_actor_failure = False
        if payload.track_removals:
            # Guard: if actor returned significantly fewer posts than the previous
            # snapshot, treat it as a possible actor failure rather than mass deletion.
            if previous_snapshot and len(posts) < len(previous_snapshot) * 0.2:
                logger.warning(
                    "Social Scout %s: actor returned %d posts vs %d previous — possible actor failure, skipping removal detection",
                    scout_name, len(posts), len(previous_snapshot),
                )
                removed_posts = []
                possible_actor_failure = True
            else:
                removed_posts = identify_removed_posts(current_ids, previous_snapshot)

        # 4. Handle execution by mode
        summary = ""
        criteria_status = False
        notification_sent = False

        if payload.monitor_mode == "summarize":
            if new_posts:
                criteria_status = True
                summary = await summarize_posts(
                    new_posts,
                    payload.profile_handle,
                    payload.preferred_language,
                )
                notification_sent = await send_social_notification(
                    user_id=user_id,
                    scout_name=scout_name,
                    platform=payload.platform,
                    handle=payload.profile_handle,
                    summary=summary,
                    new_posts=new_posts,
                    removed_posts=removed_posts if payload.track_removals else None,
                    language=payload.preferred_language,
                    topic=payload.topic,
                )
            else:
                summary = "No new posts since last check."

        elif payload.monitor_mode == "criteria":
            # TODO(Phase 3): Add notification for criteria matches.
            # Currently detects matches but does not email the user.
            # When adding notification here, include topic=payload.topic.
            matched = await match_criteria(new_posts, payload.criteria or "", payload.platform)
            criteria_status = len(matched) > 0
            if matched:
                summary = f"{len(matched)} posts matched criteria."
            else:
                summary = "No posts matched criteria."

        # 5. Append removal info or actor failure note to summary
        if removed_posts and payload.track_removals:
            summary += f"\n\n{len(removed_posts)} post(s) removed since last check."
        elif possible_actor_failure:
            summary += "\n\nNote: scraper returned significantly fewer posts than expected — possible actor failure. Removal detection skipped for this run."

        # 6. Store EXEC# record
        try:
            exec_dedup = ExecutionDeduplicationService()
            await exec_dedup.store_execution(
                user_id=user_id,
                scout_name=scout_name,
                scout_type="social",
                summary_text=summary[:150],
                is_duplicate=False,
                started_at=started_at,
            )
        except Exception as e:
            logger.error(f"Failed to store EXEC# record: {e}")

        # 7. Save POSTS# snapshot to DynamoDB
        try:
            snapshot_records = []
            for p in posts:
                snapshot_records.append({
                    "post_id": p.id,
                    "caption_truncated": (p.text or "")[:200],
                    "image_url": p.image_urls[0] if p.image_urls else None,
                    "timestamp": p.timestamp,
                })
            await _get_snapshot_service().store_snapshot(
                user_id, scout_name, snapshot_records, payload.platform, payload.profile_handle
            )
        except Exception as e:
            logger.error(f"Failed to save POSTS# snapshot: {e}")

        # 8. Decrement credits (platform-tiered)
        if not payload.skip_credit_charge:
            try:
                org_id = await get_user_org_id(user_id)
                platform_key = f"social_monitoring_{payload.platform}"
                await decrement_credit(
                    user_id, get_social_monitoring_cost(payload.platform), org_id=org_id,
                    operation=platform_key, scout_name=scout_name,
                    scout_type="social",
                )
            except Exception as e:
                logger.error(f"Failed to decrement credits: {e}")

        return {
            "scraper_status": True,
            "criteria_status": criteria_status,
            "summary": summary,
            "notification_sent": notification_sent,
            "new_posts": len(new_posts),
            "removed_posts": len(removed_posts),
            "total_posts": len(posts),
        }

    except Exception as e:
        logger.exception(f"Social scout execution failed: {e}")
        return {
            "scraper_status": False,
            "criteria_status": False,
            "summary": f"Execution error: {str(e)}",
            "notification_sent": False,
        }
