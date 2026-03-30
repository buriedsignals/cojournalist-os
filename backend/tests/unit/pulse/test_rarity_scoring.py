"""Unit tests for domain-rarity scoring in deduplicate_by_embedding()."""
import pytest
from unittest.mock import AsyncMock, patch
import numpy as np


def make_article(url: str, title: str = "Test", description: str = "desc", published: str = None) -> dict:
    d = {"url": url, "title": title, "description": description}
    if published:
        d["date"] = published
    return d


class TestRarityScoring:
    """Tests for domain-rarity bonus values in score_article."""

    @pytest.mark.asyncio
    async def test_rarity_bonus_single_occurrence(self):
        """Domain appearing once should get +8 bonus."""
        articles = [
            make_article("https://niche-blog.ch/article", "Niche"),
            make_article("https://mainstream.ch/a1", "MS1"),
            make_article("https://mainstream.ch/a2", "MS2"),
            make_article("https://mainstream.ch/a3", "MS3"),
            make_article("https://mainstream.ch/a4", "MS4"),
            make_article("https://mainstream.ch/a5", "MS5"),
        ]

        # Generate distinct embeddings so each article is its own cluster
        embeddings = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.5, 0.5, 0.0],
            [0.0, 0.5, 0.5],
            [0.5, 0.0, 0.5],
        ]

        with patch("app.services.news_utils.generate_embeddings_batch", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = embeddings
            from app.services.news_utils import deduplicate_by_embedding
            result = await deduplicate_by_embedding(articles)

        # All articles should survive (distinct embeddings = no clusters)
        assert len(result) == 6

    @pytest.mark.asyncio
    async def test_rarity_changes_cluster_winner(self):
        """When two articles are in the same cluster, rarity bonus should change which one survives."""
        # Two articles that will cluster together (high similarity)
        # One from a niche domain (1 occurrence = +8), one from mainstream (5 occurrences = +0)
        niche = make_article("https://local-blog.ch/story", "Local Story", "A local community report")
        mainstream = make_article("https://big-news.ch/story", "Big Story", "A similar report")

        # Add more mainstream articles to inflate its frequency
        padding = [
            make_article("https://big-news.ch/other1", "Other 1", "x" * 100),
            make_article("https://big-news.ch/other2", "Other 2", "x" * 100),
            make_article("https://big-news.ch/other3", "Other 3", "x" * 100),
            make_article("https://big-news.ch/other4", "Other 4", "x" * 100),
        ]

        articles = [mainstream, niche] + padding

        # First two have very similar embeddings (will cluster), rest are distinct
        embeddings = [
            [1.0, 0.0, 0.0],   # mainstream (cluster with niche)
            [0.99, 0.05, 0.0],  # niche (cluster with mainstream)
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.5, 0.5, 0.0],
            [0.0, 0.5, 0.5],
        ]

        with patch("app.services.news_utils.generate_embeddings_batch", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = embeddings
            from app.services.news_utils import deduplicate_by_embedding
            result = await deduplicate_by_embedding(articles, threshold=0.80)

        # The niche article should win the cluster (rarity bonus +8 vs +0)
        cluster_winner_urls = [r["url"] for r in result]
        assert "https://local-blog.ch/story" in cluster_winner_urls

    @pytest.mark.asyncio
    async def test_rarity_bonus_tiers(self):
        """Verify different frequency tiers get correct bonuses."""
        from collections import Counter
        from urllib.parse import urlparse

        articles = [
            make_article("https://once.ch/a"),          # freq 1 → +8
            make_article("https://twice.ch/a"),          # freq 2 → +6
            make_article("https://twice.ch/b"),
            make_article("https://three.ch/a"),          # freq 3 → +4
            make_article("https://three.ch/b"),
            make_article("https://three.ch/c"),
            make_article("https://five.ch/a"),           # freq 5 → +0
            make_article("https://five.ch/b"),
            make_article("https://five.ch/c"),
            make_article("https://five.ch/d"),
            make_article("https://five.ch/e"),
        ]

        domain_freq = Counter(
            urlparse(a.get("url", "")).netloc.replace("www.", "")
            for a in articles
        )

        expected = {
            "once.ch": 8,
            "twice.ch": 6,
            "three.ch": 4,
            "five.ch": 0,
        }

        for domain, expected_bonus in expected.items():
            freq = domain_freq[domain]
            if freq == 1:
                bonus = 8
            elif freq == 2:
                bonus = 6
            elif freq <= 4:
                bonus = 4
            else:
                bonus = 0
            assert bonus == expected_bonus, f"Domain {domain} (freq={freq}) expected bonus {expected_bonus}, got {bonus}"

    @pytest.mark.asyncio
    async def test_discovery_pass_bonus(self):
        """Articles tagged with _pass='discovery' should get +6 bonus and win clusters over news."""
        # Discovery article from niche domain (1 occurrence)
        niche = make_article("https://local-blog.ch/story", "Local Blog Post", "Community report")
        niche["_pass"] = "discovery"

        # News article from same niche domain (to equalize rarity)
        news = make_article("https://news-site.ch/story", "News Coverage", "Same story from news")
        news["_pass"] = "news"

        articles = [news, niche]

        # Both cluster together (similar embeddings)
        embeddings = [
            [1.0, 0.0, 0.0],   # news
            [0.99, 0.05, 0.0],  # discovery (clusters with news)
        ]

        with patch("app.services.news_utils.generate_embeddings_batch", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = embeddings
            from app.services.news_utils import deduplicate_by_embedding
            result = await deduplicate_by_embedding(articles, threshold=0.80)

        # Discovery article should win the cluster (discovery +6 bonus)
        assert len(result) == 1
        assert result[0]["url"] == "https://local-blog.ch/story"

    @pytest.mark.asyncio
    async def test_cluster_size_preserved(self):
        """Dedup should set _cluster_size on surviving articles."""
        # Three articles that cluster together + two singletons
        articles = [
            make_article("https://a.ch/1", "Story A1"),
            make_article("https://b.ch/1", "Story A2"),
            make_article("https://c.ch/1", "Story A3"),
            make_article("https://unique.ch/1", "Unique Story"),
        ]

        embeddings = [
            [1.0, 0.0, 0.0],    # cluster of 3
            [0.99, 0.05, 0.0],   # cluster of 3
            [0.98, 0.08, 0.0],   # cluster of 3
            [0.0, 1.0, 0.0],     # singleton
        ]

        with patch("app.services.news_utils.generate_embeddings_batch", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = embeddings
            from app.services.news_utils import deduplicate_by_embedding
            result = await deduplicate_by_embedding(articles, threshold=0.80)

        # Should have 2 results: one from the cluster of 3, one singleton
        assert len(result) == 2

        cluster_sizes = {r.get("_cluster_size", 1) for r in result}
        assert 3 in cluster_sizes, "Expected a cluster of size 3"
        assert 1 in cluster_sizes, "Expected a singleton"

    @pytest.mark.asyncio
    async def test_undated_article_gets_penalty(self):
        """Undated article should lose to dated article in same cluster due to recency penalty."""
        # Two articles from unique domains (freq=1, +8 rarity each).
        # One dated (published), one undated.
        # Dated: +5 (date) + 8 (rarity) = 13
        # Undated: -5 (penalty) + 8 (rarity) = 3
        dated = make_article("https://dated-source.ch/story", "Dated Story", published="2026-03-01T10:00:00Z")
        undated = make_article("https://undated-source.ch/story", "Undated Story")

        articles = [undated, dated]

        # Similar embeddings so they cluster together
        embeddings = [
            [1.0, 0.0, 0.0],    # undated
            [0.99, 0.05, 0.0],   # dated (clusters with undated)
        ]

        with patch("app.services.news_utils.generate_embeddings_batch", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = embeddings
            from app.services.news_utils import deduplicate_by_embedding
            result = await deduplicate_by_embedding(articles, threshold=0.80)

        # The dated article should win the cluster
        assert len(result) == 1
        assert result[0]["url"] == "https://dated-source.ch/story"

    @pytest.mark.asyncio
    async def test_dated_mainstream_beats_undated_niche(self):
        """Dated mainstream article should beat undated niche article in same cluster.

        Undated niche: -5 (penalty) + 8 (freq=1 rarity) = 3
        Dated mainstream: +5 (date) + 0 (freq=5 rarity) = 5
        """
        undated_niche = make_article("https://niche-blog.ch/story", "Niche Story")
        dated_mainstream = make_article("https://big-news.ch/story", "Mainstream Story", published="2026-03-01T10:00:00Z")

        # 4 padding articles from mainstream domain to inflate its frequency to 5
        padding = [
            make_article("https://big-news.ch/other1", "Other 1", description="x" * 100),
            make_article("https://big-news.ch/other2", "Other 2", description="x" * 100),
            make_article("https://big-news.ch/other3", "Other 3", description="x" * 100),
            make_article("https://big-news.ch/other4", "Other 4", description="x" * 100),
        ]

        articles = [undated_niche, dated_mainstream] + padding

        # First two cluster together, rest are distinct
        embeddings = [
            [1.0, 0.0, 0.0],    # undated niche (cluster)
            [0.99, 0.05, 0.0],   # dated mainstream (cluster)
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.5, 0.5, 0.0],
            [0.0, 0.5, 0.5],
        ]

        with patch("app.services.news_utils.generate_embeddings_batch", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = embeddings
            from app.services.news_utils import deduplicate_by_embedding
            result = await deduplicate_by_embedding(articles, threshold=0.80)

        # The dated mainstream article should win the cluster
        cluster_winner_urls = [r["url"] for r in result]
        assert "https://big-news.ch/story" in cluster_winner_urls


class TestThresholdBoundary:
    """Tests that the 0.80 threshold correctly merges same-event articles while keeping different events separate."""

    @pytest.mark.asyncio
    async def test_same_event_merged_at_080(self):
        """Two articles about the same event (~0.82 similarity) should merge into 1 result."""
        articles = [
            make_article("https://source-a.ch/immigration", "City passes immigration ordinance"),
            make_article("https://source-b.ch/immigration", "Immigration enforcement ordinance approved"),
        ]

        # Vectors with ~0.82 cosine similarity (above 0.80 threshold → merged)
        embeddings = [
            [1.0, 0.0, 0.0],
            [0.82, 0.5724, 0.0],
        ]

        with patch("app.services.news_utils.generate_embeddings_batch", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = embeddings
            from app.services.news_utils import deduplicate_by_embedding
            result = await deduplicate_by_embedding(articles, threshold=0.80)

        assert len(result) == 1, f"Expected 1 result (merged), got {len(result)}"

    @pytest.mark.asyncio
    async def test_different_events_not_merged_at_080(self):
        """Two articles about different events (~0.77 similarity) should both survive."""
        articles = [
            make_article("https://source-a.ch/budget", "City approves annual budget"),
            make_article("https://source-b.ch/park", "New city park breaks ground"),
        ]

        # Vectors with ~0.77 cosine similarity (below 0.80 threshold → not merged)
        embeddings = [
            [1.0, 0.0, 0.0],
            [0.77, 0.6380, 0.0],
        ]

        with patch("app.services.news_utils.generate_embeddings_batch", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = embeddings
            from app.services.news_utils import deduplicate_by_embedding
            result = await deduplicate_by_embedding(articles, threshold=0.80)

        assert len(result) == 2, f"Expected 2 results (not merged), got {len(result)}"
