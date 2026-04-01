"""
Shared execute pipeline for pulse router.

PURPOSE: Extracts the common post-orchestrator steps that pulse router
endpoints share, preventing code duplication between search and execute paths.

DEPENDS ON: dependencies (credit decrement), atomic_unit_service (fact extraction
    + dedup), execution_deduplication (EXEC# records), news_utils (lang_name),
    utils/logging (structured logging)
USED BY: routers/pulse.py

Pipeline steps:
1. Fetch recent facts for cross-run dedup + prompt injection
2. Process results through atomic unit service (fact extraction + dedup)
3. Generate and store EXEC# summary
4. Handle duplicate-only early return
5. Decrement credit
6. Log scout execution

The orchestrator call itself is type-specific and remains in each router.
The notification call is also type-specific and handled via a callback.
"""
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Awaitable, Optional

from app.dependencies import decrement_credit
from app.services.atomic_unit_service import AtomicUnitService, ProcessingResult
from app.services.execution_deduplication import ExecutionDeduplicationService
from app.services.news_utils import lang_name
from app.utils.logging import log_scout_execution

logger = logging.getLogger(__name__)

# Lazy-initialized service instances (providers must be ready before instantiation).
# These are module-level attributes so tests can patch them directly.
atomic_unit_service = None
exec_dedup_service = None


def _ensure_services():
    """Initialize service singletons on first use."""
    global atomic_unit_service, exec_dedup_service
    if atomic_unit_service is None:
        atomic_unit_service = AtomicUnitService()
    if exec_dedup_service is None:
        exec_dedup_service = ExecutionDeduplicationService()


def build_recent_findings(recent_facts: list[dict], limit: int = 10) -> list[dict]:
    """
    Convert recent facts into the format expected by orchestrator prompts.

    Takes the top `limit` facts that have a truthy "statement" field and
    wraps each in a {"summary_text": ...} dict for prompt injection.
    """
    return [
        {"summary_text": f["statement"]}
        for f in recent_facts[:limit]
        if f.get("statement")
    ]


async def fetch_recent_facts(
    user_id: str,
    scout_id: str,
    scout_type: str,
) -> tuple[list[dict], list[dict]]:
    """
    Fetch recent facts and build recent_findings for orchestrator prompt injection.

    Returns:
        (recent_facts, recent_findings) tuple
    """
    _ensure_services()
    recent_facts = await atomic_unit_service.get_recent_facts(
        user_id=user_id,
        scout_id=scout_id,
    )
    if recent_facts:
        logger.info(f"[{scout_type.capitalize()}] Retrieved {len(recent_facts)} recent facts for dedup/prompt")

    recent_findings = build_recent_findings(recent_facts)
    return recent_facts, recent_findings


@dataclass
class PipelineContext:
    """Common context needed by the shared pipeline steps."""
    user_id: str
    scraper_name: str
    scout_type: str  # "pulse"
    location: object  # GeocodedLocation or None
    topic: Optional[str]
    preferred_language: str
    start_time: float
    credit_cost: int
    skip_credit_charge: bool = False
    skip_unit_extraction: bool = False
    team_org_id: Optional[str] = None


@dataclass
class PipelineResult:
    """Result of the shared pipeline, used by routers to build their response."""
    processing_result: ProcessingResult
    exec_summary: str
    notification_sent: bool
    all_duplicates: bool


async def run_post_orchestrator_pipeline(
    articles: list[dict],
    ctx: PipelineContext,
    recent_facts: list[dict],
    user_email: Optional[str],
    send_notification: Callable[[ProcessingResult, str, Optional[str]], Awaitable[bool]],
    extra_log_fields: Optional[dict] = None,
) -> PipelineResult:
    """
    Run the shared post-orchestrator pipeline steps.

    This handles everything after the type-specific orchestrator returns results:
    1. Process results through atomic unit service (fact extraction + dedup)
    2. Generate EXEC# summary from new facts
    3. Store EXEC# record
    4. Handle all-duplicates case (credit decrement, logging, early return)
    5. Send notification via type-specific callback
    6. Decrement credit
    7. Log execution

    Args:
        articles: List of article dicts with title, summary, url, content keys.
        ctx: Common pipeline context (user_id, scraper_name, scout_type, etc.)
        recent_facts: Recent facts from previous runs (for cross-run dedup).
        user_email: User's email address (None to skip notification).
        send_notification: Async callback that sends the type-specific notification.
            Receives (processing_result, exec_summary, user_email) and returns bool.
        extra_log_fields: Additional fields to merge into the log entry.

    Returns:
        PipelineResult with processing outcome and notification status.
    """
    _ensure_services()
    started_at = datetime.utcnow().isoformat() + "Z"

    # Step 1: Process results with fact-level cross-run dedup
    if not ctx.skip_unit_extraction:
        processing_result: ProcessingResult = await atomic_unit_service.process_results(
            results=[{
                "title": a.get("title", ""),
                "summary": a.get("summary", ""),
                "url": a.get("url", ""),
                "content": a.get("summary", ""),
                "date": a.get("date"),
            } for a in articles],
            scout_id=ctx.scraper_name,
            scout_type=ctx.scout_type,
            user_id=ctx.user_id,
            location=ctx.location,
            topic=ctx.topic,
            language=lang_name(ctx.preferred_language),
            recent_facts=recent_facts,
        )
    else:
        logger.info(f"[{ctx.scout_type.capitalize()}] Skipping unit extraction for {ctx.scraper_name} (initial run)")
        processing_result = ProcessingResult(
            new_facts=[],
            duplicate_facts=[],
            all_duplicates=True,
        )

    # Step 2: Generate EXEC# summary from new facts only
    if processing_result.new_facts:
        exec_summary = await exec_dedup_service.generate_summary_from_facts(
            new_facts=processing_result.new_facts
        )
    else:
        exec_summary = "No new findings"

    # Step 3: Store EXEC# record
    await exec_dedup_service.store_execution(
        user_id=ctx.user_id,
        scout_name=ctx.scraper_name,
        scout_type=ctx.scout_type,
        summary_text=exec_summary,
        is_duplicate=processing_result.all_duplicates,
        started_at=started_at,
    )

    # Step 4: All duplicates - decrement credit, log, return early
    if processing_result.all_duplicates:
        logger.info(
            f"[{ctx.scout_type.capitalize()}] All facts are duplicates for {ctx.scraper_name} "
            f"({len(processing_result.duplicate_facts)} duplicates) - skipping notification"
        )
        if not ctx.skip_credit_charge:
            await decrement_credit(
                ctx.user_id, ctx.credit_cost, org_id=ctx.team_org_id,
                operation=ctx.scout_type, scout_name=ctx.scraper_name,
                scout_type=ctx.scout_type,
            )

        duration_ms = (time.time() - ctx.start_time) * 1000
        log_fields = {
            "duplicate": True,
            "duplicate_facts": len(processing_result.duplicate_facts),
        }
        if extra_log_fields:
            log_fields.update(extra_log_fields)
        log_scout_execution(
            scout_type=ctx.scout_type,
            user_id=ctx.user_id,
            scraper_name=ctx.scraper_name,
            status="success",
            duration_ms=duration_ms,
            extra=log_fields,
        )

        return PipelineResult(
            processing_result=processing_result,
            exec_summary=exec_summary,
            notification_sent=False,
            all_duplicates=True,
        )

    # Step 5: Send notification via type-specific callback
    notification_sent = await send_notification(processing_result, exec_summary, user_email)

    # Step 6: Decrement credits
    if not ctx.skip_credit_charge:
        await decrement_credit(
            ctx.user_id, ctx.credit_cost, org_id=ctx.team_org_id,
            operation=ctx.scout_type, scout_name=ctx.scraper_name,
            scout_type=ctx.scout_type,
        )

    # Step 7: Log execution
    duration_ms = (time.time() - ctx.start_time) * 1000
    log_fields = {
        "new_facts": len(processing_result.new_facts),
        "duplicate_facts": len(processing_result.duplicate_facts),
    }
    if extra_log_fields:
        log_fields.update(extra_log_fields)
    log_scout_execution(
        scout_type=ctx.scout_type,
        user_id=ctx.user_id,
        scraper_name=ctx.scraper_name,
        status="success",
        duration_ms=duration_ms,
        extra=log_fields,
    )

    return PipelineResult(
        processing_result=processing_result,
        exec_summary=exec_summary,
        notification_sent=notification_sent,
        all_duplicates=False,
    )
