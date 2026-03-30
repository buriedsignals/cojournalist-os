"""
Scout execution service for Page Scouts (type "web").

PURPOSE: Scrape URLs via Firecrawl, detect content changes (changeTracking
or hash-based fallback), run AI criteria analysis, extract atomic units,
and send email notifications for matching changes.

DEPENDS ON: config (API keys), notification_service, execution_deduplication,
    atomic_unit_service, http_client, news_utils (lang_name),
    dependencies (email/credit helpers), schemas/scouts (GeocodedLocation)
USED BY: routers/scouts.py, routers/scraper.py

CRITICAL: Uses Firecrawl changeTracking with user-scoped tags
({user_id}#{scraper_name}) to ensure independent baselines per user.
See CLAUDE.md "Page Scout Change Detection" for full rationale.
Do NOT remove the tag parameter or change its format.
"""
import hashlib
import json
import logging
from datetime import datetime
from typing import Optional

from app.config import settings
from app.services.notification_service import NotificationService
from app.services.execution_deduplication import ExecutionDeduplicationService
from app.services.atomic_unit_service import AtomicUnitService
from app.services.http_client import get_http_client
from app.services.news_utils import lang_name
from app.dependencies import get_user_email, decrement_credit
from app.schemas.scouts import GeocodedLocation

logger = logging.getLogger(__name__)


class ScoutService:
    """Execute scout scrapes with change detection and criteria analysis."""

    FIRECRAWL_URL = "https://api.firecrawl.dev/v2/scrape"
    OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self):
        self.notification_service = NotificationService()
        self.exec_dedup_service = ExecutionDeduplicationService()
        self.atomic_unit_service = AtomicUnitService()

    async def _detect_change_by_hash(self, markdown_text: str, user_id: str, scraper_name: str) -> tuple[str, str]:
        """Detect changes via SHA-256 hash comparison. Returns (change_status, content_hash)."""
        content_hash = hashlib.sha256(markdown_text.encode("utf-8")).hexdigest()
        previous_hash = await self.exec_dedup_service.get_latest_content_hash(
            user_id, scraper_name or "web-scout"
        )
        if previous_hash is None:
            return "new", content_hash
        elif content_hash == previous_hash:
            return "same", content_hash
        else:
            return "changed", content_hash

    async def double_probe(self, url: str, user_id: str, scraper_name: str) -> str:
        """Verify changeTracking baseline storage with two sequential scrapes.

        Call 1: Scrape with changeTracking tag (establishes baseline).
        Call 2: Scrape again with same tag — check previousScrapeAt.
          - Has timestamp → baseline confirmed stored → "firecrawl"
          - null → baseline silently dropped → "firecrawl_plain"
          - Timeout on either call → "firecrawl_plain"

        See page-scout-refactor.md § "Phase 3" for rationale.
        """
        tag = f"{user_id}#{scraper_name or 'web-scout'}"
        if len(tag) > 128:
            tag = tag[:128]

        # Call 1: establish baseline
        result1 = await self._firecrawl_scrape(url, tag=tag, timeout=30.0)
        if not result1:
            logger.info(f"Double-probe call 1 failed for {url} — firecrawl_plain")
            return "firecrawl_plain"

        # Call 2: verify baseline was stored
        result2 = await self._firecrawl_scrape(url, tag=tag, timeout=30.0)
        if not result2:
            logger.info(f"Double-probe call 2 failed for {url} — firecrawl_plain")
            return "firecrawl_plain"

        ct = result2.get("changeTracking", {})
        previous_scrape = ct.get("previousScrapeAt") if ct else None

        if previous_scrape:
            logger.info(f"Double-probe confirmed baseline for {url} (previousScrapeAt={previous_scrape})")
            return "firecrawl"
        else:
            logger.info(f"Double-probe: baseline dropped for {url} (previousScrapeAt=null)")
            return "firecrawl_plain"

    async def execute(
        self,
        url: str,
        user_id: str,
        criteria: Optional[str] = None,
        scraper_name: Optional[str] = None,
        location: Optional[dict] = None,
        topic: Optional[str] = None,
        preferred_language: str = "en",
        skip_duplicate_check: bool = False,
        skip_notification: bool = False,
        skip_credit_charge: bool = False,
        preview_mode: bool = False,
        provider: Optional[str] = None,
        org_id: Optional[str] = None
    ) -> dict:
        """
        Execute scout: scrape URL, detect changes, analyze against criteria.

        User email is fetched from MuckRock API using user_id for notifications.

        Args:
            preview_mode: If True, scrape without changeTracking (no baseline established).
                          Used for test runs that should be side-effect-free.

        Returns:
            {scraper_status, criteria_status, summary}
        """
        started_at = datetime.utcnow().isoformat() + "Z"
        content_hash = None

        async def store_exec(summary_text: str, is_duplicate: bool = False, embedding=None):
            await self.exec_dedup_service.store_execution(
                user_id=user_id,
                scout_name=scraper_name or "web-scout",
                scout_type="web",
                summary_text=summary_text,
                is_duplicate=is_duplicate,
                started_at=started_at,
                content_hash=content_hash,
                provider=provider,
                embedding=embedding,
            )

        try:
            logger.info(f"Executing scout for {url} (preview_mode={preview_mode})")

            if preview_mode:
                provider = provider or "firecrawl"  # preserve incoming, default if None
                scrape_result = await self._firecrawl_scrape(url)
                change_status = "new"
                if scrape_result:
                    content_hash = hashlib.sha256(
                        scrape_result.get("markdown", "").encode("utf-8")
                    ).hexdigest()
            elif provider == "firecrawl_plain":
                # Pre-determined: changeTracking doesn't work for this URL
                scrape_result = await self._firecrawl_scrape(url)
                if scrape_result:
                    markdown_text = scrape_result.get("markdown", "")
                    change_status, content_hash = await self._detect_change_by_hash(
                        markdown_text, user_id, scraper_name
                    )
                else:
                    change_status = "new"
            else:
                # Default (provider="firecrawl" or None): try changeTracking
                provider = "firecrawl"
                tag = f"{user_id}#{scraper_name or 'web-scout'}"
                if len(tag) > 128:
                    tag = tag[:128]
                scrape_result = await self._firecrawl_scrape(url, tag=tag)
                if scrape_result:
                    change_tracking = scrape_result.get("changeTracking", {})
                    change_status = change_tracking.get("changeStatus", "new")
                else:
                    # changeTracking failed — fall back to plain (backwards compat)
                    logger.info(f"Firecrawl changeTracking failed for {url}, trying plain scrape fallback")
                    scrape_result = await self._firecrawl_scrape(url)
                    if scrape_result:
                        provider = "firecrawl_plain"
                        markdown_text = scrape_result.get("markdown", "")
                        change_status, content_hash = await self._detect_change_by_hash(
                            markdown_text, user_id, scraper_name
                        )
                    else:
                        change_status = "new"

            if not scrape_result:
                logger.error(f"Failed to scrape URL: {url}")
                return {
                    "scraper_status": False,
                    "criteria_status": False,
                    "summary": "Failed to scrape URL",
                    "content_hash": content_hash
                }

            logger.info(f"Change status for {url}: {change_status}")

            # Step 2: If unchanged, return early (Firecrawl returns "same" not "unchanged")
            if change_status == "same":
                # Store EXEC# record for unchanged page
                if not preview_mode:
                    try:
                        await store_exec("No changes detected")
                    except Exception as e:
                        logger.warning(f"Failed to store EXEC# for unchanged page: {e}")
                return {
                    "scraper_status": True,
                    "criteria_status": False,
                    "summary": "",
                    "content_hash": content_hash
                }

            # Step 3: Criteria analysis
            markdown = scrape_result.get("markdown", "")
            page_title = (scrape_result.get("metadata") or {}).get("title", "")
            if page_title:
                page_title = page_title[:200]
            language_name = lang_name(preferred_language)

            if not criteria:
                # No criteria — generate AI summary of page content
                if not markdown or not markdown.strip():
                    summary = page_title or ""
                    logger.warning(f"Empty markdown from Firecrawl for {url}")
                else:
                    content_to_summarize = markdown[:5000]
                    summary = await self._summarize_page(content_to_summarize, url, change_status, language_name)
                    if not summary:
                        # LLM failed but scrape succeeded — degrade gracefully
                        summary = page_title or ""
                        logger.warning(f"LLM summary failed for {url}, falling back to page title")
                matched_url = ""
                matched_title = ""
                logger.info(f"Generated page summary for {url}")
            else:
                # "Specific Criteria" mode — existing LLM analysis
                content_to_analyze = markdown[:5000] if markdown else ""
                analysis = await self._analyze_changes(content_to_analyze, criteria, url, change_status, language_name)

                if not analysis.get("matches"):
                    logger.info(f"No criteria match for {url}")
                    # Store EXEC# record for non-matches (for consistency)
                    if not preview_mode:
                        try:
                            await store_exec("No criteria match")
                        except Exception as e:
                            logger.warning(f"Failed to store EXEC# for non-match: {e}")
                    return {
                        "scraper_status": True,
                        "criteria_status": False,
                        "summary": "",
                        "content_hash": content_hash
                    }

                summary = analysis.get("summary", "")
                matched_url = analysis.get("matched_url") or ""
                matched_title = analysis.get("matched_title") or ""

            logger.info(f"Criteria matched for {url}: {summary[:100]}")

            # Step 4: Check for duplicates using EXEC# records (consolidated dedup)
            if not skip_duplicate_check and not preview_mode:
                is_dup, similarity, embedding = await self.exec_dedup_service.check_duplicate(
                    user_id=user_id,
                    scout_name=scraper_name or "web-scout",
                    summary_text=summary,
                )
                if is_dup:
                    logger.info(f"Duplicate result detected for {url} (sim={similarity:.3f})")
                    await store_exec("No new findings", is_duplicate=True, embedding=embedding)
                    return {
                        "scraper_status": True,
                        "criteria_status": False,
                        "summary": "",
                        "content_hash": content_hash
                    }

            # Step 5: Store EXEC# record for matches (for card_summary)
            # For web scouts, use criteria summary directly (already short, 1-2 sentences)
            # No need to re-summarize with another LLM call
            if not preview_mode:
                try:
                    exec_summary = summary[:150] if summary else ""
                    await store_exec(exec_summary)
                except Exception as e:
                    logger.warning(f"Failed to store EXEC# for match: {e}")

            # Step 5b: Extract and store information units
            if (location or topic) and not preview_mode:
                try:
                    location_obj = GeocodedLocation(**location) if location and isinstance(location, dict) else location
                    published_date = (scrape_result.get("metadata") or {}).get("publishedDate")
                    await self.atomic_unit_service.process_results(
                        results=[{
                            "title": page_title or scraper_name or "Web Scout Match",
                            "content": markdown,
                            "summary": summary,
                            "url": url,
                            "date": published_date,
                        }],
                        scout_id=scraper_name or "web-scout",
                        scout_type="web",
                        user_id=user_id,
                        location=location_obj,
                        topic=topic,
                        language=language_name,
                    )
                except Exception as e:
                    logger.warning(f"Failed to store information units: {e}")

            # Step 6: Send notification (if not skipped)
            if not skip_notification:
                user_email = await get_user_email(user_id)
                if user_email:
                    try:
                        await self.notification_service.send_scout_alert(
                            to_email=user_email,
                            scout_name=scraper_name or "Scout",
                            url=url,
                            criteria=criteria or "",
                            summary=summary,
                            language=preferred_language,
                            matched_url=matched_url,
                            matched_title=matched_title,
                        )
                    except Exception as e:
                        logger.error(f"Failed to send notification: {e}")
                        # Don't fail the request if notification fails
                else:
                    logger.warning(f"Could not fetch email for user {user_id}, skipping notification")

            # Step 8: Decrement credit (if not skipped - only AWS Lambda calls should charge)
            if not skip_credit_charge:
                await decrement_credit(user_id, org_id=org_id)

            # Step 9: Return success
            return {
                "scraper_status": True,
                "criteria_status": True,
                "summary": summary,
                "content_hash": content_hash
            }

        except Exception as e:
            logger.exception(f"Scout execution failed: {e}")
            return {
                "scraper_status": False,
                "criteria_status": False,
                "summary": "An error occurred while processing the web scout",
                "content_hash": content_hash
            }

    async def _firecrawl_scrape(self, url: str, tag: Optional[str] = None, timeout: float = 30.0) -> Optional[dict]:
        """Scrape URL via Firecrawl. If tag provided, includes changeTracking format.

        CRITICAL: The changeTracking object MUST be inside the formats array,
        NOT in a separate changeTrackingOptions field (Firecrawl returns 400
        for that). The tag MUST include user_id for per-user baselines.
        """
        try:
            formats: list = ["markdown"]
            if tag:
                # Tag goes inside the formats array object — see CLAUDE.md
                formats.append({"type": "changeTracking", "tag": tag})

            client = await get_http_client()
            response = await client.post(
                self.FIRECRAWL_URL,
                headers={
                    "Authorization": f"Bearer {settings.firecrawl_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "url": url,
                    "formats": formats,
                    "onlyMainContent": True
                },
                timeout=timeout
            )

            if response.status_code == 200:
                result = response.json()
                if not result.get("success", True):
                    logger.error(f"Firecrawl error: {result.get('error')} - {result.get('details')}")
                    return None
                return result.get("data", {})

            logger.error(f"Firecrawl error: {response.status_code} - {response.text}")
            return None

        except Exception as e:
            logger.error(f"Firecrawl request failed: {e}")
            return None

    async def _summarize_page(self, content: str, url: str, change_status: str = "new", language_name: str = "English") -> str:
        """Generate a brief page summary when no criteria are set."""
        if change_status == "new":
            instruction = f"Summarize this web page in 1-2 sentences. Focus on what the page covers and the type of content it contains. Write in {language_name}."
        else:
            instruction = f"Summarize what changed on this web page in 1-2 sentences. Focus on specific new or updated content. Write in {language_name}."

        try:
            client = await get_http_client()
            response = await client.post(
                self.OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "HTTP-Referer": "https://cojournalist.ai",
                    "X-Title": "coJournalist",
                    "Content-Type": "application/json"
                },
                json={
                    "model": settings.llm_model,
                    "messages": [
                        {"role": "system", "content": instruction},
                        {"role": "user", "content": f"URL: {url}\n\nPage content:\n{content}"}
                    ],
                    "max_tokens": 150,
                }
            )

            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()

            logger.error(f"OpenRouter summary error: {response.status_code} - {response.text}")
            return ""
        except Exception as e:
            logger.error(f"Page summary failed: {e}")
            return ""

    async def _analyze_changes(self, content: str, criteria: str, url: str, change_status: str = "changed", language_name: str = "English") -> dict:
        """Analyze content changes against user criteria using LLM."""
        # Adjust context based on whether this is first scrape or changed content
        if change_status == "new":
            context_line = "Current page content (first time monitoring this URL):"
        else:
            context_line = "Content that changed since last check:"

        try:
            client = await get_http_client()
            response = await client.post(
                self.OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "HTTP-Referer": "https://cojournalist.ai",
                    "X-Title": "coJournalist",
                    "Content-Type": "application/json"
                },
                json={
                    "model": settings.llm_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": f"""You analyze web page content against user monitoring criteria.
Return JSON only: {{"matches": bool, "summary": "string", "matched_url": "string or null", "matched_title": "string or null"}}

For the summary:
- Be descriptive: explain WHAT changed and WHY it's relevant
- Use emoji prefix (🔔, 📢, ⚡, 🆕, 📰) to highlight the type of change
- Keep to 1-3 sentences max
- Include specific details (numbers, names, dates) when available

For matched_url and matched_title:
- If the matching content links to a specific article or page within the markdown, extract its URL and title
- Look for markdown links like [Title](https://...) that relate to the matched criteria
- If the match is about the root page itself (not a specific linked article), return null for both
- matched_url must be a full URL (https://...), not a relative path

Write in {language_name}.
If no match, return {{"matches": false, "summary": "", "matched_url": null, "matched_title": null}}"""
                        },
                        {
                            "role": "user",
                            "content": f"""User is monitoring {url} for: {criteria}

{context_line}
{content}

Does this relate to the user's criteria? If yes, summarize the relevant content with specific details."""
                        }
                    ],
                    "max_tokens": 400,
                    "response_format": {"type": "json_object"}
                }
            )

            if response.status_code == 200:
                data = response.json()
                content_str = data["choices"][0]["message"]["content"]
                return json.loads(content_str)

            logger.error(f"OpenRouter error: {response.status_code} - {response.text}")
            return {"matches": False, "summary": ""}

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return {"matches": False, "summary": ""}
