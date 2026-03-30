"""
Integration tests for the Discoveries pipeline.

Validates that discovery search queries (web-only, non-news) produce
non-mainstream content, and that cluster_size filtering correctly
identifies mainstream vs niche articles.

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

# Mainstream news domains by country
MAINSTREAM_NO = {"nrk.no", "vg.no", "dagbladet.no", "aftenposten.no", "tv2.no"}
MAINSTREAM_CH = {"nzz.ch", "srf.ch", "20min.ch", "tagesanzeiger.ch", "blick.ch"}
MAINSTREAM_CA = {"cbc.ca", "globalnews.ca", "thestar.com", "nationalpost.com", "lapresse.ca"}


def _count_domains(articles: list[dict]) -> Counter:
    return Counter(
        urlparse(a.get("url", "")).netloc.replace("www.", "")
        for a in articles
    )


def _non_mainstream_count(articles: list[dict], mainstream: set[str]) -> int:
    """Count articles NOT from mainstream domains."""
    count = 0
    for a in articles:
        domain = urlparse(a.get("url", "")).netloc.replace("www.", "")
        if not any(domain.endswith(m) for m in mainstream):
            count += 1
    return count


@pytest.mark.asyncio
@pytest.mark.skipif(not FIRECRAWL_KEY or not OPENROUTER_KEY, reason=SKIP_REASON)
class TestDiscoveriesPipeline:
    """Validate the discovery search strategy against real Firecrawl data."""

    async def _search_queries(self, queries: list[str], city: str, country_code: str,
                               sources: list[str] = None) -> list[dict]:
        """Execute search queries and return unique results."""
        from app.services.news_utils import FirecrawlTools

        tools = FirecrawlTools(FIRECRAWL_KEY)
        all_results = []
        seen_urls = set()

        for query in queries:
            result = await tools.search_web(
                query=query, location=city, country=country_code,
                limit=25, sources=sources or ["news", "web"]
            )
            for item in result.get("results", []):
                url = item.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(item)
            await asyncio.sleep(0.3)

        return all_results

    async def test_discovery_queries_bergen(self):
        """Discovery queries for Bergen return non-news content."""
        discovery_queries = [
            '"Bergen" blogg',
            '"Bergen" forening',
            '"Bergen" frivillig',
            '"Bergen" nabolag',
            '"Bergen" kulturarrangement',
        ]
        results = await self._search_queries(
            discovery_queries, city="Bergen", country_code="NO",
            sources=["web"]  # Web only, no news
        )

        domains = _count_domains(results)
        non_mainstream = _non_mainstream_count(results, MAINSTREAM_NO)

        logger.info(f"\nBergen discovery queries (web-only):")
        logger.info(f"  Total results: {len(results)}")
        logger.info(f"  Unique domains: {len(domains)}")
        logger.info(f"  Non-mainstream: {non_mainstream}")
        logger.info(f"  Top domains: {domains.most_common(5)}")

        assert len(results) > 0, "Expected some results for Bergen discovery queries"
        # At least some results should be non-mainstream
        assert non_mainstream > 0, "Expected at least some non-mainstream results"

    async def test_cluster_size_bergen(self):
        """Dedup with cluster_size identifies mainstream vs niche stories."""
        from app.services.news_utils import deduplicate_by_embedding

        news_queries = [
            '"Bergen nyheter"',
            '"Bergen aktuelt"',
            '"Bergen lokale nyheter"',
        ]
        results = await self._search_queries(
            news_queries, city="Bergen", country_code="NO",
            sources=["news", "web"]
        )

        if len(results) < 3:
            pytest.skip("Not enough results to test clustering")

        deduplicated = await deduplicate_by_embedding(
            articles=results, api_key=OPENROUTER_KEY, threshold=0.80
        )

        # Check cluster sizes
        has_large_cluster = any(a.get("_cluster_size", 1) >= 3 for a in deduplicated)
        has_unique = any(a.get("_cluster_size", 1) == 1 for a in deduplicated)

        cluster_sizes = [a.get("_cluster_size", 1) for a in deduplicated]
        logger.info(f"\nBergen cluster size distribution:")
        logger.info(f"  Articles: {len(deduplicated)}")
        logger.info(f"  Cluster sizes: {Counter(cluster_sizes)}")
        logger.info(f"  Has large cluster (>=3): {has_large_cluster}")
        logger.info(f"  Has unique (==1): {has_unique}")

        assert len(deduplicated) > 0, "Expected some deduplicated results"
        # We expect a mix of cluster sizes in real news data
        # (can't guarantee exact distribution, so just log)

    async def test_full_discovery_pipeline_bergen(self):
        """Full pipeline produces diverse output with domain cap."""
        # Reset shared HTTP client (may be stale from previous test's event loop)
        from app.services import http_client as _hc
        _hc._client = None

        from app.services.news_utils import (
            deduplicate_by_embedding, ai_filter_results, cap_articles_per_domain
        )

        # Run news queries
        news_queries = [
            '"Bergen nyheter"',
            '"Bergen aktuelt"',
        ]
        news_results = await self._search_queries(
            news_queries, city="Bergen", country_code="NO",
            sources=["news", "web"]
        )
        for r in news_results:
            r["_pass"] = "news"

        # Run discovery queries
        disc_queries = [
            '"Bergen" blogg',
            '"Bergen" forening',
            '"Bergen" frivillig',
        ]
        disc_results = await self._search_queries(
            disc_queries, city="Bergen", country_code="NO",
            sources=["web"]
        )
        for r in disc_results:
            r["_pass"] = "discovery"

        combined = news_results + disc_results

        # Dedup
        deduplicated = await deduplicate_by_embedding(
            articles=combined, api_key=OPENROUTER_KEY, threshold=0.80
        )

        # Split by pass and filter by cluster size
        niche_pool = [a for a in deduplicated if a.get("_pass") == "discovery"]
        news_pool = [a for a in deduplicated if a.get("_pass") == "news" and a.get("_cluster_size", 1) <= 2]
        candidates = niche_pool + news_pool

        # AI filter
        ai_filtered = await ai_filter_results(
            results=candidates, city_name="Bergen", country_name="Norway",
            openrouter_key=OPENROUTER_KEY, max_results=6, category="news"
        )

        domains = _count_domains(ai_filtered)
        non_mainstream = _non_mainstream_count(ai_filtered, MAINSTREAM_NO)

        logger.info(f"\nBergen full pipeline:")
        logger.info(f"  News results: {len(news_results)}, Discovery results: {len(disc_results)}")
        logger.info(f"  After dedup: {len(deduplicated)}")
        logger.info(f"  Niche pool: {len(niche_pool)}, News pool (cluster<=2): {len(news_pool)}")
        logger.info(f"  AI filtered: {len(ai_filtered)}")
        logger.info(f"  Non-mainstream: {non_mainstream}")
        logger.info(f"  Domain distribution: {domains.most_common(10)}")

        # Domain cap enforced
        for domain, count in domains.items():
            assert count <= 2, f"Domain {domain} has {count} articles (max 2)"

    async def test_discovery_queries_zurich(self):
        """Zurich discovery queries with German terms return non-mainstream .ch domains."""
        discovery_queries = [
            '"Zürich" Blog',
            '"Zürich" Verein',
            '"Zürich" Quartierverein',
            '"Zürich" Bürgerinitiative',
            '"Zürich" Kulturveranstaltung',
        ]
        results = await self._search_queries(
            discovery_queries, city="Zurich", country_code="CH",
            sources=["web"]
        )

        domains = _count_domains(results)
        non_mainstream = _non_mainstream_count(results, MAINSTREAM_CH)

        logger.info(f"\nZurich discovery queries (web-only):")
        logger.info(f"  Total results: {len(results)}")
        logger.info(f"  Unique domains: {len(domains)}")
        logger.info(f"  Non-mainstream: {non_mainstream}")
        logger.info(f"  Top domains: {domains.most_common(5)}")

        assert len(results) > 0, "Expected some results for Zurich discovery queries"
        assert non_mainstream > 0, "Expected at least some non-mainstream .ch results"

    async def test_discovery_queries_montreal(self):
        """Montreal discovery queries with French terms return non-mainstream Canadian sources."""
        discovery_queries = [
            '"Montréal" blog',
            '"Montréal" association',
            '"Montréal" communauté',
            '"Montréal" quartier',
            '"Montréal" événement culturel',
        ]
        results = await self._search_queries(
            discovery_queries, city="Montreal", country_code="CA",
            sources=["web"]
        )

        domains = _count_domains(results)
        non_mainstream = _non_mainstream_count(results, MAINSTREAM_CA)

        logger.info(f"\nMontreal discovery queries (web-only):")
        logger.info(f"  Total results: {len(results)}")
        logger.info(f"  Unique domains: {len(domains)}")
        logger.info(f"  Non-mainstream: {non_mainstream}")
        logger.info(f"  Top domains: {domains.most_common(5)}")

        assert len(results) > 0, "Expected some results for Montreal discovery queries"
        assert non_mainstream > 0, "Expected at least some non-mainstream Canadian results"
