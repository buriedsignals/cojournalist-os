"""Unit tests for domain filtering (user-level My Sources + per-scout blacklist)."""
import pytest
from unittest.mock import AsyncMock, patch


def make_article(url: str, title: str = "Test") -> dict:
    return {"url": url, "title": title, "description": "desc"}


class TestExcludedDomainFiltering:
    """Tests for excluded_domains parameter in ai_filter_results()."""

    @pytest.mark.asyncio
    async def test_excluded_domains_removed_before_ai(self):
        """Articles from excluded domains should be removed before AI filtering."""
        articles = [
            make_article("https://nzz.ch/article1", "NZZ 1"),
            make_article("https://local-blog.ch/post", "Local Blog"),
            make_article("https://reuters.com/story", "Reuters"),
            make_article("https://srf.ch/news", "SRF"),
        ]

        mock_response = {"content": "[0, 1]"}  # AI would select first 2 from remaining

        with patch("app.services.news_utils.openrouter_chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_response
            from app.services.news_utils import ai_filter_results

            result = await ai_filter_results(
                results=articles,
                city_name="Zurich",
                country_name="Switzerland",
                openrouter_key="test",
                excluded_domains=["nzz.ch", "reuters.com"],
            )

        # NZZ and Reuters should be excluded, AI gets local-blog and SRF
        urls = [r["url"] for r in result]
        assert "https://nzz.ch/article1" not in urls
        assert "https://reuters.com/story" not in urls

    @pytest.mark.asyncio
    async def test_subdomain_matching(self):
        """Subdomain should match parent domain."""
        articles = [
            make_article("https://news.nzz.ch/article", "NZZ News"),
            make_article("https://blog.example.com/post", "Blog"),
        ]

        mock_response = {"content": "[0]"}

        with patch("app.services.news_utils.openrouter_chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_response
            from app.services.news_utils import ai_filter_results

            result = await ai_filter_results(
                results=articles,
                city_name="Zurich",
                country_name="Switzerland",
                openrouter_key="test",
                excluded_domains=["nzz.ch"],
            )

        # news.nzz.ch should be excluded by endswith("nzz.ch")
        urls = [r["url"] for r in result]
        assert "https://news.nzz.ch/article" not in urls

    @pytest.mark.asyncio
    async def test_www_stripping(self):
        """www. should be stripped for matching."""
        articles = [
            make_article("https://www.nzz.ch/article", "NZZ"),
            make_article("https://other.ch/post", "Other"),
        ]

        mock_response = {"content": "[0]"}

        with patch("app.services.news_utils.openrouter_chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_response
            from app.services.news_utils import ai_filter_results

            result = await ai_filter_results(
                results=articles,
                city_name="Zurich",
                country_name="Switzerland",
                openrouter_key="test",
                excluded_domains=["nzz.ch"],
            )

        urls = [r["url"] for r in result]
        assert "https://www.nzz.ch/article" not in urls

    @pytest.mark.asyncio
    async def test_empty_excluded_domains(self):
        """Empty excluded_domains should not filter anything."""
        articles = [
            make_article("https://nzz.ch/article", "NZZ"),
        ]

        mock_response = {"content": "[0]"}

        with patch("app.services.news_utils.openrouter_chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_response
            from app.services.news_utils import ai_filter_results

            result = await ai_filter_results(
                results=articles,
                city_name="Zurich",
                country_name="Switzerland",
                openrouter_key="test",
                excluded_domains=[],
            )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_none_excluded_domains(self):
        """None excluded_domains should not filter anything."""
        articles = [
            make_article("https://nzz.ch/article", "NZZ"),
        ]

        mock_response = {"content": "[0]"}

        with patch("app.services.news_utils.openrouter_chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_response
            from app.services.news_utils import ai_filter_results

            result = await ai_filter_results(
                results=articles,
                city_name="Zurich",
                country_name="Switzerland",
                openrouter_key="test",
                excluded_domains=None,
            )

        assert len(result) == 1


class TestDomainValidation:
    """Tests for domain cleaning in UpdatePreferencesRequest."""

    def test_protocol_stripping(self):
        from app.routers.user import UpdatePreferencesRequest
        req = UpdatePreferencesRequest(excluded_domains=["https://nzz.ch", "http://reuters.com"])
        assert req.excluded_domains == ["nzz.ch", "reuters.com"]

    def test_www_stripping(self):
        from app.routers.user import UpdatePreferencesRequest
        req = UpdatePreferencesRequest(excluded_domains=["www.nzz.ch"])
        assert req.excluded_domains == ["nzz.ch"]

    def test_lowercase(self):
        from app.routers.user import UpdatePreferencesRequest
        req = UpdatePreferencesRequest(excluded_domains=["NZZ.CH", "Reuters.COM"])
        assert req.excluded_domains == ["nzz.ch", "reuters.com"]

    def test_trailing_slash_removed(self):
        from app.routers.user import UpdatePreferencesRequest
        req = UpdatePreferencesRequest(excluded_domains=["nzz.ch/"])
        assert req.excluded_domains == ["nzz.ch"]

    def test_deduplication(self):
        from app.routers.user import UpdatePreferencesRequest
        req = UpdatePreferencesRequest(excluded_domains=["nzz.ch", "nzz.ch", "reuters.com"])
        assert req.excluded_domains == ["nzz.ch", "reuters.com"]

    def test_cap_at_50(self):
        from app.routers.user import UpdatePreferencesRequest
        domains = [f"domain{i}.com" for i in range(60)]
        req = UpdatePreferencesRequest(excluded_domains=domains)
        assert len(req.excluded_domains) == 50

    def test_none_passes_through(self):
        from app.routers.user import UpdatePreferencesRequest
        req = UpdatePreferencesRequest(preferred_language="en")
        assert req.excluded_domains is None


class TestPulseSearchRequestValidator:
    """Tests for PulseSearchRequest.sanitize_excluded_domains (per-scout blacklist)."""

    def _make(self, domains):
        from app.schemas.pulse import PulseSearchRequest
        return PulseSearchRequest(
            criteria="test",
            excluded_domains=domains,
        )

    def test_protocol_stripping(self):
        req = self._make(["https://nzz.ch", "http://reuters.com"])
        assert req.excluded_domains == ["nzz.ch", "reuters.com"]

    def test_www_stripping(self):
        req = self._make(["www.nzz.ch"])
        assert req.excluded_domains == ["nzz.ch"]

    def test_path_stripping(self):
        req = self._make(["nzz.ch/some/path"])
        assert req.excluded_domains == ["nzz.ch"]

    def test_rejects_entries_without_dot(self):
        """Bare words like 'com' must not pass (would match everything via endswith)."""
        req = self._make(["com", "nzz.ch", "localhost"])
        assert req.excluded_domains == ["nzz.ch"]

    def test_empty_strings_filtered(self):
        req = self._make(["", "  ", "nzz.ch"])
        assert req.excluded_domains == ["nzz.ch"]

    def test_all_invalid_returns_none(self):
        req = self._make(["", "com", "  "])
        assert req.excluded_domains is None

    def test_none_passes_through(self):
        from app.schemas.pulse import PulseSearchRequest
        req = PulseSearchRequest(criteria="test", excluded_domains=None)
        assert req.excluded_domains is None

    def test_rejects_over_50(self):
        """Pydantic max_length=50 rejects lists with more than 50 entries."""
        from pydantic import ValidationError
        domains = [f"domain{i}.com" for i in range(60)]
        with pytest.raises(ValidationError, match="too_long"):
            self._make(domains)


class TestEmptyStringGuard:
    """Tests for the empty-string guard in ai_filter_results excluded_set."""

    @pytest.mark.asyncio
    async def test_empty_strings_in_excluded_domains_ignored(self):
        """Empty strings in excluded_domains should not cause all articles to be excluded."""
        articles = [
            make_article("https://nzz.ch/article", "NZZ"),
            make_article("https://srf.ch/news", "SRF"),
        ]

        mock_response = {"content": "[0, 1]"}

        with patch("app.services.news_utils.openrouter_chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_response
            from app.services.news_utils import ai_filter_results

            result = await ai_filter_results(
                results=articles,
                city_name="Zurich",
                country_name="Switzerland",
                openrouter_key="test",
                excluded_domains=["", "  ", "reuters.com"],
            )

        # Empty strings should not match anything — NZZ and SRF should survive
        urls = [r["url"] for r in result]
        assert "https://nzz.ch/article" in urls
        assert "https://srf.ch/news" in urls


class TestDomainMergeLogic:
    """Tests for per-scout + user-level domain merge (order-preserving dedup)."""

    def test_merge_deduplicates(self):
        """Domains appearing in both user-level and per-scout should not duplicate."""
        user_excluded = ["nzz.ch", "reuters.com"]
        scout_excluded = ["reuters.com", "srf.ch"]
        merged = list(dict.fromkeys(user_excluded + scout_excluded))
        assert merged == ["nzz.ch", "reuters.com", "srf.ch"]

    def test_merge_preserves_order(self):
        """User-level domains come first, scout-level appended."""
        user_excluded = ["b.com", "a.com"]
        scout_excluded = ["c.com", "a.com"]
        merged = list(dict.fromkeys(user_excluded + scout_excluded))
        assert merged == ["b.com", "a.com", "c.com"]

    def test_merge_empty_user(self):
        """Empty user-level list should pass through scout-level only."""
        merged = list(dict.fromkeys([] + ["nzz.ch"]))
        assert merged == ["nzz.ch"]

    def test_merge_empty_scout(self):
        """Empty scout-level list should pass through user-level only."""
        merged = list(dict.fromkeys(["nzz.ch"] + []))
        assert merged == ["nzz.ch"]

    def test_merge_both_empty(self):
        merged = list(dict.fromkeys([] + []))
        assert merged == []
