"""
Tests for the Pulse /execute endpoint dual-category pipeline.

Verifies:
- Both news + government categories run in parallel via asyncio.gather
- Partial failures (one category fails, other succeeds)
- URL deduplication across categories
- Fact splitting by source_url for email sections
- Notification receives both sections (gov_articles, gov_summary)
- Language, topic, excluded_domains forwarded correctly
- Combined article counts in response
- Sequential run dedup (recent_facts injection + all_duplicates path)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from app.schemas.common import AINewsArticle
from app.schemas.pulse import PulseExecuteRequest, PulseExecuteResponse
from app.schemas.scouts import GeocodedLocation
from app.services.atomic_unit_service import ProcessingResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_article(url: str, title: str = "Test", source: str = "example.com", summary: str = "Summary") -> AINewsArticle:
    return AINewsArticle(title=title, url=url, source=source, summary=summary)


def _make_agent_response(category: str, articles: list[AINewsArticle], summary: str = "AI summary"):
    """Build a mock AgentResponse-like object with the fields the endpoint reads."""
    resp = MagicMock()
    resp.status = "completed"
    resp.category = category
    resp.articles = articles
    resp.summary = summary
    resp.response_markdown = ""
    resp.search_queries_used = ["query"]
    resp.urls_scraped = ["http://example.com"]
    resp.processing_time_ms = 500
    resp.total_results = len(articles)
    return resp


def _make_request(
    location_display="Oslo, Norway",
    city="Oslo",
    country="Norway",
    criteria=None,
    topic=None,
    language="no",
    source_mode="reliable",
) -> PulseExecuteRequest:
    """Build a valid PulseExecuteRequest.

    Defaults to source_mode="reliable" so both categories dispatch.
    Use source_mode="niche" + no criteria to test single-category behavior.
    """
    kwargs = dict(
        userId="user_123",
        scraperName="my-scout",
        preferred_language=language,
        source_mode=source_mode,
    )
    if location_display:
        kwargs["location"] = GeocodedLocation(displayName=location_display, city=city, country=country)
    if criteria:
        kwargs["criteria"] = criteria
    if topic:
        kwargs["topic"] = topic
    return PulseExecuteRequest(**kwargs)


def _processing_result(new_facts=None, duplicate_facts=None, all_duplicates=False):
    return ProcessingResult(
        new_facts=new_facts or [],
        duplicate_facts=duplicate_facts or [],
        all_duplicates=all_duplicates,
    )


# Common patch targets (module where names are looked up at runtime)
_P = "app.routers.pulse"
_EP = "app.services.execute_pipeline"
_NU = "app.services.news_utils"


def _base_patches():
    """Return dict of common mocks used by most tests."""
    return {
        "get_user_email": AsyncMock(return_value="user@test.com"),
        "decrement_credit": AsyncMock(),
        "log_scout_execution": MagicMock(),
        "exec_dedup_service": MagicMock(
            generate_summary_from_facts=AsyncMock(return_value="New discoveries found"),
            store_execution=AsyncMock(return_value={}),
        ),
        "notification_service": MagicMock(
            send_pulse_alert=AsyncMock(return_value=True),
        ),
        "atomic_unit_service": MagicMock(
            get_recent_facts=AsyncMock(return_value=[]),
            process_results=AsyncMock(return_value=_processing_result()),
        ),
        "cross_category_dedup": AsyncMock(side_effect=lambda news, gov, **kw: (news, gov)),
    }


def _user_service_mock(excluded_domains=None):
    """Mock UserService to return user data with excluded_domains."""
    mock_service = AsyncMock()
    mock_service.get_user.return_value = {
        "user_id": "user_123",
        "excluded_domains": excluded_domains or [],
        "credits": 100,
    }
    return MagicMock(return_value=mock_service)


# ---------------------------------------------------------------------------
# Test: Both categories searched in parallel
# ---------------------------------------------------------------------------

class TestDualCategorySearch:
    """Verify asyncio.gather dispatches both categories with correct kwargs."""

    @pytest.mark.asyncio
    async def test_both_categories_called(self):
        """search_news is called once with category='news' and once with 'government'."""
        news_resp = _make_agent_response("news", [_make_article("http://a.com/1", "News A")])
        gov_resp = _make_agent_response("government", [_make_article("http://b.com/1", "Gov B")])

        mock_orchestrator = MagicMock()
        mock_orchestrator.search_news = AsyncMock(side_effect=lambda **kw: news_resp if kw["category"] == "news" else gov_resp)

        mocks = _base_patches()
        mocks["atomic_unit_service"].process_results = AsyncMock(
            return_value=_processing_result(new_facts=[
                {"source_url": "http://a.com/1", "statement": "Fact A"},
                {"source_url": "http://b.com/1", "statement": "Fact B"},
            ])
        )

        with patch(f"{_P}.get_user_email", mocks["get_user_email"]), \
             patch(f"{_P}.PulseOrchestrator", return_value=mock_orchestrator), \
             patch(f"{_EP}.atomic_unit_service", mocks["atomic_unit_service"]), \
             patch(f"{_EP}.exec_dedup_service", mocks["exec_dedup_service"]), \
             patch(f"{_P}.notification_service", mocks["notification_service"]), \
             patch(f"{_EP}.decrement_credit", mocks["decrement_credit"]), \
             patch(f"{_EP}.log_scout_execution", mocks["log_scout_execution"]), \
             patch(f"{_NU}.cross_category_dedup", mocks["cross_category_dedup"]), \
             patch(f"{_P}.UserService", _user_service_mock()):

            from app.routers.pulse import execute_pulse_scout
            result = await execute_pulse_scout(request=_make_request(), _=None)

        # Verify search_news called twice
        assert mock_orchestrator.search_news.call_count == 2
        call_categories = {c.kwargs["category"] for c in mock_orchestrator.search_news.call_args_list}
        assert call_categories == {"news", "government"}

    @pytest.mark.asyncio
    async def test_shared_kwargs_forwarded(self):
        """location, city, country, language, criteria, excluded_domains, recent_findings all forwarded."""
        news_resp = _make_agent_response("news", [])
        gov_resp = _make_agent_response("government", [])

        mock_orchestrator = MagicMock()
        mock_orchestrator.search_news = AsyncMock(side_effect=lambda **kw: news_resp if kw["category"] == "news" else gov_resp)

        mocks = _base_patches()
        mocks["atomic_unit_service"].get_recent_facts = AsyncMock(return_value=[
            {"statement": "Old fact 1"},
        ])

        with patch(f"{_P}.get_user_email", mocks["get_user_email"]), \
             patch(f"{_P}.PulseOrchestrator", return_value=mock_orchestrator), \
             patch(f"{_EP}.atomic_unit_service", mocks["atomic_unit_service"]), \
             patch(f"{_EP}.exec_dedup_service", mocks["exec_dedup_service"]), \
             patch(f"{_P}.notification_service", mocks["notification_service"]), \
             patch(f"{_EP}.decrement_credit", mocks["decrement_credit"]), \
             patch(f"{_EP}.log_scout_execution", mocks["log_scout_execution"]), \
             patch(f"{_NU}.cross_category_dedup", mocks["cross_category_dedup"]), \
             patch(f"{_P}.UserService", _user_service_mock(["blocked.com"])):

            from app.routers.pulse import execute_pulse_scout
            req = _make_request(location_display="Oslo, Norway", city="Oslo", country="Norway", criteria="climate", language="no")
            result = await execute_pulse_scout(request=req, _=None)

        # Both calls should have the same shared kwargs
        for call in mock_orchestrator.search_news.call_args_list:
            kw = call.kwargs
            assert kw["location"] == "Oslo, Norway"
            assert kw["city"] == "Oslo"
            assert kw["country"] == "Norway"
            assert kw["language"] == "no"
            assert kw["criteria"] == "climate"
            assert kw["excluded_domains"] == ["blocked.com"]
            assert kw["recent_findings"] == [{"summary_text": "Old fact 1"}]


# ---------------------------------------------------------------------------
# Test: Partial failure handling
# ---------------------------------------------------------------------------

class TestPartialFailures:
    """One category failing should not block the other."""

    @pytest.mark.asyncio
    async def test_news_fails_gov_succeeds(self):
        """If news category raises, gov articles still appear in response."""
        gov_resp = _make_agent_response("government", [
            _make_article("http://gov.no/1", "Council meeting"),
            _make_article("http://gov.no/2", "Budget approved"),
        ])

        mock_orchestrator = MagicMock()

        async def _side_effect(**kw):
            if kw["category"] == "news":
                raise RuntimeError("Firecrawl timeout")
            return gov_resp

        mock_orchestrator.search_news = AsyncMock(side_effect=_side_effect)

        mocks = _base_patches()
        mocks["atomic_unit_service"].process_results = AsyncMock(
            return_value=_processing_result(new_facts=[
                {"source_url": "http://gov.no/1", "statement": "Council met"},
            ])
        )

        with patch(f"{_P}.get_user_email", mocks["get_user_email"]), \
             patch(f"{_P}.PulseOrchestrator", return_value=mock_orchestrator), \
             patch(f"{_EP}.atomic_unit_service", mocks["atomic_unit_service"]), \
             patch(f"{_EP}.exec_dedup_service", mocks["exec_dedup_service"]), \
             patch(f"{_P}.notification_service", mocks["notification_service"]), \
             patch(f"{_EP}.decrement_credit", mocks["decrement_credit"]), \
             patch(f"{_EP}.log_scout_execution", mocks["log_scout_execution"]), \
             patch(f"{_NU}.cross_category_dedup", mocks["cross_category_dedup"]), \
             patch(f"{_P}.UserService", _user_service_mock()):

            from app.routers.pulse import execute_pulse_scout
            result = await execute_pulse_scout(request=_make_request(), _=None)

        assert result.scraper_status is True
        assert result.articles_count == 2  # Only gov articles
        assert result.notification_sent is True

    @pytest.mark.asyncio
    async def test_gov_fails_news_succeeds(self):
        """If government category raises, news articles still appear."""
        news_resp = _make_agent_response("news", [
            _make_article("http://news.no/1", "Local discovery"),
        ])

        mock_orchestrator = MagicMock()

        async def _side_effect(**kw):
            if kw["category"] == "government":
                raise RuntimeError("OpenRouter rate limit")
            return news_resp

        mock_orchestrator.search_news = AsyncMock(side_effect=_side_effect)

        mocks = _base_patches()
        mocks["atomic_unit_service"].process_results = AsyncMock(
            return_value=_processing_result(new_facts=[
                {"source_url": "http://news.no/1", "statement": "Discovery made"},
            ])
        )

        with patch(f"{_P}.get_user_email", mocks["get_user_email"]), \
             patch(f"{_P}.PulseOrchestrator", return_value=mock_orchestrator), \
             patch(f"{_EP}.atomic_unit_service", mocks["atomic_unit_service"]), \
             patch(f"{_EP}.exec_dedup_service", mocks["exec_dedup_service"]), \
             patch(f"{_P}.notification_service", mocks["notification_service"]), \
             patch(f"{_EP}.decrement_credit", mocks["decrement_credit"]), \
             patch(f"{_EP}.log_scout_execution", mocks["log_scout_execution"]), \
             patch(f"{_NU}.cross_category_dedup", mocks["cross_category_dedup"]), \
             patch(f"{_P}.UserService", _user_service_mock()):

            from app.routers.pulse import execute_pulse_scout
            result = await execute_pulse_scout(request=_make_request(), _=None)

        assert result.scraper_status is True
        assert result.articles_count == 1  # Only news articles
        assert result.notification_sent is True

    @pytest.mark.asyncio
    async def test_both_fail_returns_no_articles(self):
        """If both categories fail, endpoint returns 0 articles but doesn't crash."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.search_news = AsyncMock(side_effect=RuntimeError("Everything is broken"))

        mocks = _base_patches()
        # No new facts since no articles
        mocks["atomic_unit_service"].process_results = AsyncMock(
            return_value=_processing_result(all_duplicates=True)
        )

        with patch(f"{_P}.get_user_email", mocks["get_user_email"]), \
             patch(f"{_P}.PulseOrchestrator", return_value=mock_orchestrator), \
             patch(f"{_EP}.atomic_unit_service", mocks["atomic_unit_service"]), \
             patch(f"{_EP}.exec_dedup_service", mocks["exec_dedup_service"]), \
             patch(f"{_P}.notification_service", mocks["notification_service"]), \
             patch(f"{_EP}.decrement_credit", mocks["decrement_credit"]), \
             patch(f"{_EP}.log_scout_execution", mocks["log_scout_execution"]), \
             patch(f"{_NU}.cross_category_dedup", mocks["cross_category_dedup"]), \
             patch(f"{_P}.UserService", _user_service_mock()):

            from app.routers.pulse import execute_pulse_scout
            result = await execute_pulse_scout(request=_make_request(), _=None)

        assert result.scraper_status is True
        assert result.articles_count == 0
        assert result.notification_sent is False


# ---------------------------------------------------------------------------
# Test: URL deduplication across categories
# ---------------------------------------------------------------------------

class TestCrossCategoryDedup:
    """Duplicate URLs between news and gov should be deduplicated."""

    @pytest.mark.asyncio
    async def test_overlapping_url_kept_only_in_news(self):
        """An article appearing in both categories is only counted under news."""
        shared_url = "http://overlap.no/shared-article"
        news_resp = _make_agent_response("news", [
            _make_article(shared_url, "Shared Article"),
            _make_article("http://news.no/unique", "News Only"),
        ])
        gov_resp = _make_agent_response("government", [
            _make_article(shared_url, "Shared Article (gov)"),
            _make_article("http://gov.no/unique", "Gov Only"),
        ])

        mock_orchestrator = MagicMock()
        mock_orchestrator.search_news = AsyncMock(side_effect=lambda **kw: news_resp if kw["category"] == "news" else gov_resp)

        captured_results = {}

        async def capture_process_results(**kwargs):
            captured_results["articles"] = kwargs["results"]
            return _processing_result(new_facts=[
                {"source_url": "http://news.no/unique", "statement": "News fact"},
                {"source_url": "http://gov.no/unique", "statement": "Gov fact"},
                {"source_url": shared_url, "statement": "Shared fact"},
            ])

        mocks = _base_patches()
        mocks["atomic_unit_service"].process_results = AsyncMock(side_effect=capture_process_results)

        with patch(f"{_P}.get_user_email", mocks["get_user_email"]), \
             patch(f"{_P}.PulseOrchestrator", return_value=mock_orchestrator), \
             patch(f"{_EP}.atomic_unit_service", mocks["atomic_unit_service"]), \
             patch(f"{_EP}.exec_dedup_service", mocks["exec_dedup_service"]), \
             patch(f"{_P}.notification_service", mocks["notification_service"]), \
             patch(f"{_EP}.decrement_credit", mocks["decrement_credit"]), \
             patch(f"{_EP}.log_scout_execution", mocks["log_scout_execution"]), \
             patch(f"{_NU}.cross_category_dedup", mocks["cross_category_dedup"]), \
             patch(f"{_P}.UserService", _user_service_mock()):

            from app.routers.pulse import execute_pulse_scout
            result = await execute_pulse_scout(request=_make_request(), _=None)

        # process_results receives 3 articles: 2 news + 1 unique gov (shared excluded from gov)
        urls_processed = {r["url"] for r in captured_results["articles"]}
        assert shared_url in urls_processed
        assert "http://news.no/unique" in urls_processed
        assert "http://gov.no/unique" in urls_processed
        assert len(captured_results["articles"]) == 3

        # articles_count in response = 2 news_articles + 2 gov_articles_raw (raw count, not deduped)
        assert result.articles_count == 4

    @pytest.mark.asyncio
    async def test_no_overlap_keeps_all(self):
        """Distinct URLs from both categories all pass through to process_results."""
        news_resp = _make_agent_response("news", [
            _make_article("http://news.no/1", "News 1"),
            _make_article("http://news.no/2", "News 2"),
        ])
        gov_resp = _make_agent_response("government", [
            _make_article("http://gov.no/1", "Gov 1"),
            _make_article("http://gov.no/2", "Gov 2"),
        ])

        mock_orchestrator = MagicMock()
        mock_orchestrator.search_news = AsyncMock(side_effect=lambda **kw: news_resp if kw["category"] == "news" else gov_resp)

        captured = {}

        async def capture(**kwargs):
            captured["results"] = kwargs["results"]
            return _processing_result()

        mocks = _base_patches()
        mocks["atomic_unit_service"].process_results = AsyncMock(side_effect=capture)

        with patch(f"{_P}.get_user_email", mocks["get_user_email"]), \
             patch(f"{_P}.PulseOrchestrator", return_value=mock_orchestrator), \
             patch(f"{_EP}.atomic_unit_service", mocks["atomic_unit_service"]), \
             patch(f"{_EP}.exec_dedup_service", mocks["exec_dedup_service"]), \
             patch(f"{_P}.notification_service", mocks["notification_service"]), \
             patch(f"{_EP}.decrement_credit", mocks["decrement_credit"]), \
             patch(f"{_EP}.log_scout_execution", mocks["log_scout_execution"]), \
             patch(f"{_NU}.cross_category_dedup", mocks["cross_category_dedup"]), \
             patch(f"{_P}.UserService", _user_service_mock()):

            from app.routers.pulse import execute_pulse_scout
            result = await execute_pulse_scout(request=_make_request(), _=None)

        assert len(captured["results"]) == 4
        assert result.articles_count == 4


# ---------------------------------------------------------------------------
# Test: Notification receives both sections
# ---------------------------------------------------------------------------

class TestNotificationDualSections:
    """Email notification receives news + gov articles/summary."""

    @pytest.mark.asyncio
    async def test_gov_articles_and_summary_passed(self):
        """send_pulse_alert receives gov_articles and gov_summary when gov results exist."""
        news_resp = _make_agent_response("news", [
            _make_article("http://news.no/1", "News Story"),
        ], summary="News summary text")
        gov_resp = _make_agent_response("government", [
            _make_article("http://gov.no/1", "Gov Story"),
        ], summary="Government summary text")

        mock_orchestrator = MagicMock()
        mock_orchestrator.search_news = AsyncMock(side_effect=lambda **kw: news_resp if kw["category"] == "news" else gov_resp)

        mocks = _base_patches()
        mocks["atomic_unit_service"].process_results = AsyncMock(
            return_value=_processing_result(new_facts=[
                {"source_url": "http://news.no/1", "statement": "News fact"},
                {"source_url": "http://gov.no/1", "statement": "Gov fact"},
            ])
        )

        with patch(f"{_P}.get_user_email", mocks["get_user_email"]), \
             patch(f"{_P}.PulseOrchestrator", return_value=mock_orchestrator), \
             patch(f"{_EP}.atomic_unit_service", mocks["atomic_unit_service"]), \
             patch(f"{_EP}.exec_dedup_service", mocks["exec_dedup_service"]), \
             patch(f"{_P}.notification_service", mocks["notification_service"]), \
             patch(f"{_EP}.decrement_credit", mocks["decrement_credit"]), \
             patch(f"{_EP}.log_scout_execution", mocks["log_scout_execution"]), \
             patch(f"{_NU}.cross_category_dedup", mocks["cross_category_dedup"]), \
             patch(f"{_P}.UserService", _user_service_mock()):

            from app.routers.pulse import execute_pulse_scout
            result = await execute_pulse_scout(request=_make_request(), _=None)

        # Verify send_pulse_alert called with gov params
        call_kwargs = mocks["notification_service"].send_pulse_alert.call_args.kwargs
        assert call_kwargs["gov_summary"] == "Government summary text"
        assert isinstance(call_kwargs["gov_articles"], list)
        assert result.notification_sent is True

        # News summary should come from the orchestrator, not exec_summary
        assert call_kwargs["summary"] == "News summary text"

    @pytest.mark.asyncio
    async def test_no_gov_results_sends_empty_gov_section(self):
        """When gov returns no articles, gov_articles=[] and gov_summary=''."""
        news_resp = _make_agent_response("news", [
            _make_article("http://news.no/1", "News Story"),
        ])
        gov_resp = _make_agent_response("government", [], summary="")

        mock_orchestrator = MagicMock()
        mock_orchestrator.search_news = AsyncMock(side_effect=lambda **kw: news_resp if kw["category"] == "news" else gov_resp)

        mocks = _base_patches()
        mocks["atomic_unit_service"].process_results = AsyncMock(
            return_value=_processing_result(new_facts=[
                {"source_url": "http://news.no/1", "statement": "News fact"},
            ])
        )

        with patch(f"{_P}.get_user_email", mocks["get_user_email"]), \
             patch(f"{_P}.PulseOrchestrator", return_value=mock_orchestrator), \
             patch(f"{_EP}.atomic_unit_service", mocks["atomic_unit_service"]), \
             patch(f"{_EP}.exec_dedup_service", mocks["exec_dedup_service"]), \
             patch(f"{_P}.notification_service", mocks["notification_service"]), \
             patch(f"{_EP}.decrement_credit", mocks["decrement_credit"]), \
             patch(f"{_EP}.log_scout_execution", mocks["log_scout_execution"]), \
             patch(f"{_NU}.cross_category_dedup", mocks["cross_category_dedup"]), \
             patch(f"{_P}.UserService", _user_service_mock()):

            from app.routers.pulse import execute_pulse_scout
            result = await execute_pulse_scout(request=_make_request(), _=None)

        call_kwargs = mocks["notification_service"].send_pulse_alert.call_args.kwargs
        assert call_kwargs["gov_articles"] == []
        assert call_kwargs["gov_summary"] == ""

    @pytest.mark.asyncio
    async def test_facts_split_correctly_between_sections(self):
        """new_facts with news source_urls go to articles; gov source_urls go to gov_articles."""
        news_resp = _make_agent_response("news", [
            _make_article("http://news.no/a", "News A"),
            _make_article("http://news.no/b", "News B"),
        ])
        gov_resp = _make_agent_response("government", [
            _make_article("http://gov.no/x", "Gov X"),
        ])

        mock_orchestrator = MagicMock()
        mock_orchestrator.search_news = AsyncMock(side_effect=lambda **kw: news_resp if kw["category"] == "news" else gov_resp)

        mocks = _base_patches()
        mocks["atomic_unit_service"].process_results = AsyncMock(
            return_value=_processing_result(new_facts=[
                {"source_url": "http://news.no/a", "statement": "Fact from news A"},
                {"source_url": "http://news.no/b", "statement": "Fact from news B"},
                {"source_url": "http://gov.no/x", "statement": "Fact from gov X"},
            ])
        )

        captured_news_facts = []
        captured_gov_facts = []

        original_group = None

        def mock_group_facts(facts, source_limit=5):
            return [{"title": f.get("source_url", ""), "summary": f["statement"], "url": f.get("source_url", ""), "source": "test"} for f in facts]

        with patch(f"{_P}.get_user_email", mocks["get_user_email"]), \
             patch(f"{_P}.PulseOrchestrator", return_value=mock_orchestrator), \
             patch(f"{_EP}.atomic_unit_service", mocks["atomic_unit_service"]), \
             patch(f"{_EP}.exec_dedup_service", mocks["exec_dedup_service"]), \
             patch(f"{_P}.notification_service", mocks["notification_service"]), \
             patch(f"{_EP}.decrement_credit", mocks["decrement_credit"]), \
             patch(f"{_EP}.log_scout_execution", mocks["log_scout_execution"]), \
             patch(f"{_NU}.cross_category_dedup", mocks["cross_category_dedup"]), \
             patch(f"{_P}.UserService", _user_service_mock()), \
             patch(f"{_P}.group_facts_by_source", side_effect=mock_group_facts) as mock_gfbs:

            from app.routers.pulse import execute_pulse_scout
            result = await execute_pulse_scout(request=_make_request(), _=None)

        # group_facts_by_source called twice: once for news, once for gov
        assert mock_gfbs.call_count == 2
        news_call_facts = mock_gfbs.call_args_list[0][0][0]  # First positional arg of first call
        gov_call_facts = mock_gfbs.call_args_list[1][0][0]

        news_urls = {f["source_url"] for f in news_call_facts}
        gov_urls = {f["source_url"] for f in gov_call_facts}

        assert news_urls == {"http://news.no/a", "http://news.no/b"}
        assert gov_urls == {"http://gov.no/x"}


# ---------------------------------------------------------------------------
# Test: Language and topic forwarding
# ---------------------------------------------------------------------------

class TestLanguageAndTopicForwarding:
    """Preferred language and topic are passed through the pipeline."""

    @pytest.mark.asyncio
    async def test_language_forwarded_to_orchestrator_and_process_results(self):
        """preferred_language reaches orchestrator (as-is) and process_results (as lang_name)."""
        news_resp = _make_agent_response("news", [_make_article("http://a.com/1")])
        gov_resp = _make_agent_response("government", [])

        mock_orchestrator = MagicMock()
        mock_orchestrator.search_news = AsyncMock(side_effect=lambda **kw: news_resp if kw["category"] == "news" else gov_resp)

        mocks = _base_patches()
        mocks["atomic_unit_service"].process_results = AsyncMock(
            return_value=_processing_result(new_facts=[{"source_url": "http://a.com/1", "statement": "Fact"}])
        )

        with patch(f"{_P}.get_user_email", mocks["get_user_email"]), \
             patch(f"{_P}.PulseOrchestrator", return_value=mock_orchestrator), \
             patch(f"{_EP}.atomic_unit_service", mocks["atomic_unit_service"]), \
             patch(f"{_EP}.exec_dedup_service", mocks["exec_dedup_service"]), \
             patch(f"{_P}.notification_service", mocks["notification_service"]), \
             patch(f"{_EP}.decrement_credit", mocks["decrement_credit"]), \
             patch(f"{_EP}.log_scout_execution", mocks["log_scout_execution"]), \
             patch(f"{_NU}.cross_category_dedup", mocks["cross_category_dedup"]), \
             patch(f"{_P}.UserService", _user_service_mock()):

            from app.routers.pulse import execute_pulse_scout
            result = await execute_pulse_scout(request=_make_request(language="no"), _=None)

        # Orchestrator gets ISO code "no"
        for call in mock_orchestrator.search_news.call_args_list:
            assert call.kwargs["language"] == "no"

        # process_results gets full language name "Norwegian"
        pr_kwargs = mocks["atomic_unit_service"].process_results.call_args.kwargs
        assert pr_kwargs["language"] == "Norwegian"

        # Notification also gets ISO code
        notif_kwargs = mocks["notification_service"].send_pulse_alert.call_args.kwargs
        assert notif_kwargs["language"] == "no"

    @pytest.mark.asyncio
    async def test_criteria_only_scout_works(self):
        """A criteria-only scout (no location) correctly passes criteria to both categories."""
        news_resp = _make_agent_response("news", [_make_article("http://a.com/1")])
        gov_resp = _make_agent_response("government", [_make_article("http://b.com/1")])

        mock_orchestrator = MagicMock()
        mock_orchestrator.search_news = AsyncMock(side_effect=lambda **kw: news_resp if kw["category"] == "news" else gov_resp)

        mocks = _base_patches()
        mocks["atomic_unit_service"].process_results = AsyncMock(
            return_value=_processing_result(new_facts=[
                {"source_url": "http://a.com/1", "statement": "Fact"},
            ])
        )

        with patch(f"{_P}.get_user_email", mocks["get_user_email"]), \
             patch(f"{_P}.PulseOrchestrator", return_value=mock_orchestrator), \
             patch(f"{_EP}.atomic_unit_service", mocks["atomic_unit_service"]), \
             patch(f"{_EP}.exec_dedup_service", mocks["exec_dedup_service"]), \
             patch(f"{_P}.notification_service", mocks["notification_service"]), \
             patch(f"{_EP}.decrement_credit", mocks["decrement_credit"]), \
             patch(f"{_EP}.log_scout_execution", mocks["log_scout_execution"]), \
             patch(f"{_NU}.cross_category_dedup", mocks["cross_category_dedup"]), \
             patch(f"{_P}.UserService", _user_service_mock()):

            from app.routers.pulse import execute_pulse_scout
            req = _make_request(location_display=None, city=None, country=None, criteria="AI regulation")
            result = await execute_pulse_scout(request=req, _=None)

        for call in mock_orchestrator.search_news.call_args_list:
            assert call.kwargs["criteria"] == "AI regulation"
            assert call.kwargs["location"] is None

        assert result.scraper_status is True

    @pytest.mark.asyncio
    async def test_excluded_domains_from_user_profile(self):
        """excluded_domains fetched from DynamoDB user profile reach the orchestrator."""
        news_resp = _make_agent_response("news", [])
        gov_resp = _make_agent_response("government", [])

        mock_orchestrator = MagicMock()
        mock_orchestrator.search_news = AsyncMock(side_effect=lambda **kw: news_resp if kw["category"] == "news" else gov_resp)

        mocks = _base_patches()

        with patch(f"{_P}.get_user_email", mocks["get_user_email"]), \
             patch(f"{_P}.PulseOrchestrator", return_value=mock_orchestrator), \
             patch(f"{_EP}.atomic_unit_service", mocks["atomic_unit_service"]), \
             patch(f"{_EP}.exec_dedup_service", mocks["exec_dedup_service"]), \
             patch(f"{_P}.notification_service", mocks["notification_service"]), \
             patch(f"{_EP}.decrement_credit", mocks["decrement_credit"]), \
             patch(f"{_EP}.log_scout_execution", mocks["log_scout_execution"]), \
             patch(f"{_NU}.cross_category_dedup", mocks["cross_category_dedup"]), \
             patch(f"{_P}.UserService", _user_service_mock(["vg.no", "nrk.no"])):

            from app.routers.pulse import execute_pulse_scout
            result = await execute_pulse_scout(request=_make_request(), _=None)

        for call in mock_orchestrator.search_news.call_args_list:
            assert call.kwargs["excluded_domains"] == ["vg.no", "nrk.no"]


# ---------------------------------------------------------------------------
# Test: Sequential run deduplication
# ---------------------------------------------------------------------------

class TestSequentialRunDedup:
    """Verify that dedup works across sequential executions."""

    @pytest.mark.asyncio
    async def test_recent_facts_injected_into_orchestrator(self):
        """Recent facts from previous runs become recent_findings in the prompt."""
        news_resp = _make_agent_response("news", [])
        gov_resp = _make_agent_response("government", [])

        mock_orchestrator = MagicMock()
        mock_orchestrator.search_news = AsyncMock(side_effect=lambda **kw: news_resp if kw["category"] == "news" else gov_resp)

        mocks = _base_patches()
        mocks["atomic_unit_service"].get_recent_facts = AsyncMock(return_value=[
            {"statement": "Previously found: city budget approved"},
            {"statement": "Previously found: road construction update"},
            {"statement": "No statement key here"},  # Should be filtered (no "statement" key match)
        ])

        with patch(f"{_P}.get_user_email", mocks["get_user_email"]), \
             patch(f"{_P}.PulseOrchestrator", return_value=mock_orchestrator), \
             patch(f"{_EP}.atomic_unit_service", mocks["atomic_unit_service"]), \
             patch(f"{_EP}.exec_dedup_service", mocks["exec_dedup_service"]), \
             patch(f"{_P}.notification_service", mocks["notification_service"]), \
             patch(f"{_EP}.decrement_credit", mocks["decrement_credit"]), \
             patch(f"{_EP}.log_scout_execution", mocks["log_scout_execution"]), \
             patch(f"{_NU}.cross_category_dedup", mocks["cross_category_dedup"]), \
             patch(f"{_P}.UserService", _user_service_mock()):

            from app.routers.pulse import execute_pulse_scout
            result = await execute_pulse_scout(request=_make_request(), _=None)

        # recent_findings should include the 2 facts with "statement" key (3rd has it but value exists)
        for call in mock_orchestrator.search_news.call_args_list:
            findings = call.kwargs["recent_findings"]
            # All 3 have "statement" key, but the filter is `if f.get("statement")`
            # "No statement key here" is truthy, so all 3 pass
            assert len(findings) == 3
            assert findings[0] == {"summary_text": "Previously found: city budget approved"}

    @pytest.mark.asyncio
    async def test_recent_facts_passed_to_process_results(self):
        """recent_facts are forwarded to process_results for cross-run dedup."""
        news_resp = _make_agent_response("news", [_make_article("http://a.com/1")])
        gov_resp = _make_agent_response("government", [])

        mock_orchestrator = MagicMock()
        mock_orchestrator.search_news = AsyncMock(side_effect=lambda **kw: news_resp if kw["category"] == "news" else gov_resp)

        stored_facts = [
            {"statement": "Old fact 1", "source_url": "http://old.com/1"},
            {"statement": "Old fact 2", "source_url": "http://old.com/2"},
        ]

        mocks = _base_patches()
        mocks["atomic_unit_service"].get_recent_facts = AsyncMock(return_value=stored_facts)
        mocks["atomic_unit_service"].process_results = AsyncMock(
            return_value=_processing_result()
        )

        with patch(f"{_P}.get_user_email", mocks["get_user_email"]), \
             patch(f"{_P}.PulseOrchestrator", return_value=mock_orchestrator), \
             patch(f"{_EP}.atomic_unit_service", mocks["atomic_unit_service"]), \
             patch(f"{_EP}.exec_dedup_service", mocks["exec_dedup_service"]), \
             patch(f"{_P}.notification_service", mocks["notification_service"]), \
             patch(f"{_EP}.decrement_credit", mocks["decrement_credit"]), \
             patch(f"{_EP}.log_scout_execution", mocks["log_scout_execution"]), \
             patch(f"{_NU}.cross_category_dedup", mocks["cross_category_dedup"]), \
             patch(f"{_P}.UserService", _user_service_mock()):

            from app.routers.pulse import execute_pulse_scout
            result = await execute_pulse_scout(request=_make_request(), _=None)

        pr_kwargs = mocks["atomic_unit_service"].process_results.call_args.kwargs
        assert pr_kwargs["recent_facts"] == stored_facts

    @pytest.mark.asyncio
    async def test_all_duplicates_skips_notification(self):
        """When all facts are duplicates, no email is sent and credit is still charged."""
        news_resp = _make_agent_response("news", [_make_article("http://a.com/1")])
        gov_resp = _make_agent_response("government", [_make_article("http://b.com/1")])

        mock_orchestrator = MagicMock()
        mock_orchestrator.search_news = AsyncMock(side_effect=lambda **kw: news_resp if kw["category"] == "news" else gov_resp)

        mocks = _base_patches()
        mocks["atomic_unit_service"].process_results = AsyncMock(
            return_value=_processing_result(
                duplicate_facts=[
                    {"source_url": "http://a.com/1", "statement": "Old news"},
                    {"source_url": "http://b.com/1", "statement": "Old gov"},
                ],
                all_duplicates=True,
            )
        )

        with patch(f"{_P}.get_user_email", mocks["get_user_email"]), \
             patch(f"{_P}.PulseOrchestrator", return_value=mock_orchestrator), \
             patch(f"{_EP}.atomic_unit_service", mocks["atomic_unit_service"]), \
             patch(f"{_EP}.exec_dedup_service", mocks["exec_dedup_service"]), \
             patch(f"{_P}.notification_service", mocks["notification_service"]), \
             patch(f"{_EP}.decrement_credit", mocks["decrement_credit"]), \
             patch(f"{_EP}.log_scout_execution", mocks["log_scout_execution"]), \
             patch(f"{_NU}.cross_category_dedup", mocks["cross_category_dedup"]), \
             patch(f"{_P}.UserService", _user_service_mock()):

            from app.routers.pulse import execute_pulse_scout
            result = await execute_pulse_scout(request=_make_request(), _=None)

        assert result.notification_sent is False
        assert result.criteria_status is False
        assert result.articles_count == 2  # Still reports raw count
        # Credit still charged
        mocks["decrement_credit"].assert_awaited_once()
        # Notification NOT called
        mocks["notification_service"].send_pulse_alert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_exec_record_stored_with_correct_params(self):
        """EXEC# record is stored with summary from new_facts and correct is_duplicate flag."""
        news_resp = _make_agent_response("news", [_make_article("http://a.com/1")])
        gov_resp = _make_agent_response("government", [_make_article("http://b.com/1")])

        mock_orchestrator = MagicMock()
        mock_orchestrator.search_news = AsyncMock(side_effect=lambda **kw: news_resp if kw["category"] == "news" else gov_resp)

        mocks = _base_patches()
        mocks["atomic_unit_service"].process_results = AsyncMock(
            return_value=_processing_result(new_facts=[
                {"source_url": "http://a.com/1", "statement": "Brand new"},
            ])
        )
        mocks["exec_dedup_service"].generate_summary_from_facts = AsyncMock(return_value="Brand new discovery")

        with patch(f"{_P}.get_user_email", mocks["get_user_email"]), \
             patch(f"{_P}.PulseOrchestrator", return_value=mock_orchestrator), \
             patch(f"{_EP}.atomic_unit_service", mocks["atomic_unit_service"]), \
             patch(f"{_EP}.exec_dedup_service", mocks["exec_dedup_service"]), \
             patch(f"{_P}.notification_service", mocks["notification_service"]), \
             patch(f"{_EP}.decrement_credit", mocks["decrement_credit"]), \
             patch(f"{_EP}.log_scout_execution", mocks["log_scout_execution"]), \
             patch(f"{_NU}.cross_category_dedup", mocks["cross_category_dedup"]), \
             patch(f"{_P}.UserService", _user_service_mock()):

            from app.routers.pulse import execute_pulse_scout
            result = await execute_pulse_scout(request=_make_request(), _=None)

        store_kwargs = mocks["exec_dedup_service"].store_execution.call_args.kwargs
        assert store_kwargs["summary_text"] == "Brand new discovery"
        assert store_kwargs["is_duplicate"] is False
        assert store_kwargs["scout_type"] == "pulse"
        assert store_kwargs["user_id"] == "user_123"
        assert store_kwargs["scout_name"] == "my-scout"


# ---------------------------------------------------------------------------
# Test: Combined article count in response
# ---------------------------------------------------------------------------

class TestArticleCounts:
    """articles_count reflects the combined raw total from both categories."""

    @pytest.mark.asyncio
    async def test_combined_count_reflects_both_categories(self):
        """3 news + 2 gov = 5 in articles_count."""
        news_resp = _make_agent_response("news", [
            _make_article(f"http://news.no/{i}") for i in range(3)
        ])
        gov_resp = _make_agent_response("government", [
            _make_article(f"http://gov.no/{i}") for i in range(2)
        ])

        mock_orchestrator = MagicMock()
        mock_orchestrator.search_news = AsyncMock(side_effect=lambda **kw: news_resp if kw["category"] == "news" else gov_resp)

        mocks = _base_patches()
        mocks["atomic_unit_service"].process_results = AsyncMock(
            return_value=_processing_result(new_facts=[
                {"source_url": "http://news.no/0", "statement": "Fact"},
            ])
        )

        with patch(f"{_P}.get_user_email", mocks["get_user_email"]), \
             patch(f"{_P}.PulseOrchestrator", return_value=mock_orchestrator), \
             patch(f"{_EP}.atomic_unit_service", mocks["atomic_unit_service"]), \
             patch(f"{_EP}.exec_dedup_service", mocks["exec_dedup_service"]), \
             patch(f"{_P}.notification_service", mocks["notification_service"]), \
             patch(f"{_EP}.decrement_credit", mocks["decrement_credit"]), \
             patch(f"{_EP}.log_scout_execution", mocks["log_scout_execution"]), \
             patch(f"{_NU}.cross_category_dedup", mocks["cross_category_dedup"]), \
             patch(f"{_P}.UserService", _user_service_mock()):

            from app.routers.pulse import execute_pulse_scout
            result = await execute_pulse_scout(request=_make_request(), _=None)

        assert result.articles_count == 5

    @pytest.mark.asyncio
    async def test_single_credit_charged_regardless_of_categories(self):
        """Only 1 credit is charged even though 2 categories are searched."""
        news_resp = _make_agent_response("news", [_make_article("http://a.com/1")])
        gov_resp = _make_agent_response("government", [_make_article("http://b.com/1")])

        mock_orchestrator = MagicMock()
        mock_orchestrator.search_news = AsyncMock(side_effect=lambda **kw: news_resp if kw["category"] == "news" else gov_resp)

        mocks = _base_patches()
        mocks["atomic_unit_service"].process_results = AsyncMock(
            return_value=_processing_result(new_facts=[
                {"source_url": "http://a.com/1", "statement": "Fact"},
            ])
        )

        with patch(f"{_P}.get_user_email", mocks["get_user_email"]), \
             patch(f"{_P}.PulseOrchestrator", return_value=mock_orchestrator), \
             patch(f"{_EP}.atomic_unit_service", mocks["atomic_unit_service"]), \
             patch(f"{_EP}.exec_dedup_service", mocks["exec_dedup_service"]), \
             patch(f"{_P}.notification_service", mocks["notification_service"]), \
             patch(f"{_EP}.decrement_credit", mocks["decrement_credit"]), \
             patch(f"{_EP}.log_scout_execution", mocks["log_scout_execution"]), \
             patch(f"{_NU}.cross_category_dedup", mocks["cross_category_dedup"]), \
             patch(f"{_P}.UserService", _user_service_mock()):

            from app.routers.pulse import execute_pulse_scout
            result = await execute_pulse_scout(request=_make_request(), _=None)

        # decrement_credit called exactly once
        assert mocks["decrement_credit"].await_count == 1


# ---------------------------------------------------------------------------
# Test: Initial run skips unit extraction
# ---------------------------------------------------------------------------

class TestInitialRunSkipsUnitExtraction:
    """Verify that skip_unit_extraction=True skips process_results in pulse pipeline."""

    @pytest.mark.asyncio
    async def test_skip_unit_extraction_flag_skips_process_results(self):
        """PulseExecuteRequest with skip_unit_extraction=True skips atomic_unit_service.process_results."""
        news_resp = _make_agent_response("news", [_make_article("http://a.com/1")])
        gov_resp = _make_agent_response("government", [])

        mock_orchestrator = MagicMock()
        mock_orchestrator.search_news = AsyncMock(side_effect=lambda **kw: news_resp if kw["category"] == "news" else gov_resp)

        mocks = _base_patches()

        req = _make_request()
        # Override with skip_unit_extraction=True
        req = PulseExecuteRequest(
            userId=req.userId,
            scraperName=req.scraperName,
            preferred_language=req.preferred_language,
            location=req.location,
            skip_unit_extraction=True,
            skip_notification=True,
            skip_credit_charge=True,
        )

        with patch(f"{_P}.get_user_email", mocks["get_user_email"]), \
             patch(f"{_P}.PulseOrchestrator", return_value=mock_orchestrator), \
             patch(f"{_EP}.atomic_unit_service", mocks["atomic_unit_service"]), \
             patch(f"{_EP}.exec_dedup_service", mocks["exec_dedup_service"]), \
             patch(f"{_P}.notification_service", mocks["notification_service"]), \
             patch(f"{_EP}.decrement_credit", mocks["decrement_credit"]), \
             patch(f"{_EP}.log_scout_execution", mocks["log_scout_execution"]), \
             patch(f"{_NU}.cross_category_dedup", mocks["cross_category_dedup"]), \
             patch(f"{_P}.UserService", _user_service_mock()):

            from app.routers.pulse import execute_pulse_scout
            result = await execute_pulse_scout(request=req, _=None)

        # process_results should NOT have been called (unit extraction skipped)
        mocks["atomic_unit_service"].process_results.assert_not_awaited()

        # EXEC# record should still be stored
        mocks["exec_dedup_service"].store_execution.assert_awaited_once()
        store_kwargs = mocks["exec_dedup_service"].store_execution.call_args.kwargs
        assert store_kwargs["is_duplicate"] is True
        assert store_kwargs["summary_text"] == "No new findings"

        # Response should be valid
        assert result.scraper_status is True
