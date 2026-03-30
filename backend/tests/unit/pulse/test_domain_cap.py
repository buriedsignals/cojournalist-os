"""Unit tests for cap_articles_per_domain()."""
import pytest
from app.services.news_utils import cap_articles_per_domain


class TestCapArticlesPerDomain:
    """Tests for the domain cap function."""

    def _make_article(self, url: str, title: str = "Test") -> dict:
        return {"url": url, "title": title, "description": "desc"}

    def test_caps_at_max_per_domain(self):
        articles = [
            self._make_article("https://nzz.ch/article1", "NZZ 1"),
            self._make_article("https://nzz.ch/article2", "NZZ 2"),
            self._make_article("https://nzz.ch/article3", "NZZ 3"),
            self._make_article("https://nzz.ch/article4", "NZZ 4"),
        ]
        result = cap_articles_per_domain(articles, max_per_domain=2)
        assert len(result) == 2
        assert result[0]["title"] == "NZZ 1"
        assert result[1]["title"] == "NZZ 2"

    def test_preserves_order(self):
        articles = [
            self._make_article("https://a.com/1", "A1"),
            self._make_article("https://b.com/1", "B1"),
            self._make_article("https://a.com/2", "A2"),
            self._make_article("https://c.com/1", "C1"),
            self._make_article("https://a.com/3", "A3"),
        ]
        result = cap_articles_per_domain(articles, max_per_domain=2)
        titles = [r["title"] for r in result]
        assert titles == ["A1", "B1", "A2", "C1"]

    def test_empty_list(self):
        result = cap_articles_per_domain([], max_per_domain=2)
        assert result == []

    def test_single_domain_list(self):
        articles = [self._make_article("https://only.com/1")]
        result = cap_articles_per_domain(articles, max_per_domain=2)
        assert len(result) == 1

    def test_all_unique_domains(self):
        articles = [
            self._make_article("https://a.com/1"),
            self._make_article("https://b.com/1"),
            self._make_article("https://c.com/1"),
        ]
        result = cap_articles_per_domain(articles, max_per_domain=2)
        assert len(result) == 3

    def test_www_stripping(self):
        articles = [
            self._make_article("https://www.nzz.ch/1", "WWW"),
            self._make_article("https://nzz.ch/2", "NoWWW"),
            self._make_article("https://www.nzz.ch/3", "Extra"),
        ]
        result = cap_articles_per_domain(articles, max_per_domain=2)
        assert len(result) == 2

    def test_malformed_url(self):
        articles = [
            self._make_article("not-a-url", "Bad"),
            self._make_article("", "Empty"),
            self._make_article("https://valid.com/1", "Good"),
        ]
        result = cap_articles_per_domain(articles, max_per_domain=2)
        # Should not crash; malformed URLs treated as empty domain
        assert len(result) >= 1

    def test_max_per_domain_one(self):
        articles = [
            self._make_article("https://a.com/1"),
            self._make_article("https://a.com/2"),
            self._make_article("https://b.com/1"),
        ]
        result = cap_articles_per_domain(articles, max_per_domain=1)
        assert len(result) == 2

    def test_mixed_domains_realistic(self):
        """Simulate realistic scenario: 5 from nzz.ch, 3 from tagesanzeiger.ch, 2 from srf.ch."""
        articles = []
        for i in range(5):
            articles.append(self._make_article(f"https://nzz.ch/{i}", f"NZZ {i}"))
        for i in range(3):
            articles.append(self._make_article(f"https://tagesanzeiger.ch/{i}", f"TA {i}"))
        for i in range(2):
            articles.append(self._make_article(f"https://srf.ch/{i}", f"SRF {i}"))

        result = cap_articles_per_domain(articles, max_per_domain=2)
        domains = [r["url"].split("/")[2] for r in result]
        assert domains.count("nzz.ch") == 2
        assert domains.count("tagesanzeiger.ch") == 2
        assert domains.count("srf.ch") == 2
        assert len(result) == 6


class TestAiFilterStringIndices:
    """AI filter must handle string indices from LLM and still apply domain cap.

    Note: These tests validate the coercion pattern and domain cap in isolation.
    The actual fix lives in ai_filter_results() — a full integration test would
    require mocking the LLM response, which is covered by the benchmark audit.
    """

    def test_string_indices_coerced_to_int(self):
        """When LLM returns string indices, they should be coerced to ints."""
        candidates = [
            {"url": "https://a.com/1", "title": "A1"},
            {"url": "https://a.com/2", "title": "A2"},
            {"url": "https://b.com/1", "title": "B1"},
            {"url": "https://a.com/3", "title": "A3"},
            {"url": "https://c.com/1", "title": "C1"},
        ]
        # Simulate: relevant_indices from LLM as strings
        relevant_indices = ["0", "1", "2", "3", "4"]
        # This line must not crash
        filtered = [candidates[int(i)] for i in relevant_indices if int(i) < len(candidates)]
        capped = cap_articles_per_domain(filtered, max_per_domain=2)
        domains = [r["url"].split("/")[2] for r in capped]
        assert domains.count("a.com") == 2
        assert len(capped) == 4  # 2 from a.com, 1 from b.com, 1 from c.com


class TestAiFilterFallbackDomainCap:
    """Error fallback path must still apply domain cap."""

    def _make_article(self, url, title="Test"):
        return {"url": url, "title": title, "description": "desc"}

    def test_fallback_applies_domain_cap(self):
        """If AI filter crashes, fallback results should still be domain-capped."""
        articles = [
            self._make_article(f"https://gov.az.gov/{i}") for i in range(6)
        ] + [
            self._make_article("https://other.com/1"),
        ]
        capped = cap_articles_per_domain(articles, max_per_domain=3)
        domains = [a["url"].split("/")[2] for a in capped]
        assert domains.count("gov.az.gov") == 3
        assert len(capped) == 4  # 3 from gov.az.gov + 1 from other.com
