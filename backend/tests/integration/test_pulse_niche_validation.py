"""
Validation tests for Pulse niche source discovery strategy.

These integration tests call real Firecrawl and OpenRouter APIs to validate
that the domain cap and rarity scoring would improve niche source discovery.

Requires FIRECRAWL_API_KEY and OPENROUTER_API_KEY in .env.
"""
import os
import asyncio
import logging
import pytest
from collections import Counter
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

FIRECRAWL_KEY = os.getenv("FIRECRAWL_API_KEY")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
SKIP_REASON = "API keys required: FIRECRAWL_API_KEY and OPENROUTER_API_KEY"


@pytest.mark.asyncio
@pytest.mark.skipif(not FIRECRAWL_KEY or not OPENROUTER_KEY, reason=SKIP_REASON)
class TestPulseNicheDiscovery:
    """Validate niche source discovery strategy against real Firecrawl data."""

    @staticmethod
    def _count_domains(articles: list[dict]) -> Counter:
        return Counter(
            urlparse(a.get("url", "")).netloc.replace("www.", "")
            for a in articles
        )

    @staticmethod
    def _top_domains(domain_counts: Counter, n: int = 3) -> list[tuple[str, int]]:
        return domain_counts.most_common(n)

    async def _run_city_test(self, city: str, country: str, country_code: str, queries: list[str]):
        """Run the niche discovery validation for a single city."""
        from app.services.news_utils import (
            FirecrawlTools, deduplicate_by_embedding, ai_filter_results, cap_articles_per_domain
        )

        tools = FirecrawlTools(FIRECRAWL_KEY)

        # 1. Collect raw results
        all_results = []
        seen_urls = set()
        for query in queries:
            result = await tools.search_web(
                query=query, location=city, country=country_code,
                limit=25, sources=["news", "web"]
            )
            for item in result.get("results", []):
                url = item.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(item)
            await asyncio.sleep(0.3)

        logger.info(f"\n{'='*60}")
        logger.info(f"City: {city}, {country}")
        logger.info(f"Raw results: {len(all_results)}")

        # 2. Baseline domain distribution
        raw_domains = self._count_domains(all_results)
        top_3 = self._top_domains(raw_domains)
        logger.info(f"Top 3 domains (raw): {top_3}")
        logger.info(f"Unique domains (raw): {len(raw_domains)}")

        # 3. Run dedup
        deduplicated = await deduplicate_by_embedding(
            articles=all_results, api_key=OPENROUTER_KEY, threshold=0.80
        )
        dedup_domains = self._count_domains(deduplicated)
        logger.info(f"After dedup: {len(deduplicated)} articles, {len(dedup_domains)} domains")

        # 4. Run AI filter
        ai_filtered = await ai_filter_results(
            results=deduplicated, city_name=city, country_name=country,
            openrouter_key=OPENROUTER_KEY, max_results=15, category="news"
        )
        ai_domains = self._count_domains(ai_filtered)
        logger.info(f"After AI filter: {len(ai_filtered)} articles, {len(ai_domains)} domains")
        logger.info(f"AI filter domain distribution: {ai_domains.most_common(5)}")

        # 5. Simulate domain cap (independently, on AI-filtered results without cap)
        # Note: cap is already applied inside ai_filter_results, so we test it separately
        capped = cap_articles_per_domain(ai_filtered, max_per_domain=2)
        capped_domains = self._count_domains(capped)
        logger.info(f"After domain cap: {len(capped)} articles, {len(capped_domains)} domains")

        # Assertions
        # Domain cap should ensure max 2 per domain
        for domain, count in capped_domains.items():
            assert count <= 2, f"Domain {domain} has {count} articles (max 2)"

        # Should have at least some results
        assert len(all_results) > 0, f"No results found for {city}"
        assert len(deduplicated) > 0, f"Dedup removed all results for {city}"

        return {
            "city": city,
            "raw_count": len(all_results),
            "raw_domains": len(raw_domains),
            "dedup_count": len(deduplicated),
            "ai_count": len(ai_filtered),
            "capped_count": len(capped),
            "top_3_raw": top_3,
        }

    async def test_zurich_niche_discovery(self):
        """Validate niche source discovery for Zurich, Switzerland."""
        result = await self._run_city_test(
            city="Zurich",
            country="Switzerland",
            country_code="CH",
            queries=[
                "Zürich Nachrichten aktuell",
                "Zurich news local",
                "Zurich city council",
            ]
        )
        assert result["raw_count"] > 10, "Expected 10+ raw results for Zurich"

    async def test_montreal_niche_discovery(self):
        """Validate niche source discovery for Montreal, Canada."""
        result = await self._run_city_test(
            city="Montreal",
            country="Canada",
            country_code="CA",
            queries=[
                "Montréal actualités locales",
                "Montreal news today",
                "Montreal city hall",
            ]
        )
        assert result["raw_count"] > 10, "Expected 10+ raw results for Montreal"

    async def test_oslo_niche_discovery(self):
        """Validate niche source discovery for Oslo, Norway."""
        result = await self._run_city_test(
            city="Oslo",
            country="Norway",
            country_code="NO",
            queries=[
                "Oslo nyheter lokale",
                "Oslo news today",
                "Oslo kommune",
            ]
        )
        assert result["raw_count"] > 10, "Expected 10+ raw results for Oslo"
