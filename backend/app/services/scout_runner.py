"""
Scout Runner — executes scout runs and stores TIME# records.

Delegates storage to ScoutStoragePort (read config) and RunStoragePort (store results),
selected at runtime based on DEPLOYMENT_TARGET.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

import httpx

from app.config import get_settings
from app.utils.schedule_naming import convert_decimals

logger = logging.getLogger(__name__)


class ScoutRunner:
    """Executes scout runs and stores run records."""

    def __init__(self, scout_storage=None, run_storage=None) -> None:
        if scout_storage is None:
            from app.dependencies.providers import get_scout_storage
            scout_storage = get_scout_storage()
        if run_storage is None:
            from app.dependencies.providers import get_run_storage
            run_storage = get_run_storage()
        self.scout_storage = scout_storage
        self.run_storage = run_storage
        settings = get_settings()
        self.internal_service_key = settings.internal_service_key

    async def run_scout(self, user_id: str, scraper_name: str) -> dict:
        """Manually trigger a scout execution."""
        # 1. Read scout config via adapter
        item = await self.scout_storage.get_scout(user_id, scraper_name)
        if not item:
            return {"error": "Scout not found", "scraper_status": False}

        scout_type = item.get("scout_type", "web")
        preferred_language = item.get("preferred_language", "en")

        # 2. Build payload by scout type
        port = os.environ.get("PORT", "8000")
        base_url = f"http://127.0.0.1:{port}/api"
        headers = {"X-Service-Key": self.internal_service_key}

        if scout_type == "web":
            endpoint = f"{base_url}/scouts/execute"
            body = {
                "url": item.get("url", ""),
                "criteria": item.get("criteria", ""),
                "userId": user_id,
                "scraperName": scraper_name,
                "preferredLanguage": preferred_language,
                "skip_credit_charge": True,
            }
            if item.get("provider"):
                body["provider"] = item["provider"]
            if item.get("location"):
                body["location"] = convert_decimals(item["location"])
            if item.get("topic"):
                body["topic"] = item["topic"]
        elif scout_type == "pulse":
            endpoint = f"{base_url}/pulse/execute"
            body = {
                "userId": user_id,
                "scraperName": scraper_name,
                "preferred_language": preferred_language,
                "skip_credit_charge": True,
            }
            if item.get("location"):
                body["location"] = convert_decimals(item["location"])
            if item.get("topic"):
                body["topic"] = item["topic"]
            if item.get("excluded_domains"):
                body["excluded_domains"] = item["excluded_domains"]
            if item.get("source_mode"):
                body["source_mode"] = item["source_mode"]
            if item.get("criteria"):
                body["criteria"] = item["criteria"]
        elif scout_type == "social":
            endpoint = f"{base_url}/social/execute"
            body = {
                "userId": user_id,
                "scraperName": scraper_name,
                "platform": item.get("platform", "instagram"),
                "profile_handle": item.get("profile_handle", ""),
                "monitor_mode": item.get("monitor_mode", "summarize"),
                "track_removals": item.get("track_removals", False),
                "preferred_language": preferred_language,
                "skip_credit_charge": True,
            }
            if item.get("criteria"):
                body["criteria"] = item["criteria"]
        elif scout_type == "civic":
            endpoint = f"{base_url}/civic/execute"
            body = {
                "user_id": user_id,
                "scraper_name": scraper_name,
                "tracked_urls": item.get("tracked_urls", []),
                "criteria": item.get("criteria", ""),
                "language": item.get("preferred_language", "en"),
            }
        else:
            return {
                "error": f"Unsupported scout type: {scout_type}",
                "scraper_status": False,
            }

        # 3. Call internal endpoint
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.post(endpoint, json=body, headers=headers)

            if resp.status_code != 200:
                logger.error(
                    "Internal execute call failed (%s): %s",
                    resp.status_code, resp.text,
                )
                result_dict = {
                    "scraper_status": False,
                    "criteria_status": False,
                    "summary": f"Execution failed (status {resp.status_code})",
                }
            else:
                result_dict = resp.json()
                if scout_type == "civic":
                    civic = result_dict
                    result_dict = {
                        "scraper_status": civic.get("status") != "error",
                        "criteria_status": civic.get("promises_found", 0) > 0,
                        "summary": civic.get("summary", ""),
                        "notification_sent": civic.get("promises_found", 0) > 0,
                    }
        except Exception as exc:
            logger.exception(
                "Run scout failed for %s/%s: %s",
                user_id, scraper_name, exc,
            )
            result_dict = {
                "scraper_status": False,
                "criteria_status": False,
                "summary": f"Error: {str(exc)}",
            }

        # 4. Store run record via adapter
        try:
            await self._store_time_record(user_id, scraper_name, scout_type, result_dict)
        except Exception as exc:
            logger.error("Failed to store run record: %s", exc)

        return result_dict

    async def _store_time_record(
        self,
        user_id: str,
        scraper_name: str,
        scout_type: str,
        result: dict,
    ) -> None:
        """Store run record for scout execution history."""
        status = "success" if result.get("scraper_status") else "error"
        await self.run_storage.store_run(
            scout_id=scraper_name,
            user_id=user_id,
            status=status,
            scout_type=scout_type,
            scraper_name=scraper_name,
            scraper_status=result.get("scraper_status", False),
            criteria_status=result.get("criteria_status", False),
            notification_sent=result.get("notification_sent", False),
        )
