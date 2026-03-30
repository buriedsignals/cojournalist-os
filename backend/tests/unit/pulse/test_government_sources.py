"""
Tests for government category generating discovery queries for public-sector sources.

Verifies that category='government' generates web-only discovery queries targeting
official government websites, municipal portals, and public sector repositories.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pydantic import ValidationError


def make_article(url: str, title: str = "Test", description: str = "desc", published: str = None) -> dict:
    d = {"url": url, "title": title, "description": description}
    if published:
        d["date"] = published
    return d


class TestGovernmentDiscoveryQueries:
    """Test that government category generates web-only discovery queries."""

    @pytest.mark.asyncio
    async def test_gov_category_generates_discovery_queries(self):
        """When category='government', the orchestrator should produce queries
        with _pass='government' and sources=['web'] for surfacing official
        government websites and municipal portals.

        Currently fails because search_news() only generates discovery queries
        for category='news' (line ~189: `if category == "news"`). Government
        category gets no web-only discovery queries.
        """
        with patch("app.services.pulse_orchestrator.settings") as mock_settings:
            mock_settings.openrouter_api_key = "test-key"
            mock_settings.firecrawl_api_key = "test-key"

            from app.services.pulse_orchestrator import PulseOrchestrator
            orchestrator = PulseOrchestrator()

        # Mock query generator to return standard government queries + discovery queries
        mock_query_result = {
            "queries": ["Gemeinderat Zurich", "Stadtrat Zurich Beschluss"],
            "local_domains": [".ch", "stadt-zuerich.ch"],
            "language": "de",
            "languages": ["de"],
            "category": "government",
            "cached": False,
            "discovery_queries": [
                "Stadt Zürich offizielle Website",
                "Stadtpolizei Zürich",
                "Schulamt Zürich",
            ],
        }

        captured_queries = None

        async def capture_search_queries(queries, **kwargs):
            nonlocal captured_queries
            captured_queries = queries
            return ([], [])  # Empty results, we only care about the queries

        with patch("app.services.pulse_orchestrator.get_query_generator") as mock_gen_factory, \
             patch.object(orchestrator, "_execute_all_searches_directly", side_effect=capture_search_queries), \
             patch("app.services.pulse_orchestrator.deduplicate_by_embedding", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.pulse_orchestrator.ai_filter_results", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.pulse_orchestrator.generate_news_summary", new_callable=AsyncMock, return_value=""):
            mock_gen = AsyncMock()
            mock_gen.generate_queries = AsyncMock(return_value=mock_query_result)
            mock_gen_factory.return_value = mock_gen

            await orchestrator.search_news(
                location="Zurich, Switzerland",
                city="Zurich",
                country="Switzerland",
                category="government",
            )

        assert captured_queries is not None, "Search queries were never captured"

        # Check that government discovery queries exist
        gov_discovery = [q for q in captured_queries if q.get("_pass") == "government"]
        assert len(gov_discovery) > 0, (
            "Government category should generate queries with _pass='government', "
            "but none were found. Only passes found: "
            f"{set(q.get('_pass') for q in captured_queries)}"
        )

        # Government discovery queries should use web-only sources
        for q in gov_discovery:
            assert q.get("sources") == ["web"], (
                f"Government discovery query should use sources=['web'], "
                f"got {q.get('sources')}"
            )

    @pytest.mark.asyncio
    async def test_gov_category_always_includes_web_source(self):
        """Even in reliable mode, government queries should include 'web'
        in sources to surface official government portals that aren't
        indexed as 'news'.

        Municipal websites (.gov, .stadt, .kommune) rarely appear in news
        indices but are the primary source for government information.
        """
        with patch("app.services.pulse_orchestrator.settings") as mock_settings:
            mock_settings.openrouter_api_key = "test-key"
            mock_settings.firecrawl_api_key = "test-key"

            from app.services.pulse_orchestrator import PulseOrchestrator
            orchestrator = PulseOrchestrator()

        mock_query_result = {
            "queries": ["Gemeinderat Zurich"],
            "local_domains": [".ch"],
            "language": "de",
            "languages": ["de"],
            "category": "government",
            "cached": False,
            "discovery_queries": [
                "Stadt Zürich offizielle Website",
                "Stadtpolizei Zürich",
            ],
        }

        captured_queries = None

        async def capture_search_queries(queries, **kwargs):
            nonlocal captured_queries
            captured_queries = queries
            return ([], [])

        with patch("app.services.pulse_orchestrator.get_query_generator") as mock_gen_factory, \
             patch.object(orchestrator, "_execute_all_searches_directly", side_effect=capture_search_queries), \
             patch("app.services.pulse_orchestrator.deduplicate_by_embedding", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.pulse_orchestrator.ai_filter_results", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.pulse_orchestrator.generate_news_summary", new_callable=AsyncMock, return_value=""):
            mock_gen = AsyncMock()
            mock_gen.generate_queries = AsyncMock(return_value=mock_query_result)
            mock_gen_factory.return_value = mock_gen

            await orchestrator.search_news(
                location="Zurich, Switzerland",
                city="Zurich",
                country="Switzerland",
                category="government",
            )

        assert captured_queries is not None

        # At least some queries should be web-only (for government portals)
        web_only_queries = [q for q in captured_queries if q.get("sources") == ["web"]]
        assert len(web_only_queries) > 0, (
            "Government category should include at least one web-only query "
            "to surface official municipal/government websites. "
            f"All queries had sources: {[q.get('sources') for q in captured_queries]}"
        )


class TestQueryGeneratorDiscoveryField:
    """Test that the query generator supports a discovery_queries field."""

    def test_query_generator_returns_discovery_queries_for_gov(self):
        """The LLMQueryResponse model should accept a discovery_queries field
        so the LLM can suggest government-specific web search queries
        (e.g., 'site:stadt-zuerich.ch', 'site:.gov').

        Currently fails because LLMQueryResponse only has:
        primary_language, queries, local_domains.
        No discovery_queries field.
        """
        from app.services.query_generator import LLMQueryResponse

        # This should work after the fix adds discovery_queries to the model
        response = LLMQueryResponse(
            primary_language="de",
            queries=["Gemeinderat Zurich", "Stadtrat Zurich"],
            local_domains=[".ch", "stadt-zuerich.ch"],
            discovery_queries=[
                "site:stadt-zuerich.ch Beschluss",
                "site:.ch Gemeinderat",
            ],
        )

        assert hasattr(response, "discovery_queries"), (
            "LLMQueryResponse should have a discovery_queries field"
        )
        assert len(response.discovery_queries) == 2
        assert "site:stadt-zuerich.ch" in response.discovery_queries[0]

    def test_discovery_queries_default_empty(self):
        """discovery_queries should default to an empty list when not provided."""
        from app.services.query_generator import LLMQueryResponse

        response = LLMQueryResponse(
            primary_language="de",
            queries=["Gemeinderat Zurich"],
            local_domains=[".ch"],
        )

        assert hasattr(response, "discovery_queries"), (
            "LLMQueryResponse should have a discovery_queries field"
        )
        assert response.discovery_queries == [], (
            "discovery_queries should default to empty list"
        )
