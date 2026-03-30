"""Unit tests for recency hardening: undated article cap + date relaxation."""
import pytest
from datetime import datetime, timedelta


def make_article(url: str, title: str = "Test", published: str = None, pass_type: str = "news") -> dict:
    d = {"url": url, "title": title, "description": "desc", "_pass": pass_type}
    if published:
        d["date"] = published
    return d


class TestUndatedCap:

    def test_undated_capped_at_two(self):
        from app.services.pulse_orchestrator import cap_undated_results
        undated = [make_article(f"https://u{i}.ch/a") for i in range(5)]
        capped = cap_undated_results(undated, max_undated=2)
        # 5 news undated → capped to 2
        assert len(capped) == 2

    def test_undated_cap_preserves_order(self):
        from app.services.pulse_orchestrator import cap_undated_results
        undated = [make_article(f"https://u{i}.ch/a", title=f"Undated {i}") for i in range(5)]
        capped = cap_undated_results(undated, max_undated=2)
        assert capped[0]["title"] == "Undated 0"
        assert capped[1]["title"] == "Undated 1"

    def test_undated_cap_no_effect_when_under_limit(self):
        from app.services.pulse_orchestrator import cap_undated_results
        undated = [make_article("https://u0.ch/a")]
        capped = cap_undated_results(undated, max_undated=2)
        assert len(capped) == 1

    def test_undated_cap_zero_undated(self):
        from app.services.pulse_orchestrator import cap_undated_results
        capped = cap_undated_results([], max_undated=2)
        assert len(capped) == 0


class TestGovernmentUndatedCap:
    """Government category uses generous but finite undated caps."""

    def test_government_undated_respects_cap(self):
        from app.services.pulse_orchestrator import cap_undated_results
        undated = [make_article(f"https://gov{i}.ch/a", pass_type="news") for i in range(30)]
        result = cap_undated_results(undated, max_undated=25, category="government")
        assert len(result) == 25

    def test_government_undated_cap_from_config(self):
        from app.services.pulse_orchestrator import get_recency_config
        config = get_recency_config("location", "government", "niche")
        assert config["max_undated_news"] == 25
        assert config["max_undated_discovery"] == 25

    def test_news_undated_still_capped(self):
        from app.services.pulse_orchestrator import cap_undated_results
        undated = [make_article(f"https://news{i}.ch/a") for i in range(10)]
        result = cap_undated_results(undated, max_undated=2, category="news")
        assert len(result) == 2


def _date_str(days_ago):
    """Return an ISO date string for N days ago."""
    return (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


class TestDateRelaxation:
    """Verify progressive date relaxation when all dated results are too old."""

    def test_all_configs_use_14_day_window(self):
        """All scope/mode combos should use 14-day news window."""
        from app.services.pulse_orchestrator import get_recency_config
        for scope in ["location", "topic", "combined"]:
            for source_mode in ["niche", "reliable"]:
                config = get_recency_config(scope, "news", source_mode)
                assert config["news_days"] == 14, f"{scope}/{source_mode} news_days != 14"

    def test_relaxation_recovers_articles_in_extended_window(self):
        """When 0 articles pass 14d window but some are within 28d,
        relaxation should recover them."""
        from app.services.pulse_orchestrator import apply_date_filter, get_recency_config
        recency = get_recency_config("combined", "news", source_mode="reliable")
        assert recency["news_days"] == 14

        articles = [
            make_article(f"https://example.com/{i}", published=_date_str(20))
            for i in range(3)
        ]

        dated, undated = apply_date_filter(articles, recency)
        assert len(dated) == 3
        assert len(undated) == 0

    def test_relaxation_does_not_trigger_when_results_exist(self):
        """When some articles pass the initial window, no relaxation needed."""
        from app.services.pulse_orchestrator import apply_date_filter, get_recency_config
        recency = get_recency_config("combined", "news", source_mode="reliable")

        articles = [
            make_article("https://example.com/recent", published=_date_str(5)),
            make_article("https://example.com/old", published=_date_str(20)),
        ]

        dated, undated = apply_date_filter(articles, recency)
        assert len(dated) == 1
        assert dated[0]["url"] == "https://example.com/recent"

    def test_relaxation_uses_28_day_fallback(self):
        """Relaxed window should be 28 days, not 2x the initial window."""
        from app.services.pulse_orchestrator import apply_date_filter, get_recency_config
        recency = get_recency_config("location", "news", source_mode="niche")
        assert recency["news_days"] == 14

        # 25 days old — outside 14d, inside 28d
        articles = [make_article("https://example.com/1", published=_date_str(25))]
        dated, undated = apply_date_filter(articles, recency)
        assert len(dated) == 1

        # 30 days old — outside 28d
        articles = [make_article("https://example.com/2", published=_date_str(30))]
        dated, undated = apply_date_filter(articles, recency)
        assert len(dated) == 0

    def test_relaxation_capped_at_absolute_staleness(self):
        """Relaxed window should not exceed absolute_staleness_days."""
        from app.services.pulse_orchestrator import apply_date_filter, get_recency_config
        recency = get_recency_config("topic", "news", source_mode="reliable")
        assert recency["news_days"] == 14

        # Article 25 days old — within 28d but outside absolute cap of 20d
        articles = [make_article("https://example.com/1", published=_date_str(25))]
        dated, undated = apply_date_filter(articles, recency, absolute_staleness_days=20)
        assert len(dated) == 0

    def test_relaxation_respects_90d_floor(self):
        """Articles beyond 90-day absolute floor are never recovered."""
        from app.services.pulse_orchestrator import apply_date_filter, get_recency_config
        recency = get_recency_config("combined", "news", source_mode="reliable")

        articles = [make_article("https://example.com/1", published=_date_str(100))]
        dated, undated = apply_date_filter(articles, recency)
        assert len(dated) == 0

    def test_undated_articles_unaffected_by_relaxation(self):
        """Undated articles go to undated_results regardless of relaxation."""
        from app.services.pulse_orchestrator import apply_date_filter, get_recency_config
        recency = get_recency_config("combined", "news", source_mode="reliable")

        articles = [make_article("https://example.com/no-date")]
        dated, undated = apply_date_filter(articles, recency)
        assert len(dated) == 0
        assert len(undated) == 1

    def test_discovery_pass_recovered_by_28d_fallback(self):
        """Discovery-pass articles are recovered by the 28-day fallback."""
        from app.services.pulse_orchestrator import apply_date_filter, get_recency_config
        recency = get_recency_config("location", "news", source_mode="niche")
        assert recency["discovery_days"] == 14

        # 25 days old discovery article: outside 14d, inside 28d fallback
        articles = [
            make_article("https://example.com/1", published=_date_str(25), pass_type="discovery"),
        ]
        dated, undated = apply_date_filter(articles, recency)
        assert len(dated) == 1

    def test_no_relaxation_when_all_undated(self):
        """When all articles lack dates, relaxation should not trigger."""
        from app.services.pulse_orchestrator import apply_date_filter, get_recency_config
        recency = get_recency_config("combined", "news", source_mode="reliable")

        articles = [make_article(f"https://example.com/{i}") for i in range(3)]
        dated, undated = apply_date_filter(articles, recency)
        assert len(dated) == 0
        assert len(undated) == 3
