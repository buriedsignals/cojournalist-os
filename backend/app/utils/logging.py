"""
Shared logging utilities for structured JSON logging.

PURPOSE: Emit structured log entries for scout executions so logs can
be parsed and analyzed consistently. Standardizes the log format across
all scout types.

DEPENDS ON: (stdlib only)
USED BY: services/execute_pipeline.py
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def log_scout_execution(
    scout_type: str,
    user_id: str,
    scraper_name: str,
    status: str,
    duration_ms: float,
    extra: Optional[dict] = None
) -> None:
    """
    Emit structured log for scout execution.

    Args:
        scout_type: Type of scout (web, beat)
        user_id: MuckRock user UUID
        scraper_name: Name of the scraper/scout
        status: Execution status (success, error)
        duration_ms: Execution duration in milliseconds
        extra: Additional fields to include in the log entry
    """
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event": "scout_execution",
        "scout_type": scout_type,
        "user_id": user_id,
        "scraper_name": scraper_name,
        "status": status,
        "duration_ms": duration_ms,
        **(extra or {})
    }
    logger.info(json.dumps(log_entry))
