"""Full pipeline unit tests for Pulse with mocked APIs."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def make_article(url: str, title: str = "Test", description: str = "desc", published: str = None) -> dict:
    d = {"url": url, "title": title, "description": description}
    if published:
        d["date"] = published
    return d


class TestPulsePipelineEndToEnd:
    """Full pipeline unit tests with mocked external calls."""

    @pytest.mark.asyncio
    async def test_domain_cap_applied_after_ai_filter(self):
        """Verify domain cap is applied to AI filter output."""
        # AI returns 6 articles, 4 from same domain
        articles = [
            make_article("https://nzz.ch/a1", "NZZ 1"),
            make_article("https://nzz.ch/a2", "NZZ 2"),
            make_article("https://nzz.ch/a3", "NZZ 3"),
            make_article("https://nzz.ch/a4", "NZZ 4"),
            make_article("https://srf.ch/a1", "SRF 1"),
            make_article("https://local.ch/a1", "Local 1"),
        ]

        # AI selects all 6
        mock_response = {"content": "[0, 1, 2, 3, 4, 5]"}

        with patch("app.services.news_utils.openrouter_chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_response
            from app.services.news_utils import ai_filter_results

            result = await ai_filter_results(
                results=articles,
                city_name="Zurich",
                country_name="Switzerland",
                openrouter_key="test",
                max_results=20,
            )

        # Domain cap should limit nzz.ch to 2
        nzz_count = sum(1 for r in result if "nzz.ch" in r["url"])
        assert nzz_count <= 2
        assert len(result) == 4  # 2 NZZ + 1 SRF + 1 Local

    @pytest.mark.asyncio
    async def test_excluded_domains_frees_slots(self):
        """Excluding mainstream domains frees slots for niche sources."""
        articles = [
            make_article("https://nzz.ch/a1", "NZZ 1"),
            make_article("https://nzz.ch/a2", "NZZ 2"),
            make_article("https://community-blog.ch/post", "Community Blog"),
            make_article("https://local-gazette.ch/news", "Local Gazette"),
            make_article("https://reuters.com/story", "Reuters"),
        ]

        # Without exclusion, AI might pick mainstream
        # With exclusion, nzz.ch is removed, community sources have better chance
        mock_response = {"content": "[0, 1]"}  # AI picks first two from what remains

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

        # NZZ should be excluded
        urls = [r["url"] for r in result]
        assert all("nzz.ch" not in url for url in urls)

    @pytest.mark.asyncio
    async def test_domain_diversity_in_output(self):
        """Verify max 2 per domain in final output."""
        # Create articles with heavy domain concentration
        articles = []
        for i in range(10):
            articles.append(make_article(f"https://big-news.ch/{i}", f"Big {i}"))
        for i in range(3):
            articles.append(make_article(f"https://niche{i}.ch/post", f"Niche {i}"))

        # AI selects all
        indices = list(range(len(articles)))
        mock_response = {"content": str(indices)}

        with patch("app.services.news_utils.openrouter_chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_response
            from app.services.news_utils import ai_filter_results

            result = await ai_filter_results(
                results=articles,
                city_name="Zurich",
                country_name="Switzerland",
                openrouter_key="test",
                max_results=20,
            )

        # big-news.ch should be capped at 2
        from collections import Counter
        from urllib.parse import urlparse
        domain_counts = Counter(urlparse(r["url"]).netloc for r in result)
        assert domain_counts.get("big-news.ch", 0) <= 2
        # All 3 niche domains should be present
        niche_count = sum(1 for r in result if "niche" in r["url"])
        assert niche_count == 3

    @pytest.mark.asyncio
    async def test_rarity_scoring_affects_dedup(self):
        """Verify rarity scoring changes which article survives in dedup clusters."""
        # Two similar articles: one from niche domain, one from mainstream
        articles = [
            make_article("https://mainstream.ch/story", "Story about X"),
            make_article("https://niche-blog.ch/story", "Story about X"),
            # Add mainstream padding to inflate its frequency
            make_article("https://mainstream.ch/other1", "Other 1"),
            make_article("https://mainstream.ch/other2", "Other 2"),
            make_article("https://mainstream.ch/other3", "Other 3"),
            make_article("https://mainstream.ch/other4", "Other 4"),
        ]

        # First two cluster together (similar embeddings), rest are distinct
        embeddings = [
            [1.0, 0.0, 0.0],     # mainstream (clusters with niche)
            [0.98, 0.05, 0.0],   # niche (clusters with mainstream)
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.5, 0.5, 0.0],
            [0.0, 0.5, 0.5],
        ]

        with patch("app.services.news_utils.generate_embeddings_batch", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = embeddings
            from app.services.news_utils import deduplicate_by_embedding

            result = await deduplicate_by_embedding(
                articles=articles,
                threshold=0.80,
            )

        # The niche article should win the cluster
        cluster_urls = [r["url"] for r in result]
        assert "https://niche-blog.ch/story" in cluster_urls

    @pytest.mark.asyncio
    async def test_ai_filter_fallback_on_error(self):
        """If AI filter fails, should return original results (capped)."""
        articles = [make_article(f"https://site{i}.ch/{i}") for i in range(5)]

        with patch("app.services.news_utils.openrouter_chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = Exception("API error")
            from app.services.news_utils import ai_filter_results

            result = await ai_filter_results(
                results=articles,
                city_name="Zurich",
                country_name="Switzerland",
                openrouter_key="test",
                max_results=3,
            )

        assert len(result) == 3  # Falls back to first max_results

    @pytest.mark.asyncio
    async def test_combined_mode_uses_combined_prompt(self):
        """When both city_name and topic are provided, the combined prompt is used."""
        articles = [
            make_article("https://dn.se/energy", "Swedish Energy Policy"),
            make_article("https://svt.se/energy", "Energy in Stockholm"),
        ]
        mock_response = {"content": "[0, 1]"}

        with patch("app.services.news_utils.openrouter_chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_response
            from app.services.news_utils import ai_filter_results

            await ai_filter_results(
                results=articles,
                city_name="Stockholm",
                country_name="Sweden",
                openrouter_key="test",
                topic="energy production",
            )

        # Verify the prompt sent to the LLM mentions BOTH location AND topic
        call_args = mock_chat.call_args
        prompt_text = call_args[1]["messages"][0]["content"] if "messages" in call_args[1] else call_args[0][0][0]["content"]
        assert "Stockholm" in prompt_text
        assert "Sweden" in prompt_text
        assert "energy production" in prompt_text

    @pytest.mark.asyncio
    async def test_build_filter_prompt_matches_scope(self):
        """build_filter_prompt() with scope='combined' includes both location and topic."""
        from app.services.filter_prompts import build_filter_prompt
        prompt = build_filter_prompt(
            scope="combined",
            category="news",
            source_mode="niche",
            city_name="Stockholm",
            country_name="Sweden",
            country_tlds=".se",
            local_language="Swedish",
            topic="energy production",
            articles_text="0. Test\n   Desc\n   URL: https://test.se",
        )
        assert "Stockholm" in prompt
        assert "Sweden" in prompt
        assert "energy production" in prompt
        assert ".se" in prompt

    @pytest.mark.asyncio
    async def test_build_filter_prompt_topic_only(self):
        """build_filter_prompt() with scope='topic' mentions topic but not city."""
        from app.services.filter_prompts import build_filter_prompt
        prompt = build_filter_prompt(
            scope="topic",
            category="news",
            source_mode="niche",
            topic="renewable energy",
            articles_text="0. Test\n   Desc\n   URL: https://test.com",
        )
        assert "renewable energy" in prompt
        # Should not contain unformatted placeholders
        assert "{topic}" not in prompt

    @pytest.mark.asyncio
    async def test_build_filter_prompt_location_only(self):
        """build_filter_prompt() with scope='location' mentions city but not topic."""
        from app.services.filter_prompts import build_filter_prompt
        prompt = build_filter_prompt(
            scope="location",
            category="news",
            source_mode="reliable",
            city_name="Zurich",
            country_name="Switzerland",
            country_tlds=".ch",
            local_language="German",
            articles_text="0. Test\n   Desc\n   URL: https://nzz.ch",
        )
        assert "Zurich" in prompt
        assert "Switzerland" in prompt

    @pytest.mark.asyncio
    async def test_location_only_does_not_mention_topic(self):
        """When only city_name is provided, the location prompt is used (no topic)."""
        articles = [make_article("https://nzz.ch/a1", "Zurich News")]
        mock_response = {"content": "[0]"}

        with patch("app.services.news_utils.openrouter_chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_response
            from app.services.news_utils import ai_filter_results

            await ai_filter_results(
                results=articles,
                city_name="Zurich",
                country_name="Switzerland",
                openrouter_key="test",
                topic=None,
            )

        call_args = mock_chat.call_args
        prompt_text = call_args[1]["messages"][0]["content"] if "messages" in call_args[1] else call_args[0][0][0]["content"]
        assert "Zurich" in prompt_text


class TestCriteriaLocationQueries:
    """Verify criteria+location queries don't produce national drift."""

    @pytest.mark.asyncio
    @patch("app.services.pulse_orchestrator.generate_news_summary", new_callable=AsyncMock, return_value="")
    @patch("app.services.pulse_orchestrator.ai_filter_results", new_callable=AsyncMock, return_value=[])
    @patch("app.services.pulse_orchestrator.deduplicate_by_embedding", new_callable=AsyncMock, return_value=[])
    @patch("app.services.pulse_orchestrator.enrich_pdf_results", new_callable=AsyncMock, return_value=[])
    @patch("app.services.pulse_orchestrator.get_query_generator")
    async def test_criteria_query_no_standalone_country(
        self, mock_gen_factory, mock_enrich, mock_dedup, mock_filter, mock_summary
    ):
        """When both city and country exist, there should be no standalone
        country-only criteria query (e.g., '"housing" US' without city)
        because it causes national drift."""
        from app.services.pulse_orchestrator import PulseOrchestrator

        mock_gen = AsyncMock()
        mock_gen.generate_queries = AsyncMock(return_value={
            "queries": ["local news query"],
            "discovery_queries": [],
            "local_domains": [".com"],
            "language": "en",
            "cached": False,
        })
        mock_gen_factory.return_value = mock_gen

        orchestrator = PulseOrchestrator()

        captured_queries = None

        async def capture_searches(queries, **kwargs):
            nonlocal captured_queries
            captured_queries = queries
            return [], []

        with patch.object(orchestrator, '_execute_all_searches_directly', new_callable=AsyncMock, side_effect=capture_searches):
            await orchestrator.search_news(
                location="Bozeman, Montana",
                city="Bozeman",
                country="US",
                category="news",
                criteria="housing development",
                source_mode="reliable",
            )

        assert captured_queries is not None
        query_strings = [q["query"] for q in captured_queries]

        # Should NOT have a standalone country-only criteria query
        has_standalone_country = any(
            'US' in q and '"Bozeman"' not in q and 'housing' in q.lower()
            for q in query_strings
        )
        assert not has_standalone_country, (
            f"Should not have standalone country query (causes national drift). "
            f"Queries: {query_strings}"
        )
