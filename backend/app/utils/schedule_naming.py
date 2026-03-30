"""
Schedule naming utilities — shared between ScheduleService and Lambda functions.

These functions are replicated in three Lambda files (create-eventbridge-schedule,
scraper-lambda, delete-schedule) which are deployed as independent zips and cannot
import from this module. Keep in sync manually whenever a function changes here.

CANONICAL SOURCE for:
  aws/lambdas/create-eventbridge-schedule/lambda_function.py
  aws/lambdas/scraper-lambda/lambda_function.py
  aws/lambdas/delete-schedule/lambda_function.py
"""
from __future__ import annotations

import hashlib
import re
from decimal import Decimal
from urllib.parse import urlparse


def sanitize_name(name: str) -> str:
    """Replace non-alphanumeric chars (except - _ .) with dashes, collapse runs.

    Matches Lambda create-eventbridge-schedule sanitize_name() exactly.
    """
    sanitized = re.sub(r"[^0-9a-zA-Z\-_.]", "-", name)
    sanitized = re.sub(r"-+", "-", sanitized)
    return sanitized.strip("-")


def build_schedule_name(user_id: str, scout_name: str) -> str:
    """Build an EventBridge schedule name from user ID and scout name.

    Format: scout-{uid_prefix 12}-{sha256 8}-{sanitized_name}
    Max 64 chars (EventBridge limit).

    Matches Lambda create-eventbridge-schedule build_schedule_name() exactly.
    """
    uid = user_id.replace("user_", "")
    uid_prefix = uid[:12]
    uniqueness = hashlib.sha256(f"{user_id}:{scout_name}".encode()).hexdigest()[:8]
    name_part = sanitize_name(scout_name)
    # 64 total - "scout-" (6) - uid_prefix - "-" (1) - uniqueness (8) - "-" (1)
    max_name_len = 64 - 6 - len(uid_prefix) - 1 - 8 - 1
    name_part = name_part[:max_name_len].rstrip("-")
    if name_part:
        return f"scout-{uid_prefix}-{uniqueness}-{name_part}"
    return f"scout-{uid_prefix}-{uniqueness}"


def convert_floats_to_decimal(obj):
    """Recursively convert float values to Decimal for DynamoDB storage.

    Matches Lambda create-eventbridge-schedule convert_floats_to_decimal() exactly.
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(i) for i in obj]
    return obj


def convert_decimals(obj):
    """Convert DynamoDB Decimals to JSON-serializable types.

    Matches scraper.py _convert_decimals() exactly.
    """
    if isinstance(obj, Decimal):
        return float(obj) if obj % 1 else int(obj)
    if isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_decimals(i) for i in obj]
    return obj


def validate_url(url: str) -> bool:
    """Validate URL for SSRF protection — block localhost and private IPs.

    Based on Lambda create-eventbridge-schedule validate_url().
    Divergence: the 172.16-31.x.x check wraps int() in try/except to avoid
    crashing on malformed hostnames (e.g. "172.bad.0.1"). The Lambda version
    lets that propagate into the outer bare except; this version is explicit.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = parsed.hostname.lower() if parsed.hostname else ""
        if host in ("localhost", "127.0.0.1", "0.0.0.0"):
            return False
        if host.startswith("192.168.") or host.startswith("10."):
            return False
        if host.startswith("172."):
            try:
                second_octet = int(host.split(".")[1])
                if 16 <= second_octet <= 31:
                    return False
            except (IndexError, ValueError):
                pass
        return True
    except Exception:
        return False


def sanitize_scout_name_for_sk(name: str) -> str:
    """Replace # and | with - for use in DynamoDB sort key prefixes.

    Used for SEEN# record SK construction. EXEC# records use the raw name.
    Matches Lambda create-eventbridge-schedule sanitize_scout_name_for_sk() exactly.
    """
    return re.sub(r"[#|]", "-", name).strip()
