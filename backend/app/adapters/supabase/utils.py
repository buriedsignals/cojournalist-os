"""Shared utilities for Supabase adapters."""
from typing import Optional


def row_to_dict(row, uuid_fields=("id", "user_id", "scout_id")) -> Optional[dict]:
    if row is None:
        return None
    result = dict(row)
    for key in uuid_fields:
        if key in result and result[key] is not None:
            result[key] = str(result[key])
    return result
