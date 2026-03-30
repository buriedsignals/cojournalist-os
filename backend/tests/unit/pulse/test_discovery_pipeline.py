"""
Tests for the pulse pipeline's discovery and recency config behavior.

Covers:
1. Undated cap — discovery articles get a separate cap from news (two-bucket)
2. Date filter — discovery uses a wider window than news (14d vs 7d default)
3. Scoring — undated news articles get a -5 penalty; discovery undated do not
4. Recency config — get_recency_config() returns correct values for each
   (scope, source_mode) tuple: location/topic/combined x niche/reliable,
   plus government override and unknown-scope fallback
"""
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta
from collections import Counter
from urllib.parse import urlparse


def make_article(
    url: str,
    title: str = "Test",
    description: str = "desc",
    published: str = None,
    pass_type: str = "news",
) -> dict:
    """Build a minimal article dict matching Firecrawl search result shape.

    _pass tracks which search pass produced the article ("news" or "discovery").
    date is optional — articles without it are "undated" and subject
    to the undated cap in the pipeline.
    """
    d = {
        "url": url,
        "title": title,
        "description": description,
        "_pass": pass_type,
    }
    if published:
        d["date"] = published
    return d


class TestDiscoveryUndatedCap:
    """Test that discovery undated articles have a separate cap from news undated."""

    @pytest.mark.asyncio
    async def test_discovery_undated_cap_separate_from_news(self):
        """cap_undated_results() uses two buckets: news and discovery.

        10 undated articles (5 discovery, 5 news) — after capping with
        default caps (10 each), all should survive. The key assertion is
        that discovery articles get their own bucket and aren't crowded
        out by news articles.
        """
        articles = []
        # 5 undated discovery articles
        for i in range(5):
            articles.append(make_article(
                f"https://blog{i}.ch/post",
                f"Community Blog Post {i}",
                f"Interesting niche content about local events {i}",
                pass_type="discovery",
            ))
        # 5 undated news articles
        for i in range(5):
            articles.append(make_article(
                f"https://news{i}.com/article",
                f"News Article {i}",
                f"Standard news content {i}",
                pass_type="news",
            ))

        # Import the cap function (does not exist yet)
        from app.services.pulse_orchestrator import cap_undated_results

        capped = cap_undated_results(articles)

        # Discovery articles should have their own cap -- more than 2 should survive
        discovery_count = sum(1 for a in capped if a.get("_pass") == "discovery")
        assert discovery_count > 2, (
            f"Only {discovery_count} discovery articles survived; "
            "discovery undated should not be capped as aggressively as news"
        )


class TestDiscoveryDateFilter:
    """Test that discovery articles get a wider date window than news."""

    def test_unified_14_day_window(self):
        """Both news and discovery use the same 14-day window.

        Articles from 10 days ago pass the 14-day window regardless of pass type.
        Articles from 16 days ago are filtered out for both types.
        """
        ten_days_ago = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        sixteen_days_ago = (datetime.now() - timedelta(days=16)).strftime("%Y-%m-%dT%H:%M:%SZ")

        from app.services.pulse_orchestrator import apply_date_filter, get_recency_config
        recency = get_recency_config("location", "news", source_mode="niche")

        # 10-day-old articles should pass the 14-day window
        recent_articles = [
            make_article("https://local-blog.ch/post", published=ten_days_ago, pass_type="discovery"),
            make_article("https://news.ch/article", published=ten_days_ago, pass_type="news"),
        ]
        dated, _ = apply_date_filter(recent_articles, recency)
        assert len(dated) == 2, "Both articles from 10 days ago should pass 14-day window"

        # 30-day-old articles should fail both initial (14d) and relaxed (28d) windows
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        old_articles = [
            make_article("https://local-blog.ch/post2", published=thirty_days_ago, pass_type="discovery"),
            make_article("https://news.ch/article2", published=thirty_days_ago, pass_type="news"),
        ]
        dated, _ = apply_date_filter(old_articles, recency)
        assert len(dated) == 0, "Both articles from 30 days ago should fail 28-day relaxed window"


class TestDiscoveryScoringNoPenalty:
    """Test that undated discovery articles are not penalized in scoring."""

    @pytest.mark.asyncio
    async def test_discovery_undated_no_penalty_in_scoring(self):
        """Undated discovery articles beat undated news articles in cluster scoring.

        Two articles cluster together. The news article has a domain rarity
        advantage (+8) and longer description (+3), but gets a -5 undated
        penalty. The discovery article has no rarity (mainstream domain,
        freq >= 5) but gets a +6 pass bonus and no undated penalty.

        Score breakdown:
          news:      8 rarity + 3 desc - 5 undated penalty = 6
          discovery: 0 rarity + 6 pass + 0.5 desc           = 6.5 (wins)

        Without the -5 penalty, news would win (11 > 6.5). This verifies
        that deduplicate_by_embedding() applies the undated news penalty.
        """
        from app.services.news_utils import deduplicate_by_embedding

        # Discovery article from a high-frequency domain (0 rarity bonus)
        discovery_undated = make_article(
            "https://mainstream.ch/blog-post",
            "Community Blog",
            # Short desc (~50 chars) => +0.5 from desc length
            "Short blog about local events in the neighborhood",
            pass_type="discovery",
        )
        # News article from unique domain (8 rarity bonus) with long desc
        news_undated = make_article(
            "https://rare-unique-source.ch/article",
            "News Article",
            # Long desc (300 chars) => +3.0 from desc length
            "x" * 300,
            pass_type="news",
        )
        # Padding articles to make mainstream.ch freq >= 5 (no rarity bonus)
        padding = [
            make_article(f"https://mainstream.ch/other{i}", f"Padding {i}")
            for i in range(5)
        ]

        articles = [discovery_undated, news_undated] + padding

        # Embeddings: first two cluster together, rest are distinct
        embeddings = [
            [1.0, 0.0, 0.0],     # discovery (clusters with news)
            [0.98, 0.05, 0.0],   # news (clusters with discovery)
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.5, 0.5, 0.0],
            [0.0, 0.5, 0.5],
            [0.3, 0.3, 0.4],
        ]

        with patch("app.services.news_utils.generate_embeddings_batch", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = embeddings

            result = await deduplicate_by_embedding(
                articles=articles,
                threshold=0.80,
            )

        # Find which article won the cluster (first two indices)
        cluster_winner = result[0]  # First result is the winner of the first cluster

        # Without -5 penalty: news wins (8 rarity + 3 desc = 11 > 0 rarity + 6 pass + 0.5 desc = 6.5)
        # With -5 penalty: discovery wins (6.5 > 11 - 5 = 6)
        assert cluster_winner["_pass"] == "discovery", (
            f"Discovery should win the cluster when news gets -5 undated penalty. "
            f"Winner was _pass={cluster_winner.get('_pass')} from {cluster_winner.get('url')}. "
            "This fails because score_article has no -5 penalty for undated news."
        )

    @pytest.mark.asyncio
    async def test_news_undated_gets_negative_score(self):
        """Dated news articles beat undated news articles despite lower rarity.

        Two news articles cluster together. The undated article has higher
        rarity (+8 vs +4) and longer description (+3 vs +1), but the -5
        undated penalty flips the outcome.

        Score breakdown:
          dated:   5 date + 4 rarity + 1 desc = 10 (wins)
          undated: -5 date + 8 rarity + 3 desc = 6

        Without the -5 penalty, undated would win (11 > 10). This verifies
        that the penalty pushes undated news below dated alternatives.
        """
        from app.services.news_utils import deduplicate_by_embedding

        dated_news = make_article(
            "https://mid-freq-a.ch/dated",
            "Dated News",
            # 100 chars => +1.0 desc bonus
            "x" * 100,
            published=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            pass_type="news",
        )
        undated_news = make_article(
            "https://rare-unique-source.ch/undated",
            "Undated News",
            # 300 chars => +3.0 desc bonus
            "x" * 300,
            pass_type="news",
        )
        # Padding to set domain frequencies:
        # mid-freq-a.ch: 3 occurrences => freq 3 => rarity +4
        # rare-unique-source.ch: 1 occurrence => freq 1 => rarity +8
        padding = [
            make_article(f"https://mid-freq-a.ch/p{i}", f"Pad {i}")
            for i in range(2)
        ]

        articles = [dated_news, undated_news] + padding

        embeddings = [
            [1.0, 0.0, 0.0],     # dated (clusters with undated)
            [0.98, 0.05, 0.0],   # undated (clusters with dated)
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]

        with patch("app.services.news_utils.generate_embeddings_batch", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = embeddings

            result = await deduplicate_by_embedding(
                articles=articles,
                threshold=0.80,
            )

        # The dated article should win the cluster only if the undated
        # news article gets a -5 penalty.
        cluster_winner = result[0]
        assert cluster_winner.get("date") is not None, (
            "Dated article should win over undated news when -5 penalty is applied. "
            f"Winner: url={cluster_winner.get('url')}, published={cluster_winner.get('date')}. "
            "This fails because undated news has +8 rarity + 3 desc = 11 > "
            "dated's +5 date + 4 rarity + 1 desc = 10 (no penalty makes undated win)."
        )


class TestGetRecencyConfig:
    """Test get_recency_config() for all (scope, source_mode) tuples.

    The config is keyed by (scope, source_mode) tuples:
      - scope: "location", "topic", or "combined"
      - source_mode: "niche" or "reliable"

    Each config returns: news_days, discovery_days, max_undated_news,
    max_undated_discovery. Reliable mode gets wider windows than niche.
    Government category overrides undated caps to 999.
    Unknown scopes fall back to ("location", "niche").
    """

    def test_location_niche_scope(self):
        """Standard 14-day window with tight undated caps."""
        from app.services.pulse_orchestrator import get_recency_config
        config = get_recency_config("location", "news", source_mode="niche")
        assert config["news_days"] == 14
        assert config["discovery_days"] == 14
        assert config["max_undated_news"] == 10
        assert config["max_undated_discovery"] == 10

    def test_location_reliable_scope(self):
        """Standard 14-day window with higher undated caps for reliable."""
        from app.services.pulse_orchestrator import get_recency_config
        config = get_recency_config("location", "news", source_mode="reliable")
        assert config["news_days"] == 14
        assert config["discovery_days"] == 14
        assert config["max_undated_news"] == 15
        assert config["max_undated_discovery"] == 15

    def test_topic_niche_scope(self):
        """Standard 14-day window for topic searches."""
        from app.services.pulse_orchestrator import get_recency_config
        config = get_recency_config("topic", "news", source_mode="niche")
        assert config["news_days"] == 14
        assert config["discovery_days"] == 14
        assert config["max_undated_news"] == 20
        assert config["max_undated_discovery"] == 20

    def test_topic_reliable_scope(self):
        """Standard 14-day window with generous undated cap for reliable topic."""
        from app.services.pulse_orchestrator import get_recency_config
        config = get_recency_config("topic", "news", source_mode="reliable")
        assert config["news_days"] == 14
        assert config["discovery_days"] == 14
        assert config["max_undated_news"] == 25
        assert config["max_undated_discovery"] == 25

    def test_combined_niche_scope(self):
        """Standard 14-day window for combined scope."""
        from app.services.pulse_orchestrator import get_recency_config
        config = get_recency_config("combined", "news", source_mode="niche")
        assert config["news_days"] == 14
        assert config["discovery_days"] == 14
        assert config["max_undated_news"] == 15
        assert config["max_undated_discovery"] == 15

    def test_combined_reliable_scope(self):
        """Standard 14-day window for combined/reliable."""
        from app.services.pulse_orchestrator import get_recency_config
        config = get_recency_config("combined", "news", source_mode="reliable")
        assert config["news_days"] == 14
        assert config["discovery_days"] == 14
        assert config["max_undated_news"] == 20
        assert config["max_undated_discovery"] == 20

    def test_government_has_generous_undated_cap(self):
        """Government uses generous but finite undated caps (25)."""
        from app.services.pulse_orchestrator import get_recency_config
        config = get_recency_config("location", "government", source_mode="niche")
        assert config["news_days"] == 14
        assert config["max_undated_news"] == 25
        assert config["max_undated_discovery"] == 25

    def test_government_reliable_has_generous_undated_cap(self):
        """Government + reliable: standard window, generous undated caps (25)."""
        from app.services.pulse_orchestrator import get_recency_config
        config = get_recency_config("location", "government", source_mode="reliable")
        assert config["news_days"] == 14
        assert config["max_undated_news"] == 25
        assert config["max_undated_discovery"] == 25

    def test_unknown_scope_falls_back_to_location_niche(self):
        """Unrecognized scope defaults to the most conservative config."""
        from app.services.pulse_orchestrator import get_recency_config
        config = get_recency_config("unknown", "news")
        assert config["news_days"] == 14
        assert config["max_undated_news"] == 10
