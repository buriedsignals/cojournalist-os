"""Unit tests for summary language instruction."""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_summary_prompt_includes_english_language_instruction():
    """When language='en', prompt should still say 'Write in English'."""
    from app.services.news_utils import generate_news_summary

    captured_prompt = {}

    async def mock_chat(messages, **kwargs):
        captured_prompt["content"] = messages[0]["content"]
        return {"content": "📰 Test bullet [Source](url)"}

    articles = [{"title": "Umweltaktivisten", "url": "https://example.ch/a", "description": "German text here"}]

    with patch("app.services.news_utils.openrouter_chat", side_effect=mock_chat):
        await generate_news_summary(articles, "Schaffhausen", "fake-key", "news", "en")

    assert "English" in captured_prompt["content"], \
        "Prompt must explicitly instruct to write in English"


@pytest.mark.asyncio
async def test_summary_prompt_includes_german_language_instruction():
    """When language='de', prompt should say 'Write in German'."""
    from app.services.news_utils import generate_news_summary

    captured_prompt = {}

    async def mock_chat(messages, **kwargs):
        captured_prompt["content"] = messages[0]["content"]
        return {"content": "📰 Test bullet [Source](url)"}

    articles = [{"title": "Test", "url": "https://example.ch/a", "description": "Test"}]

    with patch("app.services.news_utils.openrouter_chat", side_effect=mock_chat):
        await generate_news_summary(articles, "Schaffhausen", "fake-key", "news", "de")

    assert "German" in captured_prompt["content"]


@pytest.mark.asyncio
async def test_summary_prompt_includes_swedish_language_instruction():
    """When language='sv', prompt should say 'Write in Swedish'."""
    from app.services.news_utils import generate_news_summary

    captured_prompt = {}

    async def mock_chat(messages, **kwargs):
        captured_prompt["content"] = messages[0]["content"]
        return {"content": "📰 Test bullet [Source](url)"}

    articles = [{"title": "Test", "url": "https://example.se/a", "description": "Test"}]

    with patch("app.services.news_utils.openrouter_chat", side_effect=mock_chat):
        await generate_news_summary(articles, "Malmö", "fake-key", "news", "sv")

    assert "Swedish" in captured_prompt["content"]
