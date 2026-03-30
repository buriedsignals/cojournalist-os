"""Supabase implementation of SchedulerPort.

Uses pg_cron via asyncpg to create scheduled jobs that fire pg_net.http_post()
to the execute-scout Edge Function. The full SQL string is built in Python
(injecting the Supabase URL and service role key as literals) to avoid
relying on PostgreSQL custom GUC variables.

DEPENDS ON: connection (get_pool), config (supabase_url, supabase_service_key),
            ports.scheduler (SchedulerPort)
USED BY: dependencies/providers.py (DI wiring)
"""
from __future__ import annotations

import json
import logging

from app.adapters.supabase.connection import get_pool
from app.config import get_settings
from app.ports.scheduler import SchedulerPort

logger = logging.getLogger(__name__)


class SupabaseScheduler(SchedulerPort):
    """pg_cron-based scheduler using asyncpg."""

    def __init__(self):
        self.pool = None
        settings = get_settings()
        self.edge_function_url = f"{settings.supabase_url}/functions/v1/execute-scout"
        self.service_key = settings.supabase_service_key

    async def _ensure_pool(self):
        if self.pool is None:
            self.pool = await get_pool()

    async def create_schedule(self, schedule_name: str, cron: str,
                               target_config: dict) -> str:
        """Create a pg_cron job that triggers the execute-scout Edge Function.

        The cron job executes a SQL statement that calls pg_net.http_post()
        with the scout configuration as the request body.
        """
        await self._ensure_pool()

        headers = json.dumps({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.service_key}",
        })
        body = json.dumps(target_config)

        sql = """
            SELECT cron.schedule(
                $1,
                $2,
                format(
                    'SELECT net.http_post(
                        url := %L,
                        headers := %L::jsonb,
                        body := %L::jsonb,
                        timeout_milliseconds := 60000
                    )',
                    $3,
                    $4,
                    $5
                )
            )
        """
        await self.pool.execute(
            sql,
            schedule_name,
            cron,
            self.edge_function_url,
            headers,
            body,
        )
        logger.info(f"Created pg_cron schedule: {schedule_name} ({cron})")
        return schedule_name

    async def delete_schedule(self, schedule_name: str) -> None:
        """Remove a pg_cron job by name."""
        await self._ensure_pool()

        await self.pool.execute(
            "SELECT cron.unschedule($1)",
            schedule_name,
        )
        logger.info(f"Deleted pg_cron schedule: {schedule_name}")

    async def update_schedule(self, schedule_name: str, cron: str = None,
                               target_config: dict = None) -> None:
        """Update a schedule by deleting and recreating it.

        pg_cron does not support in-place updates, so we delete and recreate.
        """
        await self._ensure_pool()

        # Delete existing
        await self.delete_schedule(schedule_name)

        # Recreate with new parameters
        if cron and target_config:
            await self.create_schedule(schedule_name, cron, target_config)
        else:
            logger.warning(
                f"update_schedule called without cron or target_config for {schedule_name}. "
                "Schedule was deleted but not recreated."
            )
