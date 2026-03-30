"""
LLM chat client with multi-provider routing and retry logic.

PURPOSE: Single entry point for all LLM chat completions. Routes to
the appropriate provider based on model name:
- Gemini models (gemini-*): Google AI direct API (fastest)
- All others: OpenRouter (broad model catalog)

Handles retries with exponential backoff for transient failures (429, 5xx).
Supports JSON response format for structured outputs.

DEPENDS ON: config (API keys), http_client (connection pooling)
USED BY: services/execution_deduplication.py, services/email_translations.py,
    services/news_utils.py, services/atomic_unit_service.py
"""
import asyncio
import logging
from typing import Optional

import httpx

from app.config import settings
from app.services.http_client import get_llm_client

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"


def _is_gemini_model(model: str) -> bool:
    """Check if a model should be routed to Gemini direct API."""
    return model.startswith("gemini-") or model.startswith("models/gemini-")


async def openrouter_chat(
    messages: list,
    model: str = None,
    max_tokens: int = 500,
    response_format: Optional[dict] = None,
    temperature: Optional[float] = None,
    max_retries: int = 3,
    tools: Optional[list] = None,
    tool_choice=None,
) -> dict:
    """
    Call LLM chat API with retry logic and exponential backoff.

    Routes to Gemini direct API for gemini-* models, OpenRouter for all others.

    Args:
        messages: List of chat messages
        model: Model to use (default: settings.llm_model)
        max_tokens: Maximum tokens in response
        response_format: Optional response format (e.g., {"type": "json_object"})
        temperature: Optional temperature setting
        max_retries: Maximum number of retry attempts (default: 3)
        tools: Optional list of tool definitions (OpenAI format)
        tool_choice: Optional tool choice strategy (e.g., "auto")

    Returns:
        When tools are provided: full API response dict (choices, usage, etc.)
        Otherwise: dict with "content" key containing the response text

    Raises:
        Exception: If all retries fail
    """
    model = model or settings.llm_model
    use_gemini = _is_gemini_model(model)

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens
    }

    if response_format:
        payload["response_format"] = response_format

    if temperature is not None:
        payload["temperature"] = temperature

    if tools is not None:
        payload["tools"] = tools

    if tool_choice is not None:
        payload["tool_choice"] = tool_choice

    if use_gemini:
        url = GEMINI_URL
        headers = {
            "Authorization": f"Bearer {settings.gemini_api_key}",
            "Content-Type": "application/json",
        }
        provider_label = "Gemini"
    else:
        url = OPENROUTER_URL
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "HTTP-Referer": "https://cojournalist.ai",
            "X-Title": "coJournalist",
            "Content-Type": "application/json",
        }
        provider_label = "OpenRouter"

    last_error = None
    client = await get_llm_client()

    for attempt in range(max_retries):
        try:
            response = await client.post(
                url,
                headers=headers,
                json=payload
            )

            if response.status_code == 200:
                data = response.json()

                # Log token usage
                usage = data.get("usage")
                if usage:
                    logger.info(
                        f"{provider_label} {model}: "
                        f"{usage.get('prompt_tokens')} in / "
                        f"{usage.get('completion_tokens')} out"
                    )

                # When tools are provided, return full response for tool call handling
                if tools is not None:
                    return data

                result = {
                    "content": data["choices"][0]["message"]["content"]
                }
                if usage:
                    result["usage"] = usage
                return result

            # Don't retry 4xx client errors (except rate limits)
            if response.status_code < 500 and response.status_code != 429:
                error_text = response.text[:200]
                raise Exception(f"{provider_label} client error {response.status_code}: {error_text}")

            last_error = f"HTTP {response.status_code}: {response.text[:200]}"

        except httpx.TimeoutException as e:
            last_error = f"Timeout: {e}"
        except httpx.RequestError as e:
            last_error = f"Request error: {e}"
        except Exception as e:
            # Re-raise non-retryable exceptions
            if "client error" in str(e).lower():
                raise
            last_error = str(e)

        # Exponential backoff before retry
        if attempt < max_retries - 1:
            delay = 2 ** attempt
            logger.warning(
                f"{provider_label} attempt {attempt + 1}/{max_retries} failed: {last_error}. "
                f"Retrying in {delay}s..."
            )
            await asyncio.sleep(delay)

    logger.error(f"{provider_label} failed after {max_retries} attempts: {last_error}")
    raise Exception(f"{provider_label} failed after {max_retries} attempts: {last_error}")
