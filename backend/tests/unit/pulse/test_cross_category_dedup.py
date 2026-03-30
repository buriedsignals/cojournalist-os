"""Unit tests for cross-category deduplication between news and government results."""
import pytest
from unittest.mock import AsyncMock, patch


def make_article(url: str, title: str, summary: str = "desc") -> dict:
    return {"url": url, "title": title, "summary": summary}


class TestCrossCategoryDedup:

    @pytest.mark.asyncio
    async def test_duplicate_removed_from_news(self):
        """Government article with gov keywords should stay; duplicate removed from news."""
        news = [make_article("https://local.ch/story", "City Council approves budget")]
        gov = [make_article("https://gov.ch/budget", "Municipal council budget approval")]
        embeddings = [[1.0, 0.0], [0.98, 0.05]]

        with patch("app.services.news_utils.generate_embeddings_batch", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = embeddings
            from app.services.news_utils import cross_category_dedup
            result_news, result_gov = await cross_category_dedup(news, gov, )

        assert len(result_gov) == 1
        assert len(result_news) == 0

    @pytest.mark.asyncio
    async def test_duplicate_removed_from_gov(self):
        """Non-government article should stay in news; duplicate removed from gov."""
        news = [make_article("https://blog.ch/music", "Local music festival announced")]
        gov = [make_article("https://events.ch/music", "Music festival in the city")]
        embeddings = [[1.0, 0.0], [0.98, 0.05]]

        with patch("app.services.news_utils.generate_embeddings_batch", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = embeddings
            from app.services.news_utils import cross_category_dedup
            result_news, result_gov = await cross_category_dedup(news, gov, )

        assert len(result_news) == 1
        assert len(result_gov) == 0

    @pytest.mark.asyncio
    async def test_no_duplicates_pass_through(self):
        """Dissimilar articles should all pass through unchanged."""
        news = [make_article("https://blog.ch/tech", "Tech startup raises funding")]
        gov = [make_article("https://gov.ch/roads", "Road construction announced by mayor")]
        embeddings = [[1.0, 0.0], [0.0, 1.0]]

        with patch("app.services.news_utils.generate_embeddings_batch", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = embeddings
            from app.services.news_utils import cross_category_dedup
            result_news, result_gov = await cross_category_dedup(news, gov, )

        assert len(result_news) == 1
        assert len(result_gov) == 1

    @pytest.mark.asyncio
    async def test_empty_categories(self):
        """Empty input categories should return empty without errors."""
        with patch("app.services.news_utils.generate_embeddings_batch", new_callable=AsyncMock) as mock_embed:
            from app.services.news_utils import cross_category_dedup
            r_n, r_g = await cross_category_dedup([], [], )
            assert r_n == [] and r_g == []
            mock_embed.assert_not_called()

            r_n, r_g = await cross_category_dedup([make_article("https://a.ch/1", "A")], [], )
            assert len(r_n) == 1 and r_g == []
            mock_embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_articles_partial_overlap(self):
        """Only the overlapping pair should be deduped; other articles survive."""
        news = [
            make_article("https://a.ch/1", "Unique tech story"),
            make_article("https://a.ch/2", "Council meeting summary"),
        ]
        gov = [
            make_article("https://b.ch/1", "Municipal council meeting"),
            make_article("https://b.ch/2", "Unique policy announcement"),
        ]
        embeddings = [
            [1.0, 0.0, 0.0],   # news[0] - unique
            [0.0, 1.0, 0.0],   # news[1] - overlaps with gov[0]
            [0.0, 0.98, 0.05], # gov[0] - overlaps with news[1]
            [0.0, 0.0, 1.0],   # gov[1] - unique
        ]

        with patch("app.services.news_utils.generate_embeddings_batch", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = embeddings
            from app.services.news_utils import cross_category_dedup
            result_news, result_gov = await cross_category_dedup(news, gov, )

        assert len(result_news) == 1
        assert result_news[0]["url"] == "https://a.ch/1"
        assert len(result_gov) == 2
