"""Shared utilities for Supabase adapters."""
import json
from datetime import datetime, date
from typing import Optional


_JSONB_FIELDS = {"location", "config", "metadata", "posts", "entities", "preferences", "default_location"}


def row_to_dict(row, uuid_fields=("id", "user_id", "scout_id")) -> Optional[dict]:
    if row is None:
        return None
    result = dict(row)
    for key in uuid_fields:
        if key in result and result[key] is not None:
            result[key] = str(result[key])
    # Parse JSONB fields that asyncpg may return as strings
    for key in _JSONB_FIELDS:
        if key in result and isinstance(result[key], str):
            try:
                result[key] = json.loads(result[key])
            except (json.JSONDecodeError, TypeError):
                pass
    # Convert datetime objects to ISO strings for JSON serialization
    for key, value in result.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, date):
            result[key] = value.isoformat()
    return result
