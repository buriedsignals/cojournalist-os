"""
Firecrawl API client for data extraction with async polling.

PURPOSE: Submit extraction jobs to Firecrawl v2 API and poll for completion
with exponential backoff. Used exclusively for the Scrape sidebar service
(structured data extraction), NOT for Smart Scout search or Page Scout
scraping (those use FirecrawlTools in news_utils.py and direct API calls
in scout_service.py respectively).

DEPENDS ON: (httpx + asyncio only — no app imports)
USED BY: workflows/data_extractor.py, routers/data_extractor.py
"""

import asyncio
from typing import Dict, Any, Optional, AsyncGenerator
import httpx


class FirecrawlError(Exception):
    """Custom exception for Firecrawl API errors."""
    pass


class FirecrawlClient:
    """
    Client for interacting with Firecrawl API v2.
    Supports async job submission and polling for completion.
    """

    BASE_URL = "https://api.firecrawl.dev/v2"
    INITIAL_POLL_INTERVAL = 2  # seconds
    MAX_POLL_INTERVAL = 10  # seconds
    POLL_MULTIPLIER = 1.5
    TIMEOUT_SECONDS = 600  # 10 minutes

    def __init__(self, api_key: str):
        """
        Initialize Firecrawl client.

        Args:
            api_key: Firecrawl API authentication key
        """
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    async def start_extraction(
        self,
        url: str,
        prompt: str
    ) -> str:
        """
        Start a data extraction job.

        Args:
            url: URL to extract data from
            prompt: Extraction prompt/target describing what data to extract

        Returns:
            Job ID for polling

        Raises:
            FirecrawlError: If API request fails
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.BASE_URL}/extract",
                    headers=self.headers,
                    json={
                        "urls": [url],
                        "prompt": prompt,
                        "enableWebSearch": False
                    }
                )
                response.raise_for_status()
                data = response.json()

                if "id" not in data:
                    raise FirecrawlError(f"No job ID in response: {data}")

                return data["id"]

            except httpx.HTTPStatusError as e:
                error_detail = e.response.text
                raise FirecrawlError(
                    f"Failed to start extraction: {e.response.status_code} - {error_detail}"
                )
            except httpx.RequestError as e:
                raise FirecrawlError(f"Request failed: {str(e)}")

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get the status of an extraction job.

        Args:
            job_id: The job ID to check

        Returns:
            Job status data including status field and data if completed

        Raises:
            FirecrawlError: If API request fails
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/extract/{job_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                error_detail = e.response.text
                raise FirecrawlError(
                    f"Failed to get job status: {e.response.status_code} - {error_detail}"
                )
            except httpx.RequestError as e:
                raise FirecrawlError(f"Request failed: {str(e)}")

    async def poll_until_complete(self, job_id: str) -> Dict[str, Any]:
        """
        Poll job status until completion or timeout.

        Args:
            job_id: The job ID to poll

        Returns:
            Completed job data

        Raises:
            FirecrawlError: If job fails, times out, or API error occurs
        """
        start_time = asyncio.get_event_loop().time()
        current_interval = self.INITIAL_POLL_INTERVAL

        while (asyncio.get_event_loop().time() - start_time) < self.TIMEOUT_SECONDS:
            status_data = await self.get_job_status(job_id)
            status = status_data.get("status")

            if status == "completed":
                return status_data

            if status == "failed":
                error_msg = status_data.get("error", "Unknown error")
                raise FirecrawlError(f"Extraction job failed: {error_msg}")

            # Wait before next poll
            await asyncio.sleep(current_interval)
            
            # Adaptive polling: increase interval up to max
            current_interval = min(
                current_interval * self.POLL_MULTIPLIER,
                self.MAX_POLL_INTERVAL
            )

        # Timeout reached
        raise FirecrawlError(
            f"Extraction job timed out after {self.TIMEOUT_SECONDS} seconds"
        )

    async def extract_and_wait(
        self,
        url: str,
        prompt: str
    ) -> Dict[str, Any]:
        """
        Start extraction and wait for completion.

        This is the main method that combines job submission and polling.

        Args:
            url: URL to extract data from
            prompt: Extraction prompt describing what data to extract

        Returns:
            Extracted data from the completed job

        Raises:
            FirecrawlError: If any step fails
        """
        job_id = await self.start_extraction(url, prompt)
        result = await self.poll_until_complete(job_id)

        # Extract the data field from result
        if "data" not in result:
            raise FirecrawlError(f"No data in completed job: {result}")

        return result["data"]

    def calculate_progress(self, elapsed_time: float) -> int:
        """
        Calculate progress percentage based on elapsed time vs timeout.
        
        Args:
            elapsed_time: Time elapsed in seconds since start

        Returns:
            Progress percentage (0-95)
        """
        # Logarithmic-like progress: fast at first, slows down as it approaches timeout
        # Using a simple ratio for now but capped at 95%
        progress_ratio = elapsed_time / self.TIMEOUT_SECONDS
        
        # Make it feel faster initially: 
        # If 10% of timeout passed, show 20% progress
        # If 50% of timeout passed, show 80% progress
        adjusted_progress = progress_ratio ** 0.5  # Square root makes small numbers bigger (0.01 -> 0.1)
        
        percentage = int(adjusted_progress * 100)
        
        # Ensure we start at least at 5% and cap at 95%
        return max(5, min(percentage, 95))

    def get_status_message(self, status: str, elapsed_time: float) -> str:
        """
        Generate user-friendly status message based on job status.

        Args:
            status: Job status from Firecrawl API
            elapsed_time: Time elapsed in seconds

        Returns:
            User-friendly status message
        """
        status_messages = {
            "queued": "Extraction queued, waiting to start...",
            "processing": "Extracting data from webpage...",
            "completed": "Extraction complete!",
            "failed": "Extraction failed"
        }

        base_message = status_messages.get(status, "Processing extraction...")

        # Add time indicator for long-running jobs
        if status == "processing" and elapsed_time > 60:
            elapsed_min = int(elapsed_time // 60)
            base_message = f"Extracting data... ({elapsed_min}m elapsed)"

        return base_message

    async def poll_with_progress(
        self,
        job_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Poll job status and yield progress updates.

        Args:
            job_id: The job ID to poll

        Yields:
            Progress updates with structure:
            {
                "status": "queued|processing|completed|failed",
                "progress": 0-100,
                "message": "User-friendly status message",
                "elapsed": elapsed seconds,
                "data": job data (only when completed)
            }

        Raises:
            FirecrawlError: If job fails or times out
        """
        start_time = asyncio.get_event_loop().time()
        current_interval = self.INITIAL_POLL_INTERVAL

        while (asyncio.get_event_loop().time() - start_time) < self.TIMEOUT_SECONDS:
            status_data = await self.get_job_status(job_id)
            status = status_data.get("status")
            
            elapsed = asyncio.get_event_loop().time() - start_time

            # Calculate progress
            progress = self.calculate_progress(elapsed)
            message = self.get_status_message(status, elapsed)

            # Yield progress update
            yield {
                "status": status,
                "progress": progress,
                "message": message,
                "elapsed": elapsed
            }

            # Check completion
            if status == "completed":
                # Final progress update with data
                yield {
                    "status": "completed",
                    "progress": 100,
                    "message": "Extraction complete!",
                    "elapsed": elapsed,
                    "data": status_data.get("data")
                }
                return

            if status == "failed":
                error_msg = status_data.get("error", "Unknown error")
                raise FirecrawlError(f"Extraction job failed: {error_msg}")

            # Wait before next poll
            await asyncio.sleep(current_interval)
            
            # Adaptive polling
            current_interval = min(
                current_interval * self.POLL_MULTIPLIER,
                self.MAX_POLL_INTERVAL
            )

        # Timeout reached
        raise FirecrawlError(
            f"Extraction job timed out after {self.TIMEOUT_SECONDS} seconds"
        )
