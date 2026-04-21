"""Supabase implementation of PromiseStoragePort.

Uses asyncpg to execute SQL against the PostgreSQL promises table.
Implements all 6 port methods: store_promises, mark_promises_notified,
get_stored_hash, get_processed_urls, update_scraper_record, delete_promises_for_scout.

Content hash and processed URLs are stored in the scouts table config JSONB
(civic-specific fields). This avoids adding extra tables for what DynamoDB
stored as attributes on the SCRAPER# record.

DEPENDS ON: connection (get_pool), ports.storage (PromiseStoragePort)
USED BY: civic_orchestrator (via DI)
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from app.adapters.supabase.connection import get_pool
from app.adapters.supabase.utils import row_to_dict
from app.ports.storage import PromiseStoragePort

logger = logging.getLogger(__name__)


class SupabaseCivicPromiseStorage(PromiseStoragePort):
    """PostgreSQL-backed civic promise storage using asyncpg."""

    def __init__(self):
        self.pool = None

    async def _ensure_pool(self):
        if self.pool is None:
            self.pool = await get_pool()

    async def store_promises(self, user_id: str, scraper_name: str,
                              promises: list) -> None:
        """Bulk insert civic promises. Resolves scraper_name to scout_id.

        Maps Pydantic ``Promise`` fields onto the DB columns:
          * ``source_date`` (date of the council document) → ``meeting_date``
          * ``due_date`` (when the promise is due) → ``due_date``
          * ``date_confidence`` (high|medium|low) → ``date_confidence``

        The old adapter read ``p.get("meeting_date")``, which the Pydantic
        model never emits, so the meeting_date column was always NULL for
        civic promises. Reading ``source_date`` fixes that.
        """
        await self._ensure_pool()

        if not promises:
            return

        from datetime import date as date_type

        def _parse_date(raw):
            if not raw:
                return None
            if isinstance(raw, str):
                try:
                    return date_type.fromisoformat(raw)
                except ValueError:
                    return None
            return raw

        records = []
        for promise in promises:
            # Convert Pydantic models to dicts if needed
            p = promise.model_dump() if hasattr(promise, 'model_dump') else (
                promise.dict() if hasattr(promise, 'dict') else promise
            )
            meeting_date = _parse_date(p.get("source_date") or p.get("meeting_date"))
            due_date = _parse_date(p.get("due_date"))
            date_confidence = p.get("date_confidence")
            if date_confidence not in ("high", "medium", "low"):
                date_confidence = None

            records.append((
                user_id,
                scraper_name,
                user_id,
                p.get("promise_text", p.get("text", "")),
                p.get("context"),
                p.get("source_url"),
                p.get("source_title"),
                meeting_date,
                due_date,
                date_confidence,
            ))

        await self.pool.executemany(
            """
            INSERT INTO promises (
                scout_id, user_id, promise_text, context,
                source_url, source_title, meeting_date, due_date, date_confidence
            )
            VALUES (
                (SELECT id FROM scouts WHERE user_id = $1::uuid AND name = $2::text),
                $3::uuid, $4::text, $5::text, $6::text, $7::text, $8, $9, $10
            )
            """,
            records,
        )
        logger.info(f"Stored {len(records)} promises for scout {scraper_name}")

    async def mark_promises_notified(self, user_id: str, scraper_name: str,
                                      promise_ids: list[str]) -> None:
        """Mark promises as notified by updating their status."""
        await self._ensure_pool()

        if not promise_ids:
            return

        placeholders = ", ".join(f"${i+1}::uuid" for i in range(len(promise_ids)))
        await self.pool.execute(
            f"""
            UPDATE promises SET status = 'notified'
            WHERE id IN ({placeholders})
            """,
            *promise_ids,
        )

    async def get_stored_hash(self, user_id: str, scraper_name: str) -> str:
        """Get the content hash stored on the scout's config JSONB."""
        await self._ensure_pool()
        result = await self.pool.fetchval(
            """
            SELECT config->>'content_hash'
            FROM scouts
            WHERE user_id = $1::uuid AND name = $2
            """,
            user_id, scraper_name,
        )
        return result or ""

    async def get_processed_urls(self, user_id: str, scraper_name: str) -> list[str]:
        """Get the list of processed PDF URLs from scout's processed_pdf_urls column."""
        await self._ensure_pool()
        result = await self.pool.fetchval(
            """
            SELECT processed_pdf_urls
            FROM scouts
            WHERE user_id = $1::uuid AND name = $2
            """,
            user_id, scraper_name,
        )
        return result or []

    async def update_scraper_record(self, user_id: str, scraper_name: str,
                                     content_hash: str, new_processed: list[str]) -> None:
        """Update the content hash and processed URLs on the scout record."""
        await self._ensure_pool()
        await self.pool.execute(
            """
            UPDATE scouts
            SET config = config || jsonb_build_object('content_hash', $3::text),
                processed_pdf_urls = $4
            WHERE user_id = $1::uuid AND name = $2
            """,
            user_id, scraper_name, content_hash, new_processed,
        )

    async def delete_promises_for_scout(self, user_id: str, scout_name: str) -> None:
        """Delete all promises for a scout by name."""
        await self._ensure_pool()
        await self.pool.execute(
            """
            DELETE FROM promises
            WHERE user_id = $1::uuid
                AND scout_id = (SELECT id FROM scouts WHERE user_id = $1::uuid AND name = $2)
            """,
            user_id, scout_name,
        )
