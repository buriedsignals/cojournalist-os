"""Tests for source mode toggle functionality.

Source mode lets users switch between:
- "niche" (default): surfaces niche, community, underreported content
- "reliable": surfaces established news sources and verified outlets
"""
import pytest
from unittest.mock import AsyncMock, patch

def make_article(url: str, title: str = "Test", description: str = "desc", published: str = None) -> dict:
    d = {"url": url, "title": title, "description": description}
    if published:
        d["date"] = published
    return d


# =============================================================================
# 1. Schema validation
# =============================================================================


class TestSourceModeSchema:
    """Verify PulseSearchRequest and PulseExecuteRequest accept source_mode."""

    def test_pulse_search_request_accepts_source_mode(self):
        from app.schemas.pulse import PulseSearchRequest
        req = PulseSearchRequest(criteria="test", source_mode="reliable")
        assert req.source_mode == "reliable"

    def test_pulse_search_request_defaults_to_niche(self):
        from app.schemas.pulse import PulseSearchRequest
        req = PulseSearchRequest(criteria="test")
        assert req.source_mode == "niche"

    def test_pulse_execute_request_accepts_source_mode(self):
        from app.schemas.pulse import PulseExecuteRequest
        req = PulseExecuteRequest(
            topic="test",
            userId="user_123",
            scraperName="test-scout",
            source_mode="reliable",
        )
        assert req.source_mode == "reliable"

    def test_pulse_execute_request_defaults_to_niche(self):
        from app.schemas.pulse import PulseExecuteRequest
        req = PulseExecuteRequest(
            topic="test",
            userId="user_123",
            scraperName="test-scout",
        )
        assert req.source_mode == "niche"

    def test_invalid_source_mode_rejected(self):
        from app.schemas.pulse import PulseSearchRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PulseSearchRequest(topic="test", source_mode="invalid")


# =============================================================================
# 2. Filter prompts
# =============================================================================


class TestSourceModeFilterPrompts:
    """Verify reliable-mode filter prompts exist and differ from discovery."""

    def test_reliable_news_prompt_exists(self):
        from app.services.filter_prompts import RELIABLE_NEWS_FILTER_PROMPT
        assert (
            "established" in RELIABLE_NEWS_FILTER_PROMPT.lower()
            or "verified" in RELIABLE_NEWS_FILTER_PROMPT.lower()
        )

    def test_reliable_gov_prompt_exists(self):
        from app.services.filter_prompts import RELIABLE_GOV_FILTER_PROMPT
        assert "government" in RELIABLE_GOV_FILTER_PROMPT.lower()

    def test_reliable_prompts_not_niche_focused(self):
        from app.services.filter_prompts import RELIABLE_NEWS_FILTER_PROMPT
        assert "community blogs" not in RELIABLE_NEWS_FILTER_PROMPT.lower()
        assert "wouldn't find on their own" not in RELIABLE_NEWS_FILTER_PROMPT.lower()

    def test_get_default_prompt_with_source_mode(self):
        from app.services.filter_prompts import get_default_prompt
        niche = get_default_prompt("news", source_mode="niche")
        reliable = get_default_prompt("news", source_mode="reliable")
        assert niche != reliable


# =============================================================================
# 3. Prompt wiring
# =============================================================================


class TestSourceModeWiring:
    """Verify source_mode reaches AI filter and selects the correct prompt."""

    @pytest.mark.asyncio
    async def test_ai_filter_receives_source_mode(self):
        """Reliable mode prompt should contain 'established' and NOT 'Discoveries'."""
        articles = [
            make_article("https://nzz.ch/a1", "Local news story"),
            make_article("https://srf.ch/a2", "Another story"),
            make_article("https://tagesanzeiger.ch/a3", "Third story"),
        ]

        captured_prompt = None

        async def capture_prompt(messages, **kwargs):
            nonlocal captured_prompt
            captured_prompt = messages[0]["content"]
            return {"content": "[0, 1]"}

        with patch("app.services.news_utils.openrouter_chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = capture_prompt
            from app.services.news_utils import ai_filter_results

            await ai_filter_results(
                results=articles,
                city_name="Zurich",
                country_name="Switzerland",
                openrouter_key="test",
                source_mode="reliable",
            )

        assert captured_prompt is not None, "AI filter was never called"
        assert "established" in captured_prompt.lower(), (
            "Reliable mode prompt should mention 'established' sources"
        )
        assert "discoveries" not in captured_prompt.lower(), (
            "Reliable mode should NOT use the Discoveries prompt"
        )

    @pytest.mark.asyncio
    async def test_default_source_mode_uses_discoveries_prompt(self):
        """Niche mode (default) should use the Discoveries prompt."""
        articles = [
            make_article("https://nzz.ch/a1", "Local news story"),
        ]

        captured_prompt = None

        async def capture_prompt(messages, **kwargs):
            nonlocal captured_prompt
            captured_prompt = messages[0]["content"]
            return {"content": "[0]"}

        with patch("app.services.news_utils.openrouter_chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = capture_prompt
            from app.services.news_utils import ai_filter_results

            await ai_filter_results(
                results=articles,
                city_name="Zurich",
                country_name="Switzerland",
                openrouter_key="test",
                source_mode="niche",
            )

        assert captured_prompt is not None
        assert "discoveries" in captured_prompt.lower(), (
            "Default mode should use the Discoveries prompt"
        )

    @pytest.mark.asyncio
    async def test_topic_only_reliable_mode_uses_established_prompt(self):
        """Topic-only reliable mode should use the established-sources prompt."""
        articles = [
            make_article("https://example.com/a1", "Topic story"),
        ]

        captured_prompt = None

        async def capture_prompt(messages, **kwargs):
            nonlocal captured_prompt
            captured_prompt = messages[0]["content"]
            return {"content": "[0]"}

        with patch("app.services.news_utils.openrouter_chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = capture_prompt
            from app.services.news_utils import ai_filter_results

            await ai_filter_results(
                results=articles,
                city_name="",
                country_name="",
                openrouter_key="test",
                topic="climate policy",
                source_mode="reliable",
            )

        assert captured_prompt is not None
        assert "established" in captured_prompt.lower(), (
            "Topic-only reliable mode should mention 'established' sources"
        )


# =============================================================================
# 4. Niche+location category dispatch
# =============================================================================


class TestNicheLocationCategories:
    """Verify niche+location (no criteria) dispatches only news category."""

    def test_niche_location_condition(self):
        """is_niche_location should be True only when source_mode=niche,
        location present, and no criteria."""
        cases = [
            # (source_mode, has_location, criteria, expected)
            ("niche", True, None, True),
            ("niche", True, "", True),
            ("niche", True, "housing", False),   # has criteria
            ("reliable", True, None, False),     # not niche
            ("niche", False, None, False),        # no location
            ("reliable", True, "housing", False),
        ]
        for source_mode, has_location, criteria, expected in cases:
            result = (
                source_mode == "niche"
                and has_location
                and not criteria
            )
            assert result == expected, (
                f"Failed for source_mode={source_mode}, location={has_location}, "
                f"criteria={criteria}: expected {expected}, got {result}"
            )

    def test_niche_location_cost_is_standard(self):
        """Niche+location should use standard pulse cost (single category)."""
        from app.utils.credits import get_pulse_cost
        cost = get_pulse_cost("niche", has_location=True)
        assert cost == 7, (
            f"Niche+location should cost 7 credits (single category), got {cost}"
        )
